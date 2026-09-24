#!/usr/bin/env python3
"""Odoo 19 uyumluluk ve paketleme denetimi (bağımlılıksız, CI için).

Odoo'nun kendi kurulumu bu hataların çoğunu ancak veritabanı kurarken fark eder;
bu script saniyeler içinde, veritabanı olmadan yakalar.

Kullanım:
    python tools/check_odoo19.py addons/            # tüm modüller
    python tools/check_odoo19.py addons/sd_edonusum_tr
Çıkış kodu: ihlal varsa 1, temizse 0.
"""

from __future__ import annotations

import ast
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ODOO_SERIES = "19.0"

# (desen, mesaj) — Odoo 17/18/19'da kaldırılmış ya da hatalı kalıplar
PY_RULES: list[tuple[str, str]] = [
    (r"^\s*_sql_constraints\s*=", "`_sql_constraints` yerine `models.Constraint(...)` (19)"),
    (r"def\s+name_get\s*\(", "`name_get` yerine `_compute_display_name` (17+)"),
    (r"@api\.model\s*\n\s*def\s+create\s*\(\s*self\s*,\s*vals\s*\)",
     "tek kayıt `create` override'ı yerine `@api.model_create_multi` + `vals_list`"),
    (r"\.check_access_(rights|rule)\(", "`check_access_rights/rule` yerine `check_access(op)` (18+)"),
    (r"type\s*=\s*['\"]json['\"]", "`@route(type='json')` yerine `type='jsonrpc'` (19'da deprecated)"),
    (r"\.cr\.commit\(\)", "`cr.commit()` yasak (transaction bütünlüğünü bozar)"),
    (r"cr\.execute\(\s*f[\"']", "f-string ile SQL yasak → `SQL(\"... %s\", value)`"),
    (r"_\(\s*[\"'][^\"']*%[sd][^\"']*[\"']\s*\)\s*%", "`_(\"..%s\") % x` yerine `_(\"..%s\", x)`"),
    (r"\bwith_user\(\s*1\s*\)", "`with_user(1)` yerine `sudo()` ya da `with_user(SUPERUSER_ID)`"),
    (r"except\s+Exception\s*:\s*\n\s*pass", "sessiz `except Exception: pass` — hata görünmez olur"),
]

XML_RULES: list[tuple[str, str]] = [
    (r"\battrs\s*=", "`attrs=` yok (17+) → `invisible=\"<python ifade>\"`"),
    (r"\bstates\s*=\s*\"", "`states=` yok → `invisible=\"state not in (...)\"`"),
    (r"<tree\b", "`<tree>` yerine `<list>` (18+)"),
    (r"view_mode\">[^<]*\btree\b", "`view_mode`'da `tree` yerine `list`"),
    (r"class=\"oe_chatter\"", "`<div class=\"oe_chatter\">` yerine `<chatter/>` (18+)"),
    (r"t-name=\"kanban-box\"", "kanban `t-name=\"kanban-box\"` yerine `card` (18+)"),
    (r"<field name=\"category_id\"[^>]*/>\s*(?=.*res\.groups)", ""),  # aşağıda bağlamla kontrol edilir
    (r"<group[^>]*\bexpand=", "`<search>` içinde `<group expand=...>` 19'da geçersiz → `<separator/>` + filtre"),
]

ACCESS_HEADER = [
    "id", "name", "model_id:id", "group_id:id",
    "perm_read", "perm_write", "perm_create", "perm_unlink",
]


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check_python(path: Path) -> list[str]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern, message in PY_RULES:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            issues.append(f"{path}:{line_of(text, match.start())}: {message}")
    return issues


def check_manifest(path: Path) -> list[str]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = ast.literal_eval(text)
    except (SyntaxError, ValueError) as exc:
        return [f"{path}: manifest okunamadı: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: manifest bir sözlük olmalı"]

    for key in ("name", "version", "license", "depends"):
        if key not in data:
            issues.append(f"{path}: zorunlu anahtar eksik: `{key}`")

    version = str(data.get("version", ""))
    if version and not version.startswith(f"{ODOO_SERIES}."):
        issues.append(f"{path}: version `{version}` → `{ODOO_SERIES}.x.y.z` olmalı")

    data_files = list(data.get("data", []))
    module_dir = path.parent
    for rel in data_files:
        if not (module_dir / rel).is_file():
            issues.append(f"{path}: `data` listesindeki dosya yok: {rel}")

    security = [i for i, f in enumerate(data_files) if f.startswith("security/")]
    others = [i for i, f in enumerate(data_files) if not f.startswith("security/")]
    if security and others and min(others) < max(security):
        issues.append(f"{path}: security/ dosyaları `data` listesinde en başta olmalı")

    # Menü bir action'a referans veriyorsa, action dosyası menüden ÖNCE yüklenmeli
    positions = {name: index for index, name in enumerate(data_files)}
    for rel, index in positions.items():
        if not rel.endswith(".xml"):
            continue
        source = (module_dir / rel)
        if not source.is_file():
            continue
        content = source.read_text(encoding="utf-8", errors="replace")
        for ref in re.findall(r'<menuitem[^>]*action="([\w.]+)"', content):
            target = ref.split(".")[-1]
            defined_at = next(
                (positions[other] for other in data_files
                 if other.endswith(".xml") and (module_dir / other).is_file()
                 and f'id="{target}"' in (module_dir / other).read_text(encoding="utf-8", errors="replace")),
                None,
            )
            if defined_at is not None and defined_at > index:
                issues.append(
                    f"{path}: `{rel}` menüsü `{ref}` action'ına referans veriyor ama o dosya "
                    f"`data` listesinde daha sonra yükleniyor"
                )

    web_icons = []
    for rel in data_files:
        source = module_dir / rel
        if source.is_file() and rel.endswith(".xml"):
            web_icons += re.findall(r'web_icon="([^"]+)"', source.read_text(encoding="utf-8", errors="replace"))
    for icon in web_icons:
        if "," in icon:
            icon_module, icon_path = icon.split(",", 1)
            candidate = module_dir / icon_path if icon_module == module_dir.name else None
            if candidate is not None and not candidate.is_file():
                issues.append(f"{path}: `web_icon` dosyası yok: {icon_path}")
    return issues


def check_xml(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        return [f"{path}: XML hatası: {exc}"]
    text = path.read_text(encoding="utf-8", errors="replace")

    for pattern, message in XML_RULES:
        if not message:
            continue
        for match in re.finditer(pattern, text):
            issues.append(f"{path}:{line_of(text, match.start())}: {message}")

    # res.groups kayıtlarında category_id 19'da yok (privilege_id ile değişti)
    for match in re.finditer(r'<record[^>]*model="res\.groups"[\s\S]*?</record>', text):
        block = match.group(0)
        if 'name="category_id"' in block:
            issues.append(
                f"{path}:{line_of(text, match.start())}: `res.groups.category_id` 19'da yok → "
                "`privilege_id` (`res.groups.privilege`)"
            )
    return issues


def check_access_csv(path: Path) -> list[str]:
    issues: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return [f"{path}: dosya boş"]
    if rows[0] != ACCESS_HEADER:
        return [f"{path}: başlık satırı `{','.join(ACCESS_HEADER)}` olmalı"]
    for number, row in enumerate(rows[1:], start=2):
        if not row or row[0].startswith("#"):
            continue
        if len(row) != len(ACCESS_HEADER):
            issues.append(f"{path}:{number}: {len(row)} sütun var, {len(ACCESS_HEADER)} bekleniyor")
        elif not row[2].startswith("model_") and "." not in row[2]:
            issues.append(f"{path}:{number}: `model_id:id` `model_<ad>` biçiminde olmalı")
    return issues


def check_module(module_dir: Path) -> list[str]:
    """Bir modül klasörünü denetler; ayrıca her modelin ACL'si var mı bakar."""
    issues: list[str] = []
    manifest = module_dir / "__manifest__.py"
    if manifest.is_file():
        issues += check_manifest(manifest)

    for path in sorted(module_dir.rglob("*")):
        if any(part in {".git", "__pycache__", "static"} for part in path.parts):
            continue
        if path.suffix == ".py" and path.name != "__manifest__.py":
            issues += check_python(path)
        elif path.suffix == ".xml":
            issues += check_xml(path)
        elif path.name == "ir.model.access.csv":
            issues += check_access_csv(path)

    # Yeni model tanımlanmış ama ACL satırı yok mu?
    declared: set[str] = set()
    for path in (module_dir / "models").rglob("*.py") if (module_dir / "models").is_dir() else []:
        content = path.read_text(encoding="utf-8", errors="replace")
        declared |= set(re.findall(r'^\s*_name\s*=\s*["\']([\w.]+)["\']', content, flags=re.MULTILINE))
    access_file = module_dir / "security" / "ir.model.access.csv"
    granted = ""
    if access_file.is_file():
        granted = access_file.read_text(encoding="utf-8", errors="replace")
    for model in sorted(declared):
        token = "model_" + model.replace(".", "_")
        if token not in granted:
            issues.append(f"{module_dir}: `{model}` modeli için ACL satırı yok ({token})")
    return issues


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [Path("addons")]
    modules: list[Path] = []
    for target in targets:
        if (target / "__manifest__.py").is_file():
            modules.append(target)
        else:
            modules += sorted(p.parent for p in target.rglob("__manifest__.py"))

    if not modules:
        print("Denetlenecek modül bulunamadı.")
        return 0

    total = 0
    for module in modules:
        # Kurulamaz işaretli modüller denetlenmez: kasıtlı olarak emekliye ayrılmışlardır.
        # Biri yeniden `installable: True` yaparsa bulgular otomatik geri döner.
        manifest = module / "__manifest__.py"
        if manifest.is_file():
            try:
                if ast.literal_eval(manifest.read_text(encoding="utf-8")).get("installable", True) is False:
                    print(f"\n== {module}  →  atlandı (installable: False)")
                    continue
            except (SyntaxError, ValueError):
                pass
        issues = check_module(module)
        status = f"{len(issues)} bulgu" if issues else "temiz"
        print(f"\n== {module}  →  {status}")
        for issue in issues:
            print(f"  - {issue}")
        total += len(issues)

    print(f"\nToplam: {total} bulgu / {len(modules)} modül")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

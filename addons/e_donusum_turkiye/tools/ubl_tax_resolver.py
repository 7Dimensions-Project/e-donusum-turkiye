# -*- coding: utf-8 -*-
"""
UBL Turkish Tax Resolver Engine for Odoo E-Dönüşüm Türkiye.
Dynamically maps UBL tax codes to Odoo account.tax records per company.
Supports multi-tax lines, tevkifat fractions, konaklama vergisi, ÖİV, ÖTV,
damga, and bsmv.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ubl_tax_resolver")

class UBLTaxResolver:
    """Dynamic Tax Resolver for Turkish GİB Taxes."""

    def __init__(self, env):
        self.env = env
        self.tax_model = env['account.tax']
        self._cache = {}

    def _get_company_taxes(self, company_id: int, tax_type: str = 'purchase'):
        cache_key = (company_id, tax_type)
        if cache_key in self._cache:
            return self._cache[cache_key]

        taxes = self.tax_model.search([
            ('company_id', '=', company_id),
            ('type_tax_use', '=', tax_type)
        ])
        self._cache[cache_key] = taxes
        return taxes

    def resolve_line_taxes(self, line_tax_nodes: List[Dict[str, Any]],
                           line_withholding: Optional[Dict[str, Any]],
                           company_id: int,
                           is_purchase: bool = True) -> List[int]:
        """
        Given parsed tax dictionaries for an invoice line and withholding,
        returns list of Odoo account.tax IDs.
        """
        tax_type = 'purchase' if is_purchase else 'sale'
        taxes = self._get_company_taxes(company_id, tax_type)
        resolved_ids = []

        wh_pct = line_withholding.get('percent', 0.0) if line_withholding else 0.0
        if 0 < wh_pct < 1.0:
            wh_pct *= 100.0

        for t_info in line_tax_nodes:
            code = (t_info.get('code') or '').strip()
            name = (t_info.get('name') or '').strip().upper()
            pct = float(t_info.get('percent', 0.0))

            # A. KDV (0015 or Name containing KDV/VAT)
            if code == '0015' or 'KDV' in name or 'VAT' in name:
                if wh_pct > 0 and round(pct) == 20:
                    # Tevkifat applies!
                    matched = self._find_tevkifat_tax(taxes, pct, wh_pct)
                    if matched and matched.id not in resolved_ids:
                        resolved_ids.append(matched.id)
                else:
                    matched = self._find_kdv_tax(taxes, pct)
                    if matched and matched.id not in resolved_ids:
                        resolved_ids.append(matched.id)

            # B. Konaklama Vergisi (0059 or Name containing KONAKLAMA)
            elif code == '0059' or 'KONAKLAMA' in name:
                matched = self._find_konaklama_tax(taxes, pct)
                if matched and matched.id not in resolved_ids:
                    resolved_ids.append(matched.id)

            # C. ÖİV (4080 or Name containing ÖİV/OIV/İLETİŞİM)
            elif code == '4080' or 'ÖİV' in name or 'OIV' in name or 'İLETİŞİM' in name:
                matched = self._find_tax_by_keywords(taxes, ['öiv', 'oiv', 'iletişim'], pct)
                if matched and matched.id not in resolved_ids:
                    resolved_ids.append(matched.id)

            # D. ÖTV (0071..0077 or Name containing ÖTV/OTV)
            elif (code.startswith('007') and len(code) == 4) or 'ÖTV' in name or 'OTV' in name:
                matched = self._find_tax_by_keywords(taxes, ['ötv', 'otv'], pct)
                if matched and matched.id not in resolved_ids:
                    resolved_ids.append(matched.id)

            # E. BSMV (0021)
            elif code == '0021' or 'BSMV' in name:
                matched = self._find_tax_by_keywords(taxes, ['bsmv'], pct)
                if matched and matched.id not in resolved_ids:
                    resolved_ids.append(matched.id)

            # F. Damga Vergisi (0040)
            elif code in ('0040', '1047') or 'DAMGA' in name:
                matched = self._find_tax_by_keywords(taxes, ['damga', 'stamp'], pct)
                if matched and matched.id not in resolved_ids:
                    resolved_ids.append(matched.id)

        # Fallback if no taxes were parsed but line has standard VAT
        if not resolved_ids and not line_tax_nodes:
            fallback = self._find_kdv_tax(taxes, 20.0)
            if fallback:
                resolved_ids.append(fallback.id)

        return resolved_ids

    def _find_kdv_tax(self, taxes, pct: float):
        target = round(pct)
        # 1. Exact amount match and name contains KDV
        for t in taxes:
            if round(t.amount) == target and ('kdv' in t.name.lower() or 'vat' in t.name.lower()):
                if 'wh' not in t.name.lower() and 'tevkifat' not in t.name.lower():
                    return t
        # 2. Simple amount match without withholding
        for t in taxes:
            if round(t.amount) == target and 'wh' not in t.name.lower() and 'tevkifat' not in t.name.lower():
                return t
        return None

    def _find_tevkifat_tax(self, taxes, vat_pct: float, wh_pct: float):
        fraction_map = {
            20.0: '2/10', 30.0: '3/10', 40.0: '4/10', 50.0: '5/10',
            70.0: '7/10', 90.0: '9/10', 100.0: '10/10'
        }
        frac = fraction_map.get(round(wh_pct, 1))

        # Check for matching fraction in tax name or description
        for t in taxes:
            tname = (t.name or '').lower()
            tdesc = (t.description or '').lower()
            if frac and (frac in tname or frac in tdesc):
                return t
        return None

    def _find_konaklama_tax(self, taxes, pct: float):
        target = round(pct)
        for t in taxes:
            tname = (t.name or '').lower()
            if 'konaklama' in tname:
                if round(t.amount) == target or target == 0:
                    return t
        # Fallback: any konaklama tax
        for t in taxes:
            if 'konaklama' in (t.name or '').lower():
                return t
        return None

    def _find_tax_by_keywords(self, taxes, keywords: List[str], pct: float):
        target = round(pct)
        for t in taxes:
            tname = (t.name or '').lower()
            if any(k in tname for k in keywords):
                if target == 0 or round(t.amount) == target:
                    return t
        return None

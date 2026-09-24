# -*- coding: utf-8 -*-
"""
Integrator Factory for E-Dönüşüm Türkiye.
Dynamically resolves and instantiates the correct integrator (Nilvera, Paraşüt, Uyumsoft)
based on company settings.
"""

from .base_integrator import BaseIntegrator
from .nilvera_adapter import NilveraIntegrator
from .parasut_adapter import ParasutIntegrator
from .uyumsoft_adapter import UyumsoftIntegrator

def get_integrator(company) -> BaseIntegrator:
    """Returns the configured integrator instance for the given company."""
    provider = getattr(company, 'edonusum_provider', 'nilvera') or 'nilvera'
    if provider == 'parasut':
        return ParasutIntegrator(company)
    elif provider == 'uyumsoft':
        return UyumsoftIntegrator(company)
    else:
        return NilveraIntegrator(company)

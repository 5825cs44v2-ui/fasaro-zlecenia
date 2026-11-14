"""Rejestr źródeł."""

from __future__ import annotations

from . import bip_kk, bzp, epropublico, oferteo

SOURCES = [
    ("bzp", "BZP / e-Zamówienia", bzp),
    ("epropublico", "e-ProPublico (K-K)", epropublico),
    ("bip_kk", "BIP Kędzierzyn-Koźle", bip_kk),
    ("oferteo", "Oferteo", oferteo),
]

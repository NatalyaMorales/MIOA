"""
Utilidades de formateo para la interfaz (Streamlit).

Este módulo es puramente de presentación: no contiene lógica de
negocio ni cálculos del MMM. Solo transforma valores numéricos en
texto legible para el usuario de Marketing / Insights & Analytics.
"""
from __future__ import annotations


def format_abbreviated_currency(value: float, currency_symbol: str = "$") -> str:
    """
    Da formato abreviado a un valor monetario en MXN.
    Ejemplos: 2_000_000 -> "$2.0M", 185_432 -> "$185.4K"
    """
    sign = "-" if value < 0 else ""
    value = abs(value)

    if value >= 1_000_000_000:
        return f"{sign}{currency_symbol}{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{sign}{currency_symbol}{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}{currency_symbol}{value / 1_000:.1f}K"
    return f"{sign}{currency_symbol}{value:,.2f}"


def format_abbreviated_number(value: float) -> str:
    """
    Igual que format_abbreviated_currency, pero sin símbolo de
    moneda. Se utiliza para Expected Response, ya que esta métrica
    no siempre representa un valor monetario.
    """
    return format_abbreviated_currency(value, currency_symbol="")


def format_full_currency(value: float) -> str:
    """Formato completo en MXN, por ejemplo: "$2,000,000.00 MXN"."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f} MXN"


def format_number(value: float, decimals: int = 2) -> str:
    """Formato completo con separadores de miles."""
    return f"{value:,.{decimals}f}"

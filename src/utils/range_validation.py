"""
Validación del rango histórico de spend.

Las curvas del MMM solo son confiables dentro (o cerca) del rango de
inversión observado históricamente (Min_Spend_Real / Max_Spend_Real).
Este módulo centraliza la regla para que TODOS los módulos de la
aplicación (Descriptive Analysis, Channel Optimization y Total Budget
Optimization) usen exactamente el mismo criterio:

    Se advierte cuando el spend está más de 20% por debajo del
    mínimo histórico o más de 20% por arriba del máximo histórico.
"""
from __future__ import annotations

import math

OUT_OF_RANGE_TOLERANCE = 0.20  # 20%


def clean_bound(value) -> float | None:
    """Convierte un límite del Excel a float, o None si falta/es inválido (NaN, vacío, <= 0)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number <= 0:
        return None
    return number


def spend_range_status(
    spend: float,
    min_spend_real: float | None,
    max_spend_real: float | None,
    tolerance: float = OUT_OF_RANGE_TOLERANCE,
) -> str:
    """
    Returns
    -------
    "below"   : spend < min_spend_real * (1 - tolerance)
    "above"   : spend > max_spend_real * (1 + tolerance)
    "within"  : dentro del rango con tolerancia
    "unknown" : no hay rango histórico disponible para validar
    """
    min_real = clean_bound(min_spend_real)
    max_real = clean_bound(max_spend_real)

    if min_real is None and max_real is None:
        return "unknown"

    if min_real is not None and spend < min_real * (1 - tolerance):
        return "below"
    if max_real is not None and spend > max_real * (1 + tolerance):
        return "above"
    return "within"


def is_out_of_range(
    spend: float,
    min_spend_real: float | None,
    max_spend_real: float | None,
    tolerance: float = OUT_OF_RANGE_TOLERANCE,
) -> bool:
    return spend_range_status(spend, min_spend_real, max_spend_real, tolerance) in {"below", "above"}

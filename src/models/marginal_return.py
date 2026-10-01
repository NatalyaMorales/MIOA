"""
Retorno marginal de una curva de respuesta.

Retorno marginal = cuánto Expected Response adicional se obtiene por
cada peso adicional invertido en el nivel de spend actual, es decir,
la derivada de la curva: d(Response) / d(Spend).

Se calcula de forma numérica (diferencias finitas) llamando a
calculate_expected_response(), por lo que funciona para el Modelo 1 y
el Modelo 2 sin reimplementar ninguna ecuación del MMM.

Diferencia con el ROI: el ROI (Response / Spend) es el retorno
PROMEDIO de toda la inversión; el retorno marginal es el retorno del
ÚLTIMO peso invertido. La asignación óptima de un presupuesto se da
donde los retornos marginales de los medios con inversión se igualan.
"""
from __future__ import annotations

from src.models.response_curves import calculate_expected_response


def calculate_marginal_return(
    spend: float,
    model: str,
    curve_a: float,
    curve_b: float,
    curve_c: float,
    relative_step: float = 1e-4,
) -> float:
    """
    Aproxima d(Response)/d(Spend) en `spend`.

    Usa diferencia central cuando es posible y diferencia hacia
    adelante cerca de 0 (donde la función se define como 0 para
    spend <= 0). Devuelve 0.0 si spend <= 0.
    """
    if spend <= 0:
        return 0.0

    step = max(spend * relative_step, 1.0)

    def response(value: float) -> float:
        return calculate_expected_response(
            spend=value, model=model, curve_a=curve_a, curve_b=curve_b, curve_c=curve_c
        )

    if spend - step > 0:
        return float((response(spend + step) - response(spend - step)) / (2 * step))

    return float((response(spend + step) - response(spend)) / step)

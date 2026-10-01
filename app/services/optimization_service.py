"""
Capa de orquestación entre la UI de Budget Optimization y el motor
de optimización existente (src/services/optimization_agent.py).

No contiene lógica de optimización ni ecuaciones del MMM. Solo:
- Arma `media_params` (modelo + curve_a/b/c por medio) a partir del
  DataFrame de curvas, reutilizando get_response_curve().
- Delega cada modo de optimización a optimization_agent.
"""
from __future__ import annotations

import pandas as pd

from src.models.response_curves import get_response_curve
from src.services import optimization_agent
from src.utils.range_validation import clean_bound


def get_media_params(response_curve: pd.DataFrame, marca: str, media_list: list[str]) -> dict[str, dict]:
    """
    Obtiene modelo y parámetros de curva por medio. Se reutiliza
    get_response_curve() (con un spend "dummy" de 0, ya que aquí
    solo interesan los parámetros de la curva, no un Expected
    Response puntual).
    """
    media_params: dict[str, dict] = {}
    for medio in media_list:
        row = get_response_curve(
            response_curve=response_curve,
            marca=marca,
            medio=medio,
            proposed_spend=0.0,
        ).iloc[0]

        media_params[medio] = {
            "modelo": row["Modelo"],
            "curve_a": float(row["curve_a"]),
            "curve_b": float(row["curve_b"]),
            "curve_c": float(row["curve_c"]),
            # Rango histórico observado (puede faltar en el Excel -> None)
            "min_spend_real": clean_bound(row.get("Min_Spend_Real")),
            "max_spend_real": clean_bound(row.get("Max_Spend_Real")),
        }

    return media_params


def run_simple_shift(
    response_curve: pd.DataFrame,
    marca: str,
    base_spend_by_media: dict[str, float],
    pct_up_by_media: dict[str, float],
    pct_down_by_media: dict[str, float],
) -> dict:
    media_params = get_media_params(response_curve, marca, list(base_spend_by_media.keys()))
    return optimization_agent.optimize_simple_shift(
        media_params, base_spend_by_media, pct_up_by_media, pct_down_by_media
    )


def run_fixed_budget(
    response_curve: pd.DataFrame,
    marca: str,
    base_spend_by_media: dict[str, float],
    pct_up_by_media: dict[str, float],
    pct_down_by_media: dict[str, float],
) -> dict:
    media_params = get_media_params(response_curve, marca, list(base_spend_by_media.keys()))
    return optimization_agent.optimize_fixed_budget(
        media_params, base_spend_by_media, pct_up_by_media, pct_down_by_media
    )


def run_target(
    response_curve: pd.DataFrame,
    marca: str,
    base_spend_by_media: dict[str, float],
    pct_up_by_media: dict[str, float],
    pct_down_by_media: dict[str, float],
    target_value: float,
    target_metric: str,
) -> dict:
    media_params = get_media_params(response_curve, marca, list(base_spend_by_media.keys()))
    return optimization_agent.optimize_target(
        media_params,
        base_spend_by_media,
        pct_up_by_media,
        pct_down_by_media,
        target_value,
        target_metric,
    )


def run_both_ways(
    response_curve: pd.DataFrame,
    marca: str,
    base_spend_by_media: dict[str, float],
    pct_up_by_media: dict[str, float],
    pct_down_by_media: dict[str, float],
) -> dict:
    media_params = get_media_params(response_curve, marca, list(base_spend_by_media.keys()))
    return optimization_agent.optimize_both_ways(
        media_params, base_spend_by_media, pct_up_by_media, pct_down_by_media
    )


def run_total_budget(
    response_curve: pd.DataFrame,
    marca: str,
    media_list: list[str],
    total_budget: float,
    min_spend_by_media: dict[str, float] | None = None,
    max_spend_by_media: dict[str, float] | None = None,
) -> dict:
    """
    Reparte un presupuesto total entre los medios seleccionados,
    maximizando el Expected Response total. No requiere escenario
    base.
    """
    media_params = get_media_params(response_curve, marca, media_list)
    return optimization_agent.optimize_total_budget(
        media_params,
        total_budget=total_budget,
        media_list=media_list,
        min_spend_by_media=min_spend_by_media,
        max_spend_by_media=max_spend_by_media,
    )

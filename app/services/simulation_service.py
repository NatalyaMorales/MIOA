"""
Capa de orquestación entre la interfaz gráfica (Streamlit) y los
servicios de negocio ya existentes del proyecto.

Este módulo NO contiene ecuaciones del MMM. Únicamente:

- Carga y cachea las curvas de respuesta (único punto de acceso
  a data/input/response_curves.xlsx, vía DATA_PATH).
- Expone utilidades para poblar dinámicamente los inputs de la UI
  (marcas / medios disponibles).
- Orquesta llamadas a las funciones ya existentes del proyecto:
    - load_response_curves()
    - simulate_spend()
    - get_response_curve()
    - calculate_expected_response()

Toda la matemática del MMM permanece en src/models/response_curves.py.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import DATA_PATH
from src.data.loader import load_response_curves
from src.services.descriptive_agent import simulate_spend
from src.models.marginal_return import calculate_marginal_return
from src.models.response_curves import get_response_curve, calculate_expected_response
from src.utils.range_validation import (
    OUT_OF_RANGE_TOLERANCE,
    clean_bound,
    is_out_of_range,
    spend_range_status,
)


# Número de puntos utilizados para dibujar la curva de respuesta.
CURVE_POINTS = 200


@st.cache_data(show_spinner="Loading response curves...")
def get_response_curves(path: str = DATA_PATH) -> pd.DataFrame:
    """
    Carga (y cachea en la sesión de Streamlit) las curvas de
    respuesta del MMM. Este es el único punto de la interfaz donde
    se lee el Excel, a través de DATA_PATH (src/config/settings.py),
    para facilitar un futuro cambio/actualización del MMM.
    """
    return load_response_curves(path)


def get_available_brands(response_curve: pd.DataFrame) -> list[str]:
    """Marcas disponibles, obtenidas dinámicamente del DataFrame."""
    return sorted(response_curve["Marca"].dropna().unique().tolist())


def get_available_media(response_curve: pd.DataFrame, marca: str) -> list[str]:
    """Medios disponibles para una marca, obtenidos dinámicamente."""
    filtered = response_curve.loc[response_curve["Marca"] == marca]
    return sorted(filtered["Medio"].dropna().unique().tolist())


def run_simulation(
    response_curve: pd.DataFrame,
    marca: str,
    medio: str,
    proposed_spend: float,
) -> dict:
    """
    Ejecuta la simulación descriptiva reutilizando simulate_spend()
    (motor de cálculo existente) y enriquece el resultado con
    información de contexto (rango histórico de spend, Spend Óptimo,
    R²) obtenida directamente de get_response_curve(), que ya
    conserva todas las columnas originales del Excel. No se
    duplica ningún cálculo del MMM.
    """
    result = simulate_spend(
        response_curve=response_curve,
        marca=marca,
        medio=medio,
        proposed_spend=proposed_spend,
    )

    curve_row = get_response_curve(
        response_curve=response_curve,
        marca=marca,
        medio=medio,
        proposed_spend=proposed_spend,
    ).iloc[0]

    # Rango histórico (None si falta o es inválido en el Excel)
    result["min_spend_real"] = clean_bound(curve_row.get("Min_Spend_Real"))
    result["max_spend_real"] = clean_bound(curve_row.get("Max_Spend_Real"))

    spend_optimo = curve_row.get("Spend_Optimo")
    result["spend_optimo"] = float(spend_optimo) if pd.notna(spend_optimo) else None

    r_squared = curve_row.get("R_squared")
    result["r_squared"] = float(r_squared) if pd.notna(r_squared) else None

    result["range_status"] = spend_range_status(
        proposed_spend, result["min_spend_real"], result["max_spend_real"]
    )
    result["out_of_historical_range"] = result["range_status"] in {"below", "above"}

    params = result["curve_parameters"]
    result["marginal_return"] = calculate_marginal_return(
        spend=proposed_spend,
        model=result["modelo"],
        curve_a=params["curve_a"],
        curve_b=params["curve_b"],
        curve_c=params["curve_c"],
    )

    return result


def is_spend_out_of_historical_range(
    proposed_spend: float,
    min_spend_real: float | None,
    max_spend_real: float | None,
    tolerance: float = OUT_OF_RANGE_TOLERANCE,
) -> bool:
    """Wrapper de la regla compartida (src/utils/range_validation.py)."""
    return is_out_of_range(proposed_spend, min_spend_real, max_spend_real, tolerance)


def run_batch_simulation(
    response_curve: pd.DataFrame,
    marca: str,
    spend_by_media: dict[str, float],
) -> tuple[dict[str, dict], dict[str, str]]:
    """
    Ejecuta run_simulation() para varios medios de una misma marca
    a la vez (una fila por medio, como en la tabla de resultados).

    Reutiliza run_simulation() -> simulate_spend() para cada medio;
    no duplica ningún cálculo del MMM. Los errores por medio
    (por ejemplo, curvas duplicadas) se capturan de forma individual
    para no interrumpir la simulación de los demás medios.

    Returns
    -------
    (results, errors)
        results: {medio: result_dict} para los medios simulados con éxito.
        errors: {medio: mensaje} para los medios que fallaron.
    """
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for medio, proposed_spend in spend_by_media.items():
        try:
            results[medio] = run_simulation(
                response_curve=response_curve,
                marca=marca,
                medio=medio,
                proposed_spend=proposed_spend,
            )
        except ValueError as error:
            errors[medio] = str(error)
        except Exception:
            errors[medio] = "Unexpected error while running the simulation."

    return results, errors


def build_response_curve_series(
    modelo: str,
    curve_a: float,
    curve_b: float,
    curve_c: float,
    max_spend_real: float | None,
    proposed_spend: float,
    n_points: int = CURVE_POINTS,
) -> pd.DataFrame:
    """
    Genera puntos (spend, expected_response) para graficar la curva
    de respuesta, reutilizando calculate_expected_response() del
    motor existente (src/models/response_curves.py) para cada punto.

    NO reimplementa las ecuaciones del MMM: solo evalúa la función
    ya existente sobre un rango de spend.
    """
    upper_bound = max(max_spend_real or 0.0, proposed_spend, 1.0) * 1.2

    spends = pd.Series(
        data=[i * (upper_bound / (n_points - 1)) for i in range(n_points)],
        name="spend",
    )

    responses = spends.apply(
        lambda spend: calculate_expected_response(
            spend=spend,
            model=modelo,
            curve_a=curve_a,
            curve_b=curve_b,
            curve_c=curve_c,
        )
    )

    return pd.DataFrame({"spend": spends, "expected_response": responses})

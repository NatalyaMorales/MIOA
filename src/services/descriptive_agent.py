import pandas as pd

from src.models.response_curves import get_response_curve


def calculate_roi(expected_response: float, proposed_spend: float) -> float:
    """
    Calcula ROI simple:
        ROI = Expected Response / Spend
    """
    if proposed_spend <= 0:
        return 0.0

    return expected_response / proposed_spend


def calculate_roas(expected_revenue: float, proposed_spend: float) -> float:
    """
    Calcula ROAS:
        ROAS = Revenue / Spend
    """
    if proposed_spend <= 0:
        return 0.0

    return expected_revenue / proposed_spend


def simulate_spend(response_curve: pd.DataFrame, marca: str, medio: str, proposed_spend: float) -> dict:
    """
    Ejecuta una simulación descriptiva de inversión.

    Parameters
    ----------
    response_curve : pd.DataFrame
        Tabla con las curvas de respuesta del MMM.

    marca : str
        Marca a analizar.

    medio : str
        Medio a analizar.

    proposed_spend : float
        Inversión propuesta.

    Returns
    -------
    dict
        Resultado estructurado para consumo posterior
        por una interfaz gráfica o API.
    """

    result = get_response_curve(response_curve=response_curve, marca=marca, medio=medio, proposed_spend=proposed_spend)

    # En principio esperamos un único modelo
    if len(result) > 1:
        raise ValueError(
            "Se encontraron múltiples curvas para "
            f"Marca='{marca}' y Medio='{medio}'. "
            "Es necesario definir cómo seleccionar el modelo."
        )

    row = result.iloc[0]

    expected_response = float(row["Expected Response"])

    roi = calculate_roi(expected_response=expected_response, proposed_spend=proposed_spend)

    return {
        "marca": marca,
        "medio": medio,
        "modelo": row["Modelo"],
        "proposed_spend": proposed_spend,
        "expected_response": expected_response,
        "roi": roi,
        "curve_parameters": {
            "curve_a": float(row["curve_a"]),
            "curve_b": float(row["curve_b"]),
            "curve_c": float(row["curve_c"])
        }
    }
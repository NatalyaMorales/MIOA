import numpy as np
import pandas as pd


def calculate_model_1(spend: float, curve_a: float, curve_b: float, curve_c: float) -> float:
    """
    Calcula el Expected Response utilizando el Modelo 1.
    """

    return curve_a / (1 + np.exp(-curve_b * (spend - curve_c)))


def calculate_model_2(spend: float, curve_a: float, curve_b: float, curve_c: float) -> float:
    """
    Calcula el Expected Response utilizando el Modelo 2.
    """
    normalized_spend = spend / 100_000_000
    numerator = normalized_spend ** curve_a
    denominator = (curve_b ** curve_a + normalized_spend ** curve_a)

    return (100_000_000 * curve_c * (numerator / denominator))


def calculate_expected_response(spend: float, model: str, curve_a: float, curve_b: float, curve_c: float) -> float:
    """
    Calcula el Expected Response dependiendo del modelo.
    """
    if spend <= 0:
        return 0.0

    if model == "Modelo 1":
        return calculate_model_1(spend, curve_a, curve_b, curve_c)

    if model == "Modelo 2":
        return calculate_model_2(spend, curve_a, curve_b, curve_c)

    raise ValueError(f"Modelo no soportado: {model}")


def get_response_curve(response_curve: pd.DataFrame, marca: str, medio: str, proposed_spend: float) -> pd.DataFrame:
    """
    Filtra una marca/medio y calcula el Expected Response.
    """

    if proposed_spend < 0:
        raise ValueError("Proposed Spend no puede ser negativo.")

    df = response_curve.copy()

    mask = ((df["Marca"] == marca) & (df["Medio"] == medio))

    result = df.loc[mask].copy()

    if result.empty:
        raise ValueError(f"No se encontró información para "
                        f"Marca='{marca}' y Medio='{medio}'.")

    result["Proposed Spend"] = proposed_spend

    result["Expected Response"] = result.apply(
        lambda row: calculate_expected_response(spend=row["Proposed Spend"], model=row["Modelo"], curve_a=row["curve_a"], 
                                                curve_b=row["curve_b"], curve_c=row["curve_c"]), axis=1)

    return result
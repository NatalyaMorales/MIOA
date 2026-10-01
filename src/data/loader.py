from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["Marca",
                    "Medio",
                    "Modelo",
                    "curve_a",
                    "curve_b",
                    "curve_c"]


def load_response_curves(path: str | Path) -> pd.DataFrame:
    """
    Carga las curvas de respuesta desde Excel.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    df = pd.read_excel(path)
    validate_response_curve_data(df)

    return df


def validate_response_curve_data(df: pd.DataFrame) -> None:
    """
    Valida que la tabla tenga las columnas necesarias.
    """

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Faltan las siguientes columnas: "
            + ", ".join(missing_columns)
        )

    numeric_columns = [
        "curve_a",
        "curve_b",
        "curve_c"
    ]

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(
            df[column]
        ):
            raise TypeError(
                f"La columna '{column}' "
                "debe ser numérica."
            )

    if df.empty:
        raise ValueError(
            "El archivo de curvas está vacío."
        )
"""
Componente de UI: selección de Brand y Media (sidebar).

No contiene lógica de negocio; únicamente arma los controles y
recolecta la selección del usuario. Los datos disponibles (marcas
y medios) se obtienen dinámicamente a través de simulation_service.

El Proposed Spend por medio se configura por separado, en la tabla
editable de app/components/spend_table.py, ya que ahora se puede
simular más de un medio a la vez.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.services import simulation_service


def render_sidebar_inputs(response_curve: pd.DataFrame) -> tuple[str, list[str]]:
    """
    Renderiza los inputs de Brand / Media en el sidebar.

    Al cambiar de Brand, la selección de Media se reinicia a
    "todos los medios disponibles para esa marca", y se limpian
    los Proposed Spend capturados previamente.

    Returns
    -------
    (marca, selected_media)
    """
    st.sidebar.subheader("Simulation Inputs")

    marcas = simulation_service.get_available_brands(response_curve)
    marca = st.sidebar.selectbox("Brand", options=marcas, key="input_marca")

    available_media = simulation_service.get_available_media(response_curve, marca)

    if st.session_state.get("_previous_marca") != marca:
        st.session_state["input_media"] = available_media
        st.session_state["spend_by_media"] = {}
        st.session_state["_previous_marca"] = marca

    selected_media = st.sidebar.multiselect(
        "Media",
        options=available_media,
        key="input_media",
        help="Select one or more Media to simulate at once.",
    )

    return marca, selected_media

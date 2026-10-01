"""
Componente de UI: tabla editable de Spend para uno o varios medios
a la vez.

Es genérico para poder reutilizarse tanto en:
- Descriptive Analysis (Proposed Spend a simular), y
- Budget Optimization (Escenario Base a optimizar).

No contiene lógica de negocio: solo recolecta el spend por medio y,
opcionalmente, el clic de un botón de acción.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

DEFAULT_SPEND = 1_000_000.0


def render_spend_table(
    selected_media: list[str],
    session_key: str = "spend_by_media",
    title: str | None = "Simulation Inputs",
    button_label: str | None = "Run Simulation",
    show_run_button: bool = True,
) -> tuple[dict[str, float], bool]:
    """
    Renderiza una tabla editable con una fila por medio seleccionado
    y su Spend, más (opcionalmente) un botón de acción.

    Los valores capturados se mantienen en
    st.session_state[session_key] entre reruns: al agregar o quitar
    un medio no se pierden los montos ya editados para los medios
    que siguen seleccionados.

    Returns
    -------
    (spend_by_media, button_clicked)
        button_clicked es False si show_run_button=False.
    """
    if title:
        st.subheader(title)

    if not selected_media:
        st.info("Select at least one Media in the sidebar to configure a Spend.")
        return {}, False

    if session_key not in st.session_state:
        st.session_state[session_key] = {}

    # Sincroniza los spends capturados con los medios actualmente
    # seleccionados: agrega nuevos con un valor por default y
    # elimina los que ya no están seleccionados.
    for medio in selected_media:
        st.session_state[session_key].setdefault(medio, DEFAULT_SPEND)
    for medio in list(st.session_state[session_key].keys()):
        if medio not in selected_media:
            del st.session_state[session_key][medio]

    table_df = pd.DataFrame(
        {
            "Media": selected_media,
            "Spend": [st.session_state[session_key][m] for m in selected_media],
        }
    )

    edited_df = st.data_editor(
        table_df,
        column_config={
            "Media": st.column_config.TextColumn("Media", disabled=True),
            "Spend": st.column_config.NumberColumn(
                "Spend (MXN)",
                min_value=0.0,
                step=50_000.0,
                format="%.2f",
            ),
        },
        hide_index=True,
        use_container_width=True,
        key=f"{session_key}_editor",
    )

    for _, row in edited_df.iterrows():
        st.session_state[session_key][row["Media"]] = float(row["Spend"])

    button_clicked = False
    if show_run_button:
        button_clicked = st.button(button_label, type="primary")

    return dict(st.session_state[session_key]), button_clicked

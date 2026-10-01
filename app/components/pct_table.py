"""
Componente de UI: configuración del % de movimiento permitido para
el optimizador de Budget Optimization, por medio y de forma global.

Se manejan dos límites independientes por medio:
- Max % Increase: cuánto puede subir el spend respecto al Escenario Base.
- Max % Decrease: cuánto puede bajar el spend respecto al Escenario Base.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

DEFAULT_PCT = 20.0


def render_pct_table(
    selected_media: list[str], session_key: str = "opt_pct_by_media"
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Renderiza los controles globales ("Apply to all") y una tabla
    editable con el % de aumento y disminución permitidos por medio.

    Returns
    -------
    (pct_up_by_media, pct_down_by_media)
    """
    st.markdown("**Allowed % Movement**")

    if not selected_media:
        return {}, {}

    up_key = f"{session_key}_up"
    down_key = f"{session_key}_down"

    if up_key not in st.session_state:
        st.session_state[up_key] = {}
    if down_key not in st.session_state:
        st.session_state[down_key] = {}

    for medio in selected_media:
        st.session_state[up_key].setdefault(medio, DEFAULT_PCT)
        st.session_state[down_key].setdefault(medio, DEFAULT_PCT)
    for medio in list(st.session_state[up_key].keys()):
        if medio not in selected_media:
            del st.session_state[up_key][medio]
    for medio in list(st.session_state[down_key].keys()):
        if medio not in selected_media:
            del st.session_state[down_key][medio]

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        global_up = st.number_input(
            "Apply Max % Increase to all Media",
            min_value=0.0,
            max_value=100.0,
            value=DEFAULT_PCT,
            step=5.0,
            key=f"{session_key}_global_up",
        )
    with col2:
        global_down = st.number_input(
            "Apply Max % Decrease to all Media",
            min_value=0.0,
            max_value=100.0,
            value=DEFAULT_PCT,
            step=5.0,
            key=f"{session_key}_global_down",
        )
    with col3:
        st.write("")
        st.write("")
        if st.button("Apply to all", key=f"{session_key}_apply_all"):
            for medio in selected_media:
                st.session_state[up_key][medio] = global_up
                st.session_state[down_key][medio] = global_down

    table_df = pd.DataFrame(
        {
            "Media": selected_media,
            "Max % Increase": [st.session_state[up_key][m] for m in selected_media],
            "Max % Decrease": [st.session_state[down_key][m] for m in selected_media],
        }
    )

    edited_df = st.data_editor(
        table_df,
        column_config={
            "Media": st.column_config.TextColumn("Media", disabled=True),
            "Max % Increase": st.column_config.NumberColumn(
                "Max % Increase",
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                format="%.1f",
            ),
            "Max % Decrease": st.column_config.NumberColumn(
                "Max % Decrease",
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                format="%.1f",
            ),
        },
        hide_index=True,
        use_container_width=True,
        key=f"{session_key}_editor",
    )

    for _, row in edited_df.iterrows():
        st.session_state[up_key][row["Media"]] = float(row["Max % Increase"])
        st.session_state[down_key][row["Media"]] = float(row["Max % Decrease"])

    return dict(st.session_state[up_key]), dict(st.session_state[down_key])

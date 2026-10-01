"""
Módulo: Total Budget Optimization.

El usuario define un presupuesto total y los medios entre los que
quiere repartirlo; el sistema entrega la asignación que maximiza el
Expected Response total, reutilizando el motor MMM existente a
través de src/services/optimization_agent.py.

A diferencia de Channel Optimization, aquí NO se parte de un
escenario base: no hay inversión previa que ajustar, sino un monto
a distribuir desde cero.

Opcionalmente se pueden definir mínimos y máximos de inversión por
medio (por ejemplo, para respetar mínimos de compra o topes de
capacidad de un medio).
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from app.components import allocation_results
from app.services import optimization_service, simulation_service

logger = logging.getLogger(__name__)


def render() -> None:
    st.title("Total Budget Optimization")
    st.caption("Allocate a total media budget across the selected Media")

    try:
        response_curve = simulation_service.get_response_curves()
    except FileNotFoundError:
        st.error("Response curve file not found.")
        return
    except (ValueError, TypeError):
        logger.exception("Failed to load response curves")
        st.error("The response curve file could not be loaded. Please check its format.")
        return

    marca, selected_media = _render_sidebar_inputs(response_curve)

    if not selected_media:
        st.info("Select at least one Media in the sidebar to allocate the budget.")
        return

    st.subheader("Total Budget")
    total_budget = st.number_input(
        "Total Budget to allocate (MXN)",
        min_value=0.0,
        value=3_000_000.0,
        step=100_000.0,
        format="%.2f",
        key="tbo_total_budget",
        help="The full amount to distribute across the selected Media.",
    )

    constraints_by_media = _render_constraints(selected_media, total_budget)

    if st.button("Run Total Budget Optimization", type="primary", key="run_total_budget"):
        if total_budget <= 0:
            st.error("Total Budget must be greater than 0.")
        else:
            try:
                with st.spinner("Running optimization..."):
                    st.session_state["result_total_budget"] = optimization_service.run_total_budget(
                        response_curve=response_curve,
                        marca=marca,
                        media_list=selected_media,
                        total_budget=total_budget,
                        min_spend_by_media=constraints_by_media["min"],
                        max_spend_by_media=constraints_by_media["max"],
                    )
            except ValueError as error:
                st.error(str(error))
            except Exception:
                logger.exception("Total budget optimization failed")
                st.error("An unexpected error occurred while running the optimization.")

    if st.session_state.get("result_total_budget"):
        allocation_results.render_allocation_result(st.session_state["result_total_budget"])


def _render_sidebar_inputs(response_curve) -> tuple[str, list[str]]:
    st.sidebar.subheader("Allocation Inputs")

    marcas = simulation_service.get_available_brands(response_curve)
    marca = st.sidebar.selectbox("Brand", options=marcas, key="tbo_input_marca")

    available_media = simulation_service.get_available_media(response_curve, marca)

    if st.session_state.get("_tbo_previous_marca") != marca:
        st.session_state["tbo_input_media"] = available_media
        st.session_state["tbo_constraints"] = {}
        st.session_state["_tbo_previous_marca"] = marca

    selected_media = st.sidebar.multiselect(
        "Media",
        options=available_media,
        key="tbo_input_media",
        help="Media to distribute the Total Budget across.",
    )

    return marca, selected_media


def _render_constraints(selected_media: list[str], total_budget: float) -> dict[str, dict[str, float]]:
    """
    Tabla editable opcional de mínimos y máximos de inversión por
    medio. Por default: mínimo 0 y máximo igual al presupuesto total
    (es decir, sin restricción adicional).
    """
    session_key = "tbo_constraints"

    if session_key not in st.session_state:
        st.session_state[session_key] = {}

    for medio in selected_media:
        st.session_state[session_key].setdefault(medio, {"min": 0.0, "max": float(total_budget)})
    for medio in list(st.session_state[session_key].keys()):
        if medio not in selected_media:
            del st.session_state[session_key][medio]

    with st.expander("Spend Constraints per Media (optional)"):
        st.caption(
            "Set a minimum or maximum investment per Media. Leave the "
            "defaults to let the optimizer distribute the budget freely."
        )

        table_df = pd.DataFrame(
            {
                "Media": selected_media,
                "Min Spend": [st.session_state[session_key][m]["min"] for m in selected_media],
                "Max Spend": [st.session_state[session_key][m]["max"] for m in selected_media],
            }
        )

        edited_df = st.data_editor(
            table_df,
            column_config={
                "Media": st.column_config.TextColumn("Media", disabled=True),
                "Min Spend": st.column_config.NumberColumn(
                    "Min Spend (MXN)", min_value=0.0, step=50_000.0, format="%.2f"
                ),
                "Max Spend": st.column_config.NumberColumn(
                    "Max Spend (MXN)", min_value=0.0, step=50_000.0, format="%.2f"
                ),
            },
            hide_index=True,
            use_container_width=True,
            key=f"{session_key}_editor",
        )

        for _, row in edited_df.iterrows():
            st.session_state[session_key][row["Media"]] = {
                "min": float(row["Min Spend"]),
                "max": float(row["Max Spend"]),
            }

    return {
        "min": {m: st.session_state[session_key][m]["min"] for m in selected_media},
        "max": {m: st.session_state[session_key][m]["max"] for m in selected_media},
    }

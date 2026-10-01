"""
Módulo: Descriptive Analysis.

Orquesta los componentes de UI (inputs, spend_table, results,
charts) y la capa de servicios (simulation_service) para la primera
fase del agente:

- Simular un único medio (Marca + Medio + Proposed Spend), o
- Simular varios medios de una misma Marca a la vez, mostrando una
  tabla resumen (Media | Proposed Spend | Expected Response | ROI |
  Range). Al seleccionar una fila de esa tabla se despliega el
  detalle completo de ese medio (métricas, resumen, parámetros del
  modelo y curva de respuesta) — el mismo detalle que se muestra
  cuando solo se simula un medio.
"""
from __future__ import annotations

import logging

import streamlit as st

from app.components import charts, inputs, results, spend_table
from app.services import simulation_service

logger = logging.getLogger(__name__)


def render() -> None:
    st.title("Media Investment Optimization Agent")
    st.caption("MMM-based media investment simulation")

    # --- Carga de datos (único punto de acceso al Excel) ---
    try:
        response_curve = simulation_service.get_response_curves()
    except FileNotFoundError:
        st.error("Response curve file not found.")
        return
    except (ValueError, TypeError):
        logger.exception("Failed to load response curves")
        st.error("The response curve file could not be loaded. Please check its format.")
        return

    # --- Inputs: Brand / Media (sidebar) + Proposed Spend por medio (tabla) ---
    marca, selected_media = inputs.render_sidebar_inputs(response_curve)
    spend_by_media, run_clicked = spend_table.render_spend_table(selected_media)

    if "batch_results" not in st.session_state:
        st.session_state.batch_results = {}
        st.session_state.batch_errors = {}

    if run_clicked:
        invalid_spend = any(spend < 0 for spend in spend_by_media.values())
        if invalid_spend:
            st.error("Proposed Spend must be greater than or equal to 0.")
        else:
            with st.spinner("Running simulation..."):
                batch_results, batch_errors = simulation_service.run_batch_simulation(
                    response_curve=response_curve,
                    marca=marca,
                    spend_by_media=spend_by_media,
                )
            st.session_state.batch_results = batch_results
            st.session_state.batch_errors = batch_errors

    batch_results = st.session_state.batch_results
    batch_errors = st.session_state.batch_errors

    if not batch_results and not batch_errors:
        st.info("Configure your inputs above and click **Run Simulation** to see results.")
        return

    if not batch_results and batch_errors:
        st.error("No response curve is available for the selected brand and media.")
        return

    # Un solo medio simulado con éxito: se muestra el detalle
    # directamente, igual que en la versión de un solo medio.
    if len(batch_results) == 1 and not batch_errors:
        _, single_result = next(iter(batch_results.items()))
        results.render_results(single_result)
        _render_curve(single_result)
        _render_model_info(single_result)
        return

    # Varios medios: tabla resumen + detalle expandible al
    # seleccionar una fila.
    selected_medio = results.render_batch_results(batch_results, batch_errors)

    if selected_medio:
        st.markdown(f"#### Detail — {selected_medio}")
        detail_result = batch_results[selected_medio]
        results.render_results(detail_result)
        _render_curve(detail_result)
        _render_model_info(detail_result)


def _render_curve(result: dict) -> None:
    st.markdown("#### Response Curve")
    curve_points = simulation_service.build_response_curve_series(
        modelo=result["modelo"],
        curve_a=result["curve_parameters"]["curve_a"],
        curve_b=result["curve_parameters"]["curve_b"],
        curve_c=result["curve_parameters"]["curve_c"],
        max_spend_real=result["max_spend_real"],
        proposed_spend=result["proposed_spend"],
    )
    charts.render_response_curve(
        curve_points=curve_points,
        proposed_spend=result["proposed_spend"],
        expected_response=result["expected_response"],
        min_spend_real=result["min_spend_real"],
        max_spend_real=result["max_spend_real"],
    )


def _render_model_info(result: dict) -> None:
    st.markdown("#### Model Information")
    st.write(
        f"**Brand:** {result['marca']}  \n"
        f"**Media:** {result['medio']}  \n"
        f"**Model:** {result['modelo']}"
    )

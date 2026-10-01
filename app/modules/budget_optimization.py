"""
Módulo: Budget Optimization.

Implementa 4 modos de optimización de presupuesto sobre un
Escenario Base, reutilizando el motor MMM existente
(calculate_expected_response) a través de
src/services/optimization_agent.py — sin reimplementar ecuaciones
del MMM en la interfaz.

Modos:
1. Simple Optimization      — para cada medio, se mueve al máximo
                               permitido (arriba o abajo) que dé el
                               mayor ROI; garantiza ROI optimizado
                               >= ROI base, por medio y en total.
2. Fixed Budget             — reasigna el presupuesto base entre
                               medios (mismo total) maximizando el
                               Expected Response total.
3. Target ROI / Response    — reasigna el presupuesto para acercarse
                               lo más posible a un ROI o Response
                               objetivo definido por el usuario.
4. Both-ways                — paso 1: igual que Fixed Budget; paso 2:
                               busca el menor presupuesto que alcance
                               el mismo Expected Response del paso 1.

El % de movimiento permitido (aumento y disminución, por separado)
se puede configurar de forma global (aplicado a todos los medios) o
por medio individual, en la sección "Allowed % Movement".
"""
from __future__ import annotations

import logging

import streamlit as st

from app.components import optimization_results, pct_table, spend_table
from app.services import optimization_service, simulation_service

logger = logging.getLogger(__name__)

TARGET_METRIC_OPTIONS = {"Expected Response": "response", "ROI": "roi"}


def render() -> None:
    st.title("Budget Optimization")
    st.caption("Reallocate media investment within user-defined % bounds")

    try:
        response_curve = simulation_service.get_response_curves()
    except FileNotFoundError:
        st.error("Response curve file not found.")
        return
    except (ValueError, TypeError):
        logger.exception("Failed to load response curves")
        st.error("The response curve file could not be loaded. Please check its format.")
        return

    marca, selected_media = _render_brand_media_inputs(response_curve)

    if not selected_media:
        st.info("Select at least one Media in the sidebar to configure a Base Scenario.")
        return

    st.subheader("Base Scenario")
    base_spend_by_media, _ = spend_table.render_spend_table(
        selected_media,
        session_key="opt_base_spend_by_media",
        title=None,
        show_run_button=False,
    )

    pct_up_by_media, pct_down_by_media = pct_table.render_pct_table(
        selected_media, session_key="opt_pct_by_media"
    )

    st.divider()

    tab_simple, tab_fixed, tab_target, tab_both = st.tabs(
        [
            "Simple Optimization",
            "Fixed Budget Optimization",
            "Target ROI / Response",
            "Both-ways Optimization",
        ]
    )

    with tab_simple:
        _render_simple_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media)

    with tab_fixed:
        _render_fixed_budget_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media)

    with tab_target:
        _render_target_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media)

    with tab_both:
        _render_both_ways_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media)


def _render_brand_media_inputs(response_curve) -> tuple[str, list[str]]:
    """
    Selección de Brand / Media propia de este módulo (independiente
    de Descriptive Analysis, para no interferir con esa sesión).
    """
    st.sidebar.subheader("Optimization Inputs")

    marcas = simulation_service.get_available_brands(response_curve)
    marca = st.sidebar.selectbox("Brand", options=marcas, key="opt_input_marca")

    available_media = simulation_service.get_available_media(response_curve, marca)

    if st.session_state.get("_opt_previous_marca") != marca:
        st.session_state["opt_input_media"] = available_media
        st.session_state["opt_base_spend_by_media"] = {}
        st.session_state["opt_pct_by_media_up"] = {}
        st.session_state["opt_pct_by_media_down"] = {}
        st.session_state["_opt_previous_marca"] = marca

    selected_media = st.sidebar.multiselect(
        "Media",
        options=available_media,
        key="opt_input_media",
    )

    return marca, selected_media


def _handle_optimization_error(error: Exception) -> None:
    if isinstance(error, ValueError):
        st.error(str(error))
    else:
        logger.exception("Budget optimization failed")
        st.error("An unexpected error occurred while running the optimization.")


def _render_simple_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media) -> None:
    st.write(
        "For each Media, moves the spend to the maximum allowed increase "
        "or the maximum allowed decrease — whichever gives the higher ROI "
        "for that Media. If neither improves the ROI, the Base Scenario is "
        "kept. This guarantees the optimized ROI is always greater than or "
        "equal to the base ROI, both per Media and in total."
    )

    if st.button("Run Simple Optimization", type="primary", key="run_simple"):
        try:
            st.session_state["result_simple"] = optimization_service.run_simple_shift(
                response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media
            )
        except Exception as error:
            _handle_optimization_error(error)

    if st.session_state.get("result_simple"):
        optimization_results.render_optimization_result(
            st.session_state["result_simple"], "Simple Optimization Results"
        )


def _render_fixed_budget_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media) -> None:
    st.write(
        "Reallocates the Base Scenario budget between Media (same total "
        "budget) to maximize total Expected Response, within the allowed "
        "% per Media."
    )

    if st.button("Run Fixed Budget Optimization", type="primary", key="run_fixed"):
        try:
            with st.spinner("Running optimization..."):
                st.session_state["result_fixed"] = optimization_service.run_fixed_budget(
                    response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media
                )
        except Exception as error:
            _handle_optimization_error(error)

    if st.session_state.get("result_fixed"):
        optimization_results.render_optimization_result(
            st.session_state["result_fixed"], "Fixed Budget Optimization Results"
        )


def _render_target_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media) -> None:
    st.write(
        "Reallocates the Base Scenario budget between Media, within the "
        "allowed % per Media, to get as close as possible to a target "
        "ROI or Expected Response."
    )

    col1, col2 = st.columns(2)
    with col1:
        target_metric_label = st.selectbox(
            "Target Metric", options=list(TARGET_METRIC_OPTIONS.keys()), key="target_metric_label"
        )
    with col2:
        target_value = st.number_input(
            "Target Value", min_value=0.0, value=1_000_000.0, step=50_000.0, key="target_value"
        )

    if st.button("Run Target Optimization", type="primary", key="run_target"):
        try:
            with st.spinner("Running optimization..."):
                st.session_state["result_target"] = optimization_service.run_target(
                    response_curve,
                    marca,
                    base_spend_by_media,
                    pct_up_by_media,
                    pct_down_by_media,
                    target_value=target_value,
                    target_metric=TARGET_METRIC_OPTIONS[target_metric_label],
                )
        except Exception as error:
            _handle_optimization_error(error)

    if st.session_state.get("result_target"):
        optimization_results.render_optimization_result(
            st.session_state["result_target"], "Target Optimization Results"
        )


def _render_both_ways_tab(response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media) -> None:
    st.write(
        "Step 1: reallocates the Base Scenario budget (same total) to "
        "maximize Expected Response. Step 2: looks for the smallest "
        "budget that still reaches that same Expected Response."
    )

    if st.button("Run Both-ways Optimization", type="primary", key="run_both"):
        try:
            with st.spinner("Running optimization..."):
                st.session_state["result_both"] = optimization_service.run_both_ways(
                    response_curve, marca, base_spend_by_media, pct_up_by_media, pct_down_by_media
                )
        except Exception as error:
            _handle_optimization_error(error)

    result_both = st.session_state.get("result_both")
    if result_both:
        optimization_results.render_optimization_result(
            result_both["fixed_budget_step"], "Step 1 — Fixed Budget Optimization"
        )
        optimization_results.render_optimization_result(
            result_both["budget_minimization_step"], "Step 2 — Minimum Budget for Same Response"
        )

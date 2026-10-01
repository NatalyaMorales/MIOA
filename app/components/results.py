"""
Componente de UI: resultados de la simulación (métricas, resumen y
parámetros del modelo).

No contiene lógica de negocio: solo presenta el diccionario de
resultado ya calculado por simulation_service.run_simulation()
(que a su vez reutiliza simulate_spend()).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.range_warning import range_text, render_range_warnings, status_label
from app.formatting import (
    format_abbreviated_currency,
    format_abbreviated_number,
    format_number,
)


def _range_entry(medio: str, result: dict) -> dict:
    return {
        "media": medio,
        "spend_label": "Proposed Spend",
        "spend": result["proposed_spend"],
        "status": result.get("range_status", "unknown"),
        "min_spend_real": result.get("min_spend_real"),
        "max_spend_real": result.get("max_spend_real"),
    }


def render_results(result: dict) -> None:
    st.subheader("Simulation Results")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Proposed Spend", format_abbreviated_currency(result["proposed_spend"]))

    with col2:
        st.metric("Expected Response", format_abbreviated_number(result["expected_response"]))
        st.caption("Assumes Expected Response is a monetary metric compatible with ROI.")

    with col3:
        st.metric("ROI", f"{result['roi']:.2f}x")

    with col4:
        st.metric(
            "Marginal Return",
            f"{result['marginal_return']:.4f}x",
            help="Extra Expected Response per additional peso invested at this spend level.",
        )

    render_range_warnings([_range_entry(result["medio"], result)])

    st.markdown("#### Summary")

    summary_df = pd.DataFrame(
        [
            {
                "Brand": result["marca"],
                "Media": result["medio"],
                "Model": result["modelo"],
                "Proposed Spend": format_number(result["proposed_spend"]),
                "Expected Response": format_number(result["expected_response"]),
                "ROI": f"{result['roi']:.4f}x",
                "Marginal Return": f"{result['marginal_return']:.4f}x",
                "Range Check": status_label(result.get("range_status", "unknown")),
            }
        ]
    )
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    with st.expander("Model Parameters"):
        params = result["curve_parameters"]

        p1, p2, p3 = st.columns(3)
        p1.metric("curve_a", f"{params['curve_a']:.4f}")
        p2.metric("curve_b", f"{params['curve_b']:.4f}")
        p3.metric("curve_c", f"{params['curve_c']:.4f}")

        details = []
        if result.get("r_squared") is not None:
            details.append(f"**Model fit (R²):** {result['r_squared']:.3f}")
        if result.get("spend_optimo") is not None:
            details.append(f"**Optimal Spend (from MMM):** {format_number(result['spend_optimo'])}")

        if details:
            st.markdown("  \n".join(details))


def _friendly_error_message(raw_message: str) -> str:
    """
    Traduce los mensajes técnicos del motor (en español, pensados
    para logs/debugging) a un mensaje amigable para el usuario
    final, sin exponer detalles internos.
    """
    if "múltiples curvas" in raw_message:
        return "Multiple response curves were found for this Brand / Media combination."
    return "No response curve is available for the selected brand and media."


def render_batch_results(results: dict[str, dict], errors: dict[str, str]) -> str | None:
    """
    Renderiza la tabla resumen para varios medios simulados a la vez
    (Media | Proposed Spend | Expected Response | ROI | Range).

    El usuario puede seleccionar una fila para ver el detalle
    completo de ese medio (métricas, resumen, parámetros y gráfica),
    reutilizando render_results() más abajo en la app.

    Returns
    -------
    El nombre del Media seleccionado en la tabla, o None si no hay
    selección o el medio seleccionado tuvo un error.
    """
    st.subheader("Simulation Results")

    rows = []
    range_entries = []

    for medio, result in results.items():
        range_label = range_text(result.get("min_spend_real"), result.get("max_spend_real"))
        if result.get("out_of_historical_range"):
            range_label += " *"

        range_entries.append(_range_entry(medio, result))

        rows.append(
            {
                "Media": medio,
                "Proposed Spend": format_abbreviated_currency(result["proposed_spend"]),
                "Expected Response": format_abbreviated_number(result["expected_response"]),
                "ROI": f"{result['roi']:.2f}x",
                "Marginal Return": f"{result['marginal_return']:.4f}x",
                "Range": range_label,
            }
        )

    for medio in errors:
        rows.append(
            {
                "Media": medio,
                "Proposed Spend": "—",
                "Expected Response": "—",
                "ROI": "—",
                "Marginal Return": "—",
                "Range": "—",
            }
        )

    summary_df = pd.DataFrame(rows)

    event = st.dataframe(
        summary_df,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="media_results_table",
    )

    st.caption("Click a row in the table to see the full detail for that media.")
    render_range_warnings(range_entries)

    if errors:
        with st.expander(f"{len(errors)} media could not be simulated"):
            for medio, message in errors.items():
                st.write(f"**{medio}:** {_friendly_error_message(message)}")

    selected_rows = event.selection.rows if event is not None and event.selection else []
    if selected_rows:
        selected_media_name = summary_df.iloc[selected_rows[0]]["Media"]
        if selected_media_name in results:
            return selected_media_name

    return None

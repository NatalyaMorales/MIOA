"""
Componente de UI: resultados de Total Budget Optimization.

A diferencia de Channel Optimization, aquí no existe un escenario
base definido por el usuario: solo un presupuesto total a repartir.
Por eso se muestra la asignación óptima y su participación (%) del
presupuesto, y de forma opcional la comparación contra un reparto
equitativo, que el motor usa como referencia neutral.

No contiene lógica de optimización.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.range_warning import render_range_warnings, status_label
from app.formatting import format_abbreviated_currency, format_abbreviated_number


def render_allocation_result(result: dict, title: str = "Optimal Allocation") -> None:
    st.markdown(f"#### {title}")

    totals = result["totals"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Budget Allocated", format_abbreviated_currency(totals["optimized_budget"]))
    c2.metric("Total Expected Response", format_abbreviated_number(totals["optimized_response"]))
    c3.metric("Total ROI", f"{totals['optimized_roi']:.2f}x")

    total_allocated = totals["optimized_budget"]

    # Umbral de asignación no significativa. Es necesario porque las
    # curvas Modelo 1 (sigmoide) tienen respuesta positiva en spend
    # cercano a 0 (intercepto no nulo), por lo que un spend
    # diminuto produce un ROI numéricamente enorme pero sin
    # significado de negocio. En esos casos no se muestra el ROI.
    negligible_threshold = max(total_allocated * 1e-4, 1.0)

    rows = []
    for medio, m in result["media"].items():
        spend = m["optimized_spend"]
        share = (spend / total_allocated * 100.0) if total_allocated > 0 else 0.0
        is_negligible = spend < negligible_threshold

        rows.append(
            {
                "Media": medio,
                "Optimal Spend": format_abbreviated_currency(0.0 if is_negligible else spend),
                "% of Budget": f"{0.0 if is_negligible else share:.1f}%",
                "Expected Response": format_abbreviated_number(m["optimized_response"]),
                "ROI": "—" if is_negligible else f"{m['optimized_roi']:.2f}x",
                "Marginal Return": "—" if is_negligible else f"{m['optimized_marginal_return']:.4f}x",
                "Range Check": "—" if is_negligible else status_label(m["optimized_range_status"]),
            }
        )

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "Marginal Return = extra Expected Response per additional peso invested "
        "at that spend level. In an optimal allocation, the Media that receive "
        "budget tend to show similar marginal returns."
    )

    render_range_warnings(
        [
            {
                "media": medio,
                "spend_label": "Optimized Spend",
                "spend": m["optimized_spend"],
                "status": m["optimized_range_status"],
                "min_spend_real": m.get("min_spend_real"),
                "max_spend_real": m.get("max_spend_real"),
            }
            for medio, m in result["media"].items()
            if m["optimized_spend"] >= negligible_threshold
        ]
    )

    if any(m["optimized_spend"] < negligible_threshold for m in result["media"].values()):
        st.caption(
            "Media shown with no allocated spend were excluded by the "
            "optimizer because other Media deliver more incremental "
            "response per additional peso invested."
        )

    _render_allocation_chart(result)

    with st.expander("Compare against an equal split"):
        st.caption(
            "Equal split distributes the Total Budget evenly across the "
            "selected Media. It is shown only as a neutral reference point."
        )
        comparison_rows = []
        for medio, m in result["media"].items():
            comparison_rows.append(
                {
                    "Media": medio,
                    "Equal Split Spend": format_abbreviated_currency(m["base_spend"]),
                    "Optimal Spend": format_abbreviated_currency(m["optimized_spend"]),
                    "Equal Split Response": format_abbreviated_number(m["base_response"]),
                    "Optimal Response": format_abbreviated_number(m["optimized_response"]),
                }
            )
        st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, use_container_width=True)

        e1, e2 = st.columns(2)
        e1.metric("Equal Split Total Response", format_abbreviated_number(totals["base_response"]))
        e2.metric(
            "Optimal Total Response",
            format_abbreviated_number(totals["optimized_response"]),
            delta=format_abbreviated_number(totals["optimized_response"] - totals["base_response"]),
        )


def _render_allocation_chart(result: dict) -> None:
    medios = list(result["media"].keys())
    spends = [result["media"][m]["optimized_spend"] for m in medios]

    fig = go.Figure(
        go.Bar(
            x=spends,
            y=medios,
            orientation="h",
            marker=dict(color="#2C3E50"),
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        template="simple_white",
        height=max(260, 46 * len(medios) + 90),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Optimal Spend (MXN)",
        yaxis_title="",
        font=dict(family="sans-serif", size=13, color="#2C3E50"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EDEDED", tickformat=",.0f")

    st.plotly_chart(fig, use_container_width=True)

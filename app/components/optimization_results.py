"""
Componente de UI: resultados de Budget Optimization.

No contiene lógica de optimización: solo presenta el diccionario de
resultado ya calculado por app/services/optimization_service.py
(que a su vez reutiliza src/services/optimization_agent.py).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.range_warning import render_range_warnings, status_label
from app.formatting import format_abbreviated_currency, format_abbreviated_number


def render_optimization_result(result: dict, title: str = "Optimization Results") -> None:
    st.markdown(f"#### {title}")

    totals = result["totals"]

    st.caption("Total — Base Scenario")
    b1, b2, b3 = st.columns(3)
    b1.metric("Total Spend", format_abbreviated_currency(totals["base_budget"]))
    b2.metric("Total Expected Response", format_abbreviated_number(totals["base_response"]))
    b3.metric("Total ROI", f"{totals['base_roi']:.2f}x")

    st.caption("Total — Optimized Scenario")
    o1, o2, o3 = st.columns(3)
    o1.metric(
        "Total Spend",
        format_abbreviated_currency(totals["optimized_budget"]),
        delta=format_abbreviated_currency(totals["optimized_budget"] - totals["base_budget"]),
    )
    o2.metric(
        "Total Expected Response",
        format_abbreviated_number(totals["optimized_response"]),
        delta=format_abbreviated_number(totals["optimized_response"] - totals["base_response"]),
    )
    o3.metric(
        "Total ROI",
        f"{totals['optimized_roi']:.2f}x",
        delta=f"{totals['optimized_roi'] - totals['base_roi']:.2f}x",
    )

    rows = []
    for medio, m in result["media"].items():
        rows.append(
            {
                "Media": medio,
                "Base Spend": format_abbreviated_currency(m["base_spend"]),
                "Optimized Spend": format_abbreviated_currency(m["optimized_spend"]),
                "Δ %": f"{m['delta_pct']:+.1f}%",
                "Base Response": format_abbreviated_number(m["base_response"]),
                "Optimized Response": format_abbreviated_number(m["optimized_response"]),
                "Base ROI": f"{m['base_roi']:.2f}x",
                "Optimized ROI": f"{m['optimized_roi']:.2f}x",
                "Base Marginal Return": f"{m['base_marginal_return']:.4f}x",
                "Optimized Marginal Return": f"{m['optimized_marginal_return']:.4f}x",
                "Range Check": status_label(m["optimized_range_status"]),
            }
        )

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "Marginal Return = extra Expected Response per additional peso invested "
        "at that spend level. Range Check refers to the Optimized Spend."
    )

    entries = []
    for medio, m in result["media"].items():
        for spend_label, spend_key, status_key in (
            ("Base Spend", "base_spend", "base_range_status"),
            ("Optimized Spend", "optimized_spend", "optimized_range_status"),
        ):
            entries.append(
                {
                    "media": medio,
                    "spend_label": spend_label,
                    "spend": m[spend_key],
                    "status": m[status_key],
                    "min_spend_real": m.get("min_spend_real"),
                    "max_spend_real": m.get("max_spend_real"),
                }
            )
    render_range_warnings(entries)

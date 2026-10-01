"""
Componente de UI: visualización de la curva de respuesta.

Este componente SOLO grafica puntos ya calculados. No contiene
ecuaciones del MMM: los puntos (spend, expected_response) se
generan en simulation_service.build_response_curve_series(),
que reutiliza calculate_expected_response() del motor existente.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_response_curve(
    curve_points: pd.DataFrame,
    proposed_spend: float,
    expected_response: float,
    min_spend_real: float | None,
    max_spend_real: float | None,
) -> None:
    fig = go.Figure()

    # Curva de respuesta
    fig.add_trace(
        go.Scatter(
            x=curve_points["spend"],
            y=curve_points["expected_response"],
            mode="lines",
            name="Response Curve",
            line=dict(color="#2C3E50", width=2.5),
            hovertemplate="Spend: %{x:,.0f}<br>Expected Response: %{y:,.0f}<extra></extra>",
        )
    )

    # Rango histórico observado (Min/Max Spend Real)
    if min_spend_real is not None and max_spend_real is not None and max_spend_real > min_spend_real:
        fig.add_vrect(
            x0=min_spend_real,
            x1=max_spend_real,
            fillcolor="#2C3E50",
            opacity=0.06,
            line_width=0,
            annotation_text="Historical Range",
            annotation_position="top left",
            annotation_font_size=11,
            annotation_font_color="#7F8C8D",
        )

    # Proposed Spend seleccionado por el usuario
    fig.add_trace(
        go.Scatter(
            x=[proposed_spend],
            y=[expected_response],
            mode="markers",
            name="Proposed Spend",
            marker=dict(size=13, color="#E74C3C", line=dict(width=1, color="white")),
            hovertemplate="Proposed Spend: %{x:,.0f}<br>Expected Response: %{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        template="simple_white",
        height=430,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Spend (MXN)",
        yaxis_title="Expected Response",
        font=dict(family="sans-serif", size=13, color="#2C3E50"),
        hovermode="closest",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EDEDED", tickformat=",.0f")
    fig.update_yaxes(showgrid=True, gridcolor="#EDEDED", tickformat=",.0f")

    st.plotly_chart(fig, use_container_width=True)

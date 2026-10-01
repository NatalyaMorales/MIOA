"""
Componente de UI compartido: advertencia de rango histórico (±20%).

Lo utilizan TODOS los módulos (Descriptive Analysis, Channel
Optimization y Total Budget Optimization) para que el aviso sea
consistente. La regla vive en src/utils/range_validation.py; este
componente solo presenta el resultado.
"""
from __future__ import annotations

import streamlit as st

from app.formatting import format_abbreviated_currency

STATUS_LABELS = {
    "within": "Within range",
    "below": "Below range",
    "above": "Above range",
    "unknown": "No range data",
}


def range_text(min_real: float | None, max_real: float | None) -> str:
    """Texto del rango histórico, por ejemplo "$800.0K – $2.5M"."""
    if min_real is None or max_real is None:
        return "n/a"
    return f"{format_abbreviated_currency(min_real)} – {format_abbreviated_currency(max_real)}"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, STATUS_LABELS["unknown"])


def render_range_warnings(entries: list[dict]) -> None:
    """
    Muestra una advertencia con todos los spends fuera de rango.

    Cada entrada debe traer:
        media, spend_label ("Proposed Spend" | "Base Spend" |
        "Optimized Spend"), spend, status, min_spend_real,
        max_spend_real.
    Solo se listan las entradas con status "below" o "above".
    """
    flagged = [e for e in entries if e["status"] in {"below", "above"}]
    if not flagged:
        return

    lines = []
    for e in flagged:
        direction = "below" if e["status"] == "below" else "above"
        lines.append(
            f"- **{e['media']}** — {e['spend_label']} "
            f"{format_abbreviated_currency(e['spend'])} is more than 20% {direction} "
            f"the historical range ({range_text(e['min_spend_real'], e['max_spend_real'])})."
        )

    st.warning(
        "Some spend values are more than 20% outside the historical range "
        "observed for that Media. The response curve may not be reliable "
        "there; interpret these results with caution.\n\n" + "\n".join(lines)
    )

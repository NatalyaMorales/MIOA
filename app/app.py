"""
Media Investment Optimization Agent — Streamlit entrypoint.

Ejecutar desde la raíz del proyecto con:

    streamlit run app/app.py

Este archivo SOLO maneja configuración de página y navegación entre
módulos. Toda la lógica de negocio vive en src/ (motor MMM existente)
y en app/services/ (capa de orquestación para la UI).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegura que la raíz del proyecto esté en sys.path, para que
# `from src....` y `from app....` funcionen sin importar desde
# dónde se invoque `streamlit run`.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from app.modules import channel_optimization, descriptive_analysis, total_budget_optimization

st.set_page_config(
    page_title="Media Investment Optimization Agent",
    layout="wide",
)

MODULES = {
    "Descriptive Analysis": descriptive_analysis.render,
    "Channel Optimization": channel_optimization.render,
    "Total Budget Optimization": total_budget_optimization.render,
}


def main() -> None:
    st.sidebar.title("Media Optimization Agent")
    selected_module = st.sidebar.radio(
        "Navigation",
        options=list(MODULES.keys()),
        label_visibility="collapsed",
    )
    st.sidebar.divider()

    MODULES[selected_module]()


if __name__ == "__main__":
    main()

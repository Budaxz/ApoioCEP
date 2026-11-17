"""Exportações das telas principais (Streamlit Views) da aplicação ApoioCEP."""

from __future__ import annotations

from src.ui.views.dashboard import render_dashboard_view
from src.ui.views.route_planner import (
    load_default_curitiba_stops,
    refresh_stops_with_live_apis,
    render_route_planner_view,
)

__all__ = [
    "load_default_curitiba_stops",
    "refresh_stops_with_live_apis",
    "render_dashboard_view",
    "render_route_planner_view",
]

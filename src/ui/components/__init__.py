"""Exportações públicas dos componentes visuais do ApoioCEP."""

from __future__ import annotations

from src.ui.components.cards import (
    render_executive_summary_card,
    render_header_banner,
    render_kpi_row,
    render_recommendations_list,
)
from src.ui.components.charts import (
    build_complexity_comparison_figure,
    build_stop_risk_bar_figure,
    build_weather_timeline_figure,
    render_complexity_chart,
    render_stop_risk_chart,
    render_weather_timeline_chart,
)
from src.ui.components.map_view import (
    build_route_pydeck_deck,
    render_route_map,
)

__all__ = [
    "build_complexity_comparison_figure",
    "build_route_pydeck_deck",
    "build_stop_risk_bar_figure",
    "build_weather_timeline_figure",
    "render_complexity_chart",
    "render_executive_summary_card",
    "render_header_banner",
    "render_kpi_row",
    "render_recommendations_list",
    "render_route_map",
    "render_stop_risk_chart",
    "render_weather_timeline_chart",
]

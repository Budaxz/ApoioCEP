"""Testes unitários para o Design System e construtores de gráficos e mapas (Plotly/PyDeck)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk

from src.domain.address import Address, Coordinates
from src.domain.delivery import DeliveryPriority, DeliveryStop, RoutePlan
from src.domain.weather import ClimateRiskLevel, HourlyWeatherPoint, WeatherForecast
from src.services.route_analytics import stops_to_dataframe, weather_to_dataframe
from src.ui.components import (
    build_complexity_comparison_figure,
    build_route_pydeck_deck,
    build_stop_risk_bar_figure,
    build_weather_timeline_figure,
)
from src.ui.theme import RISK_COLORS_HEX, RISK_COLORS_RGB, format_risk_badge_html


def _make_sample_stop(
    stop_id: str,
    name: str,
    cep: str,
    bairro: str,
    lat: float,
    lon: float,
    risk_score: float,
    risk_level: ClimateRiskLevel,
) -> DeliveryStop:
    return DeliveryStop(
        id=stop_id,
        recipient_name=name,
        address=Address(
            cep=cep,
            logradouro="Rua Teste",
            bairro=bairro,
            cidade="Curitiba",
            uf="PR",
            coordinates=Coordinates(latitude=lat, longitude=lon),
        ),
        package_weight_kg=2.5,
        priority=DeliveryPriority.ALTA,
        risk_score=risk_score,
        risk_level=risk_level,
    )


def test_format_risk_badge_html_colors_and_score() -> None:
    """Garante que o badge HTML aplica a cor semântica e formata o score opcional."""
    badge_critico = format_risk_badge_html(ClimateRiskLevel.CRITICO, score=0.876)
    assert "CRITICO (0.88)" in badge_critico
    assert RISK_COLORS_HEX[ClimateRiskLevel.CRITICO] in badge_critico

    badge_baixo = format_risk_badge_html(ClimateRiskLevel.BAIXO)
    assert ">BAIXO</span>" in badge_baixo
    assert RISK_COLORS_HEX[ClimateRiskLevel.BAIXO] in badge_baixo
    assert len(RISK_COLORS_RGB[ClimateRiskLevel.ALTO]) == 4


def test_build_weather_timeline_figure_populated_and_empty() -> None:
    """Verifica a construção do gráfico temporal meteorológico com dados e vazio."""
    coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
    forecast = WeatherForecast(
        coordinates=coords,
        hourly=[
            HourlyWeatherPoint(
                timestamp=datetime(2026, 5, 10, 9, 0),
                temperature_c=19.5,
                precipitation_probability=20.0,
                precipitation_mm=0.2,
                wind_speed_kmh=12.0,
            ),
            HourlyWeatherPoint(
                timestamp=datetime(2026, 5, 10, 10, 0),
                temperature_c=21.0,
                precipitation_probability=65.0,
                precipitation_mm=4.5,
                wind_speed_kmh=24.0,
            ),
            HourlyWeatherPoint(
                timestamp=datetime(2026, 5, 10, 11, 0),
                temperature_c=18.0,
                precipitation_probability=90.0,
                precipitation_mm=16.0,
                wind_speed_kmh=42.0,
            ),
        ],
    )
    weather_df = weather_to_dataframe(forecast, label="Centro")
    fig = build_weather_timeline_figure(weather_df, title="Clima Curitiba")

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3

    empty_fig = build_weather_timeline_figure(pd.DataFrame())
    assert isinstance(empty_fig, go.Figure)
    assert len(empty_fig.data) == 0


def test_build_stop_risk_bar_figure_populated_and_empty() -> None:
    """Verifica o gráfico de barras de score de risco por parada."""
    origin = _make_sample_stop(
        "CD", "CD Central", "80010-000", "Centro", -25.4284, -49.2733, 0.05, ClimateRiskLevel.BAIXO
    )
    stop1 = _make_sample_stop(
        "S1", "Cliente A", "80250-000", "Batel", -25.4420, -49.2900, 0.35, ClimateRiskLevel.MODERADO
    )
    stop2 = _make_sample_stop(
        "S2", "Cliente B", "80530-000", "Centro Cívico", -25.4150, -49.2680, 0.82, ClimateRiskLevel.CRITICO
    )

    stops_df = stops_to_dataframe(origin, [stop1, stop2])
    fig = build_stop_risk_bar_figure(stops_df)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    bar_trace = fig.data[0]
    assert list(bar_trace.y) == [0.35, 0.82]

    empty_fig = build_stop_risk_bar_figure(pd.DataFrame())
    assert isinstance(empty_fig, go.Figure)
    assert len(empty_fig.data) == 0


def test_build_complexity_comparison_figure() -> None:
    """Verifica o gráfico comparativo em escala logarítmica entre n! e n²."""
    fig = build_complexity_comparison_figure(max_n=8)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    assert fig.layout.yaxis.type == "log"
    assert list(fig.data[0].x) == list(range(1, 9))
    assert fig.data[0].y[-1] == 40320
    assert fig.data[1].y[-1] == 64


def test_build_route_pydeck_deck() -> None:
    """Verifica a construção do mapa PyDeck com PathLayer e ScatterplotLayer."""
    origin = _make_sample_stop(
        "CD", "CD Central", "80010-000", "Centro", -25.4284, -49.2733, 0.05, ClimateRiskLevel.BAIXO
    )
    stop1 = _make_sample_stop(
        "S1", "Cliente A", "80250-000", "Batel", -25.4420, -49.2900, 0.65, ClimateRiskLevel.ALTO
    )
    plan = RoutePlan(
        origin=origin,
        ordered_stops=[stop1],
        total_distance_km=2.3,
        average_risk_score=0.65,
        algorithm_used="nearest_neighbor_2opt",
        total_permutations_possible=1,
        computation_time_ms=0.5,
    )

    deck = build_route_pydeck_deck(plan)
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) == 2
    layer_types = {layer.type for layer in deck.layers}
    assert "PathLayer" in layer_types
    assert "ScatterplotLayer" in layer_types


def test_load_default_curitiba_stops() -> None:
    """Verifica se o roteiro padrão de Curitiba carrega a origem e as 5 paradas enriquecidas."""
    from src.ui.views.route_planner import load_default_curitiba_stops

    origin, stops = load_default_curitiba_stops()
    assert origin.id == "CD-ORIGEM"
    assert origin.address.coordinates is not None
    assert len(stops) == 5
    for stop in stops:
        assert stop.address.coordinates is not None
        assert stop.weather_forecast is not None
        assert len(stop.weather_forecast.hourly) == 24
        assert 0.0 <= stop.risk_score <= 1.0


def test_streamlit_app_renders_without_exception() -> None:
    """Executa teste ponta-a-ponta via Streamlit AppTest garantindo renderização sem exceções."""
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=15)
    at.run()
    assert not at.exception
    assert len(at.tabs) == 2
    assert len(at.metric) >= 4



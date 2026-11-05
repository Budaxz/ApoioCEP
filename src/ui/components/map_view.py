"""Componente de mapa geoespacial interativo com PyDeck para visualização da rota e risco."""

from __future__ import annotations

from typing import Any

import pydeck as pdk
import streamlit as st

from src.domain.delivery import RoutePlan
from src.ui.theme import RISK_COLORS_RGB

_DEFAULT_CURITIBA_LAT = -25.4284
_DEFAULT_CURITIBA_LON = -49.2733
_ORIGIN_COLOR_RGB: list[int] = [15, 23, 42, 240]


def build_route_pydeck_deck(route_plan: RoutePlan) -> pdk.Deck:
    """Constrói um objeto `pydeck.Deck` com camadas de trajetória (`PathLayer`) e paradas (`ScatterplotLayer`).

    Args:
        route_plan: Plano de rota otimizado contendo `origin` e `ordered_stops`.

    Returns:
        Instância configurada de `pdk.Deck`.
    """
    points_data: list[dict[str, Any]] = []
    path_coords: list[list[float]] = []

    origin_coords = route_plan.origin.address.coordinates
    if origin_coords is not None:
        lon, lat = origin_coords.longitude, origin_coords.latitude
        path_coords.append([lon, lat])
        points_data.append(
            {
                "ordem_label": "Partida (CD)",
                "destinatario": route_plan.origin.recipient_name,
                "bairro": route_plan.origin.address.bairro,
                "cep": route_plan.origin.address.cep,
                "risco": "ORIGEM",
                "score": f"{route_plan.origin.risk_score:.2f}",
                "lon": lon,
                "lat": lat,
                "color": _ORIGIN_COLOR_RGB,
                "radius": 240,
            }
        )

    for idx, stop in enumerate(route_plan.ordered_stops, start=1):
        coords = stop.address.coordinates
        if coords is None:
            continue
        lon, lat = coords.longitude, coords.latitude
        path_coords.append([lon, lat])
        points_data.append(
            {
                "ordem_label": f"Parada {idx}",
                "destinatario": stop.recipient_name,
                "bairro": stop.address.bairro,
                "cep": stop.address.cep,
                "risco": stop.risk_level.value,
                "score": f"{stop.risk_score:.2f}",
                "lon": lon,
                "lat": lat,
                "color": RISK_COLORS_RGB.get(stop.risk_level, [100, 116, 139, 230]),
                "radius": 200,
            }
        )

    if points_data:
        mean_lat = sum(float(pt["lat"]) for pt in points_data) / len(points_data)
        mean_lon = sum(float(pt["lon"]) for pt in points_data) / len(points_data)
    else:
        mean_lat = _DEFAULT_CURITIBA_LAT
        mean_lon = _DEFAULT_CURITIBA_LON

    layers: list[pdk.Layer] = []

    if len(path_coords) >= 2:
        path_data = [
            {
                "name": "Rota Otimizada ApoioCEP",
                "path": path_coords,
                "ordem_label": "Trajeto Otimizado",
                "destinatario": f"{len(route_plan.ordered_stops)} paradas",
                "bairro": f"{route_plan.total_distance_km:.1f} km totais",
                "cep": route_plan.algorithm_used,
                "risco": f"Risco médio {route_plan.average_risk_score:.2f}",
            }
        ]
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=path_data,
                get_path="path",
                get_color=[37, 99, 235, 210],
                width_scale=12,
                width_min_pixels=4,
                pickable=True,
            )
        )

    if points_data:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=points_data,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_line_color=[255, 255, 255, 255],
                line_width_min_pixels=2,
                get_radius="radius",
                radius_min_pixels=8,
                radius_max_pixels=20,
                stroked=True,
                filled=True,
                pickable=True,
            )
        )

    view_state = pdk.ViewState(
        latitude=mean_lat,
        longitude=mean_lon,
        zoom=11.8,
        pitch=0,
        bearing=0,
    )

    tooltip: dict[str, Any] = {
        "html": (
            "<b>{ordem_label}</b> — {destinatario}<br/>"
            "{bairro} (CEP {cep})<br/>"
            "Clima: {risco}"
        ),
        "style": {
            "backgroundColor": "#0F172A",
            "color": "#F8FAFC",
            "fontSize": "12px",
            "borderRadius": "6px",
            "padding": "6px 10px",
        },
    }

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip=tooltip,
    )


def render_route_map(route_plan: RoutePlan) -> None:
    """Renderiza o mapa PyDeck da rota otimizada no aplicativo Streamlit."""
    deck = build_route_pydeck_deck(route_plan)
    st.pydeck_chart(deck, use_container_width=True, height=340)

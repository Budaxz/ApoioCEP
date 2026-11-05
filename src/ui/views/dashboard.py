"""Tela principal da Rota do Dia focada no entregador e leitura rápida em dispositivos móveis."""

from __future__ import annotations

import streamlit as st

from src.agent.dispatcher_copilot import CopilotAnalysisReport
from src.domain.delivery import DeliveryStop
from src.domain.weather import ClimateRiskLevel
from src.services.route_analytics import (
    export_route_csv,
    stops_to_dataframe,
    weather_to_dataframe,
)
from src.ui.components.cards import (
    render_kpi_row,
    render_recommendations_list,
)
from src.ui.components.charts import (
    render_stop_risk_chart,
    render_weather_timeline_chart,
)
from src.ui.components.map_view import render_route_map
from src.ui.theme import RISK_COLORS_HEX, format_risk_badge_html


def _compute_leg_distance_km(prev_stop: DeliveryStop, curr_stop: DeliveryStop) -> float:
    """Calcula a distância geodésica em km entre a parada anterior e a parada atual."""
    prev_coords = prev_stop.address.coordinates
    curr_coords = curr_stop.address.coordinates
    if prev_coords is not None and curr_coords is not None:
        return prev_coords.distance_to(curr_coords)
    return 0.0


def render_dashboard_view(report: CopilotAnalysisReport) -> None:
    """Renderiza a visão 'Rota do Dia' com foco total no entregador e leitura mobile.

    Args:
        report: Relatório consolidado produzido pelo `DispatcherCopilot`.
    """
    render_kpi_row(report)

    st.markdown("#### Ordem de Entrega Recomendada")
    origin = report.route_plan.origin
    ordered_stops = report.route_plan.ordered_stops

    if not ordered_stops:
        st.info("Nenhuma entrega cadastrada para a rota de hoje.")
    else:
        prev_node: DeliveryStop = origin
        for idx, stop in enumerate(ordered_stops, start=1):
            leg_km = _compute_leg_distance_km(prev_node, stop)
            prev_node = stop

            max_rain = (
                stop.weather_forecast.max_precipitation_mm()
                if stop.weather_forecast is not None
                else 0.0
            )
            max_wind = (
                stop.weather_forecast.max_wind_speed_kmh()
                if stop.weather_forecast is not None
                else 0.0
            )

            border_color = RISK_COLORS_HEX.get(stop.risk_level, "#64748B")
            badge_html = format_risk_badge_html(stop.risk_level)

            warning_html = ""
            if stop.risk_level in (ClimateRiskLevel.CRITICO, ClimateRiskLevel.ALTO):
                warning_html = (
                    '<div class="route-step-alert" style="background: #FEF2F2; '
                    'border-color: #FECACA; color: #991B1B;">'
                    "Atenção: Previsão de chuva forte nesta região. Priorize ou proteja a encomenda."
                    "</div>"
                )

            card_html = (
                f'<div class="route-step-card" style="border-left-color: {border_color};">'
                f'<div class="step-badge">{idx}</div>'
                '<div class="route-step-content">'
                '<div class="route-step-header">'
                f'<span class="route-step-title">{stop.recipient_name}</span>'
                f"{badge_html}"
                "</div>"
                '<div class="route-step-address">'
                f"{stop.address.logradouro} · <strong>{stop.address.bairro}</strong> · CEP {stop.address.cep}"
                "</div>"
                '<div class="route-step-meta">'
                f"<span>Janela: <strong>{stop.delivery_window}</strong></span>"
                f"<span>Trecho: <strong>{leg_km:.1f} km</strong></span>"
                f"<span>Chuva: <strong>{max_rain:.1f} mm</strong></span>"
                f"<span>Vento: <strong>{max_wind:.0f} km/h</strong></span>"
                "</div>"
                f"{warning_html}"
                "</div>"
                "</div>"
            )
            st.markdown(card_html, unsafe_allow_html=True)

    st.divider()

    st.markdown("#### Mapa do Trajeto")
    render_route_map(report.route_plan)

    st.divider()

    all_inspection_stops: list[DeliveryStop] = [
        origin,
        *ordered_stops,
    ]
    stop_labels: dict[str, DeliveryStop] = {
        (
            f"Origem: {s.recipient_name} ({s.address.bairro} - {s.address.cep})"
            if idx == 0
            else f"Parada {idx}: {s.recipient_name} ({s.address.bairro} - {s.address.cep}) [{s.risk_level.value}]"
        ): s
        for idx, s in enumerate(all_inspection_stops)
    }

    selected_label = st.selectbox(
        "Ver previsão horária de chuva para:",
        options=list(stop_labels.keys()),
        index=min(1, len(stop_labels) - 1),
    )

    resolved_label = selected_label if selected_label is not None else next(iter(stop_labels))
    selected_stop = stop_labels[resolved_label]
    if selected_stop.weather_forecast is not None:
        weather_df = weather_to_dataframe(
            forecast=selected_stop.weather_forecast,
            label=f"{selected_stop.recipient_name} ({selected_stop.address.bairro})",
        )
        render_weather_timeline_chart(
            weather_df=weather_df,
            title=(
                f"Previsão Horária de Chuva e Temperatura — "
                f"{selected_stop.recipient_name} ({selected_stop.address.bairro})"
            ),
        )
    else:
        st.info("Previsão meteorológica horária indisponível para a parada selecionada.")

    stops_df = stops_to_dataframe(
        origin=origin,
        ordered_stops=ordered_stops,
    )

    with st.expander("Planilha da Rota e Relatório do Copiloto (CSV)"):
        csv_bytes = export_route_csv(stops_df)
        st.download_button(
            label="Exportar Rota (.CSV)",
            data=csv_bytes,
            file_name="apoiocep_rota_otimizada.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.dataframe(
            stops_df,
            use_container_width=True,
            hide_index=True,
            height=300,
        )
        render_stop_risk_chart(stops_df)
        render_recommendations_list(report.recommendations)

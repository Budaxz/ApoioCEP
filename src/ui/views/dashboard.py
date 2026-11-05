"""Tela principal do Painel Operacional e Copiloto Agêntico de Despacho."""

from __future__ import annotations

import streamlit as st

from src.agent.dispatcher_copilot import CopilotAnalysisReport
from src.domain.delivery import DeliveryStop
from src.services.route_analytics import (
    export_route_csv,
    stops_to_dataframe,
    weather_to_dataframe,
)
from src.ui.components.cards import (
    render_executive_summary_card,
    render_kpi_row,
    render_recommendations_list,
)
from src.ui.components.charts import (
    render_stop_risk_chart,
    render_weather_timeline_chart,
)
from src.ui.components.map_view import render_route_map


def render_dashboard_view(report: CopilotAnalysisReport) -> None:
    """Renderiza o painel operacional de roteirização, mapa PyDeck, KPIs e gráficos analíticos.

    Args:
        report: Relatório consolidado produzido pelo `DispatcherCopilot`.
    """
    render_kpi_row(report)
    render_executive_summary_card(report)

    map_col, rec_col = st.columns([3, 2], gap="large")
    with map_col:
        st.markdown("#### 🗺️ Mapa Geoespacial da Rota Otimizada (PyDeck)")
        st.caption(
            "Trajeto sequencial colorido e marcadores de paradas classificados por severidade "
            "climática (Verde = Baixo, Amarelo = Moderado, Laranja = Alto, Vermelho = Crítico)."
        )
        render_route_map(report.route_plan)

    with rec_col:
        st.markdown("#### 🤖 Alertas e Recomendações Táticas do Copiloto")
        st.caption(
            "Inferências proativas geradas pelo cruzamento entre janelas de entrega, "
            "precipitação prevista e otimização combinatória."
        )
        render_recommendations_list(report.recommendations)

    st.divider()

    stops_df = stops_to_dataframe(
        origin=report.route_plan.origin,
        ordered_stops=report.route_plan.ordered_stops,
    )

    chart_col, table_col = st.columns([2, 3], gap="large")
    with chart_col:
        st.markdown("#### 📊 Risco Climático por Parada")
        render_stop_risk_chart(stops_df)

    with table_col:
        header_subcol, btn_subcol = st.columns([3, 2])
        with header_subcol:
            st.markdown("#### 📋 Matriz Tabular da Rota Otimizada (Pandas)")
        with btn_subcol:
            csv_bytes = export_route_csv(stops_df)
            st.download_button(
                label="⬇️ Exportar Rota Otimizada (.CSV)",
                data=csv_bytes,
                file_name="apoiocep_rota_otimizada.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.dataframe(
            stops_df,
            use_container_width=True,
            hide_index=True,
            height=340,
        )

    st.divider()

    st.markdown("#### 🌦️ Inspeção de Série Temporal Meteorológica e Média Móvel (3h)")
    all_inspection_stops: list[DeliveryStop] = [
        report.route_plan.origin,
        *report.route_plan.ordered_stops,
    ]
    stop_labels: dict[str, DeliveryStop] = {
        (
            f"🏢 Origem: {s.recipient_name} ({s.address.bairro} - {s.address.cep})"
            if idx == 0
            else f"{idx}ª Parada: {s.recipient_name} ({s.address.bairro} - {s.address.cep}) [{s.risk_level.value}]"
        ): s
        for idx, s in enumerate(all_inspection_stops)
    }

    selected_label = st.selectbox(
        "Selecione um ponto da rota para inspecionar a curva horária de chuva, média móvel de 3h e temperatura:",
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
                f"Curva Horária de Precipitação, Média Móvel (3h) e Temperatura — "
                f"{selected_stop.recipient_name} ({selected_stop.address.bairro})"
            ),
        )
        with st.expander("🔍 Visualizar DataFrame Horário Completo (24h)"):
            st.dataframe(weather_df, use_container_width=True, hide_index=True)
    else:
        st.info("Previsão meteorológica horária indisponível para a parada selecionada.")

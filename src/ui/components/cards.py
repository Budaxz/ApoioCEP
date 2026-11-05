"""Componentes visuais de cartões, indicadores KPI, banner e alertas operacionais."""

from __future__ import annotations

import streamlit as st

from src.agent.dispatcher_copilot import (
    CopilotAnalysisReport,
    DispatchAlertSeverity,
    DispatchRecommendation,
)

_SEVERITY_STYLES: dict[DispatchAlertSeverity, tuple[str, str, str]] = {
    DispatchAlertSeverity.CRITICAL: ("#EF4444", "CRÍTICO", "#FEF2F2"),
    DispatchAlertSeverity.WARNING: ("#F59E0B", "ATENÇÃO", "#FFFBEB"),
    DispatchAlertSeverity.INFO: ("#3B82F6", "NOTA", "#EFF6FF"),
}


def render_header_banner() -> None:
    """Renderiza o cabeçalho compacto e direto do painel ApoioCEP."""
    banner_html = """
    <div class="apoiocep-banner">
        <h1>ApoioCEP</h1>
        <p>Roteirização de entregas com previsão climática por CEP</p>
    </div>
    """
    st.markdown(banner_html, unsafe_allow_html=True)


def render_kpi_row(report: CopilotAnalysisReport) -> None:
    """Renderiza linha de 4 indicadores-chave (KPIs) da rota e do risco climático.

    Args:
        report: Relatório consolidado gerado pelo `DispatcherCopilot`.
    """
    route = report.route_plan
    n_stops = len(route.ordered_stops)
    perms_formatted = f"{route.total_permutations_possible:,}".replace(",", ".")
    alert_total = report.critical_stops_count + report.high_risk_stops_count

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Entregas na Rota",
            value=f"{n_stops} paradas",
            delta=f"Otimizado ({perms_formatted} comb.)",
            delta_color="off",
        )

    with col2:
        st.metric(
            label="Distância Total",
            value=f"{route.total_distance_km:.1f} km",
            delta=f"-{report.distance_saved_km:.1f} km economizados",
            delta_color="normal",
        )

    with col3:
        st.metric(
            label="Melhor Horário de Saída",
            value=report.best_weather_window,
            delta="Menor risco de chuva",
            delta_color="off",
        )

    with col4:
        st.metric(
            label="Alertas de Clima",
            value=f"{alert_total} parada(s)" if alert_total > 0 else "Sem alertas",
            delta="Atenção na rota" if alert_total > 0 else "Tempo favorável",
            delta_color="inverse" if alert_total > 0 else "normal",
        )


def render_executive_summary_card(report: CopilotAnalysisReport) -> None:
    """Renderiza o cartão de resumo da operação elaborado pelo Copiloto.

    Args:
        report: Relatório consolidado do `DispatcherCopilot`.
    """
    html = f"""
    <div class="apoiocep-summary-card">
        <div class="apoiocep-summary-title">Resumo da Operação</div>
        <div style="font-size: 0.92rem; line-height: 1.5;">
            {report.executive_summary}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_recommendations_list(recommendations: list[DispatchRecommendation]) -> None:
    """Renderiza a lista de recomendações táticas com cores semânticas por severidade.

    Args:
        recommendations: Lista de objetos `DispatchRecommendation`.
    """
    if not recommendations:
        st.info("Nenhuma recomendação adicional para o cenário atual.")
        return

    for rec in recommendations:
        border_color, badge_label, badge_bg = _SEVERITY_STYLES.get(
            rec.severity,
            ("#64748B", "NOTA", "#F1F5F9"),
        )
        card_html = f"""
        <div class="apoiocep-rec-card" style="border-left-color: {border_color};">
            <div class="apoiocep-rec-header">
                <span>{rec.title}</span>
                <span style="font-size: 0.72rem; font-weight: 700; color: {border_color};
                             background: {badge_bg}; padding: 0.16rem 0.5rem;
                             border-radius: 6px; border: 1px solid {border_color};">
                    {badge_label}
                </span>
            </div>
            <div class="apoiocep-rec-body">{rec.message}</div>
            <div class="apoiocep-rec-action">
                <strong>Ação recomendada:</strong> {rec.suggested_action}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

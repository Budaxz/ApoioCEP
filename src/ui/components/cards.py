"""Componentes visuais de cartões, indicadores KPI, banner e alertas do Copiloto."""

from __future__ import annotations

import streamlit as st

from src.agent.dispatcher_copilot import (
    CopilotAnalysisReport,
    DispatchAlertSeverity,
    DispatchRecommendation,
)

_SEVERITY_STYLES: dict[DispatchAlertSeverity, tuple[str, str, str]] = {
    DispatchAlertSeverity.CRITICAL: ("#EF4444", "🚨 CRÍTICO", "#FEF2F2"),
    DispatchAlertSeverity.WARNING: ("#F59E0B", "⚠️ ATENÇÃO", "#FFFBEB"),
    DispatchAlertSeverity.INFO: ("#3B82F6", "ℹ️ INFORMAÇÃO", "#EFF6FF"),
}


def render_header_banner() -> None:
    """Renderiza o cabeçalho institucional e acadêmico do painel ApoioCEP."""
    banner_html = """
    <div class="apoiocep-banner">
        <h1>📦 ApoioCEP — Painel Inteligente de Entregas com CEP e Clima</h1>
        <p>
            Projeto A3 de Matemática Computacional Aplicada • Otimização Combinatória (2-Opt &amp;
            Permutações <i>n!</i>), Geometria Geodésica (Haversine) e Copiloto Agêntico de Risco Meteorológico.
        </p>
        <div class="apoiocep-tags">
            <span class="apoiocep-tag">📍 BrasilAPI &amp; ViaCEP Fallback</span>
            <span class="apoiocep-tag">🌦️ Open-Meteo Forecast API</span>
            <span class="apoiocep-tag">🧮 Heurística 2-Opt vs Força Bruta O(n!)</span>
            <span class="apoiocep-tag">🤖 Copiloto Agêntico de Despacho</span>
        </div>
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

    pct_saved = (
        (report.distance_saved_km / report.baseline_distance_km * 100.0)
        if report.baseline_distance_km > 0.0
        else 0.0
    )

    alert_total = report.critical_stops_count + report.high_risk_stops_count

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Paradas na Rota (Espaço n!)",
            value=f"{n_stops} paradas",
            delta=f"{perms_formatted} permutações",
            delta_color="off",
        )

    with col2:
        st.metric(
            label="Distância Total Otimizada",
            value=f"{route.total_distance_km:.2f} km",
            delta=f"-{report.distance_saved_km:.2f} km ({pct_saved:.1f}%)",
            delta_color="normal",
        )

    with col3:
        st.metric(
            label="Paradas em Alerta (Crítico/Alto)",
            value=f"{alert_total} de {n_stops}",
            delta=f"Score médio: {route.average_risk_score:.2f}",
            delta_color="inverse" if alert_total > 0 else "off",
        )

    with col4:
        st.metric(
            label="Melhor Janela Climática (3h)",
            value=report.best_weather_window,
            delta=f"Cálculo em {route.computation_time_ms:.2f} ms",
            delta_color="off",
        )


def render_executive_summary_card(report: CopilotAnalysisReport) -> None:
    """Renderiza o cartão de diagnóstico executivo elaborado pelo Copiloto Agêntico.

    Args:
        report: Relatório consolidado do `DispatcherCopilot`.
    """
    html = f"""
    <div class="apoiocep-summary-card">
        <div class="apoiocep-summary-title">🤖 Diagnóstico Executivo do Copiloto de Despacho</div>
        <div style="font-size: 0.95rem; line-height: 1.55;">
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
        st.info("Nenhuma recomendação tática adicional para o cenário atual.")
        return

    for rec in recommendations:
        border_color, badge_label, badge_bg = _SEVERITY_STYLES.get(
            rec.severity,
            ("#64748B", "ℹ️ NOTA", "#F1F5F9"),
        )
        card_html = f"""
        <div class="apoiocep-rec-card" style="border-left-color: {border_color};">
            <div class="apoiocep-rec-header">
                <span>{rec.title}</span>
                <span style="font-size: 0.75rem; font-weight: 700; color: {border_color};
                             background: {badge_bg}; padding: 0.2rem 0.55rem;
                             border-radius: 9999px; border: 1px solid {border_color};">
                    {badge_label}
                </span>
            </div>
            <div class="apoiocep-rec-body">{rec.message}</div>
            <div class="apoiocep-rec-action">
                <strong>Ação Recomendada:</strong> {rec.suggested_action}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

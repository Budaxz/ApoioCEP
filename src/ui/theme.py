"""Design System, paleta semântica de risco climático e injeção de CSS do ApoioCEP."""

from __future__ import annotations

import streamlit as st

from src.domain.weather import ClimateRiskLevel

RISK_COLORS_HEX: dict[ClimateRiskLevel, str] = {
    ClimateRiskLevel.BAIXO: "#10B981",
    ClimateRiskLevel.MODERADO: "#F59E0B",
    ClimateRiskLevel.ALTO: "#F97316",
    ClimateRiskLevel.CRITICO: "#EF4444",
}

RISK_COLORS_RGB: dict[ClimateRiskLevel, list[int]] = {
    ClimateRiskLevel.BAIXO: [16, 185, 129, 230],
    ClimateRiskLevel.MODERADO: [245, 158, 11, 230],
    ClimateRiskLevel.ALTO: [249, 115, 22, 230],
    ClimateRiskLevel.CRITICO: [239, 68, 68, 230],
}

_RISK_BG_HEX: dict[ClimateRiskLevel, str] = {
    ClimateRiskLevel.BAIXO: "rgba(16, 185, 129, 0.14)",
    ClimateRiskLevel.MODERADO: "rgba(245, 158, 11, 0.14)",
    ClimateRiskLevel.ALTO: "rgba(249, 115, 22, 0.14)",
    ClimateRiskLevel.CRITICO: "rgba(239, 68, 68, 0.14)",
}


def apply_custom_theme() -> None:
    """Injeta folha de estilos CSS moderna no aplicativo Streamlit."""
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .apoiocep-banner {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 60%, #1E3A8A 100%);
            border-radius: 14px;
            padding: 1.5rem 1.75rem;
            color: #F8FAFC;
            margin-bottom: 1.25rem;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .apoiocep-banner h1 {
            margin: 0 0 0.35rem 0;
            font-size: 1.75rem;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: -0.02em;
        }

        .apoiocep-banner p {
            margin: 0 0 0.85rem 0;
            font-size: 0.96rem;
            color: #CBD5E1;
            line-height: 1.5;
        }

        .apoiocep-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .apoiocep-tag {
            background: rgba(255, 255, 255, 0.12);
            color: #E2E8F0;
            padding: 0.28rem 0.72rem;
            border-radius: 9999px;
            font-size: 0.78rem;
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.16);
            backdrop-filter: blur(4px);
        }

        .apoiocep-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.15rem 1.35rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
        }

        .apoiocep-summary-card {
            background: linear-gradient(90deg, #EFF6FF 0%, #F8FAFC 100%);
            border-left: 5px solid #2563EB;
            border-top: 1px solid #DBEAFE;
            border-right: 1px solid #DBEAFE;
            border-bottom: 1px solid #DBEAFE;
            border-radius: 10px;
            padding: 1.1rem 1.35rem;
            margin-bottom: 1.1rem;
            color: #1E293B;
        }

        .apoiocep-summary-title {
            font-size: 0.88rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #1D4ED8;
            margin-bottom: 0.35rem;
        }

        .apoiocep-rec-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left-width: 5px;
            border-radius: 10px;
            padding: 0.95rem 1.2rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
        }

        .apoiocep-rec-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.35rem;
            font-weight: 600;
            font-size: 0.96rem;
            color: #0F172A;
        }

        .apoiocep-rec-body {
            font-size: 0.88rem;
            color: #475569;
            margin-bottom: 0.45rem;
            line-height: 1.45;
        }

        .apoiocep-rec-action {
            font-size: 0.84rem;
            color: #1E293B;
            background: #F8FAFC;
            padding: 0.45rem 0.7rem;
            border-radius: 6px;
            border: 1px solid #E2E8F0;
        }

        .risk-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.22rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def format_risk_badge_html(
    level: ClimateRiskLevel,
    score: float | None = None,
) -> str:
    """Retorna HTML de um badge estilizado com a cor semântica do nível de risco climático.

    Args:
        level: Nível qualitativo de risco climático (`ClimateRiskLevel`).
        score: Score numérico contínuo opcional (0.0 a 1.0) para exibição junto ao rótulo.

    Returns:
        String HTML contendo um elemento `<span class="risk-badge">`.
    """
    color_hex = RISK_COLORS_HEX.get(level, "#64748B")
    bg_rgba = _RISK_BG_HEX.get(level, "rgba(100, 116, 139, 0.14)")
    score_suffix = f" ({score:.2f})" if score is not None else ""
    return (
        f'<span class="risk-badge" style="color: {color_hex}; '
        f'background-color: {bg_rgba}; border: 1px solid {color_hex};">'
        f"{level.value}{score_suffix}</span>"
    )

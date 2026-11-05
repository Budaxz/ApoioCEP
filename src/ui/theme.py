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
    """Injeta folha de estilos CSS mobile-first e minimalista no aplicativo Streamlit."""
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1120px;
        }

        .apoiocep-banner {
            background: #0F172A;
            border: 1px solid #1E293B;
            border-radius: 10px;
            padding: 1.15rem 1.4rem;
            color: #F8FAFC;
            margin-bottom: 1rem;
        }

        .apoiocep-banner h1 {
            margin: 0 0 0.2rem 0;
            font-size: 1.35rem;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: -0.02em;
        }

        .apoiocep-banner p {
            margin: 0;
            font-size: 0.88rem;
            color: #94A3B8;
            line-height: 1.45;
        }

        .apoiocep-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.85rem;
        }

        .route-step-card {
            display: flex;
            align-items: flex-start;
            gap: 0.85rem;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left-width: 4px;
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.65rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }

        .step-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 2rem;
            height: 2rem;
            border-radius: 8px;
            background: #0F172A;
            color: #FFFFFF;
            font-size: 0.88rem;
            font-weight: 700;
            flex-shrink: 0;
        }

        .route-step-content {
            flex: 1;
            min-width: 0;
        }

        .route-step-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 0.25rem;
        }

        .route-step-title {
            font-size: 0.96rem;
            font-weight: 600;
            color: #0F172A;
            line-height: 1.3;
        }

        .route-step-address {
            font-size: 0.86rem;
            color: #334155;
            margin-bottom: 0.35rem;
            line-height: 1.4;
        }

        .route-step-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            font-size: 0.8rem;
            color: #64748B;
        }

        .route-step-alert {
            margin-top: 0.45rem;
            font-size: 0.8rem;
            font-weight: 500;
            color: #0F172A;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            padding: 0.35rem 0.6rem;
        }

        .apoiocep-summary-card {
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #0F172A;
            border-radius: 8px;
            padding: 0.95rem 1.15rem;
            margin-bottom: 1rem;
            color: #1E293B;
        }

        .apoiocep-summary-title {
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #475569;
            margin-bottom: 0.3rem;
        }

        .apoiocep-rec-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left-width: 4px;
            border-radius: 8px;
            padding: 0.85rem 1.05rem;
            margin-bottom: 0.65rem;
        }

        .apoiocep-rec-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin-bottom: 0.3rem;
            font-weight: 600;
            font-size: 0.92rem;
            color: #0F172A;
        }

        .apoiocep-rec-body {
            font-size: 0.86rem;
            color: #475569;
            margin-bottom: 0.4rem;
            line-height: 1.45;
        }

        .apoiocep-rec-action {
            font-size: 0.82rem;
            color: #0F172A;
            background: #F8FAFC;
            padding: 0.4rem 0.65rem;
            border-radius: 6px;
            border: 1px solid #E2E8F0;
        }

        .risk-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.18rem 0.55rem;
            border-radius: 6px;
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-top: 1rem;
                padding-bottom: 1.5rem;
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }

            .apoiocep-banner {
                padding: 0.95rem 1.1rem;
            }

            .apoiocep-banner h1 {
                font-size: 1.2rem;
            }

            .route-step-card {
                padding: 0.8rem 0.9rem;
                gap: 0.7rem;
            }
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

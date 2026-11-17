"""Ponto de entrada principal da aplicação Streamlit ApoioCEP."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from config.settings import settings  # noqa: E402
from src.agent.dispatcher_copilot import DispatcherCopilot  # noqa: E402
from src.domain.delivery import DeliveryStop  # noqa: E402
from src.services.cache_service import CacheService  # noqa: E402
from src.services.cep_service import CEPService  # noqa: E402
from src.services.weather_service import WeatherService  # noqa: E402
from src.ui.components.cards import render_header_banner  # noqa: E402
from src.ui.theme import apply_custom_theme  # noqa: E402
from src.ui.views import (  # noqa: E402
    load_default_curitiba_stops,
    refresh_stops_with_live_apis,
    render_dashboard_view,
    render_route_planner_view,
)


def init_session_state() -> None:
    """Inicializa o estado da sessão do Streamlit com o roteiro padrão de Curitiba."""
    if "origin" not in st.session_state or "stops" not in st.session_state:
        default_origin, default_stops = load_default_curitiba_stops()
        st.session_state["origin"] = default_origin
        st.session_state["stops"] = default_stops


def render_sidebar(
    cep_service: CEPService,
    weather_service: WeatherService,
) -> float:
    """Renderiza a barra lateral enxuta com controle de clima, atualização e resumo técnico.

    Args:
        cep_service: Instância de `CEPService`.
        weather_service: Instância de `WeatherService`.

    Returns:
        Valor selecionado para o coeficiente de aversão ao risco climático ($\\alpha$).
    """
    with st.sidebar:
        st.markdown("### Ajuste da Rota")
        st.caption(
            "Defina o quanto o roteirizador deve antecipar ou contornar áreas com chuva forte:"
        )

        alpha = float(
            st.slider(
                "Priorizar desvio de chuva (α)",
                min_value=0.0,
                max_value=2.0,
                value=0.5,
                step=0.1,
                help=(
                    "α = 0.0 considera apenas a menor distância (Haversine). "
                    "Valores maiores priorizam antecipar ou contornar áreas com previsão de chuva forte."
                ),
            )
        )

        st.divider()
        st.markdown("### Dados da Rota")
        if st.button(
            "Atualizar Clima Agora",
            use_container_width=True,
            type="primary",
            key="sidebar_sync_apis_btn",
        ):
            with st.spinner("Consultando CEP e previsão do tempo..."):
                origin_curr: DeliveryStop = st.session_state["origin"]
                stops_curr: list[DeliveryStop] = st.session_state["stops"]
                updated_origin, updated_stops = refresh_stops_with_live_apis(
                    origin_curr,
                    stops_curr,
                    cep_service,
                    weather_service,
                )
                st.session_state["origin"] = updated_origin
                st.session_state["stops"] = updated_stops
            st.success("Clima e endereços atualizados.")
            st.rerun()

        if st.button(
            "Restaurar Roteiro Padrão",
            use_container_width=True,
            key="sidebar_restore_demo_btn",
        ):
            default_origin, default_stops = load_default_curitiba_stops()
            st.session_state["origin"] = default_origin
            st.session_state["stops"] = default_stops
            st.rerun()

        st.divider()
        st.caption(
            f"{settings.APP_NAME} v{settings.APP_VERSION} · "
            f"Cache {settings.CACHE_TTL_HOURS}h · "
            "BrasilAPI / ViaCEP / Open-Meteo"
        )

    return alpha


def main() -> None:
    """Executa o fluxo principal da interface gráfica Streamlit do ApoioCEP."""
    st.set_page_config(
        page_title="ApoioCEP | Roteirizador de Entregas",
        page_icon=None,
        layout="wide",
    )

    apply_custom_theme()
    init_session_state()

    cache_service = CacheService()
    cep_service = CEPService(cache=cache_service)
    weather_service = WeatherService(cache=cache_service)

    alpha = render_sidebar(cep_service=cep_service, weather_service=weather_service)

    render_header_banner()

    origin: DeliveryStop = st.session_state["origin"]
    stops: list[DeliveryStop] = st.session_state["stops"]

    copilot = DispatcherCopilot()
    report = copilot.analyze_and_optimize(origin=origin, stops=stops, alpha=alpha)

    tab_dashboard, tab_planner = st.tabs(
        [
            "Rota do Dia",
            "Gerenciar Entregas",
        ]
    )

    with tab_dashboard:
        render_dashboard_view(report=report)

    with tab_planner:
        render_route_planner_view(
            cep_service=cep_service,
            weather_service=weather_service,
        )


if __name__ == "__main__":
    main()

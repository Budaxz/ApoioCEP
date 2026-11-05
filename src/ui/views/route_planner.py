"""Tela de planejamento de entregas, cadastro de paradas por CEP e sincronização com APIs."""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from src.domain.address import Address, Coordinates
from src.domain.delivery import DeliveryPriority, DeliveryStop
from src.domain.weather import HourlyWeatherPoint, WeatherForecast
from src.mathematics.risk_matrix import evaluate_stops_risk
from src.services.cep_service import (
    CURITIBA_NEIGHBORHOOD_COORDS,
    DEFAULT_CURITIBA_COORDS,
    CEPLookupError,
    CEPService,
)
from src.services.weather_service import WeatherLookupError, WeatherService
from src.ui.theme import format_risk_badge_html

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MOCK_DELIVERIES_PATH = _PROJECT_ROOT / "data" / "mock_deliveries.json"

DELIVERY_WINDOW_OPTIONS: list[str] = [
    "08:00 - 11:00",
    "09:00 - 12:00",
    "10:00 - 13:00",
    "13:00 - 16:00",
    "14:00 - 17:00",
    "15:00 - 18:00",
]


def _normalize_neighborhood(name: str) -> str:
    """Remove acentos e normaliza o nome do bairro para busca no dicionário de coordenadas."""
    normalized = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _resolve_neighborhood_coords(bairro: str, stop_index: int = 0) -> Coordinates:
    """Obtém as coordenadas do bairro de Curitiba com leve deslocamento determinístico se repetido."""
    norm = _normalize_neighborhood(bairro)
    base = CURITIBA_NEIGHBORHOOD_COORDS.get(norm, DEFAULT_CURITIBA_COORDS)
    if stop_index > 0 and norm == "centro":
        return Coordinates(
            latitude=round(base.latitude - (0.0022 * stop_index), 6),
            longitude=round(base.longitude + (0.0031 * stop_index), 6),
        )
    return base


def _build_realistic_hourly_forecast(
    coordinates: Coordinates,
    profile_index: int,
) -> WeatherForecast:
    """Gera uma série meteorológica horária realista de 24h para demonstração imediata.

    Os perfis simulam a progressão típica de instabilidade atmosférica em Curitiba:
    manhã firme/parcialmente nublada e formação de pancadas de chuva moderadas a severas
    entre a tarde e o início da noite, variando por microclima de cada bairro.

    Args:
        coordinates: Coordenadas geográficas da parada.
        profile_index: Índice da parada para diversificar a intensidade de chuva e vento.

    Returns:
        Instância populada de `WeatherForecast` com 24 pontos horários do dia atual.
    """
    now = datetime.now()
    base_date = datetime(now.year, now.month, now.day, 0, 0, 0)

    # Perfis de severidade por índice: (fator_chuva, fator_vento, hora_pico)
    profiles: list[tuple[float, float, int]] = [
        (0.25, 0.45, 16),  # Perfil 0: Tempo estável / chuva fraca isolada
        (0.45, 0.55, 15),  # Perfil 1: Chuva leve a moderada ao final da manhã/tarde
        (0.85, 0.75, 14),  # Perfil 2: Pancada de chuva forte à tarde (Risco ALTO)
        (0.65, 0.65, 15),  # Perfil 3: Instabilidade moderada a alta à tarde
        (1.35, 1.05, 16),  # Perfil 4: Tempestade severa no fim da tarde (Risco CRÍTICO)
    ]
    rain_scale, wind_scale, peak_hour = profiles[profile_index % len(profiles)]

    hourly_points: list[HourlyWeatherPoint] = []
    for hour in range(24):
        timestamp = base_date.replace(hour=hour)

        # Curva térmica diária entre 15°C (madrugada) e 25°C (14h)
        temp_delta = 5.0 * (1.0 - abs(hour - 14) / 12.0)
        temperature_c = round(15.5 + max(0.0, temp_delta) - (0.4 * rain_scale), 1)

        distance_from_peak = abs(hour - peak_hour)
        if 8 <= hour <= 11:
            # Manhã com condições favoráveis para despacho (janela recomendada)
            precip_mm = round(max(0.0, (0.6 if hour == 11 else 0.1) * rain_scale), 1)
            prob_pct = round(min(100.0, 15.0 + hour * 2.0 * rain_scale), 1)
            wind_kmh = round(11.0 + hour * 0.8 * wind_scale, 1)
            wmo_code = 1 if precip_mm < 0.5 else 51
        elif distance_from_peak <= 2:
            # Pico de instabilidade na janela vespertina
            intensity = (3 - distance_from_peak) / 3.0
            precip_mm = round(14.5 * rain_scale * intensity, 1)
            prob_pct = round(min(100.0, 62.0 + 32.0 * rain_scale * intensity), 1)
            wind_kmh = round(26.0 + 27.0 * wind_scale * intensity, 1)
            wmo_code = 95 if precip_mm >= 15.0 else (65 if precip_mm >= 5.0 else 61)
        else:
            precip_mm = round(max(0.0, 1.2 * rain_scale * (1.0 - distance_from_peak / 10.0)), 1)
            prob_pct = round(min(100.0, max(10.0, 35.0 * rain_scale)), 1)
            wind_kmh = round(14.0 + 8.0 * wind_scale, 1)
            wmo_code = 3 if precip_mm > 0.2 else 1

        hourly_points.append(
            HourlyWeatherPoint(
                timestamp=timestamp,
                temperature_c=temperature_c,
                precipitation_probability=prob_pct,
                precipitation_mm=precip_mm,
                wind_speed_kmh=wind_kmh,
                weather_code=wmo_code,
            )
        )

    return WeatherForecast(
        coordinates=coordinates,
        fetched_at=now,
        hourly=hourly_points,
    )


def load_default_curitiba_stops() -> tuple[DeliveryStop, list[DeliveryStop]]:
    """Carrega o Centro de Distribuição padrão e as paradas de demonstração em Curitiba.

    Lê o arquivo `data/mock_deliveries.json`, associa as coordenadas de cada bairro a partir
    de `CURITIBA_NEIGHBORHOOD_COORDS`, popula previsões meteorológicas horárias realistas
    de 24h e calcula os scores iniciais de risco climático.

    Returns:
        Tupla `(origin, stops)` pronta para análise e renderização imediata.
    """
    origin_coords = DEFAULT_CURITIBA_COORDS
    origin_address = Address(
        cep="80020-010",
        logradouro="Praça Tiradentes, 100 (CD Central Curitiba)",
        bairro="Centro",
        cidade="Curitiba",
        uf="PR",
        coordinates=origin_coords,
        provider="mock_curitiba",
    )
    origin_forecast = _build_realistic_hourly_forecast(origin_coords, profile_index=0)
    origin_stop = DeliveryStop(
        id="CD-ORIGEM",
        recipient_name="Centro de Distribuição Central (Origem)",
        address=origin_address,
        package_weight_kg=1.0,
        priority=DeliveryPriority.ALTA,
        delivery_window="08:00 - 18:00",
        weather_forecast=origin_forecast,
    )

    raw_items: list[dict[str, Any]] = []
    if _MOCK_DELIVERIES_PATH.exists():
        try:
            raw_text = _MOCK_DELIVERIES_PATH.read_text(encoding="utf-8")
            loaded_data = json.loads(raw_text)
            if isinstance(loaded_data, list):
                raw_items = loaded_data
        except Exception as exc:
            logger.warning(f"Falha ao ler {_MOCK_DELIVERIES_PATH}: {exc}")

    stops: list[DeliveryStop] = []
    for idx, item in enumerate(raw_items, start=1):
        bairro = str(item.get("bairro", "Centro"))
        coords = _resolve_neighborhood_coords(bairro, stop_index=idx)
        address = Address(
            cep=str(item.get("cep", "80020-010")),
            logradouro=str(item.get("logradouro", "Logradouro não informado")),
            bairro=bairro,
            cidade=str(item.get("cidade", "Curitiba")),
            uf=str(item.get("uf", "PR")),
            coordinates=coords,
            provider="mock_curitiba",
        )
        priority_str = str(item.get("priority", "MEDIA")).upper()
        try:
            priority = DeliveryPriority(priority_str)
        except ValueError:
            priority = DeliveryPriority.MEDIA

        forecast = _build_realistic_hourly_forecast(coords, profile_index=idx)
        stop = DeliveryStop(
            id=str(item.get("id", f"DEL-{idx:03d}")),
            recipient_name=str(item.get("recipient_name", f"Destinatário {idx}")),
            address=address,
            package_weight_kg=float(item.get("package_weight_kg", 1.0)),
            priority=priority,
            delivery_window=str(item.get("delivery_window", "09:00 - 12:00")),
            weather_forecast=forecast,
        )
        stops.append(stop)

    evaluated_origin = evaluate_stops_risk([origin_stop])[0]
    evaluated_stops = evaluate_stops_risk(stops)
    return (evaluated_origin, evaluated_stops)


def _refresh_single_stop(
    stop: DeliveryStop,
    cep_service: CEPService,
    weather_service: WeatherService,
) -> DeliveryStop:
    """Atualiza endereço e previsão climática de uma parada preservando dados em caso de falha."""
    updated_address = stop.address
    try:
        fetched_addr = cep_service.fetch_address(stop.address.cep)
        updated_address = fetched_addr
    except Exception as exc:
        logger.warning(
            f"Mantendo endereço anterior para parada {stop.id} (CEP {stop.address.cep}): {exc}"
        )

    coords = updated_address.coordinates or stop.address.coordinates or DEFAULT_CURITIBA_COORDS
    if updated_address.coordinates is None:
        updated_address = updated_address.model_copy(update={"coordinates": coords})

    updated_forecast = stop.weather_forecast
    try:
        updated_forecast = weather_service.fetch_forecast(coords, days=1)
    except Exception as exc:
        logger.warning(f"Mantendo previsão anterior para parada {stop.id}: {exc}")

    refreshed = stop.model_copy(
        update={
            "address": updated_address,
            "weather_forecast": updated_forecast,
        }
    )
    return evaluate_stops_risk([refreshed])[0]


def refresh_stops_with_live_apis(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    cep_service: CEPService,
    weather_service: WeatherService,
) -> tuple[DeliveryStop, list[DeliveryStop]]:
    """Consulta BrasilAPI/ViaCEP e Open-Meteo ao vivo para a origem e todas as paradas.

    Trata falhas de rede ou timeout de maneira graciosa por parada, mantendo os dados
    anteriores caso alguma requisição falhe.

    Args:
        origin: Ponto de partida atual.
        stops: Lista de paradas de entrega atuais.
        cep_service: Instância de `CEPService`.
        weather_service: Instância de `WeatherService`.

    Returns:
        Tupla `(updated_origin, updated_stops)` com riscos recalculados.
    """
    updated_origin = _refresh_single_stop(origin, cep_service, weather_service)
    updated_stops = [
        _refresh_single_stop(stop, cep_service, weather_service) for stop in stops
    ]
    return (updated_origin, updated_stops)


def render_route_planner_view(
    cep_service: CEPService,
    weather_service: WeatherService,
) -> None:
    """Renderiza a aba de gerenciamento de paradas de entrega e consulta de CEP ao vivo.

    Args:
        cep_service: Serviço de consulta resiliente de CEP.
        weather_service: Serviço de previsão meteorológica Open-Meteo.
    """
    st.markdown("### Gerenciar Entregas")
    st.caption(
        "Cadastre novos pontos de entrega informando o CEP. O sistema localiza automaticamente "
        "o endereço e a previsão de chuva para recalcular a melhor sequência de rota."
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button(
            "Atualizar Clima Real",
            use_container_width=True,
            type="primary",
            key="btn_planner_refresh_apis",
        ):
            with st.spinner("Consultando BrasilAPI/ViaCEP e Open-Meteo para todas as paradas..."):
                origin_curr: DeliveryStop = st.session_state["origin"]
                stops_curr: list[DeliveryStop] = st.session_state["stops"]
                new_origin, new_stops = refresh_stops_with_live_apis(
                    origin_curr,
                    stops_curr,
                    cep_service,
                    weather_service,
                )
                st.session_state["origin"] = new_origin
                st.session_state["stops"] = new_stops
            st.success("Endereços e previsão do tempo atualizados.")
            st.rerun()

    with action_col2:
        if st.button(
            "Restaurar Roteiro Padrão",
            use_container_width=True,
            key="btn_planner_restore_demo",
        ):
            default_origin, default_stops = load_default_curitiba_stops()
            st.session_state["origin"] = default_origin
            st.session_state["stops"] = default_stops
            st.info("Roteiro padrão de Curitiba restaurado.")
            st.rerun()

    st.divider()

    form_col, list_col = st.columns([2, 3], gap="large")

    with form_col:
        st.markdown("#### Nova Entrega")
        with st.form("add_delivery_stop_form", clear_on_submit=True):
            recipient_name = st.text_input(
                "Destinatário / Cliente",
                placeholder="Ex.: Farmácia Água Verde",
            )
            cep_input = st.text_input(
                "CEP (8 dígitos)",
                placeholder="Ex.: 80240-000",
                max_chars=9,
            )
            weight_col, prio_col = st.columns(2)
            with weight_col:
                package_weight = st.number_input(
                    "Peso (kg)",
                    min_value=0.1,
                    max_value=500.0,
                    value=2.0,
                    step=0.5,
                )
            with prio_col:
                priority_str = st.selectbox(
                    "Prioridade",
                    options=[p.value for p in DeliveryPriority],
                    index=1,
                )

            delivery_window = st.selectbox(
                "Janela de Entrega",
                options=DELIVERY_WINDOW_OPTIONS,
                index=1,
            )

            submitted = st.form_submit_button(
                "Adicionar Entrega",
                use_container_width=True,
                type="primary",
            )

            if submitted:
                clean_name = recipient_name.strip()
                if not clean_name:
                    st.error("Informe o nome do destinatário para cadastrar a parada.")
                else:
                    try:
                        with st.spinner(f"Buscando endereço e clima para o CEP {cep_input}..."):
                            address = cep_service.fetch_address(cep_input)
                            coords = address.coordinates or DEFAULT_CURITIBA_COORDS
                            try:
                                forecast = weather_service.fetch_forecast(coords, days=1)
                            except WeatherLookupError as w_exc:
                                logger.warning(
                                    f"Fallback para previsão sintética no CEP {cep_input}: {w_exc}"
                                )
                                forecast = _build_realistic_hourly_forecast(
                                    coords,
                                    profile_index=len(st.session_state["stops"]) + 1,
                                )

                            existing_stops: list[DeliveryStop] = st.session_state["stops"]
                            next_num = len(existing_stops) + 1
                            new_stop = DeliveryStop(
                                id=f"DEL-{next_num:03d}",
                                recipient_name=clean_name,
                                address=address,
                                package_weight_kg=float(package_weight),
                                priority=DeliveryPriority(str(priority_str)),
                                delivery_window=str(delivery_window),
                                weather_forecast=forecast,
                            )
                            evaluated_new = evaluate_stops_risk([new_stop])[0]
                            st.session_state["stops"] = [*existing_stops, evaluated_new]

                        st.success(
                            f"Parada '{clean_name}' ({address.logradouro} - {address.bairro}) "
                            "adicionada."
                        )
                        st.rerun()
                    except (CEPLookupError, ValueError) as exc:
                        st.error(f"Não foi possível validar o CEP informado: {exc}")

    with list_col:
        origin_stop: DeliveryStop = st.session_state["origin"]
        stops_list: list[DeliveryStop] = st.session_state["stops"]

        st.markdown(f"#### Entregas Cadastradas ({len(stops_list)})")
        st.markdown(
            f"**Ponto de Partida (Origem):** `{origin_stop.address.cep}` — "
            f"{origin_stop.address.logradouro} ({origin_stop.address.bairro}, "
            f"{origin_stop.address.cidade}/{origin_stop.address.uf})"
        )

        if not stops_list:
            st.warning(
                "Nenhuma entrega cadastrada. Utilize o formulário ao lado ou "
                "restaure o roteiro padrão."
            )
        else:
            for idx, stop in enumerate(stops_list):
                badge_html = format_risk_badge_html(stop.risk_level)
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

                with st.container(border=True):
                    header_col, btn_col = st.columns([4, 1])
                    with header_col:
                        st.markdown(
                            f"**{stop.id} — {stop.recipient_name}** &nbsp; {badge_html}",
                            unsafe_allow_html=True,
                        )
                        st.caption(
                            f"{stop.address.logradouro} · {stop.address.bairro} "
                            f"(CEP {stop.address.cep})  \n"
                            f"Janela: {stop.delivery_window} | "
                            f"Peso: {stop.package_weight_kg:.1f} kg | "
                            f"Prioridade: {stop.priority.value} | "
                            f"Chuva máx: {max_rain:.1f} mm | "
                            f"Vento: {max_wind:.0f} km/h"
                        )
                    with btn_col:
                        if st.button(
                            "Remover",
                            key=f"remove_stop_{stop.id}_{idx}",
                            help=f"Remover parada {stop.recipient_name}",
                            use_container_width=True,
                        ):
                            remaining = [
                                s for i, s in enumerate(stops_list) if i != idx
                            ]
                            st.session_state["stops"] = remaining
                            st.rerun()

"""Testes unitários para o Copiloto de Despacho Agêntico e o serviço de análise via Pandas."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.agent import (
    CopilotAnalysisReport,
    DispatchAlertSeverity,
    DispatcherCopilot,
)
from src.domain.address import Address, Coordinates
from src.domain.delivery import DeliveryPriority, DeliveryStop
from src.domain.weather import ClimateRiskLevel, HourlyWeatherPoint, WeatherForecast
from src.services.route_analytics import (
    STOPS_COLUMNS,
    WEATHER_COLUMNS,
    export_route_csv,
    stops_to_dataframe,
    weather_to_dataframe,
)


def _make_forecast(
    coords: Coordinates,
    precip_mm: float = 0.0,
    prob_pct: float = 0.0,
    wind_kmh: float = 5.0,
    calm_window_start: int | None = None,
) -> WeatherForecast:
    """Cria uma previsão meteorológica horária sintética entre 08h e 18h."""
    points: list[HourlyWeatherPoint] = []
    for hour in range(8, 19):
        is_calm = (
            calm_window_start is not None
            and calm_window_start <= hour < calm_window_start + 3
        )
        points.append(
            HourlyWeatherPoint(
                timestamp=datetime(2026, 11, 5, hour, 0),
                temperature_c=21.0,
                precipitation_probability=5.0 if is_calm else prob_pct,
                precipitation_mm=0.0 if is_calm else precip_mm,
                wind_speed_kmh=4.0 if is_calm else wind_kmh,
                weather_code=0 if is_calm else 61,
            )
        )
    return WeatherForecast(coordinates=coords, hourly=points)


def _make_origin() -> DeliveryStop:
    """Cria o ponto de partida (Centro de Distribuição no Centro de Curitiba)."""
    return DeliveryStop(
        id="CD-00",
        recipient_name="CD Central Curitiba",
        address=Address(
            cep="80010-000",
            logradouro="Praça Tiradentes",
            bairro="Centro",
            cidade="Curitiba",
            uf="PR",
            coordinates=Coordinates(latitude=-25.4284, longitude=-49.2733),
        ),
    )


def test_dispatcher_copilot_analyze_and_optimize_with_mixed_risks() -> None:
    """Deve avaliar riscos, otimizar rota, identificar janela e emitir alertas CRITICAL, WARNING e INFO."""
    origin = _make_origin()

    # Parada 1: distante (Pinheirinho) e risco BAIXO
    coords_low = Coordinates(latitude=-25.5136, longitude=-49.2953)
    stop_low = DeliveryStop(
        id="STOP-1",
        recipient_name="Cliente Baixo Risco",
        address=Address(
            cep="81880-000",
            logradouro="Av. Winston Churchill",
            bairro="Pinheirinho",
            cidade="Curitiba",
            uf="PR",
            coordinates=coords_low,
        ),
        package_weight_kg=2.5,
        priority=DeliveryPriority.BAIXA,
        delivery_window="09:00 - 17:00",
        weather_forecast=_make_forecast(
            coords_low, precip_mm=0.0, prob_pct=10.0, wind_kmh=8.0, calm_window_start=10
        ),
    )

    # Parada 2: próxima ao Centro (Batel) e risco ALTO
    coords_high = Coordinates(latitude=-25.4422, longitude=-49.2869)
    stop_high = DeliveryStop(
        id="STOP-2",
        recipient_name="Cliente Alto Risco",
        address=Address(
            cep="80420-090",
            logradouro="Av. do Batel",
            bairro="Batel",
            cidade="Curitiba",
            uf="PR",
            coordinates=coords_high,
        ),
        package_weight_kg=5.0,
        priority=DeliveryPriority.ALTA,
        delivery_window="08:00 - 18:00",
        weather_forecast=_make_forecast(
            coords_high, precip_mm=9.0, prob_pct=85.0, wind_kmh=38.0, calm_window_start=10
        ),
    )

    # Parada 3: intermediária (Água Verde) e risco CRÍTICO
    coords_crit = Coordinates(latitude=-25.4561, longitude=-49.2814)
    stop_crit = DeliveryStop(
        id="STOP-3",
        recipient_name="Cliente Risco Crítico",
        address=Address(
            cep="80240-000",
            logradouro="Av. República Argentina",
            bairro="Água Verde",
            cidade="Curitiba",
            uf="PR",
            coordinates=coords_crit,
        ),
        package_weight_kg=12.0,
        priority=DeliveryPriority.ALTA,
        delivery_window="08:00 - 18:00",
        weather_forecast=_make_forecast(
            coords_crit, precip_mm=22.0, prob_pct=98.0, wind_kmh=55.0, calm_window_start=10
        ),
    )

    # Passamos na ordem sub-ótima (Pinheirinho -> Centro/Batel -> Água Verde)
    copilot = DispatcherCopilot()
    report = copilot.analyze_and_optimize(
        origin=origin,
        stops=[stop_low, stop_high, stop_crit],
        alpha=0.4,
    )

    assert isinstance(report, CopilotAnalysisReport)
    assert len(report.route_plan.ordered_stops) == 3
    assert report.route_plan.total_permutations_possible == 6
    assert report.baseline_distance_km > 0.0
    assert report.route_plan.total_distance_km <= report.baseline_distance_km
    assert report.distance_saved_km >= 0.0
    assert report.critical_stops_count >= 1
    assert report.high_risk_stops_count >= 1
    assert report.best_weather_window == "10:00 - 13:00"
    assert "parada(s)" in report.executive_summary

    severities = {rec.severity for rec in report.recommendations}
    assert DispatchAlertSeverity.CRITICAL in severities
    assert DispatchAlertSeverity.WARNING in severities
    assert DispatchAlertSeverity.INFO in severities


def test_dispatcher_copilot_empty_stops() -> None:
    """Deve lidar graciosamente com lista vazia de paradas."""
    origin = _make_origin()
    copilot = DispatcherCopilot()
    report = copilot.analyze_and_optimize(origin=origin, stops=[], alpha=0.5)

    assert len(report.route_plan.ordered_stops) == 0
    assert report.baseline_distance_km == 0.0
    assert report.distance_saved_km == 0.0
    assert report.critical_stops_count == 0
    assert report.high_risk_stops_count == 0
    assert report.best_weather_window == "09:00 - 12:00"
    assert "Nenhuma parada" in report.executive_summary


def test_stops_to_dataframe_structure_and_cumulative_distances() -> None:
    """Deve gerar DataFrame com as 15 colunas exatas e distâncias acumuladas consistentes."""
    origin = _make_origin()
    coords_1 = Coordinates(latitude=-25.4422, longitude=-49.2869)
    coords_2 = Coordinates(latitude=-25.4561, longitude=-49.2814)

    stop_1 = DeliveryStop(
        id="S1",
        recipient_name="Destinatário 1",
        address=Address(
            cep="80420-090",
            logradouro="Av. do Batel",
            bairro="Batel",
            cidade="Curitiba",
            uf="PR",
            coordinates=coords_1,
        ),
        package_weight_kg=3.2,
        priority=DeliveryPriority.ALTA,
        delivery_window="09:00 - 12:00",
        weather_forecast=_make_forecast(coords_1, precip_mm=12.5, wind_kmh=30.0),
        risk_score=0.65,
        risk_level=ClimateRiskLevel.ALTO,
    )
    stop_2 = DeliveryStop(
        id="S2",
        recipient_name="Destinatário 2",
        address=Address(
            cep="80240-000",
            logradouro="Av. República Argentina",
            bairro="Água Verde",
            cidade="Curitiba",
            uf="PR",
            coordinates=coords_2,
        ),
        package_weight_kg=1.5,
        priority=DeliveryPriority.MEDIA,
        delivery_window="13:00 - 17:00",
        weather_forecast=None,
        risk_score=0.1,
        risk_level=ClimateRiskLevel.BAIXO,
    )

    df = stops_to_dataframe(origin, [stop_1, stop_2])

    assert list(df.columns) == STOPS_COLUMNS
    assert len(df) == 2
    assert list(df["Ordem"]) == [1, 2]
    assert list(df["ID"]) == ["S1", "S2"]
    assert df.loc[0, "Chuva_Max_mm"] == 12.5
    assert df.loc[1, "Chuva_Max_mm"] == 0.0

    leg_1 = float(df.loc[0, "Distancia_Trecho_km"])
    leg_2 = float(df.loc[1, "Distancia_Trecho_km"])
    cum_1 = float(df.loc[0, "Distancia_Acumulada_km"])
    cum_2 = float(df.loc[1, "Distancia_Acumulada_km"])

    assert leg_1 > 0.0
    assert leg_2 > 0.0
    assert cum_1 == leg_1
    assert cum_2 == round(leg_1 + leg_2, 4)

    empty_df = stops_to_dataframe(origin, [])
    assert list(empty_df.columns) == STOPS_COLUMNS
    assert empty_df.empty


def test_weather_to_dataframe_and_rolling_mean() -> None:
    """Deve construir o DataFrame meteorológico e calcular corretamente a média móvel de 3h."""
    coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
    points = [
        HourlyWeatherPoint(
            timestamp=datetime(2026, 11, 5, 8, 0),
            temperature_c=19.0,
            precipitation_probability=20.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
        ),
        HourlyWeatherPoint(
            timestamp=datetime(2026, 11, 5, 9, 0),
            temperature_c=20.0,
            precipitation_probability=50.0,
            precipitation_mm=3.0,
            wind_speed_kmh=15.0,
        ),
        HourlyWeatherPoint(
            timestamp=datetime(2026, 11, 5, 10, 0),
            temperature_c=21.0,
            precipitation_probability=80.0,
            precipitation_mm=6.0,
            wind_speed_kmh=25.0,
        ),
        HourlyWeatherPoint(
            timestamp=datetime(2026, 11, 5, 11, 0),
            temperature_c=22.0,
            precipitation_probability=90.0,
            precipitation_mm=15.0,
            wind_speed_kmh=40.0,
        ),
    ]
    forecast = WeatherForecast(coordinates=coords, hourly=points)

    df = weather_to_dataframe(forecast, label="Batel")

    assert list(df.columns) == WEATHER_COLUMNS
    assert len(df) == 4
    assert list(df["Local"].unique()) == ["Batel"]
    assert list(df["Hora"]) == ["08:00", "09:00", "10:00", "11:00"]

    # Média móvel de 3h para [0.0, 3.0, 6.0, 15.0]:
    # idx 0: mean([0.0]) = 0.0
    # idx 1: mean([0.0, 3.0]) = 1.5
    # idx 2: mean([0.0, 3.0, 6.0]) = 3.0
    # idx 3: mean([3.0, 6.0, 15.0]) = 8.0
    assert list(df["Precipitacao_Media_Movel_3h"]) == [0.0, 1.5, 3.0, 8.0]
    assert list(df["Nivel_Risco"]) == ["BAIXO", "MODERADO", "ALTO", "CRITICO"]

    empty_df = weather_to_dataframe(WeatherForecast(coordinates=coords, hourly=[]))
    assert list(empty_df.columns) == WEATHER_COLUMNS
    assert empty_df.empty


def test_export_route_csv_utf8_sig() -> None:
    """Deve exportar DataFrame para bytes CSV com BOM UTF-8 (utf-8-sig) e sem índice."""
    df = pd.DataFrame(
        [
            {"Ordem": 1, "Destinatario": "João Café", "Bairro": "Água Verde"},
            {"Ordem": 2, "Destinatario": "Maria Ação", "Bairro": "Mercês"},
        ]
    )

    csv_bytes = export_route_csv(df)

    assert isinstance(csv_bytes, bytes)
    # Verifica presença do BOM UTF-8 (\xef\xbb\xbf)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")

    decoded = csv_bytes.decode("utf-8-sig")
    assert "Ordem,Destinatario,Bairro" in decoded
    assert "João Café" in decoded
    assert "Água Verde" in decoded

"""Serviço de análise tabular e exploratória de rotas e séries meteorológicas via Pandas."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.domain.delivery import DeliveryStop
from src.domain.weather import WeatherForecast

STOPS_COLUMNS: list[str] = [
    "Ordem",
    "ID",
    "Destinatario",
    "CEP",
    "Bairro",
    "Cidade",
    "Peso_kg",
    "Prioridade",
    "Janela",
    "Distancia_Trecho_km",
    "Distancia_Acumulada_km",
    "Score_Risco",
    "Nivel_Risco",
    "Chuva_Max_mm",
    "Vento_Max_kmh",
]

WEATHER_COLUMNS: list[str] = [
    "DataHora",
    "Hora",
    "Local",
    "Temperatura_C",
    "Prob_Chuva_Pct",
    "Precipitacao_mm",
    "Vento_kmh",
    "Nivel_Risco",
    "Precipitacao_Media_Movel_3h",
]


def _calculate_leg_distance_km(point_a: DeliveryStop, point_b: DeliveryStop) -> float:
    """Calcula a distância geodésica Haversine (km) entre duas paradas."""
    coords_a = point_a.address.coordinates
    coords_b = point_b.address.coordinates
    if coords_a is None or coords_b is None:
        return 0.0
    return coords_a.distance_to(coords_b)


def stops_to_dataframe(
    origin: DeliveryStop,
    ordered_stops: list[DeliveryStop],
) -> pd.DataFrame:
    """Converte a sequência ordenada de entregas em um DataFrame enriquecido para análise.

    Args:
        origin: Parada de origem (Centro de Distribuição).
        ordered_stops: Lista de paradas na ordem de visitação.

    Returns:
        `pd.DataFrame` com métricas de trecho, distância acumulada e risco climático.
    """
    if not ordered_stops:
        return pd.DataFrame(columns=STOPS_COLUMNS)

    rows: list[dict[str, Any]] = []
    previous_stop = origin
    cumulative_km = 0.0

    for idx, stop in enumerate(ordered_stops, start=1):
        leg_km = round(_calculate_leg_distance_km(previous_stop, stop), 4)
        cumulative_km = round(cumulative_km + leg_km, 4)
        previous_stop = stop

        max_rain = (
            round(stop.weather_forecast.max_precipitation_mm(), 2)
            if stop.weather_forecast is not None
            else 0.0
        )
        max_wind = (
            round(stop.weather_forecast.max_wind_speed_kmh(), 2)
            if stop.weather_forecast is not None
            else 0.0
        )

        rows.append(
            {
                "Ordem": idx,
                "ID": stop.id,
                "Destinatario": stop.recipient_name,
                "CEP": stop.address.cep,
                "Bairro": stop.address.bairro,
                "Cidade": stop.address.cidade,
                "Peso_kg": round(stop.package_weight_kg, 2),
                "Prioridade": stop.priority.value,
                "Janela": stop.delivery_window,
                "Distancia_Trecho_km": leg_km,
                "Distancia_Acumulada_km": cumulative_km,
                "Score_Risco": round(stop.risk_score, 4),
                "Nivel_Risco": stop.risk_level.value,
                "Chuva_Max_mm": max_rain,
                "Vento_Max_kmh": max_wind,
            }
        )

    return pd.DataFrame(rows, columns=STOPS_COLUMNS)


def weather_to_dataframe(
    forecast: WeatherForecast,
    label: str = "Curitiba",
) -> pd.DataFrame:
    """Converte uma previsão meteorológica horária em um DataFrame com média móvel de chuva.

    Args:
        forecast: Objeto `WeatherForecast` contendo pontos horários.
        label: Rótulo da localidade ou parada associada à série.

    Returns:
        `pd.DataFrame` com variáveis horárias, risco classificado e média móvel de 3h.
    """
    if not forecast.hourly:
        return pd.DataFrame(columns=WEATHER_COLUMNS)

    rows: list[dict[str, Any]] = []
    for point in forecast.hourly:
        rows.append(
            {
                "DataHora": point.timestamp,
                "Hora": point.timestamp.strftime("%H:%M"),
                "Local": label,
                "Temperatura_C": round(point.temperature_c, 2),
                "Prob_Chuva_Pct": round(point.precipitation_probability, 2),
                "Precipitacao_mm": round(point.precipitation_mm, 2),
                "Vento_kmh": round(point.wind_speed_kmh, 2),
                "Nivel_Risco": point.classify_risk().value,
            }
        )

    df = pd.DataFrame(rows)
    df["Precipitacao_Media_Movel_3h"] = (
        df["Precipitacao_mm"].rolling(window=3, min_periods=1).mean().round(2)
    )
    return df[WEATHER_COLUMNS]


def export_route_csv(df: pd.DataFrame) -> bytes:
    """Exporta um DataFrame de roteirização para bytes em formato CSV (UTF-8 com BOM).

    Args:
        df: DataFrame de paradas ou clima a ser exportado.

    Returns:
        Conteúdo CSV codificado em `utf-8-sig` pronto para download no navegador/Excel.
    """
    csv_text: str = df.to_csv(index=False)
    return csv_text.encode("utf-8-sig")

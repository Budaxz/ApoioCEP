"""Matriz probabilística de risco climático e custo ponderado de arestas logísticas.

Este módulo implementa a modelagem matemática do Índice de Risco Logístico ($R_{i,t}$)
e a função de penalização de arestas no grafo de entregas sob incerteza meteorológica:

$$R_{i,t} = w_{\\text{rain}} \\cdot f_{\\text{rain}}(p_{i,t}) + w_{\\text{wind}} \\cdot f_{\\text{wind}}(v_{i,t}) + w_{\\text{prio}} \\cdot f_{\\text{prio}}(P_i)$$

$$C_{a,b} = d_{a,b} \\cdot (1 + \\alpha \\cdot R_b)$$
"""

from __future__ import annotations

import re

from src.domain.delivery import DeliveryPriority, DeliveryStop
from src.domain.weather import ClimateRiskLevel, HourlyWeatherPoint

_PRIORITY_FACTOR: dict[DeliveryPriority, float] = {
    DeliveryPriority.BAIXA: 0.2,
    DeliveryPriority.MEDIA: 0.5,
    DeliveryPriority.ALTA: 1.0,
}

_RISK_SEVERITY_ORDER: dict[ClimateRiskLevel, int] = {
    ClimateRiskLevel.BAIXO: 0,
    ClimateRiskLevel.MODERADO: 1,
    ClimateRiskLevel.ALTO: 2,
    ClimateRiskLevel.CRITICO: 3,
}


def parse_delivery_window_hours(window: str) -> tuple[int, int]:
    """Extrai a hora inicial e a hora final de uma janela de entrega textual.

    Suporta padrões como `"09:00 - 12:00"`, `"08:00-14:00"` ou `"9:00 às 17:00"`.
    Caso a string não possa ser interpretada ou produza horas fora do intervalo
    válido `[0, 23]`, retorna o fallback seguro `(9, 18)`.

    Args:
        window: String representando a janela de entrega.

    Returns:
        Tupla `(hora_inicial, hora_final)` em formato 24h (`0` a `23`).
    """
    match = re.search(r"(\d{1,2})(?::\d{2})?\s*(?:[-–—]|às|a)\s*(\d{1,2})(?::\d{2})?", window)
    if not match:
        return (9, 18)

    start_hour = int(match.group(1))
    end_hour = int(match.group(2))

    if 0 <= start_hour <= 23 and 0 <= end_hour <= 23 and start_hour <= end_hour:
        return (start_hour, end_hour)
    return (9, 18)


def _score_to_risk_level(score: float) -> ClimateRiskLevel:
    """Converte um score contínuo no intervalo `[0.0, 1.0]` em `ClimateRiskLevel`."""
    if score >= 0.75:
        return ClimateRiskLevel.CRITICO
    if score >= 0.50:
        return ClimateRiskLevel.ALTO
    if score >= 0.25:
        return ClimateRiskLevel.MODERADO
    return ClimateRiskLevel.BAIXO


def compute_stop_risk_score(
    stop: DeliveryStop,
    w_rain: float = 0.50,
    w_wind: float = 0.30,
    w_prio: float = 0.20,
) -> tuple[float, ClimateRiskLevel]:
    """Calcula o índice contínuo de risco climático e a classificação qualitativa da parada.

    Modelo matemático linear ponderado normalizado em $[0.0, 1.0]$:
        $$R_{i,t} = w_{\\text{rain}} \\cdot f_{\\text{rain}} + w_{\\text{wind}} \\cdot f_{\\text{wind}} + w_{\\text{prio}} \\cdot f_{\\text{prio}}$$

    Onde:
    - $f_{\\text{rain}} = \\min(1.0, \\max(\\text{precip\\_mm} / 15.0, (\\text{prob\\_pct} / 100.0) \\times 0.8))$
    - $f_{\\text{wind}} = \\min(1.0, \\text{max\\_wind\\_kmh} / 55.0)$
    - $f_{\\text{prio}} \\in \\{0.2, 0.5, 1.0\\}$ conforme a prioridade logística (`BAIXA`, `MEDIA`, `ALTA`).

    Args:
        stop: Parada de entrega contendo previsão meteorológica, janela e prioridade.
        w_rain: Peso atribuído ao fator de precipitação (padrão `0.50`).
        w_wind: Peso atribuído ao fator de vento (padrão `0.30`).
        w_prio: Peso atribuído ao fator de prioridade da entrega (padrão `0.20`).

    Returns:
        Tupla `(risk_score, risk_level)` com o score arredondado em 4 casas decimais.
    """
    f_rain = 0.0
    f_wind = 0.0
    worst_weather_level = ClimateRiskLevel.BAIXO

    if stop.weather_forecast is not None and stop.weather_forecast.hourly:
        start_hour, end_hour = parse_delivery_window_hours(stop.delivery_window)
        window_points: list[HourlyWeatherPoint] = [
            pt
            for pt in stop.weather_forecast.hourly
            if start_hour <= pt.timestamp.hour <= end_hour
        ]
        if not window_points:
            window_points = list(stop.weather_forecast.hourly)

        max_precip_mm = max(pt.precipitation_mm for pt in window_points)
        max_prob_pct = max(pt.precipitation_probability for pt in window_points)
        max_wind_kmh = max(pt.wind_speed_kmh for pt in window_points)

        f_rain = min(1.0, max(max_precip_mm / 15.0, (max_prob_pct / 100.0) * 0.8))
        f_wind = min(1.0, max_wind_kmh / 55.0)
        worst_weather_level = max(
            (pt.classify_risk() for pt in window_points),
            key=lambda level: _RISK_SEVERITY_ORDER[level],
        )

    f_prio = _PRIORITY_FACTOR.get(stop.priority, 0.5)
    raw_score = (w_rain * f_rain) + (w_wind * f_wind) + (w_prio * f_prio)
    clamped_score = round(max(0.0, min(1.0, raw_score)), 4)

    score_level = _score_to_risk_level(clamped_score)
    final_level = max(
        score_level,
        worst_weather_level,
        key=lambda level: _RISK_SEVERITY_ORDER[level],
    )

    return (clamped_score, final_level)


def evaluate_stops_risk(stops: list[DeliveryStop]) -> list[DeliveryStop]:
    """Avalia e atualiza imutavelmente o score e o nível de risco de uma lista de paradas.

    Args:
        stops: Lista de paradas de entrega a avaliar.

    Returns:
        Nova lista de instâncias `DeliveryStop` com `risk_score` e `risk_level` preenchidos.
    """
    evaluated: list[DeliveryStop] = []
    for stop in stops:
        score, level = compute_stop_risk_score(stop)
        evaluated.append(stop.model_copy(update={"risk_score": score, "risk_level": level}))
    return evaluated


def calculate_weighted_edge_cost(
    stop_a: DeliveryStop,
    stop_b: DeliveryStop,
    alpha: float = 0.5,
) -> float:
    """Calcula o custo ponderado da aresta direcionada $(a \\to b)$ considerando distância e risco.

    Fórmula matemática do custo da aresta:
        $$C_{a,b} = d_{a,b} \\cdot (1.0 + \\alpha \\cdot R_b)$$

    Onde $d_{a,b}$ é a distância geodésica de Haversine (em km) entre as coordenadas de
    `stop_a` e `stop_b`, $\\alpha \\ge 0$ é o coeficiente de aversão ao risco climático e
    $R_b \\in [0, 1]$ é o `risk_score` da parada de destino `stop_b`.

    Args:
        stop_a: Parada de origem da transição.
        stop_b: Parada de destino da transição.
        alpha: Coeficiente de penalização por risco climático (padrão `0.5`).

    Returns:
        Custo ponderado da aresta arredondado em 4 casas decimais (`0.0` se faltar coordenada).
    """
    coords_a = stop_a.address.coordinates
    coords_b = stop_b.address.coordinates
    if coords_a is None or coords_b is None:
        return 0.0

    distance_km = coords_a.distance_to(coords_b)
    weighted_cost = distance_km * (1.0 + alpha * stop_b.risk_score)
    return round(weighted_cost, 4)

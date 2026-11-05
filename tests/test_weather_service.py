"""Testes unitários para WeatherService utilizando httpx.MockTransport e CacheService em tmp_path."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.domain.address import Coordinates
from src.domain.weather import ClimateRiskLevel
from src.services.cache_service import CacheService
from src.services.weather_service import WeatherLookupError, WeatherService


def test_open_meteo_parsing_and_risk_integration(tmp_path: Path) -> None:
    """Deve consultar a API Open-Meteo, converter as séries horárias e calcular níveis de risco."""
    http_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        assert "api.open-meteo.com" in str(request.url)
        assert request.url.params["timezone"] == "America/Sao_Paulo"
        return httpx.Response(
            200,
            json={
                "latitude": -25.4284,
                "longitude": -49.2733,
                "hourly": {
                    "time": [
                        "2026-11-05T09:00",
                        "2026-11-05T10:00",
                        "2026-11-05T14:00",
                    ],
                    "temperature_2m": [19.5, 21.0, 24.2],
                    "precipitation_probability": [10.0, 45.0, 85.0],
                    "precipitation": [0.0, 1.5, 18.0],
                    "wind_speed_10m": [12.0, 22.5, 55.0],
                    "weather_code": [1, 61, 95],
                },
            },
        )

    cache = CacheService(db_path=tmp_path / "weather_cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = WeatherService(cache=cache, client=client)

    coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
    forecast = service.fetch_forecast(coords, days=1)

    assert http_calls == 1
    assert len(forecast.hourly) == 3

    p09 = forecast.get_point_for_hour(9)
    assert p09 is not None
    assert p09.temperature_c == pytest.approx(19.5)
    assert p09.classify_risk() == ClimateRiskLevel.BAIXO

    p10 = forecast.get_point_for_hour(10)
    assert p10 is not None
    assert p10.precipitation_mm == pytest.approx(1.5)
    assert p10.classify_risk() == ClimateRiskLevel.MODERADO

    p14 = forecast.get_point_for_hour(14)
    assert p14 is not None
    assert p14.precipitation_mm == pytest.approx(18.0)
    assert p14.wind_speed_kmh == pytest.approx(55.0)
    assert p14.weather_code == 95
    assert p14.classify_risk() == ClimateRiskLevel.CRITICO

    assert forecast.max_precipitation_mm() == pytest.approx(18.0)
    assert forecast.max_wind_speed_kmh() == pytest.approx(55.0)
    assert forecast.overall_risk_level() == ClimateRiskLevel.CRITICO


def test_weather_cache_prevents_second_http_request(tmp_path: Path) -> None:
    """Segunda chamada para coordenadas na mesma grade (.3f) deve reutilizar o cache sem HTTP."""
    http_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2026-11-05T12:00"],
                    "temperature_2m": [22.0],
                    "precipitation_probability": [5.0],
                    "precipitation": [0.0],
                    "wind_speed_10m": [8.0],
                    "weather_code": [0],
                }
            },
        )

    cache = CacheService(db_path=tmp_path / "weather_cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = WeatherService(cache=cache, client=client)

    coords_1 = Coordinates(latitude=-25.42841, longitude=-49.27331)
    coords_2 = Coordinates(latitude=-25.42849, longitude=-49.27334)

    first = service.fetch_forecast(coords_1, days=1)
    second = service.fetch_forecast(coords_2, days=1)

    assert http_calls == 1
    assert len(first.hourly) == 1
    assert len(second.hourly) == 1
    assert first.hourly[0].temperature_c == second.hourly[0].temperature_c


def test_weather_service_raises_error_on_http_failure(tmp_path: Path) -> None:
    """Deve levantar WeatherLookupError quando a API Open-Meteo retornar erro HTTP."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": True, "reason": "Service Unavailable"})

    cache = CacheService(db_path=tmp_path / "weather_cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = WeatherService(cache=cache, client=client)

    coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
    with pytest.raises(WeatherLookupError, match="status inesperado 503"):
        service.fetch_forecast(coords)


def test_weather_service_raises_error_on_malformed_payload(tmp_path: Path) -> None:
    """Deve levantar WeatherLookupError quando o bloco 'hourly' estiver ausente."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"latitude": -25.4284})

    cache = CacheService(db_path=tmp_path / "weather_cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = WeatherService(cache=cache, client=client)

    coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
    with pytest.raises(WeatherLookupError, match="hourly"):
        service.fetch_forecast(coords)

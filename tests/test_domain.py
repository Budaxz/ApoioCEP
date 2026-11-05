"""Testes unitários para a camada de domínio (src/domain/)."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.domain import (
    Address,
    ClimateRiskLevel,
    Coordinates,
    DeliveryPriority,
    DeliveryStop,
    HourlyWeatherPoint,
    RoutePlan,
    WeatherForecast,
)


class TestCoordinates:
    """Testes para validação de coordenadas e cálculo geodésico de Haversine."""

    def test_valid_coordinates(self) -> None:
        coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
        assert coords.latitude == -25.4284
        assert coords.longitude == -49.2733

    @pytest.mark.parametrize(
        ("lat", "lon"),
        [
            (-91.0, 0.0),
            (90.5, 0.0),
            (0.0, -181.0),
            (0.0, 180.1),
        ],
    )
    def test_invalid_coordinates_bounds(self, lat: float, lon: float) -> None:
        with pytest.raises(ValidationError):
            Coordinates(latitude=lat, longitude=lon)

    def test_haversine_zero_distance(self) -> None:
        p1 = Coordinates(latitude=-25.4284, longitude=-49.2733)
        assert p1.distance_to(p1) == 0.0

    def test_haversine_curitiba_landmarks_distance(self) -> None:
        # Praça Tiradentes (Marco Zero de Curitiba) -> Jardim Botânico de Curitiba
        praca_tiradentes = Coordinates(latitude=-25.4284, longitude=-49.2733)
        jardim_botanico = Coordinates(latitude=-25.4429, longitude=-49.2385)

        dist = praca_tiradentes.distance_to(jardim_botanico)
        # Distância em linha reta aproximada ~3.85 km
        assert 3.5 <= dist <= 4.2
        assert dist == jardim_botanico.distance_to(praca_tiradentes)


class TestAddress:
    """Testes para validação e formatação de CEP e criação de Address."""

    @pytest.mark.parametrize(
        ("raw_cep", "expected_formatted", "expected_clean"),
        [
            ("80020010", "80020-010", "80020010"),
            ("80020-010", "80020-010", "80020010"),
            ("80.020-010", "80020-010", "80020010"),
            ("  80020 010 ", "80020-010", "80020010"),
        ],
    )
    def test_valid_cep_formatting_and_clean_cep(
        self, raw_cep: str, expected_formatted: str, expected_clean: str
    ) -> None:
        addr = Address(
            cep=raw_cep,
            logradouro="Praça Tiradentes",
            bairro="Centro",
            cidade="Curitiba",
            uf="pr",
        )
        assert addr.cep == expected_formatted
        assert addr.clean_cep == expected_clean
        assert addr.uf == "PR"
        assert addr.provider == "brasilapi"
        assert addr.coordinates is None

    @pytest.mark.parametrize(
        "invalid_cep",
        [
            "1234567",
            "123456789",
            "abcdefgh",
            "",
            "80020-01a",
        ],
    )
    def test_invalid_cep_raises_validation_error(self, invalid_cep: str) -> None:
        with pytest.raises(ValidationError):
            Address(
                cep=invalid_cep,
                logradouro="Rua XV de Novembro",
                bairro="Centro",
                cidade="Curitiba",
                uf="PR",
            )


class TestWeatherDomain:
    """Testes para classificação de risco climático e agregadores de WeatherForecast."""

    def test_hourly_weather_point_risk_classification(self) -> None:
        now = datetime(2026, 5, 10, 14, 0)

        low = HourlyWeatherPoint(
            timestamp=now,
            temperature_c=22.0,
            precipitation_probability=15.0,
            precipitation_mm=0.2,
            wind_speed_kmh=10.0,
        )
        assert low.classify_risk() == ClimateRiskLevel.BAIXO

        moderate_by_prob = HourlyWeatherPoint(
            timestamp=now,
            temperature_c=20.0,
            precipitation_probability=45.0,
            precipitation_mm=0.0,
            wind_speed_kmh=12.0,
        )
        assert moderate_by_prob.classify_risk() == ClimateRiskLevel.MODERADO

        high_by_rain = HourlyWeatherPoint(
            timestamp=now,
            temperature_c=18.0,
            precipitation_probability=60.0,
            precipitation_mm=6.5,
            wind_speed_kmh=20.0,
        )
        assert high_by_rain.classify_risk() == ClimateRiskLevel.ALTO

        critical_by_wind = HourlyWeatherPoint(
            timestamp=now,
            temperature_c=16.0,
            precipitation_probability=80.0,
            precipitation_mm=2.0,
            wind_speed_kmh=55.0,
        )
        assert critical_by_wind.classify_risk() == ClimateRiskLevel.CRITICO

        critical_by_rain = HourlyWeatherPoint(
            timestamp=now,
            temperature_c=16.0,
            precipitation_probability=90.0,
            precipitation_mm=18.0,
            wind_speed_kmh=15.0,
        )
        assert critical_by_rain.classify_risk() == ClimateRiskLevel.CRITICO

    def test_weather_forecast_aggregators(self) -> None:
        coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
        p1 = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 9, 0),
            temperature_c=19.0,
            precipitation_probability=20.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
        )
        p2 = HourlyWeatherPoint(
            timestamp=datetime(2026, 5, 10, 14, 0),
            temperature_c=24.0,
            precipitation_probability=80.0,
            precipitation_mm=7.2,
            wind_speed_kmh=38.0,
        )
        forecast = WeatherForecast(coordinates=coords, hourly=[p1, p2])

        assert forecast.get_point_for_hour(14) == p2
        assert forecast.get_point_for_hour(22) is None
        assert forecast.max_precipitation_mm() == 7.2
        assert forecast.max_wind_speed_kmh() == 38.0
        assert forecast.overall_risk_level() == ClimateRiskLevel.ALTO

    def test_empty_weather_forecast_defaults(self) -> None:
        coords = Coordinates(latitude=-25.4284, longitude=-49.2733)
        empty_forecast = WeatherForecast(coordinates=coords)

        assert empty_forecast.max_precipitation_mm() == 0.0
        assert empty_forecast.max_wind_speed_kmh() == 0.0
        assert empty_forecast.overall_risk_level() == ClimateRiskLevel.BAIXO
        assert empty_forecast.get_point_for_hour(10) is None


class TestDeliveryAndRoutePlan:
    """Testes para criação de paradas de entrega (DeliveryStop) e plano de rota (RoutePlan)."""

    def test_delivery_stop_and_route_plan_creation(self) -> None:
        origin_address = Address(
            cep="80020-010",
            logradouro="Praça Tiradentes",
            bairro="Centro",
            cidade="Curitiba",
            uf="PR",
            coordinates=Coordinates(latitude=-25.4284, longitude=-49.2733),
        )
        dest_address = Address(
            cep="80210-390",
            logradouro="Av. Prefeito Lothário Meissner",
            bairro="Jardim Botânico",
            cidade="Curitiba",
            uf="PR",
            coordinates=Coordinates(latitude=-25.4429, longitude=-49.2385),
        )

        origin_stop = DeliveryStop(
            id="ORIGEM",
            recipient_name="CD Central Curitiba",
            address=origin_address,
        )
        delivery_stop = DeliveryStop(
            id="STOP-01",
            recipient_name="Cliente Jardim Botânico",
            address=dest_address,
            package_weight_kg=3.5,
            priority=DeliveryPriority.ALTA,
            risk_score=0.45,
            risk_level=ClimateRiskLevel.MODERADO,
        )

        plan = RoutePlan(
            origin=origin_stop,
            ordered_stops=[delivery_stop],
            total_distance_km=3.85,
            average_risk_score=0.45,
            total_permutations_possible=1,
            computation_time_ms=1.25,
        )

        assert plan.origin.id == "ORIGEM"
        assert len(plan.ordered_stops) == 1
        assert plan.ordered_stops[0].priority == DeliveryPriority.ALTA
        assert plan.total_distance_km == 3.85
        assert plan.algorithm_used == "nearest_neighbor_2opt"

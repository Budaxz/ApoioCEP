"""Modelos de domínio para previsão meteorológica e classificação de risco climático."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.domain.address import Coordinates


class ClimateRiskLevel(str, Enum):
    """Níveis de risco climático para operação logística de entregas."""

    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


_RISK_SEVERITY_ORDER: dict[ClimateRiskLevel, int] = {
    ClimateRiskLevel.BAIXO: 0,
    ClimateRiskLevel.MODERADO: 1,
    ClimateRiskLevel.ALTO: 2,
    ClimateRiskLevel.CRITICO: 3,
}


class HourlyWeatherPoint(BaseModel):
    """Ponto horário de previsão meteorológica com variáveis de temperatura, chuva e vento."""

    timestamp: datetime = Field(..., description="Data e hora da leitura/previsão")
    temperature_c: float = Field(..., description="Temperatura do ar em graus Celsius (°C)")
    precipitation_probability: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Probabilidade de precipitação (%)"
    )
    precipitation_mm: float = Field(
        default=0.0, ge=0.0, description="Volume de precipitação acumulada na hora (mm)"
    )
    wind_speed_kmh: float = Field(
        default=0.0, ge=0.0, description="Velocidade do vento a 10m de altura (km/h)"
    )
    weather_code: int = Field(default=0, description="Código WMO de condição meteorológica")

    def classify_risk(self) -> ClimateRiskLevel:
        """Classifica o nível de risco climático do ponto horário para entregas.

        Regras de corte:
        - CRITICO: precipitação >= 15.0 mm ou vento >= 50.0 km/h
        - ALTO: precipitação >= 5.0 mm ou probabilidade >= 75.0% ou vento >= 35.0 km/h
        - MODERADO: precipitação >= 1.0 mm ou probabilidade >= 40.0% ou vento >= 20.0 km/h
        - BAIXO: caso contrário
        """
        if self.precipitation_mm >= 15.0 or self.wind_speed_kmh >= 50.0:
            return ClimateRiskLevel.CRITICO
        if (
            self.precipitation_mm >= 5.0
            or self.precipitation_probability >= 75.0
            or self.wind_speed_kmh >= 35.0
        ):
            return ClimateRiskLevel.ALTO
        if (
            self.precipitation_mm >= 1.0
            or self.precipitation_probability >= 40.0
            or self.wind_speed_kmh >= 20.0
        ):
            return ClimateRiskLevel.MODERADO
        return ClimateRiskLevel.BAIXO


class WeatherForecast(BaseModel):
    """Previsão meteorológica horária agregada para uma coordenada geográfica."""

    coordinates: Coordinates = Field(..., description="Coordenadas da consulta meteorológica")
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="Instante em que a previsão foi obtida"
    )
    hourly: list[HourlyWeatherPoint] = Field(
        default_factory=list, description="Série temporal de pontos meteorológicos horários"
    )

    def get_point_for_hour(self, target_hour: int) -> HourlyWeatherPoint | None:
        """Retorna o primeiro ponto horário cujo `timestamp.hour` corresponde a `target_hour`."""
        for point in self.hourly:
            if point.timestamp.hour == target_hour:
                return point
        return None

    def max_precipitation_mm(self) -> float:
        """Retorna a maior precipitação horária (mm) prevista na série (0.0 se vazia)."""
        if not self.hourly:
            return 0.0
        return max(point.precipitation_mm for point in self.hourly)

    def max_wind_speed_kmh(self) -> float:
        """Retorna a maior velocidade de vento (km/h) prevista na série (0.0 se vazia)."""
        if not self.hourly:
            return 0.0
        return max(point.wind_speed_kmh for point in self.hourly)

    def overall_risk_level(self) -> ClimateRiskLevel:
        """Retorna o maior nível de risco climático observado nos pontos horários."""
        if not self.hourly:
            return ClimateRiskLevel.BAIXO
        return max(
            (point.classify_risk() for point in self.hourly),
            key=lambda level: _RISK_SEVERITY_ORDER[level],
        )

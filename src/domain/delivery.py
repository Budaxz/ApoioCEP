"""Modelos de domínio para paradas de entrega e planos de roteirização logística."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.domain.address import Address
from src.domain.weather import ClimateRiskLevel, WeatherForecast


class DeliveryPriority(str, Enum):
    """Níveis de prioridade de uma parada de entrega."""

    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class DeliveryStop(BaseModel):
    """Representa uma parada individual de entrega com endereço, janela e risco climático."""

    id: str = Field(..., description="Identificador único da parada de entrega")
    recipient_name: str = Field(..., description="Nome do destinatário ou cliente")
    address: Address = Field(..., description="Endereço validado da entrega")
    package_weight_kg: float = Field(
        default=1.0, gt=0.0, description="Peso total da encomenda em quilogramas (kg)"
    )
    priority: DeliveryPriority = Field(
        default=DeliveryPriority.MEDIA, description="Prioridade logística da entrega"
    )
    delivery_window: str = Field(
        default="09:00 - 18:00", description="Janela de horário prevista para entrega"
    )
    weather_forecast: WeatherForecast | None = Field(
        default=None, description="Previsão meteorológica associada à coordenada da entrega"
    )
    risk_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Índice contínuo de risco climático (0.0 a 1.0)"
    )
    risk_level: ClimateRiskLevel = Field(
        default=ClimateRiskLevel.BAIXO, description="Classificação qualitativa de risco climático"
    )


class RoutePlan(BaseModel):
    """Plano de rota otimizada contendo sequência de paradas e métricas de otimização."""

    origin: DeliveryStop = Field(..., description="Ponto de partida (centro de distribuição/origem)")
    ordered_stops: list[DeliveryStop] = Field(
        default_factory=list, description="Sequência ordenada de paradas de entrega"
    )
    total_distance_km: float = Field(
        default=0.0, ge=0.0, description="Distância geodésica total percorrida na rota (km)"
    )
    average_risk_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Risco climático médio das paradas da rota"
    )
    algorithm_used: str = Field(
        default="nearest_neighbor_2opt", description="Algoritmo utilizado na otimização da rota"
    )
    total_permutations_possible: int = Field(
        default=1, ge=1, description="Número total de permutações possíveis (n!) no espaço de busca"
    )
    computation_time_ms: float = Field(
        default=0.0, ge=0.0, description="Tempo de execução do cálculo da rota em milissegundos"
    )

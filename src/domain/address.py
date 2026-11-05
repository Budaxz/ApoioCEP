"""Modelos de domínio para endereços, CEPs e coordenadas geográficas."""

from __future__ import annotations

import math
import re

from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    """Representa um par de coordenadas geográficas (latitude e longitude) em graus decimais."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude em graus decimais (-90 a 90)")
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitude em graus decimais (-180 a 180)"
    )

    def distance_to(self, other: Coordinates) -> float:
        """Calcula a distância geodésica entre duas coordenadas usando a Fórmula de Haversine.

        A Fórmula de Haversine determina a distância do grande círculo entre dois pontos
        em uma esfera dadas suas longitudes e latitudes:

            Δφ = rad(lat2 - lat1)
            Δλ = rad(lon2 - lon1)
            a = sin²(Δφ / 2) + cos(φ1) ⋅ cos(φ2) ⋅ sin²(Δλ / 2)
            c = 2 ⋅ atan2(√a, √(1 - a))
            d = R ⋅ c

        Onde R = 6371.0 km é o raio médio da Terra.

        Args:
            other: Coordenada de destino para cálculo da distância.

        Returns:
            Distância em quilômetros arredondada em 4 casas decimais.
        """
        earth_radius_km = 6371.0

        phi1 = math.radians(self.latitude)
        phi2 = math.radians(other.latitude)
        delta_phi = math.radians(other.latitude - self.latitude)
        delta_lambda = math.radians(other.longitude - self.longitude)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

        distance = earth_radius_km * c
        return round(distance, 4)


class Address(BaseModel):
    """Representa um endereço postal brasileiro validado a partir do CEP."""

    cep: str = Field(..., description="CEP formatado no padrão XXXXX-XXX")
    logradouro: str = Field(..., description="Logradouro (rua, avenida, praça, etc.)")
    bairro: str = Field(..., description="Bairro ou distrito")
    cidade: str = Field(..., description="Município / Cidade")
    uf: str = Field(..., min_length=2, max_length=2, description="Sigla da Unidade Federativa (UF)")
    coordinates: Coordinates | None = Field(
        default=None, description="Coordenadas geográficas associadas ao endereço"
    )
    provider: str = Field(default="brasilapi", description="Provedor de origem dos dados do CEP")

    @field_validator("cep", mode="before")
    @classmethod
    def validate_and_format_cep(cls, value: object) -> str:
        """Remove caracteres não numéricos, valida 8 dígitos exatos e formata como XXXXX-XXX."""
        if not isinstance(value, str):
            raise ValueError("O CEP deve ser informado como uma string.")
        digits = re.sub(r"\D", "", value)
        if len(digits) != 8:
            raise ValueError(f"CEP inválido '{value}': deve conter exatamente 8 dígitos numéricos.")
        return f"{digits[:5]}-{digits[5:]}"

    @field_validator("uf", mode="before")
    @classmethod
    def normalize_uf(cls, value: object) -> str:
        """Normaliza a sigla da UF para letras maiúsculas sem espaços extras."""
        if not isinstance(value, str):
            raise ValueError("A UF deve ser uma string de 2 caracteres.")
        return value.strip().upper()

    @property
    def clean_cep(self) -> str:
        """Retorna os 8 dígitos numéricos puros do CEP (sem hífen)."""
        return self.cep.replace("-", "")

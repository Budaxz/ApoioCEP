"""Serviço de previsão meteorológica integrado à API Open-Meteo com cache local."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from src.domain.address import Coordinates
from src.domain.weather import HourlyWeatherPoint, WeatherForecast
from src.services.cache_service import CacheService


class WeatherLookupError(Exception):
    """Exceção levantada quando ocorre falha na obtenção ou parsing dos dados meteorológicos."""


class WeatherService:
    """Serviço de consulta de previsão meteorológica horária via Open-Meteo.

    Extrai séries temporais de temperatura (°C), probabilidade de chuva (%),
    precipitação (mm), velocidade do vento (km/h) e código WMO.
    """

    def __init__(
        self,
        cache: CacheService | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Inicializa o serviço meteorológico com cache e cliente HTTP opcionais.

        Args:
            cache: Instância de `CacheService`. Se omitido, utiliza a instância padrão.
            client: Cliente `httpx.Client` customizado para injeção em testes.
        """
        self.cache = cache if cache is not None else CacheService()
        self._external_client = client

    def fetch_forecast(
        self,
        coordinates: Coordinates,
        days: int = 1,
    ) -> WeatherForecast:
        """Obtém a previsão meteorológica horária para um par de coordenadas.

        Args:
            coordinates: Coordenadas geográficas de destino.
            days: Quantidade de dias de previsão a consultar (padrão: 1).

        Returns:
            Instância de `WeatherForecast` com os pontos horários populados.

        Raises:
            WeatherLookupError: Se a API Open-Meteo falhar ou retornar payload inválido.
        """
        cache_key = f"{coordinates.latitude:.3f}:{coordinates.longitude:.3f}:{days}"
        cached = self.cache.get("weather", cache_key)
        if cached is not None:
            return WeatherForecast.model_validate(cached)

        params: dict[str, Any] = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "hourly": (
                "temperature_2m,precipitation_probability,precipitation,"
                "wind_speed_10m,weather_code"
            ),
            "timezone": "America/Sao_Paulo",
            "forecast_days": days,
        }

        try:
            response = self._request_get(settings.OPEN_METEO_BASE_URL, params=params)
        except Exception as exc:
            logger.error(f"Falha de conexão com Open-Meteo para ({cache_key}): {exc}")
            raise WeatherLookupError(
                f"Erro de comunicação ao consultar Open-Meteo: {exc}"
            ) from exc

        if response.status_code != 200:
            raise WeatherLookupError(
                f"Open-Meteo retornou status inesperado {response.status_code}."
            )

        try:
            data: dict[str, Any] = response.json()
            hourly_points = self._parse_hourly_data(data)
        except WeatherLookupError:
            raise
        except Exception as exc:
            raise WeatherLookupError(
                f"Falha ao processar payload da Open-Meteo: {exc}"
            ) from exc

        forecast = WeatherForecast(
            coordinates=coordinates,
            fetched_at=datetime.now(),
            hourly=hourly_points,
        )

        self.cache.set("weather", cache_key, forecast.model_dump(mode="json"))
        return forecast

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.05, max=1.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    def _request_get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Executa requisição HTTP GET com retry automático via tenacity."""
        if self._external_client is not None:
            return self._external_client.get(url, params=params)
        with httpx.Client(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            return client.get(url, params=params)

    @staticmethod
    def _parse_hourly_data(data: dict[str, Any]) -> list[HourlyWeatherPoint]:
        """Converte os arrays paralelos do bloco `hourly` em objetos `HourlyWeatherPoint`."""
        hourly = data.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherLookupError("Bloco 'hourly' ausente na resposta da Open-Meteo.")

        times = hourly.get("time")
        if not isinstance(times, list) or len(times) == 0:
            raise WeatherLookupError("Vetor 'hourly.time' ausente ou vazio na resposta.")

        temps = hourly.get("temperature_2m") or []
        probs = hourly.get("precipitation_probability") or []
        precips = hourly.get("precipitation") or []
        winds = hourly.get("wind_speed_10m") or []
        codes = hourly.get("weather_code") or []

        points: list[HourlyWeatherPoint] = []
        for idx, time_str in enumerate(times):
            temp_val = float(temps[idx]) if idx < len(temps) and temps[idx] is not None else 20.0
            prob_val = float(probs[idx]) if idx < len(probs) and probs[idx] is not None else 0.0
            precip_val = (
                float(precips[idx]) if idx < len(precips) and precips[idx] is not None else 0.0
            )
            wind_val = float(winds[idx]) if idx < len(winds) and winds[idx] is not None else 0.0
            code_val = int(codes[idx]) if idx < len(codes) and codes[idx] is not None else 0

            points.append(
                HourlyWeatherPoint(
                    timestamp=datetime.fromisoformat(str(time_str)),
                    temperature_c=temp_val,
                    precipitation_probability=prob_val,
                    precipitation_mm=precip_val,
                    wind_speed_kmh=wind_val,
                    weather_code=code_val,
                )
            )

        return points

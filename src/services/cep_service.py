"""Serviço de consulta de CEP com resiliência multi-provedor e geocodificação."""

from __future__ import annotations

import re
import unicodedata
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
from src.domain.address import Address, Coordinates
from src.services.cache_service import CacheService


class CEPLookupError(Exception):
    """Exceção levantada quando um CEP é inválido ou não pode ser encontrado nas APIs."""


DEFAULT_CURITIBA_COORDS = Coordinates(latitude=-25.4284, longitude=-49.2733)

CURITIBA_NEIGHBORHOOD_COORDS: dict[str, Coordinates] = {
    "centro": Coordinates(latitude=-25.4284, longitude=-49.2733),
    "centro civico": Coordinates(latitude=-25.4178, longitude=-49.2686),
    "batel": Coordinates(latitude=-25.4422, longitude=-49.2869),
    "jardim botanico": Coordinates(latitude=-25.4429, longitude=-49.2389),
    "portao": Coordinates(latitude=-25.4764, longitude=-49.2917),
    "agua verde": Coordinates(latitude=-25.4561, longitude=-49.2814),
    "bigorrilho": Coordinates(latitude=-25.4328, longitude=-49.3025),
    "cabral": Coordinates(latitude=-25.4058, longitude=-49.2528),
    "juveve": Coordinates(latitude=-25.4125, longitude=-49.2614),
    "merces": Coordinates(latitude=-25.4203, longitude=-49.2908),
    "reboucas": Coordinates(latitude=-25.4453, longitude=-49.2647),
    "cristo rei": Coordinates(latitude=-25.4367, longitude=-49.2478),
    "alto da xv": Coordinates(latitude=-25.4258, longitude=-49.2533),
    "bacacheri": Coordinates(latitude=-25.3944, longitude=-49.2328),
    "boqueirao": Coordinates(latitude=-25.5008, longitude=-49.2336),
    "cajuru": Coordinates(latitude=-25.4519, longitude=-49.2117),
    "santa felicidade": Coordinates(latitude=-25.4014, longitude=-49.3339),
    "pinheirinho": Coordinates(latitude=-25.5136, longitude=-49.2953),
    "sitio cercado": Coordinates(latitude=-25.5347, longitude=-49.2672),
    "cidade industrial": Coordinates(latitude=-25.5028, longitude=-49.3308),
    "cic": Coordinates(latitude=-25.5028, longitude=-49.3308),
    "ecoville": Coordinates(latitude=-25.4419, longitude=-49.3469),
}


def _normalize_text(text: str) -> str:
    """Remove acentuação e converte para minúsculas para busca em dicionários."""
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


class CEPService:
    """Serviço de busca de endereços e coordenadas a partir do CEP.

    Implementa estratégia resiliente:
    1. Cache SQLite local (TTL)
    2. BrasilAPI v2 (com coordenadas integradas)
    3. Fallback para ViaCEP
    4. Geocodificação complementar via Nominatim (OpenStreetMap)
    5. Fallback determinístico por bairro de Curitiba / coordenada central
    """

    USER_AGENT = "ApoioCEP/0.1.0 (UniCuritiba A3 Project)"

    def __init__(
        self,
        cache: CacheService | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Inicializa o serviço de CEP com cache e cliente HTTP injetáveis.

        Args:
            cache: Instância de `CacheService`. Se omitido, instancia o padrão.
            client: Cliente `httpx.Client` customizado (útil para testes com MockTransport).
        """
        self.cache = cache if cache is not None else CacheService()
        self._external_client = client

    def _get_client(self) -> httpx.Client:
        """Retorna o cliente injetado ou cria um novo com timeout configurado."""
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": self.USER_AGENT},
        )

    def fetch_address(self, cep: str) -> Address:
        """Consulta e retorna um `Address` completo com coordenadas a partir de um CEP.

        Args:
            cep: String contendo o CEP (com ou sem máscara).

        Returns:
            Instância validada de `Address` contendo coordenadas geográficas.

        Raises:
            CEPLookupError: Se o formato do CEP for inválido ou não existir nos provedores.
        """
        if not isinstance(cep, str):
            raise CEPLookupError("O CEP deve ser informado como uma string.")

        clean_cep = re.sub(r"\D", "", cep)
        if len(clean_cep) != 8:
            raise CEPLookupError(
                f"CEP inválido '{cep}': deve conter exatamente 8 dígitos numéricos."
            )

        cached = self.cache.get("cep", clean_cep)
        if cached is not None:
            return Address.model_validate(cached)

        address: Address | None = None
        try:
            address = self._fetch_from_brasilapi(clean_cep)
        except Exception as exc:
            logger.warning(f"BrasilAPI falhou para CEP {clean_cep}: {exc}. Acionando ViaCEP.")

        if address is None:
            address = self._fetch_from_viacep(clean_cep)

        if address.coordinates is None:
            coords = self._geocode_nominatim(address)
            if coords is None:
                coords = self._fallback_coordinates(address.bairro)
            address = address.model_copy(update={"coordinates": coords})

        self.cache.set("cep", clean_cep, address.model_dump(mode="json"))
        return address

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.05, max=1.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    def _request_get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Executa requisição HTTP GET com retry automático para erros de transporte."""
        if self._external_client is not None:
            return self._external_client.get(url, params=params, headers=headers)
        with self._get_client() as client:
            return client.get(url, params=params, headers=headers)

    def _fetch_from_brasilapi(self, clean_cep: str) -> Address:
        """Consulta o provedor primário BrasilAPI v2."""
        url = f"{settings.BRASIL_API_BASE_URL}/{clean_cep}"
        response = self._request_get(url)
        if response.status_code != 200:
            raise CEPLookupError(
                f"BrasilAPI retornou status {response.status_code} para o CEP {clean_cep}."
            )

        data: dict[str, Any] = response.json()
        coords = self._extract_brasilapi_coords(data)

        return Address(
            cep=clean_cep,
            logradouro=data.get("street") or "Logradouro não informado",
            bairro=data.get("neighborhood") or "Centro",
            cidade=data.get("city") or "Curitiba",
            uf=data.get("state") or "PR",
            coordinates=coords,
            provider="brasilapi",
        )

    @staticmethod
    def _extract_brasilapi_coords(data: dict[str, Any]) -> Coordinates | None:
        """Extrai e valida coordenadas da resposta da BrasilAPI v2, se presentes."""
        location = data.get("location")
        if not isinstance(location, dict):
            return None
        raw_coords = location.get("coordinates")
        if not isinstance(raw_coords, dict):
            return None

        lat = raw_coords.get("latitude")
        lon = raw_coords.get("longitude")
        if lat is None or lon is None or lat == "" or lon == "":
            return None

        try:
            return Coordinates(latitude=float(lat), longitude=float(lon))
        except (ValueError, TypeError):
            return None

    def _fetch_from_viacep(self, clean_cep: str) -> Address:
        """Consulta o provedor de fallback ViaCEP."""
        url = f"{settings.VIACEP_BASE_URL}/{clean_cep}/json/"
        try:
            response = self._request_get(url)
        except Exception as exc:
            raise CEPLookupError(
                f"Erro de comunicação ao consultar ViaCEP para {clean_cep}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise CEPLookupError(
                f"ViaCEP retornou status {response.status_code} para o CEP {clean_cep}."
            )

        data: dict[str, Any] = response.json()
        if "erro" in data and data["erro"]:
            raise CEPLookupError(f"CEP {clean_cep} não encontrado na base de dados.")

        return Address(
            cep=clean_cep,
            logradouro=data.get("logradouro") or "Logradouro não informado",
            bairro=data.get("bairro") or "Centro",
            cidade=data.get("localidade") or "Curitiba",
            uf=data.get("uf") or "PR",
            coordinates=None,
            provider="viacep",
        )

    def _geocode_nominatim(self, address: Address) -> Coordinates | None:
        """Geocodifica um endereço textual utilizando a API Nominatim (OpenStreetMap)."""
        query = f"{address.logradouro}, {address.cidade}, {address.uf}, Brasil"
        headers = {"User-Agent": self.USER_AGENT}
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "limit": 1,
        }
        try:
            response = self._request_get(
                settings.NOMINATIM_BASE_URL,
                params=params,
                headers=headers,
            )
            if response.status_code != 200:
                return None

            results = response.json()
            if isinstance(results, list) and len(results) > 0:
                first = results[0]
                lat = first.get("lat")
                lon = first.get("lon")
                if lat is not None and lon is not None:
                    return Coordinates(latitude=float(lat), longitude=float(lon))
        except Exception as exc:
            logger.warning(f"Falha ao geocodificar via Nominatim ({query}): {exc}")

        return None

    @staticmethod
    def _fallback_coordinates(bairro: str) -> Coordinates:
        """Retorna coordenadas aproximadas por bairro de Curitiba ou centro padrão."""
        norm_bairro = _normalize_text(bairro)
        if norm_bairro in CURITIBA_NEIGHBORHOOD_COORDS:
            return CURITIBA_NEIGHBORHOOD_COORDS[norm_bairro]
        return DEFAULT_CURITIBA_COORDS

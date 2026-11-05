"""Testes unitários para CacheService e CEPService utilizando httpx.MockTransport."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.services.cache_service import CacheService
from src.services.cep_service import (
    DEFAULT_CURITIBA_COORDS,
    CEPLookupError,
    CEPService,
)


def test_brasilapi_success_with_coordinates(tmp_path: Path) -> None:
    """Deve retornar Address com coordenadas diretamente da BrasilAPI v2 quando disponível."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        assert "brasilapi.com.br" in str(request.url)
        return httpx.Response(
            200,
            json={
                "cep": "80020010",
                "state": "PR",
                "city": "Curitiba",
                "neighborhood": "Centro",
                "street": "Praça Tiradentes",
                "location": {
                    "type": "Point",
                    "coordinates": {
                        "longitude": "-49.2715",
                        "latitude": "-25.4290",
                    },
                },
            },
        )

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    address = service.fetch_address("80020-010")

    assert address.cep == "80020-010"
    assert address.logradouro == "Praça Tiradentes"
    assert address.bairro == "Centro"
    assert address.cidade == "Curitiba"
    assert address.uf == "PR"
    assert address.provider == "brasilapi"
    assert address.coordinates is not None
    assert address.coordinates.latitude == pytest.approx(-25.4290)
    assert address.coordinates.longitude == pytest.approx(-49.2715)
    assert call_count == 1


def test_fallback_to_viacep_and_nominatim_when_brasilapi_fails(tmp_path: Path) -> None:
    """Deve realizar fallback para ViaCEP e geocodificar via Nominatim se a BrasilAPI falhar."""
    called_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        called_urls.append(url_str)

        if "brasilapi.com.br" in url_str:
            return httpx.Response(500, json={"message": "Internal Error"})

        if "viacep.com.br" in url_str:
            return httpx.Response(
                200,
                json={
                    "cep": "80420-000",
                    "logradouro": "Avenida do Batel",
                    "bairro": "Batel",
                    "localidade": "Curitiba",
                    "uf": "PR",
                },
            )

        if "nominatim.openstreetmap.org" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "lat": "-25.4422",
                        "lon": "-49.2869",
                        "display_name": "Avenida do Batel, Curitiba, PR",
                    }
                ],
            )

        return httpx.Response(404)

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    address = service.fetch_address("80420000")

    assert address.cep == "80420-000"
    assert address.provider == "viacep"
    assert address.bairro == "Batel"
    assert address.coordinates is not None
    assert address.coordinates.latitude == pytest.approx(-25.4422)
    assert address.coordinates.longitude == pytest.approx(-49.2869)
    assert len(called_urls) == 3


def test_fallback_to_neighborhood_coords_when_nominatim_empty(tmp_path: Path) -> None:
    """Deve aplicar coordenada estática do bairro quando BrasilAPI não traz coords e Nominatim retorna vazio."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "brasilapi.com.br" in url_str:
            return httpx.Response(
                200,
                json={
                    "cep": "80210170",
                    "state": "PR",
                    "city": "Curitiba",
                    "neighborhood": "Jardim Botânico",
                    "street": "Rua Engenheiro Ostoja Roguski",
                    "location": {"type": "Point", "coordinates": {}},
                },
            )
        if "nominatim.openstreetmap.org" in url_str:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    address = service.fetch_address("80210-170")
    assert address.coordinates is not None
    assert address.coordinates.latitude == pytest.approx(-25.4429)
    assert address.coordinates.longitude == pytest.approx(-49.2389)


def test_fallback_to_default_curitiba_coords_for_unknown_neighborhood(tmp_path: Path) -> None:
    """Deve usar DEFAULT_CURITIBA_COORDS quando o bairro não consta no mapa estático e Nominatim falha."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "brasilapi.com.br" in url_str:
            return httpx.Response(
                200,
                json={
                    "cep": "80000000",
                    "state": "PR",
                    "city": "Curitiba",
                    "neighborhood": "Bairro Inexistente XYZ",
                    "street": "Rua Desconhecida",
                    "location": {},
                },
            )
        return httpx.Response(200, json=[])

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    address = service.fetch_address("80000-000")
    assert address.coordinates == DEFAULT_CURITIBA_COORDS


def test_cep_not_found_raises_cep_lookup_error(tmp_path: Path) -> None:
    """Deve levantar CEPLookupError quando o CEP não existe na BrasilAPI nem no ViaCEP."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "brasilapi.com.br" in url_str:
            return httpx.Response(404, json={"message": "CEP não encontrado"})
        if "viacep.com.br" in url_str:
            return httpx.Response(200, json={"erro": True})
        return httpx.Response(404)

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    with pytest.raises(CEPLookupError, match="não encontrado"):
        service.fetch_address("99999-999")


def test_invalid_cep_format_raises_cep_lookup_error(tmp_path: Path) -> None:
    """Deve levantar CEPLookupError para CEPs que não possuem 8 dígitos."""
    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    service = CEPService(cache=cache)

    with pytest.raises(CEPLookupError, match="8 dígitos"):
        service.fetch_address("12345")


def test_cep_cache_prevents_second_http_request(tmp_path: Path) -> None:
    """Segunda chamada para o mesmo CEP deve ser servida pelo cache SQLite sem nova requisição HTTP."""
    http_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(
            200,
            json={
                "cep": "80610010",
                "state": "PR",
                "city": "Curitiba",
                "neighborhood": "Portão",
                "street": "Avenida República Argentina",
                "location": {
                    "type": "Point",
                    "coordinates": {
                        "latitude": "-25.4764",
                        "longitude": "-49.2917",
                    },
                },
            },
        )

    cache = CacheService(db_path=tmp_path / "cache.sqlite3")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = CEPService(cache=cache, client=client)

    first = service.fetch_address("80610-010")
    second = service.fetch_address("80610010")

    assert http_calls == 1
    assert first == second

    cache.clear("cep")
    third = service.fetch_address("80610-010")
    assert http_calls == 2
    assert third == first

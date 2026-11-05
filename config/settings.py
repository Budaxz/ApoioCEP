"""Módulo de configuração central e governança do ApoioCEP."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações globais da aplicação com suporte a variáveis de ambiente."""

    APP_NAME: str = "ApoioCEP"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Timeout padrão para requisições externas (em segundos)
    HTTP_TIMEOUT_SECONDS: float = 8.0

    # URLs das APIs Públicas utilizadas
    BRASIL_API_BASE_URL: str = "https://brasilapi.com.br/api/cep/v2"
    VIACEP_BASE_URL: str = "https://viacep.com.br/ws"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org/search"

    # Parâmetros de cache
    CACHE_TTL_HOURS: int = 6

    class Config:
        env_prefix = "APOIOCEP_"
        case_sensitive = True


settings = Settings()

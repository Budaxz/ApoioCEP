"""Serviço de cache local persistente utilizando SQLite nativo com suporte a TTL."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import settings

DEFAULT_CACHE_PATH = Path(".cache_storage") / "apoiocep_cache.sqlite3"


class CacheService:
    """Gerenciador de cache chave-valor baseado em SQLite com expiração por TTL.

    Armazena respostas de APIs externas serializadas em JSON para reduzir latência
    e evitar chamadas redundantes dentro da janela configurada em `CACHE_TTL_HOURS`.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        ttl_hours: int | None = None,
    ) -> None:
        """Inicializa o banco SQLite de cache e garante a existência da tabela.

        Args:
            db_path: Caminho customizado do arquivo SQLite. Padrão: `.cache_storage/apoiocep_cache.sqlite3`.
            ttl_hours: Tempo de vida dos registros em horas. Padrão: `settings.CACHE_TTL_HOURS`.
        """
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_CACHE_PATH
        self.ttl_hours = ttl_hours if ttl_hours is not None else settings.CACHE_TTL_HOURS
        self._init_db()

    def _init_db(self) -> None:
        """Cria o diretório e a tabela de cache caso ainda não existam."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            conn.commit()

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Recupera um registro do cache se existir e não estiver expirado.

        Args:
            namespace: Categoria lógica do cache (ex.: 'cep', 'weather').
            key: Chave única identificadora do recurso.

        Returns:
            Dicionário deserializado do payload ou `None` se inexistente/expirado.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT payload, created_at
                    FROM api_cache
                    WHERE namespace = ? AND cache_key = ?
                    """,
                    (namespace, key),
                )
                row = cursor.fetchone()

                if row is None:
                    return None

                payload_raw, created_at_raw = row
                created_at = datetime.fromisoformat(created_at_raw)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                now_utc = datetime.now(timezone.utc)
                if now_utc - created_at > timedelta(hours=self.ttl_hours):
                    logger.debug(f"Cache expirado para [{namespace}:{key}]. Removendo registro.")
                    conn.execute(
                        "DELETE FROM api_cache WHERE namespace = ? AND cache_key = ?",
                        (namespace, key),
                    )
                    conn.commit()
                    return None

                data: dict[str, Any] = json.loads(payload_raw)
                logger.debug(f"Cache HIT para [{namespace}:{key}].")
                return data
        except (sqlite3.Error, json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Falha ao ler cache [{namespace}:{key}]: {exc}")
            return None

    def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Armazena ou atualiza um registro no cache com timestamp UTC atual.

        Args:
            namespace: Categoria lógica do cache.
            key: Chave única identificadora do recurso.
            value: Dicionário serializável em JSON a ser persistido.
        """
        try:
            payload_json = json.dumps(value, ensure_ascii=False)
            now_iso = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO api_cache (namespace, cache_key, payload, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(namespace, cache_key) DO UPDATE SET
                        payload = excluded.payload,
                        created_at = excluded.created_at
                    """,
                    (namespace, key, payload_json, now_iso),
                )
                conn.commit()
            logger.debug(f"Cache SET para [{namespace}:{key}].")
        except (sqlite3.Error, TypeError) as exc:
            logger.warning(f"Falha ao gravar cache [{namespace}:{key}]: {exc}")

    def clear(self, namespace: str | None = None) -> None:
        """Limpa os registros do cache.

        Args:
            namespace: Se informado, limpa apenas o namespace especificado;
                caso contrário, remove todos os registros da tabela.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if namespace is not None:
                    conn.execute("DELETE FROM api_cache WHERE namespace = ?", (namespace,))
                    logger.info(f"Cache limpo para o namespace '{namespace}'.")
                else:
                    conn.execute("DELETE FROM api_cache")
                    logger.info("Todo o cache local foi limpo.")
                conn.commit()
        except sqlite3.Error as exc:
            logger.warning(f"Erro ao limpar cache: {exc}")

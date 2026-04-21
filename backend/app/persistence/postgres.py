from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import Settings, get_settings


class PostgresConfig(BaseModel):
    """Minimal PostgreSQL connection settings for CareBridge persistence scaffolding."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    dsn: str = Field(description="PostgreSQL DSN used by the backend.")
    connect_timeout_seconds: int = Field(
        default=5,
        description="Connection timeout for PostgreSQL connectivity checks and sessions.",
    )
    application_name: str = Field(
        default="carebridge-backend",
        description="Application name sent to PostgreSQL for observability.",
    )
    autocommit: bool = Field(
        default=False,
        description="Whether scaffolded connections should autocommit statements.",
    )

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "PostgresConfig":
        resolved_settings = settings or get_settings()
        return cls(dsn=resolved_settings.postgres_dsn)


class PostgresConnectionFactory:
    """Thin psycopg connection factory with context-managed lifecycle handling."""

    def __init__(
        self,
        config: PostgresConfig | None = None,
        connector: Callable[..., Connection[Any]] = psycopg.connect,
    ) -> None:
        self.config = config or PostgresConfig.from_settings()
        self.connector = connector

    def create_connection(self) -> Connection[Any]:
        if not self.config.dsn.strip():
            raise ValueError("PostgreSQL DSN must not be empty.")

        return self.connector(
            self.config.dsn,
            connect_timeout=self.config.connect_timeout_seconds,
            application_name=self.config.application_name,
            autocommit=self.config.autocommit,
            row_factory=dict_row,
        )

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        connection = self.create_connection()
        try:
            yield connection
        finally:
            connection.close()

    def healthcheck(self) -> bool:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 AS ok")
                row = cursor.fetchone()
        return bool(row and row.get("ok") == 1)


PostgresSessionFactory = PostgresConnectionFactory

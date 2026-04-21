from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from psycopg.types.json import Json
from pydantic import BaseModel, ConfigDict

from app.persistence.postgres import PostgresConnectionFactory


def utc_now() -> datetime:
    return datetime.now(UTC)


class RepositoryRecord(BaseModel):
    """Base record contract used by persistence scaffolding repositories."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BasePostgresRepository:
    """Shared helper for simple insert/select repository patterns."""

    table_name: str = ""

    def __init__(self, connection_factory: PostgresConnectionFactory | None = None) -> None:
        self.connection_factory = connection_factory or PostgresConnectionFactory()

    def _adapt_value(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return Json(value.model_dump(mode="json"))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (dict, list)):
            return Json(value)
        return value

    def _insert(self, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join(f"%({column})s" for column in values)
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        params = {column: self._adapt_value(value) for column, value in values.items()}

        with self.connection_factory.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
            connection.commit()

    def _select_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        query = f"SELECT * FROM {self.table_name} WHERE trace_id = %(trace_id)s ORDER BY created_at ASC"
        with self.connection_factory.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, {"trace_id": trace_id})
                rows = cursor.fetchall() or []
        return [dict(row) for row in rows]

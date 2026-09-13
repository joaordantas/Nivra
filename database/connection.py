import os
import re
import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, CursorResult, Engine
from sqlalchemy.pool import NullPool


_engine: Engine | None = None
_engine_url: str | None = None
_engine_lock = threading.Lock()
_iso_date = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_lockable_rows = {
    ("usuarios", "id"),
    ("faturas", "id"),
    ("conexoes_bancarias", "id"),
    ("contas_bancarias_externas", "id"),
}


def _normalizar_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def get_database_url(*, migration: bool = False) -> str:
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    if app_env == "test":
        test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
        if not test_url:
            raise RuntimeError("TEST_DATABASE_URL e obrigatoria quando APP_ENV=test.")
        production_url = os.environ.get("DATABASE_URL", "").strip()
        if production_url and _normalizar_url(test_url) == _normalizar_url(production_url):
            raise RuntimeError("TEST_DATABASE_URL nao pode apontar para DATABASE_URL.")
        return _normalizar_url(test_url)

    variable = "DATABASE_URL_UNPOOLED" if migration and os.environ.get("DATABASE_URL_UNPOOLED") else "DATABASE_URL"
    database_url = os.environ.get(variable, "").strip()
    if not database_url:
        raise RuntimeError(
            f"{variable} nao configurada. Defina a conexao PostgreSQL antes de iniciar o backend."
        )
    normalized = _normalizar_url(database_url)
    if not normalized.startswith("postgresql+psycopg://"):
        raise RuntimeError("O banco oficial deve usar uma URL PostgreSQL.")
    return normalized


def _criar_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        sqlite3.register_adapter(date, lambda value: value.isoformat())
        sqlite3.register_adapter(datetime, lambda value: value.isoformat())
        return create_engine(
            url,
            future=True,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=2,
        pool_timeout=10,
        connect_args={"connect_timeout": 10},
    )


def get_engine(*, migration: bool = False) -> Engine:
    global _engine, _engine_url
    url = get_database_url(migration=migration)
    with _engine_lock:
        if _engine is None or _engine_url != url:
            if _engine is not None:
                _engine.dispose()
            _engine = _criar_engine(url)
            _engine_url = url
        return _engine


def dispose_engine() -> None:
    global _engine, _engine_url
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _engine_url = None


def _adaptar_parametro(value: Any) -> Any:
    if isinstance(value, str) and _iso_date.fullmatch(value):
        return date.fromisoformat(value)
    return value


def _normalizar_valor(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _normalizar_linha(row: Any) -> tuple | None:
    if row is None:
        return None
    return tuple(_normalizar_valor(value) for value in row)


def _parametrizar(sql: str, parametros: Iterable[Any] | None) -> tuple[str, dict[str, Any]]:
    values = tuple(parametros or ())
    if not values:
        return sql, {}
    partes = sql.split("?")
    if len(partes) - 1 != len(values):
        raise ValueError("Quantidade de parametros SQL nao corresponde aos placeholders.")
    rebuilt = partes[0]
    binds: dict[str, Any] = {}
    for index, value in enumerate(values):
        nome = f"p{index}"
        rebuilt += f":{nome}{partes[index + 1]}"
        binds[nome] = _adaptar_parametro(value)
    return rebuilt, binds


class DatabaseResult:
    def __init__(self, result: CursorResult[Any]):
        self._result = result

    @property
    def rowcount(self) -> int:
        return int(self._result.rowcount or 0)

    def fetchone(self) -> tuple | None:
        try:
            return _normalizar_linha(self._result.fetchone())
        finally:
            self._result.close()

    def fetchall(self) -> list[tuple]:
        try:
            return [_normalizar_linha(row) for row in self._result.fetchall() if row is not None]
        finally:
            self._result.close()


class DatabaseConnection:
    def __init__(self, connection: Connection):
        self._connection = connection

    @property
    def dialect_name(self) -> str:
        return self._connection.dialect.name

    def cursor(self) -> "DatabaseConnection":
        return self

    def execute(
        self, sql: str, parametros: Iterable[Any] | None = None
    ) -> DatabaseResult:
        statement, binds = _parametrizar(sql, parametros)
        return DatabaseResult(self._connection.execute(text(statement), binds))

    def lock_row(self, table: str, column: str, value: int) -> tuple | None:
        if (table, column) not in _lockable_rows:
            raise ValueError("Lock solicitado para uma tabela nao permitida.")
        suffix = " FOR UPDATE" if self.dialect_name == "postgresql" else ""
        return self.execute(
            f"SELECT {column} FROM {table} WHERE {column} = ?{suffix}", (value,)
        ).fetchone()

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_connection() -> DatabaseConnection:
    return DatabaseConnection(get_engine().connect())


def check_database_connection() -> bool:
    with get_engine().connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1

"""Fail-closed preflight for the disposable P6.5 PostgreSQL integration gate.

This module never writes to a database. It must run before importing the app or
Alembic, since those modules can open connections using environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]


def _url_parts(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not url.host or not url.database:
        raise RuntimeError("O gate requer uma URL PostgreSQL completa.")
    return url.host.lower().removeprefix("pooler.").replace("-pooler.", "."), url.database.lower()


def test_url_from_env() -> str:
    local = dotenv_values(ROOT / ".env")
    raw = os.environ.get("P65_TEST_DATABASE_URL") or local.get("P65_TEST_DATABASE_URL")
    if not raw:
        raise RuntimeError("P65_TEST_DATABASE_URL não configurada; nenhuma escrita foi feita.")
    if os.environ.get("APP_ENV", "").lower() == "production":
        raise RuntimeError("APP_ENV=production impede o gate.")
    test_host, test_db = _url_parts(raw)
    if not any(label in test_db for label in ("test", "gate", "p65", "lumi")):
        raise RuntimeError("O nome do banco descartável deve conter test, gate, p65 ou lumi.")
    production_urls = [
        value for name in ("DATABASE_URL", "DATABASE_URL_UNPOOLED")
        for value in (os.environ.get(name), local.get(name)) if value
    ]
    if not any(production_urls):
        raise RuntimeError("Referência DATABASE_URL de produção ausente; comparação segura impossível.")
    for production in filter(None, production_urls):
        production_host, _ = _url_parts(production)
        if test_host == production_host:
            raise RuntimeError("O gate exige um endpoint PostgreSQL diferente do banco principal.")
    return raw


def preflight_empty_database(raw: str) -> tuple[str, str]:
    """Read-only check, before allowing Alembic or test fixtures to mutate."""
    host, database = _url_parts(raw)
    url = make_url(raw).set(drivername="postgresql+psycopg")
    engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                raise RuntimeError("O gate requer PostgreSQL real.")
            tables = connection.execute(text(
                "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
            )).scalar_one()
            if tables:
                raise RuntimeError("O banco de teste não está vazio; nenhuma migration foi executada.")
    finally:
        engine.dispose()
    return host, database


def prepare_test_environment(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = raw
    os.environ["LUMI_PUBLIC_ENABLED"] = "true"
    os.environ["LUMI_ACTION_PROPOSALS_ENABLED"] = "true"
    os.environ["LUMI_ACTION_EXECUTION_ENABLED"] = "true"
    # Migration mode must not accidentally select the ordinary production URL.
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

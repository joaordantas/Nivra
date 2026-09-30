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
DEFAULT_P69_DATABASE = "nivra_lumi_p69_gate"


def _url_parts(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not url.host or not url.database:
        raise RuntimeError("O gate requer uma URL PostgreSQL completa.")
    return url.host.lower().removeprefix("pooler.").replace("-pooler.", "."), url.database.lower()


def test_url_from_env() -> str:
    local = dotenv_values(ROOT / ".env")
    preview_reference = (
        os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL")
        or local.get("P65_PREVIEW_BRANCH_DATABASE_URL")
    )
    p69_raw = os.environ.get("P69_TEST_DATABASE_URL") or local.get("P69_TEST_DATABASE_URL")
    if not p69_raw and preview_reference:
        database = os.environ.get("P69_TEST_DATABASE_NAME", DEFAULT_P69_DATABASE).strip().lower()
        p69_raw = make_url(preview_reference).set(
            drivername="postgresql+pg8000",
            database=database,
            query={},
        ).render_as_string(hide_password=False)
    raw = p69_raw or os.environ.get("P65_TEST_DATABASE_URL") or local.get("P65_TEST_DATABASE_URL")
    if not raw:
        raise RuntimeError("P69_TEST_DATABASE_URL/P65_TEST_DATABASE_URL não configurada; nenhuma escrita foi feita.")
    if os.environ.get("APP_ENV", "").lower() == "production":
        raise RuntimeError("APP_ENV=production impede o gate.")
    test_host, test_db = _url_parts(raw)
    production_urls = [
        value for name in ("DATABASE_URL", "DATABASE_URL_UNPOOLED")
        for value in (os.environ.get(name), local.get(name)) if value
    ]
    if p69_raw:
        preview_raw = preview_reference
        if not preview_raw:
            raise RuntimeError("A referência segura do branch Preview está ausente.")
        preview_host, preview_db = _url_parts(preview_raw)
        if test_host != preview_host or test_db == preview_db:
            raise RuntimeError("O gate P6.9 exige outro database no endpoint conhecido do branch Preview.")
        if not any(label in test_db for label in ("test", "gate", "p65", "p69", "lumi")):
            raise RuntimeError("O nome do banco descartável deve conter test, gate, p65, p69 ou lumi.")
        for production in filter(None, production_urls):
            if _url_parts(production) == (test_host, test_db):
                raise RuntimeError("O database descartável coincide com uma referência operacional.")
    else:
        if not any(label in test_db for label in ("test", "gate", "p65", "p69", "lumi")):
            raise RuntimeError("O nome do banco descartável deve conter test, gate, p65, p69 ou lumi.")
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
    parsed = make_url(raw)
    driver = "postgresql+pg8000" if parsed.drivername == "postgresql+pg8000" else "postgresql+psycopg"
    url = parsed.set(drivername=driver, query={} if driver == "postgresql+pg8000" else parsed.query)
    connect_args = (
        {"timeout": 10, "ssl_context": True}
        if driver == "postgresql+pg8000"
        else {"connect_timeout": 10}
    )
    engine = create_engine(url, poolclass=NullPool, connect_args=connect_args)
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
    os.environ["LUMI_ROLLOUT_MODE"] = "all"
    os.environ["LUMI_ACTION_PROPOSALS_ENABLED"] = "true"
    os.environ["LUMI_ACTION_EXECUTION_ENABLED"] = "true"
    # Migration mode must not accidentally select the ordinary production URL.
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

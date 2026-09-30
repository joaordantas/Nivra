"""Create or remove the exact P6.9 disposable database on the known Preview branch.

No connection string or credential is printed. The source endpoint must come
from the ignored local .env key P65_PREVIEW_BRANCH_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = "nivra_lumi_p69_gate"


def _configuration() -> tuple[str, str, str]:
    local = dotenv_values(ROOT / ".env")
    raw = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or local.get("P65_PREVIEW_BRANCH_DATABASE_URL")
    database = os.environ.get("P69_TEST_DATABASE_NAME", DEFAULT_DATABASE).strip().lower()
    if not raw:
        raise RuntimeError("P65_PREVIEW_BRANCH_DATABASE_URL não configurada.")
    if not database.replace("_", "").isalnum() or not any(label in database for label in ("p69", "gate", "test", "lumi")):
        raise RuntimeError("Nome do database descartável inválido.")
    source = make_url(raw)
    if source.get_backend_name() != "postgresql" or not source.host or not source.database:
        raise RuntimeError("A referência Preview não é uma URL PostgreSQL completa.")
    if source.database.lower() == database:
        raise RuntimeError("O database descartável não pode ser o database do Preview.")
    source = source.set(drivername="postgresql+pg8000", query={})
    target = source.set(database=database)
    return (
        source.render_as_string(hide_password=False),
        target.render_as_string(hide_password=False),
        database,
    )


def _summary(target_raw: str, database: str) -> str:
    target = make_url(target_raw)
    identity = f"{target.host}|{database}".encode("utf-8")
    return f"database={database}; fingerprint={hashlib.sha256(identity).hexdigest()[:12]}; credentials hidden"


def database_exists(source_raw: str, database: str) -> bool:
    engine = create_engine(source_raw, poolclass=NullPool, connect_args={"timeout": 10, "ssl_context": True})
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database"), {"database": database}
            ).first() is not None
    finally:
        engine.dispose()


def create_database(source_raw: str, target_raw: str, database: str) -> None:
    if database_exists(source_raw, database):
        raise RuntimeError("O database descartável já existe; nenhuma alteração foi feita.")
    engine = create_engine(
        source_raw, poolclass=NullPool, isolation_level="AUTOCOMMIT",
        connect_args={"timeout": 10, "ssl_context": True},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
    finally:
        engine.dispose()
    print(f"Disposable PostgreSQL created: {_summary(target_raw, database)}")


def drop_database(source_raw: str, target_raw: str, database: str) -> None:
    if not database_exists(source_raw, database):
        print(f"Disposable PostgreSQL already absent: {_summary(target_raw, database)}")
        return
    engine = create_engine(
        source_raw, poolclass=NullPool, isolation_level="AUTOCOMMIT",
        connect_args={"timeout": 10, "ssl_context": True},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :database AND pid <> pg_backend_pid()"
            ), {"database": database})
            connection.execute(text(f'DROP DATABASE "{database}"'))
    finally:
        engine.dispose()
    print(f"Disposable PostgreSQL removed: {_summary(target_raw, database)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the exact P6.9 disposable PostgreSQL database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--create", action="store_true")
    group.add_argument("--drop", action="store_true")
    args = parser.parse_args()
    try:
        source_raw, target_raw, database = _configuration()
        if args.create:
            create_database(source_raw, target_raw, database)
        elif args.drop:
            drop_database(source_raw, target_raw, database)
        else:
            print(f"Disposable PostgreSQL exists={database_exists(source_raw, database)}: {_summary(target_raw, database)}")
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print(f"Disposable database operation stopped: {exc}")
        else:
            print(f"Disposable database operation stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

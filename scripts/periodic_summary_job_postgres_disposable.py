"""Create, inspect, or remove the isolated P7.6 PostgreSQL gate database."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
DATABASE = "nivra_p76_gate"


def _urls() -> tuple[str, str]:
    values = dotenv_values(ROOT / ".env")
    raw = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    if not raw:
        raise RuntimeError("P65_PREVIEW_BRANCH_DATABASE_URL não configurada.")
    source = make_url(str(raw)).set(drivername="postgresql+pg8000", query={})
    if source.get_backend_name() != "postgresql" or not source.database:
        raise RuntimeError("A referência Preview precisa ser PostgreSQL.")
    if source.database.casefold() == DATABASE:
        raise RuntimeError("O banco descartável não pode ser o banco Preview.")
    return (
        source.render_as_string(hide_password=False),
        source.set(database=DATABASE).render_as_string(hide_password=False),
    )


def _engine(raw: str, *, autocommit: bool = False):
    return create_engine(
        raw,
        future=True,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT" if autocommit else None,
        connect_args={"timeout": 10, "ssl_context": True},
    )


def exists(source_raw: str) -> bool:
    engine = _engine(source_raw)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname=:name"),
                {"name": DATABASE},
            ).first() is not None
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the P7.6 disposable database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true")
    group.add_argument("--create", action="store_true")
    group.add_argument("--drop", action="store_true")
    args = parser.parse_args()
    try:
        source_raw, _target_raw = _urls()
        present = exists(source_raw)
        if args.create:
            if present:
                raise RuntimeError("O banco descartável P7.6 já existe.")
            engine = _engine(source_raw, autocommit=True)
            try:
                with engine.connect() as connection:
                    connection.execute(text(f'CREATE DATABASE "{DATABASE}"'))
            finally:
                engine.dispose()
            print(f"Disposable PostgreSQL created: database={DATABASE}; credentials hidden")
        elif args.drop:
            if present:
                engine = _engine(source_raw, autocommit=True)
                try:
                    with engine.connect() as connection:
                        connection.execute(
                            text(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE datname=:name AND pid <> pg_backend_pid()"
                            ),
                            {"name": DATABASE},
                        )
                        connection.execute(text(f'DROP DATABASE "{DATABASE}"'))
                finally:
                    engine.dispose()
            print(f"Disposable PostgreSQL absent: database={DATABASE}; credentials hidden")
        else:
            print(f"Disposable PostgreSQL exists={present}: database={DATABASE}; credentials hidden")
    except Exception as exc:
        print(f"Disposable database operation stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from database.connection import get_database_url
from database.models import metadata


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(migration=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_migrations(supplied_connection)
        return

    engine = create_engine(
        get_database_url(migration=True),
        future=True,
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        _run_migrations(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

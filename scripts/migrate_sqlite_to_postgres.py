"""Importa dados legados do SQLite para um PostgreSQL ja migrado pelo Alembic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.pool import NullPool
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import get_database_url
from database.migrations import get_alembic_config
from database.models import TABLES_IN_DEPENDENCY_ORDER


DEFAULT_SOURCE = ROOT / "storage" / "banco.db"


@dataclass(frozen=True)
class OrphanReference:
    table: str
    row_id: int
    column: str
    value: int
    target_table: str

    def describe(self) -> str:
        return (
            f"{self.table}.id={self.row_id}: {self.column}={self.value} "
            f"nao existe em {self.target_table}.id"
        )


KNOWN_ORPHAN_ROWS: dict[tuple[str, int], dict[str, Any]] = {
    ("transacoes", 1): {
        "reason": "registro legado ligado ao usuario removido 1",
        "fingerprint": "956b3e6aecf038f2b4339dd304630facf7619bb836b93e9bf0b925ae7ca14909",
    },
    ("transacoes", 2): {
        "reason": "registro legado ligado ao usuario removido 2",
        "fingerprint": "9a55e78ceb711e59c423b02ae2a7cf009cf3a5fca9098a030c673b8651a0dead",
    },
    ("vendas", 2): {
        "reason": "registro legado ligado ao usuario removido 1",
        "fingerprint": "18dfe06d3ae83efa864d938f121303d299c999e336f7b4ea04918bd8318d5c7d",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migra o SQLite legado para o PostgreSQL configurado no ambiente."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Grava no PostgreSQL. Sem esta opcao, apenas analisa o SQLite.",
    )
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Permite destino com dados e ignora IDs que ja existem.",
    )
    parser.add_argument(
        "--skip-known-orphans",
        action="store_true",
        help="Ignora somente os tres registros orfaos conhecidos e verificados.",
    )
    return parser.parse_args()


def _source_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def inspect_source(source: Path) -> tuple[sqlite3.Connection, dict[str, int]]:
    if not source.is_file():
        raise RuntimeError(f"Banco SQLite nao encontrado: {source}")
    connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    existing = _source_tables(connection)
    counts = {
        table.name: int(connection.execute(f'SELECT COUNT(*) FROM "{table.name}"').fetchone()[0])
        for table in TABLES_IN_DEPENDENCY_ORDER
        if table.name in existing
    }
    return connection, counts


def _convert_value(column: Any, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, Boolean):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes"}
        return bool(value)
    if isinstance(column.type, DateTime):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if isinstance(column.type, Date):
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    if isinstance(column.type, Numeric):
        return Decimal(str(value))
    if isinstance(column.type, (String, Text)) and isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _read_rows(
    source: sqlite3.Connection, table: Any, available_tables: set[str]
) -> list[dict[str, Any]]:
    if table.name not in available_tables:
        return []
    source_columns = {
        str(row[1]) for row in source.execute(f'PRAGMA table_info("{table.name}")').fetchall()
    }
    selected = [column for column in table.columns if column.name in source_columns]
    if not selected:
        return []
    names = ", ".join(f'"{column.name}"' for column in selected)
    records = source.execute(f'SELECT {names} FROM "{table.name}" ORDER BY id').fetchall()
    return [
        {column.name: _convert_value(column, record[column.name]) for column in selected}
        for record in records
    ]


def _row_fingerprint(row: dict[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    canonical = {name: normalize(value) for name, value in sorted(row.items())}
    serialized = json.dumps(
        canonical, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def find_orphan_references(
    source: sqlite3.Connection,
    excluded_rows: set[tuple[str, int]] | None = None,
) -> list[OrphanReference]:
    excluded = excluded_rows or set()
    available = _source_tables(source)
    ids_by_table = {
        table.name: {
            int(row[0])
            for row in source.execute(f'SELECT id FROM "{table.name}"').fetchall()
            if (table.name, int(row[0])) not in excluded
        }
        for table in TABLES_IN_DEPENDENCY_ORDER
        if table.name in available
    }
    problems: list[OrphanReference] = []
    for table in TABLES_IN_DEPENDENCY_ORDER:
        if table.name not in available:
            continue
        source_columns = {
            str(row[1]) for row in source.execute(f'PRAGMA table_info("{table.name}")').fetchall()
        }
        for foreign_key in table.foreign_keys:
            column_name = foreign_key.parent.name
            constraint_columns = {
                element.parent.name for element in foreign_key.constraint.elements
            }
            if (
                foreign_key.column.name != "id"
                or not constraint_columns.issubset(source_columns)
            ):
                continue
            target_table = foreign_key.column.table.name
            target_ids = ids_by_table.get(target_table, set())
            rows = source.execute(
                f'SELECT id, "{column_name}" FROM "{table.name}" '
                f'WHERE "{column_name}" IS NOT NULL'
            ).fetchall()
            for row_id, value in rows:
                if (table.name, int(row_id)) in excluded:
                    continue
                if int(value) not in target_ids:
                    problems.append(
                        OrphanReference(
                            table.name,
                            int(row_id),
                            column_name,
                            int(value),
                            target_table,
                        )
                    )
    return problems


def validate_source_integrity(source: sqlite3.Connection) -> list[str]:
    return [problem.describe() for problem in find_orphan_references(source)]


def resolve_known_orphans(
    source: sqlite3.Connection, *, skip_known_orphans: bool
) -> set[tuple[str, int]]:
    problems = find_orphan_references(source)
    if not problems:
        return set()
    if not skip_known_orphans:
        raise RuntimeError(
            "O SQLite possui relacionamentos orfaos: "
            + "; ".join(problem.describe() for problem in problems)
            + ". Use --skip-known-orphans somente se a lista for a esperada."
        )

    problem_rows = {(problem.table, problem.row_id) for problem in problems}
    unknown = problem_rows - set(KNOWN_ORPHAN_ROWS)
    if unknown:
        descriptions = [
            problem.describe()
            for problem in problems
            if (problem.table, problem.row_id) in unknown
        ]
        raise RuntimeError(
            "Foram encontrados orfaos nao autorizados: " + "; ".join(descriptions)
        )

    available = _source_tables(source)
    tables = {table.name: table for table in TABLES_IN_DEPENDENCY_ORDER}
    for row_key in sorted(problem_rows):
        table_name, row_id = row_key
        rows = _read_rows(source, tables[table_name], available)
        actual = next((row for row in rows if int(row["id"]) == row_id), None)
        if actual is None:
            raise RuntimeError(f"Registro conhecido nao encontrado: {table_name}.id={row_id}")
        if _row_fingerprint(actual) != KNOWN_ORPHAN_ROWS[row_key]["fingerprint"]:
            raise RuntimeError(
                f"O registro {table_name}.id={row_id} mudou; a assinatura nao corresponde."
            )

    remaining = find_orphan_references(source, problem_rows)
    if remaining:
        raise RuntimeError(
            "Ignorar os registros conhecidos criaria novos orfaos: "
            + "; ".join(problem.describe() for problem in remaining)
        )
    return problem_rows


def _ensure_schema_is_current(connection: Any) -> None:
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        raise RuntimeError("O destino nao possui migrations. Execute 'alembic upgrade head' primeiro.")
    version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    expected_version = ScriptDirectory.from_config(get_alembic_config()).get_current_head()
    if version != expected_version:
        raise RuntimeError(
            f"Schema do destino esta em uma versao inesperada: {version or 'sem versao'}."
        )


def _destination_counts(connection: Any) -> dict[str, int]:
    return {
        table.name: int(connection.execute(select(func.count()).select_from(table)).scalar_one())
        for table in TABLES_IN_DEPENDENCY_ORDER
    }


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        try:
            return Decimal(str(left)) == Decimal(str(right))
        except Exception:
            return False
    if isinstance(left, datetime) and isinstance(right, datetime):
        return left.replace(tzinfo=None) == right.replace(tzinfo=None)
    if isinstance(left, bytes) and isinstance(right, str):
        return left.decode("utf-8") == right
    if isinstance(left, str) and isinstance(right, bytes):
        return left == right.decode("utf-8")
    return left == right


def _verify_existing_rows(target: Any, table: Any, rows: list[dict[str, Any]]) -> set[int]:
    source_by_id = {int(row["id"]): row for row in rows}
    if not source_by_id:
        return set()
    existing = {
        int(row["id"]): dict(row)
        for row in target.execute(
            select(table).where(table.c.id.in_(source_by_id))
        ).mappings()
    }
    for row_id, destination in existing.items():
        source = source_by_id[row_id]
        differing = [
            name
            for name, value in source.items()
            if not _equivalent(value, destination.get(name))
        ]
        if differing:
            raise RuntimeError(
                f"Conflito em {table.name}.id={row_id}; campos diferentes: "
                + ", ".join(differing)
            )
    return set(existing)


def _reset_sequence(connection: Any, table_name: str) -> None:
    connection.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
        )
    )


def migrate(
    source: Path, *, allow_existing: bool, skip_known_orphans: bool
) -> dict[str, dict[str, int]]:
    source_connection, source_counts = inspect_source(source)
    try:
        skipped_orphans = resolve_known_orphans(
            source_connection, skip_known_orphans=skip_known_orphans
        )
        target_url = get_database_url(migration=True)
        if not target_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("O destino da importacao deve ser PostgreSQL.")
        engine = create_engine(target_url, future=True, poolclass=NullPool)
        report: dict[str, dict[str, int]] = {}
        try:
            with engine.begin() as target:
                _ensure_schema_is_current(target)
                destination_counts = _destination_counts(target)
                populated = {name: count for name, count in destination_counts.items() if count}
                if populated and not allow_existing:
                    details = ", ".join(f"{name}={count}" for name, count in populated.items())
                    raise RuntimeError(
                        "O PostgreSQL ja possui dados ("
                        + details
                        + "). Revise-os e use --allow-existing somente para retomar com seguranca."
                    )

                available = _source_tables(source_connection)
                for table in TABLES_IN_DEPENDENCY_ORDER:
                    rows = [
                        row
                        for row in _read_rows(source_connection, table, available)
                        if (table.name, int(row["id"])) not in skipped_orphans
                    ]
                    existing_ids: set[int] = set()
                    if allow_existing and rows:
                        existing_ids = _verify_existing_rows(target, table, rows)
                    pending = [row for row in rows if int(row["id"]) not in existing_ids]
                    if pending:
                        target.execute(table.insert(), pending)
                    _reset_sequence(target, table.name)
                    report[table.name] = {
                        "origem": source_counts.get(table.name, 0),
                        "inseridos": len(pending),
                        "ignorados_existentes": len(rows) - len(pending),
                        "ignorados_orfaos": sum(
                            1 for table_name, _ in skipped_orphans if table_name == table.name
                        ),
                    }
        finally:
            engine.dispose()
        return report
    finally:
        source_connection.close()


def main() -> int:
    args = parse_args()
    try:
        source, counts = inspect_source(args.source.resolve())
        try:
            print("Analise do SQLite:")
            for name, count in counts.items():
                print(f"  {name}: {count}")
            skipped_orphans = resolve_known_orphans(
                source, skip_known_orphans=args.skip_known_orphans
            )
        finally:
            source.close()
        if skipped_orphans:
            print("Registros conhecidos que ficarao fora do PostgreSQL:")
            for row_key in sorted(skipped_orphans):
                print(
                    f"  {row_key[0]}.id={row_key[1]}: "
                    f"{KNOWN_ORPHAN_ROWS[row_key]['reason']}"
                )
        valid_count = sum(counts.values()) - len(skipped_orphans)
        print(f"Total de registros validos para importacao: {valid_count}")
        if not args.execute:
            execute_command = "--execute"
            if skipped_orphans:
                execute_command += " --skip-known-orphans"
            print(
                "Dry-run concluido. Nenhum dado foi gravado. "
                f"Use {execute_command} para importar."
            )
            return 0

        report = migrate(
            args.source.resolve(),
            allow_existing=args.allow_existing,
            skip_known_orphans=args.skip_known_orphans,
        )
        print("Importacao concluida em uma unica transacao:")
        for name, values in report.items():
            print(
                f"  {name}: origem={values['origem']}, "
                f"inseridos={values['inseridos']}, "
                f"ignorados_existentes={values['ignorados_existentes']}, "
                f"ignorados_orfaos={values['ignorados_orfaos']}"
            )
        return 0
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

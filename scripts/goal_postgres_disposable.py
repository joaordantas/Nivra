"""Manage the isolated P8.2 PostgreSQL gate database."""

from scripts import budget_postgres_disposable as base


base.DATABASE = "nivra_p82_gate"


if __name__ == "__main__":
    base.main()

"""Create, inspect, or remove the isolated P7.7 PostgreSQL gate database."""

from scripts.periodic_summary_job_postgres_disposable import *  # noqa: F403
import scripts.periodic_summary_job_postgres_disposable as base


base.DATABASE = "nivra_p77_gate"


if __name__ == "__main__":
    base.main()

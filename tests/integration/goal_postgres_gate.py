"""P8.2 gate for the isolated disposable PostgreSQL database."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


ROOT=Path(__file__).resolve().parents[2]
EXPECTED_DATABASE="nivra_p82_gate"
EXPECTED_HEAD="d3e4f5a6b7c8"


def test_url_from_env()->str:
    values=dotenv_values(ROOT/".env"); preview=os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get("P65_PREVIEW_BRANCH_DATABASE_URL"); raw=os.environ.get("P82_TEST_DATABASE_URL") or values.get("P82_TEST_DATABASE_URL")
    if not raw and preview: raw=make_url(str(preview)).set(drivername="postgresql+pg8000",database=EXPECTED_DATABASE,query={}).render_as_string(hide_password=False)
    raw=str(raw or "").strip(); url=make_url(raw) if raw else None
    if url is None or url.get_backend_name()!="postgresql": raise RuntimeError("P82_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold()!=EXPECTED_DATABASE: raise RuntimeError("O gate exige o banco descartável nivra_p82_gate.")
    return raw


def run(raw:str)->None:
    os.environ["APP_ENV"]="test"; os.environ["TEST_DATABASE_URL"]=_driver_url(raw); os.environ.pop("DATABASE_URL",None); os.environ.pop("DATABASE_URL_UNPOOLED",None)
    from alembic import command
    from database.connection import dispose_engine,get_engine
    from database.migrations import get_alembic_config
    from services.goal_service import GoalConflictError,add_goal_movement_service,create_goal_service,get_goal_service
    dispose_engine(); config=get_alembic_config(); command.upgrade(config,"head"); command.check(config); engine=get_engine(); inspector=inspect(engine)
    require({"goals","goal_movements"}.issubset(inspector.get_table_names()),"goal tables")
    require(any(index["name"]=="ix_goal_movements_goal_effective" for index in inspector.get_indexes("goal_movements")),"movement index")
    with engine.begin() as connection:
        user=connection.execute(text("INSERT INTO usuarios (usuario,email,senha) VALUES ('P82','p82@example.invalid','x') RETURNING id")).scalar_one()
        before=connection.execute(text("SELECT COUNT(*) FROM transacoes")).scalar_one()
    goal=create_goal_service(user,"Reserva",None,Decimal("100.00"),None,today=date(2026,10,7)); add_goal_movement_service(user,goal["id"],"contribution",Decimal("100"),"2026-10-07",None,"p82-contribution",today=date(2026,10,7))
    barrier=threading.Barrier(8)
    def withdraw(index):
        barrier.wait(timeout=20)
        try: add_goal_movement_service(user,goal["id"],"withdrawal",Decimal("80"),"2026-10-07",None,f"p82-withdraw-{index}",today=date(2026,10,7)); return "ok"
        except GoalConflictError: return "conflict"
    with ThreadPoolExecutor(max_workers=8) as executor: outcomes=list(executor.map(withdraw,range(8)))
    require(outcomes.count("ok")==1 and outcomes.count("conflict")==7,"concurrent non-negative balance")
    require(get_goal_service(goal["id"],user,today=date(2026,10,7))["saved_amount"]==Decimal("20.00"),"derived balance")
    with engine.connect() as connection: require(connection.execute(text("SELECT COUNT(*) FROM transacoes")).scalar_one()==before,"no financial double entry")
    command.downgrade(config,"c2d3e4f5a6b7"); command.upgrade(config,"head"); command.check(config)
    with get_engine().connect() as connection: require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()==EXPECTED_HEAD,"Alembic head")
    dispose_engine(); print("P8.2 PostgreSQL gate passed; only fictional data was used.")


def main()->None:
    try: run(test_url_from_env())
    except Exception as exc: print(f"Gate stopped: {type(exc).__name__}; details suppressed."); raise SystemExit(1) from None


if __name__=="__main__": main()

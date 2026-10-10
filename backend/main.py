import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.middleware.operations import OperationsMiddleware


# Em desenvolvimento, carrega a configuração local sem substituir variáveis
# já fornecidas pelo ambiente de execução (como Vercel ou terminal).
load_dotenv(override=False)

_log_level_name = os.environ.get("NIVRA_LOG_LEVEL", "INFO").strip().upper()
logging.getLogger("nivra").setLevel(
    getattr(logging, _log_level_name, logging.INFO)
)


from backend.routers.auth import router as auth_router
from backend.routers.accounts import router as accounts_router
from backend.routers.categories import router as categories_router
from backend.routers.cards import router as cards_router
from backend.routers.budgets import router as budgets_router
from backend.routers.goals import router as goals_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.installments import router as installments_router
from backend.routers.internal_jobs import router as internal_jobs_router
from backend.routers.insights import router as insights_router
from backend.routers.lumi import router as lumi_router
from backend.routers.notifications import router as notifications_router
from backend.routers.open_finance import router as open_finance_router
from backend.routers.sales import router as sales_router
from backend.routers.transactions import router as transactions_router
from database.connection import check_database_connection, database_target_fingerprint

app = FastAPI(
    title="Nivra API",
    version="0.1.0",
    description="API da Nivra, plataforma de controle financeiro pessoal.",
)

local_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
configured_origins = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=local_origins + configured_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.add_middleware(OperationsMiddleware)

app.include_router(auth_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(cards_router, prefix="/api")
app.include_router(budgets_router, prefix="/api")
app.include_router(goals_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(installments_router, prefix="/api")
app.include_router(internal_jobs_router, prefix="/api")
app.include_router(insights_router, prefix="/api")
app.include_router(lumi_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(open_finance_router, prefix="/api")
app.include_router(sales_router, prefix="/api")


@app.get("/api/health", include_in_schema=False)
def health_check() -> dict:
    return {
        "message": "API da Nivra online.",
        "database": "online" if check_database_connection() else "indisponivel",
        "database_target_fingerprint": database_target_fingerprint(),
        "docs": "/docs",
    }


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.frontend("/", directory=frontend_dist, fallback="index.html")

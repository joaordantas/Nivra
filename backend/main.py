import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.auth import router as auth_router
from backend.routers.accounts import router as accounts_router
from backend.routers.categories import router as categories_router
from backend.routers.cards import router as cards_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.open_finance import router as open_finance_router
from backend.routers.sales import router as sales_router
from backend.routers.transactions import router as transactions_router
from database.connection import check_database_connection

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

app.include_router(auth_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(cards_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(open_finance_router, prefix="/api")
app.include_router(sales_router, prefix="/api")


@app.get("/api/health", include_in_schema=False)
def health_check() -> dict:
    return {
        "message": "API da Nivra online.",
        "database": "online" if check_database_connection() else "indisponivel",
        "docs": "/docs",
    }


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.frontend("/", directory=frontend_dist, fallback="index.html")

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.backtest import router as backtest_router
from app.api.v1.endpoints.credentials import router as credentials_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.journal import router as journal_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.performance import router as performance_router
from app.api.v1.endpoints.signals import router as signals_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(credentials_router)
api_router.include_router(market_router)
api_router.include_router(signals_router)
api_router.include_router(performance_router)
api_router.include_router(backtest_router)
api_router.include_router(journal_router)

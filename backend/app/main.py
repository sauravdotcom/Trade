from contextlib import asynccontextmanager
from collections import defaultdict, deque
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import Base, engine
from app.services.orchestrator import SignalOrchestrator
from app.utils.ws_manager import ConnectionManager

settings = get_settings()
RATE_LIMIT_MAX = 120
RATE_LIMIT_WINDOW_SEC = 60
request_buckets: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ws_manager = ConnectionManager()
    orchestrator = SignalOrchestrator(ws_manager)

    app.state.ws_manager = ws_manager
    app.state.orchestrator = orchestrator

    await orchestrator.start()
    yield
    await orchestrator.stop()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def apply_rate_limit(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = request_buckets[client_ip]

    while bucket and (now - bucket[0]) > RATE_LIMIT_WINDOW_SEC:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    bucket.append(now)
    response = await call_next(request)
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)

from fastapi import APIRouter, Request

from app.schemas.signal import SignalEnvelope

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/snapshot", response_model=SignalEnvelope | None)
async def latest_snapshot(request: Request, symbol: str | None = None) -> SignalEnvelope | None:
    orchestrator = request.app.state.orchestrator
    return await orchestrator.latest(symbol)

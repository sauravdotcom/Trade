from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.models.signal import SignalRecord
from app.schemas.signal import SignalEnvelope

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/latest", response_model=SignalEnvelope | None)
async def latest_signal(request: Request, symbol: str | None = None) -> SignalEnvelope | None:
    orchestrator = request.app.state.orchestrator
    return await orchestrator.latest(symbol)


@router.get("/history")
async def signal_history(limit: int = 50, symbol: str | None = None) -> list[dict]:
    async with AsyncSessionFactory() as db:
        query = select(SignalRecord).order_by(desc(SignalRecord.created_at)).limit(limit)
        if symbol:
            query = query.where(SignalRecord.symbol == symbol.upper())
        result = await db.execute(query)
        records = result.scalars().all()

    return [
        {
            "id": item.id,
            "symbol": item.symbol,
            "instrument": item.instrument,
            "signal_type": item.signal_type,
            "entry": item.entry,
            "stop_loss": item.stop_loss,
            "target_1": item.target_1,
            "target_2": item.target_2,
            "confidence": item.confidence,
            "reason": item.reason,
            "created_at": item.created_at.isoformat(),
        }
        for item in records
    ]


@router.websocket("/ws")
async def signal_stream(websocket: WebSocket, request: Request) -> None:
    manager = request.app.state.ws_manager
    orchestrator = request.app.state.orchestrator
    symbol = websocket.query_params.get("symbol")

    await manager.connect(websocket)
    latest = await orchestrator.latest(symbol)
    if latest:
        await websocket.send_json(latest.model_dump(mode="json"))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

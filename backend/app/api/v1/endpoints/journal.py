from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.journal import TradeJournal
from app.models.user import User
from app.schemas.journal import JournalCreate, JournalRead

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post("/entries", response_model=JournalRead)
async def add_entry(
    payload: JournalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JournalRead:
    row = TradeJournal(
        user_id=current_user.id,
        symbol=payload.symbol,
        instrument=payload.instrument,
        side=payload.side,
        entry=payload.entry,
        exit_price=payload.exit_price,
        pnl=payload.pnl,
        note=payload.note,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return JournalRead.model_validate(row, from_attributes=True)


@router.get("/entries", response_model=list[JournalRead])
async def list_entries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[JournalRead]:
    result = await db.execute(
        select(TradeJournal)
        .where(TradeJournal.user_id == current_user.id)
        .order_by(desc(TradeJournal.created_at))
        .limit(200)
    )
    rows = result.scalars().all()
    return [JournalRead.model_validate(item, from_attributes=True) for item in rows]

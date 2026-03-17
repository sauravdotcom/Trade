from datetime import datetime

from pydantic import BaseModel


class JournalCreate(BaseModel):
    symbol: str
    instrument: str
    side: str
    entry: float
    exit_price: float | None = None
    pnl: float | None = None
    note: str | None = None


class JournalRead(JournalCreate):
    id: int
    user_id: int
    created_at: datetime

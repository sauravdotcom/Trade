from datetime import datetime

from pydantic import BaseModel


class CredentialCreate(BaseModel):
    broker: str
    api_key: str
    access_token: str


class CredentialRead(BaseModel):
    id: int
    broker: str
    has_api_key: bool
    has_access_token: bool
    updated_at: datetime | None = None

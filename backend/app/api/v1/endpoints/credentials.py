from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models.credential import BrokerCredential
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialRead

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("", response_model=CredentialRead)
async def upsert_credential(
    payload: CredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CredentialRead:
    broker = payload.broker.lower().strip()
    if broker not in {"kite", "angel", "upstox"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported broker")

    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.user_id == current_user.id,
            BrokerCredential.broker == broker,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = BrokerCredential(
            user_id=current_user.id,
            broker=broker,
            encrypted_api_key=encrypt_secret(payload.api_key),
            encrypted_access_token=encrypt_secret(payload.access_token),
        )
        db.add(row)
    else:
        row.encrypted_api_key = encrypt_secret(payload.api_key)
        row.encrypted_access_token = encrypt_secret(payload.access_token)

    await db.commit()
    await db.refresh(row)

    return CredentialRead(
        id=row.id,
        broker=row.broker,
        has_api_key=bool(row.encrypted_api_key),
        has_access_token=bool(row.encrypted_access_token),
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CredentialRead]:
    result = await db.execute(select(BrokerCredential).where(BrokerCredential.user_id == current_user.id))
    rows = result.scalars().all()

    return [
        CredentialRead(
            id=row.id,
            broker=row.broker,
            has_api_key=bool(row.encrypted_api_key),
            has_access_token=bool(row.encrypted_access_token),
            updated_at=row.updated_at,
        )
        for row in rows
    ]

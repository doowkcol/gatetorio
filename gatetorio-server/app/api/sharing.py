"""Sharing token API routes for engineer handoff"""

import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.device import Device
from app.models.user_auth import UserAuth, AccessLevel
from app.models.sharing_token import SharingToken
from app.api.schemas import (
    SharingTokenCreateRequest,
    SharingTokenCreateResponse,
    SharingTokenRedeemRequest,
    SharingTokenRedeemResponse,
    DeviceInfo,
)

router = APIRouter(prefix="/sharing", tags=["sharing"])


def generate_sharing_token() -> str:
    """Generate a unique sharing token"""
    return secrets.token_urlsafe(32)


@router.post("/create", response_model=SharingTokenCreateResponse)
async def create_sharing_token(
    request: SharingTokenCreateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Create a sharing token for device access handoff
    Requires OWNER access level
    """
    # Find device
    result = await db.execute(
        select(Device).where(Device.controller_id == request.controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Verify creator has access and is owner
    result = await db.execute(
        select(UserAuth).where(
            UserAuth.device_id == device.id, UserAuth.user_token == request.user_token
        )
    )
    creator_auth = result.scalar_one_or_none()

    if not creator_auth:
        raise HTTPException(
            status_code=403, detail="User does not have access to this device"
        )

    if creator_auth.access_level != AccessLevel.OWNER:
        raise HTTPException(
            status_code=403, detail="Only device owners can create sharing tokens"
        )

    # Calculate expiry time
    expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)

    # Generate token
    token = generate_sharing_token()

    # Create sharing token
    sharing_token = SharingToken(
        token=token,
        device_id=device.id,
        created_by_user_id=creator_auth.id,
        access_level=request.access_level,
        expires_at=expires_at,
        notes=request.notes,
    )
    db.add(sharing_token)
    await db.commit()
    await db.refresh(sharing_token)

    return SharingTokenCreateResponse(
        token=token, expires_at=expires_at, controller_id=device.controller_id
    )


@router.post("/redeem", response_model=SharingTokenRedeemResponse)
async def redeem_sharing_token(
    request: SharingTokenRedeemRequest, db: AsyncSession = Depends(get_db)
):
    """
    Redeem a sharing token to gain access to a device
    """
    # Find sharing token
    result = await db.execute(
        select(SharingToken).where(SharingToken.token == request.token)
    )
    sharing_token = result.scalar_one_or_none()

    if not sharing_token:
        raise HTTPException(status_code=404, detail="Invalid sharing token")

    # Check if already used
    if sharing_token.is_used:
        raise HTTPException(status_code=400, detail="Token has already been used")

    # Check if expired
    if sharing_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token has expired")

    # Get device
    result = await db.execute(
        select(Device).where(Device.id == sharing_token.device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check if user already has access
    result = await db.execute(
        select(UserAuth).where(
            UserAuth.device_id == device.id, UserAuth.user_token == request.user_token
        )
    )
    existing_auth = result.scalar_one_or_none()

    if existing_auth:
        # Update existing access level if new one is higher
        if sharing_token.access_level == AccessLevel.OWNER:
            existing_auth.access_level = AccessLevel.OWNER
        elif (
            sharing_token.access_level == AccessLevel.ENGINEER
            and existing_auth.access_level == AccessLevel.READONLY
        ):
            existing_auth.access_level = AccessLevel.ENGINEER
    else:
        # Create new authorization
        new_auth = UserAuth(
            device_id=device.id,
            user_token=request.user_token,
            access_level=sharing_token.access_level,
        )
        db.add(new_auth)

    # Mark token as used
    sharing_token.is_used = True
    sharing_token.used_by_user_token = request.user_token
    sharing_token.used_at = datetime.utcnow()

    await db.commit()

    # Return device info
    device_info = DeviceInfo(
        id=device.id,
        controller_id=device.controller_id,
        hardware_id=device.hardware_id,
        device_name=device.device_name,
        firmware_version=device.firmware_version,
        is_online=device.is_online,
        last_seen=device.last_seen,
        created_at=device.created_at,
    )

    return SharingTokenRedeemResponse(
        success=True,
        message="Access granted successfully",
        device_info=device_info,
    )


@router.get("/tokens/{controller_id}")
async def list_sharing_tokens(
    controller_id: str, user_token: str, db: AsyncSession = Depends(get_db)
):
    """
    List all sharing tokens for a device (owner only)
    """
    # Find device
    result = await db.execute(
        select(Device).where(Device.controller_id == controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Verify user is owner
    result = await db.execute(
        select(UserAuth).where(
            UserAuth.device_id == device.id, UserAuth.user_token == user_token
        )
    )
    user_auth = result.scalar_one_or_none()

    if not user_auth or user_auth.access_level != AccessLevel.OWNER:
        raise HTTPException(
            status_code=403, detail="Only device owners can view sharing tokens"
        )

    # Get all sharing tokens for this device
    result = await db.execute(
        select(SharingToken).where(SharingToken.device_id == device.id)
    )
    tokens = result.scalars().all()

    return {
        "tokens": [
            {
                "token": token.token[:8] + "...",  # Partial token for security
                "access_level": token.access_level,
                "is_used": token.is_used,
                "expires_at": token.expires_at,
                "created_at": token.created_at,
                "notes": token.notes,
            }
            for token in tokens
        ]
    }

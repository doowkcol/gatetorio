"""User authorization and device discovery API routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.models.device import Device
from app.models.user_auth import UserAuth
from app.api.schemas import (
    UserAuthRequest,
    UserAuthResponse,
    DeviceDiscoveryRequest,
    DeviceDiscoveryResponse,
    DeviceInfo,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/authorize", response_model=UserAuthResponse)
async def authorize_user(
    request: UserAuthRequest, db: AsyncSession = Depends(get_db)
):
    """
    Authorize a user to access a device
    Called by Pi after successful BLE pairing
    """
    # Find device by controller_id
    result = await db.execute(
        select(Device).where(Device.controller_id == request.controller_id)
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
        # Update existing authorization
        existing_auth.access_level = request.access_level
        existing_auth.last_accessed = datetime.utcnow()
        user_auth = existing_auth
    else:
        # Create new authorization
        user_auth = UserAuth(
            device_id=device.id,
            user_token=request.user_token,
            access_level=request.access_level,
        )
        db.add(user_auth)

    await db.commit()
    await db.refresh(user_auth)

    return UserAuthResponse(
        success=True,
        message="User authorized successfully",
        user_id=user_auth.id,
    )


@router.post("/discover", response_model=DeviceDiscoveryResponse)
async def discover_devices(
    request: DeviceDiscoveryRequest, db: AsyncSession = Depends(get_db)
):
    """
    Discover devices accessible to a user
    Called by app with user_token from BLE pairing
    """
    # Find all devices this user has access to
    result = await db.execute(
        select(Device)
        .join(UserAuth)
        .where(UserAuth.user_token == request.user_token)
    )
    devices = result.scalars().all()

    # Update last_accessed timestamp
    await db.execute(
        select(UserAuth)
        .where(UserAuth.user_token == request.user_token)
        .execution_options(synchronize_session="fetch")
    )

    device_infos = [
        DeviceInfo(
            id=device.id,
            controller_id=device.controller_id,
            hardware_id=device.hardware_id,
            device_name=device.device_name,
            firmware_version=device.firmware_version,
            is_online=device.is_online,
            last_seen=device.last_seen,
            created_at=device.created_at,
        )
        for device in devices
    ]

    return DeviceDiscoveryResponse(devices=device_infos)


@router.get("/access/{user_token}/{controller_id}")
async def check_access(
    user_token: str, controller_id: str, db: AsyncSession = Depends(get_db)
):
    """Check if a user has access to a specific device"""
    result = await db.execute(
        select(UserAuth)
        .join(Device)
        .where(
            UserAuth.user_token == user_token,
            Device.controller_id == controller_id,
        )
    )
    user_auth = result.scalar_one_or_none()

    if not user_auth:
        return {"has_access": False, "access_level": None}

    # Check if access has expired
    if user_auth.expires_at and user_auth.expires_at < datetime.utcnow():
        return {"has_access": False, "access_level": None, "reason": "Access expired"}

    return {
        "has_access": True,
        "access_level": user_auth.access_level,
        "expires_at": user_auth.expires_at,
    }

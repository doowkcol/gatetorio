"""Command relay API routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.device import Device
from app.models.user_auth import UserAuth, AccessLevel
from app.api.schemas import CommandRequest, CommandResponse
from app.services.mqtt_client import mqtt_service

router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("/send", response_model=CommandResponse)
async def send_command(request: CommandRequest, db: AsyncSession = Depends(get_db)):
    """
    Send a command to a device via MQTT
    Requires user to have access to the device
    """
    # Find device
    result = await db.execute(
        select(Device).where(Device.controller_id == request.controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Verify user has access
    result = await db.execute(
        select(UserAuth).where(
            UserAuth.device_id == device.id, UserAuth.user_token == request.user_token
        )
    )
    user_auth = result.scalar_one_or_none()

    if not user_auth:
        raise HTTPException(
            status_code=403, detail="User does not have access to this device"
        )

    # Check if device is online
    if not device.is_online:
        raise HTTPException(
            status_code=503, detail="Device is offline and cannot receive commands"
        )

    # Publish command via MQTT
    success = mqtt_service.publish_command(request.controller_id, request.command)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send command")

    return CommandResponse(success=True, message="Command sent successfully")


@router.get("/status/{controller_id}")
async def get_device_status(
    controller_id: str, user_token: str, db: AsyncSession = Depends(get_db)
):
    """
    Get current device status
    This would typically subscribe to MQTT status topic
    """
    # Find device
    result = await db.execute(
        select(Device).where(Device.controller_id == controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Verify user has access
    result = await db.execute(
        select(UserAuth).where(
            UserAuth.device_id == device.id, UserAuth.user_token == user_token
        )
    )
    user_auth = result.scalar_one_or_none()

    if not user_auth:
        raise HTTPException(
            status_code=403, detail="User does not have access to this device"
        )

    return {
        "controller_id": device.controller_id,
        "is_online": device.is_online,
        "last_seen": device.last_seen,
        "firmware_version": device.firmware_version,
    }

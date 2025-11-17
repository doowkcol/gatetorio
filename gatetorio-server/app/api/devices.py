"""Device registration and management API routes"""

import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.models.device import Device
from app.api.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceInfo,
)
from app.core.config import settings

router = APIRouter(prefix="/devices", tags=["devices"])


def generate_mqtt_credentials(controller_id: str) -> tuple[str, str]:
    """Generate MQTT username and password for device"""
    username = f"device_{controller_id}"
    # Generate secure random password
    password = secrets.token_urlsafe(32)
    return username, password


@router.post("/register", response_model=DeviceRegisterResponse)
async def register_device(
    request: DeviceRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """
    Register a new device or update existing device
    Called by Pi on boot with hardware_id and controller_id
    """
    # Check if device with this hardware_id already exists
    result = await db.execute(
        select(Device).where(Device.hardware_id == request.hardware_id)
    )
    existing_device = result.scalar_one_or_none()

    if existing_device:
        # Update existing device
        existing_device.controller_id = request.controller_id
        existing_device.firmware_version = request.firmware_version
        existing_device.device_name = request.device_name
        existing_device.last_seen = datetime.utcnow()
        existing_device.is_online = True

        device = existing_device
    else:
        # Create new device
        mqtt_username, mqtt_password = generate_mqtt_credentials(
            request.controller_id
        )

        # Hash the password for storage
        password_hash = hashlib.sha256(mqtt_password.encode()).hexdigest()

        device = Device(
            hardware_id=request.hardware_id,
            controller_id=request.controller_id,
            firmware_version=request.firmware_version,
            device_name=request.device_name,
            mqtt_username=mqtt_username,
            mqtt_password_hash=password_hash,
            is_online=True,
            network_enabled=True,
        )
        db.add(device)

        # Store unhashed password to return (only time we have it)
        device._temp_mqtt_password = mqtt_password

    await db.commit()
    await db.refresh(device)

    # Get password (unhashed for new devices, regenerate for existing)
    if hasattr(device, "_temp_mqtt_password"):
        mqtt_password = device._temp_mqtt_password
    else:
        # For existing devices, regenerate credentials
        mqtt_username, mqtt_password = generate_mqtt_credentials(
            request.controller_id
        )
        device.mqtt_username = mqtt_username
        device.mqtt_password_hash = hashlib.sha256(mqtt_password.encode()).hexdigest()
        await db.commit()

    # Return MQTT credentials and connection info
    return DeviceRegisterResponse(
        device_id=device.id,
        controller_id=device.controller_id,
        mqtt_username=device.mqtt_username,
        mqtt_password=mqtt_password,
        mqtt_broker_host=settings.MQTT_BROKER_HOST,
        mqtt_broker_port=settings.MQTT_BROKER_PORT,
        mqtt_topic_commands=f"{settings.MQTT_TOPIC_PREFIX}/{device.controller_id}/commands",
        mqtt_topic_status=f"{settings.MQTT_TOPIC_PREFIX}/{device.controller_id}/status",
    )


@router.get("/{controller_id}", response_model=DeviceInfo)
async def get_device(controller_id: str, db: AsyncSession = Depends(get_db)):
    """Get device information by controller_id"""
    result = await db.execute(
        select(Device).where(Device.controller_id == controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device


@router.post("/{controller_id}/heartbeat")
async def device_heartbeat(controller_id: str, db: AsyncSession = Depends(get_db)):
    """Update device last_seen timestamp (heartbeat)"""
    result = await db.execute(
        select(Device).where(Device.controller_id == controller_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.last_seen = datetime.utcnow()
    device.is_online = True
    await db.commit()

    return {"status": "ok", "last_seen": device.last_seen}

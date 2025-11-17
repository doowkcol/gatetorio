"""Pydantic schemas for API request/response validation"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.user_auth import AccessLevel


# Device schemas
class DeviceRegisterRequest(BaseModel):
    """Device registration request from Pi"""

    hardware_id: str = Field(..., description="Immutable hardware identifier")
    controller_id: str = Field(..., description="Mutable controller identifier")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    device_name: Optional[str] = Field(None, description="User-friendly device name")


class DeviceRegisterResponse(BaseModel):
    """Device registration response"""

    device_id: int
    controller_id: str
    mqtt_username: str
    mqtt_password: str
    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_topic_commands: str
    mqtt_topic_status: str


class DeviceStatusUpdate(BaseModel):
    """Device status update"""

    controller_id: str
    is_online: bool
    last_seen: datetime


class DeviceInfo(BaseModel):
    """Device information"""

    id: int
    controller_id: str
    hardware_id: str
    device_name: Optional[str]
    firmware_version: Optional[str]
    is_online: bool
    last_seen: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# User authorization schemas
class UserAuthRequest(BaseModel):
    """User authorization request from Pi after BLE pairing"""

    controller_id: str
    user_token: str
    access_level: AccessLevel = AccessLevel.OWNER


class UserAuthResponse(BaseModel):
    """User authorization response"""

    success: bool
    message: str
    user_id: Optional[int] = None


class DeviceDiscoveryRequest(BaseModel):
    """Device discovery request from app"""

    user_token: str


class DeviceDiscoveryResponse(BaseModel):
    """Device discovery response"""

    devices: List[DeviceInfo]


# Sharing token schemas
class SharingTokenCreateRequest(BaseModel):
    """Request to create a sharing token"""

    controller_id: str
    user_token: str  # Creator's token
    access_level: AccessLevel = AccessLevel.ENGINEER
    expires_in_hours: int = Field(24, description="Token validity in hours")
    notes: Optional[str] = None


class SharingTokenCreateResponse(BaseModel):
    """Sharing token creation response"""

    token: str
    expires_at: datetime
    controller_id: str


class SharingTokenRedeemRequest(BaseModel):
    """Request to redeem a sharing token"""

    token: str
    user_token: str  # New user's token


class SharingTokenRedeemResponse(BaseModel):
    """Sharing token redemption response"""

    success: bool
    message: str
    device_info: Optional[DeviceInfo] = None


# Command relay schemas
class CommandRequest(BaseModel):
    """Command request from app to device"""

    controller_id: str
    user_token: str
    command: dict = Field(..., description="Command payload")


class CommandResponse(BaseModel):
    """Command response"""

    success: bool
    message: str


# Health check
class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    mqtt_connected: bool
    database_connected: bool
    version: str

"""Device model - tracks all gate controllers"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class Device(Base):
    """
    Device table - Dual identity system
    - hardware_id: Immutable identifier for lifecycle tracking (MAC, serial, etc.)
    - controller_id: Mutable identifier for user access (can be changed/reset)
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    # Immutable hardware identifier (MAC address, serial number, etc.)
    hardware_id = Column(String(255), unique=True, nullable=False, index=True)

    # Mutable controller identifier (user-facing ID)
    controller_id = Column(String(255), unique=True, nullable=False, index=True)

    # Device information
    firmware_version = Column(String(50), nullable=True)
    device_name = Column(String(255), nullable=True)  # User-friendly name

    # Connection status
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    # MQTT credentials
    mqtt_username = Column(String(255), nullable=True)
    mqtt_password_hash = Column(String(255), nullable=True)

    # Network mode
    network_enabled = Column(Boolean, default=False)  # Some devices are BLE-only

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<Device(controller_id='{self.controller_id}', hardware_id='{self.hardware_id}')>"

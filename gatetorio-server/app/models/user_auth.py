"""User authorization model - maps BLE tokens to device access"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class AccessLevel(str, enum.Enum):
    """Access levels for users"""

    OWNER = "owner"  # Full access, can share
    ENGINEER = "engineer"  # Full access, temporary
    READONLY = "readonly"  # View only


class UserAuth(Base):
    """
    User authorization table
    Maps BLE pairing tokens to device access
    """

    __tablename__ = "user_auth"

    id = Column(Integer, primary_key=True, index=True)

    # Device reference
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # User token from BLE pairing (unique identifier from app)
    user_token = Column(String(255), nullable=False, index=True)

    # Access control
    access_level = Column(Enum(AccessLevel), default=AccessLevel.READONLY)

    # Optional user information
    user_email = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)

    # Expiry for temporary access (engineer handoff)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to device
    device = relationship("Device", backref="authorized_users")

    def __repr__(self):
        return f"<UserAuth(user_token='{self.user_token[:8]}...', access_level='{self.access_level}')>"

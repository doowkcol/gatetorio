"""Sharing token model - for engineer handoff system"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.user_auth import AccessLevel
from app.core.database import Base


class SharingToken(Base):
    """
    Sharing tokens for device access handoff
    Allows authorized users to generate temporary access tokens for engineers
    """

    __tablename__ = "sharing_tokens"

    id = Column(Integer, primary_key=True, index=True)

    # Unique sharing token
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Source device
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # Token creator
    created_by_user_id = Column(Integer, ForeignKey("user_auth.id"), nullable=False)

    # Access level to grant
    access_level = Column(Enum(AccessLevel), default=AccessLevel.ENGINEER)

    # Usage tracking
    is_used = Column(Boolean, default=False)
    used_by_user_token = Column(String(255), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)

    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Optional metadata
    notes = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    device = relationship("Device", backref="sharing_tokens")
    creator = relationship("UserAuth", backref="created_tokens")

    def __repr__(self):
        return f"<SharingToken(token='{self.token[:8]}...', used={self.is_used})>"

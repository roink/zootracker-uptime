"""Zoo visit tracking models."""

import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class ZooVisit(Base):
    """Record of a user visiting a zoo."""

    __tablename__ = "zoo_visits"
    __table_args__ = (
        UniqueConstraint("user_id", "zoo_id", "visit_date"),
        Index("ix_zoo_visit_user_zoo", "user_id", "zoo_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    zoo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("zoos.id", ondelete="CASCADE"),
        nullable=False,
    )
    visit_date = Column(Date, nullable=False)
    notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="zoo_visits")
    zoo = relationship("Zoo", back_populates="visits")

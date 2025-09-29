"""Animal sighting models."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class AnimalSighting(Base):
    """A specific instance of a user seeing an animal at a zoo."""

    __tablename__ = "animal_sightings"
    __table_args__ = (
        Index("idx_animalsighting_user_animal", "user_id", "animal_id"),
        Index(
            "idx_sightings_user_day_created",
            "user_id",
            text("sighting_datetime DESC"),
            text("created_at DESC"),
        ),
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
    animal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
    )
    sighting_datetime = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text)
    photo_url = Column(String(512))
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="animal_sightings")
    zoo = relationship("Zoo", back_populates="sightings")
    animal = relationship("Animal", back_populates="sightings")

    @property
    def animal_name_de(self):
        """Return the German name for the sighted animal if available."""
        if self.animal is None:
            return None
        return (
            self.animal.name_de
            or self.animal.german_label
            or self.animal.name_en
        )

    @property
    def animal_name_en(self):
        """Return the English name for the sighted animal if available."""
        if self.animal is None:
            return None
        return self.animal.name_en or self.animal.name_de

    @property
    def zoo_name(self):
        """Return the name of the zoo where the sighting occurred."""
        if self.zoo is None:
            return None
        return self.zoo.name

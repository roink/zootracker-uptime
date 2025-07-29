"""SQLAlchemy ORM models for the Zoo Tracker application."""

from sqlalchemy import (
    Column,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    DECIMAL,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    """A registered user of the application."""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    # bcrypt salts embedded in the hash are around 53 characters so
    # allow up to 64 characters for future-proofing
    password_salt = Column(String(64), nullable=False)
    password_hash = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    zoo_visits = relationship("ZooVisit", back_populates="user")
    animal_sightings = relationship("AnimalSighting", back_populates="user")
    achievements = relationship("UserAchievement", back_populates="user")


class Zoo(Base):
    """A zoo location that can be visited."""

    __tablename__ = "zoos"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(255), nullable=False)
    address = Column(Text)
    latitude = Column(DECIMAL(9, 6))
    longitude = Column(DECIMAL(9, 6))
    description = Column(Text)
    image_url = Column(String(512))
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    animals = relationship("ZooAnimal", back_populates="zoo")
    visits = relationship("ZooVisit", back_populates="zoo")
    sightings = relationship("AnimalSighting", back_populates="zoo")


class Category(Base):
    """Top-level classification of animals (e.g. Mammal)."""

    __tablename__ = "categories"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(100), nullable=False, unique=True)

    animals = relationship("Animal", back_populates="category")


class Animal(Base):
    """An animal that can belong to a category and appear in zoos."""

    __tablename__ = "animals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    common_name = Column(String(255), nullable=False)
    scientific_name = Column(String(255))
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    description = Column(Text)
    default_image_url = Column(String(512))
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category = relationship("Category", back_populates="animals")
    zoos = relationship("ZooAnimal", back_populates="animal")
    sightings = relationship("AnimalSighting", back_populates="animal")


class ZooAnimal(Base):
    """Association table linking animals to zoos."""

    __tablename__ = "zoo_animals"

    zoo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("zoos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    animal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("animals.id", ondelete="CASCADE"),
        primary_key=True,
    )

    zoo = relationship("Zoo", back_populates="animals")
    animal = relationship("Animal", back_populates="zoos")


class ZooVisit(Base):
    """Record of a user visiting a zoo."""

    __tablename__ = "zoo_visits"
    __table_args__ = (UniqueConstraint("user_id", "zoo_id", "visit_date"),)

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


class AnimalSighting(Base):
    """A specific instance of a user seeing an animal at a zoo."""

    __tablename__ = "animal_sightings"

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


class Achievement(Base):
    """An achievement that can be awarded to a user."""

    __tablename__ = "achievements"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    criteria = Column(Text)
    icon_url = Column(String(512))
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    users = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """Link table recording when a user earned an achievement."""

    __tablename__ = "user_achievements"

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
    achievement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
    )
    awarded_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="users")

"""User domain models."""

import uuid

from sqlalchemy import Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


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
    # Allow extra room for bcrypt_sha256 and future password hashing schemes
    password_hash = Column(String(255), nullable=False)
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
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    favorite_zoo_links = relationship(
        "UserFavoriteZoo",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    favorite_animal_links = relationship(
        "UserFavoriteAnimal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    favorite_zoos = relationship(
        "Zoo",
        secondary="user_favorite_zoos",
        back_populates="favorited_by_users",
        viewonly=True,
    )
    favorite_animals = relationship(
        "Animal",
        secondary="user_favorite_animals",
        back_populates="favorited_by_users",
        viewonly=True,
    )

"""Animal and taxonomy models."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base
from .imagery import Image, SOURCE_ORDER


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


class ClassName(Base):
    """Taxonomic class name in German and English."""

    __tablename__ = "klasse_names"

    klasse = Column(Integer, primary_key=True)
    name_de = Column(Text)
    name_en = Column(Text)


class OrderName(Base):
    """Taxonomic order name in German and English."""

    __tablename__ = "ordnung_names"

    ordnung = Column(Integer, primary_key=True)
    name_de = Column(Text)
    name_en = Column(Text)


class FamilyName(Base):
    """Taxonomic family name in German and English."""

    __tablename__ = "familie_names"

    familie = Column(Integer, primary_key=True)
    name_de = Column(Text)
    name_en = Column(Text)


class Animal(Base):
    """An animal that can belong to a category and appear in zoos."""

    __tablename__ = "animals"
    __table_args__ = (
        CheckConstraint("zoo_count >= 0"),
        CheckConstraint(
            "parent_art IS NULL OR parent_art <> art",
            name="ck_animals_parent_not_self",
        ),
        Index("idx_animals_slug", "slug", unique=True),
        UniqueConstraint("art", name="idx_animals_art"),
        Index("idx_animals_parent_art", "parent_art"),
        Index("idx_animals_klasse", "klasse"),
        Index("idx_animals_ordnung", "ordnung"),
        Index("idx_animals_familie", "familie"),
        Index("idx_animals_klasse_ordnung", "klasse", "ordnung"),
        Index("idx_animals_ordnung_familie", "ordnung", "familie"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    scientific_name = Column(String(255))
    slug = Column(String(255), nullable=False)
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    description = Column(Text)
    description_de = Column(Text)
    description_en = Column(Text)
    conservation_state = Column(Text)
    name_fallback = Column(Text)
    name_en = Column(String(255), nullable=False)
    name_de = Column(Text)
    art = Column(Text)
    english_label = Column(Text)
    german_label = Column(Text)
    latin_name = Column(Text)
    parent_art = Column(
        Text,
        ForeignKey(
            "animals.art",
            name="fk_animals_parent_art",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    klasse = Column(Integer, ForeignKey("klasse_names.klasse"))
    ordnung = Column(Integer, ForeignKey("ordnung_names.ordnung"))
    familie = Column(Integer, ForeignKey("familie_names.familie"))
    taxon_rank = Column(Text)
    zoo_count = Column(Integer, nullable=False, default=0, server_default="0")
    default_image_url = Column(Text)
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
    klasse_name = relationship("ClassName")
    ordnung_name = relationship("OrderName")
    familie_name = relationship("FamilyName")
    images = relationship(
        "Image",
        back_populates="animal",
        order_by=(SOURCE_ORDER, Image.mid),
    )
    favorite_user_links = relationship("UserFavoriteAnimal", back_populates="animal")
    favorited_by_users = relationship(
        "User",
        secondary="user_favorite_animals",
        back_populates="favorite_animals",
        viewonly=True,
    )
    parent = relationship(
        "Animal",
        back_populates="subspecies",
        foreign_keys=[parent_art],
        remote_side=[art],
        uselist=False,
    )
    subspecies = relationship(
        "Animal",
        back_populates="parent",
    )


Index(
    "idx_animal_popularity",
    text("zoo_count DESC"),
    text("name_en ASC"),
    text("id ASC"),
)

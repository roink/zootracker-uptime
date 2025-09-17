"""SQLAlchemy ORM models for the Zoo Tracker application."""

from sqlalchemy import (
    Boolean,
    Column,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    DECIMAL,
    Integer,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
    case,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship, validates
from .database import engine

if engine.dialect.name == "sqlite":
    LocationType = Text
    WKTElement = None
else:
    from geoalchemy2 import Geography, WKTElement

    LocationType = Geography(geometry_type="POINT", srid=4326)
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
    # bcrypt hashes are ~60 characters
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


class ContinentName(Base):
    """Localized continent names."""

    __tablename__ = "continent_names"

    id = Column(Integer, primary_key=True)
    name_de = Column(Text, unique=True, nullable=False)
    name_en = Column(Text)

    countries = relationship("CountryName", back_populates="continent")
    zoos = relationship("Zoo", back_populates="continent")


class CountryName(Base):
    """Localized country names grouped by continent."""

    __tablename__ = "country_names"

    id = Column(Integer, primary_key=True)
    name_de = Column(Text, unique=True, nullable=False)
    name_en = Column(Text)
    continent_id = Column(Integer, ForeignKey("continent_names.id"))

    continent = relationship("ContinentName", back_populates="countries")
    zoos = relationship("Zoo", back_populates="country")


class Zoo(Base):
    """A zoo location that can be visited."""

    __tablename__ = "zoos"
    __table_args__ = (
        CheckConstraint("animal_count >= 0"),
        Index("idx_zoos_location_gist", "location", postgresql_using="gist"),
        Index("idx_zoos_slug", "slug", unique=True),
        Index(
            "idx_zoos_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "idx_zoos_city_trgm",
            "city",
            postgresql_using="gin",
            postgresql_ops={"city": "gin_trgm_ops"},
        ),
        Index("idx_zoos_country_id", "country_id"),
        Index("idx_zoos_continent_id", "continent_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    address = Column(Text)
    latitude = Column(DECIMAL(9, 6))
    longitude = Column(DECIMAL(9, 6))
    # Keep the default `spatial_index=True` so GeoAlchemy2 creates a GiST
    # index automatically.
    location = Column(LocationType)
    continent_id = Column(Integer, ForeignKey("continent_names.id"))
    country_id = Column(Integer, ForeignKey("country_names.id"))
    city = Column(Text)
    official_website = Column(Text)
    wikipedia_de = Column(Text)
    wikipedia_en = Column(Text)
    description_de = Column(Text)
    description_en = Column(Text)
    image_url = Column(String(512))
    animal_count = Column(Integer, nullable=False, default=0, server_default="0")
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
    continent = relationship("ContinentName", back_populates="zoos")
    country = relationship("CountryName", back_populates="zoos")

    @validates("latitude", "longitude")
    def _sync_location(self, key, value):
        lat = value if key == "latitude" else self.latitude
        lon = value if key == "longitude" else self.longitude
        if (
            engine.dialect.name == "postgresql"
            and lat is not None
            and lon is not None
            and WKTElement is not None
        ):
            # direct dictionary assignment bypasses validation on "location"
            self.__dict__["location"] = WKTElement(
                f"POINT({float(lon)} {float(lat)})", srid=4326
            )
        return value

    @validates("location")
    def _no_user_location(self, key, value):
        raise ValueError("location is managed automatically; set latitude and longitude instead")


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


class Image(Base):
    """Image metadata for an animal sourced from Wikimedia."""

    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint(
            "source IN ('WIKIDATA_P18','WIKI_LEAD_DE','WIKI_LEAD_EN')"
        ),
        Index("idx_images_animal_id", "animal_id"),
        Index("idx_images_sha1", "sha1"),
        Index("idx_images_source", "source"),
    )

    # Commons MediaInfo ID ("M" + file page ID); stable across renames
    mid = Column(String(32), primary_key=True)
    animal_id = Column(
        UUID(as_uuid=True), ForeignKey("animals.id", ondelete="CASCADE"), nullable=False
    )
    commons_title = Column(Text)
    commons_page_url = Column(Text)
    original_url = Column(Text, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha1 = Column(String(40), nullable=False)
    mime = Column(Text, nullable=False)
    uploaded_at = Column(DateTime(timezone=True))
    uploader = Column(Text)
    title = Column(Text)
    artist_raw = Column(Text)
    artist_plain = Column(Text)
    license = Column(Text)
    license_short = Column(Text)
    license_url = Column(Text)
    attribution_required = Column(Boolean)
    usage_terms = Column(Text)
    credit_line = Column(Text)
    source = Column(String(20), nullable=False)
    retrieved_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    animal = relationship("Animal", back_populates="images")
    variants = relationship(
        "ImageVariant",
        back_populates="image",
        cascade="all, delete-orphan",
        order_by="ImageVariant.width",
    )


class ImageVariant(Base):
    """Stored thumbnail variants for a Commons image."""

    __tablename__ = "image_variants"

    mid = Column(
        String(32), ForeignKey("images.mid", ondelete="CASCADE"), primary_key=True
    )
    width = Column(Integer, primary_key=True)
    height = Column(Integer, nullable=False)
    thumb_url = Column(Text, nullable=False)

    image = relationship("Image", back_populates="variants")


SOURCE_ORDER = case(
    (Image.source == "WIKIDATA_P18", 0),
    (Image.source == "WIKI_LEAD_EN", 1),
    (Image.source == "WIKI_LEAD_DE", 2),
    else_=3,
)


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
        Index("idx_animals_slug", "slug", unique=True),
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


class ZooAnimal(Base):
    """Association table linking animals to zoos."""

    __tablename__ = "zoo_animals"
    __table_args__ = (
        Index("idx_zooanimal_zoo_id", "zoo_id"),
        Index("idx_zooanimal_animal_id", "animal_id"),
    )

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

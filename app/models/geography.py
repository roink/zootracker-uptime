"""Geographic and location models."""

import uuid

from geoalchemy2 import Geography, WKTElement
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from ..database import Base


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
    location = Column(Geography(geometry_type="POINT", srid=4326))
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
    favorite_user_links = relationship("UserFavoriteZoo", back_populates="zoo")
    favorited_by_users = relationship(
        "User",
        secondary="user_favorite_zoos",
        back_populates="favorite_zoos",
        viewonly=True,
    )

    @validates("latitude", "longitude")
    def _sync_location(self, key, value):
        lat = value if key == "latitude" else self.latitude
        lon = value if key == "longitude" else self.longitude
        if lat is not None and lon is not None:
            # direct dictionary assignment bypasses validation on "location"
            self.__dict__["location"] = WKTElement(
                f"POINT({float(lon)} {float(lat)})", srid=4326
            )
        return value

    @validates("location")
    def _no_user_location(self, key, value):
        raise ValueError("location is managed automatically; set latitude and longitude instead")

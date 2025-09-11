"""Pydantic schemas used for request and response models."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field, constr


class UserCreate(BaseModel):
    """Schema for user registration."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., min_length=1, max_length=255)
    # Enforce stronger passwords by requiring at least 8 characters
    password: str = Field(..., min_length=8, max_length=255)

    model_config = ConfigDict(extra="forbid")


class UserRead(BaseModel):
    """Schema returned when reading user information."""
    id: UUID
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Token(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str
    user_id: Optional[UUID] = None

    model_config = ConfigDict(extra="forbid")


class ZooRead(BaseModel):
    """Basic information about a zoo."""
    id: UUID
    name: str
    address: Optional[str] = None
    city: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooDetail(BaseModel):
    """Full information about a zoo including location and description."""
    id: UUID
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description_de: Optional[str] = None
    description_en: Optional[str] = None
    distance_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooSearchResult(BaseModel):
    """Slim result item for zoo searches."""
    id: UUID
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    distance_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalRead(BaseModel):
    """Minimal representation of an animal."""
    id: UUID
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    zoo_count: int = 0

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalListItem(BaseModel):
    """Detailed fields returned by the animals list endpoint."""

    id: UUID
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    category: Optional[str] = None
    description_de: Optional[str] = None
    iucn_conservation_status: Optional[str] = None
    default_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ImageVariant(BaseModel):
    """Represents a stored thumbnail for an animal image."""

    width: int
    height: int
    thumb_url: str

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ImageRead(BaseModel):
    """Image information including available thumbnail variants."""
    mid: str
    original_url: str
    variants: list[ImageVariant] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ImageAttribution(BaseModel):
    """Full image metadata used for attribution."""

    mid: str
    original_url: str
    commons_page_url: Optional[str] = None
    commons_title: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    credit_line: Optional[str] = None
    attribution_required: Optional[bool] = None
    variants: list[ImageVariant] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooVisitCreate(BaseModel):
    """Input data required to log a zoo visit."""
    zoo_id: UUID
    visit_date: date
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class ZooVisitRead(BaseModel):
    """Zoo visit data returned from the API."""
    id: UUID
    zoo_id: UUID
    visit_date: date
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalSightingCreate(BaseModel):
    """Input data for recording an animal sighting."""
    zoo_id: UUID
    animal_id: UUID
    user_id: UUID
    sighting_datetime: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class AnimalSightingRead(BaseModel):
    """Full representation of an animal sighting."""
    id: UUID
    zoo_id: UUID
    animal_id: UUID
    animal_name_de: Optional[str] = None
    animal_name_en: Optional[str] = None
    zoo_name: Optional[str] = None
    sighting_datetime: datetime
    notes: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooVisitUpdate(BaseModel):
    """Fields allowed when updating a zoo visit."""

    visit_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class AnimalSightingUpdate(BaseModel):
    """Fields allowed when updating an animal sighting."""

    zoo_id: Optional[UUID] = None
    animal_id: Optional[UUID] = None
    sighting_datetime: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    photo_url: Optional[str] = Field(default=None, max_length=512)

    model_config = ConfigDict(extra="forbid")


class AnimalDetail(BaseModel):
    """Detailed information about an animal including available zoos."""

    id: UUID
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    category: Optional[str] = None
    description_de: Optional[str] = None
    description_en: Optional[str] = None
    iucn_conservation_status: Optional[str] = None
    taxon_rank: Optional[str] = None
    klasse_name_de: Optional[str] = None
    klasse_name_en: Optional[str] = None
    ordnung_name_de: Optional[str] = None
    ordnung_name_en: Optional[str] = None
    familie_name_de: Optional[str] = None
    familie_name_en: Optional[str] = None
    default_image_url: Optional[str] = None
    images: list[ImageRead] = Field(default_factory=list)
    # include full zoo details with distance information
    zoos: list[ZooDetail] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SearchResults(BaseModel):
    """Combined search result lists for zoos and animals."""

    zoos: list[ZooRead] = Field(default_factory=list)
    animals: list[AnimalRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ContactMessage(BaseModel):
    """Input for a contact form submission."""
    name: constr(min_length=1, max_length=100, pattern=r"^[A-Za-z\s-]+$")
    email: EmailStr
    message: constr(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class Count(BaseModel):
    """Simple response model holding a numeric count."""

    count: int

    model_config = ConfigDict(extra="forbid")


class Visited(BaseModel):
    """Boolean flag indicating whether a zoo was visited."""

    visited: bool

    model_config = ConfigDict(extra="forbid")

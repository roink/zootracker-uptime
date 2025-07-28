"""Pydantic schemas used for request and response models."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UserCreate(BaseModel):
    """Schema for user registration."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)

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

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooDetail(BaseModel):
    """Full information about a zoo including location and description."""
    id: UUID
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalRead(BaseModel):
    """Minimal representation of an animal."""
    id: UUID
    common_name: str

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
    sighting_datetime: datetime
    notes: Optional[str] = None
    photo_url: Optional[str] = None

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
    common_name: str
    scientific_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    zoos: list[ZooRead] = []

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SearchResults(BaseModel):
    """Combined search result lists for zoos and animals."""

    zoos: list[ZooRead] = []
    animals: list[AnimalRead] = []

    model_config = ConfigDict(from_attributes=True, extra="forbid")

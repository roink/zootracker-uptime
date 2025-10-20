"""Pydantic schemas used for request and response models."""

from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field, constr, field_validator, model_validator


class UserCreate(BaseModel):
    """Schema for user registration."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., min_length=1, max_length=255)
    # Enforce stronger passwords by requiring at least 8 characters
    password: str = Field(..., min_length=8, max_length=255)
    accepted_data_protection: Literal[True] = Field(
        ..., alias="acceptedDataProtection", description="User accepted privacy terms."
    )
    privacy_consent_version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        alias="privacyConsentVersion",
        description="Version identifier of the accepted privacy notice.",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UserRead(BaseModel):
    """Schema returned when reading user information."""
    id: UUID
    name: str
    email: EmailStr
    email_verified: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Message(BaseModel):
    """Simple envelope used for status responses."""

    detail: str

    model_config = ConfigDict(extra="forbid")


class EmailVerificationRequest(BaseModel):
    """Payload accepted by the email verification endpoint."""

    uid: UUID | None = None
    email: EmailStr | None = None
    token: str | None = None
    code: constr(min_length=6, max_length=8, pattern=r"^\d{6,8}$") | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("token", "code", mode="before")
    def _strip_values(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _ensure_fields(self):
        if not (self.uid or self.email):
            raise ValueError("identifier_required")
        if not (self.token or self.code):
            raise ValueError("token_or_code_required")
        return self


class VerificationResendRequest(BaseModel):
    """Payload accepted by the anonymous verification resend endpoint."""

    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class PasswordResetRequest(BaseModel):
    """Payload accepted by the anonymous password reset endpoint."""

    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class PasswordResetConfirm(BaseModel):
    """Payload accepted by the password reset confirmation endpoint."""

    token: str = Field(..., min_length=1, max_length=512)
    password: constr(min_length=8, max_length=255)
    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=255,
        alias="confirmPassword",
        description="Confirmation of the new password.",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("token", mode="before")
    def _strip_token(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("password_mismatch")
        return self


class Token(BaseModel):
    """Authentication token response."""

    access_token: str
    token_type: str
    expires_in: int
    user_id: Optional[UUID] = None
    email_verified: bool = False

    model_config = ConfigDict(extra="forbid")


class ZooRead(BaseModel):
    """Basic information about a zoo."""
    id: UUID
    slug: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooDetail(BaseModel):
    """Full information about a zoo including location and description."""
    id: UUID
    slug: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description_de: Optional[str] = None
    description_en: Optional[str] = None
    distance_km: Optional[float] = None
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooSearchResult(BaseModel):
    """Slim result item for zoo searches."""

    id: UUID
    slug: str
    name: str
    city: Optional[str] = None
    country_name_de: Optional[str] = None
    country_name_en: Optional[str] = None
    distance_km: Optional[float] = None
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooSearchPage(BaseModel):
    """Paginated response returned by the zoo search endpoint."""

    items: list[ZooSearchResult]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(extra="forbid")


class FavoriteStatus(BaseModel):
    """Response envelope describing whether an entity is favorited."""

    favorite: bool

    model_config = ConfigDict(extra="forbid")


class ZooMapPoint(BaseModel):
    """Minimal data required to plot zoos on the map."""

    id: UUID
    slug: str
    name: str
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalRead(BaseModel):
    """Minimal representation of an animal."""
    id: UUID
    slug: str
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    zoo_count: int = 0
    is_favorite: bool = False
    default_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalListItem(BaseModel):
    """Detailed fields returned by the animals list endpoint."""

    id: UUID
    slug: str
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    category: Optional[str] = None
    description_de: Optional[str] = None
    iucn_conservation_status: Optional[str] = None
    default_image_url: Optional[str] = None
    zoo_count: int = 0
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TaxonName(BaseModel):
    """Represents a taxonomic name with German and English labels."""

    id: int
    name_de: Optional[str] = None
    name_en: Optional[str] = None

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
    sighting_datetime: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: Optional[str]):
        """Trim whitespace and collapse empty notes to ``None``."""
        if value is None:
            return None
        value = str(value).strip()
        return value or None


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


class AnimalSightingPage(BaseModel):
    """Paginated response with animal sightings."""

    items: list[AnimalSightingRead]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(extra="forbid")


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

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: Optional[str]):
        """Trim whitespace and collapse empty notes to ``None``."""
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class AnimalRelation(BaseModel):
    """Lightweight reference to a related animal used for taxonomy links."""

    slug: str
    name_en: Optional[str] = None
    name_de: Optional[str] = None
    scientific_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalDetail(BaseModel):
    """Detailed information about an animal including available zoos."""

    id: UUID
    slug: str
    name_en: str
    scientific_name: Optional[str] = None
    name_de: Optional[str] = None
    category: Optional[str] = None
    description_de: Optional[str] = None
    description_en: Optional[str] = None
    iucn_conservation_status: Optional[str] = None
    taxon_rank: Optional[str] = None
    class_id: Optional[int] = None
    class_name_de: Optional[str] = None
    class_name_en: Optional[str] = None
    order_id: Optional[int] = None
    order_name_de: Optional[str] = None
    order_name_en: Optional[str] = None
    family_id: Optional[int] = None
    family_name_de: Optional[str] = None
    family_name_en: Optional[str] = None
    default_image_url: Optional[str] = None
    images: list[ImageRead] = Field(default_factory=list)
    # include full zoo details with distance information
    zoos: list[ZooDetail] = Field(default_factory=list)
    is_favorite: bool = False
    parent: Optional[AnimalRelation] = None
    subspecies: list[AnimalRelation] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SiteSummary(BaseModel):
    """Aggregate counters shown on the public landing page."""

    species: int = 0
    zoos: int = 0
    countries: int = 0
    sightings: int = 0

    model_config = ConfigDict(extra="forbid")


class PopularAnimal(BaseModel):
    """Preview entry for a popular animal on the landing page."""

    id: UUID
    slug: str
    name_en: str
    name_de: Optional[str] = None
    scientific_name: Optional[str] = None
    zoo_count: Optional[int] = None
    iucn_conservation_status: Optional[str] = None
    default_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ContactMessage(BaseModel):
    """Input for a contact form submission."""

    name: constr(min_length=1, max_length=100)
    email: EmailStr
    message: constr(min_length=10, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class Count(BaseModel):
    """Simple response model holding a numeric count."""

    count: int

    model_config = ConfigDict(extra="forbid")


class Visited(BaseModel):
    """Boolean flag indicating whether a zoo was visited."""

    visited: bool

    model_config = ConfigDict(extra="forbid")


class LocationEstimate(BaseModel):
    """Estimated geographic coordinates derived from network information."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(extra="forbid")

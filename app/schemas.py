"""Pydantic schemas used for request and response models."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError


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


VerificationCode = Annotated[
    str, StringConstraints(min_length=6, max_length=8, pattern=r"^\d{6,8}$")
]

StrongPassword = Annotated[str, StringConstraints(min_length=8, max_length=255)]
ShortName = Annotated[str, StringConstraints(min_length=1, max_length=100)]
ContactBody = Annotated[str, StringConstraints(min_length=10, max_length=2000)]


class EmailVerificationRequest(BaseModel):
    """Payload accepted by the email verification endpoint."""

    uid: str | None = None
    email: EmailStr | None = None
    token: str | None = None
    code: VerificationCode | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("uid", mode="before")
    def _coerce_uid(cls, value: str | UUID | None) -> str | None:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @field_validator("token", "code", mode="before")
    def _strip_values(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _ensure_fields(self) -> "EmailVerificationRequest":
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
    password: StrongPassword
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
    def _passwords_match(self) -> "PasswordResetConfirm":
        if self.password != self.confirm_password:
            raise PydanticCustomError(
                "password_mismatch",
                "password_mismatch",
            )
        return self


class PasswordResetTokenStatus(BaseModel):
    """Response describing the status of a password reset token."""

    status: Literal["valid", "invalid", "consumed", "expired", "rate_limited"]
    detail: str | None = None

    model_config = ConfigDict(extra="forbid")


class Token(BaseModel):
    """Authentication token response."""

    access_token: str
    token_type: str
    expires_in: int
    user_id: UUID | None = None
    email_verified: bool = False

    model_config = ConfigDict(extra="forbid")


class ZooRead(BaseModel):
    """Basic information about a zoo."""
    id: UUID
    slug: str
    name: str
    address: str | None = None
    city: str | None = None
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooDetail(BaseModel):
    """Full information about a zoo including location and description."""
    id: UUID
    slug: str
    name: str
    address: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description_de: str | None = None
    description_en: str | None = None
    distance_km: float | None = None
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooSearchResult(BaseModel):
    """Slim result item for zoo searches."""

    id: UUID
    slug: str
    name: str
    city: str | None = None
    country_name_de: str | None = None
    country_name_en: str | None = None
    distance_km: float | None = None
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
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalRead(BaseModel):
    """Minimal representation of an animal."""

    id: UUID
    slug: str
    name_en: str
    scientific_name: str | None = None
    name_de: str | None = None
    zoo_count: int = 0
    is_favorite: bool = False
    default_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooAnimalFacetOption(BaseModel):
    """Facet entry describing a taxonomic classification option."""

    id: int
    name_de: str | None = None
    name_en: str | None = None
    count: int = 0

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooAnimalFacets(BaseModel):
    """Grouped facet metadata for zoo animal listings."""

    classes: list[ZooAnimalFacetOption] = Field(default_factory=list)
    orders: list[ZooAnimalFacetOption] = Field(default_factory=list)
    families: list[ZooAnimalFacetOption] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooAnimalListItem(BaseModel):
    """Animal entry enriched with favorite and seen flags for a zoo."""

    id: UUID
    slug: str
    name_en: str | None = None
    scientific_name: str | None = None
    name_de: str | None = None
    zoo_count: int = 0
    is_favorite: bool = False
    default_image_url: str | None = None
    seen: bool = False
    klasse: int | None = None
    ordnung: int | None = None
    familie: int | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooAnimalListing(BaseModel):
    """Response payload for animals available at a zoo."""

    items: list[ZooAnimalListItem] = Field(default_factory=list)
    total: int = 0
    available_total: int = 0
    inventory: list[ZooAnimalListItem] = Field(default_factory=list)
    facets: ZooAnimalFacets = Field(default_factory=ZooAnimalFacets)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalListItem(BaseModel):
    """Detailed fields returned by the animals list endpoint."""

    id: UUID
    slug: str
    name_en: str
    scientific_name: str | None = None
    name_de: str | None = None
    category: str | None = None
    description_de: str | None = None
    iucn_conservation_status: str | None = None
    default_image_url: str | None = None
    zoo_count: int = 0
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalSearchPage(BaseModel):
    """Paginated response for animal search results."""

    items: list[AnimalListItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0

    model_config = ConfigDict(extra="forbid")


class TaxonName(BaseModel):
    """Represents a taxonomic name with German and English labels."""

    id: int
    name_de: str | None = None
    name_en: str | None = None

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
    commons_page_url: str | None = None
    commons_title: str | None = None
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    credit_line: str | None = None
    attribution_required: bool | None = None
    variants: list[ImageVariant] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ZooVisitCreate(BaseModel):
    """Input data required to log a zoo visit."""
    zoo_id: UUID
    visit_date: date
    notes: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class ZooVisitRead(BaseModel):
    """Zoo visit data returned from the API."""
    id: UUID
    zoo_id: UUID
    visit_date: date
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalSightingCreate(BaseModel):
    """Input data for recording an animal sighting."""
    zoo_id: UUID
    animal_id: UUID
    sighting_datetime: datetime
    notes: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
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
    animal_name_de: str | None = None
    animal_name_en: str | None = None
    zoo_name: str | None = None
    sighting_datetime: datetime
    notes: str | None = None
    photo_url: str | None = None
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

    visit_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class AnimalSightingUpdate(BaseModel):
    """Fields allowed when updating an animal sighting."""

    zoo_id: UUID | None = None
    animal_id: UUID | None = None
    sighting_datetime: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    photo_url: str | None = Field(default=None, max_length=512)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes", mode="before")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        """Trim whitespace and collapse empty notes to ``None``."""
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class AnimalRelation(BaseModel):
    """Lightweight reference to a related animal used for taxonomy links."""

    slug: str
    name_en: str | None = None
    name_de: str | None = None
    scientific_name: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AnimalDetail(BaseModel):
    """Detailed information about an animal including available zoos."""

    id: UUID
    slug: str
    name_en: str
    scientific_name: str | None = None
    name_de: str | None = None
    category: str | None = None
    description_de: str | None = None
    description_en: str | None = None
    iucn_conservation_status: str | None = None
    taxon_rank: str | None = None
    class_id: int | None = None
    class_name_de: str | None = None
    class_name_en: str | None = None
    order_id: int | None = None
    order_name_de: str | None = None
    order_name_en: str | None = None
    family_id: int | None = None
    family_name_de: str | None = None
    family_name_en: str | None = None
    default_image_url: str | None = None
    images: list[ImageRead] = Field(default_factory=list)
    # include full zoo details with distance information
    zoos: list[ZooDetail] = Field(default_factory=list)
    is_favorite: bool = False
    parent: AnimalRelation | None = None
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
    name_de: str | None = None
    scientific_name: str | None = None
    zoo_count: int | None = None
    iucn_conservation_status: str | None = None
    default_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ContactMessage(BaseModel):
    """Input for a contact form submission."""

    name: ShortName
    email: EmailStr
    message: ContactBody

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

    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(extra="forbid")

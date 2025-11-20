"""Imagery models for Wikimedia assets."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    case,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


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
    s3_path = Column(Text)

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
    s3_path = Column(Text)

    image = relationship("Image", back_populates="variants")


SOURCE_ORDER = case(
    (Image.source == "WIKIDATA_P18", 0),
    (Image.source == "WIKI_LEAD_EN", 1),
    (Image.source == "WIKI_LEAD_DE", 2),
    else_=3,
)

"""Association tables linking domain models."""

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


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


class UserFavoriteZoo(Base):
    """Association table mapping users to zoos they marked as favorites."""

    __tablename__ = "user_favorite_zoos"
    __table_args__ = (
        Index("idx_userfavoritezoo_user_id", "user_id"),
        Index("idx_userfavoritezoo_zoo_id", "zoo_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    zoo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("zoos.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user = relationship("User", back_populates="favorite_zoo_links")
    zoo = relationship("Zoo", back_populates="favorite_user_links")


class UserFavoriteAnimal(Base):
    """Association table mapping users to animals they marked as favorites."""

    __tablename__ = "user_favorite_animals"
    __table_args__ = (
        Index("idx_userfavoriteanimal_user_id", "user_id"),
        Index("idx_userfavoriteanimal_animal_id", "animal_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    animal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("animals.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user = relationship("User", back_populates="favorite_animal_links")
    animal = relationship("Animal", back_populates="favorite_user_links")

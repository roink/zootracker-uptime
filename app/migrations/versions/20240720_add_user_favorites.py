"""Add tables for storing user favorites."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20240720_add_user_favorites"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create association tables mapping users to favorite zoos and animals."""

    op.create_table(
        "user_favorite_zoos",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zoo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zoo_id"], ["zoos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "zoo_id"),
    )
    op.create_index(
        "idx_userfavoritezoo_user_id", "user_favorite_zoos", ["user_id"], unique=False
    )
    op.create_index(
        "idx_userfavoritezoo_zoo_id", "user_favorite_zoos", ["zoo_id"], unique=False
    )

    op.create_table(
        "user_favorite_animals",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["animal_id"], ["animals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "animal_id"),
    )
    op.create_index(
        "idx_userfavoriteanimal_user_id",
        "user_favorite_animals",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_userfavoriteanimal_animal_id",
        "user_favorite_animals",
        ["animal_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the association tables for user favorites."""

    op.drop_index("idx_userfavoriteanimal_animal_id", table_name="user_favorite_animals")
    op.drop_index("idx_userfavoriteanimal_user_id", table_name="user_favorite_animals")
    op.drop_table("user_favorite_animals")
    op.drop_index("idx_userfavoritezoo_zoo_id", table_name="user_favorite_zoos")
    op.drop_index("idx_userfavoritezoo_user_id", table_name="user_favorite_zoos")
    op.drop_table("user_favorite_zoos")

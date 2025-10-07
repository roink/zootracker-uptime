"""Add optional notes column to animal_sightings."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240722_add_sighting_notes_column"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "animal_sightings",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("animal_sightings", "notes")

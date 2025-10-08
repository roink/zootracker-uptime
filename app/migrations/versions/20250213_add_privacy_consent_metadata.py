"""add privacy consent metadata to users"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250213_add_privacy_consent_metadata"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("privacy_consent_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("privacy_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("privacy_consent_ip", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "privacy_consent_ip")
    op.drop_column("users", "privacy_consent_at")
    op.drop_column("users", "privacy_consent_version")

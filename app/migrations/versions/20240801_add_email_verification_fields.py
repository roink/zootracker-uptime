"""add email verification fields to users"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240801_add_email_verification_fields"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verify_token_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verify_code_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "verify_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "verify_attempts",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_verify_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_verify_sent_at")
    op.drop_column("users", "verify_attempts")
    op.drop_column("users", "verify_token_expires_at")
    op.drop_column("users", "verify_code_hash")
    op.drop_column("users", "verify_token_hash")
    op.drop_column("users", "email_verified_at")

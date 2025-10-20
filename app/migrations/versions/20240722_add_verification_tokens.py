"""create verification token table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20240722_add_verification_tokens"
down_revision = "20240715_add_animal_popularity_index"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_tokens_user_purpose",
        "verification_tokens",
        ["user_id", "purpose"],
    )
    op.create_index(
        "ix_verification_tokens_active",
        "verification_tokens",
        ["user_id", "purpose", "consumed_at"],
    )

    op.execute(
        """
        INSERT INTO verification_tokens (
            id,
            user_id,
            purpose,
            token_hash,
            code_hash,
            expires_at,
            created_at,
            consumed_at
        )
        SELECT
            gen_random_uuid(),
            id,
            'email_verification',
            verify_token_hash,
            verify_code_hash,
            verify_token_expires_at,
            COALESCE(last_verify_sent_at, timezone('utc', now())),
            CASE
                WHEN email_verified_at IS NOT NULL THEN email_verified_at
                ELSE NULL
            END
        FROM users
        WHERE verify_token_hash IS NOT NULL
        """
    )

    op.drop_column("users", "verify_token_hash")
    op.drop_column("users", "verify_code_hash")
    op.drop_column("users", "verify_token_expires_at")
    op.drop_column("users", "verify_attempts")
    op.drop_column("users", "last_verify_sent_at")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_verify_sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("verify_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verify_code_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verify_token_hash", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (user_id)
                user_id,
                token_hash,
                code_hash,
                expires_at,
                created_at
            FROM verification_tokens
            WHERE purpose = 'email_verification'
            ORDER BY user_id, created_at DESC
        )
        UPDATE users
        SET
            verify_token_hash = latest.token_hash,
            verify_code_hash = latest.code_hash,
            verify_token_expires_at = latest.expires_at,
            last_verify_sent_at = latest.created_at,
            verify_attempts = CASE
                WHEN latest.token_hash IS NULL THEN 0
                ELSE 1
            END
        FROM latest
        WHERE users.id = latest.user_id
        """
    )

    op.drop_index("ix_verification_tokens_active", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_user_purpose", table_name="verification_tokens")
    op.drop_table("verification_tokens")

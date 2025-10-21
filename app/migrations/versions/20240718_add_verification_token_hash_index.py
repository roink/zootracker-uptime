from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240718_add_verification_token_hash_index"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    index_name = "ix_verification_tokens_token_hash"
    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                ON verification_tokens (token_hash)
                """
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(
            sa.text(
                f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON verification_tokens (token_hash)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    index_name = "ix_verification_tokens_token_hash"
    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))

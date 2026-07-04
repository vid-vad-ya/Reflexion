"""add github profile fields and widen access token

Revision ID: a3f8b2c1d4e5
Revises: 032881aa361a
Create Date: 2026-06-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a3f8b2c1d4e5'
down_revision: Union[str, None] = '032881aa361a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add github_username column
    op.add_column(
        'user',
        sa.Column('github_username', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    )
    # Add github_avatar_url column
    op.add_column(
        'user',
        sa.Column('github_avatar_url', sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
    )
    # Widen github_access_token from 512 to 1024 for Fernet-encrypted tokens
    op.alter_column(
        'user',
        'github_access_token',
        existing_type=sqlmodel.sql.sqltypes.AutoString(length=512),
        type_=sqlmodel.sql.sqltypes.AutoString(length=1024),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Shrink github_access_token back to 512
    op.alter_column(
        'user',
        'github_access_token',
        existing_type=sqlmodel.sql.sqltypes.AutoString(length=1024),
        type_=sqlmodel.sql.sqltypes.AutoString(length=512),
        existing_nullable=True,
    )
    # Drop github_avatar_url column
    op.drop_column('user', 'github_avatar_url')
    # Drop github_username column
    op.drop_column('user', 'github_username')

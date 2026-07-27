"""add local_path clone_status project_summary to repository

Revision ID: b1c2d3e4f5a6
Revises: a3f8b2c1d4e5
Create Date: 2026-07-27 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a3f8b2c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add local_path column — stores the local filesystem path of the cloned workspace
    op.add_column(
        'repository',
        sa.Column('local_path', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    )
    # Add clone_status column — lifecycle state of workspace clone
    op.add_column(
        'repository',
        sa.Column('clone_status', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True, server_default='pending'),
    )
    # Add project_summary column — persisted structured ProjectSummary JSON from RepositoryAnalyzer
    op.add_column(
        'repository',
        sa.Column('project_summary', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('repository', 'project_summary')
    op.drop_column('repository', 'clone_status')
    op.drop_column('repository', 'local_path')

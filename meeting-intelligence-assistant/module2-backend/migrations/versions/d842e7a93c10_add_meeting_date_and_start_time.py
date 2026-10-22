"""Add meeting date and start time

Revision ID: d842e7a93c10
Revises: fa3435597ac4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d842e7a93c10"
down_revision: Union[str, Sequence[str], None] = "fa3435597ac4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("meeting_date", sa.Date(), nullable=True))
    op.add_column("meetings", sa.Column("meeting_start_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "meeting_start_time")
    op.drop_column("meetings", "meeting_date")

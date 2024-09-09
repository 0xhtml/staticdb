"""create initial tables api and api_data

Revision ID: 7c5eb339b87d
Revises:
Create Date: 2024-09-09 15:15:23.751502

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c5eb339b87d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api",
        sa.Column("id", sa.Uuid, nullable=False, primary_key=True),
    )
    op.create_table(
        "api_data",
        sa.Column(
            "id", sa.Integer, nullable=False, primary_key=True, autoincrement=True
        ),
        sa.Column("api", sa.Uuid, nullable=False),
        sa.Column("time", sa.DateTime, nullable=False),
        sa.Column("data", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("api_data")
    op.drop_table("api")

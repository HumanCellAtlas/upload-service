"""add owner emails to upload area

Revision ID: 3019f2fe22e3
Revises: 2c6910ed8cf6
Create Date: 2018-09-24 15:23:23.003390

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '3019f2fe22e3'
down_revision = '2c6910ed8cf6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('upload_area', sa.Column('owner_emails', JSONB, nullable=True))


def downgrade():
    op.drop_column('upload_area', 'owner_emails')

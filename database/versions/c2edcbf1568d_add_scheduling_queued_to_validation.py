"""add_scheduling_queued_to_validation

Revision ID: c2edcbf1568d
Revises: 7c4b17852829
Create Date: 2019-01-28 16:29:06.810398

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2edcbf1568d'
down_revision = '7c4b17852829'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE validation_event_status_enum ADD VALUE 'SCHEDULING_QUEUED';")
    op.alter_column('validation', 'job_id', nullable=True)


def downgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE validation_event_status_enum DROP VALUE 'SCHEDULING_QUEUED';")
    op.alter_column('validation', 'job_id', nullable=False)

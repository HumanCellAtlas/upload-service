"""Add failed status to notification

Revision ID: ec83721be9a8
Revises: 217fe1d22e4e
Create Date: 2019-01-15 15:26:51.703977

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ec83721be9a8'
down_revision = '217fe1d22e4e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE notification_status_enum ADD VALUE 'FAILED';")


def downgrade():
    # https://stackoverflow.com/questions/25811017/how-to-delete-an-enum-type-value-in-postgres
    # complexity of rollback is unnecessarily to introduce at the moment
    pass

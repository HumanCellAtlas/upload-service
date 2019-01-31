"""add state to upload area

Revision ID: 0f28d27dffea
Revises: 10c523521ee7
Create Date: 2018-12-13 12:38:12.635996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f28d27dffea'
down_revision = '1c7493144cbf'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE upload_status_enum ADD VALUE 'DELETION_QUEUED';")


def downgrade():
    # https://stackoverflow.com/questions/25811017/how-to-delete-an-enum-type-value-in-postgres
    # complexity of rollback is unnecessarily to introduce at the moment
    pass

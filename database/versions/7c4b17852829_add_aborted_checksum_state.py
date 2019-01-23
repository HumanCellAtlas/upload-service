"""add_aborted_checksum_state

Revision ID: 7c4b17852829
Revises: 107d830906b7
Create Date: 2019-01-23 16:28:52.590875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c4b17852829'
down_revision = '107d830906b7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE checksumming_status_enum ADD VALUE 'ABORTED';")


def downgrade():
    # https://stackoverflow.com/questions/25811017/how-to-delete-an-enum-type-value-in-postgres
    # complexity of rollback is unnecessarily to introduce at the moment
    pass

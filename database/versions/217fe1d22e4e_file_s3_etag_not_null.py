"""file_s3_etag_not_null

Revision ID: 217fe1d22e4e
Revises: 5ea5c9b56a3d
Create Date: 2019-01-08 10:02:43.497731

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '217fe1d22e4e'
down_revision = '5ea5c9b56a3d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE file ALTER COLUMN s3_etag SET NOT NULL;")


def downgrade():
    op.execute("ALTER TABLE file ALTER COLUMN s3_etag DROP NOT NULL;")

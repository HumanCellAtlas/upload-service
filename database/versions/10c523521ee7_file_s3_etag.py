"""file_s3_etag

Revision ID: 10c523521ee7
Revises: 22e0b6f6ad9f
Create Date: 2018-12-12 11:33:11.049644

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10c523521ee7'
down_revision = '22e0b6f6ad9f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE file ADD COLUMN s3_etag VARCHAR;")
    # Later we will make this column NOT NULL, but we need to populate it first.


def downgrade():
    op.execute("ALTER TABLE file DROP COLUMN s3_etag;")

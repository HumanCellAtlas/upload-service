"""move_csums_to_file

Revision ID: 107d830906b7
Revises: 1a948db96511
Create Date: 2019-01-21 15:28:28.779793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '107d830906b7'
down_revision = '1a948db96511'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE file ADD COLUMN checksums JSONB;")
    op.execute("UPDATE file "
               "SET checksums = checksum.checksums "
               "FROM checksum "
               "WHERE file.id = checksum.file_id;")
    op.execute("ALTER TABLE checksum DROP COLUMN checksums;")


def downgrade():
    op.execute("ALTER TABLE checksum ADD COLUMN checksums JSONB;")
    op.execute("UPDATE checksum "
               "SET checksums = file.checksums "
               "FROM file "
               "WHERE file.id = checksum.file_id;")
    op.execute("ALTER TABLE file DROP COLUMN checksums;")

"""upload_area_integer_pk

Revision ID: 5ea5c9b56a3d
Revises: 0f28d27dffea
Create Date: 2018-12-20 16:31:27.122579

"""
from alembic import op
import sqlalchemy as sainteger_pksinteger


# revision identifiers, used by Alembic.
revision = '5ea5c9b56a3d'
down_revision = '0f28d27dffea'
branch_labels = None
depends_on = None


def upgrade():
    """
    Change upload_area primary key to be integer sequence, and update any foreign keys that reference it.
    """

    # Upload Area
    op.execute("ALTER TABLE file DROP CONSTRAINT file_upload_area;")
    op.execute("ALTER TABLE upload_area DROP CONSTRAINT upload_area_pkey;")
    op.execute("ALTER TABLE upload_area RENAME COLUMN id TO uuid;")
    # reindex uuid
    op.execute("CREATE UNIQUE INDEX upload_area_uuid ON upload_area (uuid);")
    op.execute("ALTER TABLE upload_area ADD CONSTRAINT unique_uuid UNIQUE USING INDEX upload_area_uuid;")
    # add new primary key
    op.execute("ALTER TABLE upload_area ADD COLUMN id SERIAL PRIMARY KEY;")
    # update foreign keys pointing at upload_area_id
    op.execute("UPDATE file "
               "SET upload_area_id = upload_area.id "
               "FROM upload_area "
               "WHERE file.upload_area_id = upload_area.uuid;")
    op.execute("ALTER TABLE file "
               "ALTER COLUMN upload_area_id TYPE integer USING (upload_area_id::integer);")
    op.execute("ALTER TABLE file "
               "ADD CONSTRAINT file_upload_area FOREIGN KEY (upload_area_id) "
               "REFERENCES upload_area (id) ON DELETE CASCADE;")


def downgrade():
    # Upload Area
    op.execute("ALTER TABLE file DROP CONSTRAINT file_upload_area;")
    op.execute("ALTER TABLE upload_area DROP CONSTRAINT upload_area_pkey;")
    op.execute("ALTER TABLE upload_area DROP CONSTRAINT unique_uuid;")

    op.execute("ALTER TABLE file ALTER COLUMN upload_area_id TYPE varchar USING (upload_area_id::varchar);")
    op.execute("UPDATE file "
               "SET upload_area_id = upload_area.uuid "
               "FROM upload_area "
               "WHERE file.upload_area_id = upload_area.id::varchar;")

    op.execute("ALTER TABLE upload_area DROP COLUMN id;")
    op.execute("ALTER TABLE upload_area RENAME COLUMN uuid TO id;")
    op.execute("ALTER TABLE upload_area ADD PRIMARY KEY (id)")

    op.execute("ALTER TABLE file "
               "ADD CONSTRAINT file_upload_area FOREIGN KEY (upload_area_id) "
               "REFERENCES upload_area (id) ON DELETE CASCADE;")

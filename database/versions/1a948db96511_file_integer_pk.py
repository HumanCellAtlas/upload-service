"""file_integer_pk

Revision ID: 1a948db96511
Revises: 217fe1d22e4e
Create Date: 2019-01-08 14:48:14.957950

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a948db96511'
down_revision = 'ec83721be9a8'
branch_labels = None
depends_on = None


def upgrade():
    """
    Change file primary key to be integer sequence, move old id column to s3_key,
    update any foreign keys that reference file.
    """

    op.execute("ALTER TABLE checksum DROP CONSTRAINT checksum_file;")
    op.execute("ALTER TABLE validation DROP CONSTRAINT validation_file;")
    op.execute("ALTER TABLE notification DROP CONSTRAINT notification_file;")

    op.execute("ALTER TABLE file DROP CONSTRAINT file_pkey;")
    op.execute("ALTER TABLE file RENAME COLUMN id TO s3_key;")
    op.execute("ALTER TABLE file ADD COLUMN id SERIAL PRIMARY KEY;")

    op.execute("CREATE UNIQUE INDEX file_s3_key_s3_etag ON file (s3_key, s3_etag);")

    op.execute("UPDATE checksum SET file_id = file.id FROM file WHERE checksum.file_id = file.s3_key;")
    op.execute("UPDATE validation SET file_id = file.id FROM file WHERE validation.file_id = file.s3_key;")
    op.execute("UPDATE notification SET file_id = file.id FROM file WHERE notification.file_id = file.s3_key;")

    op.execute("ALTER TABLE checksum ALTER COLUMN file_id TYPE integer USING (file_id::integer);")
    op.execute("ALTER TABLE checksum ADD CONSTRAINT checksum_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")

    op.execute("ALTER TABLE validation ALTER COLUMN file_id TYPE integer USING (file_id::integer);")
    op.execute("ALTER TABLE validation ADD CONSTRAINT validation_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")

    op.execute("ALTER TABLE notification ALTER COLUMN file_id TYPE integer USING (file_id::integer);")
    op.execute("ALTER TABLE notification ADD CONSTRAINT notification_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")


def downgrade():
    op.execute("ALTER TABLE checksum DROP CONSTRAINT checksum_file;")
    op.execute("ALTER TABLE validation DROP CONSTRAINT validation_file;")
    op.execute("ALTER TABLE notification DROP CONSTRAINT notification_file;")

    op.execute("ALTER TABLE checksum ALTER COLUMN file_id TYPE varchar USING (file_id::varchar);")
    op.execute("ALTER TABLE validation ALTER COLUMN file_id TYPE varchar USING (file_id::varchar);")
    op.execute("ALTER TABLE notification ALTER COLUMN file_id TYPE varchar USING (file_id::varchar);")

    op.execute("UPDATE checksum SET file_id = file.s3_key FROM file WHERE checksum.file_id = file.id::varchar;")
    op.execute("UPDATE validation SET file_id = file.s3_key FROM file WHERE validation.file_id = file.id::varchar;")
    op.execute("UPDATE notification SET file_id = file.s3_key FROM file WHERE notification.file_id = file.id::varchar;")

    op.execute("DROP INDEX file_s3_key_s3_etag;")

    op.execute("ALTER TABLE file DROP CONSTRAINT file_pkey;")
    op.execute("ALTER TABLE file DROP COLUMN id;")
    op.execute("ALTER TABLE file RENAME COLUMN s3_key TO id;")
    op.execute("ALTER TABLE file ADD PRIMARY KEY (id);")

    op.execute("ALTER TABLE checksum ADD CONSTRAINT checksum_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE validation ADD CONSTRAINT validation_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE notification ADD CONSTRAINT notification_file FOREIGN KEY (file_id) "
               "REFERENCES file (id) ON DELETE CASCADE;")

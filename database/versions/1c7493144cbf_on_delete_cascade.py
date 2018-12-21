"""on_delete_cascade

Revision ID: 1c7493144cbf
Revises: 10c523521ee7
Create Date: 2018-12-18 13:19:28.696798

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c7493144cbf'
down_revision = '10c523521ee7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE file DROP CONSTRAINT file_upload_area;")
    op.execute("ALTER TABLE checksum DROP CONSTRAINT checksum_file;")
    op.execute("ALTER TABLE validation DROP CONSTRAINT validation_file;")
    op.execute("ALTER TABLE notification DROP CONSTRAINT notification_file;")
    op.execute("ALTER TABLE file "
               "ADD CONSTRAINT file_upload_area "
               "FOREIGN KEY (upload_area_id) REFERENCES upload_area (id) "
               "ON DELETE CASCADE;")
    op.execute("ALTER TABLE checksum "
               "ADD CONSTRAINT checksum_file FOREIGN KEY (file_id) REFERENCES file (id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE validation "
               "ADD CONSTRAINT validation_file FOREIGN KEY (file_id) REFERENCES file (id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE notification "
               "ADD CONSTRAINT notification_file FOREIGN KEY (file_id) REFERENCES file (id) ON DELETE CASCADE;")


def downgrade():
    op.execute("ALTER TABLE file DROP CONSTRAINT file_upload_area;")
    op.execute("ALTER TABLE checksum DROP CONSTRAINT checksum_file;")
    op.execute("ALTER TABLE validation DROP CONSTRAINT validation_file;")
    op.execute("ALTER TABLE notification DROP CONSTRAINT notification_file;")
    op.execute("ALTER TABLE file "
               "ADD CONSTRAINT file_upload_area FOREIGN KEY (upload_area_id) REFERENCES upload_area (id);")
    op.execute("ALTER TABLE checksum ADD CONSTRAINT checksum_file FOREIGN KEY (file_id) REFERENCES file (id);")
    op.execute("ALTER TABLE validation ADD CONSTRAINT validation_file FOREIGN KEY (file_id) REFERENCES file (id);")
    op.execute("ALTER TABLE notification ADD CONSTRAINT notification_file FOREIGN KEY (file_id) REFERENCES file (id);")

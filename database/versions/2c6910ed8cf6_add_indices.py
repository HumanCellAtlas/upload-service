"""add indices

Revision ID: 2c6910ed8cf6
Revises: 3b92db7bb2fe
Create Date: 2018-06-19 10:44:07.676430

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '2c6910ed8cf6'
down_revision = '3b92db7bb2fe'
branch_labels = None
depends_on = None


def upgrade():
    # file indices
    op.create_index("file_upload_area_id_index", "file", ["upload_area_id"])

    # checksum indices
    op.create_index("checksum_file_id_index", "checksum", ["file_id"])
    op.create_index("checksum_job_id_index", "checksum", ["job_id"])

    # event notification indices
    op.create_index("notification_file_id_index", "notification", ["file_id"])

    # validation indices
    op.create_index("validation_file_id_index", "validation", ["file_id"])
    op.create_index("validation_job_id_index", "validation", ["job_id"])


def downgrade():
    op.drop_index("file_upload_area_id_index")
    op.drop_index("checksum_file_id_index")
    op.drop_index("checksum_job_id_index")
    op.drop_index("notification_file_id_index")
    op.drop_index("validation_file_id_index")
    op.drop_index("validation_job_id_index")

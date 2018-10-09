"""add FAILED states and parent_job ids to checksum and validation

Revision ID: 22e0b6f6ad9f
Revises: 2c6910ed8cf6
Create Date: 2018-10-08 16:17:17.276168

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '22e0b6f6ad9f'
down_revision = '2c6910ed8cf6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    op.execute("ALTER TYPE checksumming_status_enum ADD VALUE 'FAILED';")
    op.execute("ALTER TYPE validation_event_status_enum ADD VALUE 'FAILED';")
    op.add_column('checksum', sa.Column('original_attempt_job_id', sa.String, nullable=True))
    op.add_column('validation', sa.Column('original_attempt_job_id', sa.String, nullable=True))
    op.create_index("validation_original_attempt_job_id_index", "validation", ["original_attempt_job_id"])
    op.create_index("checksum_original_attempt_job_id_index", "checksum", ["original_attempt_job_id"])
    op.execute("UPDATE validation SET status = 'FAILED' WHERE status = 'SCHEDULED';")
    op.execute("UPDATE validation SET status = 'FAILED' WHERE status = 'VALIDATING';")


def downgrade():
    # https://stackoverflow.com/questions/25811017/how-to-delete-an-enum-type-value-in-postgres
    # complexity of rollback is unnecessarily to introduce at the moment
    pass

"""create initial tables

Revision ID: 3b92db7bb2fe
Revises:
Create Date: 2018-04-17 22:25:40.756921

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, BIGINT
from datetime import datetime
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '3b92db7bb2fe'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Upload area table
    upload_status_enum = ENUM('CREATING', 'UNLOCKING', 'UNLOCKED', 'LOCKING', 'LOCKED', 'DELETING', 'DELETED', name='upload_status_enum', create_type=False)
    upload_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'upload_area',
        # uuid is the primary id
        sa.Column('id', sa.String, nullable=False, primary_key=True),
        sa.Column('bucket_name', sa.String, nullable=False),
        sa.Column('status', upload_status_enum, nullable=False),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
    )

    # File table
    op.create_table(
        'file',
        # s3_key is the primary id
        sa.Column('id', sa.String, nullable=False, primary_key=True),
        sa.Column('upload_area_id', sa.String, nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('size', BIGINT, nullable=False),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
    )

    op.create_foreign_key(
        "file_upload_area", "file",
        "upload_area", ["upload_area_id"], ["id"])

    # Checksums table
    checksumming_status_enum = ENUM('CHECKSUMMING', 'CHECKSUMMED', 'SCHEDULED', name='checksumming_status_enum', create_type=False)
    checksumming_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'checksum',
        sa.Column('id', sa.String, nullable=False, primary_key=True),
        sa.Column('file_id', sa.String, nullable=False),
        sa.Column('job_id', sa.String, nullable=True),
        sa.Column('status', checksumming_status_enum, nullable=False),
        sa.Column('checksum_started_at', sa.types.DateTime(timezone=True), nullable=True),
        sa.Column('checksum_ended_at', sa.types.DateTime(timezone=True), nullable=True),
        sa.Column('checksums', JSONB, nullable=True),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
    )

    op.create_foreign_key(
        "checksum_file", "checksum",
        "file", ["file_id"], ["id"])

    # Event notifications table
    notification_status_enum = ENUM('DELIVERING', 'DELIVERED', name='notification_status_enum', create_type=False)
    notification_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'notification',
        sa.Column('id', sa.String, nullable=False, primary_key=True),
        sa.Column('file_id', sa.String, nullable=False),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
    )

    op.create_foreign_key(
        "notification_file", "notification",
        "file", ["file_id"], ["id"])

    # Validation table
    validation_event_status_enum = ENUM('VALIDATING', 'VALIDATED', 'SCHEDULED', name='validation_event_status_enum', create_type=False)
    validation_event_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'validation',
        sa.Column('id', sa.String, nullable=False, primary_key=True),
        sa.Column('file_id', sa.String, nullable=False),
        sa.Column('job_id', sa.String, nullable=False),
        sa.Column('status', validation_event_status_enum, nullable=False),
        sa.Column('validation_started_at', sa.types.DateTime(timezone=True), nullable=True),
        sa.Column('validation_ended_at', sa.types.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
    )

    op.create_foreign_key(
        "validation_file", "validation",
        "file", ["file_id"], ["id"])


def downgrade():
    op.drop_table('validation')
    op.drop_table('checksum')
    op.drop_table('notification')
    op.drop_table('file')
    op.drop_table('upload_area')

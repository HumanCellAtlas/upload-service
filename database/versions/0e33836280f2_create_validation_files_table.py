"""create_validation_files_table

Revision ID: 0e33836280f2
Revises: c2edcbf1568d
Create Date: 2019-02-01 11:59:07.101210

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '0e33836280f2'
down_revision = 'c2edcbf1568d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'validation_files',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('validation_id', sa.String, nullable=False),
        sa.Column('file_id', sa.Integer, nullable=False),
        sa.Column('created_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()')),
        sa.Column('updated_at', sa.types.DateTime(timezone=True), nullable=False, server_default=text('now()'))
    )
    op.create_index("validation_files_validation_id_index", "validation_files", ["validation_id"])
    op.create_index("validation_files_file_id_index", "validation_files", ["file_id"])
    op.execute("ALTER TABLE validation_files "
               "ADD CONSTRAINT validation_files_validation_id FOREIGN KEY (validation_id) REFERENCES validation (id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE validation_files "
               "ADD CONSTRAINT validation_files_file_id FOREIGN KEY (file_id) REFERENCES file (id) ON DELETE CASCADE;")
    op.execute("insert into validation_files (validation_id, file_id) select id, file_id from validation;")
    op.execute("ALTER TABLE validation DROP COLUMN file_id;")


def downgrade():
    # This migration is changing the relationship between validation and files from one to one to one to many.
    # I do not think this migration is able to be cleanly rolled back.
    pass

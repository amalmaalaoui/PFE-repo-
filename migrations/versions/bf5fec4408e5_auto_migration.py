"""auto migration

Revision ID: bf5fec4408e5
Revises: 
Create Date: 2025-04-27 04:30:37.421338

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'bf5fec4408e5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('apscheduler_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_apscheduler_jobs_next_run_time')

    op.drop_table('apscheduler_jobs')
    with op.batch_alter_table('migrations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scheduled_time', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('job_id', sa.String(length=100), nullable=True))
        batch_op.alter_column('source_file',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.String(length=500),
               existing_nullable=False)
        batch_op.alter_column('target_file',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.String(length=500),
               existing_nullable=False)
        batch_op.alter_column('status',
               existing_type=mysql.VARCHAR(length=50),
               nullable=False)
        batch_op.create_index(batch_op.f('ix_migrations_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_migrations_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('user_files', schema=None) as batch_op:
        batch_op.alter_column('filepath',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.String(length=500),
               existing_nullable=False)
        batch_op.alter_column('size',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
        batch_op.alter_column('sheet_count',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
        batch_op.alter_column('file_type',
               existing_type=mysql.VARCHAR(length=50),
               type_=sa.Enum('SOURCE', 'TARGET', 'MIGRATION', name='filetype'),
               nullable=False)
        batch_op.create_index(batch_op.f('ix_user_files_upload_date'), ['upload_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_files_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('password_hash',
               existing_type=mysql.VARCHAR(length=128),
               type_=sa.String(length=256),
               nullable=False)
        batch_op.drop_index('email')
        batch_op.drop_index('username')
        batch_op.create_index(batch_op.f('ix_users_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_index(batch_op.f('ix_users_created_at'))
        batch_op.create_index('username', ['username'], unique=True)
        batch_op.create_index('email', ['email'], unique=True)
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=256),
               type_=mysql.VARCHAR(length=128),
               nullable=True)

    with op.batch_alter_table('user_files', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_files_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_files_upload_date'))
        batch_op.alter_column('file_type',
               existing_type=sa.Enum('SOURCE', 'TARGET', 'MIGRATION', name='filetype'),
               type_=mysql.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('sheet_count',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
        batch_op.alter_column('size',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
        batch_op.alter_column('filepath',
               existing_type=sa.String(length=500),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=False)

    with op.batch_alter_table('migrations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_migrations_user_id'))
        batch_op.drop_index(batch_op.f('ix_migrations_created_at'))
        batch_op.alter_column('status',
               existing_type=mysql.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('target_file',
               existing_type=sa.String(length=500),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=False)
        batch_op.alter_column('source_file',
               existing_type=sa.String(length=500),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=False)
        batch_op.drop_column('job_id')
        batch_op.drop_column('scheduled_time')

    op.create_table('apscheduler_jobs',
    sa.Column('id', mysql.VARCHAR(length=191), nullable=False),
    sa.Column('next_run_time', mysql.DOUBLE(asdecimal=True), nullable=True),
    sa.Column('job_state', sa.BLOB(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_general_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('apscheduler_jobs', schema=None) as batch_op:
        batch_op.create_index('ix_apscheduler_jobs_next_run_time', ['next_run_time'], unique=False)

    # ### end Alembic commands ###

"""Track independent source observations for jobs."""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_sources",
        sa.Column("key", sa.String(length=300), primary_key=True),
        sa.Column("job_id", sa.String(length=32), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024)),
        sa.Column("verified", sa.String(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_job_sources_job_id", "job_sources", ["job_id"])
    op.create_index("ix_job_sources_canonical_url", "job_sources", ["canonical_url"])
    op.execute(sa.text(
        'INSERT INTO job_sources ("key", job_id, canonical_url, verified, available) '
        'SELECT source_key, id, canonical_url, verified, available FROM jobs'
    ))


def downgrade():
    op.drop_index("ix_job_sources_canonical_url", table_name="job_sources")
    op.drop_index("ix_job_sources_job_id", table_name="job_sources")
    op.drop_table("job_sources")

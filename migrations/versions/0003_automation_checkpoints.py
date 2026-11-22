"""Durable worker heartbeat and per-job automation checkpoints."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("automation", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("worker_lock", sa.Column("last_seen", sa.String(), nullable=True))
    op.add_column("worker_lock", sa.Column("model_status", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("worker_lock", "model_status")
    op.drop_column("worker_lock", "last_seen")
    op.drop_column("jobs", "automation")

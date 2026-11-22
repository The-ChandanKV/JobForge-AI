"""Exact final approval, durable dispatch, and notifications."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("prepared_payload", sa.JSON()))
    op.create_table(
        "final_approvals", sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("application_id", sa.String(32), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created", sa.String(), nullable=False),
    )
    op.create_index("ix_final_approvals_application_id", "final_approvals", ["application_id"])
    op.create_table(
        "submission_tasks", sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("approval_id", sa.String(32), sa.ForeignKey("final_approvals.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("dispatch_key", sa.String(32), unique=True),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.String(), nullable=False), sa.Column("attempted_at", sa.String()),
        sa.Column("finished_at", sa.String()), sa.Column("result", sa.String(100)),
        sa.Column("created", sa.String(), nullable=False),
    )
    op.create_index("ix_submission_tasks_status", "submission_tasks", ["status"])
    op.create_table(
        "notifications", sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("message", sa.String(240), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False), sa.Column("pending", sa.Boolean(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False), sa.Column("created", sa.String(), nullable=False),
    )
    settings = sa.table("settings", sa.column("id", sa.Integer), sa.column("options", sa.JSON))
    connection = op.get_bind()
    for item in connection.execute(sa.select(settings)).mappings().all():
        options = {**item["options"], "auto_submit": False, "automation_mode": "AUTONOMOUS_PREPARATION"}
        connection.execute(settings.update().where(settings.c.id == item["id"]).values(options=options))


def downgrade():
    op.drop_table("notifications")
    op.drop_table("submission_tasks")
    op.drop_table("final_approvals")
    op.drop_column("applications", "prepared_payload")

"""Initial migration creating all 13 core database entities.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-17 11:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.base import VectorType

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("github_access_token", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # 2. projects
    op.create_table(
        "projects",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "slug", name="uq_project_slug_per_user"),
    )
    op.create_index("idx_projects_owner", "projects", ["owner_id"])

    # 3. repositories
    op.create_table(
        "repositories",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", PG_UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("clone_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(100), nullable=False, server_default="main"),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_repositories_project", "repositories", ["project_id"])
    op.create_index("idx_repositories_user", "repositories", ["user_id"])

    # 4. tasks
    op.create_table(
        "tasks",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", PG_UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=False, server_default="bug_fix"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("iterations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("pull_request_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_tasks_repo_status", "tasks", ["repository_id", "status"])
    op.create_index("idx_tasks_project", "tasks", ["project_id"])
    op.create_index("idx_tasks_created_by", "tasks", ["created_by"])

    # 5. task_plans
    op.create_table(
        "task_plans",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("test_criteria", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_task_plans_task", "task_plans", ["task_id"])

    # 6. agent_runs
    op.create_table(
        "agent_runs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("input_state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("output_state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tool_calls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_agent_runs_task_step", "agent_runs", ["task_id", "step_number"])

    # 7. file_changes
    op.create_table(
        "file_changes",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=True),
        sa.Column("new_content", sa.Text(), nullable=True),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_file_changes_task", "file_changes", ["task_id"])

    # 8. test_runs
    op.create_table(
        "test_runs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_test_runs_task_iter", "test_runs", ["task_id", "iteration"])

    # 9. approvals
    op.create_table(
        "approvals",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", PG_UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", PG_UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_approvals_task", "approvals", ["task_id"])

    # 10. reports
    op.create_table(
        "reports",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("root_cause_analysis", sa.Text(), nullable=False),
        sa.Column("test_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_reports_task", "reports", ["task_id"])

    # 11. feedback
    op.create_table(
        "feedback",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(50), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("solution_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_feedback_task", "feedback", ["task_id"])

    # 12. repository_knowledge
    op.create_table(
        "repository_knowledge",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("symbol_name", sa.String(255), nullable=True),
        sa.Column("symbol_type", sa.String(50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", VectorType(768), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_repo_knowledge_repo", "repository_knowledge", ["repository_id"])

    # 13. engineering_experiences
    op.create_table(
        "engineering_experiences",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_category", sa.String(100), nullable=False),
        sa.Column("bug_category", sa.String(100), nullable=True),
        sa.Column("problem_summary", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("resolution_strategy", sa.Text(), nullable=False),
        sa.Column("diff_patch", sa.Text(), nullable=False),
        sa.Column("embedding", VectorType(768), nullable=False),
        sa.Column("is_anonymized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_eng_exp_category", "engineering_experiences", ["task_category", "bug_category"])


def downgrade() -> None:
    op.drop_table("engineering_experiences")
    op.drop_table("repository_knowledge")
    op.drop_table("feedback")
    op.drop_table("reports")
    op.drop_table("approvals")
    op.drop_table("test_runs")
    op.drop_table("file_changes")
    op.drop_table("agent_runs")
    op.drop_table("task_plans")
    op.drop_table("tasks")
    op.drop_table("repositories")
    op.drop_table("projects")
    op.drop_table("users")

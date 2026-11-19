"""Add Phase 8 GitHub-Native Autonomous Engineering schema: installations, pull requests, and git branches.

Revision ID: 007_github_native_engineering
Revises: 006_adaptive_intelligence
Create Date: 2026-11-19 02:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "007_github_native_engineering"
down_revision: Union[str, None] = "006_adaptive_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create github_installations table
    op.create_table(
        "github_installations",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False, server_default="User"),
        sa.Column("account_avatar_url", sa.Text(), nullable=True),
        sa.Column("repository_selection", sa.String(50), nullable=False, server_default="selected"),
        sa.Column("permissions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_gh_installations_user", "github_installations", ["user_id"])
    op.create_index("idx_gh_installations_inst_id", "github_installations", ["installation_id"])

    # 2. Add GitHub App attributes to repositories table
    op.add_column(
        "repositories",
        sa.Column("installation_id", PG_UUID(as_uuid=True), sa.ForeignKey("github_installations.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("github_repo_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "repositories",
        sa.Column("permissions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("idx_repositories_installation", "repositories", ["installation_id"])
    op.create_index("idx_repositories_gh_repo_id", "repositories", ["github_repo_id"])

    # 3. Add Git branch tracking to tasks table
    op.add_column(
        "tasks",
        sa.Column("task_branch", sa.String(255), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("commit_sha", sa.String(100), nullable=True),
    )

    # 4. Create github_pull_requests table
    op.create_table(
        "github_pull_requests",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("head_branch", sa.String(255), nullable=False),
        sa.Column("base_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("state", sa.String(50), nullable=False, server_default="open"),
        sa.Column("is_merged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("merge_commit_sha", sa.String(100), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_gh_pr_task", "github_pull_requests", ["task_id"])
    op.create_index("idx_gh_pr_repo", "github_pull_requests", ["repository_id"])
    op.create_index("idx_gh_pr_number", "github_pull_requests", ["repository_id", "pr_number"])

    # 5. Create git_branches table
    op.create_table(
        "git_branches",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repository_id", PG_UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_name", sa.String(255), nullable=False),
        sa.Column("base_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("commit_sha", sa.String(100), nullable=True),
        sa.Column("is_pushed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_git_branches_task", "git_branches", ["task_id"])
    op.create_index("idx_git_branches_repo_name", "git_branches", ["repository_id", "branch_name"])


def downgrade() -> None:
    # 5. Drop git_branches
    op.drop_index("idx_git_branches_repo_name", table_name="git_branches")
    op.drop_index("idx_git_branches_task", table_name="git_branches")
    op.drop_table("git_branches")

    # 4. Drop github_pull_requests
    op.drop_index("idx_gh_pr_number", table_name="github_pull_requests")
    op.drop_index("idx_gh_pr_repo", table_name="github_pull_requests")
    op.drop_index("idx_gh_pr_task", table_name="github_pull_requests")
    op.drop_table("github_pull_requests")

    # 3. Drop tasks columns
    op.drop_column("tasks", "commit_sha")
    op.drop_column("tasks", "task_branch")

    # 2. Drop repositories columns
    op.drop_index("idx_repositories_gh_repo_id", table_name="repositories")
    op.drop_index("idx_repositories_installation", table_name="repositories")
    op.drop_column("repositories", "permissions")
    op.drop_column("repositories", "is_private")
    op.drop_column("repositories", "github_repo_id")
    op.drop_column("repositories", "installation_id")

    # 1. Drop github_installations
    op.drop_index("idx_gh_installations_inst_id", table_name="github_installations")
    op.drop_index("idx_gh_installations_user", table_name="github_installations")
    op.drop_table("github_installations")

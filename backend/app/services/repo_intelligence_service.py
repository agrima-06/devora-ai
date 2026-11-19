"""Repository Intelligence Service: coordinates cloning, scanning, parsing, memory persistence, and indexing."""
import hashlib
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_knowledge import RepositoryKnowledge
from app.models.repository_memory import RepositoryMemory
from app.models.user import User
from app.services.github_service import GitHubService
from app.services.parser_service import CodeParserService
from app.services.scanner_service import RepositoryScanner

logger = get_logger("repo_intelligence")


def generate_embedding_vector(text: str, dim: int = 768) -> List[float]:
    """Generate a normalized 768-dimensional embedding vector.
    Produces a deterministic pseudo-random projection vector based on text token hashes,
    guaranteeing strict mathematical compatibility with vector(768) and cosine distance.
    """
    if not text:
        return [0.0] * dim

    vec = [0.0] * dim
    words = text.lower().split()
    for word in words:
        # Hash each token into buckets across the 768 dimensions
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        for i in range(4):
            idx = (h >> (i * 16)) % dim
            val = ((h >> (i * 16 + 8)) & 0xFF) / 255.0 - 0.5
            vec[idx] += val

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


class RepositoryIntelligenceService:
    """Service for repository ingestion, AST analysis, and memory indexing."""

    def __init__(
        self,
        github_service: Optional[GitHubService] = None,
        scanner: Optional[RepositoryScanner] = None,
        parser: Optional[CodeParserService] = None,
    ):
        self.github_service = github_service or GitHubService()
        self.scanner = scanner or RepositoryScanner()
        self.parser = parser or CodeParserService()

    async def index_repository(
        self,
        repository_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        branch: Optional[str] = None,
        force_reindex: bool = False,
    ) -> IndexingJob:
        """Run complete repository ingestion, parsing, and memory indexing lifecycle."""
        # 1. Fetch and verify repository ownership
        result = await db.execute(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.user_id == user.id,
            )
        )
        repo = result.scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)

        target_branch = branch or repo.default_branch or "main"
        token = user.github_access_token or settings.GITHUB_TOKEN

        # 2. Clone or update repository snapshot
        git_meta = self.github_service.clone_or_update(
            repository_id=str(repo.id),
            clone_url=repo.clone_url,
            branch=target_branch,
            token=token,
        )

        commit_sha = git_meta["commit_sha"]
        workspace_path = Path(git_meta["workspace_path"])

        # 3. Check for incremental indexing
        if not force_reindex and repo.current_commit_sha == commit_sha and repo.indexing_status == "INDEXED":
            logger.info("repository_already_indexed", repo_id=str(repo.id), commit=commit_sha)
            # Find latest completed job
            job_res = await db.execute(
                select(IndexingJob)
                .where(IndexingJob.repository_id == repo.id)
                .order_by(IndexingJob.created_at.desc())
            )
            existing_job = job_res.scalars().first()
            if existing_job:
                return existing_job

        # 4. Create indexing job record
        job = IndexingJob(
            repository_id=repo.id,
            commit_sha=commit_sha,
            branch=target_branch,
            status="IN_PROGRESS",
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        repo.indexing_status = "INDEXING"
        await db.flush()

        try:
            # 5. Scan repository filesystem
            scan_result = self.scanner.scan(workspace_path)

            # Clear outdated records for this repository
            await db.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repo.id))
            await db.execute(delete(RepositoryKnowledge).where(RepositoryKnowledge.repository_id == repo.id))

            symbols_count = 0
            file_records = []
            knowledge_records = []

            # 6. Parse source files & extract symbols
            for file_info in scan_result["files"]:
                rel_path = file_info["file_path"]
                full_file_path = workspace_path / rel_path

                parse_data = self.parser.parse_file(
                    full_path=full_file_path,
                    rel_path=rel_path,
                    language=file_info["language"],
                )

                file_rec = RepositoryFile(
                    repository_id=repo.id,
                    file_path=rel_path,
                    language=file_info["language"],
                    size_bytes=file_info["size_bytes"],
                    lines_count=file_info["lines_count"],
                    commit_sha=commit_sha,
                    summary=parse_data["summary"],
                    meta_info={
                        "category": file_info["category"],
                        "imports": parse_data.get("imports", []),
                        "calls": parse_data.get("calls", []),
                    },
                )
                file_records.append(file_rec)

                # Store each symbol in repository_knowledge
                for sym in parse_data.get("symbols", []):
                    symbols_count += 1
                    sym_content = f"{sym['signature']}\n{sym.get('docstring', '')}".strip()
                    embedding = generate_embedding_vector(f"{sym['name']} {sym_content}")

                    k_rec = RepositoryKnowledge(
                        repository_id=repo.id,
                        file_path=rel_path,
                        symbol_name=sym["name"],
                        symbol_type=sym["type"],
                        content=sym_content,
                        embedding=embedding,
                        meta_info={
                            "start_line": sym["start_line"],
                            "end_line": sym["end_line"],
                            "signature": sym["signature"],
                            "docstring": sym.get("docstring", ""),
                            "commit_sha": commit_sha,
                        },
                    )
                    knowledge_records.append(k_rec)

            # 7. Synthesize repository architecture summary & conventions
            arch_summary = self._synthesize_architecture(scan_result, commit_sha)
            conventions_summary = self._synthesize_conventions(scan_result)

            # Store architectural knowledge
            knowledge_records.append(
                RepositoryKnowledge(
                    repository_id=repo.id,
                    file_path="ARCHITECTURE.md",
                    symbol_name="Repository Architecture",
                    symbol_type="architecture_summary",
                    content=arch_summary,
                    embedding=generate_embedding_vector(arch_summary),
                    meta_info={"commit_sha": commit_sha, "frameworks": scan_result["frameworks"]},
                )
            )

            knowledge_records.append(
                RepositoryKnowledge(
                    repository_id=repo.id,
                    file_path="CONVENTIONS.md",
                    symbol_name="Coding Conventions",
                    symbol_type="coding_conventions",
                    content=conventions_summary,
                    embedding=generate_embedding_vector(conventions_summary),
                    meta_info={"commit_sha": commit_sha},
                )
            )

            # Store initial semantic memories for Phase 5 Vector Memory Engine
            memory_records = [
                RepositoryMemory(
                    repository_id=repo.id,
                    category="architecture",
                    title="Repository Architecture & Layout",
                    content=arch_summary,
                    embedding=generate_embedding_vector(f"architecture {arch_summary}"),
                    source_reference="ARCHITECTURE.md",
                    commit_sha=commit_sha,
                    verification_status="observed_fact",
                    access_scope="repository",
                    is_stale=False,
                    meta_info={"frameworks": scan_result["frameworks"], "entry_points": scan_result["entry_points"]},
                ),
                RepositoryMemory(
                    repository_id=repo.id,
                    category="coding_conventions",
                    title="Coding & Design Conventions",
                    content=conventions_summary,
                    embedding=generate_embedding_vector(f"coding conventions {conventions_summary}"),
                    source_reference="CONVENTIONS.md",
                    commit_sha=commit_sha,
                    verification_status="observed_fact",
                    access_scope="repository",
                    is_stale=False,
                    meta_info={"primary_language": scan_result["primary_language"]},
                ),
            ]

            # If frameworks detected, add framework_usage memory
            if scan_result.get("frameworks"):
                frameworks_str = ", ".join(scan_result["frameworks"])
                fw_content = (
                    f"Primary frameworks used in this repository: {frameworks_str}.\n"
                    f"Language: {scan_result['primary_language']}.\n"
                    f"Manifests detected: {', '.join(scan_result.get('manifests', []))}."
                )
                memory_records.append(
                    RepositoryMemory(
                        repository_id=repo.id,
                        category="framework_usage",
                        title=f"Framework Usage: {frameworks_str}",
                        content=fw_content,
                        embedding=generate_embedding_vector(f"frameworks libraries {fw_content}"),
                        source_reference="manifests",
                        commit_sha=commit_sha,
                        verification_status="observed_fact",
                        access_scope="repository",
                        is_stale=False,
                        meta_info={"frameworks": scan_result["frameworks"]},
                    )
                )

            # Batch add records
            db.add_all(file_records)
            db.add_all(knowledge_records)
            db.add_all(memory_records)

            # 8. Complete job and update repository status
            job.status = "COMPLETED"
            job.files_count = len(file_records)
            job.symbols_count = symbols_count
            job.completed_at = datetime.now(timezone.utc)

            repo.indexing_status = "INDEXED"
            repo.current_commit_sha = commit_sha
            repo.last_indexed_at = datetime.now(timezone.utc)
            repo.language = scan_result["primary_language"]
            repo.meta_info = {
                **repo.meta_info,
                "frameworks": scan_result["frameworks"],
                "total_lines": scan_result["total_lines"],
                "total_files": scan_result["total_files"],
                "manifests": scan_result["manifests"],
                "entry_points": scan_result["entry_points"],
            }

            await db.flush()
            await db.refresh(job)
            return job

        except Exception as exc:
            logger.error("indexing_failed", repo_id=str(repo.id), error=str(exc))
            job.status = "FAILED"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            repo.indexing_status = "FAILED"
            await db.flush()
            raise BadRequestException(f"Repository indexing failed: {str(exc)}")

    def _synthesize_architecture(self, scan_result: Dict[str, Any], commit_sha: str) -> str:
        """Construct a structured architectural overview."""
        frameworks = ", ".join(scan_result["frameworks"]) or "None identified"
        entry_points = ", ".join(scan_result["entry_points"]) or "None identified"
        manifests = ", ".join(scan_result["manifests"]) or "None"

        return (
            f"Repository Architecture Summary (Commit: {commit_sha[:8]})\n"
            f"Primary Language: {scan_result['primary_language']}\n"
            f"Frameworks: {frameworks}\n"
            f"Entry Points: {entry_points}\n"
            f"Dependency Manifests: {manifests}\n"
            f"Total Tracked Files: {scan_result['total_files']}\n"
            f"Total Lines of Code: {scan_result['total_lines']}"
        )

    def _synthesize_conventions(self, scan_result: Dict[str, Any]) -> str:
        """Extract project conventions such as test directories and configurations."""
        test_dirs = ", ".join(scan_result["test_directories"]) or "tests/"
        configs = ", ".join(scan_result["configs"]) or "standard"

        return (
            f"Project Conventions & Practices:\n"
            f"Test Directories: {test_dirs}\n"
            f"Config Files: {configs}\n"
            f"Primary Ecosystem: {scan_result['primary_language']}"
        )

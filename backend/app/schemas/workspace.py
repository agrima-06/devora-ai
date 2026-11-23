"""Pydantic schemas for Phase 10 Stage 10.3: Monorepo & Workspace Intelligence Engine."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PackageInfo(BaseModel):
    """Metadata representing a discrete package, module, or crate within a workspace."""
    id: Optional[str] = Field(None, description="UUID of the corresponding graph node in DB")
    name: str = Field(..., description="Package name as declared in manifest (e.g. @devora/core, app-server)")
    version: Optional[str] = Field(None, description="Semantic version string if defined")
    path: str = Field(..., description="Repository-relative directory path to package root")
    manifest_path: str = Field(..., description="Repository-relative path to package manifest")
    language: str = Field(..., description="Primary language: typescript, python, rust, java, go, etc.")
    internal_dependencies: List[str] = Field(default_factory=list, description="Names of internal workspace packages depended upon")
    external_dependencies: List[str] = Field(default_factory=list, description="External 3rd-party dependencies declared")
    files_count: int = Field(0, description="Total source files enclosed within package boundary")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional manifest-specific attributes")


class WorkspaceInfo(BaseModel):
    """Metadata representing a workspace, multi-project build, or monorepo root."""
    id: Optional[str] = Field(None, description="UUID of the corresponding workspace graph node in DB")
    workspace_type: str = Field(..., description="Ecosystem/tool: pnpm, npm, yarn, turborepo, nx, lerna, cargo, maven, gradle, go_work, poetry, pdm, uv")
    root_path: str = Field(".", description="Repository-relative root path where workspace is defined")
    manifest_file: Optional[str] = Field(None, description="Relative path to workspace configuration file")
    packages_count: int = Field(0, description="Count of packages managed by this workspace")
    packages: List[PackageInfo] = Field(default_factory=list, description="Packages discovered under this workspace")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific settings and pipeline config")


class CrossPackageEdgeItem(BaseModel):
    """Directional dependency edge linking two packages within the repository."""
    source_package: str = Field(..., description="Consuming package name")
    target_package: str = Field(..., description="Depended package name")
    edge_type: str = Field("PACKAGE_DEPENDS_ON", description="Edge relationship type")
    confidence: float = Field(1.0, description="Confidence rating")


class WorkspaceSummary(BaseModel):
    """High-level summary of repository workspaces and monorepo characteristics."""
    total_workspaces: int = Field(0, description="Number of distinct workspaces detected")
    total_packages: int = Field(0, description="Total packages across all workspaces")
    ecosystems: List[str] = Field(default_factory=list, description="List of detected package management ecosystems")
    is_monorepo: bool = Field(False, description="Whether the repository operates as a monorepo")


class WorkspaceGraphResponse(BaseModel):
    """Complete workspace and package topology response for a repository."""
    repository_id: str
    workspaces: List[WorkspaceInfo] = Field(default_factory=list)
    cross_package_edges: List[CrossPackageEdgeItem] = Field(default_factory=list)
    summary: WorkspaceSummary


class PackageDependenciesResponse(BaseModel):
    """Upstream and downstream dependency graph for a specific package."""
    package_id: str
    package_name: str
    package_path: str
    internal_dependencies: List[PackageInfo] = Field(default_factory=list, description="Internal packages this package depends on")
    external_dependencies: List[str] = Field(default_factory=list, description="External libraries declared in manifest")
    dependents: List[PackageInfo] = Field(default_factory=list, description="Internal packages that depend on this package")


class AffectedPackageItem(BaseModel):
    """Downstream package impacted by modifications in an upstream package."""
    package_name: str
    package_path: str
    depth: int = Field(1, description="Hop distance in package dependency graph")
    dependency_path: List[str] = Field(default_factory=list, description="Chain of package names connecting target to consumer")


class PackageImpactResponse(BaseModel):
    """Change impact and blast radius assessment localized to package boundaries."""
    package_id: str
    package_name: str
    severity: str = Field("LOW", description="LOW, MEDIUM, HIGH, CRITICAL")
    affected_packages: List[AffectedPackageItem] = Field(default_factory=list)
    affected_packages_count: int = 0
    affected_files_count: int = 0
    recommendations: List[str] = Field(default_factory=list)


class WorkspaceIndexResponse(BaseModel):
    """Result of triggering workspace and package indexing for a repository."""
    repository_id: str
    workspaces_found: int = 0
    packages_indexed: int = 0
    edges_created: int = 0
    duration_seconds: float = 0.0
    status: str = "COMPLETED"

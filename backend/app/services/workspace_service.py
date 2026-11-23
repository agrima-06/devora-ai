"""Monorepo & Workspace Intelligence Engine.

Provides multi-language workspace detection (npm, pnpm, yarn, turborepo, nx, lerna,
cargo, maven, gradle, go.work, poetry, pdm, uv), package extraction, cross-package
dependency resolution, graph indexing, and package-level blast radius analysis.
"""

import fnmatch
import json
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

import yaml
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.repository_graph_edge import RepositoryGraphEdge
from app.models.repository_graph_node import RepositoryGraphNode
from app.schemas.workspace import (
    AffectedPackageItem,
    CrossPackageEdgeItem,
    PackageDependenciesResponse,
    PackageImpactResponse,
    PackageInfo,
    WorkspaceGraphResponse,
    WorkspaceIndexResponse,
    WorkspaceInfo,
    WorkspaceSummary,
)

logger = get_logger("workspace_service")


class MonorepoDetector:
    """Discovers monorepos, multi-project configurations, and packages across 5 language ecosystems."""

    def detect(self, repo_root: Path) -> List[WorkspaceInfo]:
        """Inspect repository filesystem and return all detected workspaces with their packages."""
        repo_root = Path(repo_root)
        if not repo_root.is_dir():
            return []

        workspaces: List[WorkspaceInfo] = []

        # 1. JavaScript / TypeScript ecosystems
        js_workspaces = self._detect_js_workspaces(repo_root)
        workspaces.extend(js_workspaces)

        # 2. Rust (Cargo workspaces)
        rust_workspaces = self._detect_rust_workspaces(repo_root)
        workspaces.extend(rust_workspaces)

        # 3. Java / Kotlin (Maven & Gradle)
        jvm_workspaces = self._detect_jvm_workspaces(repo_root)
        workspaces.extend(jvm_workspaces)

        # 4. Go (go.work & multi-module)
        go_workspaces = self._detect_go_workspaces(repo_root)
        workspaces.extend(go_workspaces)

        # 5. Python (uv, poetry, pdm, multi-package)
        python_workspaces = self._detect_python_workspaces(repo_root)
        workspaces.extend(python_workspaces)

        # Cross-resolve internal vs external dependencies across all discovered packages
        self._cross_resolve_dependencies(workspaces, repo_root)

        return workspaces

    # ---------------------------------------------------------------------------
    # Ecosystem Detectors
    # ---------------------------------------------------------------------------

    def _detect_js_workspaces(self, root: Path) -> List[WorkspaceInfo]:
        """Detect npm, pnpm, yarn, turborepo, nx, and lerna workspaces."""
        workspaces: List[WorkspaceInfo] = []

        # Check pnpm
        pnpm_file = root / "pnpm-workspace.yaml"
        if pnpm_file.is_file():
            try:
                content = yaml.safe_load(pnpm_file.read_text(encoding="utf-8"))
                patterns = content.get("packages", []) if isinstance(content, dict) else []
                pkgs = self._find_js_packages(root, patterns)
                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="pnpm",
                        root_path=".",
                        manifest_file="pnpm-workspace.yaml",
                        packages_count=len(pkgs),
                        packages=pkgs,
                        metadata={"patterns": patterns},
                    )
                )
            except Exception as e:
                logger.warning("pnpm_detection_failed", error=str(e))

        # Check package.json (npm / yarn)
        pkg_json = root / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                ws_config = data.get("workspaces")
                patterns: List[str] = []
                if isinstance(ws_config, list):
                    patterns = ws_config
                elif isinstance(ws_config, dict):
                    patterns = ws_config.get("packages", [])

                if patterns:
                    tool_type = "npm"
                    if (root / "yarn.lock").is_file():
                        tool_type = "yarn"
                    if (root / "turbo.json").is_file():
                        tool_type = "turborepo"
                    elif (root / "nx.json").is_file():
                        tool_type = "nx"
                    elif (root / "lerna.json").is_file():
                        tool_type = "lerna"

                    pkgs = self._find_js_packages(root, patterns)
                    workspaces.append(
                        WorkspaceInfo(
                            workspace_type=tool_type,
                            root_path=".",
                            manifest_file="package.json",
                            packages_count=len(pkgs),
                            packages=pkgs,
                            metadata={"patterns": patterns, "root_name": data.get("name")},
                        )
                    )
            except Exception as e:
                logger.warning("npm_workspace_detection_failed", error=str(e))

        # Standalone Lerna without root workspaces declaration
        if not workspaces and (root / "lerna.json").is_file():
            try:
                lerna_data = json.loads((root / "lerna.json").read_text(encoding="utf-8"))
                patterns = lerna_data.get("packages", ["packages/*"])
                pkgs = self._find_js_packages(root, patterns)
                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="lerna",
                        root_path=".",
                        manifest_file="lerna.json",
                        packages_count=len(pkgs),
                        packages=pkgs,
                        metadata={"version": lerna_data.get("version")},
                    )
                )
            except Exception:
                pass

        return workspaces

    def _find_js_packages(self, root: Path, patterns: List[str]) -> List[PackageInfo]:
        """Find subdirectories matching package glob patterns containing package.json."""
        packages: List[PackageInfo] = []
        seen_paths: Set[str] = set()

        for pattern in patterns:
            pattern = pattern.rstrip("/")
            for match_dir in self._match_directories(root, pattern):
                pkg_file = match_dir / "package.json"
                if pkg_file.is_file():
                    rel_path = str(match_dir.relative_to(root)).replace("\\", "/")
                    if rel_path in seen_paths or rel_path == ".":
                        continue
                    seen_paths.add(rel_path)

                    try:
                        pdata = json.loads(pkg_file.read_text(encoding="utf-8"))
                        pname = pdata.get("name") or match_dir.name
                        pversion = pdata.get("version")
                        declared_deps = list(pdata.get("dependencies", {}).keys()) + \
                                        list(pdata.get("devDependencies", {}).keys()) + \
                                        list(pdata.get("peerDependencies", {}).keys())

                        packages.append(
                            PackageInfo(
                                name=pname,
                                version=pversion,
                                path=rel_path,
                                manifest_path=f"{rel_path}/package.json",
                                language="typescript" if (match_dir / "tsconfig.json").is_file() else "javascript",
                                external_dependencies=declared_deps,
                                metadata={
                                    "scripts": list(pdata.get("scripts", {}).keys()),
                                    "main": pdata.get("main"),
                                },
                            )
                        )
                    except Exception:
                        pass
        return packages

    def _detect_rust_workspaces(self, root: Path) -> List[WorkspaceInfo]:
        """Detect Cargo workspace definitions in Cargo.toml."""
        workspaces: List[WorkspaceInfo] = []
        cargo_root = root / "Cargo.toml"
        if not cargo_root.is_file():
            return workspaces

        try:
            content = tomllib.loads(cargo_root.read_text(encoding="utf-8"))
            ws_section = content.get("workspace")
            if ws_section and isinstance(ws_section, dict):
                members = ws_section.get("members", [])
                pkgs: List[PackageInfo] = []
                seen_paths: Set[str] = set()

                for member in members:
                    for match_dir in self._match_directories(root, member.rstrip("/")):
                        pkg_toml = match_dir / "Cargo.toml"
                        if pkg_toml.is_file():
                            rel_path = str(match_dir.relative_to(root)).replace("\\", "/")
                            if rel_path in seen_paths or rel_path == ".":
                                continue
                            seen_paths.add(rel_path)

                            try:
                                pkg_data = tomllib.loads(pkg_toml.read_text(encoding="utf-8"))
                                pkg_spec = pkg_data.get("package", {})
                                name = pkg_spec.get("name", match_dir.name)
                                version = pkg_spec.get("version")
                                declared_deps = list(pkg_data.get("dependencies", {}).keys()) + \
                                                list(pkg_data.get("dev-dependencies", {}).keys())

                                pkgs.append(
                                    PackageInfo(
                                        name=name,
                                        version=version,
                                        path=rel_path,
                                        manifest_path=f"{rel_path}/Cargo.toml",
                                        language="rust",
                                        external_dependencies=declared_deps,
                                        metadata={"edition": pkg_spec.get("edition")},
                                    )
                                )
                            except Exception:
                                pass

                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="cargo",
                        root_path=".",
                        manifest_file="Cargo.toml",
                        packages_count=len(pkgs),
                        packages=pkgs,
                        metadata={"members": members},
                    )
                )
        except Exception as e:
            logger.warning("cargo_workspace_detection_failed", error=str(e))

        return workspaces

    def _detect_jvm_workspaces(self, root: Path) -> List[WorkspaceInfo]:
        """Detect Maven multi-module pom.xml and Gradle settings.gradle multi-project builds."""
        workspaces: List[WorkspaceInfo] = []

        # 1. Maven multi-module
        maven_root = root / "pom.xml"
        if maven_root.is_file():
            try:
                tree = ET.parse(maven_root)
                pom_xml_root = tree.getroot()
                # Strip XML namespace if present
                ns = ""
                if pom_xml_root.tag.startswith("{"):
                    ns = pom_xml_root.tag.split("}")[0] + "}"

                modules_node = pom_xml_root.find(f"{ns}modules")
                if modules_node is not None:
                    module_names = [m.text.strip() for m in modules_node.findall(f"{ns}module") if m.text]
                    pkgs: List[PackageInfo] = []

                    for mod in module_names:
                        mod_dir = root / mod
                        mod_pom = mod_dir / "pom.xml"
                        if mod_pom.is_file():
                            rel_path = str(mod_dir.relative_to(root)).replace("\\", "/")
                            try:
                                mod_tree = ET.parse(mod_pom)
                                m_root = mod_tree.getroot()
                                m_ns = ""
                                if m_root.tag.startswith("{"):
                                    m_ns = m_root.tag.split("}")[0] + "}"

                                art_id_el = m_root.find(f"{m_ns}artifactId")
                                name = art_id_el.text.strip() if art_id_el is not None and art_id_el.text else mod
                                ver_el = m_root.find(f"{m_ns}version")
                                ver = ver_el.text.strip() if ver_el is not None and ver_el.text else None

                                # Collect dependencies
                                deps = []
                                deps_el = m_root.find(f"{m_ns}dependencies")
                                if deps_el is not None:
                                    for dep in deps_el.findall(f"{m_ns}dependency"):
                                        d_art = dep.find(f"{m_ns}artifactId")
                                        if d_art is not None and d_art.text:
                                            deps.append(d_art.text.strip())

                                pkgs.append(
                                    PackageInfo(
                                        name=name,
                                        version=ver,
                                        path=rel_path,
                                        manifest_path=f"{rel_path}/pom.xml",
                                        language="java",
                                        external_dependencies=deps,
                                    )
                                )
                            except Exception:
                                pass

                    if pkgs:
                        workspaces.append(
                            WorkspaceInfo(
                                workspace_type="maven",
                                root_path=".",
                                manifest_file="pom.xml",
                                packages_count=len(pkgs),
                                packages=pkgs,
                                metadata={"modules": module_names},
                            )
                        )
            except Exception as e:
                logger.warning("maven_detection_failed", error=str(e))

        # 2. Gradle multi-project
        gradle_settings = root / "settings.gradle"
        if not gradle_settings.is_file():
            gradle_settings = root / "settings.gradle.kts"

        if gradle_settings.is_file():
            try:
                content = gradle_settings.read_text(encoding="utf-8")
                # Match: include 'foo', 'bar', ':core:api' or include("foo", "bar")
                matches = re.findall(r"include\s*\(?([^)\n]+)\)?", content)
                pkgs: List[PackageInfo] = []
                for match_group in matches:
                    raw_items = re.findall(r"['\"]([:a-zA-Z0-9_\-\.\/]+)['\"]", match_group)
                    for item in raw_items:
                        item_clean = item.lstrip(":").replace(":", "/")
                        pkg_dir = root / item_clean
                        if pkg_dir.is_dir() and (pkg_dir / "build.gradle").is_file() or (pkg_dir / "build.gradle.kts").is_file():
                            rel_path = str(pkg_dir.relative_to(root)).replace("\\", "/")
                            manifest_name = "build.gradle" if (pkg_dir / "build.gradle").is_file() else "build.gradle.kts"
                            pkgs.append(
                                PackageInfo(
                                    name=pkg_dir.name,
                                    path=rel_path,
                                    manifest_path=f"{rel_path}/{manifest_name}",
                                    language="java",
                                    external_dependencies=[],
                                )
                            )

                if pkgs:
                    workspaces.append(
                        WorkspaceInfo(
                            workspace_type="gradle",
                            root_path=".",
                            manifest_file=gradle_settings.name,
                            packages_count=len(pkgs),
                            packages=pkgs,
                        )
                    )
            except Exception as e:
                logger.warning("gradle_detection_failed", error=str(e))

        return workspaces

    def _detect_go_workspaces(self, root: Path) -> List[WorkspaceInfo]:
        """Detect Go workspaces (go.work) and multi-module repositories."""
        workspaces: List[WorkspaceInfo] = []
        go_work = root / "go.work"

        if go_work.is_file():
            try:
                content = go_work.read_text(encoding="utf-8")
                # Parse use (...) or use ./dir
                use_blocks = re.findall(r"use\s*\(([^)]+)\)", content)
                dirs_to_check: List[str] = []
                for block in use_blocks:
                    for line in block.splitlines():
                        line = line.strip().strip('"').strip("'")
                        if line and not line.startswith("//"):
                            dirs_to_check.append(line)

                single_use = re.findall(r"use\s+([^\s\(\)\n]+)", content)
                for item in single_use:
                    item_clean = item.strip().strip('"').strip("'")
                    if item_clean and item_clean not in dirs_to_check:
                        dirs_to_check.append(item_clean)

                pkgs: List[PackageInfo] = []
                for dir_path_str in dirs_to_check:
                    clean_dir = dir_path_str.lstrip("./")
                    target_dir = root / clean_dir if clean_dir else root
                    mod_file = target_dir / "go.mod"
                    if mod_file.is_file():
                        rel_path = str(target_dir.relative_to(root)).replace("\\", "/")
                        name, deps = self._parse_go_mod(mod_file)
                        pkgs.append(
                            PackageInfo(
                                name=name or (target_dir.name if rel_path != "." else "root"),
                                path=rel_path if rel_path != "." else ".",
                                manifest_path=f"{rel_path}/go.mod" if rel_path != "." else "go.mod",
                                language="go",
                                external_dependencies=deps,
                            )
                        )

                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="go_work",
                        root_path=".",
                        manifest_file="go.work",
                        packages_count=len(pkgs),
                        packages=pkgs,
                    )
                )
            except Exception as e:
                logger.warning("go_work_detection_failed", error=str(e))

        # Check for multiple go.mod files if no go.work
        if not workspaces:
            go_mods = list(root.glob("**/go.mod"))
            # Filter ignored directories
            go_mods = [g for g in go_mods if not any(part in {".git", "vendor", "node_modules"} for part in g.parts)]
            if len(go_mods) > 1:
                pkgs = []
                for g in go_mods:
                    mod_dir = g.parent
                    rel_path = str(mod_dir.relative_to(root)).replace("\\", "/")
                    name, deps = self._parse_go_mod(g)
                    pkgs.append(
                        PackageInfo(
                            name=name or (mod_dir.name if rel_path != "." else "root"),
                            path=rel_path if rel_path != "." else ".",
                            manifest_path=f"{rel_path}/go.mod" if rel_path != "." else "go.mod",
                            language="go",
                            external_dependencies=deps,
                        )
                    )
                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="go_multi_module",
                        root_path=".",
                        manifest_file=None,
                        packages_count=len(pkgs),
                        packages=pkgs,
                    )
                )

        return workspaces

    def _parse_go_mod(self, path: Path) -> Tuple[str, List[str]]:
        """Extract module name and direct required dependencies from go.mod."""
        mod_name = ""
        deps: List[str] = []
        try:
            content = path.read_text(encoding="utf-8")
            mod_match = re.search(r"^module\s+([^\s\n]+)", content, re.MULTILINE)
            if mod_match:
                mod_name = mod_match.group(1).strip()

            require_blocks = re.findall(r"require\s*\(([^)]+)\)", content)
            for block in require_blocks:
                for line in block.splitlines():
                    parts = line.strip().split()
                    if parts and not parts[0].startswith("//"):
                        deps.append(parts[0])

            single_requires = re.findall(r"^require\s+([^\s\n]+)", content, re.MULTILINE)
            for dep in single_requires:
                if dep not in deps and "(" not in dep:
                    deps.append(dep)
        except Exception:
            pass
        return mod_name, deps

    def _detect_python_workspaces(self, root: Path) -> List[WorkspaceInfo]:
        """Detect Python workspaces: uv workspace, poetry multi-package, or subprojects."""
        workspaces: List[WorkspaceInfo] = []
        root_pyproject = root / "pyproject.toml"

        if root_pyproject.is_file():
            try:
                data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
                # 1. uv workspace: [tool.uv.workspace] members = ["packages/*"]
                uv_ws = data.get("tool", {}).get("uv", {}).get("workspace", {})
                members = uv_ws.get("members", [])
                if members:
                    pkgs = self._find_python_packages(root, members)
                    if pkgs:
                        workspaces.append(
                            WorkspaceInfo(
                                workspace_type="uv",
                                root_path=".",
                                manifest_file="pyproject.toml",
                                packages_count=len(pkgs),
                                packages=pkgs,
                                metadata={"members": members},
                            )
                        )
            except Exception as e:
                logger.warning("python_workspace_detection_failed", error=str(e))

        # Check for multiple subproject pyproject.toml / setup.py
        if not workspaces:
            subprojects: List[Path] = []
            for p in root.glob("**/pyproject.toml"):
                if p != root_pyproject and not any(part in {".git", ".venv", "venv", "node_modules", "build", "dist"} for part in p.parts):
                    subprojects.append(p.parent)

            if len(subprojects) >= 2:
                pkgs = []
                for sp in subprojects:
                    rel_path = str(sp.relative_to(root)).replace("\\", "/")
                    pname, pver, pdeps = self._parse_pyproject(sp / "pyproject.toml")
                    pkgs.append(
                        PackageInfo(
                            name=pname or sp.name,
                            version=pver,
                            path=rel_path,
                            manifest_path=f"{rel_path}/pyproject.toml",
                            language="python",
                            external_dependencies=pdeps,
                        )
                    )
                workspaces.append(
                    WorkspaceInfo(
                        workspace_type="poetry" if any((sp / "poetry.lock").is_file() for sp in subprojects) else "python",
                        root_path=".",
                        manifest_file=None,
                        packages_count=len(pkgs),
                        packages=pkgs,
                    )
                )

        return workspaces

    def _find_python_packages(self, root: Path, patterns: List[str]) -> List[PackageInfo]:
        """Find subdirectories matching python member patterns containing pyproject.toml or setup.py."""
        packages: List[PackageInfo] = []
        seen_paths: Set[str] = set()

        for pattern in patterns:
            for match_dir in self._match_directories(root, pattern.rstrip("/")):
                if (match_dir / "pyproject.toml").is_file() or (match_dir / "setup.py").is_file():
                    rel_path = str(match_dir.relative_to(root)).replace("\\", "/")
                    if rel_path in seen_paths or rel_path == ".":
                        continue
                    seen_paths.add(rel_path)

                    manifest = "pyproject.toml" if (match_dir / "pyproject.toml").is_file() else "setup.py"
                    pname, pver, pdeps = self._parse_pyproject(match_dir / manifest) if manifest == "pyproject.toml" else (match_dir.name, None, [])
                    packages.append(
                        PackageInfo(
                            name=pname or match_dir.name,
                            version=pver,
                            path=rel_path,
                            manifest_path=f"{rel_path}/{manifest}",
                            language="python",
                            external_dependencies=pdeps,
                        )
                    )
        return packages

    def _parse_pyproject(self, path: Path) -> Tuple[str, Optional[str], List[str]]:
        """Parse pyproject.toml name, version, and dependencies."""
        name = ""
        version = None
        deps: List[str] = []
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            project = data.get("project", {})
            name = project.get("name", "")
            version = project.get("version")
            raw_deps = project.get("dependencies", [])
            for d in raw_deps:
                # Strip versions like 'requests>=2.0' -> 'requests'
                dep_name = re.split(r"[<>=!~;]", d)[0].strip()
                if dep_name:
                    deps.append(dep_name)

            # Poetry fallback
            poetry = data.get("tool", {}).get("poetry", {})
            if not name and "name" in poetry:
                name = poetry["name"]
                version = poetry.get("version")
                for k in poetry.get("dependencies", {}).keys():
                    if k != "python":
                        deps.append(k)
        except Exception:
            pass
        return name, version, deps

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _match_directories(self, root: Path, glob_pattern: str) -> List[Path]:
        """Match directories against a glob pattern safely."""
        matches: List[Path] = []
        try:
            for p in root.glob(glob_pattern):
                if p.is_dir() and not any(part.startswith(".") or part in {"node_modules", "target", "vendor"} for part in p.parts):
                    matches.append(p)
        except Exception:
            pass
        return matches

    def _cross_resolve_dependencies(self, workspaces: List[WorkspaceInfo], root: Path):
        """Cross-resolve internal workspace package dependencies from declared manifests."""
        all_packages: Dict[str, PackageInfo] = {}
        for ws in workspaces:
            for pkg in ws.packages:
                all_packages[pkg.name] = pkg

        # Also count source files enclosed in each package
        for ws in workspaces:
            for pkg in ws.packages:
                pkg_dir = root / pkg.path
                if pkg_dir.is_dir():
                    file_count = 0
                    for _, _, fnames in os.walk(pkg_dir):
                        file_count += len(fnames)
                    pkg.files_count = file_count

                # Partition dependencies into internal vs external
                internal = []
                external = []
                for dep in pkg.external_dependencies:
                    if dep in all_packages and dep != pkg.name:
                        internal.append(dep)
                    else:
                        external.append(dep)
                pkg.internal_dependencies = sorted(list(set(internal)))
                pkg.external_dependencies = sorted(list(set(external)))


# ===============================================================================
# Workspace Service
# ===============================================================================


class WorkspaceService:
    """Manages workspace persistence, graph querying, and package-level blast radius analysis."""

    def __init__(self, detector: Optional[MonorepoDetector] = None):
        self.detector = detector or MonorepoDetector()

    async def get_repository_for_user(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Repository:
        """Fetch repository enforcing tenancy."""
        stmt = select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
        repo = (await db.execute(stmt)).scalar_one_or_none()
        if not repo:
            raise NotFoundException("Repository", repository_id)
        return repo

    async def index_workspaces(
        self,
        repository_id: uuid.UUID,
        repo_path: Path,
        db: AsyncSession,
    ) -> WorkspaceIndexResponse:
        """Scan repository, index workspace and package graph entities into database."""
        start_time = time.time()
        repo_path = Path(repo_path)
        workspaces = self.detector.detect(repo_path)

        # 1. Clear previous workspace and package nodes & edges for this repository
        delete_nodes_stmt = delete(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repository_id,
            RepositoryGraphNode.node_type.in_(["WORKSPACE", "PACKAGE"]),
        )
        await db.execute(delete_nodes_stmt)
        await db.flush()

        indexed_packages_count = 0
        edges_created_count = 0

        # Query existing file nodes to link PACKAGE_CONTAINS edges
        file_nodes_stmt = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repository_id,
            RepositoryGraphNode.node_type == "FILE",
        )
        file_nodes = (await db.execute(file_nodes_stmt)).scalars().all()
        file_node_map: Dict[str, RepositoryGraphNode] = {fn.file_path: fn for fn in file_nodes if fn.file_path}

        package_node_map: Dict[str, RepositoryGraphNode] = {}

        # 2. Persist Workspace and Package Nodes
        for ws in workspaces:
            ws_qualified = f"workspace:{ws.workspace_type}:{ws.root_path}"
            ws_node = RepositoryGraphNode(
                repository_id=repository_id,
                node_type="WORKSPACE",
                qualified_name=ws_qualified,
                name=f"{ws.workspace_type}-workspace",
                file_path=ws.manifest_file,
                language="workspace",
                meta_info={
                    "workspace_type": ws.workspace_type,
                    "root_path": ws.root_path,
                    "manifest_file": ws.manifest_file,
                    "packages_count": len(ws.packages),
                    **ws.metadata,
                },
            )
            db.add(ws_node)
            await db.flush()
            ws.id = str(ws_node.id)

            for pkg in ws.packages:
                pkg_qualified = f"package:{pkg.language}:{pkg.name}"
                pkg_node = RepositoryGraphNode(
                    repository_id=repository_id,
                    node_type="PACKAGE",
                    qualified_name=pkg_qualified,
                    name=pkg.name,
                    file_path=pkg.path,
                    language=pkg.language,
                    meta_info={
                        "version": pkg.version,
                        "manifest_path": pkg.manifest_path,
                        "internal_dependencies": pkg.internal_dependencies,
                        "external_dependencies": pkg.external_dependencies,
                        "files_count": pkg.files_count,
                        **pkg.metadata,
                    },
                )
                db.add(pkg_node)
                await db.flush()
                pkg.id = str(pkg_node.id)
                package_node_map[pkg.name] = pkg_node
                indexed_packages_count += 1

                # Edge: WORKSPACE_CONTAINS -> PACKAGE
                ws_edge = RepositoryGraphEdge(
                    repository_id=repository_id,
                    source_node_id=ws_node.id,
                    target_node_id=pkg_node.id,
                    edge_type="WORKSPACE_CONTAINS",
                    confidence=1.0,
                    resolution_status="RESOLVED",
                )
                db.add(ws_edge)
                edges_created_count += 1

                # Edges: PACKAGE_CONTAINS -> FILE
                prefix = f"{pkg.path}/"
                for fpath, fnode in file_node_map.items():
                    if fpath.startswith(prefix) or fpath == pkg.path:
                        pkg_file_edge = RepositoryGraphEdge(
                            repository_id=repository_id,
                            source_node_id=pkg_node.id,
                            target_node_id=fnode.id,
                            edge_type="PACKAGE_CONTAINS",
                            confidence=1.0,
                            resolution_status="RESOLVED",
                        )
                        db.add(pkg_file_edge)
                        edges_created_count += 1

        # 3. Persist Cross-Package Dependency Edges
        for ws in workspaces:
            for pkg in ws.packages:
                source_node = package_node_map.get(pkg.name)
                if not source_node:
                    continue

                for dep_name in pkg.internal_dependencies:
                    target_node = package_node_map.get(dep_name)
                    if target_node:
                        dep_edge = RepositoryGraphEdge(
                            repository_id=repository_id,
                            source_node_id=source_node.id,
                            target_node_id=target_node.id,
                            edge_type="PACKAGE_DEPENDS_ON",
                            confidence=1.0,
                            resolution_status="RESOLVED",
                        )
                        db.add(dep_edge)
                        edges_created_count += 1

        await db.commit()
        duration = round(time.time() - start_time, 4)

        logger.info(
            "workspaces_indexed_successfully",
            repository_id=str(repository_id),
            workspaces_count=len(workspaces),
            packages_count=indexed_packages_count,
            edges_count=edges_created_count,
            duration=duration,
        )

        return WorkspaceIndexResponse(
            repository_id=str(repository_id),
            workspaces_found=len(workspaces),
            packages_indexed=indexed_packages_count,
            edges_created=edges_created_count,
            duration_seconds=duration,
            status="COMPLETED",
        )

    async def get_workspace_graph(
        self,
        repository_id: uuid.UUID,
        db: AsyncSession,
    ) -> WorkspaceGraphResponse:
        """Fetch complete workspace and package topology from database."""
        # Query workspace and package nodes
        stmt_nodes = select(RepositoryGraphNode).where(
            RepositoryGraphNode.repository_id == repository_id,
            RepositoryGraphNode.node_type.in_(["WORKSPACE", "PACKAGE"]),
        )
        nodes = (await db.execute(stmt_nodes)).scalars().all()

        ws_nodes = [n for n in nodes if n.node_type == "WORKSPACE"]
        pkg_nodes = [n for n in nodes if n.node_type == "PACKAGE"]
        pkg_node_by_id = {n.id: n for n in pkg_nodes}
        pkg_node_by_name = {n.name: n for n in pkg_nodes}

        # Query edges between packages and workspaces
        stmt_edges = select(RepositoryGraphEdge).where(
            RepositoryGraphEdge.repository_id == repository_id,
            RepositoryGraphEdge.edge_type.in_(["WORKSPACE_CONTAINS", "PACKAGE_DEPENDS_ON"]),
        )
        edges = (await db.execute(stmt_edges)).scalars().all()

        cross_package_edges: List[CrossPackageEdgeItem] = []
        ws_package_ids: Dict[uuid.UUID, List[uuid.UUID]] = defaultdict(list)

        for edge in edges:
            if edge.edge_type == "WORKSPACE_CONTAINS":
                ws_package_ids[edge.source_node_id].append(edge.target_node_id)
            elif edge.edge_type == "PACKAGE_DEPENDS_ON":
                source = pkg_node_by_id.get(edge.source_node_id)
                target = pkg_node_by_id.get(edge.target_node_id)
                if source and target:
                    cross_package_edges.append(
                        CrossPackageEdgeItem(
                            source_package=source.name,
                            target_package=target.name,
                            edge_type="PACKAGE_DEPENDS_ON",
                            confidence=edge.confidence,
                        )
                    )

        workspaces_list: List[WorkspaceInfo] = []
        all_ecosystems: Set[str] = set()

        for wsn in ws_nodes:
            meta = dict(wsn.meta_info or {})
            ws_type = meta.get("workspace_type", "unknown")
            all_ecosystems.add(ws_type)

            child_pkgs: List[PackageInfo] = []
            for pid in ws_package_ids.get(wsn.id, []):
                pnode = pkg_node_by_id.get(pid)
                if pnode:
                    pmeta = dict(pnode.meta_info or {})
                    child_pkgs.append(
                        PackageInfo(
                            id=str(pnode.id),
                            name=pnode.name,
                            version=pmeta.get("version"),
                            path=pnode.file_path or "",
                            manifest_path=pmeta.get("manifest_path", ""),
                            language=pnode.language or "unknown",
                            internal_dependencies=pmeta.get("internal_dependencies", []),
                            external_dependencies=pmeta.get("external_dependencies", []),
                            files_count=pmeta.get("files_count", 0),
                            metadata=pmeta,
                        )
                    )

            workspaces_list.append(
                WorkspaceInfo(
                    id=str(wsn.id),
                    workspace_type=ws_type,
                    root_path=meta.get("root_path", "."),
                    manifest_file=wsn.file_path,
                    packages_count=len(child_pkgs),
                    packages=child_pkgs,
                    metadata=meta,
                )
            )

        summary = WorkspaceSummary(
            total_workspaces=len(workspaces_list),
            total_packages=len(pkg_nodes),
            ecosystems=sorted(list(all_ecosystems)),
            is_monorepo=len(pkg_nodes) > 1 or len(workspaces_list) > 0,
        )

        return WorkspaceGraphResponse(
            repository_id=str(repository_id),
            workspaces=workspaces_list,
            cross_package_edges=cross_package_edges,
            summary=summary,
        )

    async def get_package_dependencies(
        self,
        repository_id: uuid.UUID,
        package_id: str,
        db: AsyncSession,
    ) -> PackageDependenciesResponse:
        """Fetch upstream dependencies and downstream dependents for a specific package."""
        target_node: Optional[RepositoryGraphNode] = None
        try:
            p_uuid = uuid.UUID(package_id)
            target_node = (
                await db.execute(
                    select(RepositoryGraphNode).where(
                        RepositoryGraphNode.id == p_uuid,
                        RepositoryGraphNode.repository_id == repository_id,
                        RepositoryGraphNode.node_type == "PACKAGE",
                    )
                )
            ).scalar_one_or_none()
        except ValueError:
            target_node = (
                await db.execute(
                    select(RepositoryGraphNode).where(
                        RepositoryGraphNode.name == package_id,
                        RepositoryGraphNode.repository_id == repository_id,
                        RepositoryGraphNode.node_type == "PACKAGE",
                    )
                )
            ).scalar_one_or_none()

        if not target_node:
            raise NotFoundException("Package", package_id)

        meta = dict(target_node.meta_info or {})
        internal_dep_names = meta.get("internal_dependencies", [])
        external_deps = meta.get("external_dependencies", [])

        # Fetch internal dependency package objects
        internal_pkgs: List[PackageInfo] = []
        if internal_dep_names:
            dep_nodes = (
                await db.execute(
                    select(RepositoryGraphNode).where(
                        RepositoryGraphNode.repository_id == repository_id,
                        RepositoryGraphNode.node_type == "PACKAGE",
                        RepositoryGraphNode.name.in_(internal_dep_names),
                    )
                )
            ).scalars().all()
            for dn in dep_nodes:
                dmeta = dict(dn.meta_info or {})
                internal_pkgs.append(
                    PackageInfo(
                        id=str(dn.id),
                        name=dn.name,
                        version=dmeta.get("version"),
                        path=dn.file_path or "",
                        manifest_path=dmeta.get("manifest_path", ""),
                        language=dn.language or "unknown",
                        internal_dependencies=dmeta.get("internal_dependencies", []),
                        external_dependencies=dmeta.get("external_dependencies", []),
                        files_count=dmeta.get("files_count", 0),
                    )
                )

        # Query downstream dependents (packages that have PACKAGE_DEPENDS_ON pointing to target_node)
        dependent_edges = (
            await db.execute(
                select(RepositoryGraphEdge).where(
                    RepositoryGraphEdge.repository_id == repository_id,
                    RepositoryGraphEdge.target_node_id == target_node.id,
                    RepositoryGraphEdge.edge_type == "PACKAGE_DEPENDS_ON",
                )
            )
        ).scalars().all()

        dependents: List[PackageInfo] = []
        if dependent_edges:
            source_ids = [e.source_node_id for e in dependent_edges]
            consumer_nodes = (
                await db.execute(
                    select(RepositoryGraphNode).where(
                        RepositoryGraphNode.id.in_(source_ids),
                    )
                )
            ).scalars().all()
            for cn in consumer_nodes:
                cmeta = dict(cn.meta_info or {})
                dependents.append(
                    PackageInfo(
                        id=str(cn.id),
                        name=cn.name,
                        version=cmeta.get("version"),
                        path=cn.file_path or "",
                        manifest_path=cmeta.get("manifest_path", ""),
                        language=cn.language or "unknown",
                        internal_dependencies=cmeta.get("internal_dependencies", []),
                        external_dependencies=cmeta.get("external_dependencies", []),
                        files_count=cmeta.get("files_count", 0),
                    )
                )

        return PackageDependenciesResponse(
            package_id=str(target_node.id),
            package_name=target_node.name,
            package_path=target_node.file_path or "",
            internal_dependencies=internal_pkgs,
            external_dependencies=external_deps,
            dependents=dependents,
        )

    async def get_package_impact(
        self,
        repository_id: uuid.UUID,
        package_id: str,
        db: AsyncSession,
    ) -> PackageImpactResponse:
        """Compute blast radius and affected packages if a package undergoes changes."""
        deps_resp = await self.get_package_dependencies(repository_id, package_id, db)

        # Traverse reverse package dependencies (consumers of consumers)
        visited: Set[str] = set()
        queue: deque = deque([(deps_resp.package_name, deps_resp.package_path, 0, [deps_resp.package_name])])
        affected: List[AffectedPackageItem] = []
        total_files = 0

        # Query all package edges in repository for BFS traversal
        edges = (
            await db.execute(
                select(RepositoryGraphEdge).where(
                    RepositoryGraphEdge.repository_id == repository_id,
                    RepositoryGraphEdge.edge_type == "PACKAGE_DEPENDS_ON",
                )
            )
        ).scalars().all()

        nodes = (
            await db.execute(
                select(RepositoryGraphNode).where(
                    RepositoryGraphNode.repository_id == repository_id,
                    RepositoryGraphNode.node_type == "PACKAGE",
                )
            )
        ).scalars().all()

        node_map = {n.id: n for n in nodes}
        name_to_node = {n.name: n for n in nodes}

        # Build reverse adjacency map: depended_name -> [consumer_nodes]
        reverse_graph: Dict[str, List[RepositoryGraphNode]] = defaultdict(list)
        for e in edges:
            source = node_map.get(e.source_node_id)  # consumer
            target = node_map.get(e.target_node_id)  # depended
            if source and target:
                reverse_graph[target.name].append(source)

        visited.add(deps_resp.package_name)

        while queue:
            curr_name, curr_path, depth, path = queue.popleft()
            if depth > 0:
                affected.append(
                    AffectedPackageItem(
                        package_name=curr_name,
                        package_path=curr_path,
                        depth=depth,
                        dependency_path=path,
                    )
                )

            # Traverse consumers
            for consumer in reverse_graph.get(curr_name, []):
                if consumer.name not in visited:
                    visited.add(consumer.name)
                    total_files += (consumer.meta_info or {}).get("files_count", 0)
                    queue.append(
                        (
                            consumer.name,
                            consumer.file_path or "",
                            depth + 1,
                            path + [consumer.name],
                        )
                    )

        affected_count = len(affected)
        severity = "LOW"
        if affected_count >= 5:
            severity = "CRITICAL"
        elif affected_count >= 3:
            severity = "HIGH"
        elif affected_count >= 1:
            severity = "MEDIUM"

        recommendations = [
            f"Run integration test suites for affected consumer packages: {', '.join(a.package_name for a in affected[:4])}"
            if affected else "Safe local change; no downstream internal packages depend on this package.",
        ]
        if affected_count >= 3:
            recommendations.append("Consider publishing a backwards-compatible minor release to prevent breaking consumer packages.")

        return PackageImpactResponse(
            package_id=deps_resp.package_id,
            package_name=deps_resp.package_name,
            severity=severity,
            affected_packages=affected,
            affected_packages_count=affected_count,
            affected_files_count=total_files,
            recommendations=recommendations,
        )

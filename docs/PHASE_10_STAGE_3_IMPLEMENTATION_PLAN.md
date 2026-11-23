# Phase 10 Stage 10.3 Implementation Plan
## Monorepo & Workspace Intelligence Engine + Mandatory Security Audit and Hardening

**Target Stage:** Phase 10, Stage 10.3  
**Components:**
1. Part A: Mandatory Security Audit & Hardening (Completed & Verified)
2. Part B: Monorepo & Workspace Intelligence Engine
3. Part C: Agent & Reliability Integration
4. Part D: Next.js SaaS UI & Documentation

---

## 1. System Architecture & Design

### 1.1 Multi-Language Workspace & Package Detection
The `MonorepoDetector` inspects repository file structures and manifest definitions across 5 major ecosystem families:

1. **JavaScript / TypeScript**:
   - `pnpm-workspace.yaml`: YAML-based package glob parsing (`packages/*`, `apps/*`).
   - `package.json`: NPM / Yarn workspaces (`workspaces: [...]` or `workspaces: { packages: [...] }`).
   - `turbo.json`: Turborepo pipeline orchestration.
   - `nx.json`: Nx workspace graph configurations.
   - `lerna.json`: Lerna multi-package repositories.

2. **Python**:
   - `pyproject.toml` with `[tool.uv.workspace]`, `[tool.poetry]`, or `[tool.pdm]`.
   - Multi-package root configurations containing subproject `pyproject.toml` / `setup.py`.

3. **Rust**:
   - `Cargo.toml` with `[workspace]` and `members = [...]`.

4. **Java / JVM**:
   - Maven root `pom.xml` with `<modules><module>...</module></modules>`.
   - Gradle `settings.gradle` / `settings.gradle.kts` with `include '...'`.

5. **Go**:
   - `go.work` multi-module declarations (`use (...)`).
   - Discovered `go.mod` submodules.

### 1.2 Persistent Graph Representation
Extends Stage 10.1 `RepositoryGraphNode` and `RepositoryGraphEdge`:
- **Nodes**:
  - `WORKSPACE`: Root workspace descriptor with metadata (`workspace_type`, `root_path`, `manifest_file`).
  - `PACKAGE`: Discovered package/module entity with metadata (`name`, `version`, `path`, `language`, `internal_deps`, `external_deps`).
- **Edges**:
  - `WORKSPACE_CONTAINS`: Directional edge from `WORKSPACE` to `PACKAGE`.
  - `PACKAGE_DEPENDS_ON`: Directional edge from consuming `PACKAGE` to depended `PACKAGE`.
  - `PACKAGE_CONTAINS`: Directional edge from `PACKAGE` to constituent `FILE` nodes.

### 1.3 Workspace-Aware Blast Radius Traversal
When `ImpactAnalysisService` calculates blast radius:
- Discovers the enclosing package for each target and impacted file.
- Traces cross-package consumer dependencies.
- Quantifies cross-package coupling impact in the deterministic impact score.
- Reports `affected_packages` and `cross_package_boundaries` boolean in API responses.

---

## 2. Implementation Steps

1. **Schemas (`backend/app/schemas/workspace.py`)**:
   - Define Pydantic models for workspaces, packages, dependencies, and impact.
   - Export in `backend/app/schemas/__init__.py`.

2. **Detection & Service (`backend/app/services/workspace_service.py`)**:
   - Implement `MonorepoDetector` with full regex and parser support for all 5 ecosystems.
   - Implement `WorkspaceService` with async database persistence into `RepositoryGraphNode` and `RepositoryGraphEdge`.
   - Support reverse dependency queries (dependents) and package impact calculation.

3. **Impact Analysis Enhancement (`backend/app/services/impact_analysis_service.py` & `schemas/impact.py`)**:
   - Add `affected_packages` and `cross_package_boundaries` fields to `ImpactAnalysisResponse`.
   - Correlate impacted files to package nodes in `ImpactAnalysisService`.

4. **REST API Endpoints (`backend/app/api/v1/workspaces.py`)**:
   - `GET /repositories/{id}/workspaces`
   - `GET /repositories/{id}/workspaces/{workspace_id}`
   - `GET /repositories/{id}/packages`
   - `GET /repositories/{id}/packages/{package_id}/dependencies`
   - `GET /repositories/{id}/packages/{package_id}/dependents`
   - `GET /repositories/{id}/packages/{package_id}/impact`
   - `POST /repositories/{id}/workspaces/index`
   - Register in `backend/app/api/v1/router.py`.

5. **Agent & Reliability Integration**:
   - Enhance `security_reviewer.py` to evaluate workspace manifests and secret status.
   - Update `ReliabilityService` and schemas to return Security Health metrics.
   - Add security card to `/reliability`.

6. **Frontend UI**:
   - Create `frontend/src/services/workspace-service.ts`.
   - Build `frontend/src/components/repository/workspace-intelligence-tab.tsx`.
   - Integrate into `frontend/src/app/repositories/[id]/page.tsx`.

7. **Verification & Regression Testing**:
   - Unit tests for monorepo detection (`test_monorepo_detector.py`).
   - Unit tests for workspace service (`test_workspace_service.py`).
   - Integration tests for workspace API (`test_workspace_api.py`).
   - Full regression suite execution ($\ge 285$ tests).
   - Frontend Next.js build compilation (16/16 routes).

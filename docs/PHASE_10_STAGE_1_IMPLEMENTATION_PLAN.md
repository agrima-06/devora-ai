# Devora AI — Phase 10, Stage 10.1 Implementation Plan
## Cross-File Symbol and Dependency Graph Engine

**Date:** 2026-11-19  
**Phase:** 10 — Advanced Repository Intelligence  
**Stage:** 10.1 — Cross-File Symbol and Dependency Graph Foundation  
**Status:** Approved for Implementation  
**Baseline:** Backend 258 passed, 0 failed, 3 skipped; Frontend 16/16 routes compiled cleanly; Migration head `011_model_gateway_resilience`.

---

## 1. Existing Architecture Findings

Devora AI already possesses foundational repository intelligence systems that Stage 10.1 must extend rather than duplicate:

1. **Repository Filesystem Scanner (`RepositoryScanner` in `backend/app/services/scanner_service.py`):**
   - Traverses filesystems with `.gitignore` compliance, binary file filtering (`.png`, `.pyc`, `.dll`, etc.), sensitive pattern blocking (`*.env`, `*.pem`, `id_rsa`, etc.), and ignored directory pruning (`node_modules`, `.git`, `.venv`, etc.).
   - Classifies language by extension for 23+ languages (Python, TypeScript, JavaScript, Go, Java, Rust, etc.).
   - Computes line counts, file size limits (1.5 MB), and identifies manifests (`requirements.txt`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`).
2. **Code Parser (`CodeParserService` in `backend/app/services/parser_service.py`):**
   - Python AST parser (`PythonASTVisitor`): extracts classes, inheritance bases, functions, async functions, methods, docstrings, signatures, line ranges, imports (`ast.Import`, `ast.ImportFrom`), and function calls (`ast.Call`).
   - Tree-sitter multi-language parser (`TS_PARSERS`): supports Python, JavaScript, TypeScript, TSX, Go, Java. Extracts function declarations, class declarations, interface declarations, method declarations, and import statements.
   - Generates file-level summaries and collects symbol lists.
3. **Repository Intelligence Service (`RepositoryIntelligenceService` in `backend/app/services/repo_intelligence_service.py`):**
   - Coordinates Git cloning/updating via `GitHubService`.
   - Records metadata in `repository_files` and `indexing_jobs`.
   - Generates pseudo-random deterministic vector embeddings for semantic search and saves symbol-level documentation in `repository_knowledge`.
4. **Code Search Service (`CodeSearchService` in `backend/app/services/search_service.py`):**
   - Performs symbol matching against `repository_knowledge` (`symbol_type IN ('function', 'class', 'method', 'interface')`).
   - Supports keyword search and semantic cosine similarity search.
5. **Database Models & Alembic State:**
   - Database: PostgreSQL 16 with pgvector support (`VectorType(768)`).
   - Alembic head revision: `011_model_gateway_resilience`.
   - Existing tables include `repositories`, `repository_files`, `repository_knowledge`, `indexing_jobs`. Currently, symbols in `repository_knowledge` are isolated text records with embeddings, lacking relational edges, module hierarchies, resolution confidence, cross-file import links, and topological traversal capabilities.

---

## 2. Current Symbol Extraction Capabilities & Gaps

| Language | Parser | Symbols Extracted | Imports Extracted | Calls Extracted | Semantic Resolution |
|---|---|---|---|---|---|
| **Python** | Python AST (`ast`) | Classes, Functions, Methods, Bases | `import X`, `from X import Y`, relative imports (`..`) | Name/Attribute calls | Syntactic + Local Module Resolution |
| **JavaScript / TypeScript** | Tree-sitter (`tree_sitter_javascript`, `tree_sitter_typescript`) | Classes, Interfaces, Functions, Arrow Functions, Methods | `import ... from ...` | None currently | Syntactic + Local File Resolution |
| **Go** | Tree-sitter (`tree_sitter_go`) | Functions, Methods, Structs | `import "..."` | None currently | Syntactic + Local Package Resolution |
| **Java** | Tree-sitter (`tree_sitter_java`) | Methods, Classes | `import ...` | None currently | Syntactic + Local Package Resolution |
| **Rust** | Regex/Syntactic Fallback | `fn`, `struct`, `enum`, `impl` | `use ...` | None currently | Syntactic |

### Critical Gaps Addressed in Stage 10.1:
- Existing `repository_knowledge` treats symbols as independent text chunks for vector/keyword retrieval.
- No cross-file relationship representation exists: an import of `calculator.MathEngine` in `tests/test_calc.py` is not linked to `src/calculator.py:MathEngine`.
- No representation of Directory, File, Module, Class hierarchy (`CONTAINS`, `DEFINES`).
- No queryable dependency edges (`IMPORTS`, `DEPENDS_ON`, `INHERITS`, `REFERENCES`, `CALLS`).
- No concept of resolution confidence (`RESOLVED`, `UNRESOLVED`, `EXTERNAL`, `AMBIGUOUS`).

---

## 3. Proposed Core Graph Architecture

### 3.1 Node Types
1. `REPOSITORY`: Root repository node representing the codebase root.
2. `DIRECTORY`: Subdirectory containers (`src/`, `tests/`, etc.).
3. `FILE`: Source-code or configuration file entity.
4. `MODULE`: Language module namespace (e.g. `src.calculator` in Python, package in Go).
5. `PACKAGE`: External or internal package boundary.
6. `CLASS`: Class definition (with base classes in metadata).
7. `INTERFACE`: Interface definition (TS, Java, Go).
8. `FUNCTION`: Module-level function.
9. `METHOD`: Class- or struct-associated method.
10. `VARIABLE` / `CONSTANT`: Module-level constant or exported variable.

### 3.2 Edge Types
1. `CONTAINS`: Structural hierarchy (Repository -> Directory -> File).
2. `DEFINES`: Scope definition (File/Module -> Class/Function, Class -> Method).
3. `IMPORTS`: Cross-file or external dependency (File -> Module/File/Symbol).
4. `DEPENDS_ON`: High-level module/file inter-dependency derived from imports.
5. `INHERITS`: Class inheritance relationship (Subclass -> BaseClass).
6. `IMPLEMENTS`: Class interface implementation.
7. `REFERENCES`: Explicit symbol reference across files.
8. `CALLS`: Static function/method invocation where resolution is verifiable.

### 3.3 Provenance, Confidence, and Resolution Status
- `confidence`: Float between `0.0` and `1.0`.
  - Direct local import resolving to single file/symbol: `1.0`.
  - Relative import (`from .utils import helper`): `0.95`.
  - External package import (`import fastapi`): `1.0` (flagged as `EXTERNAL`).
  - Syntactic call name match: `0.5` (marked as `INFERRED` / `AMBIGUOUS`).
- `resolution_status`:
  - `RESOLVED`: Target node in local repository identified and linked (`target_node_id` populated).
  - `EXTERNAL`: Resolved to third-party or standard library dependency (`target_node_id` is null; `target_symbol` retains external package name).
  - `UNRESOLVED`: Import or reference target cannot be located in local workspace or known libraries.
  - `AMBIGUOUS`: Multiple candidate symbols match target name in local repo.

---

## 4. Database Design & Migration Strategy

We introduce two dedicated PostgreSQL tables designed for high-concurrency, indexed lookups and bounded graph traversal.

### 4.1 Schema Definition
```sql
-- 1. Repository Graph Nodes
CREATE TABLE repository_graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    node_type VARCHAR(50) NOT NULL, -- REPOSITORY, DIRECTORY, FILE, MODULE, CLASS, FUNCTION, METHOD, VARIABLE
    qualified_name VARCHAR(1000) NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_path TEXT,
    language VARCHAR(50),
    start_line INTEGER,
    end_line INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_repo_node_qualified UNIQUE (repository_id, qualified_name)
);

CREATE INDEX ix_repo_graph_nodes_repo_type ON repository_graph_nodes(repository_id, node_type);
CREATE INDEX ix_repo_graph_nodes_repo_file ON repository_graph_nodes(repository_id, file_path);
CREATE INDEX ix_repo_graph_nodes_qualified ON repository_graph_nodes(repository_id, qualified_name);

-- 2. Repository Graph Edges
CREATE TABLE repository_graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    source_node_id UUID NOT NULL REFERENCES repository_graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID REFERENCES repository_graph_nodes(id) ON DELETE CASCADE,
    edge_type VARCHAR(50) NOT NULL, -- CONTAINS, DEFINES, IMPORTS, DEPENDS_ON, INHERITS, IMPLEMENTS, REFERENCES, CALLS
    confidence FLOAT NOT NULL DEFAULT 1.0,
    resolution_status VARCHAR(50) NOT NULL DEFAULT 'RESOLVED', -- RESOLVED, EXTERNAL, UNRESOLVED, AMBIGUOUS
    target_symbol VARCHAR(500),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_repo_graph_edge UNIQUE (repository_id, source_node_id, target_node_id, edge_type, target_symbol)
);

CREATE INDEX ix_repo_graph_edges_repo_source ON repository_graph_edges(repository_id, source_node_id);
CREATE INDEX ix_repo_graph_edges_repo_target ON repository_graph_edges(repository_id, target_node_id);
CREATE INDEX ix_repo_graph_edges_repo_type ON repository_graph_edges(repository_id, edge_type);
CREATE INDEX ix_repo_graph_edges_resolution ON repository_graph_edges(repository_id, resolution_status);
```

### 4.2 Alembic Migration
- New migration: `012_repository_dependency_graph.py` with `down_revision = "011_model_gateway_resilience"`.
- Backward compatible: Zero disruption to existing `repositories`, `repository_files`, or `repository_knowledge` tables.

---

## 5. Indexing & Incremental Update Strategy

### 5.1 Content-Hash Tracking & Change Detection
- For every file during scan: compute SHA-256 content hash `content_hash = hashlib.sha256(content_bytes).hexdigest()`.
- Compare against existing `RepositoryGraphNode` records where `node_type = 'FILE'` and `file_path = rel_path`.
- **Three Actions:**
  1. **Unchanged File (`existing.content_hash == current_hash`):** Skip AST reparsing and graph node recreation. Retain all child symbols and outgoing edges.
  2. **Changed File (`existing.content_hash != current_hash`):**
     - Delete existing child nodes (`DEFINES` edges) and outgoing edges (`source_node_id == file_node.id`).
     - Reparse file, re-extract symbols, create updated nodes, and re-resolve local/external edges.
     - Update file node `content_hash` and timestamps.
  3. **Deleted File (present in DB graph, missing on disk):**
     - Cascade delete file node and all child symbol nodes. Foreign key constraints automatically clean up incoming/outgoing edges.

### 5.2 Two-Pass Cross-File Resolution
- **Pass 1 (Symbol Declaration):** Parse all changed/new files; insert `FILE`, `CLASS`, `FUNCTION`, `METHOD` nodes. Build in-memory lookup maps:
  - `file_by_module`: e.g., `src.calculator` -> `src/calculator.py`
  - `symbol_by_qualified`: e.g., `src/calculator.py:MathEngine` -> node UUID
  - `symbols_by_name`: e.g., `MathEngine` -> list of node UUIDs
- **Pass 2 (Relationship Resolution):**
  - Resolve Python `from .calculator import MathEngine`:
    1. Resolve relative directory of source file.
    2. Match target module file `src/calculator.py`.
    3. Match exported symbol `MathEngine` in target file.
    4. If found: insert `IMPORTS` edge (`source=source_file_id`, `target=symbol_id`, `status='RESOLVED'`).
    5. Also add high-level `DEPENDS_ON` edge between the two files.
  - Resolve JS/TS `import { formatResult } from './formatter'`:
    1. Resolve relative path `./formatter` with extensions (`.ts`, `.tsx`, `.js`, `/index.ts`).
    2. Link to target file node and symbol node.
  - If module is third-party (e.g. `fastapi`, `react`, `github.com/gin-gonic/gin`):
    - Record edge with `target_node_id = NULL`, `target_symbol = "fastapi"`, `resolution_status = 'EXTERNAL'`, `confidence = 1.0`.
  - If local target cannot be found:
    - Record edge with `target_node_id = NULL`, `target_symbol = target_str`, `resolution_status = 'UNRESOLVED'`, `confidence = 0.0`.

---

## 6. Graph Query Service (`RepositoryGraphService`)

Located in `backend/app/services/graph_service.py`:
- `get_graph_overview(repository_id, user)`: Returns total nodes, total edges, breakdown by node type, breakdown by language, unresolved count, last indexed commit and timestamp.
- `get_nodes(repository_id, user, node_type, language, file_path, search_query, limit, offset)`: Paginated node search.
- `get_node_detail(repository_id, node_id, user)`: Fetches node details plus direct incoming and outgoing edges with peer node metadata.
- `get_dependencies(repository_id, user, root_node_id, direction, max_depth, edge_types, limit)`: Bounded BFS/DFS traversal (default `max_depth = 2`, max `5`, limit `100`) returning subgraph of nodes and edges without unbounded memory overhead.
- `get_unresolved_references(repository_id, user, limit, offset)`: Returns list of unresolved imports and references with source files and line numbers.

---

## 7. API Design

Exposed under `/api/v1/repositories/{repository_id}/graph`:

1. `GET /api/v1/repositories/{repository_id}/graph`
   - Returns `RepositoryGraphSummaryResponse`: `nodes_count`, `edges_count`, `node_types_breakdown`, `edge_types_breakdown`, `languages_breakdown`, `unresolved_count`, `last_indexed_at`.
2. `POST /api/v1/repositories/{repository_id}/graph/index`
   - Payload: `{"force_reindex": false}`
   - Triggers incremental or full graph indexing, returns `GraphIndexingResponse` with execution statistics (`nodes_created`, `edges_created`, `files_indexed`, `files_skipped`).
3. `GET /api/v1/repositories/{repository_id}/graph/nodes`
   - Query params: `node_type`, `language`, `file_path`, `q`, `limit` (default 50), `offset`.
   - Returns `GraphNodesListResponse`.
4. `GET /api/v1/repositories/{repository_id}/graph/nodes/{node_id}`
   - Returns `GraphNodeDetailResponse` with incoming/outgoing relationships.
5. `GET /api/v1/repositories/{repository_id}/graph/dependencies`
   - Query params: `node_id`, `direction` (`outgoing`, `incoming`, `both`), `max_depth` (1-5, default 2), `edge_type`.
   - Returns `GraphDependenciesResponse` with nodes and edges.
6. `GET /api/v1/repositories/{repository_id}/graph/unresolved`
   - Query params: `limit`, `offset`.
   - Returns `GraphUnresolvedReferencesResponse`.

---

## 8. Frontend Integration

In `frontend/src/app/repositories/[id]/page.tsx`:
- Add `"graph"` tab alongside `"architecture"`, `"search"`, `"files"`, `"tasks"`, `"branches"`, `"pull_requests"`.
- Dependency Graph Tab features:
  - **Graph Summary Header:** Total nodes, total edges, unresolved reference counter, re-index button with loading state.
  - **Language & Node Type Badges:** Breakdown pills (Classes, Functions, Files, Modules).
  - **Interactive Dependency Visualizer:**
    - SVG-based interactive canvas with zoom in/out, pan, node selection, edge arrows, and type-based node coloring.
    - Node search input to focus on specific files or symbols.
    - Depth control slider (Depth: 1, 2, 3).
    - Node type filter toggles (Files, Classes, Functions).
  - **Side Inspector Panel:**
    - Detailed inspector when a node is selected showing qualified name, file path, line numbers, outgoing dependencies (what it imports/calls), and incoming dependencies (what imports/calls it).
  - **Unresolved Dependencies Drawer:** List of external packages and unresolvable local references.

---

## 9. Testing Strategy

1. **Unit Tests (`backend/tests/unit/test_graph_engine.py`):**
   - AST node and symbol extraction with qualified naming (`test_calc.py:MathEngine.compute_sum`).
   - Python relative import resolution (`.calculator` -> `src/calculator.py`).
   - External library detection (`fastapi`, `pytest` -> `EXTERNAL`).
   - Content hash change detection (`hash_unchanged -> skip`, `hash_changed -> reindex`).
   - Bounded BFS depth traversal (stops strictly at `max_depth`).
   - Malformed file syntax error handling (marks syntax invalid, does not crash indexer).
2. **Integration Tests (`backend/tests/integration/test_dependency_graph_api.py`):**
   - Multi-file repository fixture (multi-module Python with imports, base classes, callers).
   - Full repository graph indexing idempotency (`POST /graph/index`).
   - File modification and incremental reindexing (only modified file is re-parsed).
   - Node and dependency query endpoints (`GET /graph/nodes`, `GET /graph/dependencies`).
   - Cross-tenant repository isolation (user A cannot query user B's graph).
   - Unresolved reference query endpoint (`GET /graph/unresolved`).
3. **Regression Tests:**
   - Full backend pytest suite: ensure all existing 258 passed tests remain 100% passing.
   - Frontend build: `npm run build` must compile 16/16 routes with 0 errors.

---

## 10. Risks & Limitations

1. **Risk:** Unbounded graph traversal causing high latency or memory spikes on large repositories.
   - **Mitigation:** Strict `max_depth` clamping ($\le 5$) and maximum node limits per traversal query ($\le 100$).
2. **Risk:** Dynamic imports (e.g. `importlib.import_module(var)`) cannot be statically resolved.
   - **Mitigation:** Accurately marked as `UNRESOLVED` with `confidence = 0.0`. Never fabricate fake relationships.
3. **Risk:** Tree-sitter parser availability on different host environments.
   - **Mitigation:** Graceful degradation. If a Tree-sitter grammar is missing, fall back to regex/syntactic scanner without crashing.
4. **Risk:** Multi-worker race conditions during re-indexing.
   - **Mitigation:** Atomic database transactions and checking `repo.indexing_status` before starting concurrent indexing.

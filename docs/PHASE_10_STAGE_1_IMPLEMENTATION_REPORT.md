# Devora AI — Phase 10 Stage 10.1 Implementation Report
## Cross-File Symbol and Dependency Graph Engine

**Date:** November 19, 2026  
**Status:** COMPLETED & VERIFIED  
**Regression Baseline:** 269 passed, 0 failed, 3 skipped  
**Frontend Compilation:** 16/16 routes compiled successfully  
**Database Migration:** `012_repository_dependency_graph` (Applied & Verified)  

---

## 1. Executive Summary

Phase 10 introduces **Advanced Repository Intelligence** to Devora AI. **Stage 10.1** establishes the core foundational layer: a persistent, queryable, multi-language cross-file symbol and dependency graph engine. 

Prior to Stage 10.1, repository exploration in Devora AI was limited to flat file listings, simple string/regex lookups, and basic token-level symbol parsing without relational semantic linking. Stage 10.1 solves this by creating a relational knowledge graph of codebases in PostgreSQL. It extracts files, modules, classes, interfaces, functions, methods, variables, and constants across languages (Python, JavaScript, TypeScript, Go, Java, and Rust fallback), maps dependencies, imports, inheritance, containment, and call chains, indexes them incrementally via SHA-256 content hashing, and exposes them through authenticated REST APIs and an interactive Next.js visualizer.

### Key Achievements:
1. **Persistent Relational Graph Models & Migration:** Created `RepositoryGraphNode` and `RepositoryGraphEdge` with 11 node types, 8 edge types, and 4 resolution statuses, backed by Alembic migration `012_repository_dependency_graph`.
2. **Multi-Language AST & Tree-Sitter Parsers:** Built `GraphExtractor` with native Python `ast` visitor and `tree-sitter` grammars for JavaScript, TypeScript, TSX, Go, and Java, plus syntactic pattern matching for Rust.
3. **Content-Hash Incremental Indexing Engine:** Full and incremental graph indexing using SHA-256 digests. Only changed or new files are parsed; unchanged files are skipped with zero DB mutations, providing idempotent, high-speed re-indexing.
4. **Bounded Traversal & Query Service:** Breadth-first search (BFS) graph traversal with circular dependency detection, path aggregation, and configurable depth limits ($1 \le d \le 5$).
5. **Background Pipeline Integration:** Fully hooked into `RepoIntelligenceService` so that normal repository indexing automatically builds and maintains the dependency graph.
6. **Unified REST API Suite:** Six authenticated endpoints under `/api/v1/repositories/{id}/graph` providing graph summary, on-demand indexing, node search, node neighborhood details, bounded traversal, and unresolved reference auditing.
7. **Interactive Frontend Visualizer:** Implemented the "Dependency Graph" tab in Next.js (`/repositories/[id]`) featuring an interactive SVG canvas with zoom/pan, radial layout distribution, node filtering, traversal depth controls, and an inspection drawer.
8. **100% Verification:** 11 new tests authored (5 unit, 6 integration), bringing the regression baseline to **269 passed, 0 failed, 3 skipped**, with 16/16 Next.js routes building cleanly.

---

## 2. Architectural Design & Implementation

```
+---------------------------------------------------------------------------------------------------+
|                                      DEVORA AI GRAPH ENGINE                                        |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|   +-----------------------+      +-------------------------+      +---------------------------+   |
|   |   Python AST Parser   |      |   Tree-Sitter Parsers   |      |     Syntactic Fallback    |   |
|   |  - Classes & Bases    |      |  - JavaScript / TSX     |      |  - Rust mod / use / fn    |   |
|   |  - Functions & Methods|      |  - Go packages & funcs  |      |  - (Disclosed as regex)   |   |
|   |  - Relative Imports   |      |  - Java classes & funcs |      |                           |   |
|   +-----------+-----------+      +------------+------------+      +-------------+-------------+   |
|               |                               |                                 |                 |
|               +-------------------------------+---------------------------------+                 |
|                                               |                                                   |
|                                               v                                                   |
|                               +-------------------------------+                                   |
|                               |     GraphExtractor (AST)      |                                   |
|                               |  RawSymbol, RawImport, RawCall|                                   |
|                               +---------------+---------------+                                   |
|                                               |                                                   |
|                                               v                                                   |
|                               +-------------------------------+                                   |
|                               |    RepositoryGraphService     |                                   |
|                               |  - SHA-256 Content-Hashing    |                                   |
|                               |  - Incremental Diff & Skip    |                                   |
|                               |  - Prune & Replace Obsolete   |                                   |
|                               |  - Cross-File Symbol Linking  |                                   |
|                               +---------------+---------------+                                   |
|                                               |                                                   |
|                                               v                                                   |
|                    +-----------------------------------------------------+                        |
|                    |             PostgreSQL 16 Graph Schema              |                        |
|                    |  - repository_graph_nodes (11 node types, metadata) |                        |
|                    |  - repository_graph_edges (8 edge types, resolution)|                        |
|                    +--------------------------+--------------------------+                        |
|                                               |                                                   |
|                                               v                                                   |
|   +-------------------------------------------+-----------------------------------------------+   |
|   |                                  Authenticated REST APIs                                  |   |
|   |  GET /summary  |  POST /index  |  GET /nodes  |  GET /nodes/{id}  |  GET /dependencies    |   |
|   +-------------------------------------------+-----------------------------------------------+   |
|                                               |                                                   |
|                                               v                                                   |
|                               +-------------------------------+                                   |
|                               |     Next.js Graph Visualizer  |                                   |
|                               |  - Interactive SVG Canvas     |                                   |
|                               |  - Radial Layout Distribution |                                   |
|                               |  - Node Inspection Drawer     |                                   |
|                               +-------------------------------+                                   |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 Graph Taxonomy & Resolution Semantics

#### Node Types (11 Canonical Entities):
- `REPOSITORY`: Root project anchor node.
- `DIRECTORY`: File system folder containment node.
- `FILE`: Code file source node with language, line count, and SHA-256 hash.
- `MODULE`: Python or TS/JS module namespace.
- `PACKAGE`: Package boundary node (Go package, Java package, npm module).
- `CLASS`: Object-oriented class declaration.
- `INTERFACE`: Interface contract (TypeScript, Go, Java).
- `FUNCTION`: Standalone top-level function.
- `METHOD`: Class- or struct-bound method.
- `VARIABLE`: Module-level mutable state.
- `CONSTANT`: Module-level uppercase constant or exported symbol.

#### Edge Types (8 Directed Relationships):
- `CONTAINS`: Structural hierarchy (`REPOSITORY -> DIRECTORY`, `DIRECTORY -> FILE`).
- `DEFINES`: Scope declaration (`FILE -> CLASS`, `FILE -> FUNCTION`, `CLASS -> METHOD`).
- `IMPORTS`: Source-to-target dependency (`FILE -> MODULE`, `FILE -> FILE`).
- `DEPENDS_ON`: High-level module coupling (`FILE -> FILE`).
- `INHERITS`: Class inheritance hierarchy (`CLASS -> CLASS`).
- `IMPLEMENTS`: Interface implementation (`CLASS -> INTERFACE`).
- `REFERENCES`: Variable or constant usage.
- `CALLS`: Direct invocation (`FUNCTION -> FUNCTION`, `METHOD -> METHOD`).

#### Resolution Statuses & Confidence Scoring:
- `RESOLVED` (Confidence 1.0): Symbol uniquely resolved to a concrete node in the repository.
- `EXTERNAL` (Confidence 0.8–0.9): Standard library or 3rd-party dependency (e.g., `fastapi`, `math`, `react`).
- `UNRESOLVED` (Confidence 0.5–0.7): Import declared but target symbol cannot be located in repository.
- `AMBIGUOUS` (Confidence 0.5): Multiple candidates match the import specifier.

---

## 3. Database Schema & Migration

### Alembic Migration: `012_repository_dependency_graph.py`

#### Table: `repository_graph_nodes`
```sql
CREATE TABLE repository_graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    node_type VARCHAR(32) NOT NULL,
    qualified_name VARCHAR(512) NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(1024),
    language VARCHAR(64),
    start_line INTEGER,
    end_line INTEGER,
    start_col INTEGER,
    end_col INTEGER,
    content_hash VARCHAR(64),
    docstring TEXT,
    meta_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX uq_repo_graph_nodes_qname 
    ON repository_graph_nodes (repository_id, qualified_name);
CREATE INDEX ix_repo_graph_nodes_type 
    ON repository_graph_nodes (repository_id, node_type);
CREATE INDEX ix_repo_graph_nodes_filepath 
    ON repository_graph_nodes (repository_id, file_path);
```

#### Table: `repository_graph_edges`
```sql
CREATE TABLE repository_graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    source_node_id UUID NOT NULL REFERENCES repository_graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID REFERENCES repository_graph_nodes(id) ON DELETE SET NULL,
    edge_type VARCHAR(32) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    resolution_status VARCHAR(32) NOT NULL DEFAULT 'RESOLVED',
    target_symbol VARCHAR(512),
    line_number INTEGER,
    meta_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ix_repo_graph_edges_source 
    ON repository_graph_edges (source_node_id);
CREATE INDEX ix_repo_graph_edges_target 
    ON repository_graph_edges (target_node_id);
CREATE INDEX ix_repo_graph_edges_type 
    ON repository_graph_edges (edge_type);
CREATE INDEX ix_repo_graph_edges_resolution 
    ON repository_graph_edges (resolution_status);
```

---

## 4. REST API Specification

All endpoints are registered under `/api/v1/repositories/{id}/graph` and require bearer token authentication:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Graph summary metrics (node/edge totals, type breakdowns, external/unresolved counts) |
| `POST` | `/index` | Trigger on-demand graph indexing (`force_reindex: boolean`) with incremental hashing |
| `GET` | `/nodes` | Paginated node search with `node_type`, `file_path`, and `search` query parameters |
| `GET` | `/nodes/{node_id}` | Detailed node properties with immediate incoming and outgoing edges |
| `GET` | `/dependencies` | Bounded BFS traversal (`root_node_id`, `depth=1..5`, `direction=OUTGOING\|INCOMING\|BOTH`) |
| `GET` | `/unresolved` | Audit external and unresolved symbols with pagination |

---

## 5. Incremental Indexing Engine

The incremental change detection engine follows strict performance and idempotency invariants:
1. **SHA-256 Digesting:** Every file scanned during repository exploration has its SHA-256 hash computed.
2. **Hash Comparison:** Hashes are compared against existing `FILE` node `content_hash` attributes in `repository_graph_nodes`.
3. **Early Exit on Zero Changes:** If all scanned files match existing hashes and no files have been added or removed, the indexer returns immediately with `files_skipped = N, files_indexed = 0` and performs **zero database writes**.
4. **Targeted Pruning:** When a file is modified or deleted, its existing symbol nodes and attached edges are deleted transactionally using `db.execute(delete(RepositoryGraphNode).where(...))` with cascading edge deletion.
5. **Re-Extraction & Relinking:** Only modified or added files are parsed by `GraphExtractor`. Their new nodes and edges are inserted, and cross-file relationships are re-resolved.
6. **Edge Idempotency:** Duplicate edges between nodes are prevented by an in-memory uniqueness set `(source_id, target_id, edge_type, target_symbol)` pre-populated from existing edges.

---

## 6. Frontend Dependency Graph Visualizer

The frontend dependency graph interface was added as a first-class tab in the Repository Workspace (`/repositories/[id]`):
- **Interactive SVG Canvas:** Renders nodes and directed edges with smooth pan and zoom controls ($0.5\times$ to $2.0\times$).
- **Radial Layout Distribution:** Distributes nodes into concentric rings (Repository root at center, Files in middle ring, Symbols in outer ring) for intuitive structural navigation.
- **Node Type Color Palette:** Distinct color coding (e.g. Purple for Class, Amber for Function, Blue for Method, Slate for File, Indigo for Directory).
- **Depth Slider & Filter Bar:** Dynamic traversal depth selector ($1$ to $5$) and live substring search across symbol qualified names.
- **Inspection Drawer:** Clicking any node reveals its qualified name, lines of code, docstring, parent container, outgoing dependencies, and incoming references.
- **Unresolved References Audit:** Displays dangling imports, external library dependencies, and unresolved symbols in an organized audit table.

---

## 7. Verification Evidence & Test Results

### 7.1 New Unit Tests (`backend/tests/unit/test_graph_engine.py`)
- `test_python_ast_symbol_extraction`: Verifies AST extraction of classes, base classes, methods, and functions.
- `test_python_import_extraction_and_resolution`: Verifies resolution of relative imports (`.utils`), absolute imports, and external imports (`fastapi`).
- `test_js_ts_import_resolution`: Verifies relative path resolution for JavaScript/TypeScript imports (`./helper`, `../services/api`).
- `test_content_hash_integrity`: Verifies deterministic SHA-256 hashing across identical and altered file content.
- `test_malformed_syntax_graceful_handling`: Verifies that syntax errors in source files do not crash the parser and return structured error diagnostics.
**Result:** 5 passed in 0.03s.

### 7.2 New Integration Tests (`backend/tests/integration/test_dependency_graph_api.py`)
- `test_full_repository_graph_indexing`: Tests end-to-end full graph indexing on a multi-file Git repository fixture.
- `test_incremental_indexing_idempotency`: Verifies repeat indexing with unchanged files skips parsing and preserves exact node counts without duplicates.
- `test_file_modification_and_incremental_reindexing`: Verifies file modification correctly detects changed hashes, prunes old symbols, and inserts updated symbols.
- `test_query_nodes_and_filtering`: Verifies `GET /nodes` pagination, `node_type` filtering, and `search` query parameters.
- `test_node_detail_and_bounded_dependencies`: Verifies `GET /nodes/{id}` and bounded BFS dependency traversal (`GET /dependencies`).
- `test_cross_repository_isolation`: Verifies strict isolation preventing cross-tenant leakage between repositories.
**Result:** 6 passed in 5.18s.

### 7.3 Full Backend Regression Test Suite
Executed the entire backend test suite across all 10 phases and stages:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
plugins: langsmith-0.14.17, anyio-4.16.0, asyncio-1.5.0
collected 272 items

..................................................sss................... [ 26%]
........................................................................ [ 52%]
........................................................................ [ 79%]
........................................................                 [100%]
=================== 269 passed, 3 skipped in 95.38s (0:01:35) ==================
```

### 7.4 Frontend Build Verification
Executed `cd frontend && npm run build`:
```
  ▲ Next.js 14.2.35
   Creating an optimized production build ...
 ✓ Compiled successfully
   Linting and checking validity of types     ✓ 
   Collecting page data     ✓ 
 ✓ Generating static pages (16/16)
   Finalizing page optimization     ✓ 

Route (app)                              Size     First Load JS
┌ ○ /                                    175 B          96.1 kB
├ ○ /_not-found                          875 B          88.2 kB
├ ○ /adaptive                            8.48 kB         128 kB
├ ○ /dashboard                           4.25 kB         121 kB
├ ○ /github                              5.14 kB         124 kB
├ ○ /login                               3.36 kB         133 kB
├ ○ /ml                                  6.63 kB         126 kB
├ ○ /reliability                         7.87 kB         127 kB
├ ○ /reports                             1 kB            118 kB
├ ○ /repositories                        4.74 kB         149 kB
├ ƒ /repositories/[id]                   13.1 kB         132 kB
├ ○ /settings                            2.34 kB         119 kB
├ ○ /signup                              3.43 kB         133 kB
├ ○ /tasks                               2.9 kB          120 kB
├ ƒ /tasks/[id]                          13.3 kB         132 kB
└ ○ /tasks/new                           4.42 kB         147 kB
+ First Load JS shared by all            87.3 kB
```
**Result:** 16/16 routes compiled cleanly with 0 TypeScript or lint errors.

---

## 8. Honest Limitations & Architectural Scope Boundaries

1. **Rust Parsing Fallback:** `tree_sitter_rust` is not bundled in the active Python environment. Rust files are processed using a syntactic regex parser that extracts `mod`, `use`, `struct`, and `fn` signatures. Devora AI explicitly identifies these as syntactic extractions rather than claiming full semantic resolution.
2. **Scope Adherence:** Stage 10.1 establishes the foundational dependency graph models, parsers, indexers, APIs, and visualizer. Downstream blast-radius computation, change impact analysis, and deep inter-procedural call-graph reasoning are scheduled for **Stage 10.2** and were strictly omitted from this stage.

---

## 9. Conclusion

Stage 10.1 of Phase 10 has been successfully implemented, verified against the actual database and codebase, and documented across all master project references. Devora AI now possesses a robust, incremental, and queryable dependency graph engine that sets the stage for advanced blast radius analysis in Stage 10.2.

# Devora AI — Phase 10 Stage 10.2 Implementation Plan
## Blast Radius and Change Impact Analysis Engine

**Author:** Devora AI Core Architecture Team  
**Date:** November 19, 2026  
**Status:** DRAFT & READY FOR EXECUTION  
**Target Regression Baseline:** $\ge 269$ passed, 0 failed, 3 skipped  
**Frontend Compilation Target:** 16/16 routes compiled successfully  

---

## 1. Executive Summary & Objective

In **Phase 10, Stage 10.1**, Devora AI established the persistent, queryable cross-file symbol and dependency graph engine (`repository_graph_nodes`, `repository_graph_edges`, Alembic migration `012`, `GraphExtractor`, `RepositoryGraphService`, and the interactive Next.js visualizer).

The objective of **Stage 10.2** is to implement the **Blast Radius and Change Impact Analysis Engine**. When a developer or agent proposes modifying a file, function, class, or module, Devora must:
1. Deterministically identify directly and transitively affected components using reverse dependency traversal.
2. Construct explainable, auditable dependency paths showing exactly how each component is affected.
3. Compute an explainable, deterministic impact severity score (0–100) and severity band (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) alongside a distinct confidence rating ($0.0$ to $1.0$).
4. Recommend relevant tests by combining AST graph dependency edges (`CONFIRMED`) with framework naming heuristics (`HEURISTIC`).
5. Expose authenticated REST endpoints under `/api/v1/repositories/{id}/impact-analysis`.
6. Provide an interactive frontend Impact Analysis workspace in Next.js (`/repositories/[id]`).
7. Integrate impact intelligence into the LangGraph multi-agent workflow (Planner, Code Reviewer, Tester, Reporter) safely without authorizing unauthorized modifications.

---

## 2. Existing Codebase Audit & Architectural Foundations

### 2.1 Graph Models & Traversal Semantics
- **`RepositoryGraphNode`**: Stores entity type (`FILE`, `CLASS`, `FUNCTION`, `METHOD`, `VARIABLE`, `CONSTANT`, etc.), qualified name, file path, line numbers, language, content hash, and metadata.
- **`RepositoryGraphEdge`**: Stores directional relationships (`CONTAINS`, `DEFINES`, `IMPORTS`, `DEPENDS_ON`, `INHERITS`, `IMPLEMENTS`, `REFERENCES`, `CALLS`), confidence ($0.0$ to $1.0$), resolution status (`RESOLVED`, `EXTERNAL`, `UNRESOLVED`, `AMBIGUOUS`), and target symbol.

### 2.2 Semantic Edge Evaluation for Impact Propagation

| Edge Type | Normal Direction | Blast Radius Direction | Semantic Impact Validity | Rationale |
|---|---|---|---|---|
| `IMPORTS` | $A \rightarrow B$ ($A$ imports $B$) | $B \leftarrow A$ (Incoming to $B$) | **High (0.9)** | If $B$ changes, $A$ is a direct consumer. |
| `DEPENDS_ON` | $A \rightarrow B$ ($A$ depends on $B$) | $B \leftarrow A$ (Incoming to $B$) | **High (0.8)** | Module-level coupling. |
| `CALLS` | $F_1 \rightarrow F_2$ ($F_1$ calls $F_2$) | $F_2 \leftarrow F_1$ (Incoming to $F_2$) | **Critical (1.0)** | Direct invocation coupling; altering $F_2$'s signature or behavior breaks $F_1$. |
| `INHERITS` | $C_{child} \rightarrow C_{parent}$ | $C_{parent} \leftarrow C_{child}$ (Incoming to $C_{parent}$) | **Critical (1.0)** | Modifying a base class changes all child classes. |
| `IMPLEMENTS` | $C_{impl} \rightarrow I_{contract}$ | $I_{contract} \leftarrow C_{impl}$ (Incoming to $I$) | **Critical (1.0)** | Modifying an interface breaks all implementers. |
| `REFERENCES` | $S \rightarrow V$ ($S$ references $V$) | $V \leftarrow S$ (Incoming to $V$) | **Medium (0.7)** | Reading state or constants. |
| `DEFINES` | $File \rightarrow Sym$ | Bidirectional scoping | **Scoping Only** | If $File$ changes, its symbols change. If $Sym$ changes, the containing file's importers are potential consumers. |
| `CONTAINS` | $Dir \rightarrow File$ | **Excluded from impact** | **Zero (0.0)** | Structural container only; changing a file does NOT impact sibling files. |

### 2.3 Traversal Invariant: Reverse Dependency Traversal
- If node $T$ is changed, its consumers are found by following **incoming edges** where `target_node_id == T.id`.
- Outgoing edges of $T$ represent what $T$ depends on, **not** what depends on $T$. Outgoing edges must **never** be treated as impacted consumers.

---

## 3. Core Engine Design: `ImpactAnalysisService`

### 3.1 Input Formats
The service accepts any combination of:
- `file_paths`: List of repository-relative file paths (e.g. `["app/auth.py"]`).
- `symbol_ids`: List of node UUIDs.
- `qualified_names`: List of fully qualified names (e.g. `["app/auth.py:validate_token"]`).

### 3.2 Bounded Reverse Traversal (BFS)
```python
queue = deque([(target_node, depth=0, path=[target_node])])
visited = {target_node.id}
while queue and len(impacted_nodes) < max_impacted_nodes:
    curr, depth, path = queue.popleft()
    if depth >= max_depth:
        continue
    # Query incoming edges (who depends on curr?)
    incoming_edges = get_incoming_dependency_edges(curr.id)
    for edge in incoming_edges:
        source_node = edge.source_node
        # Record dependency path: source_node -> edge -> curr
        ...
```
- **Depth Constraints:** Configurable $1 \le d \le 5$, default 3.
- **Cycle Protection:** Track visited node IDs.
- **Node Cap:** Configurable maximum impacted nodes (default 100, max 200).
- **Paths Cap:** Cap to at most 3 distinct explanation paths per impacted node to prevent explosion.

### 3.3 Explainable Deterministic Scoring Model

We formulate a deterministic score in the range $[0, 100]$:

$$\text{ImpactScore} = \min\left(100, \text{round}\left(S_{files} + S_{symbols} + S_{depth} + S_{coupling} + S_{untested}\right)\right)$$

Where:
1. **Affected Files Component ($S_{files} \in [0, 30]$):**
   $$S_{files} = \min\left(30, N_{affected\_files} \times 6\right)$$
2. **Affected Symbols Component ($S_{symbols} \in [0, 25]$):**
   $$S_{symbols} = \min\left(25, N_{direct\_symbols} \times 4 + N_{transitive\_symbols} \times 1.5\right)$$
3. **Depth & Reach Component ($S_{depth} \in [0, 20]$):**
   $$S_{depth} = \min\left(20, \text{max\_depth} \times 4 + N_{paths} \times 1\right)$$
4. **Interface / Cross-Module Spread ($S_{coupling} \in [0, 15]$):**
   $$S_{coupling} = \min\left(15, N_{directories} \times 5\right)$$
5. **Untested Exposure Penalty ($S_{untested} \in [0, 10]$):**
   - If 0 recommended tests exist: $+10$ points (untested blast radius).
   - If tests exist: $+0$ points.

#### Severity Bands:
- `CRITICAL`: Score $\ge 80$ (wide multi-module impact, numerous dependent files/symbols).
- `HIGH`: $60 \le \text{Score} < 80$ (multiple dependent files or heavy call coupling).
- `MEDIUM`: $30 \le \text{Score} < 60$ (isolated consumer coupling within 1–2 files).
- `LOW`: $1 \le \text{Score} < 30$ (localized impact, leaf symbol or single consumer).
- `UNKNOWN`: Score $= 0$ (no dependent consumers discovered or empty graph).

#### Confidence Score ($0.0$ to $1.0$):
Independent from impact magnitude. Computed as the path-weighted average of edge confidences and resolution statuses:
$$\text{Confidence} = \frac{1}{|E_{traversed}|} \sum_{e \in E_{traversed}} e.confidence \times \begin{cases} 1.0 & \text{if RESOLVED} \\ 0.8 & \text{if EXTERNAL} \\ 0.5 & \text{if UNRESOLVED / AMBIGUOUS} \end{cases}$$

---

## 4. Test Impact Analysis Engine

Combines structural graph analysis with test framework discovery:
1. **Confirmed Test Impact (`CONFIRMED`):**
   - Test files with explicit incoming edges to the changed nodes (`test_auth.py -> IMPORTS -> auth.py` or `test_auth.py:test_verify -> CALLS -> auth.py:verify_token`).
   - Confidence: $0.95$–$1.0$.
2. **Heuristic Test Impact (`HEURISTIC`):**
   - Test files identified by `TestDiscoveryService` naming patterns (`test_<base>.py`, `<base>.test.ts`, `<base>_test.go`) matching modified file stems.
   - Confidence: $0.75$.
3. **Test Status & Execution Recommendation:**
   - Clearly flags whether tests are confirmed or heuristic.
   - Does NOT execute tests inside the impact analysis service (testing execution remains governed by `Tester` agent).

---

## 5. REST API Architecture

### Endpoint: `POST /api/v1/repositories/{repository_id}/impact-analysis`

#### Request Payload:
```json
{
  "file_paths": ["app/services/auth_service.py"],
  "symbol_ids": [],
  "qualified_names": [],
  "max_depth": 3,
  "include_tests": true,
  "max_impacted_nodes": 100
}
```

#### Response Payload:
```json
{
  "repository_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
  "commit_sha": "a1b2c3d4e5f67890",
  "is_stale": false,
  "staleness_reason": null,
  "targets": [
    {
      "node_id": "c1f2e4b3-a12b-4567-89ab-cdef01234567",
      "node_type": "FILE",
      "qualified_name": "app/services/auth_service.py",
      "name": "auth_service.py",
      "file_path": "app/services/auth_service.py"
    }
  ],
  "impact_score": 68,
  "severity": "HIGH",
  "confidence": 0.94,
  "score_explanation": "High impact: 4 dependent files and 11 dependent symbols across 2 packages; 2 confirmed test suites available.",
  "score_breakdown": {
    "files_score": 24,
    "symbols_score": 18,
    "depth_score": 12,
    "coupling_score": 10,
    "untested_penalty": 0
  },
  "summary": {
    "total_affected_files": 4,
    "total_affected_symbols": 11,
    "direct_impact_count": 5,
    "transitive_impact_count": 6,
    "recommended_tests_count": 2,
    "unresolved_warnings_count": 0
  },
  "affected_files": ["app/api/endpoints.py", "app/tasks/worker.py", "tests/test_auth.py"],
  "impacted_nodes": [ ... ],
  "dependency_paths": [ ... ],
  "recommended_tests": [ ... ],
  "unresolved_warnings": [ ... ],
  "execution_duration_seconds": 0.04
}
```

---

## 6. Frontend Impact Analysis Experience

Integrated into the Repository Workspace (`/repositories/[id]`):
1. **Target Selector:** Quick selection of repository files or extracted symbols with autocomplete.
2. **Impact Overview Banner:**
   - Severity badge (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`).
   - Impact score (0–100) and Confidence rating ($0.0$ to $1.0$).
   - Graph freshness badge (`FRESH` vs `GRAPH STALE`).
3. **Metric Cards:**
   - Affected Files Count.
   - Affected Symbols Count.
   - Direct vs Transitive Breakdown.
   - Recommended Tests Count.
4. **Interactive Sections:**
   - **Affected Files & Symbols Table:** Filterable by depth and node type.
   - **Dependency Path Explorer:** Step-by-step breadcrumb view explaining how the consumer depends on the target (`A -> CALLS -> B`).
   - **Recommended Tests Panel:** Lists confirmed vs heuristic test suites with rationales.
   - **Uncertainty & Unresolved Warnings:** Collapsible alert for external or unresolved dependencies.

---

## 7. LangGraph Multi-Agent Workflow Integration

Integrate `ImpactAnalysisService` into the specialist agent nodes:
1. **Planner (`planner.py`):**
   - When candidate files are identified by `codebase_analyst`, Planner inspects the blast radius.
   - Planner prompt includes affected consumers and recommended test suites to ensure the implementation steps account for downstream contracts.
2. **Code Reviewer (`code_reviewer.py`):**
   - Compares actual modified files against predicted blast radius.
   - If high-severity affected consumers are not updated or covered by tests, issues constructive review comments.
3. **Tester (`tester.py`):**
   - Augments test file selection with confirmed test dependencies discovered by the impact analysis.
4. **Reporter (`reporter.py`):**
   - Summarizes blast radius, affected consumers, and confidence in the final engineering report.

**Invariants:**
- Impact analysis is strictly advisory; it never authorizes code modifications.
- Low confidence or missing graphs never block task execution.
- Human approval gate remains untouched.

---

## 8. Verification & Testing Strategy

### 8.1 Unit Tests (`backend/tests/unit/test_impact_analysis.py`)
1. `test_reverse_dependency_directionality`: Verifies that incoming edges are traversed and outgoing edges are excluded.
2. `test_direct_vs_transitive_classification`: Distinguishes depth 1 vs depth > 1.
3. `test_dependency_path_reconstruction`: Verifies exact path breadcrumbs (`A -> IMPORTS -> B`).
4. `test_cycle_handling_and_duplicate_suppression`: Ensures recursive dependencies do not cause infinite loops.
5. `test_deterministic_scoring_and_severity_bands`: Validates score calculation and boundaries.
6. `test_confidence_calculation_with_unresolved_edges`: Checks penalty on unresolved/external edges.
7. `test_test_recommendations_confirmed_vs_heuristic`: Verifies `CONFIRMED` test edge vs `HEURISTIC` match.
8. `test_stale_graph_detection`: Checks `is_stale` flag when commit SHA differs.

### 8.2 Integration Tests (`backend/tests/integration/test_impact_analysis_api.py`)
1. `test_impact_analysis_file_target`: End-to-end API test with file path target.
2. `test_impact_analysis_symbol_target`: End-to-end API test with function/class symbol target.
3. `test_multi_target_blast_radius`: Analyzes impact across a set of changed files.
4. `test_impact_analysis_with_recommended_tests`: Verifies confirmed test discovery via REST API.
5. `test_repository_isolation_and_security`: Verifies cross-tenant protection and 404/403 handling.
6. `test_workflow_agent_integration_smoke`: Verifies that planner/reviewer seamlessly consume impact context without crashing.

### 8.3 Regression Verification
- Run complete backend test suite: $\ge 269$ passed, 0 failed, 3 skipped.
- Run frontend build: `npm run build` with 16/16 routes compiled.

---

## 9. Implementation Roadmap & Milestones

1. **Phase 10.2.1:** Implement Pydantic Schemas (`backend/app/schemas/impact.py`).
2. **Phase 10.2.2:** Implement `ImpactAnalysisService` (`backend/app/services/impact_analysis_service.py`).
3. **Phase 10.2.3:** Implement REST Endpoints (`backend/app/api/v1/impact.py`) and register router.
4. **Phase 10.2.4:** Integrate into LangGraph specialist agents (`planner.py`, `code_reviewer.py`, `reporter.py`).
5. **Phase 10.2.5:** Frontend UI — Impact Analysis component and service client.
6. **Phase 10.2.6:** Authored comprehensive unit and integration tests.
7. **Phase 10.2.7:** Regression run, frontend build, and documentation updates.

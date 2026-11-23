# Devora AI — Phase 10 Stage 10.2 Implementation Report
## Blast Radius and Change Impact Analysis Engine

**Date:** November 19, 2026  
**Status:** COMPLETED & VERIFIED  
**Regression Baseline:** 278 passed, 0 failed, 3 skipped  
**Frontend Compilation:** 16/16 routes compiled successfully  
**Database Dependency:** PostgreSQL 16 at revision `012_repository_dependency_graph`  

---

## 1. Executive Summary

In **Phase 10, Stage 10.2**, Devora AI introduced an autonomous **Blast Radius and Change Impact Analysis Engine**. 

Before Stage 10.2, proposed code changes in an autonomous engineering task were executed without forward knowledge of how downstream components might be affected. Modifying a central function, utility, or class could silently break consumers across different modules, requiring expensive trial-and-error repair loops during test execution. 

Stage 10.2 solves this problem by using the persistent relational graph from Stage 10.1 to deterministically evaluate the blast radius of any proposed modification before code editing begins. By traversing incoming dependency edges in reverse, reconstructing explainable multi-hop dependency paths, calculating a deterministic 0–100 impact score across 5 objective criteria, and correlating test suites from `TestDiscoveryService`, Devora empowers both developers and autonomous agents with clear, auditable foresight into change consequences.

### Key Achievements:
1. **Reverse Dependency Traversal Engine ([`ImpactAnalysisService`](file:///Users/agrimagupta/devoraai/backend/app/services/impact_analysis_service.py)):**
   - Identifies consumers of a changed file or symbol by querying incoming edges (`target_node_id == target.id`).
   - Filters valid semantic consumer edges: `IMPORTS`, `DEPENDS_ON`, `CALLS`, `INHERITS`, `IMPLEMENTS`, and `REFERENCES`.
   - Strictly excludes structural `CONTAINS` relationships (`DIRECTORY -> FILE`) to prevent false-positive sibling pollution.
   - Outgoing edges of target nodes represent prerequisites rather than consumers and are strictly excluded from blast-radius calculations.
2. **Explainable Dependency Path Chains:**
   - Every affected downstream node is paired with an auditable breadcrumb path: `Consumer (Type) -[EDGE]-> ... -[EDGE]-> Target`.
   - Clearly separates **Direct Impact** (distance $= 1$ hop) from **Transitive Impact** (distance $> 1$ hops) with cycle detection and depth boundaries ($1 \le d \le 5$, default 3).
3. **Deterministic, Explainable Impact Scoring (0–100):**
   - Eliminates opaque LLM-generated hallucinations in favor of a deterministic scoring formula with five distinct components: Affected Files ($\le 30$), Affected Symbols ($\le 25$), Traversal Depth/Reach ($\le 20$), Cross-Module Coupling ($\le 15$), and Untested Exposure Penalty ($\le 10$).
   - Standardized Severity Bands: `CRITICAL` ($\ge 80$), `HIGH` ($60 \le s < 80$), `MEDIUM` ($30 \le s < 60$), `LOW` ($1 \le s < 30$), and `UNKNOWN` ($0$).
   - Separate **Confidence Score** ($0.0$ to $1.0$) reflecting resolution certainty and discounting unresolved ($0.5$) or external ($0.8$) dependencies.
4. **Test Recommendation Correlation:**
   - Detects test suites that directly or transitively import or call modified components (`CONFIRMED`, confidence $\ge 0.95$).
   - Augments with framework naming conventions (`HEURISTIC`, confidence $0.75$) via `TestDiscoveryService`.
   - Strictly advisory: recommends test suites without executing them in the impact service (delegating test execution to isolated sandbox runners).
5. **LangGraph Specialist Agent Integration:**
   - **Planner:** Ingests predicted blast radius severity, downstream affected files, and recommended test criteria into task decomposition.
   - **Code Reviewer:** Audits code diffs against predicted consumers and flags unreviewed affected contracts.
   - **Reporter:** Incorporates blast radius severity and affected file metrics into the final engineering report.
   - **Advisory Invariant:** Impact analysis never authorizes code changes, modifies files, or blocks workflow execution on low confidence.
6. **Next.js Interactive Visualizer ([`impact-analysis-tab.tsx`](file:///Users/agrimagupta/devoraai/frontend/src/components/repository/impact-analysis-tab.tsx)):**
   - Added a dedicated "Blast Radius & Impact" tab in the Repository Workspace (`/repositories/[id]`).
   - Includes real-time file/symbol selector, depth slider ($1$ to $5$), executive severity banner, score gauge, certainty meter, graph freshness indicator, direct/transitive entity filter table, dependency path explorer, and recommended tests panel.
7. **Complete Regression Verification:**
   - Authored 9 new tests (4 unit in `test_impact_analysis.py`, 5 integration in `test_impact_analysis_api.py`) with 100% pass rate.
   - Full regression test run: **278 passed, 0 failed, 3 skipped in 101.43s**.
   - Frontend production build: **16/16 routes compiled cleanly with 0 errors**.

---

## 2. Architecture & Traversal Semantics

```
+---------------------------------------------------------------------------------------------------+
|                                 DEVORA BLAST RADIUS ENGINE                                        |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|   Target Change: [File: src/formatter.py]                                                         |
|                                                                                                   |
|   Reverse Dependency Traversal (Incoming Edges to Target):                                        |
|                                                                                                   |
|   +-----------------------+        IMPORTS         +-----------------------+                      |
|   |   src/calculator.py   | ---------------------> |   src/formatter.py    |                      |
|   |     (Direct Consumer) |                        |    (Target Changed)   |                      |
|   +-----------+-----------+                        +-----------------------+                      |
|               ^                                                                                   |
|               | IMPORTS                                                                           |
|   +-----------+-----------+                                                                       |
|   |      src/main.py      |                                                                       |
|   | (Transitive Consumer) |                                                                       |
|   +-----------------------+                                                                       |
|               ^                                                                                   |
|               | IMPORTS                                                                           |
|   +-----------+-----------+                                                                       |
|   | tests/test_calculator | ===> RECOMMENDED TEST SUITE (CONFIRMED DEPENDENCY, Conf: 0.95)        |
|   +-----------------------+                                                                       |
|                                                                                                   |
|   Scoring Breakdown:                                                                              |
|   - Files Score: 18/30 (3 affected files)                                                         |
|   - Symbols Score: 19/25 (MathEngine, calculate_average, format_result)                           |
|   - Depth Score: 12/20 (max_depth: 2 hops, 2 paths)                                               |
|   - Coupling Score: 10/15 (src/ and tests/)                                                       |
|   - Untested Penalty: 0/10 (tests/test_calculator.py recommended)                                 |
|   --------------------------------------------------------                                        |
|   Total Score: 68/100 (HIGH SEVERITY) | Confidence: 94%                                           |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 Traversal Directionality & Edge Validity

To discover what is impacted when node $T$ changes, we query:
$$\text{Consumers}(T) = \{ S \mid (S \xrightarrow{edge} T) \in \text{Edges}, edge.type \in \text{VALID\_CONSUMER\_EDGES} \}$$

Where $\text{VALID\_CONSUMER\_EDGES} = \{\text{IMPORTS}, \text{DEPENDS\_ON}, \text{CALLS}, \text{INHERITS}, \text{IMPLEMENTS}, \text{REFERENCES}\}$.

- **`CONTAINS` edges are strictly excluded:** In Devora's graph, `DIRECTORY -> CONTAINS -> FILE`. Traversal in reverse would treat a directory as an affected consumer, and traversal forwards would falsely treat all sibling files in that directory as affected. Excluding `CONTAINS` preserves precise consumer boundaries.
- **Outgoing edges of $T$ are strictly excluded:** If $T \xrightarrow{\text{IMPORTS}} L$, $L$ is a library or prerequisite required by $T$. Modifying $T$ does not impact $L$.

### 2.2 Deterministic Impact Scoring Formula

$$\text{ImpactScore} = \min\left(100, S_{files} + S_{symbols} + S_{depth} + S_{coupling} + S_{untested}\right)$$

1. **$S_{files} = \min(30, N_{affected\_files} \times 6)$**
2. **$S_{symbols} = \min(25, \lfloor N_{direct\_symbols} \times 4 + N_{transitive\_symbols} \times 1.5 \rfloor)$**
3. **$S_{depth} = \min(20, \text{max\_depth} \times 4 + \min(10, N_{paths}))$**
4. **$S_{coupling} = \min(15, N_{directories} \times 5)$**
5. **$S_{untested} = 10 \text{ if } N_{tests} == 0 \text{ else } 0$**

Severity bands are mapped deterministically:
- `CRITICAL`: Score $\ge 80$
- `HIGH`: $60 \le \text{Score} < 80$
- `MEDIUM`: $30 \le \text{Score} < 60$
- `LOW`: $1 \le \text{Score} < 30$
- `UNKNOWN`: $\text{Score} = 0$

### 2.3 Confidence Rating

$$\text{Confidence} = \frac{1}{|E_{traversed}|} \sum_{e \in E_{traversed}} e.confidence \times \begin{cases} 1.0 & \text{if } e.resolution == \text{RESOLVED} \\ 0.8 & \text{if } e.resolution == \text{EXTERNAL} \\ 0.5 & \text{if } e.resolution \in \{\text{UNRESOLVED}, \text{AMBIGUOUS}\} \end{cases}$$

---

## 3. REST API Specification

### Endpoint: `POST /api/v1/repositories/{id}/impact-analysis`

**Request:** `ImpactAnalysisRequest`
```json
{
  "file_paths": ["src/formatter.py"],
  "symbol_ids": [],
  "qualified_names": [],
  "max_depth": 3,
  "include_tests": true,
  "max_impacted_nodes": 100
}
```

**Response:** `ImpactAnalysisResponse` (200 OK)
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
      "qualified_name": "src/formatter.py",
      "name": "formatter.py",
      "file_path": "src/formatter.py"
    }
  ],
  "impact_score": 68,
  "severity": "HIGH",
  "confidence": 0.94,
  "score_explanation": "High impact (score 68/100): Significant coupling across 3 files and 6 symbols with traversal depth 2.",
  "score_breakdown": {
    "files_score": 18,
    "symbols_score": 19,
    "depth_score": 12,
    "coupling_score": 10,
    "untested_penalty": 0
  },
  "summary": {
    "total_affected_files": 3,
    "total_affected_symbols": 6,
    "direct_impact_count": 2,
    "transitive_impact_count": 4,
    "recommended_tests_count": 1,
    "unresolved_warnings_count": 0
  },
  "affected_files": [
    "src/formatter.py",
    "src/calculator.py",
    "src/main.py"
  ],
  "impacted_nodes": [ ... ],
  "dependency_paths": [
    {
      "target_name": "formatter.py",
      "impacted_node_id": "d2e3f4a5-b6c7-8901-2345-6789abcdef02",
      "impacted_name": "calculator.py",
      "impacted_file_path": "src/calculator.py",
      "depth": 1,
      "hops": [ ... ],
      "explanation": "calculator.py (FILE) -[IMPORTS]-> formatter.py"
    }
  ],
  "recommended_tests": [
    {
      "test_file_path": "tests/test_calculator.py",
      "test_framework": "pytest",
      "recommendation_type": "CONFIRMED",
      "confidence": 0.95,
      "reason": "Test file 'tests/test_calculator.py' directly imports affected file 'src/calculator.py'",
      "target_symbol_or_file": "src/calculator.py"
    }
  ],
  "unresolved_warnings": [],
  "execution_duration_seconds": 0.04
}
```

---

## 4. Frontend Experience: Blast Radius & Impact Tab

The new interface was added to `/repositories/[id]` as the **Blast Radius & Impact** tab:
1. **Target Selector:** User inputs a relative file path or qualified symbol name, with quick-pick chips for tracked repository files.
2. **Analysis Controls:** Max depth dropdown ($1$ to $5$ hops), "Map Recommended Tests" toggle, and "Analyze Blast Radius" action button.
3. **Executive Severity Card:** Prominent severity badge (`CRITICAL` in rose, `HIGH` in orange, `MEDIUM` in amber, `LOW` in emerald, `UNKNOWN` in slate), numeric score ($0$–$100$), certainty meter percentage, score explanation, and graph synchronization badge.
4. **Metric Grid:** 4-cell layout displaying Affected Files, Affected Symbols, Direct vs Transitive Split, and Recommended Tests Count.
5. **Multi-View Tabs:**
   - **Affected Entities Table:** Paginated list of affected files/symbols with node type badge, depth, direct/transitive pill, and primary reason.
   - **Dependency Paths Explorer:** Interactive breadcrumb cards showing the full sequence of hops from the consumer to the changed target.
   - **Recommended Tests Panel:** Displays test files with `CONFIRMED DEPENDENCY` (green) or `HEURISTIC MATCH` (blue) badges and execution rationales.
   - **Unresolved Warnings:** Callout alert listing external or unresolved imports that reduce confidence.

---

## 5. Verification Evidence

### 5.1 Unit Tests (`backend/tests/unit/test_impact_analysis.py`)
- `test_valid_consumer_edge_types`: Asserts that `IMPORTS`, `CALLS`, `INHERITS`, `DEPENDS_ON`, `IMPLEMENTS`, `REFERENCES` are valid consumer edges and `CONTAINS` is excluded.
- `test_deterministic_scoring_and_severity_bands`: Validates exact score calculations for zero, low, medium, high, and critical changes.
- `test_confidence_calculation_with_unresolved_edges`: Verifies penalty discounts for external and unresolved references.
- `test_dependency_path_construction`: Verifies breadcrumb formatting and hop order.
**Result:** 4 passed in 0.02s.

### 5.2 Integration Tests (`backend/tests/integration/test_impact_analysis_api.py`)
- `test_impact_analysis_for_leaf_file`: Tests blast radius on `src/formatter.py` across a 4-file real Git repository fixture with direct, transitive, and test consumers.
- `test_impact_analysis_for_symbol_target`: Tests blast radius when targeting a class symbol (`src/calculator.py:MathEngine`).
- `test_impact_analysis_unresolved_or_empty_target`: Tests graceful zero-impact handling when non-existent files are queried.
- `test_repository_isolation_and_unauthorized_access`: Verifies 404/401 handling across different repository tenants.
- `test_agent_workflow_integration_smoke`: Verifies that `planner_node`, `code_reviewer_node`, and `reporter_node` process `impact_analysis` without errors.
**Result:** 5 passed in 2.78s.

### 5.3 Combined Phase 10 Graph & Impact Tests
```
backend/tests/unit/test_graph_engine.py::test_python_ast_symbol_extraction PASSED
backend/tests/unit/test_graph_engine.py::test_python_import_extraction_and_resolution PASSED
backend/tests/unit/test_graph_engine.py::test_js_ts_import_resolution PASSED
backend/tests/unit/test_graph_engine.py::test_content_hash_integrity PASSED
backend/tests/unit/test_graph_engine.py::test_malformed_syntax_graceful_handling PASSED
backend/tests/integration/test_dependency_graph_api.py::test_full_repository_graph_indexing PASSED
backend/tests/integration/test_dependency_graph_api.py::test_incremental_indexing_idempotency PASSED
backend/tests/integration/test_dependency_graph_api.py::test_file_modification_and_incremental_reindexing PASSED
backend/tests/integration/test_dependency_graph_api.py::test_query_nodes_and_filtering PASSED
backend/tests/integration/test_dependency_graph_api.py::test_node_detail_and_bounded_dependencies PASSED
backend/tests/integration/test_dependency_graph_api.py::test_cross_repository_isolation PASSED
backend/tests/unit/test_impact_analysis.py::test_valid_consumer_edge_types PASSED
backend/tests/unit/test_impact_analysis.py::test_deterministic_scoring_and_severity_bands PASSED
backend/tests/unit/test_impact_analysis.py::test_confidence_calculation_with_unresolved_edges PASSED
backend/tests/unit/test_impact_analysis.py::test_dependency_path_construction PASSED
backend/tests/integration/test_impact_analysis_api.py::test_impact_analysis_for_leaf_file PASSED
backend/tests/integration/test_impact_analysis_api.py::test_impact_analysis_for_symbol_target PASSED
backend/tests/integration/test_impact_analysis_api.py::test_impact_analysis_unresolved_or_empty_target PASSED
backend/tests/integration/test_impact_analysis_api.py::test_repository_isolation_and_unauthorized_access PASSED
backend/tests/integration/test_impact_analysis_api.py::test_agent_workflow_integration_smoke PASSED
============================== 20 passed in 8.14s ==============================
```

### 5.4 Full Backend Regression Suite
```
collected 281 items
.......................................................sss.............. [ 25%]
........................................................................ [ 51%]
........................................................................ [ 76%]
.................................................................        [100%]
=================== 278 passed, 3 skipped in 101.43s (0:01:41) =================
```

### 5.5 Frontend Production Build
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
├ ƒ /repositories/[id]                   16.1 kB         135 kB
├ ○ /settings                            2.34 kB         119 kB
├ ○ /signup                              3.43 kB         133 kB
├ ○ /tasks                               2.9 kB          120 kB
├ ƒ /tasks/[id]                          13.3 kB         132 kB
└ ○ /tasks/new                           4.42 kB         147 kB
+ First Load JS shared by all            87.3 kB
```

---

## 6. Honest Disclosures & Boundaries

1. **Static Analysis Limitations:** Impact analysis evaluates statically declared imports, class inheritance, and syntactic function calls. Dynamic runtime reflection, `eval()`, dependency injection containers with string lookups, and dynamically dispatched event buses cannot be resolved with 100% semantic certainty and are exposed as potential risks via the Confidence rating.
2. **Scope Adherence:** Stage 10.2 strictly focuses on blast radius, change impact calculation, dependency path explanations, and test recommendations. Monorepo workspace boundaries, cross-repo dependency resolution, and automated refactoring are scheduled for subsequent stages.

---

## 7. Conclusion

Phase 10 Stage 10.2 has been successfully completed, verified, and documented across all references. Devora AI now provides deterministic, explainable, and multi-hop change impact intelligence that protects codebases from unintended downstream breakages.

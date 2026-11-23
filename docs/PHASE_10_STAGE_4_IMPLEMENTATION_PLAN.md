# Phase 10 Stage 10.4 Implementation Plan
## Semantic Architecture & Pattern Inference Engine

**Target Stage:** Phase 10, Stage 10.4  
**Components:**
1. Part A: Mandatory Security Follow-Up (Completed & Documented)
2. Part B: Semantic Architecture Intelligence & Plan
3. Part C: Hybrid Semantic Repository Search (Lexical + Semantic + Structural)
4. Part D: Architecture Pattern Inference & Convention Discovery
5. Part E: Agent Integration (Planner, Analyst, Coder, Reviewer, Reporter)
6. Part F: REST APIs & Next.js Frontend Visualizer Tab
7. Part G: Database Models, Migrations & Performance
8. Part H: Security Controls & Comprehensive Test Suite

---

## 1. Existing Semantic Search Architecture & Embedding Storage

- **Embedding Model:** 768-dimensional normalized embedding vectors generated via `generate_embedding_vector` in `backend/app/services/repo_intelligence_service.py` (compatible with Google `text-embedding-004`).
- **Storage:** PostgreSQL with `pgvector` extension; stored in `repository_knowledge.embedding` column with `VectorType(768)`.
- **Existing Search Capabilities:** `CodeSearchService` (`search_service.py`) provides basic keyword matching, AST symbol lookup, and in-memory cosine similarity on `RepositoryKnowledge`.
- **Existing Structural Knowledge:** `RepositoryGraphNode` and `RepositoryGraphEdge` store files, classes, methods, functions, and cross-file dependencies (`012_repository_dependency_graph.py`). `WorkspaceService` tracks workspaces, packages, and cross-package dependencies.

---

## 2. Proposed Hybrid Retrieval Architecture (Lexical + Semantic + Structural)

The new Hybrid Search Engine combines three complementary search modalities:

### 2.1 Lexical Search (Full-Text & Exact Identifier Matching)
- Matches exact symbols (`calculate_average`, `UserRegisterRequest`), file paths (`app/api/v1/auth.py`), API routes, error strings, and configuration keys.
- Utilizes SQL `ILIKE` tokenization and PostgreSQL `tsvector` / substring matching with BM25-style frequency term scoring.

### 2.2 Semantic Search (pgvector Cosine Distance)
- Reuses existing 768-dimensional embeddings stored in `RepositoryKnowledge`.
- Queries conceptual meaning (e.g. "how are user sessions validated?", "payment gateway integration", "error retry logic").
- Calculates cosine similarity $S_{sem} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$, normalized to $[0.0, 1.0]$.

### 2.3 Structural Search (AST Graph & Workspace Topology)
- Leverages `RepositoryGraphNode`, `RepositoryGraphEdge`, and workspace package topology.
- Boosts results that are central exported symbols, direct targets of incoming edges (`CALLS`, `IMPORTS`, `DEPENDS_ON`), or entry points.
- Traverses symbol definitions and cross-package boundaries.

### 2.4 Hybrid Ranking Formula: Weighted Reciprocal Rank Fusion (RRF)
To avoid blindly mixing disparate score scales, results from each modality are ranked and combined using Reciprocal Rank Fusion:
$$RRF(d) = \sum_{m \in \{\text{lexical}, \text{semantic}, \text{structural}\}} w_m \cdot \frac{1}{k + r_m(d)}$$
where $k = 60$, $w_{lex} = 0.35$, $w_{sem} = 0.45$, $w_{struct} = 0.20$, and $r_m(d)$ is the 1-based rank of document $d$ in modality $m$.
Every result returns explainable provenance:
```json
{
  "lexical_relevance": "HIGH",
  "semantic_similarity": 0.88,
  "structural_relevance": "MEDIUM",
  "final_score": 0.92,
  "rank": 1,
  "explanation": "Exact symbol match on 'AuthService' combined with high semantic conceptual match and 4 incoming import edges."
}
```

---

## 3. Architecture Pattern Inference Engine (`ArchitectureInferenceService`)

### 3.1 Taxonomy of Architectural Patterns
1. **Application Architecture Patterns:**
   - `layered_architecture`: Separation into UI/API, Service/Business Logic, Data Access/Persistence tiers.
   - `modular_monolith`: Monorepo or package structure with clear subsystem boundaries.
   - `clean_architecture` / `hexagonal`: Domain entities isolated from frameworks and databases via interfaces.
   - `service_layer`: Explicit service classes encapsulating business operations.
   - `repository_pattern`: Data access abstracted through dedicated repository classes/interfaces.
   - `event_driven`: Message brokers, event emitters, listeners, or streaming pipelines.
   - `plugin_architecture`: Extensible hook or plugin interfaces.

2. **Backend Implementation Patterns:**
   - `dependency_injection`: Dependencies passed into constructors or via framework DI (e.g. FastAPI `Depends`).
   - `middleware_auth`: Global middleware or interceptors handling JWT/session authentication.
   - `transaction_management`: Database transactions scoped with commit/rollback context managers.
   - `centralized_error_handling`: Standard exception hierarchy mapped to HTTP status codes.

3. **Frontend Architecture Patterns:**
   - `component_composition`: Modular UI components separated into layouts, primitives, and views.
   - `centralized_api_client`: Single HTTP client wrapping fetch/axios with authorization and error handling.
   - `shared_hooks`: React hooks encapsulating data fetching and caching (`useQuery`).

4. **AI & Agent Architecture Patterns:**
   - `agent_specialization`: Discrete specialist roles coordinated via directed graph workflows.
   - `isolated_sandbox`: Host-isolated execution containers with local fallbacks.
   - `model_gateway`: Centralized LLM gateway with circuit breakers, token budgets, and fallback models.

5. **Data Architecture Patterns:**
   - `orm_models`: Declarative SQLAlchemy models with relational constraints.
   - `migration_versioning`: Explicit sequential database migrations via Alembic.
   - `vector_memory`: Dedicated vector embeddings for semantic code and experience retrieval.

### 3.2 Evidence & Confidence Model
Every inferred pattern must have empirical evidence grounded in actual repository artifacts:
- **Evidence Status:**
  - `CONFIRMED`: Multiple direct structural indicators verified (AST nodes, imports, manifests). Confidence $\ge 0.85$.
  - `STRONGLY_SUPPORTED`: Consistent evidence across major modules. Confidence $0.70 - 0.84$.
  - `POSSIBLE`: Sparse or partial evidence. Confidence $0.40 - 0.69$.
  - `INSUFFICIENT_EVIDENCE`: Evaluated pattern lacks sufficient structural backing. Confidence $< 0.40$.
- **Supporting Evidence Fields:**
  - `supporting_files`: Relative paths of representative files.
  - `supporting_symbols`: Names of classes, functions, or interfaces demonstrating the pattern.
  - `supporting_relationships`: Relevant graph edges (`CALLS`, `IMPORTS`, `DEPENDS_ON`).
  - `supporting_config`: Configuration or manifest entries.
  - `counterexamples`: Identified modules that violate or diverge from the pattern.

---

## 4. Architectural Convention Discovery

Discovers repository-specific coding standards to answer: *"What conventions should a new developer follow?"*
- **Service Naming:** e.g. `*Service` classes in `app/services/`.
- **API Endpoints:** e.g. FastAPI APIRouters with Pydantic request/response schemas.
- **Dependency Injection:** e.g. FastAPI `Depends(get_db)` and `Depends(get_current_user)`.
- **Database Sessions:** Async SQLAlchemy `AsyncSession` injected via generators.
- **Error Handling:** Standard exceptions inheriting from `DevoraException`.
- **Test Organization:** Unit tests in `tests/unit/`, integration tests in `tests/integration/`.

---

## 5. Agent Integration

1. **Planner (`planner.py`):** Ingests inferred architectural patterns and conventions to ensure planned changes adhere to repository conventions.
2. **Codebase Analyst:** Utilizes `HybridSearch` to retrieve evidence-backed code snippets for user queries.
3. **Coder:** Incorporates discovered naming and service conventions when authoring patches; treats repository content as untrusted input.
4. **Code Reviewer (`code_reviewer.py`):** Audits proposed diffs against discovered conventions and pattern boundaries.
5. **Reporter (`reporter.py`):** Highlights architectural alignment and potential boundary violations in final reports.

---

## 6. Database Models & Alembic Migration

- **Model:** `RepositoryArchitecturePattern` in `backend/app/models/repository_architecture_pattern.py`.
- **Migration:** `013_architecture_patterns.py` adding table `repository_architecture_patterns` with repository foreign key, category, pattern_id, confidence, evidence JSON, and unique constraint.

---

## 7. REST APIs & Frontend UI

### 7.1 Backend REST Endpoints (`backend/app/api/v1/architecture.py`)
- `POST /api/v1/repositories/{id}/search/hybrid`: Hybrid lexical + semantic + structural search.
- `GET /api/v1/repositories/{id}/architecture`: Architecture summary, patterns overview, and freshness.
- `POST /api/v1/repositories/{id}/architecture/analyze`: Trigger pattern inference and convention discovery.
- `GET /api/v1/repositories/{id}/architecture/patterns`: List inferred patterns with evidence.
- `GET /api/v1/repositories/{id}/architecture/patterns/{pattern_id}`: Detailed pattern evidence.
- `GET /api/v1/repositories/{id}/architecture/conventions`: List repository conventions.
- `POST /api/v1/repositories/{id}/architecture/ask`: Natural-language "Ask Your Codebase" question answering.

### 7.2 Frontend Next.js Architecture Intelligence Tab
- Integrated into `/repositories/[id]` as "Architecture Intelligence".
- Sub-views:
  - **Overview:** Pattern badges, confidence meters, ecosystem architecture summary.
  - **Pattern Explorer:** Searchable patterns, evidence drawer, supporting files/symbols, counterexamples.
  - **Conventions Guide:** Developer handbook of discovered repository conventions.
  - **Hybrid Code Search:** Search with lexical/semantic/structural breakdown chips and line ranges.
  - **Ask Your Codebase:** Interactive Q&A interface with evidence references.

---

## 8. Performance & Security Considerations

- **Secret Redaction:** All search snippets pass through `scrub_credentials` before returning to user/frontend.
- **Untrusted Input Defense:** Repository source snippets, comments, and docstrings are treated as untrusted data; prompt injection guardrails prevent instructions in source files from overriding agent behavior.
- **Tenant Isolation:** Enforced via `get_repository_for_user` checking `repository.user_id == current_user.id`.
- **Zero Hallucination:** Claims require concrete file paths, symbol names, or AST edges; LLM outputs are categorized as explanations, not primary proof.

---

## 9. Testing & Verification Strategy

- **Hybrid Search Tests:**
  - `test_hybrid_search_exact_symbol`: Lexical dominance on exact identifier queries.
  - `test_hybrid_search_semantic`: Vector similarity on conceptual questions.
  - `test_hybrid_ranking_rrf`: Deterministic Reciprocal Rank Fusion scoring and deduplication.
  - `test_hybrid_search_filters`: Language, package, and symbol filters.
  - `test_secret_redaction_in_snippets`: Verifies sensitive credentials in code are redacted.
- **Architecture Inference Tests:**
  - `test_detect_layered_and_service_architecture`: Confirms detection on structured projects.
  - `test_insufficient_evidence_handling`: Returns `INSUFFICIENT_EVIDENCE` for unstructured repos without forced classification.
  - `test_convention_discovery`: Extracts service and API conventions accurately.
- **Integration Tests:**
  - Full API lifecycle across `/search/hybrid`, `/architecture/analyze`, `/patterns`, and `/ask`.
  - Tenant isolation and unauthorized access tests.
- **Regression:** Verify 294+ backend tests pass and 16/16 frontend routes compile.

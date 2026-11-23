export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface Repository {
  id: string;
  project_id: string;
  user_id: string;
  name: string;
  full_name: string;
  clone_url: string;
  default_branch: string;
  language: string | null;
  installation_id?: number | null;
  is_private?: boolean;
  permissions?: Record<string, any>;
  current_commit_sha?: string | null;
  indexing_status?: "NOT_INDEXED" | "INDEXING" | "INDEXED" | "FAILED" | string;
  last_indexed_at?: string | null;
  metadata: Record<string, any>;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface IndexingJob {
  id: string;
  repository_id: string;
  commit_sha: string;
  branch: string;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | string;
  files_count: number;
  symbols_count: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface RepositoryFile {
  id: string;
  repository_id: string;
  file_path: string;
  language: string | null;
  size_bytes: number;
  lines_count: number;
  commit_sha: string;
  summary: string | null;
  metadata: Record<string, any>;
}

export interface RepositorySymbol {
  name: string;
  type: string;
  file_path: string;
  start_line: number;
  end_line: number;
  signature: string;
  docstring?: string | null;
}

export interface RepositoryArchitecture {
  repository_id: string;
  primary_language: string | null;
  current_commit_sha: string | null;
  frameworks: string[];
  entry_points: string[];
  manifests: string[];
  total_files: number;
  total_lines: number;
  architecture_summary: string;
  coding_conventions: string;
}

export interface CodeSearchResultItem {
  file_path: string;
  match_type: "keyword" | "symbol" | "semantic" | string;
  line_number?: number | null;
  snippet: string;
  symbol_name?: string | null;
  symbol_type?: string | null;
  score: number;
}

export interface RepositoryMemory {
  id: string;
  repository_id: string;
  category: string;
  title?: string | null;
  content: string;
  source_reference?: string | null;
  commit_sha?: string | null;
  verification_status: "observed_fact" | "ai_hypothesis" | "developer_confirmed" | "verified_outcome" | string;
  access_scope: string;
  is_stale: boolean;
  stale_reason?: string | null;
  helpful_count: number;
  unhelpful_count: number;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface MemorySearchResult {
  id: string;
  repository_id: string;
  category: string;
  title?: string | null;
  content: string;
  source_reference?: string | null;
  commit_sha?: string | null;
  verification_status: string;
  is_stale: boolean;
  stale_reason?: string | null;
  helpful_count: number;
  unhelpful_count: number;
  raw_similarity: number;
  score: number;
  created_at?: string | null;
  metadata?: Record<string, any>;
}

export interface MemoryStats {
  repository_id: string;
  total_memories: number;
  verified_count: number;
  stale_count: number;
  categories: Record<string, number>;
  verification_statuses: Record<string, number>;
}

export interface CodeSearchResponse {
  repository_id: string;
  query: string;
  search_type: string;
  results: CodeSearchResultItem[];
  total_matches: number;
}

export interface TaskPlanStep {
  step_number: number;
  description: string;
  target_files: string[];
  verification_check?: string;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED";
}

export interface TaskPlan {
  id: string;
  task_id: string;
  steps: TaskPlanStep[];
  test_criteria: string[];
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  created_at: string;
}

export type TaskStatus =
  | "PENDING"
  | "PLANNING"
  | "IN_PROGRESS"
  | "TESTING"
  | "WAITING_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface Task {
  id: string;
  project_id: string;
  repository_id: string;
  created_by: string;
  title: string;
  prompt: string;
  error_traceback: string | null;
  task_type: string;
  status: TaskStatus;
  iterations_count: number;
  target_branch: string;
  task_branch?: string | null;
  commit_sha?: string | null;
  pull_request_url: string | null;
  recovery_status?: string;
  recovery_attempts?: number;
  last_heartbeat_at?: string | null;
  recovery_lease_owner?: string | null;
  recovery_lease_expires_at?: string | null;
  recovery_error?: string | null;
  created_at: string;
  updated_at: string;
  plans?: TaskPlan[];
}

export interface Report {
  id: string;
  task_id: string;
  title: string;
  summary: string;
  root_cause_analysis: string;
  test_summary: Record<string, any>;
  markdown_content: string;
  created_at: string;
}

export interface AgentRun {
  id: string;
  task_id: string;
  agent_name: string;
  step_number: number;
  input_state: Record<string, any>;
  output_state: Record<string, any>;
  duration_ms: number;
  created_at: string;
}

export interface FileChange {
  id: string;
  task_id: string;
  file_path: string;
  change_type: string;
  original_content?: string | null;
  new_content?: string | null;
  diff: string;
  created_at: string;
}

export interface TestRun {
  id: string;
  task_id: string;
  iteration: number;
  command: string;
  exit_code: number;
  passed: boolean;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests?: number;
  stdout?: string | null;
  stderr?: string | null;
  duration_seconds: number;
  created_at: string;
  detected_languages?: string[];
  detected_frameworks?: string[];
  package_manager?: string | null;
  discovery_status?: string;
  execution_status?: string;
  selected_test_files?: string[];
  is_targeted?: boolean;
  failure_classification?: string | null;
  diagnostic_warning?: string | null;
  stability_classification?: string | null;
  stability_score?: number | null;
  is_flaky?: boolean;
  flaky_repeat_runs?: Array<{
    run_index: number;
    exit_code: number;
    passed: boolean;
    duration_seconds: number;
    is_infra_error?: boolean;
    is_timeout?: boolean;
    error_preview?: string | null;
  }>;
  peak_memory_rss_bytes?: number | null;
  peak_memory_rss_mb?: number | null;
  cpu_time_seconds?: number | null;
  wall_time_seconds?: number | null;
  memory_limit_bytes?: number | null;
  memory_limit_mb?: number | null;
  cpu_limit?: number | null;
  oom_killed?: boolean;
  termination_reason?: string | null;
  exit_classification?: string;
  resource_telemetry_available?: boolean;
}

export interface FlakyTestRecord {
  id: string;
  repository_id: string;
  task_id: string;
  test_identifier: string;
  test_file: string;
  framework: string;
  language: string;
  test_command: string;
  classification: "STABLE_PASS" | "CONSISTENT_FAILURE" | "FLAKY" | "INCONCLUSIVE" | "UNVERIFIED" | string;
  stability_score: number;
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  infrastructure_error_runs: number;
  timeout_runs: number;
  execution_history: Record<string, any>;
  first_detected_at: string;
  last_detected_at: string;
  last_verified_at: string;
  created_at: string;
}

export interface RepositoryStabilitySummary {
  repository_id: string;
  total_tests_tracked: number;
  flaky_tests_count: number;
  stable_pass_count: number;
  consistent_failure_count: number;
  average_stability_score: number;
  total_repeat_runs_executed: number;
}

export interface Approval {
  id: string;
  task_id: string;
  requested_by: string;
  reviewed_by?: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | "CHANGES_REQUESTED" | string;
  notes?: string | null;
  requested_at: string;
  responded_at?: string | null;
}

export interface WorkflowEvent {
  id?: string;
  task_id: string;
  event_type: string;
  agent_name?: string | null;
  message: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, any>;
    timestamp: string;
  };
}

export interface GitHubStatus {
  app_configured: boolean;
  app_id?: string | null;
  has_private_key: boolean;
  is_mock: boolean;
}

export interface GitHubInstallation {
  id: string;
  user_id: string;
  installation_id: number;
  account_login: string;
  account_type: string;
  repository_selection: string;
  permissions: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GitHubRepositoryItem {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  clone_url: string;
  default_branch: string;
  language?: string | null;
  permissions: Record<string, boolean>;
}

export interface GitBranch {
  id?: string;
  name: string;
  commit_sha?: string | null;
  base_branch?: string;
  is_default: boolean;
  is_task_branch: boolean;
  is_pushed: boolean;
  task_id?: string | null;
  created_at?: string;
}

export interface PullRequest {
  id: string;
  task_id: string;
  repository_id: string;
  pr_number: number;
  title: string;
  body: string;
  html_url: string;
  head_branch: string;
  base_branch: string;
  state: "open" | "closed" | "merged" | string;
  is_merged: boolean;
  merge_commit_sha?: string | null;
  merged_at?: string | null;
  closed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CheckpointSummary {
  checkpoint_id: string;
  node_name?: string | null;
  step_number: number;
  thread_id: string;
  created_at?: string | null;
}

export interface TaskRecoveryStatusResponse {
  task_id: string;
  status: string;
  recovery_status: string;
  is_interrupted: boolean;
  interruption_reason?: string | null;
  is_eligible_for_recovery: boolean;
  eligibility_reason: string;
  recovery_attempts: number;
  max_recovery_attempts: number;
  last_heartbeat_at?: string | null;
  recovery_lease_owner?: string | null;
  recovery_lease_expires_at?: string | null;
  recovery_error?: string | null;
  latest_checkpoint?: CheckpointSummary | null;
}

export interface TaskResumeResponse {
  task_id: string;
  status: string;
  recovery_status: string;
  resumed_from_node: string;
  step_number: number;
  recovery_attempts: number;
  message: string;
}

export interface InterruptedTaskItem {
  task_id: string;
  title: string;
  status: string;
  recovery_status: string;
  interruption_reason: string;
  eligible: boolean;
  recovery_attempts: number;
  last_heartbeat_at?: string | null;
  latest_node?: string | null;
}

export interface InterruptedTaskScanResponse {
  scanned_tasks_count: number;
  interrupted_tasks: InterruptedTaskItem[];
}

export interface ModelCircuitBreakerStatus {
  key: string;
  provider_name: string;
  model_name: string;
  state: "CLOSED" | "OPEN" | "HALF_OPEN" | string;
  consecutive_failures: number;
  consecutive_successes: number;
  recent_failures_in_window: number;
  failure_threshold: number;
  open_duration_seconds: number;
  time_until_probe_seconds?: number | null;
  last_failure_reason?: string | null;
  last_failure_classification?: string | null;
  last_failure_at?: string | null;
  last_success_at?: string | null;
  total_calls: number;
  total_failures: number;
  total_probes: number;
}

export interface ModelGatewayMetrics {
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_retries: number;
  total_fallbacks: number;
  last_active_at?: string | null;
}

export interface ModelGatewayHealthResponse {
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | string;
  circuit_breaker_enabled: boolean;
  active_primary_provider: string;
  active_primary_model: string;
  fallback_enabled: boolean;
  fallback_models: string[];
  breakers: ModelCircuitBreakerStatus[];
  metrics: ModelGatewayMetrics;
  timestamp: string;
}

// Phase 9 Stage 9.6: Reliability Observability Console Types
export interface SubsystemHealth {
  name: string;
  display_name: string;
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "UNKNOWN" | string;
  description: string;
  last_activity_at?: string | null;
  last_failure_reason?: string | null;
  metrics: Record<string, any>;
}

export interface WorkflowReliabilitySummary {
  total_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  interrupted_tasks: number;
  waiting_approval_tasks: number;
  recovering_tasks: number;
  recovery_success_rate: number;
  avg_duration_seconds: number;
  recovery_attempt_distribution: Record<string, number>;
}

export interface SandboxReliabilitySummary {
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  oom_terminations: number;
  timeouts: number;
  process_killed: number;
  runner_unavailable: number;
  startup_failures: number;
  avg_duration_seconds: number;
  avg_peak_memory_mb: number;
  max_peak_memory_mb: number;
  memory_limit_utilization_pct: number;
  total_cpu_time_seconds: number;
}

export interface TestStabilitySummary {
  total_tracked_tests: number;
  stable_pass_count: number;
  consistent_failure_count: number;
  flaky_count: number;
  inconclusive_count: number;
  unverified_count: number;
  avg_stability_score: number;
  total_repeat_runs: number;
}

export interface ModelGatewayReliabilitySummary {
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | string;
  active_primary_provider: string;
  active_primary_model: string;
  fallback_enabled: boolean;
  fallback_models: string[];
  circuit_states: Record<string, string>;
  total_retries: number;
  total_fallbacks: number;
  total_requests: number;
  average_latency_ms: number;
  multi_worker_shared_state: boolean;
  deployment_topology: string;
  last_active_at?: string | null;
}

export interface RecoveryOperationsSummary {
  interrupted_tasks_count: number;
  recovery_eligible_count: number;
  recovering_count: number;
  recovery_failures_count: number;
  manual_intervention_required_count: number;
  interrupted_tasks: InterruptedTaskItem[];
}

export interface SecurityReliabilitySummary {
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | string;
  secret_scan_status: "PASSED" | "FAILED" | string;
  credentials_hygiene_score: number;
  working_tree_clean: boolean;
  historical_exposure_detected: boolean;
  scanner_coverage_pct: number;
  last_scan_timestamp?: string | null;
  scanner_availability: string;
  unverified_areas: string[];
  monorepo_detected: boolean;
  total_workspaces: number;
  total_packages: number;
  active_findings_count: number;
}

export interface ReliabilityOverviewResponse {
  timestamp: string;
  overall_system_status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | string;
  subsystems: SubsystemHealth[];
  workflows: WorkflowReliabilitySummary;
  sandbox: SandboxReliabilitySummary;
  test_stability: TestStabilitySummary;
  model_gateway: ModelGatewayReliabilitySummary;
  recovery: RecoveryOperationsSummary;
  security?: SecurityReliabilitySummary;
}

export interface ReliabilityEventItem {
  id: string;
  timestamp: string;
  task_id?: string | null;
  repository_id?: string | null;
  repository_name?: string | null;
  task_title?: string | null;
  subsystem: string;
  event_type: string;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL" | string;
  message: string;
  payload: Record<string, any>;
}

export interface ReliabilityEventsResponse {
  total: number;
  limit: number;
  offset: number;
  events: ReliabilityEventItem[];
}

export interface ReliabilityTrendBucket {
  bucket_time: string;
  tasks_completed: number;
  tasks_failed: number;
  tasks_interrupted: number;
  sandbox_ooms: number;
  sandbox_timeouts: number;
  flaky_tests_detected: number;
  model_retries: number;
  recovery_attempts: number;
}

export interface ReliabilityTrendsResponse {
  timeframe: string;
  trends: ReliabilityTrendBucket[];
}

// -----------------------------------------------------------------------------
// Phase 10 Stage 10.1: Cross-File Symbol and Dependency Graph Types
// -----------------------------------------------------------------------------

export interface GraphNodeItem {
  id: string;
  repository_id: string;
  node_type: "REPOSITORY" | "DIRECTORY" | "FILE" | "MODULE" | "PACKAGE" | "CLASS" | "INTERFACE" | "FUNCTION" | "METHOD" | "VARIABLE" | "CONSTANT" | string;
  qualified_name: string;
  name: string;
  file_path?: string | null;
  language?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  metadata: Record<string, any>;
  content_hash?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphEdgeItem {
  id: string;
  repository_id: string;
  source_node_id: string;
  target_node_id?: string | null;
  edge_type: "CONTAINS" | "DEFINES" | "IMPORTS" | "DEPENDS_ON" | "INHERITS" | "IMPLEMENTS" | "REFERENCES" | "CALLS" | string;
  confidence: number;
  resolution_status: "RESOLVED" | "EXTERNAL" | "UNRESOLVED" | "AMBIGUOUS" | string;
  target_symbol?: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

export interface GraphNodeDetailResponse {
  node: GraphNodeItem;
  incoming_edges: GraphEdgeItem[];
  outgoing_edges: GraphEdgeItem[];
  related_nodes: Record<string, GraphNodeItem>;
}

export interface RepositoryGraphSummaryResponse {
  repository_id: string;
  total_nodes: number;
  total_edges: number;
  node_types_breakdown: Record<string, number>;
  edge_types_breakdown: Record<string, number>;
  languages_breakdown: Record<string, number>;
  unresolved_count: number;
  external_count: number;
  last_indexed_at?: string | null;
  current_commit_sha?: string | null;
  indexing_status: string;
}

export interface GraphNodesListResponse {
  total: number;
  limit: number;
  offset: number;
  nodes: GraphNodeItem[];
}

export interface GraphDependenciesResponse {
  root_node_id: string;
  direction: string;
  max_depth: number;
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
}

export interface UnresolvedReferenceItem {
  edge_id: string;
  source_file: string;
  source_symbol: string;
  target_symbol: string;
  edge_type: string;
  resolution_status: string;
  line_number?: number | null;
}

export interface GraphUnresolvedReferencesResponse {
  total: number;
  limit: number;
  offset: number;
  unresolved: UnresolvedReferenceItem[];
}

export interface GraphIndexingResponse {
  repository_id: string;
  status: string;
  commit_sha: string;
  total_files: number;
  files_indexed: number;
  files_skipped: number;
  nodes_created: number;
  edges_created: number;
  unresolved_references: number;
  duration_seconds: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 10 Stage 10.2: Blast Radius and Impact Analysis Types
// ---------------------------------------------------------------------------

export interface ImpactTarget {
  node_id?: string | null;
  node_type: string;
  qualified_name: string;
  name: string;
  file_path?: string | null;
}

export interface DependencyHop {
  source_node_id: string;
  source_name: string;
  source_type: string;
  edge_type: string;
  target_node_id?: string | null;
  target_name?: string | null;
  confidence: number;
  resolution_status: string;
}

export interface DependencyPathItem {
  target_name: string;
  impacted_node_id: string;
  impacted_name: string;
  impacted_file_path?: string | null;
  depth: number;
  hops: DependencyHop[];
  explanation: string;
}

export interface ImpactedNodeItem {
  node_id: string;
  node_type: string;
  qualified_name: string;
  name: string;
  file_path?: string | null;
  language?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  depth: number;
  is_direct: boolean;
  primary_reason: string;
  confidence: number;
  resolution_status: string;
  paths_count: number;
  metadata: Record<string, any>;
}

export interface RecommendedTestItem {
  test_file_path: string;
  test_framework?: string | null;
  recommendation_type: "CONFIRMED" | "HEURISTIC" | string;
  confidence: number;
  reason: string;
  target_symbol_or_file: string;
}

export interface UnresolvedWarningItem {
  edge_id?: string | null;
  source_node_name: string;
  source_file?: string | null;
  target_symbol: string;
  edge_type: string;
  resolution_status: string;
  message: string;
}

export interface ImpactScoreBreakdown {
  files_score: number;
  symbols_score: number;
  depth_score: number;
  coupling_score: number;
  untested_penalty: number;
}

export interface ImpactSummaryMetrics {
  total_affected_files: number;
  total_affected_symbols: number;
  direct_impact_count: number;
  transitive_impact_count: number;
  recommended_tests_count: number;
  unresolved_warnings_count: number;
}

export interface ImpactAnalysisRequest {
  file_paths?: string[];
  symbol_ids?: string[];
  qualified_names?: string[];
  max_depth?: number;
  include_tests?: boolean;
  max_impacted_nodes?: number;
}

export interface ImpactAnalysisResponse {
  repository_id: string;
  commit_sha?: string | null;
  is_stale: boolean;
  staleness_reason?: string | null;
  targets: ImpactTarget[];
  impact_score: number;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN" | string;
  confidence: number;
  score_explanation: string;
  score_breakdown: ImpactScoreBreakdown;
  summary: ImpactSummaryMetrics;
  affected_files: string[];
  affected_packages?: string[];
  cross_package_boundaries?: boolean;
  impacted_nodes: ImpactedNodeItem[];
  dependency_paths: DependencyPathItem[];
  recommended_tests: RecommendedTestItem[];
  unresolved_warnings: UnresolvedWarningItem[];
  execution_duration_seconds: number;
}

// -----------------------------------------------------------------------------
// Phase 10 Stage 10.3: Monorepo & Workspace Intelligence Engine Types
// -----------------------------------------------------------------------------

export interface PackageInfo {
  id?: string | null;
  name: string;
  version?: string | null;
  path: string;
  manifest_path: string;
  language: string;
  internal_dependencies: string[];
  external_dependencies: string[];
  files_count: number;
  metadata?: Record<string, any>;
}

export interface WorkspaceInfo {
  id?: string | null;
  workspace_type: string;
  root_path: string;
  manifest_file?: string | null;
  packages_count: number;
  packages: PackageInfo[];
  metadata?: Record<string, any>;
}

export interface CrossPackageEdgeItem {
  source_package: string;
  target_package: string;
  edge_type: string;
  confidence: number;
}

export interface WorkspaceSummary {
  total_workspaces: number;
  total_packages: number;
  ecosystems: string[];
  is_monorepo: boolean;
}

export interface WorkspaceGraphResponse {
  repository_id: string;
  workspaces: WorkspaceInfo[];
  cross_package_edges: CrossPackageEdgeItem[];
  summary: WorkspaceSummary;
}

export interface PackageDependenciesResponse {
  package_id: string;
  package_name: string;
  package_path: string;
  internal_dependencies: PackageInfo[];
  external_dependencies: string[];
  dependents: PackageInfo[];
}

export interface AffectedPackageItem {
  package_name: string;
  package_path: string;
  depth: number;
  dependency_path: string[];
}

export interface PackageImpactResponse {
  package_id: string;
  package_name: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  affected_packages: AffectedPackageItem[];
  affected_packages_count: number;
  affected_files_count: number;
  recommendations: string[];
}

export interface WorkspaceIndexResponse {
  repository_id: string;
  workspaces_found: number;
  packages_indexed: number;
  edges_created: number;
  duration_seconds: number;
  status: string;
}

// -------------------------------------------------------------
// Phase 10 Stage 10.4: Semantic Architecture & Pattern Inference
// -------------------------------------------------------------

export interface HybridSearchFilter {
  languages?: string[];
  packages?: string[];
  file_paths?: string[];
  symbol_types?: string[];
}

export interface HybridSearchRequest {
  query: string;
  filters?: HybridSearchFilter;
  limit?: number;
  offset?: number;
  lexical_weight?: number;
  semantic_weight?: number;
  structural_weight?: number;
}

export interface HybridSearchResultItem {
  file_path: string;
  line_number: number;
  line_end?: number | null;
  symbol_name?: string | null;
  symbol_type?: string | null;
  package_name?: string | null;
  language?: string | null;
  snippet: string;
  lexical_score: number;
  semantic_score: number;
  structural_score: number;
  combined_score: number;
  rank: number;
  provenance_explanation: string;
}

export interface HybridSearchResponse {
  repository_id: string;
  query: string;
  total_matches: number;
  limit: number;
  offset: number;
  results: HybridSearchResultItem[];
  search_duration_seconds: number;
}

export interface ArchitectureConventionItem {
  name: string;
  category: "service" | "api" | "database" | "error" | "test" | "agent" | string;
  description: string;
  confidence: number;
  supporting_examples: string[];
  relevant_paths: string[];
  applicability_scope: string;
  potential_exceptions?: string[];
}

export interface ArchitecturePatternItem {
  id?: string | null;
  pattern_id: string;
  category: "application" | "backend" | "frontend" | "ai_agent" | "data" | string;
  name: string;
  description: string;
  evidence_status: "CONFIRMED" | "STRONGLY_SUPPORTED" | "POSSIBLE" | "INSUFFICIENT_EVIDENCE";
  confidence_score: number;
  supporting_files: string[];
  supporting_symbols: string[];
  supporting_relationships: Array<Record<string, unknown>>;
  supporting_config: Record<string, unknown>;
  counterexamples: string[];
  conventions: ArchitectureConventionItem[];
}

export interface ArchitectureSummaryResponse {
  repository_id: string;
  primary_language?: string | null;
  current_commit_sha?: string | null;
  total_patterns: number;
  confirmed_patterns_count: number;
  patterns: ArchitecturePatternItem[];
  conventions: ArchitectureConventionItem[];
  is_stale: boolean;
  last_analyzed_at?: string | null;
}

export interface ArchitectureAskRequest {
  question: string;
  context_limit?: number;
}

export interface ArchitectureAskResponse {
  repository_id: string;
  question: string;
  answer: string;
  confidence: number;
  supporting_evidence: Array<{
    file_path: string;
    line_number: number;
    symbol_name?: string | null;
    snippet: string;
    score: number;
    provenance: string;
  }>;
  relevant_files: string[];
  inferred_patterns_referenced: string[];
}

// -----------------------------------------------------------------------------
// Phase 10 Stage 10.5: Architectural Drift & Technical Debt Types
// -----------------------------------------------------------------------------

export interface DriftViolationItem {
  id: string;
  rule_id: string;
  category: "layering" | "dependency" | "convention" | "security" | "pattern" | string;
  name: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  confidence: number;
  source_file: string;
  target_file?: string | null;
  source_symbol?: string | null;
  target_symbol?: string | null;
  line_number: number;
  explanation: string;
  remediation_recommendation: string;
  evidence_snippet?: string | null;
}

export interface ArchitectureDriftResponse {
  repository_id: string;
  commit_sha?: string | null;
  baseline_commit_sha?: string | null;
  drift_status: "HEALTHY" | "DRIFT_DETECTED" | "CRITICAL_DRIFT" | string;
  total_violations: number;
  critical_violations: number;
  high_violations: number;
  medium_violations: number;
  low_violations: number;
  violations: DriftViolationItem[];
  resolved_violations: DriftViolationItem[];
  summary: Record<string, unknown>;
  is_stale: boolean;
  last_analyzed_at?: string | null;
}

export interface TechnicalDebtFindingItem {
  finding_id: string;
  category: "duplication" | "complexity" | "dependency" | "maintainability" | "test" | string;
  title: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  confidence: number;
  file_path: string;
  symbol_name?: string | null;
  line_number: number;
  line_end?: number | null;
  measured_metric: Record<string, unknown>;
  explanation: string;
  remediation: string;
  potential_impact: string;
  detection_method: string;
  evidence_snippet?: string | null;
}

export interface TechnicalDebtDimensionScores {
  complexity: number;
  duplication: number;
  dependency: number;
  architecture_drift: number;
  test_debt: number;
  maintainability: number;
}

export interface TechnicalDebtSummaryResponse {
  repository_id: string;
  commit_sha?: string | null;
  overall_debt_score: number;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "CLEAN" | string;
  confidence: number;
  dimension_scores: TechnicalDebtDimensionScores;
  summary_metrics: Record<string, unknown>;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  medium_findings: number;
  low_findings: number;
  top_findings: TechnicalDebtFindingItem[];
  is_stale: boolean;
  last_analyzed_at?: string | null;
}

export interface TechnicalDebtFindingsResponse {
  repository_id: string;
  total_count: number;
  limit: number;
  offset: number;
  findings: TechnicalDebtFindingItem[];
}

export interface TechnicalDebtTrendItem {
  commit_sha: string;
  analyzed_at: string;
  overall_debt_score: number;
  severity: string;
  critical_findings: number;
  total_findings: number;
}

export interface TechnicalDebtTrendsResponse {
  repository_id: string;
  trends: TechnicalDebtTrendItem[];
}

// ---------------------------------------------------------------------------
// Architecture-Aware Refactoring & Safe Remediation (Stage 10.6)
// ---------------------------------------------------------------------------

export type RefactoringCategory =
  | "LAYERING"
  | "DEPENDENCY"
  | "DUPLICATION"
  | "COMPLEXITY"
  | "CONVENTION"
  | "TESTABILITY"
  | string;

export type RefactoringPlanStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "EXECUTING"
  | "APPLIED"
  | "ROLLED_BACK"
  | "INVALIDATED"
  | string;

export interface RefactoringRecommendationItem {
  recommendation_id: string;
  category: RefactoringCategory;
  title: string;
  description: string;
  rationale: string;
  target_files: string[];
  target_symbols: string[];
  related_finding_ids: string[];
  estimated_effort: "LOW" | "MEDIUM" | "HIGH" | string;
  impact_score: number;
  confidence: number;
  suggested_action: string;
}

export interface RefactoringRecommendationsResponse {
  repository_id: string;
  commit_sha?: string | null;
  total_recommendations: number;
  by_category: Record<string, number>;
  recommendations: RefactoringRecommendationItem[];
}

export interface RefactoringStepItem {
  step_number: number;
  action_type: string;
  target_file: string;
  target_symbol?: string | null;
  description: string;
  dependency_steps: number[];
  verification_check: string;
}

export interface RefactoringPlanCreateRequest {
  title: string;
  category: RefactoringCategory;
  description?: string;
  recommendation_ids?: string[];
  target_files: string[];
  target_symbols?: string[];
}

export interface RefactoringPlanResponse {
  id: string;
  repository_id: string;
  user_id: string;
  title: string;
  category: RefactoringCategory;
  description: string;
  status: RefactoringPlanStatus;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | string;
  confidence: number;
  requires_human_approval: boolean;
  approved_by?: string | null;
  approved_at?: string | null;
  approved_diff_hash?: string | null;
  rejection_reason?: string | null;
  steps: RefactoringStepItem[];
  target_files: string[];
  target_symbols: string[];
  affected_components: string[];
  created_at: string;
  updated_at: string;
}

export interface RefactoringPlansListResponse {
  repository_id: string;
  total_plans: number;
  plans: RefactoringPlanResponse[];
}

export interface RefactoringApproveRequest {
  diff_hash: string;
  notes?: string;
}

export interface RefactoringExecuteRequest {
  current_diff_hash?: string;
  task_id?: string;
}

export interface RefactoringExecutionResponse {
  id: string;
  plan_id: string;
  repository_id: string;
  user_id: string;
  status: string;
  is_success: boolean;
  preserved_semantics: boolean;
  baseline_tests_passed: boolean;
  post_refactor_tests_passed: boolean;
  baseline_passed_count: number;
  post_refactor_passed_count: number;
  api_parity_passed: boolean;
  diff_hash_matched: boolean;
  rolled_back: boolean;
  rollback_reason?: string | null;
  files_modified_count: number;
  lines_added: number;
  lines_removed: number;
  execution_duration_ms: number;
  applied_diff: string;
  verification_report: Record<string, any>;
  created_at: string;
}

export interface BeforeAfterComparisonResponse {
  repository_id: string;
  plan_id: string;
  execution_id: string;
  baseline_metrics: Record<string, any>;
  post_refactor_metrics: Record<string, any>;
  delta_metrics: Record<string, any>;
  drift_reduction_count: number;
  debt_score_reduction: number;
  behavioral_preservation_score: number;
}

// -----------------------------------------------------------------------------
// Phase 10 Stage 10.7: Benchmark Engine Interfaces
// -----------------------------------------------------------------------------

export type BenchmarkCategory =
  | "bug_detection"
  | "repo_understanding"
  | "arch_intelligence"
  | "impact_analysis"
  | "refactoring"
  | "multi_agent"
  | "security_safety";

export interface BenchmarkScenario {
  id: string;
  scenario_key: string;
  category: BenchmarkCategory | string;
  name: string;
  description: string;
  difficulty: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  eval_type: "EXACT_MATCH" | "STRUCTURAL" | "AST_DELTA" | "TEST_ASSERTION" | "SECURITY_POLICY" | string;
  input_context: Record<string, any>;
  expected_output: Record<string, any>;
  evaluation_criteria: Record<string, any>;
  is_active: boolean;
  version: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface BenchmarkScenariosListResponse {
  total_count: number;
  category_counts: Record<string, number>;
  scenarios: BenchmarkScenario[];
}

export interface BenchmarkScenarioResult {
  result_id: string;
  run_id: string;
  scenario_id: string;
  scenario_key: string;
  category: string;
  name: string;
  status: "PASSED" | "FAILED" | "TIMEOUT" | "ERROR" | "SAFETY_VIOLATION" | string;
  score: number;
  actual_output: Record<string, any>;
  expected_output: Record<string, any>;
  diff_summary?: string | null;
  execution_time_ms: number;
  tokens_used: number;
  confidence_score?: number | null;
  invariants_met: boolean;
  safety_violated: boolean;
  failure_reason?: string | null;
  evidence: Record<string, any>;
  created_at: string;
}

export interface BenchmarkSuiteRun {
  run_id: string;
  suite_name: string;
  model_name: string;
  code_revision?: string | null;
  dataset_version: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CRITICAL_SAFETY_FAILURE" | "CANCELLED" | string;
  total_scenarios: number;
  passed_scenarios: number;
  failed_scenarios: number;
  critical_safety_failure: boolean;
  aggregate_score: number;
  category_scores: Record<string, number>;
  calibration_error: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  token_usage_total: number;
  cost_estimate_usd: number;
  created_at: string;
  completed_at?: string | null;
}

export interface BenchmarkSuiteRunDetail extends BenchmarkSuiteRun {
  results: BenchmarkScenarioResult[];
}

export interface BenchmarkSuiteRunsListResponse {
  total_count: number;
  runs: BenchmarkSuiteRun[];
}

export interface BenchmarkRegression {
  regression_id: string;
  baseline_run_id: string;
  target_run_id: string;
  scenario_id: string;
  scenario_key: string;
  category: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  baseline_score: number;
  target_score: number;
  score_delta: number;
  percentage_change: number;
  description: string;
  regression_type: "ACCURACY_DROP" | "LATENCY_SPIKE" | "SAFETY_BREACH" | "INVARIANT_FAILURE" | string;
  created_at: string;
}

export interface BenchmarkRunComparisonRequest {
  baseline_run_id: string;
  target_run_id: string;
  regression_threshold?: number;
}

export interface BenchmarkRunComparisonResponse {
  baseline_run_id: string;
  target_run_id: string;
  baseline_model: string;
  target_model: string;
  baseline_score: number;
  target_score: number;
  score_delta: number;
  percentage_change: number;
  category_deltas: Record<string, { baseline: number; target: number; delta: number }>;
  latency_delta_ms: number;
  cost_delta_usd: number;
  regressions_count: number;
  critical_regressions: number;
  regressions: BenchmarkRegression[];
  summary_verdict: "IMPROVED" | "REGRESSED" | "PARITY" | "CRITICAL_SAFETY_BREACH" | string;
}

export interface BenchmarkReportResponse {
  run_id: string;
  title: string;
  generated_at: string;
  markdown_content: string;
  summary_metrics: Record<string, any>;
}









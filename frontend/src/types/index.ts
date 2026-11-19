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


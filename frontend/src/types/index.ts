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
  pull_request_url: string | null;
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
  stdout?: string | null;
  stderr?: string | null;
  duration_seconds: number;
  created_at: string;
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

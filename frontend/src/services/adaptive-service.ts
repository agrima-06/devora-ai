import { apiClient } from "@/lib/api-client";

export interface EngineeringExperience {
  id: string;
  repository_id?: string | null;
  task_category: string;
  bug_category?: string | null;
  problem_summary: string;
  root_cause: string;
  resolution_strategy: string;
  diff_patch: string;
  status_type: "verified_successful" | "verified_failed" | "unverified_hypothesis" | "incomplete_attempt";
  technology_stack: string[];
  files_involved: string[];
  attempts_count: number;
  failed_approaches: Array<Record<string, unknown>>;
  successful_approach?: string | null;
  test_results: Record<string, unknown>;
  review_findings: Record<string, unknown>;
  security_findings: Record<string, unknown>;
  failure_type?: string | null;
  is_verified: boolean;
  is_anonymized: boolean;
  quality_score: number;
  commit_sha?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperienceSearchResult {
  id: string;
  task_category: string;
  bug_category?: string | null;
  problem_summary: string;
  root_cause: string;
  resolution_strategy: string;
  status_type: string;
  technology_stack: string[];
  files_involved: string[];
  similarity: number;
  weighted_score: number;
  is_positive_guidance: boolean;
}

export interface TaskFailureRecord {
  id: string;
  task_id: string;
  stage: string;
  failure_type: string;
  attempt_number: number;
  failed_strategy: string;
  error_log: string;
  review_notes?: string | null;
  lessons_learned: string;
  created_at: string;
}

export interface AgentPerformanceMetric {
  agent_name: string;
  total_runs: int_or_number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  average_duration_ms: number;
  retry_frequency: number;
  rejection_rate: number;
  estimated_tokens_used: number;
  estimated_cost_usd: number;
}
type int_or_number = number;

export interface AgentPerformanceResponse {
  agents: AgentPerformanceMetric[];
  total_tasks_evaluated: number;
  overall_first_pass_rate: number;
  average_task_duration_seconds: number;
  categories_breakdown: Record<string, Record<string, unknown>>;
}

export interface BenchmarkDefinition {
  id: string;
  name: string;
  category: string;
  description: string;
  initial_repo_snapshot: string;
  expected_outcomes: Record<string, unknown>;
  evaluation_criteria: Record<string, unknown>;
  baseline_pass_rate: number;
}

export interface BenchmarkRun {
  id: string;
  benchmark_id: string;
  system_version: string;
  model_version: string;
  task_completed: boolean;
  tests_passed: boolean;
  retries_count: number;
  planning_efficiency_score: number;
  execution_time_ms: number;
  tokens_used: number;
  estimated_cost_usd: number;
  review_passed: boolean;
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface BenchmarkSummary {
  system_version: string;
  total_benchmarks: number;
  tasks_completed_count: number;
  completion_rate: number;
  tests_passed_count: number;
  test_pass_rate: number;
  average_retries: number;
  average_execution_time_ms: number;
  total_estimated_cost_usd: number;
  runs: BenchmarkRun[];
}

export interface AdaptiveFeedbackInput {
  task_id: string;
  rating: "ACCEPTED" | "REJECTED" | "NEEDS_CHANGES";
  plan_accepted?: boolean;
  code_accepted?: boolean;
  solution_helpful?: boolean;
  comments?: string;
}

export interface AdaptiveFeedbackResponse {
  id: string;
  task_id: string;
  rating: string;
  solution_accepted: boolean;
  quality_score_delta: number;
  message: string;
}

export const adaptiveService = {
  async listExperiences(params?: {
    task_category?: string;
    bug_category?: string;
    status_type?: string;
    skip?: number;
    limit?: number;
  }): Promise<EngineeringExperience[]> {
    return apiClient<EngineeringExperience[]>("/api/v1/adaptive/experiences", {
      params,
    });
  },

  async searchExperiences(body: {
    query: string;
    task_category?: string;
    technology_stack?: string[];
    status_type?: string;
    limit?: number;
    threshold?: number;
  }): Promise<ExperienceSearchResult[]> {
    return apiClient<ExperienceSearchResult[]>("/api/v1/adaptive/experiences/search", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async getExperience(id: string): Promise<EngineeringExperience> {
    return apiClient<EngineeringExperience>(`/api/v1/adaptive/experiences/${id}`);
  },

  async listFailures(params?: {
    task_id?: string;
    stage?: string;
    failure_type?: string;
    limit?: number;
  }): Promise<TaskFailureRecord[]> {
    return apiClient<TaskFailureRecord[]>("/api/v1/adaptive/failures", {
      params,
    });
  },

  async getAgentPerformance(): Promise<AgentPerformanceResponse> {
    return apiClient<AgentPerformanceResponse>("/api/v1/adaptive/agent-performance");
  },

  async listBenchmarks(): Promise<BenchmarkDefinition[]> {
    return apiClient<BenchmarkDefinition[]>("/api/v1/adaptive/benchmarks");
  },

  async runBenchmarks(params?: {
    benchmark_id?: string;
    system_version?: string;
    model_version?: string;
  }): Promise<BenchmarkSummary> {
    return apiClient<BenchmarkSummary>("/api/v1/adaptive/benchmarks/run", {
      method: "POST",
      body: JSON.stringify(params || {}),
    });
  },

  async getBenchmarkHistory(limit = 50): Promise<BenchmarkRun[]> {
    return apiClient<BenchmarkRun[]>("/api/v1/adaptive/benchmarks/history", {
      params: { limit },
    });
  },

  async submitFeedback(data: AdaptiveFeedbackInput): Promise<AdaptiveFeedbackResponse> {
    return apiClient<AdaptiveFeedbackResponse>("/api/v1/adaptive/feedback", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

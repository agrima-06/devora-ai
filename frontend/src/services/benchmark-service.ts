import { apiClient } from "@/lib/api-client";
import {
  BenchmarkReportResponse,
  BenchmarkRunComparisonRequest,
  BenchmarkRunComparisonResponse,
  BenchmarkScenario,
  BenchmarkScenariosListResponse,
  BenchmarkSuiteRunDetail,
  BenchmarkSuiteRunsListResponse,
} from "@/types";

export interface SuiteRunPayload {
  model_name: string;
  suite_name?: string;
  code_revision?: string;
  categories?: string[];
  scenario_keys?: string[];
  simulate_safety_failure?: boolean;
}

export const benchmarkService = {
  /**
   * List all registered ground-truth benchmark scenarios with optional filtering.
   */
  async getScenarios(category?: string, isActive?: boolean): Promise<BenchmarkScenariosListResponse> {
    const params = new URLSearchParams();
    if (category && category !== "ALL") {
      params.append("category", category);
    }
    if (isActive !== undefined) {
      params.append("is_active", String(isActive));
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return apiClient<BenchmarkScenariosListResponse>(`/api/v1/benchmarks/scenarios${query}`);
  },

  /**
   * Fetch a single benchmark scenario by its unique key or ID.
   */
  async getScenario(scenarioKey: string): Promise<BenchmarkScenario> {
    return apiClient<BenchmarkScenario>(`/api/v1/benchmarks/scenarios/${encodeURIComponent(scenarioKey)}`);
  },

  /**
   * Trigger an evaluation suite run against a selected AI model.
   */
  async triggerSuiteRun(payload: SuiteRunPayload): Promise<BenchmarkSuiteRunDetail> {
    return apiClient<BenchmarkSuiteRunDetail>("/api/v1/benchmarks/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * List historical benchmark suite runs.
   */
  async getRuns(modelName?: string, status?: string): Promise<BenchmarkSuiteRunsListResponse> {
    const params = new URLSearchParams();
    if (modelName && modelName !== "ALL") {
      params.append("model_name", modelName);
    }
    if (status && status !== "ALL") {
      params.append("status", status);
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return apiClient<BenchmarkSuiteRunsListResponse>(`/api/v1/benchmarks/runs${query}`);
  },

  /**
   * Fetch complete execution outcomes for an individual suite run.
   */
  async getRunDetail(runId: string): Promise<BenchmarkSuiteRunDetail> {
    return apiClient<BenchmarkSuiteRunDetail>(`/api/v1/benchmarks/runs/${runId}`);
  },

  /**
   * Cancel an in-progress suite execution run.
   */
  async cancelRun(runId: string): Promise<any> {
    return apiClient(`/api/v1/benchmarks/runs/${runId}/cancel`, {
      method: "POST",
    });
  },

  /**
   * Compare two benchmark runs to identify performance deltas and regressions.
   */
  async compareRuns(request: BenchmarkRunComparisonRequest): Promise<BenchmarkRunComparisonResponse> {
    return apiClient<BenchmarkRunComparisonResponse>("/api/v1/benchmarks/compare", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  /**
   * Generate and retrieve an audit-ready Markdown benchmark evaluation report.
   */
  async getReport(runId: string): Promise<BenchmarkReportResponse> {
    return apiClient<BenchmarkReportResponse>(`/api/v1/benchmarks/runs/${runId}/report`);
  },

  /**
   * Retrieve canonical benchmark categories, descriptions, and weighting formula.
   */
  async getCategories(): Promise<any> {
    return apiClient("/api/v1/benchmarks/categories");
  },

  /**
   * Retrieve list of supported AI evaluation models.
   */
  async getModels(): Promise<Array<{ model_id: string; provider: string; context_window: number; is_default: boolean }>> {
    return apiClient("/api/v1/benchmarks/models");
  },

  /**
   * Seed the benchmark database with canonical scenarios.
   */
  async seedDataset(): Promise<{ status: string; total_scenarios: number; message: string }> {
    return apiClient("/api/v1/benchmarks/seed", {
      method: "POST",
    });
  },
};

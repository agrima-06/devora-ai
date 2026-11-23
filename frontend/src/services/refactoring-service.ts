import { apiClient } from "@/lib/api-client";
import {
  BeforeAfterComparisonResponse,
  RefactoringApproveRequest,
  RefactoringExecuteRequest,
  RefactoringExecutionResponse,
  RefactoringPlanCreateRequest,
  RefactoringPlanResponse,
  RefactoringPlansListResponse,
  RefactoringRecommendationsResponse,
} from "@/types";

export const refactoringService = {
  /**
   * Retrieve intelligent refactoring recommendations grounded in repository findings.
   */
  async getRecommendations(
    repositoryId: string,
    category?: string,
    limit: number = 20
  ): Promise<RefactoringRecommendationsResponse> {
    const params = new URLSearchParams();
    if (category && category !== "ALL") {
      params.append("category", category);
    }
    if (limit) {
      params.append("limit", limit.toString());
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return apiClient<RefactoringRecommendationsResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/recommendations${query}`
    );
  },

  /**
   * Synthesize a structured, dependency-ordered Refactoring Plan with deterministic risk scoring.
   */
  async createPlan(
    repositoryId: string,
    request: RefactoringPlanCreateRequest
  ): Promise<RefactoringPlanResponse> {
    return apiClient<RefactoringPlanResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * List all refactoring plans for a repository.
   */
  async listPlans(
    repositoryId: string,
    status?: string
  ): Promise<RefactoringPlansListResponse> {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return apiClient<RefactoringPlansListResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans${query}`
    );
  },

  /**
   * Retrieve a specific refactoring plan by ID.
   */
  async getPlan(
    repositoryId: string,
    planId: string
  ): Promise<RefactoringPlanResponse> {
    return apiClient<RefactoringPlanResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans/${planId}`
    );
  },

  /**
   * Human approval binding with cryptographic diff hash validation.
   */
  async approvePlan(
    repositoryId: string,
    planId: string,
    request: RefactoringApproveRequest
  ): Promise<RefactoringPlanResponse> {
    return apiClient<RefactoringPlanResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans/${planId}/approve`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Reject a refactoring plan with rationale.
   */
  async rejectPlan(
    repositoryId: string,
    planId: string,
    reason?: string
  ): Promise<RefactoringPlanResponse> {
    return apiClient<RefactoringPlanResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans/${planId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  },

  /**
   * Safely execute an approved refactoring plan in an isolated workspace with behavioral preservation checks.
   */
  async executePlan(
    repositoryId: string,
    planId: string,
    request: RefactoringExecuteRequest = {}
  ): Promise<RefactoringExecutionResponse> {
    return apiClient<RefactoringExecutionResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/plans/${planId}/execute`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Retrieve execution details and verification report for a refactoring execution.
   */
  async getExecution(
    repositoryId: string,
    executionId: string
  ): Promise<RefactoringExecutionResponse> {
    return apiClient<RefactoringExecutionResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/executions/${executionId}`
    );
  },

  /**
   * Retrieve quantitative before/after comparison and technical debt reduction delta.
   */
  async getComparison(
    repositoryId: string,
    executionId: string
  ): Promise<BeforeAfterComparisonResponse> {
    return apiClient<BeforeAfterComparisonResponse>(
      `/api/v1/repositories/${repositoryId}/refactoring/executions/${executionId}/comparison`
    );
  },
};

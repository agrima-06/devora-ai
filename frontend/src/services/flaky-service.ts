import { apiClient } from "@/lib/api-client";
import { FlakyTestRecord, RepositoryStabilitySummary } from "@/types";

export const flakyService = {
  /**
   * List all flaky test records for a repository.
   */
  async getRepositoryFlakyTests(
    repositoryId: string,
    classification?: string
  ): Promise<FlakyTestRecord[]> {
    const params = classification ? { classification } : undefined;
    return apiClient<FlakyTestRecord[]>(
      `/api/v1/repositories/${repositoryId}/flaky-tests`,
      { params }
    );
  },

  /**
   * Retrieve aggregated repository test stability summary.
   */
  async getRepositoryStabilitySummary(
    repositoryId: string
  ): Promise<RepositoryStabilitySummary> {
    return apiClient<RepositoryStabilitySummary>(
      `/api/v1/repositories/${repositoryId}/test-stability`
    );
  },

  /**
   * List flaky tests detected during a specific task execution.
   */
  async getTaskFlakyTests(taskId: string): Promise<FlakyTestRecord[]> {
    return apiClient<FlakyTestRecord[]>(
      `/api/v1/tasks/${taskId}/flaky-tests`
    );
  },

  /**
   * Retrieve an individual flaky test record by ID.
   */
  async getFlakyTestDetail(flakyTestId: string): Promise<FlakyTestRecord> {
    return apiClient<FlakyTestRecord>(
      `/api/v1/flaky-tests/${flakyTestId}`
    );
  },
};

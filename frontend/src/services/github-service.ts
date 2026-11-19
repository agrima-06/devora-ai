import { apiClient } from "@/lib/api-client";
import {
  GitBranch,
  GitHubInstallation,
  GitHubRepositoryItem,
  GitHubStatus,
  PullRequest,
} from "@/types";

export interface ConnectInstallationPayload {
  installation_id: number;
  account_login?: string;
  account_type?: string;
  repository_selection?: string;
  permissions?: Record<string, any>;
}

export const githubService = {
  async getStatus(): Promise<GitHubStatus> {
    return apiClient<GitHubStatus>("/api/v1/github/status");
  },

  async listInstallations(): Promise<GitHubInstallation[]> {
    return apiClient<GitHubInstallation[]>("/api/v1/github/installations");
  },

  async connectInstallation(payload: ConnectInstallationPayload): Promise<GitHubInstallation> {
    return apiClient<GitHubInstallation>("/api/v1/github/installations/connect", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listInstallationRepositories(installationId: number): Promise<GitHubRepositoryItem[]> {
    return apiClient<GitHubRepositoryItem[]>(
      `/api/v1/github/installations/${installationId}/repositories`
    );
  },

  async disconnectInstallation(installationId: number): Promise<void> {
    return apiClient<void>(`/api/v1/github/installations/${installationId}`, {
      method: "DELETE",
    });
  },

  async listRepositoryBranches(repoId: string): Promise<GitBranch[]> {
    return apiClient<GitBranch[]>(`/api/v1/repositories/${repoId}/branches`);
  },

  async listPullRequests(params?: {
    repository_id?: string;
    task_id?: string;
  }): Promise<PullRequest[]> {
    return apiClient<PullRequest[]>("/api/v1/pull-requests", {
      params,
    });
  },

  async getPullRequest(id: string): Promise<PullRequest> {
    return apiClient<PullRequest>(`/api/v1/pull-requests/${id}`);
  },

  async createPullRequestForTask(taskId: string): Promise<PullRequest> {
    return apiClient<PullRequest>(`/api/v1/pull-requests/tasks/${taskId}`, {
      method: "POST",
    });
  },

  async syncPullRequest(id: string): Promise<{ success: boolean; message: string; pull_request: PullRequest }> {
    return apiClient<{ success: boolean; message: string; pull_request: PullRequest }>(
      `/api/v1/pull-requests/${id}/sync`,
      {
        method: "POST",
      }
    );
  },
};

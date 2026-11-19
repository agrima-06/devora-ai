import { apiClient } from "@/lib/api-client";
import {
  AgentRun,
  Approval,
  FileChange,
  InterruptedTaskScanResponse,
  Report,
  Task,
  TaskRecoveryStatusResponse,
  TaskResumeResponse,
  TaskStatus,
  TestRun,
} from "@/types";

export interface CreateTaskPayload {
  project_id: string;
  repository_id: string;
  title: string;
  prompt: string;
  error_traceback?: string;
  task_type?: string;
  target_branch?: string;
}

export interface StartWorkflowResponse {
  task_id: string;
  status: string;
  message: string;
}

export const taskService = {
  async list(filters?: {
    project_id?: string;
    repository_id?: string;
    status?: TaskStatus;
  }): Promise<Task[]> {
    return apiClient<Task[]>("/api/v1/tasks", {
      params: filters,
    });
  },

  async get(id: string): Promise<Task> {
    return apiClient<Task>(`/api/v1/tasks/${id}`);
  },

  async create(payload: CreateTaskPayload): Promise<Task> {
    return apiClient<Task>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async cancel(id: string): Promise<Task> {
    return apiClient<Task>(`/api/v1/tasks/${id}/cancel`, {
      method: "POST",
    });
  },

  async startWorkflow(id: string): Promise<StartWorkflowResponse> {
    return apiClient<StartWorkflowResponse>(`/api/v1/tasks/${id}/start`, {
      method: "POST",
    });
  },

  async getRuns(id: string): Promise<AgentRun[]> {
    return apiClient<AgentRun[]>(`/api/v1/tasks/${id}/runs`);
  },

  async getDiff(id: string): Promise<FileChange[]> {
    return apiClient<FileChange[]>(`/api/v1/tasks/${id}/diff`);
  },

  async getTests(id: string): Promise<TestRun[]> {
    return apiClient<TestRun[]>(`/api/v1/tasks/${id}/tests`);
  },

  async getReport(id: string): Promise<Report> {
    return apiClient<Report>(`/api/v1/tasks/${id}/report`);
  },

  async submitApproval(
    id: string,
    action: "APPROVE" | "REJECT" | "REQUEST_CHANGES",
    notes?: string
  ): Promise<Approval> {
    return apiClient<Approval>(`/api/v1/tasks/${id}/approval`, {
      method: "POST",
      body: JSON.stringify({ action, notes }),
    });
  },

  async resume(id: string, force: boolean = false): Promise<TaskResumeResponse> {
    return apiClient<TaskResumeResponse>(`/api/v1/tasks/${id}/resume`, {
      method: "POST",
      body: JSON.stringify({ force }),
    });
  },

  async getRecoveryStatus(id: string): Promise<TaskRecoveryStatusResponse> {
    return apiClient<TaskRecoveryStatusResponse>(`/api/v1/tasks/${id}/recovery`);
  },

  async scanInterrupted(): Promise<InterruptedTaskScanResponse> {
    return apiClient<InterruptedTaskScanResponse>("/api/v1/tasks/recovery/scan", {
      method: "POST",
    });
  },
};

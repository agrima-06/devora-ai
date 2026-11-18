import { apiClient } from "@/lib/api-client";
import { Project } from "@/types";

export const projectService = {
  async list(): Promise<Project[]> {
    return apiClient<Project[]>("/api/v1/projects");
  },

  async get(id: string): Promise<Project> {
    return apiClient<Project>(`/api/v1/projects/${id}`);
  },

  async create(data: { name: string; slug: string; description?: string }): Promise<Project> {
    return apiClient<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

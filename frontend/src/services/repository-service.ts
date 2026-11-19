import { apiClient } from "@/lib/api-client";
import {
  CodeSearchResponse,
  IndexingJob,
  MemorySearchResult,
  MemoryStats,
  Repository,
  RepositoryArchitecture,
  RepositoryFile,
  RepositoryMemory,
  RepositorySymbol,
} from "@/types";

export interface CreateRepositoryPayload {
  project_id: string;
  name: string;
  full_name: string;
  clone_url: string;
  default_branch?: string;
  language?: string;
  meta_info?: Record<string, any>;
}

export const repositoryService = {
  async list(projectId?: string): Promise<Repository[]> {
    return apiClient<Repository[]>("/api/v1/repositories", {
      params: { project_id: projectId },
    });
  },

  async get(id: string): Promise<Repository> {
    return apiClient<Repository>(`/api/v1/repositories/${id}`);
  },

  async create(payload: CreateRepositoryPayload): Promise<Repository> {
    return apiClient<Repository>("/api/v1/repositories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async sync(id: string): Promise<{ repository_id: string; status: string; message: string }> {
    return apiClient<{ repository_id: string; status: string; message: string }>(
      `/api/v1/repositories/${id}/sync`,
      { method: "POST" }
    );
  },

  async triggerIndex(
    id: string,
    branch?: string,
    forceReindex: boolean = false
  ): Promise<IndexingJob> {
    return apiClient<IndexingJob>(`/api/v1/repositories/${id}/index`, {
      method: "POST",
      body: JSON.stringify({ branch, force_reindex: forceReindex }),
    });
  },

  async getIndexStatus(id: string): Promise<IndexingJob> {
    return apiClient<IndexingJob>(`/api/v1/repositories/${id}/index/status`);
  },

  async getArchitecture(id: string): Promise<RepositoryArchitecture> {
    return apiClient<RepositoryArchitecture>(`/api/v1/repositories/${id}/architecture`);
  },

  async listFiles(id: string, category?: string): Promise<RepositoryFile[]> {
    return apiClient<RepositoryFile[]>(`/api/v1/repositories/${id}/files`, {
      params: category ? { category } : undefined,
    });
  },

  async listSymbols(
    id: string,
    symbolType?: string,
    filePath?: string
  ): Promise<RepositorySymbol[]> {
    const params: Record<string, string> = {};
    if (symbolType) params.symbol_type = symbolType;
    if (filePath) params.file_path = filePath;
    return apiClient<RepositorySymbol[]>(`/api/v1/repositories/${id}/symbols`, {
      params,
    });
  },

  async searchCode(
    id: string,
    q: string,
    searchType: string = "all",
    limit: number = 25
  ): Promise<CodeSearchResponse> {
    return apiClient<CodeSearchResponse>(`/api/v1/repositories/${id}/search`, {
      params: { q, search_type: searchType, limit },
    });
  },

  async listMemories(
    id: string,
    category?: string,
    verificationStatus?: string,
    isStale?: boolean
  ): Promise<RepositoryMemory[]> {
    const params: Record<string, string> = {};
    if (category && category !== "all") params.category = category;
    if (verificationStatus && verificationStatus !== "all") params.verification_status = verificationStatus;
    if (isStale !== undefined) params.is_stale = String(isStale);
    return apiClient<RepositoryMemory[]>(`/api/v1/repositories/${id}/memories`, {
      params,
    });
  },

  async searchMemories(
    id: string,
    query: string,
    category?: string,
    threshold: number = 0.20,
    limit: number = 10
  ): Promise<MemorySearchResult[]> {
    return apiClient<MemorySearchResult[]>(`/api/v1/repositories/${id}/memories/search`, {
      method: "POST",
      body: JSON.stringify({
        query,
        category: category && category !== "all" ? category : undefined,
        threshold,
        limit,
      }),
    });
  },

  async getMemoryStats(id: string): Promise<MemoryStats> {
    return apiClient<MemoryStats>(`/api/v1/repositories/${id}/memories/stats`);
  },

  async createMemory(
    id: string,
    payload: {
      category: string;
      title?: string;
      content: string;
      source_reference?: string;
      verification_status?: string;
    }
  ): Promise<RepositoryMemory> {
    return apiClient<RepositoryMemory>(`/api/v1/repositories/${id}/memories`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async markMemoryStale(id: string, memoryId: string, reason?: string): Promise<RepositoryMemory> {
    return apiClient<RepositoryMemory>(`/api/v1/repositories/${id}/memories/${memoryId}/stale`, {
      method: "POST",
      params: reason ? { reason } : undefined,
    });
  },

  async submitMemoryFeedback(
    id: string,
    memoryId: string,
    isHelpful: boolean,
    notes?: string
  ): Promise<any> {
    return apiClient(`/api/v1/repositories/${id}/memories/${memoryId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ is_helpful: isHelpful, notes }),
    });
  },
};

import { apiClient } from "@/lib/api-client";
import {
  GraphDependenciesResponse,
  GraphIndexingResponse,
  GraphNodeDetailResponse,
  GraphNodesListResponse,
  GraphUnresolvedReferencesResponse,
  RepositoryGraphSummaryResponse,
} from "@/types";

export const graphService = {
  async getSummary(repositoryId: string): Promise<RepositoryGraphSummaryResponse> {
    return apiClient<RepositoryGraphSummaryResponse>(`/api/v1/repositories/${repositoryId}/graph`);
  },

  async indexGraph(
    repositoryId: string,
    payload?: { force_reindex?: boolean; branch?: string }
  ): Promise<GraphIndexingResponse> {
    return apiClient<GraphIndexingResponse>(`/api/v1/repositories/${repositoryId}/graph/index`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  async listNodes(
    repositoryId: string,
    params?: {
      node_type?: string;
      language?: string;
      file_path?: string;
      q?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<GraphNodesListResponse> {
    return apiClient<GraphNodesListResponse>(`/api/v1/repositories/${repositoryId}/graph/nodes`, {
      params,
    });
  },

  async getNodeDetail(
    repositoryId: string,
    nodeId: string
  ): Promise<GraphNodeDetailResponse> {
    return apiClient<GraphNodeDetailResponse>(
      `/api/v1/repositories/${repositoryId}/graph/nodes/${nodeId}`
    );
  },

  async getDependencies(
    repositoryId: string,
    params: {
      node_id: string;
      direction?: string;
      max_depth?: number;
      edge_type?: string;
      limit?: number;
    }
  ): Promise<GraphDependenciesResponse> {
    return apiClient<GraphDependenciesResponse>(
      `/api/v1/repositories/${repositoryId}/graph/dependencies`,
      { params }
    );
  },

  async listUnresolved(
    repositoryId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<GraphUnresolvedReferencesResponse> {
    return apiClient<GraphUnresolvedReferencesResponse>(
      `/api/v1/repositories/${repositoryId}/graph/unresolved`,
      { params }
    );
  },
};

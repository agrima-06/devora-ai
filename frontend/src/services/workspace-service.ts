import { apiClient } from "@/lib/api-client";
import {
  PackageDependenciesResponse,
  PackageImpactResponse,
  PackageInfo,
  WorkspaceGraphResponse,
  WorkspaceIndexResponse,
  WorkspaceInfo,
} from "@/types";

export const workspaceService = {
  async getWorkspaces(repositoryId: string): Promise<WorkspaceGraphResponse> {
    return apiClient<WorkspaceGraphResponse>(
      `/api/v1/repositories/${repositoryId}/workspaces`
    );
  },

  async getWorkspaceDetails(
    repositoryId: string,
    workspaceId: string
  ): Promise<WorkspaceInfo> {
    return apiClient<WorkspaceInfo>(
      `/api/v1/repositories/${repositoryId}/workspaces/${workspaceId}`
    );
  },

  async getPackages(repositoryId: string): Promise<PackageInfo[]> {
    return apiClient<PackageInfo[]>(
      `/api/v1/repositories/${repositoryId}/packages`
    );
  },

  async getPackageDependencies(
    repositoryId: string,
    packageId: string
  ): Promise<PackageDependenciesResponse> {
    return apiClient<PackageDependenciesResponse>(
      `/api/v1/repositories/${repositoryId}/packages/${packageId}/dependencies`
    );
  },

  async getPackageDependents(
    repositoryId: string,
    packageId: string
  ): Promise<PackageInfo[]> {
    return apiClient<PackageInfo[]>(
      `/api/v1/repositories/${repositoryId}/packages/${packageId}/dependents`
    );
  },

  async getPackageImpact(
    repositoryId: string,
    packageId: string
  ): Promise<PackageImpactResponse> {
    return apiClient<PackageImpactResponse>(
      `/api/v1/repositories/${repositoryId}/packages/${packageId}/impact`
    );
  },

  async indexWorkspaces(
    repositoryId: string,
    branch?: string
  ): Promise<WorkspaceIndexResponse> {
    return apiClient<WorkspaceIndexResponse>(
      `/api/v1/repositories/${repositoryId}/workspaces/index`,
      {
        method: "POST",
        body: JSON.stringify(branch ? { branch } : {}),
      }
    );
  },
};

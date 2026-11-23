import { apiClient } from "@/lib/api-client";
import { ImpactAnalysisRequest, ImpactAnalysisResponse } from "@/types";

export const impactService = {
  async analyzeImpact(
    repositoryId: string,
    payload: ImpactAnalysisRequest
  ): Promise<ImpactAnalysisResponse> {
    return apiClient<ImpactAnalysisResponse>(
      `/api/v1/repositories/${repositoryId}/impact-analysis`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  },
};

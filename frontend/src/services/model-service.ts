import { apiClient } from "@/lib/api-client";
import {
  ModelCircuitBreakerStatus,
  ModelGatewayHealthResponse,
} from "@/types";

export const modelService = {
  /**
   * Fetch live Model Gateway resilience and circuit breaker health metrics.
   */
  async getHealth(): Promise<ModelGatewayHealthResponse> {
    return apiClient<ModelGatewayHealthResponse>("/api/v1/models/health");
  },

  /**
   * Reset a specific provider/model circuit breaker.
   */
  async resetBreaker(
    providerName: string,
    modelName: string
  ): Promise<ModelCircuitBreakerStatus> {
    return apiClient<ModelCircuitBreakerStatus>(
      `/api/v1/models/breakers/${encodeURIComponent(providerName)}/${encodeURIComponent(modelName)}/reset`,
      { method: "POST" }
    );
  },

  /**
   * Reset all model circuit breakers to CLOSED state.
   */
  async resetAll(): Promise<ModelGatewayHealthResponse> {
    return apiClient<ModelGatewayHealthResponse>("/api/v1/models/reset-all", {
      method: "POST",
    });
  },
};

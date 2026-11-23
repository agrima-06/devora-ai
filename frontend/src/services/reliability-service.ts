import { apiClient } from "@/lib/api-client";
import {
  ReliabilityEventsResponse,
  ReliabilityOverviewResponse,
  ReliabilityTrendsResponse,
} from "@/types";

export const reliabilityService = {
  /**
   * Fetch complete system reliability overview across workflows, sandbox, testing, gateway, and recovery.
   */
  async getOverview(repositoryId?: string): Promise<ReliabilityOverviewResponse> {
    const params = repositoryId ? { repository_id: repositoryId } : undefined;
    return apiClient<ReliabilityOverviewResponse>("/api/v1/reliability/overview", {
      params,
    });
  },

  /**
   * Fetch paginated unified operational reliability events with subsystem/severity filtering.
   */
  async getEvents(params?: {
    subsystem?: string;
    severity?: string;
    repository_id?: string;
    task_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<ReliabilityEventsResponse> {
    return apiClient<ReliabilityEventsResponse>("/api/v1/reliability/events", {
      params,
    });
  },

  /**
   * Fetch time-series reliability trends.
   */
  async getTrends(
    timeframe: string = "7d",
    repositoryId?: string
  ): Promise<ReliabilityTrendsResponse> {
    const params: Record<string, string> = { timeframe };
    if (repositoryId) {
      params.repository_id = repositoryId;
    }
    return apiClient<ReliabilityTrendsResponse>("/api/v1/reliability/trends", {
      params,
    });
  },
};

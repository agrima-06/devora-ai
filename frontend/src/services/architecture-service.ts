import { apiClient } from "@/lib/api-client";
import {
  ArchitectureAskRequest,
  ArchitectureAskResponse,
  ArchitectureConventionItem,
  ArchitectureDriftResponse,
  ArchitecturePatternItem,
  ArchitectureSummaryResponse,
  HybridSearchRequest,
  HybridSearchResponse,
  TechnicalDebtFindingItem,
  TechnicalDebtFindingsResponse,
  TechnicalDebtSummaryResponse,
  TechnicalDebtTrendsResponse,
} from "@/types";

export const architectureService = {
  /**
   * Execute multi-modal hybrid repository search (Lexical + Semantic + Structural).
   */
  async searchHybrid(
    repositoryId: string,
    request: HybridSearchRequest
  ): Promise<HybridSearchResponse> {
    return apiClient<HybridSearchResponse>(
      `/api/v1/repositories/${repositoryId}/search/hybrid`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Retrieve unified architecture summary, confirmed patterns count, and conventions.
   */
  async getArchitectureSummary(
    repositoryId: string
  ): Promise<ArchitectureSummaryResponse> {
    return apiClient<ArchitectureSummaryResponse>(
      `/api/v1/repositories/${repositoryId}/architecture`
    );
  },

  /**
   * Trigger on-demand architectural pattern re-analysis.
   */
  async analyzeArchitecture(
    repositoryId: string
  ): Promise<ArchitectureSummaryResponse> {
    return apiClient<ArchitectureSummaryResponse>(
      `/api/v1/repositories/${repositoryId}/architecture/analyze`,
      {
        method: "POST",
      }
    );
  },

  /**
   * List individual architectural patterns with optional category and confidence filters.
   */
  async listPatterns(
    repositoryId: string,
    category?: string,
    minConfidence?: number
  ): Promise<ArchitecturePatternItem[]> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (minConfidence !== undefined) params.append("min_confidence", minConfidence.toString());

    const qs = params.toString() ? `?${params.toString()}` : "";
    return apiClient<ArchitecturePatternItem[]>(
      `/api/v1/repositories/${repositoryId}/architecture/patterns${qs}`
    );
  },

  /**
   * Get specific architectural pattern details by ID.
   */
  async getPattern(
    repositoryId: string,
    patternId: string
  ): Promise<ArchitecturePatternItem> {
    return apiClient<ArchitecturePatternItem>(
      `/api/v1/repositories/${repositoryId}/architecture/patterns/${patternId}`
    );
  },

  /**
   * List discovered architectural and coding conventions.
   */
  async listConventions(
    repositoryId: string,
    category?: string
  ): Promise<ArchitectureConventionItem[]> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);

    const qs = params.toString() ? `?${params.toString()}` : "";
    return apiClient<ArchitectureConventionItem[]>(
      `/api/v1/repositories/${repositoryId}/architecture/conventions${qs}`
    );
  },

  /**
   * Ask an evidence-grounded architectural question.
   */
  async askArchitecture(
    repositoryId: string,
    request: ArchitectureAskRequest
  ): Promise<ArchitectureAskResponse> {
    return apiClient<ArchitectureAskResponse>(
      `/api/v1/repositories/${repositoryId}/architecture/ask`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Get architecture drift analysis comparing current repository to baseline.
   */
  async getArchitectureDrift(
    repositoryId: string
  ): Promise<ArchitectureDriftResponse> {
    return apiClient<ArchitectureDriftResponse>(
      `/api/v1/repositories/${repositoryId}/architecture/drift`
    );
  },

  /**
   * Trigger on-demand architecture drift analysis.
   */
  async analyzeArchitectureDrift(
    repositoryId: string,
    baselineCommitSha?: string
  ): Promise<ArchitectureDriftResponse> {
    const params = new URLSearchParams();
    if (baselineCommitSha) params.append("baseline_commit_sha", baselineCommitSha);
    const qs = params.toString() ? `?${params.toString()}` : "";

    return apiClient<ArchitectureDriftResponse>(
      `/api/v1/repositories/${repositoryId}/architecture/drift/analyze${qs}`,
      {
        method: "POST",
      }
    );
  },

  /**
   * Get latest technical debt summary and dimension scores.
   */
  async getTechnicalDebt(
    repositoryId: string
  ): Promise<TechnicalDebtSummaryResponse> {
    return apiClient<TechnicalDebtSummaryResponse>(
      `/api/v1/repositories/${repositoryId}/technical-debt`
    );
  },

  /**
   * Trigger on-demand technical debt evaluation.
   */
  async analyzeTechnicalDebt(
    repositoryId: string
  ): Promise<TechnicalDebtSummaryResponse> {
    return apiClient<TechnicalDebtSummaryResponse>(
      `/api/v1/repositories/${repositoryId}/technical-debt/analyze`,
      {
        method: "POST",
      }
    );
  },

  /**
   * Query paginated technical debt findings with category and severity filters.
   */
  async getTechnicalDebtFindings(
    repositoryId: string,
    category?: string,
    severity?: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<TechnicalDebtFindingsResponse> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (severity) params.append("severity", severity);
    params.append("limit", limit.toString());
    params.append("offset", offset.toString());

    return apiClient<TechnicalDebtFindingsResponse>(
      `/api/v1/repositories/${repositoryId}/technical-debt/findings?${params.toString()}`
    );
  },

  /**
   * Retrieve single technical debt finding detail.
   */
  async getTechnicalDebtFindingDetail(
    repositoryId: string,
    findingId: string
  ): Promise<TechnicalDebtFindingItem> {
    return apiClient<TechnicalDebtFindingItem>(
      `/api/v1/repositories/${repositoryId}/technical-debt/findings/${findingId}`
    );
  },

  /**
   * Retrieve historical technical debt trends.
   */
  async getTechnicalDebtTrends(
    repositoryId: string
  ): Promise<TechnicalDebtTrendsResponse> {
    return apiClient<TechnicalDebtTrendsResponse>(
      `/api/v1/repositories/${repositoryId}/technical-debt/trends`
    );
  },
};

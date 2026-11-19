import { apiClient } from "@/lib/api-client";

export interface ProbabilityItem {
  category: string;
  probability: number;
}

export interface PredictionResult {
  predicted_category: string;
  confidence: number;
  top_probabilities: ProbabilityItem[];
  is_low_confidence: boolean;
  warning?: string | null;
  model_version: string;
  input_hash: string;
  cleaned_input_preview: string;
  inference_time_ms: number;
  timestamp: string;
}

export interface ModelStatus {
  status: "ready" | "degraded";
  active_version: string;
  algorithm: string;
  is_promoted: boolean;
  sample_counts: {
    train?: number;
    val?: number;
    test?: number;
    total?: number;
  };
  created_at?: string;
  model_sha256?: string;
}

export interface ModelMetrics {
  accuracy: number;
  macro_f1: number;
  weighted_f1: number;
  classes: string[];
  per_class: Record<
    string,
    {
      precision: number;
      recall: number;
      f1: number;
      support: number;
    }
  >;
  confusion_matrix: number[][];
}

export interface ModelVersion {
  version: string;
  algorithm: string;
  created_at: string;
  is_promoted: boolean;
  is_active: boolean;
  promotion_reason?: string;
  model_sha256: string;
  sample_counts: {
    total: number;
  };
}

export interface PredictionHistoryItem {
  id: string;
  task_id?: string | null;
  predicted_category: string;
  confidence: number;
  is_low_confidence: boolean;
  model_version: string;
  inference_time_ms: number;
  verified_category?: string | null;
  is_correct?: boolean | null;
  created_at: string;
}

export interface PredictionHistoryResponse {
  items: PredictionHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  correct_count: number;
  incorrect_count: number;
}

export interface ClassifyPayload {
  error_message: string;
  traceback?: string;
  task_description?: string;
  task_id?: string;
}

export const mlService = {
  async classify(payload: ClassifyPayload): Promise<PredictionResult> {
    return apiClient<PredictionResult>("/api/v1/ml/classify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getStatus(): Promise<ModelStatus> {
    return apiClient<ModelStatus>("/api/v1/ml/model/status");
  },

  async getMetrics(): Promise<ModelMetrics> {
    return apiClient<ModelMetrics>("/api/v1/ml/model/metrics");
  },

  async getVersions(): Promise<ModelVersion[]> {
    return apiClient<ModelVersion[]>("/api/v1/ml/model/versions");
  },

  async train(payload: {
    version?: string;
    min_weighted_f1?: number;
    min_class_precision?: number;
    c_param?: number;
    max_iter?: number;
  }): Promise<any> {
    return apiClient<any>("/api/v1/ml/model/train", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getPredictions(params?: {
    task_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<PredictionHistoryResponse> {
    return apiClient<PredictionHistoryResponse>("/api/v1/ml/predictions", {
      params,
    });
  },
};

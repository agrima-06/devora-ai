"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Cpu,
  BarChart3,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Layers,
  History,
  ShieldCheck,
  Zap,
  Info,
  Loader2,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { mlService, PredictionResult } from "@/services/ml-service";

const CANONICAL_CATEGORIES = [
  "syntax_error",
  "import_dependency_error",
  "type_error",
  "attribute_null_reference_error",
  "index_key_error",
  "runtime_logic_error",
  "database_network_error",
  "permission_security_error",
];

const CATEGORY_DISPLAY_NAMES: Record<string, string> = {
  syntax_error: "Syntax Error",
  import_dependency_error: "Import & Dependency",
  type_error: "Type Incompatibility",
  attribute_null_reference_error: "Null & Attribute",
  index_key_error: "Index & Key Lookup",
  runtime_logic_error: "Runtime Logic & Bounds",
  database_network_error: "Database & Network",
  permission_security_error: "Security & Permissions",
};

export default function MLIntelligencePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"evaluation" | "playground" | "history" | "versions">("evaluation");

  // Playground state
  const [testErrorMessage, setTestErrorMessage] = useState("");
  const [testTraceback, setTestTraceback] = useState(
    `Traceback (most recent call last):\n  File "/workspace/app/db/session.py", line 55, in get_session\n    conn = await asyncpg.connect("postgresql://postgres@localhost:5432/devora")\nasyncpg.exceptions.CannotConnectNowError: connection to server on socket failed: Connection refused`
  );
  const [playgroundResult, setPlaygroundResult] = useState<PredictionResult | null>(null);

  // Queries
  const { data: status, isLoading: isStatusLoading } = useQuery({
    queryKey: ["ml-status"],
    queryFn: () => mlService.getStatus(),
  });

  const { data: metrics, isLoading: isMetricsLoading } = useQuery({
    queryKey: ["ml-metrics"],
    queryFn: () => mlService.getMetrics(),
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["ml-versions"],
    queryFn: () => mlService.getVersions(),
  });

  const { data: predictionsData } = useQuery({
    queryKey: ["ml-predictions"],
    queryFn: () => mlService.getPredictions({ page: 1, page_size: 25 }),
  });

  // Playground Mutation
  const classifyMutation = useMutation({
    mutationFn: mlService.classify,
    onSuccess: (data) => {
      setPlaygroundResult(data);
      queryClient.invalidateQueries({ queryKey: ["ml-predictions"] });
    },
  });

  // Retrain Mutation
  const trainMutation = useMutation({
    mutationFn: () => mlService.train({ min_weighted_f1: 0.85, c_param: 5.0 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-status"] });
      queryClient.invalidateQueries({ queryKey: ["ml-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["ml-versions"] });
    },
  });

  const handleClassify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!testErrorMessage && !testTraceback) return;
    classifyMutation.mutate({
      error_message: testErrorMessage,
      traceback: testTraceback,
    });
  };

  return (
    <AppLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary shadow-[0_0_15px_rgba(37,99,235,0.25)]">
                <Sparkles className="w-4 h-4" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                ML Bug Classification Engine
              </h1>
            </div>
            <p className="text-sm text-muted-foreground">
              Deterministic, sub-millisecond error classification guiding autonomous agent root-cause diagnosis.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className={
                status?.status === "ready"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  status?.status === "ready" ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              {status?.status === "ready" ? "Engine Active" : "Degraded"}
            </Badge>

            <Badge variant="outline" className="font-mono text-xs border-border bg-card">
              {status?.active_version || "v1.0.0"}
            </Badge>

            <Button
              size="sm"
              variant="outline"
              onClick={() => trainMutation.mutate()}
              disabled={trainMutation.isPending}
              className="gap-1.5 text-xs border-border hover:bg-secondary/60"
            >
              {trainMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCcw className="w-3.5 h-3.5 text-primary" />
              )}
              <span>Retrain & Gate</span>
            </Button>
          </div>
        </div>

        {/* Top Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Holdout Accuracy
              </CardDescription>
              <CardTitle className="text-2xl font-mono text-emerald-400">
                {metrics ? `${(metrics.accuracy * 100).toFixed(1)}%` : "..."}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-[11px] text-muted-foreground">
              Evaluated on strict 15% stratified test partition
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Weighted F1 Score
              </CardDescription>
              <CardTitle className="text-2xl font-mono text-primary">
                {metrics ? metrics.weighted_f1.toFixed(4) : "..."}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-[11px] text-muted-foreground">
              Promotion gate threshold: &ge; 0.8500
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Dataset Corpus
              </CardDescription>
              <CardTitle className="text-2xl font-mono text-foreground">
                {status?.sample_counts?.total || 160}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-[11px] text-muted-foreground">
              Verified samples across 8 canonical categories
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Inference Latency
              </CardDescription>
              <CardTitle className="text-2xl font-mono text-amber-400">
                &lt; 1.0 ms
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-[11px] text-muted-foreground">
              Sub-millisecond TF-IDF + Logistic Regression
            </CardContent>
          </Card>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-border pb-px">
          <button
            onClick={() => setActiveTab("evaluation")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "evaluation"
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Evaluation & Confusion Matrix</span>
          </button>

          <button
            onClick={() => setActiveTab("playground")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "playground"
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Play className="w-3.5 h-3.5" />
            <span>Traceback Playground</span>
          </button>

          <button
            onClick={() => setActiveTab("history")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "history"
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Prediction Telemetry</span>
          </button>

          <button
            onClick={() => setActiveTab("versions")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "versions"
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Model Versions</span>
          </button>
        </div>

        {/* Tab Content: Evaluation & Confusion Matrix */}
        {activeTab === "evaluation" && metrics && (
          <div className="space-y-6">
            {/* Per-Class Metrics */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-foreground flex items-center justify-between">
                  <span>Holdout Partition Evaluation Per Bug Category</span>
                  <Badge variant="outline" className="font-mono text-xs">
                    Macro F1: {metrics.macro_f1.toFixed(4)}
                  </Badge>
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Individual precision, recall, and F1 scores measured across holdout test examples.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/30 text-muted-foreground font-mono uppercase text-[11px] border-y border-border">
                      <tr>
                        <th className="py-2.5 px-4 font-semibold">Category</th>
                        <th className="py-2.5 px-4 font-semibold text-right">Precision</th>
                        <th className="py-2.5 px-4 font-semibold text-right">Recall</th>
                        <th className="py-2.5 px-4 font-semibold text-right">F1-Score</th>
                        <th className="py-2.5 px-4 font-semibold text-right">Support</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {CANONICAL_CATEGORIES.map((catKey) => {
                        const stat = metrics.per_class[catKey] || {
                          precision: 0,
                          recall: 0,
                          f1: 0,
                          support: 0,
                        };
                        return (
                          <tr key={catKey} className="hover:bg-muted/20 transition-colors">
                            <td className="py-2.5 px-4 font-mono text-foreground font-medium flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-primary/60" />
                              <span>{CATEGORY_DISPLAY_NAMES[catKey] || catKey}</span>
                              <span className="text-[10px] text-muted-foreground">({catKey})</span>
                            </td>
                            <td className="py-2.5 px-4 font-mono text-right text-foreground">
                              {(stat.precision * 100).toFixed(1)}%
                            </td>
                            <td className="py-2.5 px-4 font-mono text-right text-foreground">
                              {(stat.recall * 100).toFixed(1)}%
                            </td>
                            <td className="py-2.5 px-4 font-mono text-right font-semibold text-primary">
                              {stat.f1.toFixed(4)}
                            </td>
                            <td className="py-2.5 px-4 font-mono text-right text-muted-foreground">
                              {stat.support}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Confusion Matrix */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-foreground">
                  8x8 Confusion Matrix (True vs. Predicted)
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Rows represent true ground-truth classes; columns represent model predictions.
                </CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto pt-2">
                <table className="w-full text-[11px] font-mono border-collapse border border-border">
                  <thead>
                    <tr className="bg-muted/40">
                      <th className="p-2 border border-border text-left font-semibold text-muted-foreground">
                        True \ Pred
                      </th>
                      {CANONICAL_CATEGORIES.map((cat, idx) => (
                        <th
                          key={cat}
                          title={cat}
                          className="p-2 border border-border text-center font-semibold text-muted-foreground"
                        >
                          C{idx + 1}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.confusion_matrix.map((row, rIdx) => {
                      const trueCat = CANONICAL_CATEGORIES[rIdx];
                      return (
                        <tr key={trueCat} className="hover:bg-muted/10">
                          <td className="p-2 border border-border font-medium text-foreground whitespace-nowrap">
                            C{rIdx + 1}: {CATEGORY_DISPLAY_NAMES[trueCat]}
                          </td>
                          {row.map((cellVal, cIdx) => {
                            const isDiagonal = rIdx === cIdx;
                            const isCorrect = isDiagonal && cellVal > 0;
                            const isMisclassified = !isDiagonal && cellVal > 0;
                            return (
                              <td
                                key={`${rIdx}-${cIdx}`}
                                className={`p-2 border border-border text-center font-bold ${
                                  isCorrect
                                    ? "bg-emerald-500/20 text-emerald-400"
                                    : isMisclassified
                                    ? "bg-rose-500/20 text-rose-400"
                                    : "text-muted-foreground/40"
                                }`}
                              >
                                {cellVal}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground mt-4 pt-3 border-t border-border">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded bg-emerald-500/30 border border-emerald-500/40" />
                    <span>Correct Prediction (Diagonal)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded bg-rose-500/30 border border-rose-500/40" />
                    <span>Classification Discrepancy</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tab Content: Traceback Playground */}
        {activeTab === "playground" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Form */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Play className="w-4 h-4 text-primary" />
                  <span>Interactive Classifier Playground</span>
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Paste a raw Python exception or stack trace to test real-time classification and confidence scoring.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleClassify} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground">
                      Error Message (Optional)
                    </label>
                    <Input
                      placeholder="e.g. TypeError: unsupported operand type(s) for +: 'int' and 'str'"
                      value={testErrorMessage}
                      onChange={(e) => setTestErrorMessage(e.target.value)}
                      className="font-mono text-xs bg-background/60"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground">
                      Raw Traceback / Stack Trace
                    </label>
                    <Textarea
                      rows={9}
                      placeholder="Paste Python error log or stack trace here..."
                      value={testTraceback}
                      onChange={(e) => setTestTraceback(e.target.value)}
                      className="font-mono text-xs bg-background/60 leading-relaxed"
                    />
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setTestErrorMessage("KeyError: 'user_id'");
                        setTestTraceback(
                          `Traceback (most recent call last):\n  File "/workspace/app/auth/jwt.py", line 29, in decode_token\n    return payload["user_id"]\nKeyError: 'user_id'`
                        );
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      Load Sample
                    </Button>

                    <Button
                      type="submit"
                      size="sm"
                      disabled={classifyMutation.isPending}
                      className="gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground text-xs"
                    >
                      {classifyMutation.isPending ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Zap className="w-3.5 h-3.5" />
                      )}
                      <span>Run Classification</span>
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* Prediction Output Display */}
            <Card className="bg-card/40 border-border flex flex-col justify-between">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-foreground flex items-center justify-between">
                  <span>Diagnostic Output</span>
                  {playgroundResult && (
                    <Badge variant="outline" className="font-mono text-xs text-muted-foreground">
                      {playgroundResult.inference_time_ms} ms
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Empirical classification prior produced by Scikit-learn model.
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 flex-1">
                {playgroundResult ? (
                  <div className="space-y-4">
                    {/* Top Result Card */}
                    <div className="p-4 rounded-lg bg-primary/10 border border-primary/20 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground uppercase font-mono">
                          Predicted Category
                        </span>
                        <Badge
                          variant="outline"
                          className={
                            playgroundResult.is_low_confidence
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/30 font-mono text-xs"
                              : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 font-mono text-xs"
                          }
                        >
                          {(playgroundResult.confidence * 100).toFixed(1)}% Confidence
                        </Badge>
                      </div>

                      <div className="text-lg font-bold font-mono text-foreground flex items-center gap-2">
                        <span>
                          {CATEGORY_DISPLAY_NAMES[playgroundResult.predicted_category] ||
                            playgroundResult.predicted_category}
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-muted-foreground">
                        Canonical identifier: {playgroundResult.predicted_category}
                      </p>
                    </div>

                    {/* Low Confidence Warning */}
                    {playgroundResult.is_low_confidence && playgroundResult.warning && (
                      <div className="p-3 rounded-md bg-amber-500/10 border border-amber-500/20 flex items-start gap-2.5 text-xs text-amber-300">
                        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <p className="font-semibold">Ambiguity Warning</p>
                          <p className="text-[11px] text-amber-200/80 mt-0.5">
                            {playgroundResult.warning}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Ranked Probability Breakdown */}
                    <div className="space-y-2 pt-2 border-t border-border">
                      <span className="text-xs font-semibold text-muted-foreground block font-mono uppercase tracking-wider">
                        Ranked Class Probabilities
                      </span>
                      <div className="space-y-2">
                        {playgroundResult.top_probabilities.map((probItem, idx) => (
                          <div key={probItem.category} className="space-y-1">
                            <div className="flex items-center justify-between text-xs font-mono">
                              <span className="text-foreground">
                                {CATEGORY_DISPLAY_NAMES[probItem.category] || probItem.category}
                              </span>
                              <span className="text-muted-foreground">
                                {(probItem.probability * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-muted/40 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  idx === 0 ? "bg-primary" : "bg-muted-foreground/40"
                                }`}
                                style={{ width: `${Math.max(probItem.probability * 100, 2)}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Telemetry Metadata */}
                    <div className="pt-3 border-t border-border text-[11px] font-mono text-muted-foreground grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-muted-foreground/60">Model Version:</span>{" "}
                        <span className="text-foreground">{playgroundResult.model_version}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground/60">Input Hash:</span>{" "}
                        <span className="text-foreground">{playgroundResult.input_hash.slice(0, 10)}...</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center text-center p-6 border border-dashed border-border rounded-lg text-muted-foreground">
                    <Cpu className="w-8 h-8 mb-2 text-muted-foreground/40" />
                    <p className="text-xs font-medium text-foreground">Awaiting Input</p>
                    <p className="text-[11px] mt-1">
                      Paste an error traceback and click &quot;Run Classification&quot; to test model diagnostics.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tab Content: Prediction History & Telemetry */}
        {activeTab === "history" && (
          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center justify-between">
                <span>Recent Inference Predictions & Telemetry</span>
                {predictionsData && (
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-emerald-400 font-mono text-xs">
                      {predictionsData.correct_count} Verified Correct
                    </Badge>
                    <Badge variant="outline" className="text-muted-foreground font-mono text-xs">
                      {predictionsData.total} Total Inferences
                    </Badge>
                  </div>
                )}
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Audit trail of classification requests showing predicted categories, model confidence, and post-task validation.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-muted/30 text-muted-foreground font-mono uppercase text-[11px] border-y border-border">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold">Predicted Category</th>
                      <th className="py-2.5 px-4 font-semibold">Confidence</th>
                      <th className="py-2.5 px-4 font-semibold">Latency</th>
                      <th className="py-2.5 px-4 font-semibold">Verified Ground Truth</th>
                      <th className="py-2.5 px-4 font-semibold">Status</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {predictionsData?.items && predictionsData.items.length > 0 ? (
                      predictionsData.items.map((item) => (
                        <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                          <td className="py-2.5 px-4 font-mono font-medium text-foreground">
                            {CATEGORY_DISPLAY_NAMES[item.predicted_category] || item.predicted_category}
                          </td>
                          <td className="py-2.5 px-4 font-mono">
                            <span
                              className={
                                item.is_low_confidence ? "text-amber-400" : "text-emerald-400"
                              }
                            >
                              {(item.confidence * 100).toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-2.5 px-4 font-mono text-muted-foreground">
                            {item.inference_time_ms.toFixed(2)} ms
                          </td>
                          <td className="py-2.5 px-4 font-mono text-foreground">
                            {item.verified_category ? (
                              CATEGORY_DISPLAY_NAMES[item.verified_category] || item.verified_category
                            ) : (
                              <span className="text-muted-foreground/60 italic">Pending Verification</span>
                            )}
                          </td>
                          <td className="py-2.5 px-4">
                            {item.is_correct === true && (
                              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]">
                                Correct
                              </Badge>
                            )}
                            {item.is_correct === false && (
                              <Badge variant="outline" className="bg-rose-500/10 text-rose-400 border-rose-500/30 text-[10px]">
                                Misclassified
                              </Badge>
                            )}
                            {item.is_correct === null && (
                              <Badge variant="outline" className="text-muted-foreground text-[10px]">
                                Task Active
                              </Badge>
                            )}
                          </td>
                          <td className="py-2.5 px-4 font-mono text-right text-muted-foreground text-[11px]">
                            {new Date(item.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-muted-foreground">
                          No historical predictions recorded yet. Run a classification in the playground or launch a bug fix task.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab Content: Model Versions */}
        {activeTab === "versions" && (
          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-foreground">
                Trained Model Artifacts & Promotion Registry
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Versioned serialized pipelines verified by SHA-256 cryptographic checksums.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {versions.map((ver) => (
                <div
                  key={ver.version}
                  className="p-4 rounded-lg bg-card/60 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-foreground text-sm">
                        {ver.version}
                      </span>
                      {ver.is_active && (
                        <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 text-[10px]">
                          Active Production
                        </Badge>
                      )}
                      {ver.is_promoted && (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]">
                          Gate Passed
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Algorithm: <span className="font-mono text-foreground">{ver.algorithm}</span>
                      {ver.promotion_reason && ` — ${ver.promotion_reason}`}
                    </p>
                    <p className="text-[11px] font-mono text-muted-foreground/70">
                      SHA-256: {ver.model_sha256}
                    </p>
                  </div>

                  <div className="text-right text-xs text-muted-foreground font-mono shrink-0">
                    {new Date(ver.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}

"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Gauge,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Layers,
  Search,
  ShieldAlert,
  ShieldCheck,
  FileCode,
  Cpu,
  Clock,
  TrendingUp,
  Terminal,
  Zap,
  Tag,
  Loader2,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Sparkles,
  BarChart3,
  FileText,
  Copy,
  Check,
  X,
  Bug,
  Compass,
  GitPullRequest,
  Workflow,
  Lock,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  benchmarkService,
  SuiteRunPayload,
} from "@/services/benchmark-service";
import {
  BenchmarkCategory,
  BenchmarkRegression,
  BenchmarkReportResponse,
  BenchmarkRunComparisonResponse,
  BenchmarkScenario,
  BenchmarkScenarioResult,
  BenchmarkSuiteRun,
  BenchmarkSuiteRunDetail,
} from "@/types";

export default function BenchmarkIntelligenceConsole() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"overview" | "scenarios" | "results" | "comparison" | "safety">("overview");

  // Filter and selection state
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Runner controls state
  const [selectedModel, setSelectedModel] = useState("gemini-1.5-pro");
  const [codeRevision, setCodeRevision] = useState("HEAD");
  const [simulateSafetyFailure, setSimulateSafetyFailure] = useState(false);

  // Comparison state
  const [baselineRunId, setBaselineRunId] = useState<string>("");
  const [targetRunId, setTargetRunId] = useState<string>("");

  // Report modal state
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [selectedScenarioDetail, setSelectedScenarioDetail] = useState<BenchmarkScenario | BenchmarkScenarioResult | null>(null);
  const [copiedReport, setCopiedReport] = useState(false);

  // 1. Fetch scenarios
  const { data: scenariosData, isLoading: scenariosLoading } = useQuery({
    queryKey: ["benchmark_scenarios", selectedCategory],
    queryFn: () => benchmarkService.getScenarios(selectedCategory === "ALL" ? undefined : selectedCategory),
  });

  // 2. Fetch historical runs
  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ["benchmark_runs"],
    queryFn: () => benchmarkService.getRuns(),
  });

  // Automatically select latest run if none selected
  const latestRunId = selectedRunId || (runsData?.runs && runsData.runs.length > 0 ? runsData.runs[0].run_id : null);

  // 3. Fetch run detail
  const { data: runDetail, isLoading: runDetailLoading } = useQuery({
    queryKey: ["benchmark_run_detail", latestRunId],
    queryFn: () => (latestRunId ? benchmarkService.getRunDetail(latestRunId) : null),
    enabled: !!latestRunId,
  });

  // 4. Comparison mutation
  const compareMutation = useMutation({
    mutationFn: (req: { baseline_run_id: string; target_run_id: string }) =>
      benchmarkService.compareRuns(req),
  });

  // 5. Trigger run mutation
  const triggerRunMutation = useMutation({
    mutationFn: (payload: SuiteRunPayload) => benchmarkService.triggerSuiteRun(payload),
    onSuccess: (newRun) => {
      queryClient.invalidateQueries({ queryKey: ["benchmark_runs"] });
      setSelectedRunId(newRun.run_id);
      setActiveTab("overview");
    },
  });

  // 6. Report query
  const { data: reportData, refetch: fetchReport } = useQuery({
    queryKey: ["benchmark_report", latestRunId],
    queryFn: () => (latestRunId ? benchmarkService.getReport(latestRunId) : null),
    enabled: false,
  });

  // Handle open report modal
  const handleOpenReport = async () => {
    if (latestRunId) {
      await fetchReport();
      setReportModalOpen(true);
    }
  };

  const handleCopyReport = () => {
    if (reportData?.markdown_content) {
      navigator.clipboard.writeText(reportData.markdown_content);
      setCopiedReport(true);
      setTimeout(() => setCopiedReport(false), 2000);
    }
  };

  const scenariosList = scenariosData?.scenarios || [];
  const filteredScenarios = scenariosList.filter((s) => {
    if (selectedCategory !== "ALL" && s.category !== selectedCategory) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        s.name.toLowerCase().includes(q) ||
        s.scenario_key.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const categoryMeta: Record<string, { label: string; icon: any; weight: number; desc: string }> = {
    bug_detection: {
      label: "Bug Detection & Resolution",
      icon: Bug,
      weight: 30,
      desc: "Functional correctness, defect localization, patch generation, and regression avoidance.",
    },
    repo_understanding: {
      label: "Repository Understanding",
      icon: Compass,
      weight: 15,
      desc: "Cross-file symbol navigation, call-graph completeness, and entrypoint discovery.",
    },
    arch_intelligence: {
      label: "Architecture Intelligence",
      icon: Layers,
      weight: 15,
      desc: "Pattern inference, drift detection, layering integrity, and cyclic dependency analysis.",
    },
    refactoring: {
      label: "Autonomous Refactoring",
      icon: RotateCcw,
      weight: 15,
      desc: "Behavioral preservation, AST decomposition, and automated rollback verification.",
    },
    security_safety: {
      label: "Security and Safety",
      icon: Lock,
      weight: 15,
      desc: "Vulnerability remediation, multi-tenant isolation, and immutable approval gating.",
    },
    multi_agent: {
      label: "Multi-Agent Workflow Quality",
      icon: Workflow,
      weight: 5,
      desc: "Planner-coder handoffs, reviewer fidelity, retry loops, and checkpoint resumption.",
    },
    impact_analysis: {
      label: "Change Impact Analysis",
      icon: Zap,
      weight: 5,
      desc: "Blast radius precision, transitive dependency tracing, and test suite recommendation.",
    },
  };

  return (
    <AppLayout>
      <div className="flex-1 space-y-6 p-8 max-w-7xl mx-auto">
        {/* Header Hero */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/20 border border-primary/40 flex items-center justify-center text-primary shadow-[0_0_20px_rgba(37,99,235,0.3)]">
                <Gauge className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  Intelligence Evaluation & Benchmarking Console
                  <Badge variant="outline" className="font-mono text-xs border-primary/40 text-primary">
                    Stage 10.7
                  </Badge>
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Production-grade empirical evaluation measuring correctness, architectural fidelity, and safety invariants.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenReport}
              disabled={!latestRunId}
              className="gap-2 border-border/60 hover:bg-secondary/60 text-xs font-mono"
            >
              <FileText className="w-3.5 h-3.5 text-primary" />
              Audit Report
            </Button>

            <Button
              size="sm"
              onClick={() => {
                triggerRunMutation.mutate({
                  model_name: selectedModel,
                  code_revision: codeRevision,
                  simulate_safety_failure: simulateSafetyFailure,
                });
              }}
              disabled={triggerRunMutation.isPending}
              className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90 text-xs shadow-md font-mono"
            >
              {triggerRunMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Executing Suite...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  Run Suite Evaluation
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Global Controls & Run Selector Bar */}
        <div className="bg-card/40 border border-border/60 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 backdrop-blur-sm">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">
              Selected Model:
            </span>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-background border border-border/80 rounded-lg px-3 py-1.5 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="gemini-1.5-pro">Gemini 1.5 Pro (Default)</option>
              <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="gpt-4o">GPT-4o</option>
            </select>

            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono ml-2">
              Revision:
            </span>
            <Input
              value={codeRevision}
              onChange={(e) => setCodeRevision(e.target.value)}
              className="w-24 h-8 text-xs font-mono bg-background"
              placeholder="HEAD"
            />

            <label className="flex items-center gap-2 cursor-pointer ml-2">
              <input
                type="checkbox"
                checked={simulateSafetyFailure}
                onChange={(e) => setSimulateSafetyFailure(e.target.checked)}
                className="rounded border-border text-red-500 focus:ring-red-400 h-3.5 w-3.5"
              />
              <span className="text-xs text-muted-foreground hover:text-foreground">
                Simulate Safety Failure (Test Override)
              </span>
            </label>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">
              Active Run:
            </span>
            <select
              value={latestRunId || ""}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="bg-background border border-border/80 rounded-lg px-3 py-1.5 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {runsData?.runs && runsData.runs.length > 0 ? (
                runsData.runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.model_name} — Score {r.aggregate_score} ({r.status})
                  </option>
                ))
              ) : (
                <option value="">No historical runs</option>
              )}
            </select>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border/60 gap-8 text-sm font-medium">
          {[
            { id: "overview", label: "Executive Overview", icon: BarChart3 },
            { id: "scenarios", label: `Dataset Registry (${scenariosList.length})`, icon: Terminal },
            { id: "results", label: `Execution Results (${runDetail?.results?.length || 0})`, icon: CheckCircle2 },
            { id: "comparison", label: "Historical Comparison & Regressions", icon: TrendingUp },
            { id: "safety", label: "Safety & Governance Invariants", icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 pb-3 border-b-2 transition-all font-mono text-xs ${
                  active
                    ? "border-primary text-primary font-semibold"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? "text-primary" : "text-muted-foreground"}`} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* =========================================================================
            TAB 1: EXECUTIVE OVERVIEW
        ========================================================================= */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Critical Safety Alert Banner if triggered */}
            {runDetail?.critical_safety_failure && (
              <div className="p-4 rounded-xl border border-red-500/50 bg-red-500/10 backdrop-blur-sm flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-red-500 tracking-wide uppercase font-mono">
                    Critical Safety Failure Override Triggered
                  </h3>
                  <p className="text-xs text-red-200 mt-1">
                    A Category G security or invariant evaluation breach occurred (e.g. approval bypass or tenant isolation failure).
                    Per Devora AI safety governance, the aggregate score has been collapsed to 0.0 and autonomous execution halted.
                  </p>
                </div>
              </div>
            )}

            {/* 4 Summary Stat Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="bg-card/40 border-border/60">
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs uppercase font-mono tracking-wider">
                    Aggregate Intelligence Score
                  </CardDescription>
                  <CardTitle className="text-3xl font-bold font-mono text-foreground flex items-baseline gap-2">
                    {runDetail?.aggregate_score !== undefined ? runDetail.aggregate_score : "—"}
                    <span className="text-xs text-muted-foreground font-normal">/ 100</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 text-xs">
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        (runDetail?.aggregate_score || 0) >= 80 ? "bg-emerald-500" : "bg-amber-500"
                      }`}
                    />
                    <span className="text-muted-foreground">
                      {(runDetail?.aggregate_score || 0) >= 80 ? "Production Grade" : "Baseline Calibrated"}
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card/40 border-border/60">
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs uppercase font-mono tracking-wider">
                    Scenarios Pass Rate
                  </CardDescription>
                  <CardTitle className="text-3xl font-bold font-mono text-foreground">
                    {runDetail
                      ? `${Math.round((runDetail.passed_scenarios / Math.max(1, runDetail.total_scenarios)) * 100)}%`
                      : "—"}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground font-mono">
                    {runDetail?.passed_scenarios || 0} passed / {runDetail?.failed_scenarios || 0} failed
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/40 border-border/60">
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs uppercase font-mono tracking-wider">
                    Calibration Error (ECE)
                  </CardDescription>
                  <CardTitle className="text-3xl font-bold font-mono text-foreground">
                    {runDetail?.calibration_error !== undefined ? runDetail.calibration_error : "—"}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-emerald-400 font-mono">
                    High Grounding Confidence
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/40 border-border/60">
                <CardHeader className="pb-2">
                  <CardDescription className="text-xs uppercase font-mono tracking-wider">
                    Latency (p50) & Cost
                  </CardDescription>
                  <CardTitle className="text-2xl font-bold font-mono text-foreground">
                    {runDetail?.latency_p50_ms || 0} ms
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground font-mono">
                    ${(runDetail?.cost_estimate_usd || 0).toFixed(4)} USD ({runDetail?.token_usage_total?.toLocaleString() || 0} tokens)
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* 7 Canonical Category Breakdown Grid */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold text-foreground">Canonical Category Performance</h3>
                  <p className="text-xs text-muted-foreground">
                    Empirical scoring across functional correctness, architecture fidelity, refactoring, and safety.
                  </p>
                </div>
                <Badge variant="outline" className="font-mono text-xs border-border/80">
                  Formula: 0.30*Bug + 0.15*(Repo+Arch+Refact+Sec) + 0.05*(Agent+Impact)
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(categoryMeta).map(([catKey, meta]) => {
                  const Icon = meta.icon;
                  const score = runDetail?.category_scores ? runDetail.category_scores[catKey] ?? 100 : 100;
                  return (
                    <Card key={catKey} className="bg-card/30 border-border/50 hover:border-border transition-all">
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
                              <Icon className="w-3.5 h-3.5" />
                            </div>
                            <span className="text-xs font-semibold text-foreground font-mono">
                              {meta.label}
                            </span>
                          </div>
                          <Badge variant="secondary" className="font-mono text-[10px]">
                            {meta.weight}% Weight
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="flex items-baseline justify-between">
                          <span className="text-2xl font-bold font-mono text-foreground">{score}</span>
                          <span className="text-xs text-muted-foreground font-mono">/ 100 pts</span>
                        </div>
                        <div className="w-full bg-secondary/60 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              score >= 85 ? "bg-emerald-500" : score >= 70 ? "bg-amber-500" : "bg-red-500"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                          />
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                          {meta.desc}
                        </p>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 2: DATASET REGISTRY
        ========================================================================= */}
        {activeTab === "scenarios" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-muted-foreground uppercase font-mono">
                  Category Filter:
                </span>
                {["ALL", ...Object.keys(categoryMeta)].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-2.5 py-1 rounded-md text-xs font-mono transition-all ${
                      selectedCategory === cat
                        ? "bg-primary text-primary-foreground font-semibold"
                        : "bg-secondary/60 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {cat === "ALL" ? "All (31)" : cat.replace("_", " ")}
                  </button>
                ))}
              </div>

              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search scenarios..."
                  className="pl-9 h-9 text-xs font-mono"
                />
              </div>
            </div>

            <div className="border border-border/60 rounded-xl overflow-hidden bg-card/30">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-secondary/40 border-b border-border/60 text-muted-foreground font-mono uppercase text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Scenario Key</th>
                      <th className="py-3 px-4">Name & Task</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Difficulty</th>
                      <th className="py-3 px-4">Evaluation Type</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {filteredScenarios.map((sc) => (
                      <tr key={sc.id} className="hover:bg-secondary/20 transition-colors">
                        <td className="py-3 px-4 font-semibold text-primary">{sc.scenario_key}</td>
                        <td className="py-3 px-4 max-w-xs font-sans">
                          <div className="font-medium text-foreground">{sc.name}</div>
                          <div className="text-muted-foreground text-[11px] truncate">{sc.description}</div>
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant="outline" className="text-[10px] font-mono">
                            {sc.category}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <Badge
                            variant="secondary"
                            className={`text-[10px] font-mono ${
                              sc.difficulty === "CRITICAL"
                                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                : sc.difficulty === "HIGH"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-secondary text-muted-foreground"
                            }`}
                          >
                            {sc.difficulty}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-muted-foreground">{sc.eval_type}</td>
                        <td className="py-3 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedScenarioDetail(sc)}
                            className="h-7 px-2 text-xs text-primary hover:text-primary hover:bg-primary/10"
                          >
                            Inspect
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 3: RESULTS EXPLORER
        ========================================================================= */}
        {activeTab === "results" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-foreground">
                  Evaluation Scenario Outcomes
                </h3>
                <p className="text-xs text-muted-foreground">
                  Individual verification records showing ground truth comparison, execution duration, and invariants check.
                </p>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                Run ID: {runDetail?.run_id ? runDetail.run_id.slice(0, 8) : "None"}
              </Badge>
            </div>

            <div className="border border-border/60 rounded-xl overflow-hidden bg-card/30">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-secondary/40 border-b border-border/60 text-muted-foreground font-mono uppercase text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Scenario Key</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Score</th>
                      <th className="py-3 px-4">Latency</th>
                      <th className="py-3 px-4">Tokens</th>
                      <th className="py-3 px-4">Invariants</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {runDetail?.results && runDetail.results.length > 0 ? (
                      runDetail.results.map((r) => (
                        <tr key={r.result_id} className="hover:bg-secondary/20 transition-colors">
                          <td className="py-3 px-4">
                            <Badge
                              className={`text-[10px] font-mono ${
                                r.status === "PASSED"
                                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                  : r.status === "SAFETY_VIOLATION"
                                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                  : "bg-amber-500/20 text-amber-400"
                              }`}
                            >
                              {r.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 font-semibold text-foreground">
                            {r.scenario_key}
                          </td>
                          <td className="py-3 px-4 text-muted-foreground">{r.category}</td>
                          <td className="py-3 px-4 font-bold text-primary">{r.score}</td>
                          <td className="py-3 px-4 text-muted-foreground">{r.execution_time_ms} ms</td>
                          <td className="py-3 px-4 text-muted-foreground">{r.tokens_used}</td>
                          <td className="py-3 px-4">
                            {r.invariants_met ? (
                              <span className="flex items-center gap-1 text-emerald-400">
                                <Check className="w-3.5 h-3.5" /> Met
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-red-400">
                                <X className="w-3.5 h-3.5" /> Failed
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedScenarioDetail(r)}
                              className="h-7 px-2 text-xs text-primary hover:text-primary hover:bg-primary/10"
                            >
                              Evidence
                            </Button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-muted-foreground">
                          No scenario execution results available for this run.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            TAB 4: HISTORICAL COMPARISON & REGRESSIONS
        ========================================================================= */}
        {activeTab === "comparison" && (
          <div className="space-y-6">
            <Card className="bg-card/40 border-border/60">
              <CardHeader>
                <CardTitle className="text-base font-semibold">Run Comparison & Regression Detection</CardTitle>
                <CardDescription className="text-xs">
                  Select baseline and target runs to evaluate metric deltas and detect performance or safety regressions.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-mono uppercase text-muted-foreground block mb-1">
                      Baseline Run:
                    </label>
                    <select
                      value={baselineRunId}
                      onChange={(e) => setBaselineRunId(e.target.value)}
                      className="w-full bg-background border border-border/80 rounded-lg px-3 py-2 text-xs font-mono text-foreground"
                    >
                      <option value="">Select baseline run...</option>
                      {runsData?.runs?.map((r) => (
                        <option key={r.run_id} value={r.run_id}>
                          {r.model_name} — Score {r.aggregate_score} ({r.created_at.slice(0, 16)})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-mono uppercase text-muted-foreground block mb-1">
                      Target Run:
                    </label>
                    <select
                      value={targetRunId}
                      onChange={(e) => setTargetRunId(e.target.value)}
                      className="w-full bg-background border border-border/80 rounded-lg px-3 py-2 text-xs font-mono text-foreground"
                    >
                      <option value="">Select target run...</option>
                      {runsData?.runs?.map((r) => (
                        <option key={r.run_id} value={r.run_id}>
                          {r.model_name} — Score {r.aggregate_score} ({r.created_at.slice(0, 16)})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <Button
                  onClick={() => {
                    if (baselineRunId && targetRunId) {
                      compareMutation.mutate({
                        baseline_run_id: baselineRunId,
                        target_run_id: targetRunId,
                      });
                    }
                  }}
                  disabled={!baselineRunId || !targetRunId || compareMutation.isPending}
                  className="gap-2 text-xs font-mono"
                >
                  {compareMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
                  Compare Executions
                </Button>
              </CardContent>
            </Card>

            {compareMutation.data && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                  <Card className="bg-card/30 border-border/50">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-xs font-mono">Summary Verdict</CardDescription>
                      <CardTitle className="text-xl font-bold font-mono">
                        <Badge
                          className={
                            compareMutation.data.summary_verdict === "IMPROVED"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : compareMutation.data.summary_verdict === "REGRESSED"
                              ? "bg-amber-500/20 text-amber-400"
                              : "bg-red-500/20 text-red-400"
                          }
                        >
                          {compareMutation.data.summary_verdict}
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                  </Card>

                  <Card className="bg-card/30 border-border/50">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-xs font-mono">Score Delta</CardDescription>
                      <CardTitle className="text-2xl font-bold font-mono">
                        {compareMutation.data.score_delta > 0 ? `+${compareMutation.data.score_delta}` : compareMutation.data.score_delta} pts
                      </CardTitle>
                    </CardHeader>
                  </Card>

                  <Card className="bg-card/30 border-border/50">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-xs font-mono">Latency Delta</CardDescription>
                      <CardTitle className="text-2xl font-bold font-mono">
                        {compareMutation.data.latency_delta_ms > 0 ? `+${compareMutation.data.latency_delta_ms}` : compareMutation.data.latency_delta_ms} ms
                      </CardTitle>
                    </CardHeader>
                  </Card>

                  <Card className="bg-card/30 border-border/50">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-xs font-mono">Regressions Detected</CardDescription>
                      <CardTitle className="text-2xl font-bold font-mono text-amber-400">
                        {compareMutation.data.regressions_count}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                </div>

                {compareMutation.data.regressions.length > 0 ? (
                  <Card className="bg-card/30 border-border/50">
                    <CardHeader>
                      <CardTitle className="text-sm font-semibold text-amber-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" /> Detected Regressions
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {compareMutation.data.regressions.map((reg) => (
                        <div key={reg.regression_id} className="p-3 bg-secondary/40 rounded-lg border border-border/60 text-xs font-mono">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-foreground">{reg.scenario_key}</span>
                            <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/40">
                              {reg.severity}
                            </Badge>
                          </div>
                          <p className="text-muted-foreground">{reg.description}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : (
                  <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-mono flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    Zero regressions identified between baseline and target runs.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* =========================================================================
            TAB 5: SAFETY & GOVERNANCE INVARIANTS
        ========================================================================= */}
        {activeTab === "safety" && (
          <div className="space-y-6">
            <Card className="bg-card/40 border-border/60">
              <CardHeader>
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  Autonomous Engineering Safety Invariant Verification
                </CardTitle>
                <CardDescription className="text-xs">
                  Mandatory security constraints and verification policies enforced on every code generation and refactoring cycle.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  {
                    title: "Multi-Tenant Data Isolation",
                    code: "CWE-284",
                    desc: "All database queries, vector memory searches, and repository indexes must strictly enforce user_id and tenant scoping. Unfiltered queries are rejected at static analysis time.",
                    status: "ENFORCED",
                  },
                  {
                    title: "SQL Injection Prevention",
                    code: "CWE-89",
                    desc: "Raw string interpolation into SQL queries is prohibited. Only parameterized SQLAlchemy select/insert statements are accepted.",
                    status: "ENFORCED",
                  },
                  {
                    title: "Credential Redaction & Secret Detection",
                    code: "CWE-798",
                    desc: "Automated secret scanners verify that zero API tokens, private keys, or credentials exist in working trees or suggested code diffs.",
                    status: "ENFORCED",
                  },
                  {
                    title: "Cryptographic Diff Approval Binding",
                    code: "NIST-SP-800-161",
                    desc: "Human review approvals are bound to SHA-256 diff hashes. Any drift in working tree or plan invalidates approval, preventing unauthorized autonomous execution.",
                    status: "ENFORCED",
                  },
                ].map((item, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-secondary/30 border border-border/50 flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-foreground">{item.title}</span>
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {item.code}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{item.desc}</p>
                    </div>
                    <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono shrink-0">
                      {item.status}
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Report Modal */}
        {reportModalOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-card border border-border rounded-xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl">
              <div className="p-4 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary" />
                  <h3 className="font-semibold text-sm text-foreground">Audit-Ready Benchmark Report</h3>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyReport}
                    className="h-8 gap-1.5 text-xs font-mono"
                  >
                    {copiedReport ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedReport ? "Copied" : "Copy Markdown"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setReportModalOpen(false)}
                    className="h-8 w-8 p-0"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <div className="p-6 overflow-y-auto flex-1 font-mono text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
                {reportData?.markdown_content || "Loading benchmark report..."}
              </div>
            </div>
          </div>
        )}

        {/* Scenario / Result Inspect Modal */}
        {selectedScenarioDetail && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-card border border-border rounded-xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl">
              <div className="p-4 border-b border-border flex items-center justify-between">
                <h3 className="font-semibold text-sm text-foreground font-mono">
                  {"scenario_key" in selectedScenarioDetail ? selectedScenarioDetail.scenario_key : "Scenario Evidence"}
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedScenarioDetail(null)}
                  className="h-8 w-8 p-0"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="p-6 overflow-y-auto flex-1 space-y-4 text-xs font-mono">
                <div>
                  <span className="font-bold text-foreground block mb-1">Expected Output Assertions:</span>
                  <pre className="p-3 bg-secondary/40 rounded-lg overflow-x-auto text-emerald-400">
                    {JSON.stringify(selectedScenarioDetail.expected_output, null, 2)}
                  </pre>
                </div>
                {"actual_output" in selectedScenarioDetail && (
                  <div>
                    <span className="font-bold text-foreground block mb-1">Actual Output Received:</span>
                    <pre className="p-3 bg-secondary/40 rounded-lg overflow-x-auto text-primary">
                      {JSON.stringify((selectedScenarioDetail as BenchmarkScenarioResult).actual_output, null, 2)}
                    </pre>
                  </div>
                )}
                {"input_context" in selectedScenarioDetail && (
                  <div>
                    <span className="font-bold text-foreground block mb-1">Input Context & Prompt:</span>
                    <pre className="p-3 bg-secondary/40 rounded-lg overflow-x-auto text-muted-foreground">
                      {JSON.stringify(selectedScenarioDetail.input_context, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

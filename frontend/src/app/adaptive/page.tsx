"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Brain,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Layers,
  Search,
  ShieldAlert,
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
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  adaptiveService,
  EngineeringExperience,
  ExperienceSearchResult,
  TaskFailureRecord,
  BenchmarkDefinition,
  BenchmarkRun,
  BenchmarkSummary,
} from "@/services/adaptive-service";

export default function AdaptiveIntelligencePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"experiences" | "agents" | "failures" | "benchmarks">("experiences");

  // Experiences tab state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [taskCategoryFilter, setTaskCategoryFilter] = useState<string>("");
  const [expandedExpId, setExpandedExpId] = useState<string | null>(null);

  // Failure tab state
  const [stageFilter, setStageFilter] = useState<string>("");
  const [failureTypeFilter, setFailureTypeFilter] = useState<string>("");

  // Benchmarks tab state
  const [lastBenchmarkSummary, setLastBenchmarkSummary] = useState<BenchmarkSummary | null>(null);

  // 1. Fetch Experiences
  const { data: experiences = [], isLoading: isExperiencesLoading } = useQuery({
    queryKey: ["adaptive-experiences", statusFilter, taskCategoryFilter],
    queryFn: () =>
      adaptiveService.listExperiences({
        status_type: statusFilter || undefined,
        task_category: taskCategoryFilter || undefined,
        limit: 50,
      }),
  });

  // Search Mutation
  const searchMutation = useMutation({
    mutationFn: (q: string) =>
      adaptiveService.searchExperiences({
        query: q,
        status_type: statusFilter || undefined,
        task_category: taskCategoryFilter || undefined,
        limit: 10,
      }),
  });

  // 2. Fetch Agent Performance
  const { data: performanceData, isLoading: isPerfLoading } = useQuery({
    queryKey: ["adaptive-agent-performance"],
    queryFn: () => adaptiveService.getAgentPerformance(),
  });

  // 3. Fetch Failures
  const { data: failures = [], isLoading: isFailuresLoading } = useQuery({
    queryKey: ["adaptive-failures", stageFilter, failureTypeFilter],
    queryFn: () =>
      adaptiveService.listFailures({
        stage: stageFilter || undefined,
        failure_type: failureTypeFilter || undefined,
        limit: 50,
      }),
  });

  // 4. Fetch Benchmarks
  const { data: benchmarkDefs = [], isLoading: isBenchmarksLoading } = useQuery({
    queryKey: ["adaptive-benchmarks"],
    queryFn: () => adaptiveService.listBenchmarks(),
  });

  const { data: benchmarkHistory = [], isLoading: isHistoryLoading } = useQuery({
    queryKey: ["adaptive-benchmark-history"],
    queryFn: () => adaptiveService.getBenchmarkHistory(20),
  });

  // Run Benchmarks Mutation
  const runBenchmarksMutation = useMutation({
    mutationFn: (benchmarkId?: string) =>
      adaptiveService.runBenchmarks({
        benchmark_id: benchmarkId,
        system_version: "v1.0.0",
        model_version: "gemini-1.5-pro",
      }),
    onSuccess: (data) => {
      setLastBenchmarkSummary(data);
      queryClient.invalidateQueries({ queryKey: ["adaptive-benchmark-history"] });
    },
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      searchMutation.mutate(searchQuery.trim());
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    searchMutation.reset();
  };

  // Status badge styling helper
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "verified_successful":
        return (
          <Badge variant="outline" className="text-emerald-400 border-emerald-500/40 bg-emerald-500/10 font-mono text-[10px]">
            Verified Success (1.3x)
          </Badge>
        );
      case "verified_failed":
        return (
          <Badge variant="outline" className="text-amber-400 border-amber-500/40 bg-amber-500/10 font-mono text-[10px]">
            Verified Failed (0.5x)
          </Badge>
        );
      case "unverified_hypothesis":
        return (
          <Badge variant="outline" className="text-blue-400 border-blue-500/40 bg-blue-500/10 font-mono text-[10px]">
            Hypothesis (0.7x)
          </Badge>
        );
      case "incomplete_attempt":
        return (
          <Badge variant="outline" className="text-muted-foreground border-border bg-secondary/30 font-mono text-[10px]">
            Incomplete (0.2x)
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-muted-foreground font-mono text-[10px]">
            {status}
          </Badge>
        );
    }
  };

  return (
    <AppLayout>
      <div className="space-y-6 pb-12 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.25)]">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  <span>Adaptive Engineering Intelligence</span>
                  <Badge variant="outline" className="text-[10px] font-mono border-indigo-500/40 text-indigo-400 bg-indigo-500/10">
                    Phase 7
                  </Badge>
                </h1>
                <p className="text-xs text-muted-foreground">
                  Closed-loop empirical learning from verified task outcomes, failure taxonomy, and multi-agent performance telemetry.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                queryClient.invalidateQueries({ queryKey: ["adaptive-experiences"] });
                queryClient.invalidateQueries({ queryKey: ["adaptive-agent-performance"] });
                queryClient.invalidateQueries({ queryKey: ["adaptive-failures"] });
                queryClient.invalidateQueries({ queryKey: ["adaptive-benchmark-history"] });
              }}
              className="text-xs gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Refresh Metrics</span>
            </Button>
          </div>
        </div>

        {/* Global Empirical Metrics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-1 pt-4 px-4">
              <CardDescription className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                Verified Experiences
              </CardDescription>
              <CardTitle className="text-2xl font-bold font-mono text-foreground flex items-center justify-between">
                <span>{experiences.length}</span>
                <Brain className="w-5 h-5 text-indigo-400 opacity-80" />
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-1 text-[11px] text-muted-foreground font-mono">
              <span className="text-emerald-400 font-semibold">
                {experiences.filter((e) => e.status_type === "verified_successful").length}
              </span>{" "}
              successes &bull;{" "}
              <span className="text-amber-400 font-semibold">
                {experiences.filter((e) => e.status_type === "verified_failed").length}
              </span>{" "}
              negative guidance
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-1 pt-4 px-4">
              <CardDescription className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                First-Pass Success Rate
              </CardDescription>
              <CardTitle className="text-2xl font-bold font-mono text-emerald-400 flex items-center justify-between">
                <span>
                  {performanceData ? `${(performanceData.overall_first_pass_rate * 100).toFixed(1)}%` : "--"}
                </span>
                <TrendingUp className="w-5 h-5 text-emerald-400 opacity-80" />
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-1 text-[11px] text-muted-foreground font-mono">
              Evaluated across {performanceData?.total_tasks_evaluated || 0} autonomous tasks
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-1 pt-4 px-4">
              <CardDescription className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                Failures Documented
              </CardDescription>
              <CardTitle className="text-2xl font-bold font-mono text-amber-400 flex items-center justify-between">
                <span>{failures.length}</span>
                <ShieldAlert className="w-5 h-5 text-amber-400 opacity-80" />
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-1 text-[11px] text-muted-foreground font-mono">
              Structured taxonomy across 4 verification stages
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="pb-1 pt-4 px-4">
              <CardDescription className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                Canonical Benchmarks
              </CardDescription>
              <CardTitle className="text-2xl font-bold font-mono text-primary flex items-center justify-between">
                <span>{benchmarkDefs.length} Tests</span>
                <CheckCircle2 className="w-5 h-5 text-primary opacity-80" />
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-1 text-[11px] text-muted-foreground font-mono">
              {benchmarkHistory.length} recorded version runs
            </CardContent>
          </Card>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border gap-6 text-xs font-mono">
          {[
            { id: "experiences", label: "Experience Intelligence", icon: Brain, count: experiences.length },
            { id: "agents", label: "Agent Performance Matrix", icon: Cpu, count: performanceData?.agents?.length || 9 },
            { id: "failures", label: "Failure Learning & Pitfalls", icon: AlertTriangle, count: failures.length },
            { id: "benchmarks", label: "Engineering Benchmarks", icon: CheckCircle2, count: benchmarkDefs.length },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 pb-3 transition-colors relative whitespace-nowrap ${
                  isActive
                    ? "text-indigo-400 font-semibold border-b-2 border-indigo-500"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
                {typeof tab.count === "number" && (
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-secondary text-foreground font-mono">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: EXPERIENCE INTELLIGENCE & SEMANTIC SEARCH */}
        {/* ========================================================================= */}
        {activeTab === "experiences" && (
          <div className="space-y-4">
            {/* Search and Filters */}
            <Card className="bg-card/40 border-border">
              <CardContent className="pt-4 pb-4 space-y-3">
                <form onSubmit={handleSearchSubmit} className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
                    <Input
                      placeholder="Semantic search across verified experiences (e.g. 'SQL connection refused', 'asyncpg timeout', 'FastAPI Pydantic v2 migration')..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 text-xs bg-background/60"
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={searchMutation.isPending || !searchQuery.trim()}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs gap-1.5"
                  >
                    {searchMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>Semantic Search</span>
                  </Button>
                  {searchMutation.isSuccess && (
                    <Button variant="ghost" size="sm" onClick={clearSearch} className="text-xs">
                      Clear Search
                    </Button>
                  )}
                </form>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
                  <span className="text-muted-foreground font-mono text-[11px]">Filter by:</span>

                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="bg-secondary/60 border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none"
                  >
                    <option value="">All Statuses</option>
                    <option value="verified_successful">Verified Successful (1.3x)</option>
                    <option value="verified_failed">Verified Failed (0.5x)</option>
                    <option value="unverified_hypothesis">Hypothesis (0.7x)</option>
                    <option value="incomplete_attempt">Incomplete (0.2x)</option>
                  </select>

                  <select
                    value={taskCategoryFilter}
                    onChange={(e) => setTaskCategoryFilter(e.target.value)}
                    className="bg-secondary/60 border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none"
                  >
                    <option value="">All Task Categories</option>
                    <option value="bug_fix">Bug Fix</option>
                    <option value="feature">Feature</option>
                    <option value="refactor">Refactor</option>
                    <option value="exploration">Exploration</option>
                    <option value="test_improvement">Test Improvement</option>
                  </select>
                </div>
              </CardContent>
            </Card>

            {/* Semantic Search Results (if active) */}
            {searchMutation.isSuccess && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-indigo-400">
                    Semantic Search Matches ({searchMutation.data.length}) &bull; Ranked by Weighted Relevance
                  </h3>
                </div>

                {searchMutation.data.length === 0 ? (
                  <Card className="bg-card/20 border-border p-6 text-center text-xs text-muted-foreground">
                    No matching experiences found above similarity threshold.
                  </Card>
                ) : (
                  searchMutation.data.map((res: ExperienceSearchResult) => (
                    <Card
                      key={res.id}
                      className={`border ${
                        res.is_positive_guidance ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
                      }`}
                    >
                      <CardHeader className="p-4 pb-2">
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              {renderStatusBadge(res.status_type)}
                              <Badge variant="outline" className="font-mono text-[10px]">
                                {res.task_category}
                              </Badge>
                              {res.bug_category && (
                                <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">
                                  {res.bug_category}
                                </Badge>
                              )}
                            </div>
                            <CardTitle className="text-sm font-semibold text-foreground pt-1">
                              {res.problem_summary}
                            </CardTitle>
                          </div>
                          <div className="text-right font-mono text-xs shrink-0">
                            <div className="text-indigo-400 font-bold">
                              {(res.weighted_score * 100).toFixed(1)} weighted
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                              {(res.similarity * 100).toFixed(1)}% cosine
                            </div>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="p-4 pt-1 space-y-2 text-xs">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-secondary/30 p-2.5 rounded border border-border/40">
                          <div>
                            <span className="text-[10px] font-mono uppercase text-muted-foreground block mb-0.5">
                              Root Cause:
                            </span>
                            <p className="text-foreground">{res.root_cause}</p>
                          </div>
                          <div>
                            <span className="text-[10px] font-mono uppercase text-muted-foreground block mb-0.5">
                              Resolution Strategy:
                            </span>
                            <p className="text-foreground">{res.resolution_strategy}</p>
                          </div>
                        </div>

                        {res.technology_stack && res.technology_stack.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {res.technology_stack.map((t, idx) => (
                              <Badge key={idx} variant="secondary" className="text-[10px] font-mono">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            )}

            {/* General Experiences List */}
            {!searchMutation.isSuccess && (
              <div className="space-y-3">
                {isExperiencesLoading ? (
                  <div className="p-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
                    <span className="text-xs text-muted-foreground mt-2 block font-mono">Loading experiences...</span>
                  </div>
                ) : experiences.length === 0 ? (
                  <Card className="bg-card/20 border-dashed border-border p-12 text-center space-y-2">
                    <Brain className="w-10 h-10 text-muted-foreground mx-auto opacity-50" />
                    <p className="text-sm font-medium text-foreground">No Engineering Experiences Found</p>
                    <p className="text-xs text-muted-foreground max-w-md mx-auto">
                      Experiences are distilled automatically upon successful task completions, test verifications, and post-mortem reviews.
                    </p>
                  </Card>
                ) : (
                  experiences.map((exp: EngineeringExperience) => {
                    const isExpanded = expandedExpId === exp.id;
                    return (
                      <Card key={exp.id} className="bg-card/40 border-border hover:border-border/80 transition-all">
                        <CardHeader className="p-4 pb-2">
                          <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1.5 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                {renderStatusBadge(exp.status_type)}
                                <Badge variant="outline" className="font-mono text-[10px]">
                                  {exp.task_category}
                                </Badge>
                                {exp.bug_category && (
                                  <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">
                                    {exp.bug_category}
                                  </Badge>
                                )}
                                <span className="text-[11px] font-mono text-muted-foreground ml-auto sm:ml-0">
                                  {new Date(exp.created_at).toLocaleDateString()}
                                </span>
                              </div>
                              <CardTitle className="text-sm font-semibold text-foreground">
                                {exp.problem_summary}
                              </CardTitle>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setExpandedExpId(isExpanded ? null : exp.id)}
                              className="text-xs shrink-0 gap-1 font-mono"
                            >
                              <span>{isExpanded ? "Collapse" : "Details"}</span>
                              {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent className="p-4 pt-1 space-y-3 text-xs">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-secondary/30 p-2.5 rounded border border-border/40">
                            <div>
                              <span className="text-[10px] font-mono uppercase text-muted-foreground block mb-0.5">
                                Root Cause:
                              </span>
                              <p className="text-foreground">{exp.root_cause}</p>
                            </div>
                            <div>
                              <span className="text-[10px] font-mono uppercase text-muted-foreground block mb-0.5">
                                Resolution Strategy:
                              </span>
                              <p className="text-foreground">{exp.resolution_strategy}</p>
                            </div>
                          </div>

                          {/* Tech stack and files */}
                          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {exp.technology_stack?.map((t, idx) => (
                                <Badge key={idx} variant="secondary" className="text-[10px] font-mono">
                                  {t}
                                </Badge>
                              ))}
                              {exp.files_involved?.map((f, idx) => (
                                <Badge key={idx} variant="outline" className="text-[10px] font-mono text-muted-foreground">
                                  <FileCode className="w-3 h-3 mr-1" />
                                  {f}
                                </Badge>
                              ))}
                            </div>
                            <div className="flex items-center gap-2 font-mono text-muted-foreground text-[10px]">
                              <span>Attempts: {exp.attempts_count}</span>
                              <span>&bull;</span>
                              <span>Quality: {exp.quality_score}</span>
                            </div>
                          </div>

                          {/* Expandable Technical Details & Diff */}
                          {isExpanded && (
                            <div className="pt-3 border-t border-border/60 space-y-3">
                              {exp.diff_patch && (
                                <div className="space-y-1">
                                  <span className="text-[10px] font-mono uppercase text-muted-foreground block">
                                    Precision Diff Patch:
                                  </span>
                                  <pre className="p-3 bg-black/80 rounded font-mono text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap max-h-56 border border-border/40">
                                    {exp.diff_patch}
                                  </pre>
                                </div>
                              )}

                              {exp.failed_approaches && exp.failed_approaches.length > 0 && (
                                <div className="space-y-1 bg-amber-500/5 border border-amber-500/20 p-2.5 rounded">
                                  <span className="text-[10px] font-mono uppercase text-amber-400 font-semibold block">
                                    Documented Failed Approaches ({exp.failed_approaches.length}):
                                  </span>
                                  <ul className="list-disc list-inside text-muted-foreground text-[11px] space-y-0.5">
                                    {exp.failed_approaches.map((fa, fIdx) => (
                                      <li key={fIdx}>{typeof fa === "string" ? fa : JSON.stringify(fa)}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: AGENT PERFORMANCE MATRIX */}
        {/* ========================================================================= */}
        {activeTab === "agents" && (
          <div className="space-y-4">
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Specialist Agent Performance Matrix</CardTitle>
                <CardDescription className="text-xs">
                  Empirical execution telemetry across all 9 specialized LangGraph agents.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-secondary/40 text-muted-foreground font-mono text-[11px] uppercase border-y border-border">
                      <tr>
                        <th className="px-4 py-3">Specialist Agent</th>
                        <th className="px-4 py-3">Total Runs</th>
                        <th className="px-4 py-3">Success Rate</th>
                        <th className="px-4 py-3">Avg Latency</th>
                        <th className="px-4 py-3">Retry Freq</th>
                        <th className="px-4 py-3">Rejection Rate</th>
                        <th className="px-4 py-3">Est. Tokens</th>
                        <th className="px-4 py-3">Est. Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border font-mono">
                      {isPerfLoading ? (
                        <tr>
                          <td colSpan={8} className="p-8 text-center text-muted-foreground">
                            Loading performance matrix...
                          </td>
                        </tr>
                      ) : !performanceData || performanceData.agents.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="p-8 text-center text-muted-foreground">
                            No agent runs evaluated yet.
                          </td>
                        </tr>
                      ) : (
                        performanceData.agents.map((agent) => (
                          <tr key={agent.agent_name} className="hover:bg-secondary/20 transition-colors">
                            <td className="px-4 py-3 font-semibold text-foreground flex items-center gap-2">
                              <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                              <span>{agent.agent_name}</span>
                            </td>
                            <td className="px-4 py-3">{agent.total_runs}</td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={
                                    agent.success_rate >= 0.85
                                      ? "text-emerald-400 font-bold"
                                      : agent.success_rate >= 0.7
                                      ? "text-amber-400 font-bold"
                                      : "text-destructive font-bold"
                                  }
                                >
                                  {(agent.success_rate * 100).toFixed(1)}%
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3">{agent.average_duration_ms.toFixed(0)} ms</td>
                            <td className="px-4 py-3">{agent.retry_frequency.toFixed(2)}</td>
                            <td className="px-4 py-3">{(agent.rejection_rate * 100).toFixed(1)}%</td>
                            <td className="px-4 py-3">{agent.estimated_tokens_used.toLocaleString()}</td>
                            <td className="px-4 py-3 text-emerald-400">${agent.estimated_cost_usd.toFixed(4)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Task Category Breakdown */}
            {performanceData?.categories_breakdown && (
              <Card className="bg-card/40 border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-semibold">Performance by Task Category</CardTitle>
                  <CardDescription className="text-xs">
                    Reliability metrics segmented across engineering problem domains.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {Object.entries(performanceData.categories_breakdown).map(([cat, stats]: [string, any]) => (
                      <div key={cat} className="p-3 rounded-lg bg-secondary/30 border border-border/50 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-semibold text-foreground uppercase">{cat}</span>
                          <Badge variant="outline" className="font-mono text-[10px]">
                            {stats.count || 0} tasks
                          </Badge>
                        </div>
                        <div className="text-[11px] font-mono text-muted-foreground flex justify-between">
                          <span>Pass Rate:</span>
                          <span className="text-emerald-400 font-bold">
                            {stats.pass_rate ? `${(stats.pass_rate * 100).toFixed(1)}%` : "100.0%"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: FAILURE LEARNING & PITFALLS */}
        {/* ========================================================================= */}
        {activeTab === "failures" && (
          <div className="space-y-4">
            {/* Filters */}
            <Card className="bg-card/40 border-border">
              <CardContent className="p-3 flex flex-wrap items-center gap-3 text-xs">
                <span className="text-muted-foreground font-mono text-[11px]">Filter Failures:</span>
                <select
                  value={stageFilter}
                  onChange={(e) => setStageFilter(e.target.value)}
                  className="bg-secondary/60 border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none"
                >
                  <option value="">All Verification Stages</option>
                  <option value="TESTING">Testing Stage</option>
                  <option value="CODE_REVIEW">Code Review</option>
                  <option value="SECURITY_AUDIT">Security Audit</option>
                  <option value="DEVELOPER_REVIEW">Developer Review</option>
                </select>

                <select
                  value={failureTypeFilter}
                  onChange={(e) => setFailureTypeFilter(e.target.value)}
                  className="bg-secondary/60 border border-border rounded px-2.5 py-1 text-xs text-foreground focus:outline-none"
                >
                  <option value="">All Failure Types</option>
                  <option value="INCORRECT_ASSUMPTION">Incorrect Assumption</option>
                  <option value="IMPLEMENTATION_DEFECT">Implementation Defect</option>
                  <option value="DEPENDENCY_ISSUE">Dependency Issue</option>
                  <option value="ENVIRONMENT_PROBLEM">Environment Problem</option>
                </select>
              </CardContent>
            </Card>

            {/* Failure Records List */}
            {isFailuresLoading ? (
              <div className="p-12 text-center">
                <Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" />
                <span className="text-xs text-muted-foreground mt-2 block font-mono">Loading failure taxonomy...</span>
              </div>
            ) : failures.length === 0 ? (
              <Card className="bg-card/20 border-dashed border-border p-12 text-center space-y-2">
                <ShieldAlert className="w-10 h-10 text-emerald-400 mx-auto opacity-70" />
                <p className="text-sm font-medium text-foreground">Zero Cataloged Failures</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  When tasks fail assertions in the test sandbox or receive negative review decisions, structured post-mortems appear here to prevent recurring regressions.
                </p>
              </Card>
            ) : (
              failures.map((f: TaskFailureRecord) => (
                <Card key={f.id} className="bg-card/40 border-amber-500/30">
                  <CardHeader className="p-4 pb-2">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-amber-400 border-amber-500/40 bg-amber-500/10 font-mono text-[10px]">
                            {f.stage}
                          </Badge>
                          <Badge variant="outline" className="font-mono text-[10px]">
                            {f.failure_type.replace("_", " ")}
                          </Badge>
                          <span className="text-[10px] font-mono text-muted-foreground">
                            Attempt #{f.attempt_number} &bull; {new Date(f.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <CardTitle className="text-xs font-semibold text-foreground pt-1">
                          Failed Strategy: {f.failed_strategy}
                        </CardTitle>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 space-y-2 text-xs">
                    {/* Lessons Learned */}
                    <div className="p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/20 space-y-1">
                      <span className="text-[10px] font-mono uppercase text-indigo-400 font-bold block">
                        Lesson Learned & Prevention Guidance:
                      </span>
                      <p className="text-foreground leading-relaxed">{f.lessons_learned}</p>
                    </div>

                    {/* Error log if present */}
                    {f.error_log && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-mono uppercase text-muted-foreground block">
                          Error Log Snapshot:
                        </span>
                        <pre className="p-2.5 bg-black/80 rounded font-mono text-[10px] text-destructive overflow-x-auto whitespace-pre-wrap max-h-32 border border-border/40">
                          {f.error_log}
                        </pre>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: ENGINEERING BENCHMARKS */}
        {/* ========================================================================= */}
        {activeTab === "benchmarks" && (
          <div className="space-y-6">
            {/* Benchmark Suite Controls */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <CardTitle className="text-sm font-semibold">Canonical Engineering Benchmarks</CardTitle>
                    <CardDescription className="text-xs">
                      7 standardized software engineering challenges spanning bug fixes, refactoring, dependencies, and code quality.
                    </CardDescription>
                  </div>
                  <Button
                    onClick={() => runBenchmarksMutation.mutate(undefined)}
                    disabled={runBenchmarksMutation.isPending}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs gap-1.5 shrink-0"
                  >
                    {runBenchmarksMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                    <span>Run Full Benchmark Suite</span>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Last Run Summary (if executed) */}
                {lastBenchmarkSummary && (
                  <div className="p-4 rounded-lg bg-indigo-500/5 border border-indigo-500/30 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <h4 className="text-xs font-semibold font-mono text-indigo-400 uppercase tracking-wider">
                          Benchmark Evaluation Complete ({lastBenchmarkSummary.system_version})
                        </h4>
                      </div>
                      <Badge variant="outline" className="font-mono text-[10px] text-emerald-400 border-emerald-500/40">
                        {(lastBenchmarkSummary.test_pass_rate * 100).toFixed(1)}% Pass Rate
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs font-mono">
                      <div className="p-2 rounded bg-secondary/40 border border-border/40">
                        <span className="text-muted-foreground text-[10px] block">Tasks Completed</span>
                        <span className="text-sm font-bold text-foreground">
                          {lastBenchmarkSummary.tasks_completed_count} / {lastBenchmarkSummary.total_benchmarks}
                        </span>
                      </div>
                      <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20">
                        <span className="text-emerald-400 text-[10px] block">Tests Passed</span>
                        <span className="text-sm font-bold text-emerald-400">
                          {lastBenchmarkSummary.tests_passed_count} / {lastBenchmarkSummary.total_benchmarks}
                        </span>
                      </div>
                      <div className="p-2 rounded bg-secondary/40 border border-border/40">
                        <span className="text-muted-foreground text-[10px] block">Avg Execution Time</span>
                        <span className="text-sm font-bold text-foreground">
                          {(lastBenchmarkSummary.average_execution_time_ms / 1000).toFixed(2)}s
                        </span>
                      </div>
                      <div className="p-2 rounded bg-secondary/40 border border-border/40">
                        <span className="text-muted-foreground text-[10px] block">Est. Cost</span>
                        <span className="text-sm font-bold text-emerald-400">
                          ${lastBenchmarkSummary.total_estimated_cost_usd.toFixed(4)}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Benchmark Definitions Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {isBenchmarksLoading ? (
                    <div className="p-8 text-center col-span-2 text-muted-foreground font-mono text-xs">
                      Loading benchmark suite...
                    </div>
                  ) : (
                    benchmarkDefs.map((bm: BenchmarkDefinition) => (
                      <Card key={bm.id} className="bg-secondary/20 border-border">
                        <CardHeader className="p-3.5 pb-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-indigo-400">{bm.id}</span>
                                <Badge variant="outline" className="text-[10px] font-mono">
                                  {bm.category}
                                </Badge>
                              </div>
                              <CardTitle className="text-xs font-semibold text-foreground pt-1">
                                {bm.name}
                              </CardTitle>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => runBenchmarksMutation.mutate(bm.id)}
                              disabled={runBenchmarksMutation.isPending}
                              className="text-[11px] h-7 gap-1 font-mono"
                            >
                              <Play className="w-3 h-3" />
                              <span>Run</span>
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent className="p-3.5 pt-1 space-y-2 text-xs">
                          <p className="text-muted-foreground text-[11px] leading-relaxed">{bm.description}</p>
                          <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground pt-1 border-t border-border/40">
                            <span>Baseline Pass: {(bm.baseline_pass_rate * 100).toFixed(0)}%</span>
                            <span>Snapshot: {bm.initial_repo_snapshot}</span>
                          </div>
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Historical Benchmark Runs Table */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Version-over-Version Benchmark History</CardTitle>
                <CardDescription className="text-xs">
                  Empirical tracking of autonomous engineering capability across releases.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-secondary/40 text-muted-foreground font-mono text-[11px] uppercase border-y border-border">
                      <tr>
                        <th className="px-4 py-3">Benchmark ID</th>
                        <th className="px-4 py-3">Version</th>
                        <th className="px-4 py-3">Model</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Tests Passed</th>
                        <th className="px-4 py-3">Retries</th>
                        <th className="px-4 py-3">Duration</th>
                        <th className="px-4 py-3">Cost</th>
                        <th className="px-4 py-3">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border font-mono">
                      {isHistoryLoading ? (
                        <tr>
                          <td colSpan={9} className="p-6 text-center text-muted-foreground">
                            Loading benchmark history...
                          </td>
                        </tr>
                      ) : benchmarkHistory.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="p-6 text-center text-muted-foreground">
                            No historical benchmark runs recorded yet.
                          </td>
                        </tr>
                      ) : (
                        benchmarkHistory.map((run: BenchmarkRun) => (
                          <tr key={run.id} className="hover:bg-secondary/20 transition-colors">
                            <td className="px-4 py-3 font-semibold text-foreground">{run.benchmark_id}</td>
                            <td className="px-4 py-3">{run.system_version}</td>
                            <td className="px-4 py-3 text-muted-foreground">{run.model_version}</td>
                            <td className="px-4 py-3">
                              {run.task_completed ? (
                                <Badge variant="outline" className="text-emerald-400 border-emerald-500/40 text-[10px]">
                                  Completed
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-destructive border-destructive/40 text-[10px]">
                                  Failed
                                </Badge>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {run.tests_passed ? (
                                <span className="text-emerald-400 font-bold">Passed</span>
                              ) : (
                                <span className="text-destructive font-bold">Failed</span>
                              )}
                            </td>
                            <td className="px-4 py-3">{run.retries_count}</td>
                            <td className="px-4 py-3">{(run.execution_time_ms / 1000).toFixed(2)}s</td>
                            <td className="px-4 py-3 text-emerald-400">${run.estimated_cost_usd.toFixed(4)}</td>
                            <td className="px-4 py-3 text-muted-foreground">
                              {new Date(run.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

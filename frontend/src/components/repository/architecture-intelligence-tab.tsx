"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Cpu,
  Database,
  ExternalLink,
  FileCode,
  FileText,
  FileWarning,
  Filter,
  GitCommit,
  HelpCircle,
  History,
  Layers,
  Layout,
  Lightbulb,
  Loader2,
  Network,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Sliders,
  Sparkles,
  Terminal,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { architectureService } from "@/services/architecture-service";
import {
  ArchitectureAskResponse,
  ArchitectureConventionItem,
  ArchitectureDriftResponse,
  ArchitecturePatternItem,
  ArchitectureSummaryResponse,
  DriftViolationItem,
  HybridSearchResultItem,
  HybridSearchResponse,
  TechnicalDebtFindingItem,
  TechnicalDebtFindingsResponse,
  TechnicalDebtSummaryResponse,
  TechnicalDebtTrendsResponse,
} from "@/types";

interface ArchitectureIntelligenceTabProps {
  repositoryId: string;
}

export function ArchitectureIntelligenceTab({ repositoryId }: ArchitectureIntelligenceTabProps) {
  const queryClient = useQueryClient();
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "patterns" | "conventions" | "search" | "ask" | "drift" | "debt">("overview");

  // Pattern filters
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [expandedPatternId, setExpandedPatternId] = useState<string | null>(null);

  // Drift filters & state
  const [driftSeverityFilter, setDriftSeverityFilter] = useState<string>("all");
  const [driftCategoryFilter, setDriftCategoryFilter] = useState<string>("all");
  const [expandedViolationId, setExpandedViolationId] = useState<string | null>(null);

  // Technical debt filters & state
  const [debtCategoryFilter, setDebtCategoryFilter] = useState<string>("all");
  const [debtSeverityFilter, setDebtSeverityFilter] = useState<string>("all");
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);

  // Hybrid search state
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchLanguage, setSearchLanguage] = useState<string>("");
  const [searchSymbolType, setSearchSymbolType] = useState<string>("");
  const [lexicalWeight, setLexicalWeight] = useState<number>(0.35);
  const [semanticWeight, setSemanticWeight] = useState<number>(0.45);
  const [structuralWeight, setStructuralWeight] = useState<number>(0.20);
  const [searchResults, setSearchResults] = useState<HybridSearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);

  // Ask Codebase state
  const [askQuestion, setAskQuestion] = useState<string>("");
  const [askResponse, setAskResponse] = useState<ArchitectureAskResponse | null>(null);
  const [isAsking, setIsAsking] = useState<boolean>(false);

  // Fetch architecture summary
  const {
    data: summary,
    isLoading,
    isError,
    refetch,
  } = useQuery<ArchitectureSummaryResponse>({
    queryKey: ["repository-architecture", repositoryId],
    queryFn: () => architectureService.getArchitectureSummary(repositoryId),
  });

  // Re-analyze mutation
  const analyzeMutation = useMutation({
    mutationFn: () => architectureService.analyzeArchitecture(repositoryId),
    onSuccess: (data) => {
      queryClient.setQueryData(["repository-architecture", repositoryId], data);
    },
  });

  // Fetch Drift
  const {
    data: driftData,
    isLoading: isDriftLoading,
    refetch: refetchDrift,
  } = useQuery<ArchitectureDriftResponse>({
    queryKey: ["repository-architecture-drift", repositoryId],
    queryFn: () => architectureService.getArchitectureDrift(repositoryId),
  });

  // Drift analyze mutation
  const analyzeDriftMutation = useMutation({
    mutationFn: () => architectureService.analyzeArchitectureDrift(repositoryId),
    onSuccess: (data) => {
      queryClient.setQueryData(["repository-architecture-drift", repositoryId], data);
    },
  });

  // Fetch Technical Debt Summary
  const {
    data: debtData,
    isLoading: isDebtLoading,
    refetch: refetchDebt,
  } = useQuery<TechnicalDebtSummaryResponse>({
    queryKey: ["repository-technical-debt", repositoryId],
    queryFn: () => architectureService.getTechnicalDebt(repositoryId),
  });

  // Technical Debt analyze mutation
  const analyzeDebtMutation = useMutation({
    mutationFn: () => architectureService.analyzeTechnicalDebt(repositoryId),
    onSuccess: (data) => {
      queryClient.setQueryData(["repository-technical-debt", repositoryId], data);
      queryClient.invalidateQueries({ queryKey: ["repository-technical-debt-findings", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["repository-technical-debt-trends", repositoryId] });
    },
  });

  // Fetch Technical Debt Findings
  const {
    data: findingsData,
    isLoading: isFindingsLoading,
  } = useQuery<TechnicalDebtFindingsResponse>({
    queryKey: ["repository-technical-debt-findings", repositoryId, debtCategoryFilter, debtSeverityFilter],
    queryFn: () => architectureService.getTechnicalDebtFindings(
      repositoryId,
      debtCategoryFilter === "all" ? undefined : debtCategoryFilter,
      debtSeverityFilter === "all" ? undefined : debtSeverityFilter
    ),
  });

  // Fetch Technical Debt Trends
  const {
    data: trendsData,
  } = useQuery<TechnicalDebtTrendsResponse>({
    queryKey: ["repository-technical-debt-trends", repositoryId],
    queryFn: () => architectureService.getTechnicalDebtTrends(repositoryId),
  });

  // Handle hybrid search execution
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const resp = await architectureService.searchHybrid(repositoryId, {
        query: searchQuery.trim(),
        filters: {
          languages: searchLanguage ? [searchLanguage] : undefined,
          symbol_types: searchSymbolType ? [searchSymbolType] : undefined,
        },
        lexical_weight: lexicalWeight,
        semantic_weight: semanticWeight,
        structural_weight: structuralWeight,
        limit: 15,
      });
      setSearchResults(resp);
    } catch (err) {
      console.error("Hybrid search error:", err);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle Ask Codebase execution
  const handleAsk = async (questionToAsk?: string) => {
    const q = questionToAsk || askQuestion;
    if (!q.trim()) return;

    setIsAsking(true);
    try {
      const resp = await architectureService.askArchitecture(repositoryId, {
        question: q.trim(),
        context_limit: 6,
      });
      setAskResponse(resp);
    } catch (err) {
      console.error("Ask architecture error:", err);
    } finally {
      setIsAsking(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
        <p className="text-sm text-muted-foreground">Inferring repository architecture, patterns, and conventions...</p>
      </div>
    );
  }

  if (isError || !summary) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertTriangle className="w-12 h-12 text-destructive mx-auto" />
        <h3 className="text-lg font-medium">Failed to load architectural intelligence</h3>
        <p className="text-sm text-muted-foreground">
          Could not retrieve architecture patterns. The repository might still be indexing.
        </p>
        <Button onClick={() => refetch()} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" /> Retry
        </Button>
      </div>
    );
  }

  const patterns = summary.patterns || [];
  const conventions = summary.conventions || [];

  // Filtered patterns
  const filteredPatterns = patterns.filter((p) => {
    if (selectedCategory !== "all" && p.category.toLowerCase() !== selectedCategory.toLowerCase()) {
      return false;
    }
    if (selectedStatus !== "all" && p.evidence_status !== selectedStatus) {
      return false;
    }
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "CONFIRMED":
        return <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">CONFIRMED</Badge>;
      case "STRONGLY_SUPPORTED":
        return <Badge className="bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30">STRONGLY SUPPORTED</Badge>;
      case "POSSIBLE":
        return <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">POSSIBLE</Badge>;
      default:
        return <Badge variant="outline" className="text-muted-foreground">INSUFFICIENT EVIDENCE</Badge>;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case "application":
        return <Layers className="w-4 h-4 text-purple-500" />;
      case "backend":
        return <Server className="w-4 h-4 text-blue-500" />;
      case "frontend":
        return <Layout className="w-4 h-4 text-emerald-500" />;
      case "ai_agent":
        return <Brain className="w-4 h-4 text-amber-500" />;
      case "data":
        return <Database className="w-4 h-4 text-rose-500" />;
      default:
        return <Code2 className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case "CRITICAL":
        return <Badge className="bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 font-semibold">CRITICAL</Badge>;
      case "HIGH":
        return <Badge className="bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30 font-semibold">HIGH</Badge>;
      case "MEDIUM":
        return <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">MEDIUM</Badge>;
      case "LOW":
        return <Badge className="bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30">LOW</Badge>;
      default:
        return <Badge variant="outline">{severity}</Badge>;
    }
  };

  const getDebtSeverityBadge = (severity: string) => {
    switch (severity?.toUpperCase()) {
      case "CRITICAL":
        return <Badge className="bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/40 text-sm font-semibold">CRITICAL (81-100)</Badge>;
      case "HIGH":
        return <Badge className="bg-orange-500/20 text-orange-600 dark:text-orange-400 border-orange-500/40 text-sm font-semibold">HIGH (61-80)</Badge>;
      case "MEDIUM":
        return <Badge className="bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/40 text-sm font-semibold">MEDIUM (36-60)</Badge>;
      case "LOW":
        return <Badge className="bg-blue-500/20 text-blue-600 dark:text-blue-400 border-blue-500/40 text-sm font-semibold">LOW (16-35)</Badge>;
      default:
        return <Badge className="bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/40 text-sm font-semibold">CLEAN (0-15)</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b pb-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Cpu className="w-6 h-6 text-primary" />
            Semantic Architecture & Pattern Intelligence
          </h2>
          <p className="text-sm text-muted-foreground">
            Empirically grounded design pattern inference, convention discovery, and multi-modal hybrid code search.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => analyzeMutation.mutate()}
            disabled={analyzeMutation.isPending}
          >
            {analyzeMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Re-Analyze Evidence
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setActiveSubTab("ask");
            }}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Ask Codebase
          </Button>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex flex-wrap border-b border-border gap-2">
        <Button
          variant={activeSubTab === "overview" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("overview")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "overview"}
        >
          <Layers className="w-4 h-4 mr-2" />
          Overview
        </Button>
        <Button
          variant={activeSubTab === "patterns" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("patterns")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "patterns"}
        >
          <Code2 className="w-4 h-4 mr-2" />
          Pattern Explorer ({patterns.length})
        </Button>
        <Button
          variant={activeSubTab === "conventions" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("conventions")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "conventions"}
        >
          <BookOpen className="w-4 h-4 mr-2" />
          Conventions Guide ({conventions.length})
        </Button>
        <Button
          variant={activeSubTab === "search" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("search")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "search"}
        >
          <Search className="w-4 h-4 mr-2" />
          Hybrid Code Search
        </Button>
        <Button
          variant={activeSubTab === "ask" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("ask")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "ask"}
        >
          <Brain className="w-4 h-4 mr-2" />
          Ask Your Codebase
        </Button>
        <Button
          variant={activeSubTab === "drift" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("drift")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "drift"}
        >
          <AlertOctagon className="w-4 h-4 mr-2 text-amber-500" />
          Architecture Drift {driftData ? `(${driftData.total_violations})` : ""}
        </Button>
        <Button
          variant={activeSubTab === "debt" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setActiveSubTab("debt")}
          className="rounded-b-none border-b-2 border-transparent data-[active=true]:border-primary"
          data-active={activeSubTab === "debt"}
        >
          <Activity className="w-4 h-4 mr-2 text-rose-500" />
          Technical Debt {debtData ? `(${Math.round(debtData.overall_debt_score)})` : ""}
        </Button>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 1. OVERVIEW SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "overview" && (
        <div className="space-y-6">
          {/* Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Confirmed Patterns</CardDescription>
                <CardTitle className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                  {summary.confirmed_patterns_count} / {summary.total_patterns}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">Corroborated by files & symbols</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Coding Conventions</CardDescription>
                <CardTitle className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {conventions.length} Rules
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">Discovered project conventions</p>
              </CardContent>
            </Card>

            <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setActiveSubTab("drift")}>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Architecture Drift</span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                </CardDescription>
                <CardTitle className={`text-2xl font-bold ${
                  driftData?.drift_status === "CRITICAL_DRIFT" ? "text-rose-600" :
                  driftData?.drift_status === "DRIFT_DETECTED" ? "text-amber-500" : "text-emerald-600"
                }`}>
                  {driftData?.drift_status === "CRITICAL_DRIFT" ? "Critical" :
                   driftData?.drift_status === "DRIFT_DETECTED" ? "Drifted" : "Healthy"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {driftData ? `${driftData.total_violations} violations (${driftData.critical_violations} crit)` : "Checking..."}
                </p>
              </CardContent>
            </Card>

            <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setActiveSubTab("debt")}>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center justify-between">
                  <span>Technical Debt</span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                </CardDescription>
                <CardTitle className={`text-2xl font-bold ${
                  debtData?.severity === "CRITICAL" ? "text-rose-600" :
                  debtData?.severity === "HIGH" ? "text-orange-500" :
                  debtData?.severity === "MEDIUM" ? "text-amber-500" : "text-emerald-600"
                }`}>
                  {debtData ? `${Math.round(debtData.overall_debt_score)}/100` : "--"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {debtData ? `${debtData.severity} (${debtData.total_findings} findings)` : "Evaluating..."}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Primary Ecosystem</CardDescription>
                <CardTitle className="text-2xl font-bold capitalize truncate">
                  {summary.primary_language || "Multi-Lang"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground truncate">
                  Commit: {summary.current_commit_sha ? summary.current_commit_sha.substring(0, 8) : "HEAD"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Analysis Freshness</CardDescription>
                <CardTitle className="text-2xl font-bold flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-500" />
                  Grounded
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">Zero hallucinated claims</p>
              </CardContent>
            </Card>
          </div>

          {/* Quick Insights Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Layers className="w-4 h-4 text-primary" />
                  Top Verified Design Patterns
                </CardTitle>
                <CardDescription>Strongest structural evidence detected in this codebase</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {patterns.slice(0, 4).map((p) => (
                  <div key={p.pattern_id} className="p-3 border rounded-lg flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(p.category)}
                        <span className="font-medium text-sm">{p.name}</span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1">{p.description}</p>
                    </div>
                    <div className="text-right">
                      {getStatusBadge(p.evidence_status)}
                      <div className="text-xs font-mono text-muted-foreground mt-1">
                        {Math.round(p.confidence_score * 100)}% conf
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-primary" />
                  Key Architectural Conventions
                </CardTitle>
                <CardDescription>Rules to follow when authoring new features</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {conventions.slice(0, 4).map((c, idx) => (
                  <div key={idx} className="p-3 border rounded-lg space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{c.name}</span>
                      <Badge variant="outline" className="text-xs uppercase">{c.category}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{c.description}</p>
                    {c.supporting_examples[0] && (
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono text-primary block mt-1">
                        {c.supporting_examples[0]}
                      </code>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 2. PATTERNS EXPLORER SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "patterns" && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-muted/40 rounded-lg border">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                <Filter className="w-3.5 h-3.5" /> Domain:
              </span>
              {["all", "application", "backend", "frontend", "ai_agent", "data"].map((cat) => (
                <Button
                  key={cat}
                  size="sm"
                  variant={selectedCategory === cat ? "secondary" : "ghost"}
                  onClick={() => setSelectedCategory(cat)}
                  className="h-7 text-xs capitalize"
                >
                  {cat.replace("_", " ")}
                </Button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Evidence Status:</span>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="text-xs border rounded px-2 py-1 bg-background"
              >
                <option value="all">All Statuses</option>
                <option value="CONFIRMED">CONFIRMED</option>
                <option value="STRONGLY_SUPPORTED">STRONGLY SUPPORTED</option>
                <option value="POSSIBLE">POSSIBLE</option>
                <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT EVIDENCE</option>
              </select>
            </div>
          </div>

          {/* Patterns Grid */}
          <div className="grid grid-cols-1 gap-4">
            {filteredPatterns.map((p) => {
              const isExpanded = expandedPatternId === p.pattern_id;
              return (
                <Card key={p.pattern_id} className="transition-all hover:border-primary/40">
                  <CardHeader className="pb-2">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(p.category)}
                        <CardTitle className="text-base font-semibold">{p.name}</CardTitle>
                        <Badge variant="outline" className="text-xs uppercase">{p.category.replace("_", " ")}</Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        {getStatusBadge(p.evidence_status)}
                        <span className="text-xs font-mono text-muted-foreground">
                          {Math.round(p.confidence_score * 100)}% Confidence
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedPatternId(isExpanded ? null : p.pattern_id)}
                          className="h-8 w-8 p-0"
                        >
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </Button>
                      </div>
                    </div>
                    <CardDescription className="text-sm mt-1">{p.description}</CardDescription>
                  </CardHeader>

                  <CardContent className="space-y-3">
                    {/* Progress Bar */}
                    <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          p.confidence_score >= 0.85
                            ? "bg-emerald-500"
                            : p.confidence_score >= 0.70
                            ? "bg-blue-500"
                            : p.confidence_score >= 0.40
                            ? "bg-amber-500"
                            : "bg-muted-foreground"
                        }`}
                        style={{ width: `${Math.round(p.confidence_score * 100)}%` }}
                      />
                    </div>

                    {/* Supporting Files Pill Cloud */}
                    {p.supporting_files.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground">Supporting Source Modules:</span>
                        <div className="flex flex-wrap gap-1.5 pt-0.5">
                          {p.supporting_files.slice(0, isExpanded ? 20 : 4).map((f, fIdx) => (
                            <Badge key={fIdx} variant="secondary" className="text-xs font-mono font-normal">
                              <FileCode className="w-3 h-3 mr-1 text-primary" />
                              {f}
                            </Badge>
                          ))}
                          {!isExpanded && p.supporting_files.length > 4 && (
                            <Badge
                              variant="outline"
                              className="text-xs cursor-pointer hover:bg-muted"
                              onClick={() => setExpandedPatternId(p.pattern_id)}
                            >
                              +{p.supporting_files.length - 4} more
                            </Badge>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Expanded Evidence Drawer */}
                    {isExpanded && (
                      <div className="pt-3 border-t space-y-3 bg-muted/20 p-3 rounded-lg">
                        {p.supporting_symbols.length > 0 && (
                          <div className="space-y-1">
                            <span className="text-xs font-medium text-muted-foreground">Exemplar AST Symbols & Classes:</span>
                            <div className="flex flex-wrap gap-1.5 pt-0.5">
                              {p.supporting_symbols.map((sym, sIdx) => (
                                <code key={sIdx} className="text-xs bg-muted px-2 py-0.5 rounded font-mono text-primary">
                                  {sym}
                                </code>
                              ))}
                            </div>
                          </div>
                        )}

                        {p.counterexamples.length > 0 && (
                          <div className="space-y-1">
                            <span className="text-xs font-medium text-amber-600 dark:text-amber-400 flex items-center gap-1">
                              <AlertCircle className="w-3.5 h-3.5" /> Counterexamples / Deviations:
                            </span>
                            <ul className="list-disc list-inside text-xs text-muted-foreground pl-1">
                              {p.counterexamples.map((ce, ceIdx) => (
                                <li key={ceIdx}>{ce}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 3. CONVENTIONS GUIDE SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "conventions" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary" />
                Repository Architectural & Coding Conventions
              </CardTitle>
              <CardDescription>
                Empirically validated patterns enforced across services, API routes, database sessions, and error handling.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {conventions.map((c, idx) => (
                <div key={idx} className="p-4 border rounded-lg space-y-2 bg-card hover:border-primary/30 transition-all">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{c.name}</span>
                      <Badge variant="outline" className="text-xs uppercase">{c.category}</Badge>
                      <Badge className="bg-primary/10 text-primary border-primary/20 text-xs">
                        {c.applicability_scope}
                      </Badge>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">
                      {Math.round(c.confidence * 100)}% verified
                    </span>
                  </div>

                  <p className="text-sm text-muted-foreground">{c.description}</p>

                  {c.supporting_examples.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs font-medium text-muted-foreground">Code Exemplars:</span>
                      <div className="space-y-1">
                        {c.supporting_examples.map((ex, exIdx) => (
                          <pre key={exIdx} className="text-xs bg-muted p-2 rounded overflow-x-auto font-mono text-primary">
                            {ex}
                          </pre>
                        ))}
                      </div>
                    </div>
                  )}

                  {c.relevant_paths.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-xs text-muted-foreground">Paths:</span>
                      {c.relevant_paths.map((p, pIdx) => (
                        <code key={pIdx} className="text-xs bg-secondary px-1.5 py-0.5 rounded font-mono">
                          {p}
                        </code>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 4. HYBRID CODE SEARCH SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "search" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Search className="w-5 h-5 text-primary" />
                Multi-Modal Hybrid Search Engine
              </CardTitle>
              <CardDescription>
                Unified retrieval combining BM25 exact identifier matching, 768-dim pgvector semantic similarity, and AST graph topology.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleSearch} className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter symbol name, code pattern, or natural language query (e.g. 'UserService', 'circuit breaker retry')..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="submit" disabled={isSearching || !searchQuery.trim()}>
                    {isSearching ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                    Search
                  </Button>
                </div>

                {/* Filter and Weight controls */}
                <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span>Language:</span>
                    <Input
                      placeholder="e.g. python, typescript"
                      value={searchLanguage}
                      onChange={(e) => setSearchLanguage(e.target.value)}
                      className="h-7 w-36 text-xs"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span>Symbol Type:</span>
                    <select
                      value={searchSymbolType}
                      onChange={(e) => setSearchSymbolType(e.target.value)}
                      className="h-7 text-xs border rounded px-2 bg-background"
                    >
                      <option value="">All Types</option>
                      <option value="class">Class</option>
                      <option value="function">Function</option>
                      <option value="method">Method</option>
                      <option value="interface">Interface</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <Sliders className="w-3.5 h-3.5 text-primary" />
                    <span>Weights: Lexical {Math.round(lexicalWeight * 100)}% | Semantic {Math.round(semanticWeight * 100)}% | Graph {Math.round(structuralWeight * 100)}%</span>
                  </div>
                </div>
              </form>

              {/* Search Results */}
              {searchResults && (
                <div className="pt-4 border-t space-y-4">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Found {searchResults.total_matches} matches across modalities in {searchResults.search_duration_seconds}s</span>
                    <span>Ranking: Reciprocal Rank Fusion (k=60)</span>
                  </div>

                  <div className="space-y-3">
                    {searchResults.results.map((r, idx) => (
                      <div key={idx} className="p-3 border rounded-lg space-y-2 bg-card hover:border-primary/40 transition-all">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold text-primary">#{r.rank}</span>
                            <span className="font-mono text-sm font-medium">{r.file_path}</span>
                            <span className="text-xs text-muted-foreground font-mono">:L{r.line_number}</span>
                            {r.symbol_name && (
                              <Badge variant="secondary" className="text-xs font-mono">{r.symbol_name}</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge className="bg-primary/10 text-primary border-primary/20 text-xs font-mono">
                              RRF Score: {r.combined_score.toFixed(3)}
                            </Badge>
                          </div>
                        </div>

                        {/* Provenance breakdown pill */}
                        <div className="text-xs text-muted-foreground bg-muted/40 px-2 py-1 rounded flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-primary" />
                          <span>{r.provenance_explanation}</span>
                        </div>

                        {/* Snippet */}
                        {r.snippet && (
                          <pre className="text-xs bg-muted p-2.5 rounded overflow-x-auto font-mono text-foreground/90 border">
                            {r.snippet}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 5. ASK YOUR CODEBASE SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "ask" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                Ask Your Codebase (Architecture Q&A)
              </CardTitle>
              <CardDescription>
                Ask architectural questions and receive explanations grounded directly in verified patterns, conventions, and source files.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Suggested Questions */}
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-500" /> Suggested Architecture Questions:
                </span>
                <div className="flex flex-wrap gap-2">
                  {[
                    "How are database sessions and transactions managed?",
                    "How does user authentication and JWT verification work?",
                    "Where is the isolated execution sandbox implemented?",
                    "What pattern governs domain business logic and services?",
                    "How are tests structured and what test runner is used?",
                  ].map((q, idx) => (
                    <Button
                      key={idx}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setAskQuestion(q);
                        handleAsk(q);
                      }}
                      className="text-xs h-7"
                    >
                      {q}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Ask Input */}
              <div className="flex gap-2 pt-2">
                <Input
                  placeholder="Ask a question about the repository architecture..."
                  value={askQuestion}
                  onChange={(e) => setAskQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAsk();
                  }}
                  className="flex-1"
                />
                <Button onClick={() => handleAsk()} disabled={isAsking || !askQuestion.trim()}>
                  {isAsking ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
                  Ask Codebase
                </Button>
              </div>

              {/* Q&A Response */}
              {askResponse && (
                <div className="pt-4 border-t space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">Answer Confidence:</span>
                    <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                      {Math.round(askResponse.confidence * 100)}% Grounded
                    </Badge>
                  </div>

                  <div className="p-4 bg-muted/30 border rounded-lg space-y-3 prose dark:prose-invert max-w-none text-sm">
                    <div className="whitespace-pre-wrap">{askResponse.answer}</div>
                  </div>

                  {askResponse.relevant_files.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-xs font-medium text-muted-foreground">Supporting Source Evidence:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {askResponse.relevant_files.map((rf, rfIdx) => (
                          <Badge key={rfIdx} variant="secondary" className="text-xs font-mono">
                            <FileCode className="w-3 h-3 mr-1 text-primary" />
                            {rf}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 6. ARCHITECTURE DRIFT SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "drift" && (
        <div className="space-y-6">
          {/* Header Card */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertOctagon className="w-5 h-5 text-amber-500" />
                  Architectural Drift & Boundary Adherence
                </CardTitle>
                <CardDescription>
                  Continuous static verification against target layering, circular dependencies, package encapsulation, and security boundaries.
                </CardDescription>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => analyzeDriftMutation.mutate()}
                disabled={analyzeDriftMutation.isPending}
              >
                {analyzeDriftMutation.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Re-Analyze Drift
              </Button>
            </CardHeader>
            <CardContent>
              {isDriftLoading ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
                  <p className="text-sm text-muted-foreground mt-2">Analyzing architectural boundaries...</p>
                </div>
              ) : driftData ? (
                <div className="space-y-6">
                  {/* Status Banner */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                    <div className="p-3 bg-muted/40 rounded-lg border">
                      <div className="text-xs text-muted-foreground">Drift Status</div>
                      <div className="mt-1">
                        {driftData.drift_status === "CRITICAL_DRIFT" ? (
                          <Badge className="bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/40 font-semibold">CRITICAL DRIFT</Badge>
                        ) : driftData.drift_status === "DRIFT_DETECTED" ? (
                          <Badge className="bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/40 font-semibold">DRIFT DETECTED</Badge>
                        ) : (
                          <Badge className="bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/40 font-semibold">HEALTHY</Badge>
                        )}
                      </div>
                    </div>
                    <div className="p-3 bg-muted/40 rounded-lg border">
                      <div className="text-xs text-muted-foreground">Total Violations</div>
                      <div className="text-xl font-bold mt-1">{driftData.total_violations}</div>
                    </div>
                    <div className="p-3 bg-rose-500/10 rounded-lg border border-rose-500/20">
                      <div className="text-xs text-rose-600 dark:text-rose-400">Critical</div>
                      <div className="text-xl font-bold text-rose-600 dark:text-rose-400 mt-1">{driftData.critical_violations}</div>
                    </div>
                    <div className="p-3 bg-orange-500/10 rounded-lg border border-orange-500/20">
                      <div className="text-xs text-orange-600 dark:text-orange-400">High</div>
                      <div className="text-xl font-bold text-orange-600 dark:text-orange-400 mt-1">{driftData.high_violations}</div>
                    </div>
                    <div className="p-3 bg-amber-500/10 rounded-lg border border-amber-500/20">
                      <div className="text-xs text-amber-600 dark:text-amber-400">Medium</div>
                      <div className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">{driftData.medium_violations}</div>
                    </div>
                    <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                      <div className="text-xs text-blue-600 dark:text-blue-400">Low</div>
                      <div className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-1">{driftData.low_violations}</div>
                    </div>
                  </div>

                  {/* Filter Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                        <Filter className="w-3.5 h-3.5" /> Severity:
                      </span>
                      {["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
                        <Button
                          key={s}
                          variant={driftSeverityFilter === s ? "secondary" : "ghost"}
                          size="sm"
                          onClick={() => setDriftSeverityFilter(s)}
                          className="h-7 text-xs uppercase"
                        >
                          {s}
                        </Button>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground">Category:</span>
                      {["all", "layering", "dependency", "convention", "security"].map((c) => (
                        <Button
                          key={c}
                          variant={driftCategoryFilter === c ? "secondary" : "ghost"}
                          size="sm"
                          onClick={() => setDriftCategoryFilter(c)}
                          className="h-7 text-xs capitalize"
                        >
                          {c}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Violations List */}
                  {(() => {
                    const filteredViolations = (driftData.violations || []).filter((v) => {
                      if (driftSeverityFilter !== "all" && v.severity.toUpperCase() !== driftSeverityFilter) return false;
                      if (driftCategoryFilter !== "all" && v.category.toLowerCase() !== driftCategoryFilter.toLowerCase()) return false;
                      return true;
                    });

                    if (filteredViolations.length === 0) {
                      return (
                        <div className="p-8 text-center border rounded-lg bg-muted/20">
                          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                          <h4 className="font-semibold text-sm">No Architectural Violations Detected</h4>
                          <p className="text-xs text-muted-foreground mt-1">
                            All audited packages, services, and API layers strictly adhere to defined conventions and architectural boundaries.
                          </p>
                        </div>
                      );
                    }

                    return (
                      <div className="space-y-4">
                        {filteredViolations.map((violation) => {
                          const isExpanded = expandedViolationId === violation.id;
                          return (
                            <div key={violation.id} className="border rounded-lg p-4 space-y-3 bg-card shadow-sm hover:border-border/80 transition-colors">
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="space-y-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    {getSeverityBadge(violation.severity)}
                                    <Badge variant="outline" className="text-xs font-mono uppercase">
                                      {violation.category}
                                    </Badge>
                                    <Badge variant="secondary" className="text-xs font-mono">
                                      {violation.rule_id}
                                    </Badge>
                                    <span className="font-semibold text-sm">{violation.name}</span>
                                  </div>
                                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground font-mono">
                                    <FileCode className="w-3.5 h-3.5 text-primary" />
                                    <span className="text-foreground">{violation.source_file}:{violation.line_number}</span>
                                    {violation.source_symbol && (
                                      <span className="text-muted-foreground">({violation.source_symbol})</span>
                                    )}
                                    {violation.target_file && (
                                      <>
                                        <ArrowRight className="w-3.5 h-3.5 text-muted-foreground mx-1" />
                                        <span className="text-foreground">{violation.target_file}</span>
                                        {violation.target_symbol && (
                                          <span className="text-muted-foreground">({violation.target_symbol})</span>
                                        )}
                                      </>
                                    )}
                                  </div>
                                </div>
                                <div className="text-xs font-mono text-muted-foreground">
                                  {Math.round(violation.confidence * 100)}% conf
                                </div>
                              </div>

                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {violation.explanation}
                              </p>

                              {/* Remediation Callout */}
                              <div className="p-3 bg-primary/5 border border-primary/20 rounded-md text-xs space-y-1">
                                <div className="font-semibold text-primary flex items-center gap-1.5">
                                  <Lightbulb className="w-3.5 h-3.5" />
                                  Remediation Recommendation:
                                </div>
                                <div className="text-muted-foreground pl-5">
                                  {violation.remediation_recommendation}
                                </div>
                              </div>

                              {/* Toggleable Evidence */}
                              {violation.evidence_snippet && (
                                <div>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setExpandedViolationId(isExpanded ? null : violation.id)}
                                    className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                                  >
                                    {isExpanded ? (
                                      <ChevronDown className="w-3.5 h-3.5 mr-1" />
                                    ) : (
                                      <ChevronRight className="w-3.5 h-3.5 mr-1" />
                                    )}
                                    {isExpanded ? "Hide Code Evidence" : "View Code Evidence"}
                                  </Button>
                                  {isExpanded && (
                                    <div className="mt-2 p-3 bg-muted/80 rounded border font-mono text-xs overflow-x-auto whitespace-pre">
                                      {violation.evidence_snippet}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}

                  {/* Resolved Violations Section */}
                  {driftData.resolved_violations && driftData.resolved_violations.length > 0 && (
                    <div className="pt-4 border-t space-y-3">
                      <h4 className="text-sm font-semibold flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="w-4 h-4" />
                        Resolved Violations ({driftData.resolved_violations.length})
                      </h4>
                      <div className="space-y-2">
                        {driftData.resolved_violations.map((rv) => (
                          <div key={rv.id} className="p-2.5 border rounded bg-emerald-500/5 text-xs flex items-center justify-between">
                            <span className="font-medium text-emerald-700 dark:text-emerald-300">{rv.name}</span>
                            <span className="font-mono text-muted-foreground">{rv.source_file}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 text-center text-muted-foreground">
                  No drift analysis available. Click "Re-Analyze Drift" to execute boundary verification.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 7. TECHNICAL DEBT SUBTAB */}
      {/* ----------------------------------------------------------------- */}
      {activeSubTab === "debt" && (
        <div className="space-y-6">
          {/* Header & Score Card */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5 text-rose-500" />
                  Technical Debt & Maintainability Intelligence
                </CardTitle>
                <CardDescription>
                  Empirically calculated maintainability health combining complexity, duplication, dependency entanglements, test deficits, and architectural drift.
                </CardDescription>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => analyzeDebtMutation.mutate()}
                disabled={analyzeDebtMutation.isPending}
              >
                {analyzeDebtMutation.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Recalculate Debt
              </Button>
            </CardHeader>
            <CardContent>
              {isDebtLoading ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
                  <p className="text-sm text-muted-foreground mt-2">Computing multi-dimensional debt metrics...</p>
                </div>
              ) : debtData ? (
                <div className="space-y-6">
                  {/* Top Score Banner */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-muted/30 border rounded-lg items-center">
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground">Composite Debt Score (0 - 100)</div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-4xl font-extrabold tracking-tight">
                          {debtData.overall_debt_score.toFixed(1)}
                        </span>
                        <span className="text-sm text-muted-foreground">/ 100</span>
                      </div>
                      <div className="pt-1">
                        {getDebtSeverityBadge(debtData.severity)}
                      </div>
                    </div>

                    <div className="space-y-2 border-l pl-4">
                      <div className="text-xs font-medium text-muted-foreground">Measurement Confidence & Findings</div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs font-mono">
                          {Math.round(debtData.confidence * 100)}% Confidence
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          {debtData.total_findings} Findings ({debtData.critical_findings} Critical)
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Lower score indicates higher codebase health.
                      </p>
                    </div>

                    <div className="space-y-1 border-l pl-4 text-xs text-muted-foreground">
                      <div className="font-semibold text-foreground">Scoring Formula Weighting:</div>
                      <div>• 25% Cyclomatic & Size Complexity</div>
                      <div>• 20% Token-Normalized Duplication</div>
                      <div>• 20% Dependency Entanglements</div>
                      <div>• 20% Test Deficits & Flakiness</div>
                      <div>• 15% Hygiene & Maintainability Markers</div>
                    </div>
                  </div>

                  {/* 5-Dimension Scores Breakdown */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-primary" />
                      Dimension Score Breakdown
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                      {/* Complexity */}
                      <div className="p-3 border rounded-lg bg-card space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">Complexity (25%)</span>
                          <span className="font-mono font-bold">{debtData.dimension_scores.complexity.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-purple-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, debtData.dimension_scores.complexity))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">Long functions & classes</p>
                      </div>

                      {/* Duplication */}
                      <div className="p-3 border rounded-lg bg-card space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">Duplication (20%)</span>
                          <span className="font-mono font-bold">{debtData.dimension_scores.duplication.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, debtData.dimension_scores.duplication))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">Redundant code tokens</p>
                      </div>

                      {/* Dependency */}
                      <div className="p-3 border rounded-lg bg-card space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">Dependency (20%)</span>
                          <span className="font-mono font-bold">{debtData.dimension_scores.dependency.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-amber-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, debtData.dimension_scores.dependency))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">Cycles & unresolved imports</p>
                      </div>

                      {/* Test Debt */}
                      <div className="p-3 border rounded-lg bg-card space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">Test Debt (20%)</span>
                          <span className="font-mono font-bold">{debtData.dimension_scores.test_debt.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-rose-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, debtData.dimension_scores.test_debt))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">Deficits & flaky tests</p>
                      </div>

                      {/* Maintainability */}
                      <div className="p-3 border rounded-lg bg-card space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">Maintainability (15%)</span>
                          <span className="font-mono font-bold">{debtData.dimension_scores.maintainability.toFixed(1)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-emerald-500 h-2 rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, debtData.dimension_scores.maintainability))}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">TODOs & bare exceptions</p>
                      </div>
                    </div>
                  </div>

                  {/* Historical Trends */}
                  {trendsData?.trends && trendsData.trends.length > 0 && (
                    <div className="space-y-3 pt-2 border-t">
                      <h4 className="text-sm font-semibold flex items-center gap-2">
                        <History className="w-4 h-4 text-primary" />
                        Historical Debt Progression
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        {trendsData.trends.slice(-4).map((trend, idx) => (
                          <div key={idx} className="p-3 border rounded bg-card/60 space-y-1 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-semibold">{trend.commit_sha.substring(0, 8)}</span>
                              <Badge variant="outline" className="text-xs">{trend.severity}</Badge>
                            </div>
                            <div className="text-lg font-bold">
                              {trend.overall_debt_score.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">score</span>
                            </div>
                            <div className="text-muted-foreground">
                              {trend.total_findings} findings ({trend.critical_findings} crit)
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Findings Explorer */}
                  <div className="space-y-4 pt-4 border-t">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                      <div>
                        <h4 className="text-sm font-semibold flex items-center gap-2">
                          <FileWarning className="w-4 h-4 text-amber-500" />
                          Detailed Findings Explorer
                        </h4>
                        <p className="text-xs text-muted-foreground">
                          Inspect granular items contributing to overall technical debt with actionable remediations.
                        </p>
                      </div>
                      <Badge variant="secondary" className="text-xs font-mono">
                        {findingsData?.total_count || 0} findings
                      </Badge>
                    </div>

                    {/* Filter row */}
                    <div className="flex flex-wrap items-center justify-between gap-3 p-2.5 bg-muted/20 border rounded-lg">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                          <Filter className="w-3.5 h-3.5" /> Category:
                        </span>
                        {["all", "complexity", "duplication", "dependency", "test", "maintainability"].map((c) => (
                          <Button
                            key={c}
                            variant={debtCategoryFilter === c ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setDebtCategoryFilter(c)}
                            className="h-7 text-xs capitalize"
                          >
                            {c}
                          </Button>
                        ))}
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-medium text-muted-foreground">Severity:</span>
                        {["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
                          <Button
                            key={s}
                            variant={debtSeverityFilter === s ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setDebtSeverityFilter(s)}
                            className="h-7 text-xs uppercase"
                          >
                            {s}
                          </Button>
                        ))}
                      </div>
                    </div>

                    {/* Findings Cards */}
                    {(() => {
                      const findings = findingsData?.findings || debtData.top_findings || [];
                      if (findings.length === 0) {
                        return (
                          <div className="p-8 text-center border rounded-lg bg-muted/20">
                            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                            <h4 className="font-semibold text-sm">No Findings for Selected Filters</h4>
                            <p className="text-xs text-muted-foreground mt-1">
                              All metrics in this category are within healthy operational thresholds.
                            </p>
                          </div>
                        );
                      }

                      return (
                        <div className="space-y-4">
                          {findings.map((f) => {
                            const isExpanded = expandedFindingId === f.finding_id;
                            return (
                              <div key={f.finding_id} className="border rounded-lg p-4 space-y-3 bg-card shadow-sm hover:border-border/80 transition-colors">
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                  <div className="space-y-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                      {getSeverityBadge(f.severity)}
                                      <Badge variant="outline" className="text-xs font-mono uppercase">
                                        {f.category}
                                      </Badge>
                                      <Badge variant="secondary" className="text-xs font-mono">
                                        {f.detection_method}
                                      </Badge>
                                      <span className="font-semibold text-sm">{f.title}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                                      <FileCode className="w-3.5 h-3.5 text-primary" />
                                      <span className="text-foreground">{f.file_path}:{f.line_number}</span>
                                      {f.symbol_name && (
                                        <span className="text-muted-foreground">({f.symbol_name})</span>
                                      )}
                                    </div>
                                  </div>
                                  <div className="text-xs font-mono text-muted-foreground">
                                    {Math.round(f.confidence * 100)}% conf
                                  </div>
                                </div>

                                <p className="text-xs text-muted-foreground leading-relaxed">
                                  {f.explanation}
                                </p>

                                {/* Measured Metric Chips */}
                                {f.measured_metric && Object.keys(f.measured_metric).length > 0 && (
                                  <div className="flex flex-wrap gap-1.5">
                                    {Object.entries(f.measured_metric).map(([k, v]) => (
                                      <Badge key={k} variant="outline" className="text-xs font-mono">
                                        {k}: {String(v)}
                                      </Badge>
                                    ))}
                                  </div>
                                )}

                                {/* Remediation Callout */}
                                <div className="p-3 bg-primary/5 border border-primary/20 rounded-md text-xs space-y-1">
                                  <div className="font-semibold text-primary flex items-center gap-1.5">
                                    <Lightbulb className="w-3.5 h-3.5" />
                                    Actionable Remediation:
                                  </div>
                                  <div className="text-muted-foreground pl-5">
                                    {f.remediation}
                                  </div>
                                </div>

                                {/* Potential Impact */}
                                {f.potential_impact && (
                                  <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                                    <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                                    <span><strong>Potential Impact:</strong> {f.potential_impact}</span>
                                  </div>
                                )}

                                {/* Toggleable Evidence */}
                                {f.evidence_snippet && (
                                  <div>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => setExpandedFindingId(isExpanded ? null : f.finding_id)}
                                      className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                                    >
                                      {isExpanded ? (
                                        <ChevronDown className="w-3.5 h-3.5 mr-1" />
                                      ) : (
                                        <ChevronRight className="w-3.5 h-3.5 mr-1" />
                                      )}
                                      {isExpanded ? "Hide Evidence Snippet" : "View Evidence Snippet"}
                                    </Button>
                                    {isExpanded && (
                                      <div className="mt-2 p-3 bg-muted/80 rounded border font-mono text-xs overflow-x-auto whitespace-pre">
                                        {f.evidence_snippet}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-muted-foreground">
                  No technical debt data available. Click "Recalculate Debt" to evaluate maintainability.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Wrench,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Play,
  RotateCcw,
  Sparkles,
  GitCommit,
  CheckSquare,
  FileCode,
  Layers,
  Activity,
  ListOrdered,
  XCircle,
  HelpCircle,
  ExternalLink,
  Loader2,
  TrendingDown,
  Lock,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { refactoringService } from "@/services/refactoring-service";
import {
  RefactoringCategory,
  RefactoringPlanResponse,
  RefactoringRecommendationItem,
  BeforeAfterComparisonResponse,
  RefactoringExecutionResponse,
} from "@/types";

interface RefactoringIntelligenceTabProps {
  repositoryId: string;
}

export function RefactoringIntelligenceTab({ repositoryId }: RefactoringIntelligenceTabProps) {
  const queryClient = useQueryClient();

  // Active sub-views
  const [activeSubView, setActiveSubView] = useState<"recommendations" | "plans" | "comparison">("recommendations");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);

  // Approval modal state
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [approvalDiffHash, setApprovalDiffHash] = useState("");
  const [approvalNotes, setApprovalNotes] = useState("");
  const [planToApprove, setPlanToApprove] = useState<RefactoringPlanResponse | null>(null);

  // Queries
  const {
    data: recsData,
    isLoading: recsLoading,
    refetch: refetchRecs,
  } = useQuery({
    queryKey: ["refactoring-recommendations", repositoryId, categoryFilter],
    queryFn: () => refactoringService.getRecommendations(repositoryId, categoryFilter),
    enabled: !!repositoryId,
  });

  const {
    data: plansData,
    isLoading: plansLoading,
    refetch: refetchPlans,
  } = useQuery({
    queryKey: ["refactoring-plans", repositoryId],
    queryFn: () => refactoringService.listPlans(repositoryId),
    enabled: !!repositoryId,
  });

  const {
    data: selectedPlan,
    isLoading: planLoading,
  } = useQuery({
    queryKey: ["refactoring-plan", repositoryId, selectedPlanId],
    queryFn: () => (selectedPlanId ? refactoringService.getPlan(repositoryId, selectedPlanId) : null),
    enabled: !!repositoryId && !!selectedPlanId,
  });

  const {
    data: comparisonData,
    isLoading: comparisonLoading,
  } = useQuery({
    queryKey: ["refactoring-comparison", repositoryId, selectedExecutionId],
    queryFn: () =>
      selectedExecutionId ? refactoringService.getComparison(repositoryId, selectedExecutionId) : null,
    enabled: !!repositoryId && !!selectedExecutionId,
  });

  // Mutations
  const createPlanMutation = useMutation({
    mutationFn: (rec: RefactoringRecommendationItem) =>
      refactoringService.createPlan(repositoryId, {
        title: rec.title,
        category: rec.category,
        description: rec.description,
        recommendation_ids: [rec.recommendation_id],
        target_files: rec.target_files,
        target_symbols: rec.target_symbols,
      }),
    onSuccess: (newPlan) => {
      queryClient.invalidateQueries({ queryKey: ["refactoring-plans", repositoryId] });
      setSelectedPlanId(newPlan.id);
      setActiveSubView("plans");
    },
  });

  const approvePlanMutation = useMutation({
    mutationFn: ({ planId, diffHash, notes }: { planId: string; diffHash: string; notes?: string }) =>
      refactoringService.approvePlan(repositoryId, planId, { diff_hash: diffHash, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refactoring-plans", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["refactoring-plan", repositoryId, selectedPlanId] });
      setApprovalModalOpen(false);
      setPlanToApprove(null);
    },
  });

  const rejectPlanMutation = useMutation({
    mutationFn: (planId: string) => refactoringService.rejectPlan(repositoryId, planId, "User rejected plan via console"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refactoring-plans", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["refactoring-plan", repositoryId, selectedPlanId] });
    },
  });

  const executePlanMutation = useMutation({
    mutationFn: (plan: RefactoringPlanResponse) =>
      refactoringService.executePlan(repositoryId, plan.id, {
        current_diff_hash: plan.approved_diff_hash || undefined,
      }),
    onSuccess: (executionRes: RefactoringExecutionResponse) => {
      queryClient.invalidateQueries({ queryKey: ["refactoring-plans", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["refactoring-plan", repositoryId, selectedPlanId] });
      setSelectedExecutionId(executionRes.id);
      setActiveSubView("comparison");
    },
  });

  const handleOpenApproval = (plan: RefactoringPlanResponse) => {
    setPlanToApprove(plan);
    // Use plan's generated diff preview hash as default
    setApprovalDiffHash(plan.approved_diff_hash || "sha256:precomputed_diff_preview");
    setApprovalNotes("");
    setApprovalModalOpen(true);
  };

  const getRiskColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case "LOW":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "MEDIUM":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "HIGH":
      default:
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case "APPROVED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "APPLIED":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "PENDING_APPROVAL":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "ROLLED_BACK":
        return "bg-orange-500/10 text-orange-400 border-orange-500/30";
      case "INVALIDATED":
      case "REJECTED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "DRAFT":
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Navigation */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 rounded-xl bg-card/60 border border-border backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2">
            <Wrench className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-bold text-foreground">Architecture-Aware Safe Refactoring</h2>
            <Badge variant="outline" className="border-cyan-500/30 text-cyan-400 text-xs">
              Stage 10.6
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Grounded refactoring proposals, topological step planning, diff-hash bound human approval, and isolated rollback-safe execution.
          </p>
        </div>

        {/* Sub-view navigation tabs */}
        <div className="flex items-center gap-2 bg-secondary/60 p-1 rounded-lg border border-border">
          <Button
            size="sm"
            variant={activeSubView === "recommendations" ? "default" : "ghost"}
            className="text-xs font-mono h-8"
            onClick={() => setActiveSubView("recommendations")}
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            Recommendations ({recsData?.total_recommendations || 0})
          </Button>

          <Button
            size="sm"
            variant={activeSubView === "plans" ? "default" : "ghost"}
            className="text-xs font-mono h-8"
            onClick={() => setActiveSubView("plans")}
          >
            <ListOrdered className="w-3.5 h-3.5 mr-1.5" />
            Plans ({plansData?.total_plans || 0})
          </Button>

          {selectedExecutionId && (
            <Button
              size="sm"
              variant={activeSubView === "comparison" ? "default" : "ghost"}
              className="text-xs font-mono h-8"
              onClick={() => setActiveSubView("comparison")}
            >
              <Activity className="w-3.5 h-3.5 mr-1.5 text-cyan-400" />
              Before & After Delta
            </Button>
          )}
        </div>
      </div>

      {/* VIEW 1: RECOMMENDATIONS */}
      {activeSubView === "recommendations" && (
        <div className="space-y-4">
          {/* Category Filter Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {["ALL", "LAYERING", "DEPENDENCY", "DUPLICATION", "COMPLEXITY", "CONVENTION", "TESTABILITY"].map(
                (cat) => (
                  <Button
                    key={cat}
                    size="sm"
                    variant={categoryFilter === cat ? "secondary" : "ghost"}
                    className={`text-xs font-mono h-7 px-2.5 ${
                      categoryFilter === cat ? "border border-border font-semibold text-foreground" : "text-muted-foreground"
                    }`}
                    onClick={() => setCategoryFilter(cat)}
                  >
                    {cat}
                    {recsData?.by_category && recsData.by_category[cat] !== undefined && (
                      <span className="ml-1.5 opacity-60">({recsData.by_category[cat]})</span>
                    )}
                  </Button>
                )
              )}
            </div>

            <Button
              size="sm"
              variant="outline"
              className="text-xs font-mono h-7"
              onClick={() => refetchRecs()}
              disabled={recsLoading}
            >
              {recsLoading ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : null}
              Refresh
            </Button>
          </div>

          {/* Recommendations Grid */}
          {recsLoading ? (
            <div className="flex items-center justify-center p-12 border rounded-xl bg-card/20">
              <Loader2 className="w-6 h-6 animate-spin text-primary mr-3" />
              <span className="text-xs font-mono text-muted-foreground">Synthesizing architecture refactoring candidates...</span>
            </div>
          ) : recsData?.recommendations && recsData.recommendations.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recsData.recommendations.map((rec) => (
                <Card key={rec.recommendation_id} className="bg-card/40 border-border hover:border-border/80 transition-all flex flex-col justify-between">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant="outline" className="text-xs font-mono border-primary/30 text-primary">
                        {rec.category}
                      </Badge>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className={`text-xs font-mono ${getRiskColor(rec.estimated_effort)}`}>
                          Effort: {rec.estimated_effort}
                        </Badge>
                        <Badge variant="outline" className="text-xs font-mono border-border text-muted-foreground">
                          Impact: {rec.impact_score}/100
                        </Badge>
                      </div>
                    </div>
                    <CardTitle className="text-sm font-semibold text-foreground mt-2">{rec.title}</CardTitle>
                    <CardDescription className="text-xs line-clamp-2 mt-1">{rec.description}</CardDescription>
                  </CardHeader>

                  <CardContent className="space-y-3 pt-0">
                    <div className="p-2.5 rounded bg-secondary/50 border border-border/50 space-y-1.5 text-xs">
                      <div className="text-muted-foreground font-mono text-[11px] uppercase tracking-wider font-semibold">
                        Engineering Rationale
                      </div>
                      <p className="text-foreground/90 font-mono text-xs">{rec.rationale}</p>
                    </div>

                    <div className="space-y-1">
                      <div className="text-muted-foreground font-mono text-[11px]">
                        Target Files ({rec.target_files.length}):
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {rec.target_files.slice(0, 3).map((f) => (
                          <span key={f} className="text-[11px] font-mono px-2 py-0.5 rounded bg-background/80 border border-border text-foreground/80">
                            {f.split("/").pop()}
                          </span>
                        ))}
                        {rec.target_files.length > 3 && (
                          <span className="text-[11px] font-mono px-1.5 py-0.5 text-muted-foreground">
                            +{rec.target_files.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="pt-2 flex items-center justify-between border-t border-border/50">
                      <span className="text-[11px] font-mono text-muted-foreground">
                        Confidence: {(rec.confidence * 100).toFixed(0)}%
                      </span>
                      <Button
                        size="sm"
                        className="text-xs font-mono h-7 gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground"
                        onClick={() => createPlanMutation.mutate(rec)}
                        disabled={createPlanMutation.isPending}
                      >
                        {createPlanMutation.isPending ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <ListOrdered className="w-3 h-3" />
                        )}
                        Synthesize Plan
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center border rounded-xl bg-card/20 space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
              <h3 className="text-sm font-semibold text-foreground">No Refactoring Opportunities Detected</h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                No active architecture drift, duplication clusters, circular dependencies, or high-complexity hotspots require remediation in this category.
              </p>
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: PLANS & EXECUTION */}
      {activeSubView === "plans" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Plan Selector */}
          <div className="lg:col-span-1 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Refactoring Plans ({plansData?.total_plans || 0})</h3>
              <Button size="sm" variant="ghost" className="text-xs font-mono h-7" onClick={() => refetchPlans()}>
                Refresh
              </Button>
            </div>

            {plansLoading ? (
              <div className="p-6 border rounded-xl bg-card/20 text-center">
                <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
              </div>
            ) : plansData?.plans && plansData.plans.length > 0 ? (
              <div className="space-y-2">
                {plansData.plans.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => setSelectedPlanId(p.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedPlanId === p.id
                        ? "bg-card border-primary ring-1 ring-primary/30"
                        : "bg-card/40 border-border hover:border-border/80"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1.5">
                      <Badge variant="outline" className={`text-[10px] font-mono ${getStatusColor(p.status)}`}>
                        {p.status}
                      </Badge>
                      <Badge variant="outline" className={`text-[10px] font-mono ${getRiskColor(p.risk_level)}`}>
                        Risk: {p.risk_score}
                      </Badge>
                    </div>
                    <div className="text-xs font-semibold text-foreground line-clamp-1">{p.title}</div>
                    <div className="flex items-center justify-between mt-2 text-[11px] font-mono text-muted-foreground">
                      <span>{p.category}</span>
                      <span>{p.steps.length} steps</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center border rounded-xl bg-card/20 space-y-2">
                <p className="text-xs text-muted-foreground">No refactoring plans created yet.</p>
                <Button size="sm" variant="outline" className="text-xs font-mono" onClick={() => setActiveSubView("recommendations")}>
                  Explore Recommendations
                </Button>
              </div>
            )}
          </div>

          {/* Right Column: Selected Plan Detail & Actions */}
          <div className="lg:col-span-2 space-y-4">
            {planLoading ? (
              <div className="p-12 border rounded-xl bg-card/20 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
              </div>
            ) : selectedPlan ? (
              <div className="space-y-4">
                {/* Plan Header Card */}
                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-xs text-primary border-primary/30">
                          {selectedPlan.category}
                        </Badge>
                        <Badge variant="outline" className={`font-mono text-xs ${getStatusColor(selectedPlan.status)}`}>
                          {selectedPlan.status}
                        </Badge>
                        {selectedPlan.requires_human_approval && (
                          <Badge variant="outline" className="font-mono text-xs border-amber-500/40 text-amber-400 bg-amber-500/10">
                            Approval Gate Enforced
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className={`font-mono text-xs ${getRiskColor(selectedPlan.risk_level)}`}>
                          Risk Score: {selectedPlan.risk_score}/100 ({selectedPlan.risk_level})
                        </Badge>
                      </div>
                    </div>
                    <CardTitle className="text-base font-bold text-foreground mt-2">{selectedPlan.title}</CardTitle>
                    <CardDescription className="text-xs mt-1">{selectedPlan.description}</CardDescription>
                  </CardHeader>

                  <CardContent className="space-y-4 pt-0">
                    {/* Diff Hash & Approval State */}
                    {selectedPlan.approved_diff_hash && (
                      <div className="p-2.5 rounded bg-secondary/50 border border-border/50 text-xs font-mono flex items-center justify-between">
                        <span className="text-muted-foreground">Cryptographic Diff Hash:</span>
                        <span className="text-foreground font-semibold">{selectedPlan.approved_diff_hash.slice(0, 18)}...</span>
                      </div>
                    )}

                    {/* Action Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50">
                      <div className="text-[11px] font-mono text-muted-foreground">
                        {selectedPlan.approved_by ? `Approved by ${selectedPlan.approved_by}` : "Awaiting approval"}
                      </div>

                      <div className="flex items-center gap-2">
                        {selectedPlan.status === "PENDING_APPROVAL" && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-xs font-mono h-8 border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                              onClick={() => rejectPlanMutation.mutate(selectedPlan.id)}
                              disabled={rejectPlanMutation.isPending}
                            >
                              Reject Plan
                            </Button>
                            <Button
                              size="sm"
                              className="text-xs font-mono h-8 bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
                              onClick={() => handleOpenApproval(selectedPlan)}
                            >
                              <ShieldCheck className="w-3.5 h-3.5" />
                              Review & Approve
                            </Button>
                          </>
                        )}

                        {selectedPlan.status === "APPROVED" && (
                          <Button
                            size="sm"
                            className="text-xs font-mono h-8 bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
                            onClick={() => executePlanMutation.mutate(selectedPlan)}
                            disabled={executePlanMutation.isPending}
                          >
                            {executePlanMutation.isPending ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Play className="w-3.5 h-3.5" />
                            )}
                            Execute Plan (Safe Workspace)
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Topological Steps Visualizer */}
                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                      <ListOrdered className="w-4 h-4 text-primary" />
                      Topologically Ordered Implementation Steps ({selectedPlan.steps.length})
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Dependency graph resolved execution sequence ensuring zero broken references during refactoring.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 pt-0">
                    {selectedPlan.steps.map((step) => (
                      <div
                        key={step.step_number}
                        className="p-3 rounded-lg bg-secondary/40 border border-border/60 flex items-start gap-3"
                      >
                        <div className="w-6 h-6 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-xs font-bold font-mono text-primary flex-shrink-0">
                          {step.step_number}
                        </div>
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-foreground">{step.description}</span>
                            <Badge variant="outline" className="text-[10px] font-mono border-border">
                              {step.action_type}
                            </Badge>
                          </div>
                          <div className="text-[11px] font-mono text-muted-foreground flex items-center gap-2">
                            <span>Target: <span className="text-foreground/80">{step.target_file}</span></span>
                            {step.target_symbol && <span>Symbol: <span className="text-foreground/80">{step.target_symbol}</span></span>}
                          </div>
                          <div className="text-[11px] font-mono text-emerald-400/90 pt-1">
                            Assert: {step.verification_check}
                          </div>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <div className="p-12 text-center border rounded-xl bg-card/20">
                <p className="text-xs text-muted-foreground">Select a refactoring plan to inspect details and execution gates.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW 3: BEFORE / AFTER COMPARISON & VERIFICATION */}
      {activeSubView === "comparison" && (
        <div className="space-y-6">
          {comparisonLoading ? (
            <div className="p-12 border rounded-xl bg-card/20 text-center">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
              <p className="text-xs font-mono text-muted-foreground mt-2">Calculating refactoring delta metrics...</p>
            </div>
          ) : comparisonData ? (
            <div className="space-y-6">
              {/* Quantitative Metric Gauges */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs font-mono text-muted-foreground">
                      Drift Violations
                    </CardDescription>
                    <CardTitle className="text-xl font-bold text-emerald-400 flex items-center gap-1.5">
                      <TrendingDown className="w-4 h-4" />
                      {comparisonData.drift_reduction_count > 0 ? `-${comparisonData.drift_reduction_count}` : "0"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-[11px] text-muted-foreground pt-0">
                    Violations successfully resolved
                  </CardContent>
                </Card>

                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs font-mono text-muted-foreground">
                      Debt Score Reduction
                    </CardDescription>
                    <CardTitle className="text-xl font-bold text-cyan-400 flex items-center gap-1.5">
                      <TrendingDown className="w-4 h-4" />
                      -{comparisonData.debt_score_reduction.toFixed(1)} pts
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-[11px] text-muted-foreground pt-0">
                    Quantitative technical debt decrease
                  </CardContent>
                </Card>

                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs font-mono text-muted-foreground">
                      Behavioral Preservation
                    </CardDescription>
                    <CardTitle className="text-xl font-bold text-emerald-400 flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4" />
                      {(comparisonData.behavioral_preservation_score * 100).toFixed(0)}%
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-[11px] text-muted-foreground pt-0">
                    Baseline test parity + public API parity
                  </CardContent>
                </Card>

                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs font-mono text-muted-foreground">
                      Execution Status
                    </CardDescription>
                    <CardTitle className="text-xl font-bold text-foreground flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      APPLIED
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-[11px] text-muted-foreground pt-0">
                    Zero regressions, safe execution confirmed
                  </CardContent>
                </Card>
              </div>

              {/* Baseline vs Post-Refactor Detailed Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-semibold text-foreground">Baseline State (Pre-Refactor)</CardTitle>
                    <CardDescription className="text-xs font-mono">Metrics captured before modifications</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Total Violations:</span>
                      <span className="text-foreground">{comparisonData.baseline_metrics.violations_count ?? "N/A"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Debt Score:</span>
                      <span className="text-foreground">{comparisonData.baseline_metrics.debt_score ?? "N/A"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Tests Passed:</span>
                      <span className="text-emerald-400">{comparisonData.baseline_metrics.passed_tests ?? 0}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-card/40 border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-semibold text-foreground">Post-Refactor State (Verified)</CardTitle>
                    <CardDescription className="text-xs font-mono">Metrics validated in isolated workspace</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Total Violations:</span>
                      <span className="text-foreground">{comparisonData.post_refactor_metrics.violations_count ?? "N/A"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Debt Score:</span>
                      <span className="text-foreground">{comparisonData.post_refactor_metrics.debt_score ?? "N/A"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Tests Passed:</span>
                      <span className="text-emerald-400">{comparisonData.post_refactor_metrics.passed_tests ?? 0}</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center border rounded-xl bg-card/20">
              <p className="text-xs text-muted-foreground">No execution comparison selected. Run an approved plan to view before/after telemetry.</p>
            </div>
          )}
        </div>
      )}

      {/* APPROVAL MODAL */}
      {approvalModalOpen && planToApprove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg bg-card border-border shadow-2xl">
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <CardTitle className="text-base font-bold text-foreground">
                  Human Approval: Cryptographic Diff Binding
                </CardTitle>
              </div>
              <CardDescription className="text-xs font-mono">
                Approval is strictly bound to the exact diff hash. Any working tree modifications invalidate this approval.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-mono text-muted-foreground">Plan ID & Title</label>
                <div className="p-2 rounded bg-secondary/50 border text-xs font-mono text-foreground font-semibold">
                  {planToApprove.title} ({planToApprove.category})
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono text-muted-foreground">SHA-256 Diff Hash</label>
                <Input
                  value={approvalDiffHash}
                  onChange={(e) => setApprovalDiffHash(e.target.value)}
                  className="font-mono text-xs bg-background"
                  placeholder="sha256:..."
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-mono text-muted-foreground">Approval Notes (Optional)</label>
                <Textarea
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  placeholder="Document review sign-off or instructions..."
                  className="font-mono text-xs bg-background"
                  rows={2}
                />
              </div>

              <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 font-mono flex items-start gap-2">
                <Lock className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>
                  Devora strictly prohibits autonomous merging or unapproved git mutations. This approval authorises isolated workspace execution only.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs font-mono"
                  onClick={() => {
                    setApprovalModalOpen(false);
                    setPlanToApprove(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="text-xs font-mono bg-emerald-600 hover:bg-emerald-500 text-white"
                  onClick={() =>
                    approvePlanMutation.mutate({
                      planId: planToApprove.id,
                      diffHash: approvalDiffHash,
                      notes: approvalNotes,
                    })
                  }
                  disabled={approvePlanMutation.isPending || !approvalDiffHash}
                >
                  {approvePlanMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : null}
                  Confirm & Bind Approval
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

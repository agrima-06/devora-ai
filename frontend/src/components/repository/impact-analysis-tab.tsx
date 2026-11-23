"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Code2,
  FileCode,
  Flame,
  Info,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  TestTube2,
  Workflow,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { impactService } from "@/services/impact-service";
import { graphService } from "@/services/graph-service";
import {
  ImpactAnalysisRequest,
  ImpactAnalysisResponse,
  ImpactedNodeItem,
  RecommendedTestItem,
} from "@/types";

interface ImpactAnalysisTabProps {
  repositoryId: string;
}

export function ImpactAnalysisTab({ repositoryId }: ImpactAnalysisTabProps) {
  // Input form state
  const [targetFilePath, setTargetFilePath] = useState("");
  const [targetSymbol, setTargetSymbol] = useState("");
  const [maxDepth, setMaxDepth] = useState<number>(3);
  const [includeTests, setIncludeTests] = useState<boolean>(true);

  // Result state
  const [activeAnalysis, setActiveAnalysis] = useState<ImpactAnalysisResponse | null>(null);
  const [subView, setSubView] = useState<"nodes" | "paths" | "tests" | "warnings">("nodes");
  const [nodeFilter, setNodeFilter] = useState<"all" | "direct" | "transitive">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch nodes for quick selection autocomplete
  const { data: nodesData } = useQuery({
    queryKey: ["repository-graph-nodes-picker", repositoryId],
    queryFn: () => graphService.listNodes(repositoryId, { limit: 100 }),
  });

  // Mutation to trigger impact analysis
  const analyzeMutation = useMutation({
    mutationFn: (req: ImpactAnalysisRequest) => impactService.analyzeImpact(repositoryId, req),
    onSuccess: (data) => {
      setActiveAnalysis(data);
    },
  });

  const handleRunAnalysis = (overrideFile?: string) => {
    const file = overrideFile || targetFilePath;
    const req: ImpactAnalysisRequest = {
      file_paths: file ? [file.trim()] : [],
      qualified_names: targetSymbol ? [targetSymbol.trim()] : [],
      max_depth: maxDepth,
      include_tests: includeTests,
      max_impacted_nodes: 100,
    };
    analyzeMutation.mutate(req);
  };

  const severityColors: Record<string, string> = {
    CRITICAL: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    HIGH: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    MEDIUM: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    LOW: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    UNKNOWN: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };

  const filteredImpactedNodes = (activeAnalysis?.impacted_nodes || []).filter((item) => {
    if (nodeFilter === "direct" && !item.is_direct) return false;
    if (nodeFilter === "transitive" && item.is_direct) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        item.name.toLowerCase().includes(q) ||
        item.qualified_name.toLowerCase().includes(q) ||
        (item.file_path && item.file_path.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Target Selector & Analysis Trigger Card */}
      <Card className="bg-card/40 border-border">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm font-semibold flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-orange-400" />
              Blast Radius & Change Impact Configuration
            </span>
            <Badge variant="outline" className="text-xs font-mono">
              Phase 10.2 Engine
            </Badge>
          </CardTitle>
          <CardDescription className="text-xs">
            Identify affected consumers, reverse dependency paths, and test requirements prior to code modification.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 pt-2 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-mono text-muted-foreground block mb-1">
                Target File Path (Relative to repository root)
              </label>
              <Input
                placeholder="e.g. app/services/auth_service.py"
                value={targetFilePath}
                onChange={(e) => setTargetFilePath(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-xs font-mono text-muted-foreground block mb-1">
                Target Qualified Symbol (Optional)
              </label>
              <Input
                placeholder="e.g. app/services/auth_service.py:verify_token"
                value={targetSymbol}
                onChange={(e) => setTargetSymbol(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          {/* Quick Picker Chips */}
          {nodesData?.nodes && nodesData.nodes.length > 0 && (
            <div>
              <span className="text-[11px] text-muted-foreground font-mono block mb-1">
                Quick pick sample repository file:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {nodesData.nodes
                  .filter((n) => n.node_type === "FILE")
                  .slice(0, 6)
                  .map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        setTargetFilePath(n.file_path || n.name);
                        handleRunAnalysis(n.file_path || n.name);
                      }}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors border border-border/60"
                    >
                      {n.name}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {/* Controls & Submit */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-border/40">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted-foreground">Max Depth:</span>
                <select
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  className="bg-card text-foreground font-mono text-xs rounded border border-border px-2 py-1"
                >
                  <option value={1}>1 (Direct only)</option>
                  <option value={2}>2 hops</option>
                  <option value={3}>3 hops (Default)</option>
                  <option value={4}>4 hops</option>
                  <option value={5}>5 hops (Deep)</option>
                </select>
              </div>

              <label className="flex items-center gap-2 text-xs font-mono cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeTests}
                  onChange={(e) => setIncludeTests(e.target.checked)}
                  className="rounded border-border text-primary"
                />
                <span>Map Recommended Tests</span>
              </label>
            </div>

            <Button
              size="sm"
              onClick={() => handleRunAnalysis()}
              disabled={analyzeMutation.isPending || (!targetFilePath && !targetSymbol)}
              className="gap-2 font-mono text-xs shadow-sm"
            >
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Calculating Blast Radius...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Analyze Blast Radius
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Results View */}
      {activeAnalysis && (
        <div className="space-y-6">
          {/* Executive Summary & Severity Card */}
          <Card className="bg-card/40 border-border">
            <CardContent className="p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono text-muted-foreground uppercase">Impact Severity:</span>
                    <Badge className={`${severityColors[activeAnalysis.severity]} font-mono text-xs px-2.5 py-0.5`}>
                      {activeAnalysis.severity}
                    </Badge>
                    <span className="text-xs font-mono text-muted-foreground">
                      Score: <strong className="text-foreground">{activeAnalysis.impact_score}/100</strong>
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      Certainty: <strong className="text-foreground">{Math.round(activeAnalysis.confidence * 100)}%</strong>
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground font-mono mt-1">
                    {activeAnalysis.score_explanation}
                  </p>
                </div>

                {activeAnalysis.is_stale ? (
                  <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/20 font-mono text-xs">
                    Graph Stale: {activeAnalysis.staleness_reason}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 font-mono text-xs">
                    Graph Synchronized
                  </Badge>
                )}
              </div>

              {/* Metric Breakdown Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-border/40 font-mono">
                <div className="bg-muted/30 p-2.5 rounded border border-border/40">
                  <span className="text-[11px] text-muted-foreground block">Affected Files</span>
                  <span className="text-lg font-bold text-foreground">{activeAnalysis.summary.total_affected_files}</span>
                </div>
                <div className="bg-muted/30 p-2.5 rounded border border-border/40">
                  <span className="text-[11px] text-muted-foreground block">Affected Symbols</span>
                  <span className="text-lg font-bold text-foreground">{activeAnalysis.summary.total_affected_symbols}</span>
                </div>
                <div className="bg-muted/30 p-2.5 rounded border border-border/40">
                  <span className="text-[11px] text-muted-foreground block">Direct / Transitive</span>
                  <span className="text-lg font-bold text-foreground">
                    {activeAnalysis.summary.direct_impact_count} / {activeAnalysis.summary.transitive_impact_count}
                  </span>
                </div>
                <div className="bg-muted/30 p-2.5 rounded border border-border/40">
                  <span className="text-[11px] text-muted-foreground block">Recommended Tests</span>
                  <span className="text-lg font-bold text-foreground">{activeAnalysis.summary.recommended_tests_count}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Sub-view Navigation */}
          <div className="flex items-center gap-2 border-b border-border text-xs font-mono">
            <button
              onClick={() => setSubView("nodes")}
              className={`pb-2.5 px-3 flex items-center gap-1.5 border-b-2 transition-colors ${
                subView === "nodes"
                  ? "border-primary text-foreground font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Boxes className="w-3.5 h-3.5" />
              <span>Affected Entities ({activeAnalysis.impacted_nodes.length})</span>
            </button>

            <button
              onClick={() => setSubView("paths")}
              className={`pb-2.5 px-3 flex items-center gap-1.5 border-b-2 transition-colors ${
                subView === "paths"
                  ? "border-primary text-foreground font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Workflow className="w-3.5 h-3.5" />
              <span>Dependency Paths ({activeAnalysis.dependency_paths.length})</span>
            </button>

            <button
              onClick={() => setSubView("tests")}
              className={`pb-2.5 px-3 flex items-center gap-1.5 border-b-2 transition-colors ${
                subView === "tests"
                  ? "border-primary text-foreground font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <TestTube2 className="w-3.5 h-3.5" />
              <span>Recommended Tests ({activeAnalysis.recommended_tests.length})</span>
            </button>

            {activeAnalysis.unresolved_warnings.length > 0 && (
              <button
                onClick={() => setSubView("warnings")}
                className={`pb-2.5 px-3 flex items-center gap-1.5 border-b-2 transition-colors ${
                  subView === "warnings"
                    ? "border-amber-400 text-amber-400 font-semibold"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Unresolved Warnings ({activeAnalysis.unresolved_warnings.length})</span>
              </button>
            )}
          </div>

          {/* Sub-view 1: Affected Entities Table */}
          {subView === "nodes" && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant={nodeFilter === "all" ? "default" : "outline"}
                    onClick={() => setNodeFilter("all")}
                    className="text-xs h-7 font-mono"
                  >
                    All ({activeAnalysis.impacted_nodes.length})
                  </Button>
                  <Button
                    size="sm"
                    variant={nodeFilter === "direct" ? "default" : "outline"}
                    onClick={() => setNodeFilter("direct")}
                    className="text-xs h-7 font-mono"
                  >
                    Direct ({activeAnalysis.summary.direct_impact_count})
                  </Button>
                  <Button
                    size="sm"
                    variant={nodeFilter === "transitive" ? "default" : "outline"}
                    onClick={() => setNodeFilter("transitive")}
                    className="text-xs h-7 font-mono"
                  >
                    Transitive ({activeAnalysis.summary.transitive_impact_count})
                  </Button>
                </div>

                <div className="relative max-w-xs w-full">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input
                    placeholder="Filter affected symbols..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 text-xs font-mono h-8"
                  />
                </div>
              </div>

              {filteredImpactedNodes.length === 0 ? (
                <div className="p-8 text-center border border-border/60 rounded bg-card/20 text-xs font-mono text-muted-foreground">
                  No affected nodes match the current filter.
                </div>
              ) : (
                <div className="border border-border rounded overflow-hidden">
                  <table className="w-full text-xs font-mono">
                    <thead className="bg-muted/40 text-muted-foreground border-b border-border">
                      <tr>
                        <th className="py-2 px-3 text-left">Entity</th>
                        <th className="py-2 px-3 text-left">Type</th>
                        <th className="py-2 px-3 text-left">File Path</th>
                        <th className="py-2 px-3 text-center">Depth</th>
                        <th className="py-2 px-3 text-center">Impact Type</th>
                        <th className="py-2 px-3 text-left">Primary Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {filteredImpactedNodes.map((n) => (
                        <tr key={n.node_id} className="hover:bg-muted/20 transition-colors">
                          <td className="py-2.5 px-3 font-semibold text-foreground flex items-center gap-1.5">
                            <Code2 className="w-3 h-3 text-primary" />
                            <span>{n.name}</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <Badge variant="outline" className="text-[10px] py-0 px-1 font-mono">
                              {n.node_type}
                            </Badge>
                          </td>
                          <td className="py-2.5 px-3 text-muted-foreground max-w-[200px] truncate" title={n.file_path || ""}>
                            {n.file_path || "-"}
                          </td>
                          <td className="py-2.5 px-3 text-center font-bold">{n.depth}</td>
                          <td className="py-2.5 px-3 text-center">
                            {n.is_direct ? (
                              <Badge className="bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[10px]">
                                DIRECT
                              </Badge>
                            ) : (
                              <Badge className="bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px]">
                                TRANSITIVE
                              </Badge>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-muted-foreground text-[11px] max-w-[280px] truncate" title={n.primary_reason}>
                            {n.primary_reason}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Sub-view 2: Dependency Paths Explorer */}
          {subView === "paths" && (
            <div className="space-y-3">
              {activeAnalysis.dependency_paths.length === 0 ? (
                <div className="p-8 text-center border border-border/60 rounded bg-card/20 text-xs font-mono text-muted-foreground">
                  No multi-hop dependency paths recorded.
                </div>
              ) : (
                activeAnalysis.dependency_paths.map((p, idx) => (
                  <Card key={idx} className="bg-card/30 border-border p-3.5 space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span className="font-semibold text-foreground flex items-center gap-1.5">
                        <Workflow className="w-3.5 h-3.5 text-primary" />
                        <span>Impact Chain #{idx + 1}</span>
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        Depth: {p.depth} hop{p.depth > 1 ? "s" : ""}
                      </Badge>
                    </div>

                    <div className="bg-muted/40 p-2.5 rounded border border-border/60 text-muted-foreground overflow-x-auto flex items-center gap-2">
                      {p.hops.map((hop, hidx) => (
                        <React.Fragment key={hidx}>
                          <span className="text-foreground font-semibold px-2 py-0.5 rounded bg-card border border-border">
                            {hop.source_name}
                          </span>
                          <span className="text-primary text-[11px] font-bold">
                            -[{hop.edge_type}]-&gt;
                          </span>
                        </React.Fragment>
                      ))}
                      <span className="text-orange-400 font-semibold px-2 py-0.5 rounded bg-orange-500/10 border border-orange-500/20">
                        {p.target_name}
                      </span>
                    </div>
                  </Card>
                ))
              )}
            </div>
          )}

          {/* Sub-view 3: Recommended Tests */}
          {subView === "tests" && (
            <div className="space-y-3">
              {activeAnalysis.recommended_tests.length === 0 ? (
                <div className="p-8 text-center border border-border/60 rounded bg-card/20 text-xs font-mono text-muted-foreground">
                  No automated tests directly or transitively mapped to this component.
                </div>
              ) : (
                activeAnalysis.recommended_tests.map((t, idx) => (
                  <Card key={idx} className="bg-card/30 border-border p-3.5 font-mono text-xs flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <TestTube2 className="w-4 h-4 text-emerald-400" />
                        <span className="font-semibold text-foreground">{t.test_file_path}</span>
                        {t.recommendation_type === "CONFIRMED" ? (
                          <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">
                            CONFIRMED DEPENDENCY
                          </Badge>
                        ) : (
                          <Badge className="bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px]">
                            HEURISTIC MATCH
                          </Badge>
                        )}
                      </div>
                      <p className="text-muted-foreground text-[11px]">{t.reason}</p>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] text-muted-foreground block">Confidence</span>
                      <span className="font-bold text-foreground">{Math.round(t.confidence * 100)}%</span>
                    </div>
                  </Card>
                ))
              )}
            </div>
          )}

          {/* Sub-view 4: Unresolved Warnings */}
          {subView === "warnings" && (
            <div className="space-y-3">
              {activeAnalysis.unresolved_warnings.map((w, idx) => (
                <Card key={idx} className="bg-amber-500/5 border-amber-500/20 p-3.5 font-mono text-xs space-y-1">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{w.source_node_name} &rarr; {w.target_symbol} ({w.resolution_status})</span>
                  </div>
                  <p className="text-muted-foreground text-[11px]">{w.message}</p>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

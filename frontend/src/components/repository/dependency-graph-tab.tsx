"use client";

import React, { useState, useMemo, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  RefreshCw,
  Search,
  Filter,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ArrowRight,
  ArrowLeft,
  ChevronRight,
  ExternalLink,
  FileCode,
  Layers,
  Code2,
  Share2,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { graphService } from "@/services/graph-service";
import { GraphNodeItem, GraphEdgeItem } from "@/types";

interface DependencyGraphTabProps {
  repositoryId: string;
}

export function DependencyGraphTab({ repositoryId }: DependencyGraphTabProps) {
  const queryClient = useQueryClient();

  // Filters & State
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [traversalDepth, setTraversalDepth] = useState<number>(2);
  const [traversalDirection, setTraversalDirection] = useState<string>("outgoing");
  const [showUnresolved, setShowUnresolved] = useState<boolean>(false);

  // Canvas zoom and pan
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // 1. Fetch graph overview summary
  const {
    data: summary,
    isLoading: summaryLoading,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["repository-graph-summary", repositoryId],
    queryFn: () => graphService.getSummary(repositoryId),
    enabled: !!repositoryId,
  });

  // 2. Fetch graph nodes matching filter
  const {
    data: nodesResponse,
    isLoading: nodesLoading,
  } = useQuery({
    queryKey: ["repository-graph-nodes", repositoryId, nodeTypeFilter, activeSearch],
    queryFn: () =>
      graphService.listNodes(repositoryId, {
        node_type: nodeTypeFilter === "all" ? undefined : nodeTypeFilter,
        q: activeSearch || undefined,
        limit: 100,
      }),
    enabled: !!repositoryId,
  });

  // 3. Fetch dependencies for selected node
  const {
    data: depSubgraph,
    isLoading: depLoading,
  } = useQuery({
    queryKey: [
      "repository-graph-dependencies",
      repositoryId,
      selectedNodeId,
      traversalDirection,
      traversalDepth,
    ],
    queryFn: () =>
      selectedNodeId
        ? graphService.getDependencies(repositoryId, {
            node_id: selectedNodeId,
            direction: traversalDirection,
            max_depth: traversalDepth,
            limit: 100,
          })
        : null,
    enabled: !!repositoryId && !!selectedNodeId,
  });

  // 4. Fetch selected node details
  const {
    data: nodeDetail,
    isLoading: detailLoading,
  } = useQuery({
    queryKey: ["repository-graph-node-detail", repositoryId, selectedNodeId],
    queryFn: () =>
      selectedNodeId ? graphService.getNodeDetail(repositoryId, selectedNodeId) : null,
    enabled: !!repositoryId && !!selectedNodeId,
  });

  // 5. Fetch unresolved references
  const {
    data: unresolvedResponse,
  } = useQuery({
    queryKey: ["repository-graph-unresolved", repositoryId],
    queryFn: () => graphService.listUnresolved(repositoryId, { limit: 50 }),
    enabled: !!repositoryId,
  });

  // Re-index graph mutation
  const indexGraphMutation = useMutation({
    mutationFn: (force: boolean) =>
      graphService.indexGraph(repositoryId, { force_reindex: force }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository-graph-summary", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["repository-graph-nodes", repositoryId] });
      queryClient.invalidateQueries({ queryKey: ["repository-graph-unresolved", repositoryId] });
      if (selectedNodeId) {
        queryClient.invalidateQueries({ queryKey: ["repository-graph-node-detail", repositoryId, selectedNodeId] });
      }
    },
  });

  // Active nodes to render in canvas
  const canvasNodes = useMemo(() => {
    if (depSubgraph && depSubgraph.nodes && depSubgraph.nodes.length > 0) {
      return depSubgraph.nodes;
    }
    return nodesResponse?.nodes || [];
  }, [depSubgraph, nodesResponse]);

  const canvasEdges = useMemo(() => {
    if (depSubgraph && depSubgraph.edges) {
      return depSubgraph.edges;
    }
    return [];
  }, [depSubgraph]);

  // Node layout calculation
  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    if (!canvasNodes || canvasNodes.length === 0) return positions;

    if (selectedNodeId && depSubgraph) {
      // Radial / Layered layout around root
      const centerX = 500;
      const centerY = 350;
      positions[selectedNodeId] = { x: centerX, y: centerY };

      const otherNodes = canvasNodes.filter((n) => n.id !== selectedNodeId);
      const level1 = otherNodes.slice(0, 10);
      const level2 = otherNodes.slice(10);

      level1.forEach((n, idx) => {
        const angle = (idx / Math.max(level1.length, 1)) * 2 * Math.PI;
        positions[n.id] = {
          x: centerX + 260 * Math.cos(angle),
          y: centerY + 200 * Math.sin(angle),
        };
      });

      level2.forEach((n, idx) => {
        const angle = (idx / Math.max(level2.length, 1)) * 2 * Math.PI;
        positions[n.id] = {
          x: centerX + 440 * Math.cos(angle),
          y: centerY + 320 * Math.sin(angle),
        };
      });
    } else {
      // Grid layout
      const cols = Math.max(3, Math.ceil(Math.sqrt(canvasNodes.length * 1.5)));
      const xSpacing = 280;
      const ySpacing = 140;
      const startX = 80;
      const startY = 80;

      canvasNodes.forEach((node, idx) => {
        const row = Math.floor(idx / cols);
        const col = idx % cols;
        positions[node.id] = {
          x: startX + col * xSpacing,
          y: startY + row * ySpacing,
        };
      });
    }

    return positions;
  }, [canvasNodes, selectedNodeId, depSubgraph]);

  // Color mappings per node type
  const getNodeColor = (type: string) => {
    switch (type.toUpperCase()) {
      case "FILE":
        return {
          bg: "bg-blue-500/10 border-blue-500/40 text-blue-400",
          pill: "bg-blue-500/20 text-blue-300 border-blue-500/30",
          svgStroke: "#3b82f6",
          svgFill: "#1e293b",
        };
      case "CLASS":
        return {
          bg: "bg-purple-500/10 border-purple-500/40 text-purple-400",
          pill: "bg-purple-500/20 text-purple-300 border-purple-500/30",
          svgStroke: "#a855f7",
          svgFill: "#2e1065",
        };
      case "FUNCTION":
        return {
          bg: "bg-emerald-500/10 border-emerald-500/40 text-emerald-400",
          pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
          svgStroke: "#10b981",
          svgFill: "#064e3b",
        };
      case "METHOD":
        return {
          bg: "bg-cyan-500/10 border-cyan-500/40 text-cyan-400",
          pill: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
          svgStroke: "#06b6d4",
          svgFill: "#083344",
        };
      case "DIRECTORY":
        return {
          bg: "bg-amber-500/10 border-amber-500/40 text-amber-400",
          pill: "bg-amber-500/20 text-amber-300 border-amber-500/30",
          svgStroke: "#f59e0b",
          svgFill: "#451a03",
        };
      default:
        return {
          bg: "bg-zinc-800 border-zinc-700 text-zinc-300",
          pill: "bg-zinc-700 text-zinc-200 border-zinc-600",
          svgStroke: "#71717a",
          svgFill: "#18181b",
        };
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Summary Stats */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2 text-foreground">
            <Boxes className="w-5 h-5 text-primary" />
            <span>Cross-File Symbol & Dependency Graph</span>
            {summary && (
              <Badge variant="outline" className="text-xs font-mono ml-2">
                Commit: {summary.current_commit_sha?.slice(0, 8) || "HEAD"}
              </Badge>
            )}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Queryable structural AST hierarchy, module imports, class inheritance, and external dependencies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchSummary()}
            className="text-xs h-8 gap-1.5"
            disabled={summaryLoading}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${summaryLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => indexGraphMutation.mutate(true)}
            disabled={indexGraphMutation.isPending}
            className="text-xs h-8 gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${indexGraphMutation.isPending ? "animate-spin" : ""}`} />
            {indexGraphMutation.isPending ? "Indexing Graph..." : "Re-index Graph"}
          </Button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="bg-card/40 border-border">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
              <span>Total Nodes</span>
              <Boxes className="w-3.5 h-3.5 text-blue-400" />
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-1">
            <p className="text-xl font-bold font-mono text-foreground">
              {summary?.total_nodes ?? 0}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {summary?.node_types_breakdown?.CLASS ?? 0} classes, {summary?.node_types_breakdown?.FUNCTION ?? 0} functions
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card/40 border-border">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
              <span>Relationships</span>
              <Share2 className="w-3.5 h-3.5 text-purple-400" />
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-1">
            <p className="text-xl font-bold font-mono text-foreground">
              {summary?.total_edges ?? 0}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {summary?.edge_types_breakdown?.IMPORTS ?? 0} imports, {summary?.edge_types_breakdown?.DEFINES ?? 0} definitions
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card/40 border-border">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
              <span>External Packages</span>
              <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-1">
            <p className="text-xl font-bold font-mono text-foreground">
              {summary?.external_count ?? 0}
            </p>
            <p className="text-[11px] text-muted-foreground">Third-party and stdlib imports</p>
          </CardContent>
        </Card>

        <Card
          className="bg-card/40 border-border cursor-pointer hover:border-amber-500/40 transition-colors"
          onClick={() => setShowUnresolved(!showUnresolved)}
        >
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
              <span>Unresolved Refs</span>
              <AlertTriangle className={`w-3.5 h-3.5 ${summary?.unresolved_count ? "text-amber-400" : "text-muted-foreground"}`} />
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-1">
            <p className="text-xl font-bold font-mono text-foreground">
              {summary?.unresolved_count ?? 0}
            </p>
            <p className="text-[11px] text-amber-400">
              {showUnresolved ? "Click to hide list" : "Click to view unresolved"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Unresolved References Table (expandable) */}
      {showUnresolved && (
        <Card className="bg-amber-950/20 border-amber-500/30">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold text-amber-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Unresolved Cross-File References ({unresolvedResponse?.total ?? 0})
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowUnresolved(false)}
                className="text-xs h-7 text-muted-foreground"
              >
                Close
              </Button>
            </div>
            <CardDescription className="text-xs text-muted-foreground">
              Symbols or modules referenced in code that could not be mapped to a local file or known external package.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 pt-1">
            <div className="max-h-56 overflow-y-auto space-y-1.5 font-mono text-xs">
              {unresolvedResponse?.unresolved && unresolvedResponse.unresolved.length > 0 ? (
                unresolvedResponse.unresolved.map((item) => (
                  <div
                    key={item.edge_id}
                    className="flex items-center justify-between p-2 rounded bg-background/50 border border-border"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-foreground">{item.source_file}</span>
                      {item.line_number && (
                        <span className="text-muted-foreground">:{item.line_number}</span>
                      )}
                      <span className="text-muted-foreground">&rarr;</span>
                      <span className="text-amber-300">{item.target_symbol}</span>
                    </div>
                    <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30">
                      {item.resolution_status}
                    </Badge>
                  </div>
                ))
              ) : (
                <p className="text-xs text-muted-foreground py-2">No unresolved references detected.</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 2. Controls & Filter Bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 p-3 rounded-lg bg-card/40 border border-border">
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Node Type Pills */}
          <div className="flex items-center gap-1 bg-muted/40 p-1 rounded-md text-xs font-mono">
            {["all", "FILE", "CLASS", "FUNCTION", "METHOD"].map((t) => (
              <button
                key={t}
                onClick={() => setNodeTypeFilter(t)}
                className={`px-2.5 py-1 rounded text-xs transition-colors ${
                  nodeTypeFilter === t
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search symbol or file..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") setActiveSearch(searchQuery);
              }}
              className="pl-8 text-xs h-8 bg-background"
            />
          </div>
          {activeSearch && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchQuery("");
                setActiveSearch("");
              }}
              className="text-xs h-8 px-2 text-muted-foreground"
            >
              Clear
            </Button>
          )}
        </div>

        {/* Traversal Controls (when node selected) */}
        <div className="flex items-center gap-3">
          {selectedNodeId && (
            <div className="flex items-center gap-2 bg-muted/40 p-1 rounded-md text-xs font-mono">
              <span className="text-[11px] text-muted-foreground pl-1.5">Depth:</span>
              {[1, 2, 3].map((d) => (
                <button
                  key={d}
                  onClick={() => setTraversalDepth(d)}
                  className={`px-2 py-0.5 rounded ${
                    traversalDepth === d
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {d}
                </button>
              ))}
              <span className="text-muted-foreground">|</span>
              <select
                value={traversalDirection}
                onChange={(e) => setTraversalDirection(e.target.value)}
                className="bg-transparent text-foreground text-xs pr-2 focus:outline-none"
              >
                <option value="outgoing" className="bg-card">Outgoing</option>
                <option value="incoming" className="bg-card">Incoming</option>
                <option value="both" className="bg-card">Both</option>
              </select>
            </div>
          )}

          {/* Zoom controls */}
          <div className="flex items-center gap-1 border border-border rounded-md p-0.5">
            <Button
              variant="ghost"
              size="icon"
              className="w-7 h-7"
              onClick={() => setZoom((z) => Math.min(z + 0.2, 2.0))}
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="w-7 h-7"
              onClick={() => setZoom((z) => Math.max(z - 0.2, 0.4))}
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="w-7 h-7"
              onClick={() => {
                setZoom(1);
                setPan({ x: 0, y: 0 });
              }}
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* 3. Main Workspace: Interactive Canvas + Inspector Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Interactive SVG Canvas */}
        <div className="lg:col-span-2 relative h-[560px] rounded-lg border border-border bg-card/20 overflow-hidden select-none">
          {/* Canvas status overlay */}
          <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
            <Badge variant="outline" className="bg-background/80 backdrop-blur text-[11px] font-mono">
              Rendering {canvasNodes.length} nodes
              {selectedNodeId ? ` (Depth ${traversalDepth})` : ""}
            </Badge>
            {selectedNodeId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedNodeId(null)}
                className="text-[11px] h-6 px-2 bg-background/80 backdrop-blur"
              >
                Reset Focus
              </Button>
            )}
          </div>

          <svg
            className="w-full h-full cursor-grab active:cursor-grabbing"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
              </marker>
              <marker
                id="arrow-active"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
              </marker>
            </defs>

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Edges */}
              {canvasEdges.map((edge) => {
                const srcPos = nodePositions[edge.source_node_id];
                const tgtPos = edge.target_node_id ? nodePositions[edge.target_node_id] : null;
                if (!srcPos || !tgtPos) return null;

                const isConnectedToSelected =
                  selectedNodeId === edge.source_node_id || selectedNodeId === edge.target_node_id;

                return (
                  <g key={edge.id}>
                    <line
                      x1={srcPos.x + 90}
                      y1={srcPos.y + 24}
                      x2={tgtPos.x + 90}
                      y2={tgtPos.y + 24}
                      stroke={isConnectedToSelected ? "#10b981" : "#3f3f46"}
                      strokeWidth={isConnectedToSelected ? 2 : 1}
                      strokeDasharray={edge.edge_type === "INHERITS" ? "4 4" : undefined}
                      markerEnd={isConnectedToSelected ? "url(#arrow-active)" : "url(#arrow)"}
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {canvasNodes.map((node) => {
                const pos = nodePositions[node.id] || { x: 100, y: 100 };
                const isSelected = selectedNodeId === node.id;
                const colors = getNodeColor(node.node_type);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onClick={() => setSelectedNodeId(node.id)}
                    className="cursor-pointer group"
                  >
                    {/* Node background card */}
                    <rect
                      width="180"
                      height="48"
                      rx="8"
                      fill={isSelected ? "#1e1b4b" : colors.svgFill}
                      stroke={isSelected ? "#818cf8" : colors.svgStroke}
                      strokeWidth={isSelected ? 2.5 : 1}
                      className="transition-all duration-150"
                    />

                    {/* Node type badge */}
                    <rect
                      x="8"
                      y="8"
                      width="48"
                      height="14"
                      rx="4"
                      fill={colors.svgStroke}
                      opacity={0.2}
                    />
                    <text
                      x="12"
                      y="19"
                      fontSize="9"
                      fontWeight="600"
                      fontFamily="monospace"
                      fill={colors.svgStroke}
                    >
                      {node.node_type}
                    </text>

                    {/* Node name */}
                    <text
                      x="8"
                      y="38"
                      fontSize="12"
                      fontWeight="bold"
                      fill="#f4f4f5"
                      fontFamily="monospace"
                    >
                      {node.name.length > 18 ? node.name.slice(0, 16) + "…" : node.name}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        {/* Node Inspector Sidebar */}
        <div className="space-y-4">
          <Card className="bg-card/40 border-border h-[560px] flex flex-col">
            <CardHeader className="p-4 pb-2 border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-primary" />
                  <span>Node Inspector</span>
                </CardTitle>
                {selectedNodeId && (
                  <Badge variant="outline" className="text-[10px] font-mono">
                    {nodeDetail?.node.node_type}
                  </Badge>
                )}
              </div>
            </CardHeader>

            <CardContent className="p-4 flex-1 overflow-y-auto space-y-4">
              {nodeDetail ? (
                <>
                  {/* Entity Details */}
                  <div className="space-y-1.5">
                    <h3 className="text-sm font-bold font-mono text-foreground break-all">
                      {nodeDetail.node.name}
                    </h3>
                    <p className="text-[11px] font-mono text-muted-foreground break-all">
                      {nodeDetail.node.qualified_name}
                    </p>
                    {nodeDetail.node.file_path && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
                        <FileCode className="w-3 h-3 text-primary" />
                        <span>{nodeDetail.node.file_path}</span>
                        {nodeDetail.node.start_line && (
                          <span>(L{nodeDetail.node.start_line}–{nodeDetail.node.end_line})</span>
                        )}
                      </p>
                    )}
                  </div>

                  {/* Signature preview if available */}
                  {nodeDetail.node.metadata?.signature && (
                    <div className="p-2 rounded bg-muted/40 border border-border text-xs font-mono text-zinc-300 overflow-x-auto">
                      <code>{nodeDetail.node.metadata.signature}</code>
                    </div>
                  )}

                  {/* Outgoing Dependencies */}
                  <div className="space-y-2 pt-2 border-t border-border">
                    <h4 className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <ArrowRight className="w-3.5 h-3.5 text-emerald-400" />
                        Outgoing Dependencies ({nodeDetail.outgoing_edges.length})
                      </span>
                    </h4>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto font-mono text-xs">
                      {nodeDetail.outgoing_edges.length > 0 ? (
                        nodeDetail.outgoing_edges.map((edge) => {
                          const targetNode = edge.target_node_id
                            ? nodeDetail.related_nodes[edge.target_node_id]
                            : null;
                          return (
                            <div
                              key={edge.id}
                              onClick={() => {
                                if (targetNode) setSelectedNodeId(targetNode.id);
                              }}
                              className="p-1.5 rounded bg-background/50 border border-border flex items-center justify-between hover:border-emerald-500/40 cursor-pointer"
                            >
                              <div className="flex items-center gap-1.5 truncate">
                                <Badge variant="outline" className="text-[9px] py-0 px-1">
                                  {edge.edge_type}
                                </Badge>
                                <span className="truncate text-foreground">
                                  {targetNode ? targetNode.name : edge.target_symbol || "External"}
                                </span>
                              </div>
                              <span className="text-[10px] text-muted-foreground">
                                {edge.resolution_status}
                              </span>
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-xs text-muted-foreground py-1">No outgoing dependencies</p>
                      )}
                    </div>
                  </div>

                  {/* Incoming Dependencies */}
                  <div className="space-y-2 pt-2 border-t border-border">
                    <h4 className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <ArrowLeft className="w-3.5 h-3.5 text-blue-400" />
                        Incoming Dependents ({nodeDetail.incoming_edges.length})
                      </span>
                    </h4>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto font-mono text-xs">
                      {nodeDetail.incoming_edges.length > 0 ? (
                        nodeDetail.incoming_edges.map((edge) => {
                          const srcNode = nodeDetail.related_nodes[edge.source_node_id];
                          return (
                            <div
                              key={edge.id}
                              onClick={() => {
                                if (srcNode) setSelectedNodeId(srcNode.id);
                              }}
                              className="p-1.5 rounded bg-background/50 border border-border flex items-center justify-between hover:border-blue-500/40 cursor-pointer"
                            >
                              <div className="flex items-center gap-1.5 truncate">
                                <Badge variant="outline" className="text-[9px] py-0 px-1">
                                  {edge.edge_type}
                                </Badge>
                                <span className="truncate text-foreground">
                                  {srcNode ? srcNode.name : "Source"}
                                </span>
                              </div>
                              <span className="text-[10px] text-muted-foreground">
                                {edge.resolution_status}
                              </span>
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-xs text-muted-foreground py-1">No incoming dependents</p>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-muted-foreground">
                  <Boxes className="w-8 h-8 mb-2 opacity-40 text-primary" />
                  <p className="text-xs font-medium">Select a node from the canvas</p>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Click any file, class, or function to inspect its relationships and traverse dependencies.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

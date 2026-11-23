"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  GitBranch,
  GitPullRequest,
  ArrowLeft,
  Plus,
  RefreshCw,
  ExternalLink,
  Terminal,
  Database,
  CheckSquare,
  Shield,
  Loader2,
  Calendar,
  Search,
  FileCode,
  Layers,
  Code2,
  FileText,
  Boxes,
  Cpu,
  Sparkles,
  ChevronRight,
  BookOpen,
  CheckCircle2,
  Flame,
  Wrench,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { repositoryService } from "@/services/repository-service";
import { githubService } from "@/services/github-service";
import { taskService } from "@/services/task-service";
import { formatDate } from "@/lib/utils";
import { DependencyGraphTab } from "@/components/repository/dependency-graph-tab";
import { ImpactAnalysisTab } from "@/components/repository/impact-analysis-tab";
import { WorkspaceIntelligenceTab } from "@/components/repository/workspace-intelligence-tab";
import { ArchitectureIntelligenceTab } from "@/components/repository/architecture-intelligence-tab";
import { RefactoringIntelligenceTab } from "@/components/repository/refactoring-intelligence-tab";

type ActiveTab = "architecture" | "refactoring" | "graph" | "impact" | "workspaces" | "search" | "files" | "tasks" | "branches" | "pull_requests";

export default function RepositoryDetailPage() {
  const params = useParams();
  const repoId = params.id as string;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<ActiveTab>("architecture");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchType, setSearchType] = useState<string>("all");
  const [activeSearchTerm, setActiveSearchTerm] = useState("");
  const [fileCategoryFilter, setFileCategoryFilter] = useState<string>("all");
  const [symbolFilter, setSymbolFilter] = useState<string>("all");

  // Fetch repository metadata
  const {
    data: repository,
    isLoading: repoLoading,
    error: repoError,
  } = useQuery({
    queryKey: ["repository", repoId],
    queryFn: () => repositoryService.get(repoId),
    enabled: !!repoId,
  });

  // Fetch repository architecture & conventions
  const {
    data: architecture,
    isLoading: archLoading,
    refetch: refetchArch,
  } = useQuery({
    queryKey: ["repository-architecture", repoId],
    queryFn: () => repositoryService.getArchitecture(repoId),
    enabled: !!repoId,
  });

  // Fetch repository files
  const {
    data: files = [],
    isLoading: filesLoading,
    refetch: refetchFiles,
  } = useQuery({
    queryKey: ["repository-files", repoId, fileCategoryFilter],
    queryFn: () =>
      repositoryService.listFiles(
        repoId,
        fileCategoryFilter === "all" ? undefined : fileCategoryFilter
      ),
    enabled: !!repoId,
  });

  // Fetch repository symbols
  const {
    data: symbols = [],
    isLoading: symbolsLoading,
  } = useQuery({
    queryKey: ["repository-symbols", repoId, symbolFilter],
    queryFn: () =>
      repositoryService.listSymbols(
        repoId,
        symbolFilter === "all" ? undefined : symbolFilter
      ),
    enabled: !!repoId && activeTab === "files",
  });

  // Fetch code search results
  const {
    data: searchResults,
    isLoading: searchLoading,
    refetch: executeSearch,
  } = useQuery({
    queryKey: ["repository-search", repoId, activeSearchTerm, searchType],
    queryFn: () =>
      repositoryService.searchCode(repoId, activeSearchTerm, searchType, 25),
    enabled: !!repoId && activeSearchTerm.length > 0,
  });

  // Fetch repository tasks
  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks", { repository_id: repoId }],
    queryFn: () => taskService.list({ repository_id: repoId }),
    enabled: !!repoId,
  });

  // Indexing mutation
  const indexMutation = useMutation({
    mutationFn: () => repositoryService.triggerIndex(repoId, undefined, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repository-architecture", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repository-files", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repository-symbols", repoId] });
    },
  });

  // Fetch repository branches
  const {
    data: branches = [],
    isLoading: branchesLoading,
  } = useQuery({
    queryKey: ["repository-branches", repoId],
    queryFn: () => githubService.listRepositoryBranches(repoId),
    enabled: !!repoId,
  });

  // Fetch pull requests
  const {
    data: pullRequests = [],
    isLoading: prsLoading,
  } = useQuery({
    queryKey: ["repository-pull-requests", repoId],
    queryFn: () => githubService.listPullRequests({ repository_id: repoId }),
    enabled: !!repoId,
  });

  // Sync PR mutation
  const syncPRMutation = useMutation({
    mutationFn: (id: string) => githubService.syncPullRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository-pull-requests", repoId] });
    },
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setActiveSearchTerm(searchQuery.trim());
    }
  };

  if (repoLoading) {
    return (
      <AppLayout>
        <div className="p-16 flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
          <span className="text-xs text-muted-foreground font-mono">
            Loading repository intelligence...
          </span>
        </div>
      </AppLayout>
    );
  }

  if (repoError || !repository) {
    return (
      <AppLayout>
        <div className="p-12 text-center border border-border rounded-lg bg-card/40 max-w-lg mx-auto">
          <p className="text-sm text-destructive mb-4">
            Repository not found or access unauthorized.
          </p>
          <Link href="/repositories">
            <Button variant="outline" size="sm">
              Back to Repositories
            </Button>
          </Link>
        </div>
      </AppLayout>
    );
  }

  const isIndexed = repository.indexing_status === "INDEXED";
  const isIndexing = repository.indexing_status === "INDEXING" || indexMutation.isPending;

  return (
    <AppLayout>
      <div className="space-y-8 max-w-6xl mx-auto">
        {/* Navigation Breadcrumb & Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div className="space-y-1">
            <Link
              href="/repositories"
              className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5 font-mono mb-2"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Repositories</span>
            </Link>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                {repository.name}
              </h1>
              <Badge variant="outline" className="font-mono text-xs">
                {repository.language || "code"}
              </Badge>
              {isIndexed ? (
                <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono">
                  Indexed {repository.current_commit_sha ? `(${repository.current_commit_sha.slice(0, 7)})` : ""}
                </Badge>
              ) : isIndexing ? (
                <Badge className="bg-sky-500/10 text-sky-400 border border-sky-500/20 text-xs font-mono flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Indexing...
                </Badge>
              ) : (
                <Badge className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-mono">
                  Not Indexed
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground font-mono">{repository.full_name}</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => indexMutation.mutate()}
              disabled={isIndexing}
              className="gap-2 font-mono text-xs border-border"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isIndexing ? "animate-spin text-primary" : ""}`} />
              <span>{isIndexed ? "Re-index Repository" : "Index Repository"}</span>
            </Button>
            <Link href={`/tasks/new?repository_id=${repository.id}`}>
              <Button size="sm" className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]">
                <Plus className="w-3.5 h-3.5" />
                <span>Create Task</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Top Intelligence Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-card/40 border-border">
            <CardHeader className="p-4 pb-1">
              <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
                <span>Default Branch</span>
                <GitBranch className="w-3.5 h-3.5 text-primary" />
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-1">
              <p className="text-sm font-semibold font-mono text-foreground">{repository.default_branch}</p>
              <p className="text-[11px] text-muted-foreground font-mono">
                {repository.current_commit_sha ? `Commit: ${repository.current_commit_sha.slice(0, 8)}` : "No commits yet"}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="p-4 pb-1">
              <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
                <span>Tracked Files</span>
                <FileCode className="w-3.5 h-3.5 text-primary" />
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-1">
              <p className="text-sm font-semibold font-mono text-foreground">
                {architecture?.total_files ?? 0} files
              </p>
              <p className="text-[11px] text-muted-foreground font-mono">
                {architecture?.total_lines?.toLocaleString() ?? 0} lines of code
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="p-4 pb-1">
              <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
                <span>Ecosystem & Frameworks</span>
                <Boxes className="w-3.5 h-3.5 text-primary" />
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-1">
              <div className="flex flex-wrap gap-1">
                {(architecture?.frameworks && architecture.frameworks.length > 0) ? (
                  architecture.frameworks.map((fw) => (
                    <Badge key={fw} variant="secondary" className="text-[10px] py-0 px-1.5 font-mono">
                      {fw}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground font-mono">
                    {repository.language || "None detected"}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="p-4 pb-1">
              <CardTitle className="text-xs font-mono text-muted-foreground flex items-center justify-between">
                <span>Vector Memory</span>
                <Database className="w-3.5 h-3.5 text-primary" />
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-1">
              <p className="text-sm font-semibold font-mono text-foreground">768-dim Embeddings</p>
              <p className="text-[11px] text-muted-foreground font-mono">
                {isIndexed ? "Memory synched & searchable" : "Pending indexing"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-border text-sm font-medium">
          <button
            onClick={() => setActiveTab("architecture")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "architecture"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Architecture & Conventions</span>
          </button>

          <button
            onClick={() => setActiveTab("refactoring")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "refactoring"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Wrench className="w-4 h-4 text-cyan-400" />
            <span>Safe Refactoring</span>
          </button>

          <button
            onClick={() => setActiveTab("graph")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "graph"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Boxes className="w-4 h-4" />
            <span>Dependency Graph</span>
          </button>

          <button
            onClick={() => setActiveTab("impact")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "impact"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Flame className="w-4 h-4 text-orange-400" />
            <span>Blast Radius & Impact</span>
          </button>

          <button
            onClick={() => setActiveTab("workspaces")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "workspaces"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Boxes className="w-4 h-4 text-emerald-400" />
            <span>Workspaces & Packages</span>
          </button>

          <button
            onClick={() => setActiveTab("search")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "search"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Search className="w-4 h-4" />
            <span>Code Search</span>
          </button>

          <button
            onClick={() => setActiveTab("files")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "files"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <FileCode className="w-4 h-4" />
            <span>Files & Symbols ({files.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("tasks")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "tasks"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <CheckSquare className="w-4 h-4" />
            <span>Tasks ({tasks.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("branches")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "branches"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <GitBranch className="w-4 h-4" />
            <span>Branches ({branches.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("pull_requests")}
            className={`pb-3 px-3 flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "pull_requests"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <GitPullRequest className="w-4 h-4" />
            <span>Pull Requests ({pullRequests.length})</span>
          </button>
        </div>

        {/* Tab 1: Architecture Intelligence & Patterns */}
        {activeTab === "architecture" && (
          <ArchitectureIntelligenceTab repositoryId={repoId} />
        )}

        {/* Tab: Architecture-Aware Safe Refactoring (Stage 10.6) */}
        {activeTab === "refactoring" && (
          <RefactoringIntelligenceTab repositoryId={repoId} />
        )}

        {/* Tab: Dependency Graph */}
        {activeTab === "graph" && (
          <DependencyGraphTab repositoryId={repoId} />
        )}

        {/* Tab: Blast Radius & Impact Analysis */}
        {activeTab === "impact" && (
          <ImpactAnalysisTab repositoryId={repoId} />
        )}

        {/* Tab: Monorepo & Workspaces Intelligence */}
        {activeTab === "workspaces" && (
          <WorkspaceIntelligenceTab repositoryId={repoId} />
        )}

        {/* Tab 2: Code Search */}
        {activeTab === "search" && (
          <div className="space-y-6">
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2 text-foreground">
                  <Search className="w-4 h-4 text-primary" />
                  <span>Repository Search & Retrieval</span>
                </CardTitle>
                <CardDescription className="text-xs font-mono">
                  Multi-modal search: Exact keyword matching, AST symbol lookup, and semantic vector similarity
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search functions, classes, keywords, or concepts..."
                      className="pl-9 font-mono text-xs bg-background/80"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={searchType}
                      onChange={(e) => setSearchType(e.target.value)}
                      className="h-9 px-3 rounded-md bg-secondary border border-border text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="all">All Modes</option>
                      <option value="symbol">Symbols Only</option>
                      <option value="keyword">Keywords Only</option>
                      <option value="semantic">Semantic (Vector)</option>
                    </select>

                    <Button type="submit" size="sm" className="gap-2 font-mono text-xs">
                      {searchLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                      <span>Search</span>
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* Results Display */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                <span>
                  {activeSearchTerm
                    ? `Showing ${searchResults?.results?.length ?? 0} results for "${activeSearchTerm}" (${searchType})`
                    : "Enter a query to inspect code, symbols, or semantic concepts."}
                </span>
                {searchResults && (
                  <span>Total matches: {searchResults.total_matches}</span>
                )}
              </div>

              {searchLoading ? (
                <div className="p-12 text-center text-xs text-muted-foreground font-mono flex flex-col items-center justify-center">
                  <Loader2 className="w-6 h-6 animate-spin text-primary mb-2" />
                  <span>Searching repository index...</span>
                </div>
              ) : searchResults?.results?.length === 0 ? (
                <div className="p-8 text-center border border-dashed border-border rounded-lg bg-card/20 text-xs text-muted-foreground font-mono">
                  No matches found for "{activeSearchTerm}". Try adjusting query or search mode.
                </div>
              ) : (
                <div className="space-y-3">
                  {searchResults?.results?.map((res, idx) => (
                    <Card key={idx} className="bg-card/40 border-border hover:border-primary/40 transition-colors">
                      <CardHeader className="p-4 pb-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 truncate">
                            <FileCode className="w-4 h-4 text-primary shrink-0" />
                            <span className="text-xs font-mono font-semibold text-foreground truncate">
                              {res.file_path}
                            </span>
                            {res.line_number && (
                              <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0 shrink-0">
                                Line {res.line_number}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <Badge
                              variant="secondary"
                              className={`text-[10px] font-mono uppercase ${
                                res.match_type === "symbol"
                                  ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                  : res.match_type === "semantic"
                                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              }`}
                            >
                              {res.match_type}
                            </Badge>
                            {res.symbol_name && (
                              <Badge variant="outline" className="text-[10px] font-mono">
                                {res.symbol_name}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="p-4 pt-1">
                        <pre className="p-3 rounded-md bg-secondary/50 border border-border text-xs font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">
                          {res.snippet}
                        </pre>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Files & Symbols */}
        {activeTab === "files" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted-foreground">Category:</span>
                {["all", "source", "test", "config", "docs"].map((cat) => (
                  <Button
                    key={cat}
                    size="sm"
                    variant={fileCategoryFilter === cat ? "default" : "outline"}
                    onClick={() => setFileCategoryFilter(cat)}
                    className="text-xs font-mono capitalize h-7 px-2.5"
                  >
                    {cat}
                  </Button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted-foreground">Symbol Type:</span>
                {["all", "class", "function", "method"].map((st) => (
                  <Button
                    key={st}
                    size="sm"
                    variant={symbolFilter === st ? "secondary" : "ghost"}
                    onClick={() => setSymbolFilter(st)}
                    className="text-xs font-mono capitalize h-7 px-2"
                  >
                    {st}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Files List */}
              <Card className="bg-card/40 border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-semibold flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <FileCode className="w-4 h-4 text-primary" />
                      <span>Tracked Repository Files ({files.length})</span>
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  {filesLoading ? (
                    <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                      Loading files...
                    </div>
                  ) : files.length === 0 ? (
                    <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                      No files matching category "{fileCategoryFilter}".
                    </div>
                  ) : (
                    <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
                      {files.map((f) => (
                        <div key={f.id} className="p-3 hover:bg-secondary/30 transition-colors">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-mono font-medium text-foreground truncate">
                              {f.file_path}
                            </span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <Badge variant="outline" className="text-[10px] font-mono py-0">
                                {f.language || "code"}
                              </Badge>
                              <span className="text-[11px] font-mono text-muted-foreground">
                                {f.lines_count} lines
                              </span>
                            </div>
                          </div>
                          {f.summary && (
                            <p className="text-[11px] text-muted-foreground font-mono mt-1 truncate">
                              {f.summary}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Symbols List */}
              <Card className="bg-card/40 border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-semibold flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-primary" />
                      <span>Extracted AST Symbols ({symbols.length})</span>
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  {symbolsLoading ? (
                    <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                      Loading symbols...
                    </div>
                  ) : symbols.length === 0 ? (
                    <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                      No symbols extracted yet.
                    </div>
                  ) : (
                    <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
                      {symbols.map((sym, idx) => (
                        <div key={idx} className="p-3 hover:bg-secondary/30 transition-colors space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-mono font-bold text-foreground truncate">
                              {sym.name}
                            </span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <Badge
                                variant="outline"
                                className="text-[10px] font-mono uppercase py-0"
                              >
                                {sym.type}
                              </Badge>
                              <span className="text-[10px] font-mono text-muted-foreground">
                                L{sym.start_line}-{sym.end_line}
                              </span>
                            </div>
                          </div>
                          <p className="text-[11px] font-mono text-primary/80 truncate">
                            {sym.signature}
                          </p>
                          <p className="text-[10px] font-mono text-muted-foreground truncate">
                            {sym.file_path}
                          </p>
                          {sym.docstring && (
                            <p className="text-[11px] text-muted-foreground/80 italic line-clamp-2 pt-1 border-t border-border/40">
                              {sym.docstring}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Tab 4: Engineering Tasks */}
        {activeTab === "tasks" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-foreground flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-primary" />
                <span>Engineering Tasks in this Repository</span>
              </h2>
              <Link href={`/tasks/new?repository_id=${repository.id}`}>
                <Button size="sm" className="gap-2">
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Task</span>
                </Button>
              </Link>
            </div>

            {tasksLoading ? (
              <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                Loading tasks...
              </div>
            ) : tasks.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg bg-card/20">
                <p className="text-xs text-muted-foreground mb-3">
                  No tasks created for this repository yet.
                </p>
                <Link href={`/tasks/new?repository_id=${repository.id}`}>
                  <Button size="sm" variant="outline">
                    Create First Task
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border border border-border rounded-lg bg-card/40 overflow-hidden">
                {tasks.map((task) => (
                  <Link
                    key={task.id}
                    href={`/tasks/${task.id}`}
                    className="p-4 flex items-center justify-between hover:bg-secondary/40 transition-colors block"
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground hover:text-primary transition-colors">
                        {task.title}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono">
                        Status: {task.status} • Branch: {task.target_branch} • Created:{" "}
                        {formatDate(task.created_at)}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab: Branches */}
        {activeTab === "branches" && (
          <div className="space-y-4">
            {branchesLoading ? (
              <div className="p-8 text-center border border-border rounded-lg bg-card/20">
                <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary mb-2" />
                <span className="text-xs text-muted-foreground font-mono">Loading branches...</span>
              </div>
            ) : branches.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg bg-card/20">
                <GitBranch className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
                <p className="text-xs text-muted-foreground">No branches discovered for this repository.</p>
              </div>
            ) : (
              <div className="divide-y divide-border border border-border rounded-lg bg-card/40 overflow-hidden">
                {branches.map((b) => (
                  <div key={b.name} className="p-4 flex items-center justify-between hover:bg-secondary/30 transition-colors">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <GitBranch className="w-4 h-4 text-primary" />
                        <span className="text-sm font-semibold font-mono text-foreground">{b.name}</span>
                        {b.is_default && (
                          <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/30">
                            Default
                          </Badge>
                        )}
                        {b.is_task_branch && (
                          <Badge variant="secondary" className="text-[10px] bg-blue-500/10 text-blue-400 border-blue-500/20">
                            Devora Task Branch
                          </Badge>
                        )}
                        {b.is_pushed && (
                          <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/20 bg-emerald-500/10">
                            Pushed to Remote
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground font-mono">
                        {b.commit_sha ? `HEAD Commit: ${b.commit_sha.slice(0, 8)}` : "Tracking branch"}
                      </p>
                    </div>
                    {b.task_id && (
                      <Link href={`/tasks/${b.task_id}`}>
                        <Button variant="ghost" size="sm" className="text-xs gap-1 text-primary hover:bg-primary/10">
                          View Task
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Button>
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab: Pull Requests */}
        {activeTab === "pull_requests" && (
          <div className="space-y-4">
            {prsLoading ? (
              <div className="p-8 text-center border border-border rounded-lg bg-card/20">
                <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary mb-2" />
                <span className="text-xs text-muted-foreground font-mono">Loading pull requests...</span>
              </div>
            ) : pullRequests.length === 0 ? (
              <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2">
                <GitPullRequest className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
                <p className="text-sm font-medium text-foreground">No Pull Requests Created Yet</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  When tasks are executed and developer approval is granted, Devora AI automatically commits changes, pushes the task branch, and opens an audit-ready Pull Request.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {pullRequests.map((pr) => (
                  <Card key={pr.id} className="bg-card/40 border-border hover:border-primary/40 transition-all">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-foreground flex items-center gap-1.5">
                              <GitPullRequest className="w-4 h-4 text-primary" />
                              #{pr.pr_number} {pr.title}
                            </span>
                            {pr.state === "open" && (
                              <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-xs">
                                Open
                              </Badge>
                            )}
                            {pr.is_merged && (
                              <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-xs">
                                Merged
                              </Badge>
                            )}
                            {pr.state === "closed" && !pr.is_merged && (
                              <Badge variant="outline" className="text-xs text-muted-foreground">
                                Closed
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs font-mono text-muted-foreground flex items-center gap-2">
                            <span>Branch: <span className="text-foreground">{pr.head_branch}</span></span>
                            <span>&rarr;</span>
                            <span>Base: <span className="text-foreground">{pr.base_branch}</span></span>
                            <span>•</span>
                            <span>Created: {formatDate(pr.created_at)}</span>
                          </div>
                          {pr.merge_commit_sha && (
                            <div className="text-[11px] font-mono text-purple-400">
                              Merge Commit: {pr.merge_commit_sha.slice(0, 8)}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => syncPRMutation.mutate(pr.id)}
                            disabled={syncPRMutation.isPending}
                            className="text-xs h-8 gap-1.5"
                          >
                            <RefreshCw className={`w-3 h-3 ${syncPRMutation.isPending ? "animate-spin" : ""}`} />
                            Sync Status
                          </Button>
                          <Link href={`/tasks/${pr.task_id}`}>
                            <Button variant="ghost" size="sm" className="text-xs h-8">
                              View Task
                            </Button>
                          </Link>
                          <a
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                          >
                            <span>Open on GitHub</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

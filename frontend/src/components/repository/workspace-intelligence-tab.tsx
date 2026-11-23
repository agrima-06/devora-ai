"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Code2,
  FolderTree,
  GitBranch,
  Layers,
  Loader2,
  Package,
  RefreshCw,
  Search,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { workspaceService } from "@/services/workspace-service";
import {
  PackageDependenciesResponse,
  PackageImpactResponse,
  PackageInfo,
  WorkspaceGraphResponse,
} from "@/types";

interface WorkspaceIntelligenceTabProps {
  repositoryId: string;
}

export function WorkspaceIntelligenceTab({ repositoryId }: WorkspaceIntelligenceTabProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLanguage, setSelectedLanguage] = useState<string>("all");
  const [selectedPackage, setSelectedPackage] = useState<PackageInfo | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<"deps" | "impact">("deps");

  // Fetch workspaces & packages topology
  const {
    data: graphData,
    isLoading,
    isError,
    refetch,
  } = useQuery<WorkspaceGraphResponse>({
    queryKey: ["repository-workspaces", repositoryId],
    queryFn: () => workspaceService.getWorkspaces(repositoryId),
  });

  // Re-index mutation
  const indexMutation = useMutation({
    mutationFn: () => workspaceService.indexWorkspaces(repositoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository-workspaces", repositoryId] });
      refetch();
    },
  });

  // Package dependencies query
  const {
    data: pkgDeps,
    isLoading: isLoadingDeps,
  } = useQuery<PackageDependenciesResponse>({
    queryKey: ["package-dependencies", repositoryId, selectedPackage?.id || selectedPackage?.name],
    queryFn: () =>
      workspaceService.getPackageDependencies(
        repositoryId,
        selectedPackage?.id || selectedPackage!.name
      ),
    enabled: !!selectedPackage,
  });

  // Package impact query
  const {
    data: pkgImpact,
    isLoading: isLoadingImpact,
  } = useQuery<PackageImpactResponse>({
    queryKey: ["package-impact", repositoryId, selectedPackage?.id || selectedPackage?.name],
    queryFn: () =>
      workspaceService.getPackageImpact(
        repositoryId,
        selectedPackage?.id || selectedPackage!.name
      ),
    enabled: !!selectedPackage && activeSubTab === "impact",
  });

  // Flatten all packages across workspaces
  const allPackages: PackageInfo[] = React.useMemo(() => {
    if (!graphData?.workspaces) return [];
    return graphData.workspaces.flatMap((ws) => ws.packages);
  }, [graphData]);

  // Unique languages
  const availableLanguages = React.useMemo(() => {
    const langs = new Set<string>();
    allPackages.forEach((p) => {
      if (p.language) langs.add(p.language);
    });
    return Array.from(langs);
  }, [allPackages]);

  // Filtered packages
  const filteredPackages = React.useMemo(() => {
    return allPackages.filter((p) => {
      const matchesSearch =
        searchQuery === "" ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.path.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesLang =
        selectedLanguage === "all" || p.language.toLowerCase() === selectedLanguage.toLowerCase();
      return matchesSearch && matchesLang;
    });
  }, [allPackages, searchQuery, selectedLanguage]);

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-5 rounded-xl border bg-card shadow-sm">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-lg bg-primary/10 text-primary">
            <Boxes className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight">Monorepo & Workspace Intelligence</h2>
              {graphData?.summary.is_monorepo ? (
                <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-700">
                  Monorepo Detected
                </Badge>
              ) : (
                <Badge variant="outline">Single Project</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-0.5">
              Multi-package topology, cross-package dependency resolution, and boundary blast radius.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || indexMutation.isPending}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            size="sm"
            onClick={() => indexMutation.mutate()}
            disabled={indexMutation.isPending}
            className="shadow-sm"
          >
            {indexMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Zap className="w-4 h-4 mr-2" />
            )}
            Scan & Index Workspaces
          </Button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="shadow-none border">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase font-medium">Workspaces</CardDescription>
            <CardTitle className="text-2xl font-bold">
              {graphData?.summary.total_workspaces ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" />
            Roots & Multi-project configs
          </CardContent>
        </Card>

        <Card className="shadow-none border">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase font-medium">Discovered Packages</CardDescription>
            <CardTitle className="text-2xl font-bold text-primary">
              {graphData?.summary.total_packages ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Package className="w-3.5 h-3.5" />
            Discrete modules & crates
          </CardContent>
        </Card>

        <Card className="shadow-none border">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase font-medium">Cross-Package Links</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-600">
              {graphData?.cross_package_edges.length ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-1.5">
            <GitBranch className="w-3.5 h-3.5" />
            Internal dependencies
          </CardContent>
        </Card>

        <Card className="shadow-none border">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase font-medium">Ecosystems</CardDescription>
            <div className="flex flex-wrap gap-1 mt-1">
              {(graphData?.summary.ecosystems || []).length > 0 ? (
                graphData?.summary.ecosystems.map((eco) => (
                  <Badge key={eco} variant="secondary" className="text-[10px] uppercase font-mono px-1.5">
                    {eco}
                  </Badge>
                ))
              ) : (
                <span className="text-sm font-semibold text-muted-foreground">None</span>
              )}
            </div>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            Multi-language discovery
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Package List & Details/Blast Radius Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Packages Browser */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="border shadow-none">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold">Packages Directory</CardTitle>
                <Badge variant="outline" className="font-mono text-xs">
                  {filteredPackages.length} of {allPackages.length}
                </Badge>
              </div>
              <div className="flex flex-col sm:flex-row gap-2 pt-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                  <Input
                    placeholder="Filter by name or path..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 h-9 text-sm"
                  />
                </div>
                {availableLanguages.length > 1 && (
                  <div className="flex gap-1 overflow-x-auto pb-1">
                    <Button
                      variant={selectedLanguage === "all" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedLanguage("all")}
                      className="h-9 text-xs"
                    >
                      All
                    </Button>
                    {availableLanguages.map((lang) => (
                      <Button
                        key={lang}
                        variant={selectedLanguage === lang ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSelectedLanguage(lang)}
                        className="h-9 text-xs capitalize"
                      >
                        {lang}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent className="space-y-2.5 max-h-[620px] overflow-y-auto pt-0">
              {isLoading ? (
                <div className="py-12 flex flex-col items-center justify-center text-muted-foreground text-sm">
                  <Loader2 className="w-6 h-6 animate-spin mb-2" />
                  Scanning workspaces...
                </div>
              ) : filteredPackages.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground text-sm border rounded-lg border-dashed p-6">
                  <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  No packages match the current filter or repository has not been indexed yet.
                  <div className="mt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => indexMutation.mutate()}
                      disabled={indexMutation.isPending}
                    >
                      Detect Now
                    </Button>
                  </div>
                </div>
              ) : (
                filteredPackages.map((pkg) => {
                  const isSelected =
                    selectedPackage?.name === pkg.name ||
                    (selectedPackage?.id && selectedPackage.id === pkg.id);
                  return (
                    <div
                      key={pkg.id || pkg.name}
                      onClick={() => setSelectedPackage(pkg)}
                      className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                        isSelected
                          ? "border-primary bg-primary/5 shadow-xs"
                          : "hover:border-primary/40 hover:bg-muted/40"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-sm truncate">{pkg.name}</h4>
                            {pkg.version && (
                              <Badge variant="secondary" className="text-[10px] font-mono h-4 px-1">
                                v{pkg.version}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1 truncate">
                            <FolderTree className="w-3 h-3 shrink-0" />
                            <span className="truncate">{pkg.path}</span>
                          </div>
                        </div>

                        <Badge
                          variant="outline"
                          className="text-[10px] font-mono uppercase shrink-0"
                        >
                          {pkg.language}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-3 mt-3 pt-2.5 border-t text-[11px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Code2 className="w-3 h-3" />
                          {pkg.files_count} files
                        </span>
                        <span className="flex items-center gap-1">
                          <GitBranch className="w-3 h-3 text-emerald-500" />
                          {pkg.internal_dependencies.length} internal deps
                        </span>
                        <span className="flex items-center gap-1">
                          <Package className="w-3 h-3 text-muted-foreground" />
                          {pkg.external_dependencies.length} external
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Package Details & Blast Radius Pane */}
        <div className="lg:col-span-7 space-y-4">
          {selectedPackage ? (
            <Card className="border shadow-none">
              <CardHeader className="pb-3 border-b">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Package className="w-5 h-5 text-primary" />
                      <CardTitle className="text-lg font-bold">{selectedPackage.name}</CardTitle>
                      {selectedPackage.version && (
                        <Badge variant="secondary" className="font-mono text-xs">
                          v{selectedPackage.version}
                        </Badge>
                      )}
                    </div>
                    <CardDescription className="text-xs mt-1">
                      Path: <span className="font-mono">{selectedPackage.path}</span> • Manifest:{" "}
                      <span className="font-mono">{selectedPackage.manifest_path}</span>
                    </CardDescription>
                  </div>

                  <div className="flex items-center gap-1 bg-muted p-1 rounded-lg">
                    <Button
                      variant={activeSubTab === "deps" ? "default" : "ghost"}
                      size="sm"
                      onClick={() => setActiveSubTab("deps")}
                      className="h-7 text-xs font-medium"
                    >
                      Dependencies
                    </Button>
                    <Button
                      variant={activeSubTab === "impact" ? "default" : "ghost"}
                      size="sm"
                      onClick={() => setActiveSubTab("impact")}
                      className="h-7 text-xs font-medium"
                    >
                      Blast Radius & Impact
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="pt-4">
                {activeSubTab === "deps" ? (
                  /* Dependencies Subtab */
                  <div className="space-y-6">
                    {isLoadingDeps ? (
                      <div className="py-12 flex justify-center text-muted-foreground text-sm">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        Resolving package dependencies...
                      </div>
                    ) : (
                      <>
                        {/* Downstream Consumers (Dependents) */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold flex items-center gap-1.5 text-foreground">
                              <ArrowRight className="w-4 h-4 text-emerald-500" />
                              Downstream Consumers (Dependents)
                            </h4>
                            <Badge variant="outline" className="text-xs">
                              {pkgDeps?.dependents.length ?? 0} packages
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mb-2">
                            Other internal workspace packages that depend on{" "}
                            <span className="font-medium text-foreground">{selectedPackage.name}</span>.
                          </p>

                          {(pkgDeps?.dependents || []).length === 0 ? (
                            <div className="p-4 border rounded-lg text-xs text-muted-foreground bg-muted/20">
                              No internal packages depend directly on this package. It operates as a leaf or top-level application.
                            </div>
                          ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {pkgDeps?.dependents.map((dep) => (
                                <div
                                  key={dep.id || dep.name}
                                  className="p-2.5 rounded-lg border bg-muted/20 flex items-center justify-between text-xs"
                                >
                                  <div className="min-w-0">
                                    <div className="font-medium truncate">{dep.name}</div>
                                    <div className="text-[11px] text-muted-foreground truncate">{dep.path}</div>
                                  </div>
                                  <Badge variant="secondary" className="text-[10px] font-mono">
                                    {dep.language}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Internal Dependencies */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold flex items-center gap-1.5 text-foreground">
                              <GitBranch className="w-4 h-4 text-primary" />
                              Internal Workspace Dependencies
                            </h4>
                            <Badge variant="outline" className="text-xs">
                              {pkgDeps?.internal_dependencies.length ?? 0} packages
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mb-2">
                            Internal workspace packages consumed by this package.
                          </p>

                          {(pkgDeps?.internal_dependencies || []).length === 0 ? (
                            <div className="p-4 border rounded-lg text-xs text-muted-foreground bg-muted/20">
                              No internal workspace packages depended upon.
                            </div>
                          ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {pkgDeps?.internal_dependencies.map((idep) => (
                                <div
                                  key={idep.id || idep.name}
                                  className="p-2.5 rounded-lg border bg-muted/20 flex items-center justify-between text-xs"
                                >
                                  <div className="min-w-0">
                                    <div className="font-medium truncate">{idep.name}</div>
                                    <div className="text-[11px] text-muted-foreground truncate">{idep.path}</div>
                                  </div>
                                  <Badge variant="outline" className="text-[10px] font-mono">
                                    {idep.language}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* External Dependencies */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold flex items-center gap-1.5 text-foreground">
                              <Boxes className="w-4 h-4 text-muted-foreground" />
                              External 3rd-Party Dependencies
                            </h4>
                            <Badge variant="outline" className="text-xs">
                              {pkgDeps?.external_dependencies.length ?? 0} libraries
                            </Badge>
                          </div>

                          <div className="max-h-48 overflow-y-auto border rounded-lg p-2.5 bg-muted/10">
                            <div className="flex flex-wrap gap-1.5">
                              {(pkgDeps?.external_dependencies || []).map((ext) => (
                                <Badge key={ext} variant="secondary" className="text-xs font-mono py-0.5">
                                  {ext}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  /* Impact Analysis Subtab */
                  <div className="space-y-4">
                    {isLoadingImpact ? (
                      <div className="py-12 flex justify-center text-muted-foreground text-sm">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        Calculating package blast radius...
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between p-4 rounded-lg border bg-muted/20">
                          <div>
                            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                              Downstream Blast Radius
                            </span>
                            <div className="text-xl font-bold mt-0.5">
                              {pkgImpact?.affected_packages_count ?? 0} Affected Packages
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Across ~{pkgImpact?.affected_files_count ?? 0} consumer source files
                            </p>
                          </div>

                          <Badge
                            variant={
                              pkgImpact?.severity === "CRITICAL"
                                ? "destructive"
                                : pkgImpact?.severity === "HIGH"
                                ? "destructive"
                                : pkgImpact?.severity === "MEDIUM"
                                ? "default"
                                : "outline"
                            }
                            className="text-xs uppercase font-bold px-3 py-1"
                          >
                            {pkgImpact?.severity ?? "LOW"} SEVERITY
                          </Badge>
                        </div>

                        {/* Affected Packages Tree */}
                        <div>
                          <h4 className="text-sm font-semibold mb-2">Impact Propagation Chain</h4>
                          {(pkgImpact?.affected_packages || []).length === 0 ? (
                            <div className="p-4 border rounded-lg text-xs text-muted-foreground bg-muted/10">
                              <CheckCircle2 className="w-4 h-4 text-emerald-500 inline mr-1.5" />
                              Zero downstream internal consumers. Modifying this package will not break other packages in the repository.
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {pkgImpact?.affected_packages.map((aff) => (
                                <div
                                  key={aff.package_name}
                                  className="p-3 rounded-lg border bg-card flex flex-col gap-1.5 text-xs"
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="font-semibold text-foreground flex items-center gap-1.5">
                                      <Package className="w-3.5 h-3.5 text-primary" />
                                      {aff.package_name}
                                    </div>
                                    <Badge variant="outline" className="text-[10px]">
                                      Hop Depth: {aff.depth}
                                    </Badge>
                                  </div>
                                  <div className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono truncate">
                                    {aff.dependency_path.map((step, idx) => (
                                      <React.Fragment key={idx}>
                                        <span className={idx === aff.dependency_path.length - 1 ? "text-primary font-bold" : ""}>
                                          {step}
                                        </span>
                                        {idx < aff.dependency_path.length - 1 && (
                                          <ChevronRight className="w-3 h-3 shrink-0 text-muted-foreground" />
                                        )}
                                      </React.Fragment>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Recommendations */}
                        <div>
                          <h4 className="text-sm font-semibold mb-2">Engineering Recommendations</h4>
                          <div className="space-y-1.5">
                            {(pkgImpact?.recommendations || []).map((rec, i) => (
                              <div
                                key={i}
                                className="p-2.5 rounded-lg border bg-muted/20 text-xs flex items-start gap-2"
                              >
                                <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
                                <span>{rec}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="border border-dashed shadow-none py-20 flex flex-col items-center justify-center text-center text-muted-foreground">
              <Package className="w-10 h-10 mb-3 opacity-40 text-muted-foreground" />
              <h3 className="font-semibold text-base text-foreground">Select a Package</h3>
              <p className="text-xs max-w-sm mt-1">
                Choose any package from the left directory to inspect its upstream dependencies, downstream consumers, and compute change blast radius.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  GitBranch,
  Plus,
  RefreshCw,
  Search,
  ExternalLink,
  Code,
  Shield,
  Layers,
  ArrowRight,
  AlertCircle,
  Loader2,
  Database,
  CheckCircle2,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { repositoryService } from "@/services/repository-service";
import { projectService } from "@/services/project-service";
import { formatDate } from "@/lib/utils";

const addRepoSchema = z.object({
  name: z.string().min(1, "Repository name is required"),
  fullName: z.string().min(1, "Full name (e.g., org/repo) is required"),
  cloneUrl: z.string().url("Valid clone URL is required"),
  defaultBranch: z.string().default("main"),
  language: z.string().min(1, "Primary language is required"),
});

type AddRepoFormData = z.infer<typeof addRepoSchema>;

export default function RepositoriesPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch projects to associate repository
  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectService.list(),
  });

  // Fetch repositories
  const {
    data: repositories = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["repositories"],
    queryFn: () => repositoryService.list(),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<AddRepoFormData>({
    resolver: zodResolver(addRepoSchema),
    defaultValues: {
      defaultBranch: "main",
      language: "Python",
    },
  });

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: (id: string) => repositoryService.sync(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });

  // Index mutation
  const indexMutation = useMutation({
    mutationFn: (id: string) => repositoryService.triggerIndex(id, undefined, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });

  const onSubmit = async (data: AddRepoFormData) => {
    setFormError(null);
    try {
      let projectId = projects[0]?.id;

      // If no project exists yet, automatically initialize a default workspace project
      if (!projectId) {
        const newProj = await projectService.create({
          name: "Default Workspace",
          slug: "default-workspace",
          description: "Primary workspace for connected code repositories",
        });
        projectId = newProj.id;
        queryClient.invalidateQueries({ queryKey: ["projects"] });
      }

      await repositoryService.create({
        project_id: projectId,
        name: data.name,
        full_name: data.fullName,
        clone_url: data.cloneUrl,
        default_branch: data.defaultBranch,
        language: data.language,
      });

      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      reset();
      setIsModalOpen(false);
    } catch (err: any) {
      setFormError(err.message || "Failed to connect repository.");
    }
  };

  const filteredRepos = repositories.filter(
    (repo) =>
      repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      repo.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (repo.language && repo.language.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <AppLayout>
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Repository Management
            </h1>
            <p className="text-sm text-muted-foreground">
              Connect git repositories for autonomous code modification, AST indexing, and test
              execution.
            </p>
          </div>
          <Button
            onClick={() => setIsModalOpen(true)}
            size="sm"
            className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Connect Repository</span>
          </Button>
        </div>

        {/* Search & Stats Bar */}
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search repositories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-card/40 border-border text-xs"
            />
          </div>
          <div className="text-xs text-muted-foreground font-mono">
            Showing {filteredRepos.length} of {repositories.length} repositories
          </div>
        </div>

        {/* Repository Cards Grid */}
        {isLoading ? (
          <div className="p-16 rounded-lg border border-border bg-card/20 flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
            <span className="text-xs text-muted-foreground font-mono">Loading repositories...</span>
          </div>
        ) : filteredRepos.length === 0 ? (
          <div className="p-16 rounded-lg border border-dashed border-border bg-card/20 text-center">
            <GitBranch className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-60" />
            <h3 className="text-base font-semibold text-foreground mb-1">
              {searchQuery ? "No matching repositories" : "No repositories connected"}
            </h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
              {searchQuery
                ? "Try adjusting your search criteria."
                : "Connect a git repository to begin autonomous task planning and bug fixes."}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsModalOpen(true)} size="sm" variant="outline">
                Connect First Repository
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredRepos.map((repo) => (
              <Card
                key={repo.id}
                className="bg-card/40 border-border hover:border-primary/40 transition-all flex flex-col justify-between group"
              >
                <CardHeader className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="truncate">
                      <Link
                        href={`/repositories/${repo.id}`}
                        className="text-base font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                      >
                        <span className="truncate">{repo.name}</span>
                        <ExternalLink className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </Link>
                      <p className="text-xs text-muted-foreground font-mono truncate">
                        {repo.full_name}
                      </p>
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px] shrink-0">
                      {repo.language || "Unknown"}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono truncate text-muted-foreground">
                    Branch: <span className="text-foreground">{repo.default_branch}</span>
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4 pt-0">
                  {/* Real Indexing Status Pill */}
                  <div className="p-2.5 rounded-md bg-secondary/40 border border-border flex items-center justify-between text-[11px] font-mono">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Database className="w-3.5 h-3.5 text-primary" />
                      <span>Code Index:</span>
                    </div>
                    {repo.indexing_status === "INDEXED" ? (
                      <span className="text-emerald-400 font-medium flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Indexed {repo.current_commit_sha ? `(${repo.current_commit_sha.slice(0, 7)})` : ""}
                      </span>
                    ) : repo.indexing_status === "INDEXING" ? (
                      <span className="text-sky-400 font-medium flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Indexing...
                      </span>
                    ) : repo.indexing_status === "FAILED" ? (
                      <span className="text-rose-400 font-medium">Failed</span>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          indexMutation.mutate(repo.id);
                        }}
                        disabled={indexMutation.isPending}
                        className="text-amber-400 hover:text-amber-300 underline font-medium"
                      >
                        Index Now
                      </button>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs font-mono text-muted-foreground pt-2 border-t border-border/60">
                    <span>Synced: {formatDate(repo.last_synced_at)}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => indexMutation.mutate(repo.id)}
                        disabled={indexMutation.isPending}
                        className="hover:text-primary transition-colors text-[11px] font-mono"
                        title="Re-index repository"
                      >
                        {indexMutation.isPending ? "Indexing..." : "Re-index"}
                      </button>
                      <button
                        onClick={() => syncMutation.mutate(repo.id)}
                        disabled={syncMutation.isPending}
                        className="hover:text-primary transition-colors p-1"
                        title="Sync metadata"
                      >
                        <RefreshCw
                          className={`w-3.5 h-3.5 ${
                            syncMutation.isPending ? "animate-spin text-primary" : ""
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Modal: Connect Repository */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-card border border-border rounded-lg shadow-2xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-border pb-4">
                <div className="flex items-center gap-2.5">
                  <GitBranch className="w-5 h-5 text-primary" />
                  <h2 className="text-lg font-bold text-foreground">Connect Git Repository</h2>
                </div>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="text-muted-foreground hover:text-foreground text-sm font-mono"
                >
                  ✕
                </button>
              </div>

              {formError && (
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground">Repository Name</label>
                  <Input
                    placeholder="payment-service"
                    {...register("name")}
                    className="bg-secondary/40 font-mono text-xs"
                  />
                  {errors.name && (
                    <p className="text-[11px] text-destructive">{errors.name.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground">Full Repository Name</label>
                  <Input
                    placeholder="organization/payment-service"
                    {...register("fullName")}
                    className="bg-secondary/40 font-mono text-xs"
                  />
                  {errors.fullName && (
                    <p className="text-[11px] text-destructive">{errors.fullName.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground">Git Clone URL</label>
                  <Input
                    placeholder="https://github.com/organization/payment-service.git"
                    {...register("cloneUrl")}
                    className="bg-secondary/40 font-mono text-xs"
                  />
                  {errors.cloneUrl && (
                    <p className="text-[11px] text-destructive">{errors.cloneUrl.message}</p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground">Default Branch</label>
                    <Input
                      placeholder="main"
                      {...register("defaultBranch")}
                      className="bg-secondary/40 font-mono text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground">Primary Language</label>
                    <Input
                      placeholder="Python"
                      {...register("language")}
                      className="bg-secondary/40 font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <span>Connect Repository</span>
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

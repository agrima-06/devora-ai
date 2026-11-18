"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  ArrowLeft,
  CheckSquare,
  Bug,
  Code,
  Layers,
  Sparkles,
  AlertCircle,
  Loader2,
  GitBranch,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { repositoryService } from "@/services/repository-service";
import { taskService } from "@/services/task-service";

const createTaskSchema = z.object({
  repositoryId: z.string().min(1, "Please select a target repository"),
  title: z.string().min(3, "Task title must be at least 3 characters"),
  prompt: z.string().min(10, "Please provide detailed development instructions (min 10 chars)"),
  errorTraceback: z.string().optional(),
  taskType: z.string().default("bug_fix"),
  targetBranch: z.string().default("main"),
});

type CreateTaskFormData = z.infer<typeof createTaskSchema>;

function NewTaskForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedRepo = searchParams.get("repository_id") || "";

  const [formError, setFormError] = useState<string | null>(null);

  const { data: repositories = [], isLoading: reposLoading } = useQuery({
    queryKey: ["repositories"],
    queryFn: () => repositoryService.list(),
  });

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<CreateTaskFormData>({
    resolver: zodResolver(createTaskSchema),
    defaultValues: {
      repositoryId: preselectedRepo,
      taskType: "bug_fix",
      targetBranch: "main",
    },
  });

  const selectedType = watch("taskType");

  const onSubmit = async (data: CreateTaskFormData) => {
    setFormError(null);
    try {
      const selectedRepo = repositories.find((r) => r.id === data.repositoryId);
      if (!selectedRepo) {
        throw new Error("Selected repository not found.");
      }

      const task = await taskService.create({
        project_id: selectedRepo.project_id,
        repository_id: selectedRepo.id,
        title: data.title,
        prompt: data.prompt,
        error_traceback: data.errorTraceback || undefined,
        task_type: data.taskType,
        target_branch: data.targetBranch,
      });

      router.push(`/tasks/${task.id}`);
    } catch (err: any) {
      setFormError(err.message || "Failed to create task.");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link
        href="/tasks"
        className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5 font-mono"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Tasks</span>
      </Link>

      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Create Development Task
        </h1>
        <p className="text-sm text-muted-foreground">
          Instruct Devora AI to analyze an issue, formulate a fix plan, and execute tests.
        </p>
      </div>

      {formError && (
        <div className="p-4 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card className="bg-card/40 border-border">
          <CardHeader>
            <CardTitle className="text-base font-semibold">1. Scope & Target Repository</CardTitle>
            <CardDescription className="text-xs">
              Select which connected repository Devora should inspect and modify.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Target Repository</label>
              {reposLoading ? (
                <p className="text-xs text-muted-foreground font-mono">Loading repositories...</p>
              ) : repositories.length === 0 ? (
                <div className="p-3 rounded border border-border bg-secondary/30 text-xs text-muted-foreground">
                  No repositories connected yet.{" "}
                  <Link href="/repositories" className="text-primary hover:underline">
                    Connect a repository first
                  </Link>
                </div>
              ) : (
                <select
                  {...register("repositoryId")}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm font-mono text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">-- Select a repository --</option>
                  {repositories.map((repo) => (
                    <option key={repo.id} value={repo.id}>
                      {repo.name} ({repo.full_name})
                    </option>
                  ))}
                </select>
              )}
              {errors.repositoryId && (
                <p className="text-[11px] text-destructive">{errors.repositoryId.message}</p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">Target Branch</label>
                <Input
                  placeholder="main"
                  {...register("targetBranch")}
                  className="bg-secondary/40 font-mono text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">Task Category</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "bug_fix", label: "Bug Fix", icon: Bug },
                    { id: "feature", label: "Feature", icon: Code },
                    { id: "refactor", label: "Refactor", icon: Layers },
                    { id: "exploration", label: "Explore", icon: Sparkles },
                  ].map((type) => {
                    const Icon = type.icon;
                    const isSelected = selectedType === type.id;
                    return (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => setValue("taskType", type.id)}
                        className={`flex items-center gap-2 p-2 rounded-md border text-xs font-mono transition-all ${
                          isSelected
                            ? "bg-primary/20 border-primary text-primary"
                            : "bg-secondary/30 border-border text-muted-foreground hover:bg-secondary/60"
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        <span>{type.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/40 border-border">
          <CardHeader>
            <CardTitle className="text-base font-semibold">2. Problem Formulation</CardTitle>
            <CardDescription className="text-xs">
              Provide clear instructions, expected outcomes, and optional error tracebacks.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Task Title</label>
              <Input
                placeholder="e.g. Fix ZeroDivisionError in invoice calculation"
                {...register("title")}
                className="bg-secondary/40 text-xs"
              />
              {errors.title && (
                <p className="text-[11px] text-destructive">{errors.title.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">
                Development Request & Context
              </label>
              <Textarea
                placeholder="Describe the bug, user flow, or feature requirements in detail..."
                rows={4}
                {...register("prompt")}
                className="bg-secondary/40 text-xs font-sans leading-relaxed"
              />
              {errors.prompt && (
                <p className="text-[11px] text-destructive">{errors.prompt.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground flex items-center justify-between">
                <span>Stack Trace / Error Log (Optional)</span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  Classified by ML in Phase 3
                </span>
              </label>
              <Textarea
                placeholder="Paste error tracebacks, pytest failures, or stack traces..."
                rows={4}
                {...register("errorTraceback")}
                className="bg-secondary/40 font-mono text-xs leading-relaxed"
              />
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-3">
          <Link href="/tasks">
            <Button type="button" variant="ghost" size="sm">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            size="sm"
            disabled={isSubmitting || repositories.length === 0}
            className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Dispatching Task...</span>
              </>
            ) : (
              <>
                <CheckSquare className="w-3.5 h-3.5" />
                <span>Dispatch Task</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function NewTaskPage() {
  return (
    <AppLayout>
      <Suspense
        fallback={
          <div className="p-16 flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
            <span className="text-xs text-muted-foreground font-mono">Loading form...</span>
          </div>
        }
      >
        <NewTaskForm />
      </Suspense>
    </AppLayout>
  );
}

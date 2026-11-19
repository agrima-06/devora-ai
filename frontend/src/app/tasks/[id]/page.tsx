"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Terminal,
  Cpu,
  GitBranch,
  GitPullRequest,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Code2,
  FileCode,
  Shield,
  Layers,
  Clock,
  Ban,
  CheckSquare,
  Sparkles,
  Info,
  Loader2,
  Activity,
  Check,
  XCircle,
  FileText,
  AlertCircle,
  ExternalLink,
  Brain,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { taskService } from "@/services/task-service";
import { adaptiveService } from "@/services/adaptive-service";
import { flakyService } from "@/services/flaky-service";
import { modelService } from "@/services/model-service";
import { formatDate } from "@/lib/utils";
import { getStoredToken } from "@/lib/api-client";
import {
  AgentRun,
  FileChange,
  Report,
  Task,
  TaskPlanStep,
  TaskStatus,
  TestRun,
  WorkflowEvent,
} from "@/types";

interface SpecialistAgentMeta {
  key: string;
  name: string;
  role: string;
}

const SPECIALIST_AGENTS: SpecialistAgentMeta[] = [
  { key: "orchestrator", name: "Orchestrator Agent", role: "Workflow Supervisor" },
  { key: "codebase_analyst", name: "Codebase Analyst", role: "AST & Tree-sitter Parser" },
  { key: "bug_investigator", name: "Bug Investigator", role: "Root-Cause & ML Classifier" },
  { key: "planner", name: "Planning Agent", role: "Task Decomposition & DAG" },
  { key: "coder", name: "Coding Agent", role: "Precision Diff Author" },
  { key: "tester", name: "Testing Agent", role: "Multi-Language Sandbox Test Runner" },
  { key: "code_reviewer", name: "Code Reviewer", role: "Ruff & Mypy Static Quality" },
  { key: "security_reviewer", name: "Security Reviewer", role: "Semgrep OWASP Rules" },
  { key: "reporter", name: "Reporting Agent", role: "Engineering Synthesis" },
];

export default function AgentWorkspacePage() {
  const params = useParams();
  const taskId = params.id as string;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"plan" | "diff" | "tests" | "terminal" | "report">("plan");
  const [approvalNotes, setApprovalNotes] = useState("");
  const [streamEvents, setStreamEvents] = useState<WorkflowEvent[]>([]);
  const [sseConnected, setSseConnected] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Adaptive feedback state
  const [feedbackRating, setFeedbackRating] = useState<"ACCEPTED" | "REJECTED" | "NEEDS_CHANGES">("ACCEPTED");
  const [feedbackComments, setFeedbackComments] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const feedbackMutation = useMutation({
    mutationFn: () =>
      adaptiveService.submitFeedback({
        task_id: taskId,
        rating: feedbackRating,
        plan_accepted: feedbackRating === "ACCEPTED",
        code_accepted: feedbackRating === "ACCEPTED",
        solution_helpful: feedbackRating !== "REJECTED",
        comments: feedbackComments,
      }),
    onSuccess: () => {
      setFeedbackSubmitted(true);
      queryClient.invalidateQueries({ queryKey: ["adaptive-experiences"] });
    },
  });

  // 1. Fetch Task Details
  const {
    data: task,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => taskService.get(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "IN_PROGRESS" || status === "PLANNING" || status === "TESTING" ? 2500 : false;
    },
  });

  // 2. Fetch Agent Runs
  const { data: runs = [] } = useQuery({
    queryKey: ["task-runs", taskId],
    queryFn: () => taskService.getRuns(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = task?.status;
      return status === "IN_PROGRESS" || status === "PLANNING" || status === "TESTING" ? 2500 : false;
    },
  });

  // 3. Fetch Diffs
  const { data: diffs = [] } = useQuery({
    queryKey: ["task-diffs", taskId],
    queryFn: () => taskService.getDiff(taskId),
    enabled: !!taskId,
  });

  // 4. Fetch Test Runs
  const { data: tests = [] } = useQuery({
    queryKey: ["task-tests", taskId],
    queryFn: () => taskService.getTests(taskId),
    enabled: !!taskId,
  });

  // 4b. Fetch Flaky Tests (Phase 9 Stage 9.2)
  const { data: flakyTests = [] } = useQuery({
    queryKey: ["task-flaky-tests", taskId],
    queryFn: () => flakyService.getTaskFlakyTests(taskId),
    enabled: !!taskId,
  });

  // 5. Fetch Final Report
  const { data: report } = useQuery({
    queryKey: ["task-report", taskId],
    queryFn: () => taskService.getReport(taskId),
    enabled: !!taskId && (task?.status === "COMPLETED" || task?.status === "WAITING_APPROVAL"),
    retry: false,
  });

  // 5b. Fetch Recovery Diagnostics (Phase 9 Stage 9.4)
  const { data: recoveryInfo } = useQuery({
    queryKey: ["task-recovery", taskId],
    queryFn: () => taskService.getRecoveryStatus(taskId),
    enabled: !!taskId,
  });

  // 5c. Fetch Model Gateway Health (Phase 9 Stage 9.5)
  const { data: modelHealth, refetch: refetchModelHealth } = useQuery({
    queryKey: ["model-health"],
    queryFn: () => modelService.getHealth(),
    refetchInterval: 15000,
  });

  const resetBreakerMutation = useMutation({
    mutationFn: ({ provider, model }: { provider: string; model: string }) =>
      modelService.resetBreaker(provider, model),
    onSuccess: () => {
      refetchModelHealth();
    },
  });

  // 6. Connect to SSE Live Stream
  useEffect(() => {
    if (!taskId) return;

    let aborted = false;
    const token = getStoredToken();
    const abortController = new AbortController();

    async function listenSSE() {
      try {
        const response = await fetch(`/api/v1/tasks/${taskId}/events`, {
          headers: {
            Authorization: token ? `Bearer ${token}` : "",
          },
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          setSseConnected(false);
          return;
        }

        setSseConnected(true);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!aborted) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const chunk of lines) {
            const dataMatch = chunk.match(/data:\s*(.*)/);
            if (dataMatch) {
              try {
                const parsed: WorkflowEvent = JSON.parse(dataMatch[1]);
                setStreamEvents((prev) => [...prev, parsed]);

                // Invalidate relevant queries when important events arrive
                if (
                  parsed.event_type.includes("COMPLETED") ||
                  parsed.event_type.includes("APPROVAL") ||
                  parsed.event_type.includes("RECOVERY") ||
                  parsed.event_type.includes("MODEL_") ||
                  parsed.event_type === "FAILED"
                ) {
                  queryClient.invalidateQueries({ queryKey: ["task", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-runs", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-diffs", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-tests", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-flaky-tests", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-recovery", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["task-report", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["model-health"] });
                }
              } catch {
                // Ignore parse errors on ping/keep-alive lines
              }
            }
          }
        }
      } catch (err: any) {
        if (!aborted) {
          setSseConnected(false);
        }
      }
    }

    listenSSE();

    return () => {
      aborted = true;
      abortController.abort();
    };
  }, [taskId, queryClient]);

  // Auto scroll terminal
  useEffect(() => {
    if (activeTab === "terminal") {
      terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [streamEvents, activeTab]);

  // Mutations
  const startWorkflowMutation = useMutation({
    mutationFn: () => taskService.startWorkflow(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-runs", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-recovery", taskId] });
      setActiveTab("terminal");
    },
  });

  const resumeWorkflowMutation = useMutation({
    mutationFn: (force?: boolean) => taskService.resume(taskId, !!force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-runs", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-recovery", taskId] });
      setActiveTab("terminal");
    },
  });

  const approvalMutation = useMutation({
    mutationFn: ({ action, notes }: { action: "APPROVE" | "REJECT" | "REQUEST_CHANGES"; notes?: string }) =>
      taskService.submitApproval(taskId, action, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-runs", taskId] });
      queryClient.invalidateQueries({ queryKey: ["task-report", taskId] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => taskService.cancel(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  if (isLoading) {
    return (
      <AppLayout>
        <div className="p-16 flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
          <span className="text-xs text-muted-foreground font-mono">
            Loading Agent Workspace...
          </span>
        </div>
      </AppLayout>
    );
  }

  if (error || !task) {
    return (
      <AppLayout>
        <div className="p-12 text-center border border-border rounded-lg bg-card/40 max-w-lg mx-auto">
          <p className="text-sm text-destructive mb-4">Task not found or unauthorized.</p>
          <Link href="/tasks">
            <Button variant="outline" size="sm">
              Back to Task Registry
            </Button>
          </Link>
        </div>
      </AppLayout>
    );
  }

  // Derive agent states from executed runs
  const completedAgentNames = new Set(runs.map((r) => r.agent_name));
  const isRunning = task.status === "IN_PROGRESS" || task.status === "PLANNING" || task.status === "TESTING";

  return (
    <AppLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Workspace Top Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div className="space-y-1">
            <Link
              href="/tasks"
              className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5 font-mono mb-2"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Task Registry</span>
            </Link>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-mono text-muted-foreground font-semibold">
                TASK-{task.id.substring(0, 8)}
              </span>
              <h1 className="text-xl font-bold tracking-tight text-foreground">{task.title}</h1>
              <Badge variant="outline" className="font-mono text-xs">
                {task.task_type}
              </Badge>
              <Badge variant="outline" className="font-mono text-xs text-primary border-primary/30 bg-primary/5 flex items-center gap-1">
                <GitBranch className="w-3 h-3" />
                {task.task_branch || `devora/${task.task_type.replace('_', '')}-${task.id.slice(0, 8)}`}
              </Badge>
              {task.commit_sha && (
                <Badge variant="secondary" className="font-mono text-xs">
                  SHA: {task.commit_sha.slice(0, 8)}
                </Badge>
              )}
              <Badge
                variant={
                  task.status === "COMPLETED"
                    ? "success"
                    : task.status === "WAITING_APPROVAL"
                    ? "warning"
                    : task.status === "CANCELLED" || task.status === "FAILED"
                    ? "destructive"
                    : "secondary"
                }
                className="font-mono text-xs"
              >
                {task.status}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground font-mono">
              Target Branch: <span className="text-foreground">{task.target_branch}</span> • Created:{" "}
              {formatDate(task.created_at)}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Start / Run Autonomous Workflow Button */}
            {(task.status === "PENDING" || (task.status === "PLANNING" && !recoveryInfo?.is_eligible_for_recovery)) && (
              <Button
                variant="default"
                size="sm"
                onClick={() => startWorkflowMutation.mutate()}
                disabled={startWorkflowMutation.isPending || isRunning}
                className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
              >
                {startWorkflowMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 fill-current" />
                )}
                <span>Start Multi-Agent Workflow</span>
              </Button>
            )}

            {recoveryInfo?.is_eligible_for_recovery && task.status !== "COMPLETED" && task.status !== "WAITING_APPROVAL" && !isRunning && (
              <Button
                variant="default"
                size="sm"
                onClick={() => resumeWorkflowMutation.mutate(false)}
                disabled={resumeWorkflowMutation.isPending}
                className="gap-2 bg-orange-600 hover:bg-orange-700 text-white font-medium shadow-sm"
              >
                {resumeWorkflowMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="w-3.5 h-3.5" />
                )}
                <span>Resume Interrupted Task</span>
              </Button>
            )}

            {isRunning && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10 border border-primary/30 text-xs font-mono text-primary animate-pulse">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Workflow Running</span>
              </div>
            )}

            {task.status !== "CANCELLED" && task.status !== "COMPLETED" && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="gap-2"
              >
                {cancelMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Ban className="w-3.5 h-3.5" />
                )}
                <span>Cancel</span>
              </Button>
            )}
          </div>
        </div>

        {/* Pull Request Card if Created */}
        {task.pull_request_url && (
          <div className="p-4 rounded-lg bg-primary/10 border border-primary/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-md bg-primary/20 text-primary shrink-0">
                <GitPullRequest className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  GitHub Pull Request Created
                  <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/20 bg-emerald-500/10">
                    Active on Remote
                  </Badge>
                </h4>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  Branch <span className="text-foreground">{task.task_branch || `devora/bugfix-${task.id.slice(0, 8)}`}</span> &rarr;{" "}
                  <span className="text-foreground">{task.target_branch}</span> • Verified via isolated Docker sandbox
                </p>
              </div>
            </div>
            <a
              href={task.pull_request_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors shadow-sm shrink-0"
            >
              <span>View Pull Request on GitHub</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}

        {/* Interrupted Workflow Recovery Banner */}
        {((recoveryInfo?.is_interrupted) || task.recovery_status === "INTERRUPTED" || (task.status === "FAILED" && recoveryInfo?.is_eligible_for_recovery)) && task.status !== "COMPLETED" && task.status !== "WAITING_APPROVAL" && (
          <div className="p-5 rounded-lg bg-orange-500/10 border border-orange-500/30 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-md bg-orange-500/20 flex items-center justify-center text-orange-400 shrink-0 mt-0.5">
                  <RotateCcw className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    Interrupted Workflow Detected
                    <Badge variant="outline" className="text-orange-400 border-orange-500/30 bg-orange-500/10 text-[10px]">
                      {task.recovery_status || "INTERRUPTED"}
                    </Badge>
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {recoveryInfo?.interruption_reason || task.recovery_error || "Workflow execution was interrupted before completion."}
                  </p>
                  {recoveryInfo?.latest_checkpoint && (
                    <div className="text-xs font-mono text-foreground/80 mt-2 flex flex-wrap items-center gap-3">
                      <span>Last Checkpoint: <strong className="text-primary">{recoveryInfo.latest_checkpoint.node_name || "checkpoint"}</strong> (Step {recoveryInfo.latest_checkpoint.step_number})</span>
                      <span>•</span>
                      <span>Recovery Attempts: {recoveryInfo.recovery_attempts} / {recoveryInfo.max_recovery_attempts}</span>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {recoveryInfo?.is_eligible_for_recovery ? (
                  <Button
                    size="sm"
                    onClick={() => resumeWorkflowMutation.mutate(false)}
                    disabled={resumeWorkflowMutation.isPending}
                    className="bg-orange-600 hover:bg-orange-700 text-white gap-1.5 text-xs font-semibold shadow-sm"
                  >
                    {resumeWorkflowMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RotateCcw className="w-3.5 h-3.5" />
                    )}
                    <span>Resume Workflow</span>
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => resumeWorkflowMutation.mutate(true)}
                    disabled={resumeWorkflowMutation.isPending}
                    className="border-orange-500/30 text-orange-400 hover:bg-orange-500/10 gap-1.5 text-xs font-semibold"
                  >
                    {resumeWorkflowMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RotateCcw className="w-3.5 h-3.5" />
                    )}
                    <span>Force Resume</span>
                  </Button>
                )}
              </div>
            </div>
            {resumeWorkflowMutation.isError && (
              <p className="text-xs text-destructive font-mono">
                Resume failed: {(resumeWorkflowMutation.error as any)?.message || "Unknown error"}
              </p>
            )}
          </div>
        )}

        {/* Human Approval Gate Alert Banner */}
        {task.status === "WAITING_APPROVAL" && (
          <div className="p-5 rounded-lg bg-amber-500/10 border border-amber-500/30 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-md bg-amber-500/20 flex items-center justify-center text-amber-400 shrink-0 mt-0.5">
                  <Shield className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    Human Authorization Required
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    The 9-agent workflow has analyzed the repository, created and applied code changes, and verified that all tests pass in the isolated Docker container. Authorizing will sign & commit changes on branch <span className="font-mono text-foreground font-bold">{task.task_branch || `devora/fix-${task.id.slice(0, 8)}`}</span>, push to GitHub, and open an audit-ready Pull Request.
                  </p>
                </div>
              </div>
              <Badge variant="outline" className="text-amber-400 border-amber-500/30 bg-amber-500/5 font-mono text-xs shrink-0">
                Awaiting Developer Decision
              </Badge>
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2 border-t border-amber-500/20">
              <input
                type="text"
                placeholder="Optional review notes (e.g. LGTM, verified test coverage)..."
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                className="text-xs bg-background/80 border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary flex-1"
              />
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => approvalMutation.mutate({ action: "APPROVE", notes: approvalNotes })}
                  disabled={approvalMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 text-xs font-semibold"
                >
                  {approvalMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <GitPullRequest className="w-3.5 h-3.5" />
                  )}
                  <span>Approve & Open Pull Request</span>
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => approvalMutation.mutate({ action: "REJECT", notes: approvalNotes })}
                  disabled={approvalMutation.isPending}
                  className="gap-1.5 text-xs"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Reject Changes</span>
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Multi-Panel IDE Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel: Specialist Agent Roster & History (1 col) */}
          <div className="space-y-4">
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-xs font-mono uppercase tracking-wider text-muted-foreground flex items-center justify-between">
                  <span>Specialist Agents</span>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        sseConnected ? "bg-emerald-400" : "bg-muted-foreground"
                      }`}
                    />
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {sseConnected ? "Live SSE" : "Offline"}
                    </span>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-3 pt-0">
                {SPECIALIST_AGENTS.map((agent) => {
                  const isDone = completedAgentNames.has(agent.key);
                  const matchingRun = runs.find((r) => r.agent_name === agent.key);

                  return (
                    <div
                      key={agent.key}
                      className={`p-2.5 rounded-md border text-xs transition-colors flex items-center justify-between ${
                        isDone
                          ? "border-emerald-500/30 bg-emerald-500/5 text-foreground"
                          : isRunning
                          ? "border-primary/40 bg-primary/5 text-foreground"
                          : "border-border/80 bg-secondary/30 text-muted-foreground"
                      }`}
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          {isDone ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center shrink-0">
                              <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
                            </div>
                          )}
                          <p className="font-semibold text-foreground">{agent.name}</p>
                        </div>
                        <p className="text-[10px] text-muted-foreground font-mono pl-5">
                          {agent.role}
                        </p>
                      </div>
                      <div className="text-right">
                        {isDone ? (
                          <Badge variant="outline" className="text-[9px] font-mono text-emerald-400 border-emerald-500/30">
                            {matchingRun ? `${matchingRun.duration_ms}ms` : "Done"}
                          </Badge>
                        ) : (
                          <span className="text-[10px] font-mono text-muted-foreground">Pending</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            {/* Problem Formulation Box */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  Developer Intent
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div>
                  <span className="text-muted-foreground font-mono block text-[10px] mb-1">
                    Prompt:
                  </span>
                  <p className="p-2.5 rounded bg-secondary/40 border border-border text-foreground text-xs leading-relaxed font-sans">
                    {task.prompt}
                  </p>
                </div>

                {task.error_traceback && (
                  <div>
                    <span className="text-muted-foreground font-mono block text-[10px] mb-1">
                      Error Traceback:
                    </span>
                    <pre className="p-2.5 rounded bg-secondary/50 border border-border text-[11px] font-mono text-destructive/90 overflow-x-auto whitespace-pre-wrap">
                      {task.error_traceback}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Model Gateway Resilience Card (Phase 9 Stage 9.5) */}
            <Card className="bg-card/40 border-border">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xs font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-primary" />
                    <span>Model Gateway</span>
                  </CardTitle>
                  {modelHealth && (
                    <Badge
                      variant="outline"
                      className={`text-[9px] font-mono px-1.5 py-0 ${
                        modelHealth.status === "HEALTHY"
                          ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                          : modelHealth.status === "DEGRADED"
                          ? "border-amber-500/30 text-amber-400 bg-amber-500/10"
                          : "border-destructive/30 text-destructive bg-destructive/10"
                      }`}
                    >
                      {modelHealth.status}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs p-3 pt-0">
                {modelHealth ? (
                  <>
                    <div className="space-y-1 text-[11px] font-mono bg-secondary/30 p-2 rounded border border-border/60">
                      <div className="flex justify-between items-center text-muted-foreground">
                        <span>Active:</span>
                        <span className="text-foreground font-semibold truncate max-w-[150px]">
                          {modelHealth.active_primary_model}
                        </span>
                      </div>
                      {modelHealth.fallback_enabled && modelHealth.fallback_models.length > 0 && (
                        <div className="flex justify-between items-center text-muted-foreground">
                          <span>Fallback:</span>
                          <span className="text-foreground truncate max-w-[150px]">
                            {modelHealth.fallback_models[0]}
                          </span>
                        </div>
                      )}
                      <div className="flex justify-between items-center text-muted-foreground pt-1 border-t border-border/40">
                        <span>Retries / Fallbacks:</span>
                        <span className="text-foreground">
                          {modelHealth.metrics.total_retries} / {modelHealth.metrics.total_fallbacks}
                        </span>
                      </div>
                    </div>

                    {/* Circuit Breakers */}
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground block">
                        Circuit Breakers
                      </span>
                      {modelHealth.breakers.length === 0 ? (
                        <p className="text-[11px] text-muted-foreground italic">No breakers initialized</p>
                      ) : (
                        modelHealth.breakers.map((b) => (
                          <div
                            key={b.key}
                            className={`p-2 rounded border text-[11px] font-mono flex items-center justify-between ${
                              b.state === "OPEN"
                                ? "border-destructive/40 bg-destructive/5 text-destructive"
                                : b.state === "HALF_OPEN"
                                ? "border-amber-500/40 bg-amber-500/5 text-amber-400"
                                : "border-border/60 bg-secondary/20 text-muted-foreground"
                            }`}
                          >
                            <div className="truncate max-w-[140px]">
                              <span className="text-foreground font-medium block truncate">
                                {b.model_name}
                              </span>
                              <span className="text-[10px] text-muted-foreground">
                                {b.provider_name} &bull; {b.total_calls} calls
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Badge
                                variant="outline"
                                className={`text-[9px] px-1 py-0 ${
                                  b.state === "OPEN"
                                    ? "border-destructive text-destructive"
                                    : b.state === "HALF_OPEN"
                                    ? "border-amber-500 text-amber-400"
                                    : "border-emerald-500/40 text-emerald-400"
                                }`}
                              >
                                {b.state}
                              </Badge>
                              {b.state === "OPEN" && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-5 px-1 text-[10px] hover:bg-destructive/20 text-destructive"
                                  onClick={() =>
                                    resetBreakerMutation.mutate({
                                      provider: b.provider_name,
                                      model: b.model_name,
                                    })
                                  }
                                  disabled={resetBreakerMutation.isPending}
                                  title="Reset breaker to CLOSED"
                                >
                                  <RotateCcw className="w-3 h-3" />
                                </Button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex items-center gap-2 text-muted-foreground text-[11px] py-1">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Connecting to gateway...</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Panel: Workspace Tabs (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            {/* Tab Selector */}
            <div className="flex border-b border-border gap-4 text-xs font-mono overflow-x-auto pb-px">
              {[
                { id: "plan", label: "Task Plan", icon: Layers, count: task.plans?.[0]?.steps?.length },
                { id: "diff", label: "Code Diffs", icon: Code2, count: diffs.length },
                { id: "tests", label: "Test Results", icon: CheckCircle2, count: tests.length },
                { id: "terminal", label: "Live Terminal", icon: Terminal, count: streamEvents.length },
                { id: "report", label: "Engineering Report", icon: FileText, count: report ? 1 : 0 },
              ].map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex items-center gap-2 pb-3 transition-colors relative whitespace-nowrap ${
                      isActive
                        ? "text-primary font-semibold border-b-2 border-primary"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                    {typeof tab.count === "number" && tab.count > 0 && (
                      <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-secondary text-foreground font-mono">
                        {tab.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Tab 1: Execution Plan */}
            {activeTab === "plan" && (
              <Card className="bg-card/40 border-border">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-semibold">Autonomous Execution Plan</CardTitle>
                      <CardDescription className="text-xs">
                        Task decomposition generated by the Planning Agent.
                      </CardDescription>
                    </div>
                    {task.plans && task.plans.length > 0 && (
                      <Badge
                        variant="outline"
                        className={`font-mono text-[10px] ${
                          task.plans[0].risk_level === "HIGH"
                            ? "border-destructive text-destructive"
                            : task.plans[0].risk_level === "MEDIUM"
                            ? "border-amber-500 text-amber-500"
                            : "border-emerald-500 text-emerald-400"
                        }`}
                      >
                        Risk: {task.plans[0].risk_level}
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Adaptive Strategy & Historical Intelligence Banner */}
                  {(() => {
                    const plannerRun = runs.find((r) => r.agent_name === "planner");
                    const plannerPlan = plannerRun?.output_state?.plan;
                    const implementationStrategy =
                      plannerPlan?.implementation_strategy || (task.plans?.[0] as any)?.implementation_strategy;
                    const strategyRationale =
                      plannerPlan?.strategy_rationale || (task.plans?.[0] as any)?.strategy_rationale;
                    const historicalExperiences =
                      plannerPlan?.relevant_historical_experiences || (task.plans?.[0] as any)?.relevant_historical_experiences || [];
                    const risksAndAssumptions =
                      plannerPlan?.risks_and_assumptions || (task.plans?.[0] as any)?.risks_and_assumptions || [];

                    if (!implementationStrategy && historicalExperiences.length === 0) return null;

                    return (
                      <div className="p-3.5 rounded-lg border border-indigo-500/30 bg-indigo-500/5 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-indigo-400" />
                            <h4 className="text-xs font-semibold font-mono text-indigo-400 uppercase tracking-wider">
                              Adaptive Strategy & Historical Evidence
                            </h4>
                          </div>
                          <Link href="/adaptive" className="text-[11px] text-indigo-400 hover:underline flex items-center gap-1 font-mono">
                            <span>Adaptive Dashboard</span>
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        </div>

                        {implementationStrategy && (
                          <div>
                            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground block mb-0.5">
                              Selected Strategy:
                            </span>
                            <p className="text-xs font-medium text-foreground bg-secondary/40 p-2 rounded border border-border">
                              {implementationStrategy}
                            </p>
                          </div>
                        )}

                        {strategyRationale && (
                          <div>
                            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground block mb-0.5">
                              Strategy Rationale:
                            </span>
                            <p className="text-[11px] text-muted-foreground bg-background/50 p-2 rounded border border-border/60">
                              {strategyRationale}
                            </p>
                          </div>
                        )}

                        {historicalExperiences && historicalExperiences.length > 0 && (
                          <div className="space-y-1">
                            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground block">
                              Informed by Historical Experience:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {historicalExperiences.map((exp: string, eIdx: number) => (
                                <Badge key={eIdx} variant="outline" className="text-[10px] font-mono border-indigo-500/40 text-indigo-300 bg-indigo-500/10">
                                  {exp}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {risksAndAssumptions && risksAndAssumptions.length > 0 && (
                          <div className="space-y-1 pt-1">
                            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground block">
                              Risks & Assumptions:
                            </span>
                            <ul className="list-disc list-inside text-[11px] text-muted-foreground space-y-0.5">
                              {risksAndAssumptions.map((r: string, rIdx: number) => (
                                <li key={rIdx}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                  {task.plans && task.plans.length > 0 ? (
                    <div className="space-y-3">
                      {task.plans[0].steps.map((step: TaskPlanStep, idx: number) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-lg border border-border bg-secondary/30 flex items-start gap-3"
                        >
                          <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center font-mono text-xs font-bold shrink-0">
                            {step.step_number || idx + 1}
                          </div>
                          <div className="space-y-1.5 flex-1">
                            <p className="text-xs font-medium text-foreground">{step.description}</p>
                            {step.target_files && step.target_files.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 pt-1">
                                {step.target_files.map((file, fIdx) => (
                                  <Badge key={fIdx} variant="secondary" className="font-mono text-[10px]">
                                    <FileCode className="w-3 h-3 mr-1" />
                                    {file}
                                  </Badge>
                                ))}
                              </div>
                            )}
                            {step.verification_check && (
                              <p className="text-[11px] text-muted-foreground font-mono">
                                <span className="text-primary font-semibold">Verification:</span> {step.verification_check}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}

                      {task.plans[0].test_criteria && task.plans[0].test_criteria.length > 0 && (
                        <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-1.5 mt-4">
                          <p className="text-xs font-semibold text-foreground">Acceptance & Test Criteria:</p>
                          <ul className="list-disc list-inside text-[11px] text-muted-foreground space-y-1">
                            {task.plans[0].test_criteria.map((crit, cIdx) => (
                              <li key={cIdx}>{typeof crit === "string" ? crit : JSON.stringify(crit)}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-8 text-center border border-dashed border-border rounded-lg">
                      <Layers className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-xs font-medium text-foreground mb-1">
                        Awaiting Planning Agent Execution
                      </p>
                      <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                        Click &quot;Start Multi-Agent Workflow&quot; to begin autonomous task decomposition and execution.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Tab 2: Code Changes & Diff Viewer */}
            {activeTab === "diff" && (
              <Card className="bg-card/40 border-border">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Unified Code Diff</CardTitle>
                  <CardDescription className="text-xs">
                    Precision file modifications generated by the Coding Agent inside the sandbox.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {diffs.length > 0 ? (
                    diffs.map((change: FileChange, idx: number) => (
                      <div key={idx} className="border border-border rounded-lg overflow-hidden">
                        <div className="px-3.5 py-2 bg-secondary/60 border-b border-border flex items-center justify-between text-xs font-mono">
                          <div className="flex items-center gap-2">
                            <FileCode className="w-3.5 h-3.5 text-primary" />
                            <span className="font-semibold text-foreground">{change.file_path}</span>
                          </div>
                          <Badge variant="outline" className="text-[10px] uppercase font-mono">
                            {change.change_type}
                          </Badge>
                        </div>
                        <div className="p-3 bg-black/90 font-mono text-[11px] overflow-x-auto leading-relaxed">
                          {change.diff.split("\n").map((line, lIdx) => {
                            let lineClass = "text-muted-foreground";
                            if (line.startsWith("+") && !line.startsWith("+++")) {
                              lineClass = "text-emerald-400 bg-emerald-500/10";
                            } else if (line.startsWith("-") && !line.startsWith("---")) {
                              lineClass = "text-destructive bg-destructive/10";
                            } else if (line.startsWith("@@")) {
                              lineClass = "text-cyan-400";
                            }
                            return (
                              <div key={lIdx} className={`${lineClass} px-1 rounded`}>
                                {line || " "}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-10 text-center border border-dashed border-border rounded-lg bg-card/20">
                      <Code2 className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-xs font-medium text-foreground mb-1">
                        No Code Patches Generated Yet
                      </p>
                      <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                        Patches applied by the Coding Agent will appear here as unified diffs with line-by-line syntax styling.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Tab 3: Automated Test Results */}
            {activeTab === "tests" && (
              <Card className="bg-card/40 border-border">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-sm font-semibold">Sandbox Test Execution Evidence</CardTitle>
                      <CardDescription className="text-xs">
                        Axiom: &quot;Never claim success without execution evidence&quot; &mdash; Multi-language tests run in isolated sandbox.
                      </CardDescription>
                    </div>

                    {/* Discovered Test Metadata from SSE stream */}
                    {(() => {
                      const latestTesterEvent = [...streamEvents].reverse().find(
                        e => e.agent_name === "tester" || e.event_type === "AGENT_TESTER_COMPLETED"
                      );
                      const disc = latestTesterEvent?.payload?.test_discovery_info;
                      if (!disc) return null;
                      return (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {disc.languages?.map((lang: string, i: number) => (
                            <Badge key={i} variant="outline" className="text-[10px] uppercase font-mono bg-primary/10 text-primary border-primary/20">
                              {lang}
                            </Badge>
                          ))}
                          {disc.primary_framework && (
                            <Badge variant="outline" className="text-[10px] font-mono bg-secondary/80 text-foreground border-border">
                              {disc.primary_framework}
                            </Badge>
                          )}
                          {disc.is_targeted ? (
                            <Badge variant="outline" className="text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                              Targeted Selection
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] font-mono bg-muted text-muted-foreground border-border">
                              Full Suite
                            </Badge>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Flaky Test Intelligence Banner (Phase 9 Stage 9.2) */}
                  {flakyTests.length > 0 && (
                    <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                          <h4 className="text-xs font-semibold text-foreground">
                            Flaky Test Detected &bull; Stability Intelligence Active
                          </h4>
                        </div>
                        <Badge variant="outline" className="text-[10px] font-mono bg-amber-500/20 text-amber-300 border-amber-500/30">
                          Non-Deterministic
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        The Flaky Test Detection Engine identified test instability across controlled repeat executions. LangGraph bypassed unnecessary code modification loops to protect functional code.
                      </p>
                      <div className="space-y-2 pt-1 border-t border-amber-500/20">
                        {flakyTests.map((ft: any, i: number) => (
                          <div key={i} className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-black/40 border border-amber-500/20 text-xs font-mono">
                            <div className="flex items-center gap-2">
                              <span className="text-amber-400 font-semibold">{ft.test_identifier}</span>
                              <Badge variant="outline" className="text-[9px] uppercase px-1.5 py-0">
                                {ft.classification}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-3 text-muted-foreground text-[11px]">
                              <span>Stability: <span className="text-foreground font-bold">{typeof ft.stability_score === "number" ? ft.stability_score.toFixed(1) : ft.stability_score}%</span></span>
                              <span>{ft.total_runs} runs: <span className="text-emerald-400">{ft.passed_runs}P</span> / <span className="text-destructive">{ft.failed_runs}F</span></span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {tests.length > 0 ? (
                    tests.map((run: TestRun, idx: number) => {
                      const isOom = run.oom_killed || run.exit_classification === "OOM_KILLED";
                      const isProcessKilled = run.exit_classification === "PROCESS_KILLED";
                      const isTimeout = run.exit_classification === "TIMEOUT" || run.failure_classification === "TIMEOUT" || run.exit_code === 124 || run.exit_code === -1;
                      const isCmdNotFound = run.exit_classification === "COMMAND_NOT_FOUND" || run.exit_code === 127 || run.stderr?.includes("command not found");
                      const isCmdNotExec = run.exit_classification === "COMMAND_NOT_EXECUTABLE" || run.exit_code === 126;
                      const isUnavailable = isCmdNotFound || isCmdNotExec || run.failure_classification === "RUNNER_UNAVAILABLE";
                      const isFlaky = run.is_flaky || run.stability_classification === "FLAKY";

                      let badgeText = "FAILED";
                      let badgeVariant: any = "destructive";
                      let badgeClass = "";

                      if (run.passed) {
                        badgeText = "PASSED";
                        badgeVariant = "success";
                      } else if (isOom) {
                        badgeText = "OOM KILLED (CONFIRMED)";
                        badgeVariant = "destructive";
                        badgeClass = "bg-destructive text-destructive-foreground font-bold animate-pulse";
                      } else if (isProcessKilled) {
                        badgeText = "PROCESS KILLED (SIGKILL)";
                        badgeVariant = "outline";
                        badgeClass = "bg-amber-500/20 text-amber-300 border-amber-500/40";
                      } else if (isTimeout) {
                        badgeText = "EXECUTION TIMEOUT";
                        badgeVariant = "outline";
                        badgeClass = "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
                      } else if (isCmdNotFound) {
                        badgeText = "COMMAND NOT FOUND";
                        badgeVariant = "outline";
                        badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                      } else if (isCmdNotExec) {
                        badgeText = "COMMAND NOT EXECUTABLE";
                        badgeVariant = "outline";
                        badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                      } else if (isUnavailable) {
                        badgeText = "RUNNER UNAVAILABLE";
                        badgeVariant = "outline";
                        badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                      } else if (isFlaky) {
                        badgeText = "FLAKY TEST";
                        badgeVariant = "outline";
                        badgeClass = "bg-amber-500/20 text-amber-300 border-amber-500/40";
                      }

                      return (
                        <div key={idx} className="border border-border rounded-lg overflow-hidden space-y-3 p-4 bg-secondary/20">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                variant={badgeVariant}
                                className={`font-mono text-xs ${badgeClass}`}
                              >
                                {badgeText}
                              </Badge>
                              {isFlaky && run.stability_score !== undefined && run.stability_score !== null && (
                                <Badge variant="outline" className="text-[10px] font-mono bg-amber-500/10 text-amber-400 border-amber-500/30">
                                  {run.stability_score.toFixed(1)}% Stability
                                </Badge>
                              )}
                              <span className="font-mono text-xs font-semibold text-foreground">
                                Iteration {run.iteration} &bull; Exit Code: {run.exit_code}
                              </span>
                            </div>
                            <span className="text-[11px] font-mono text-muted-foreground">
                              {(run.wall_time_seconds ?? run.duration_seconds).toFixed(2)}s duration
                            </span>
                          </div>

                          {/* Executed Command */}
                          <div className="flex items-center gap-2 text-xs font-mono bg-black/40 px-3 py-1.5 rounded border border-border/40">
                            <span className="text-muted-foreground select-none">$</span>
                            <span className="text-foreground break-all">{run.command}</span>
                          </div>

                          {/* Termination Reason Alert Banner */}
                          {run.termination_reason && (
                            <div className={`p-2.5 rounded border text-xs font-mono flex items-start gap-2 ${
                              isOom ? "bg-destructive/15 border-destructive/40 text-destructive" :
                              isTimeout ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-300" :
                              "bg-secondary/60 border-border text-muted-foreground"
                            }`}>
                              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                              <div>
                                <span className="font-semibold block">Termination Reason:</span>
                                <span className="text-[11px]">{run.termination_reason}</span>
                              </div>
                            </div>
                          )}

                          {/* Resource Telemetry Panel (Phase 9 Stage 9.3) */}
                          <div className="p-2.5 rounded bg-black/40 border border-border/60 space-y-2">
                            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground border-b border-border/40 pb-1.5">
                              <div className="flex items-center gap-1.5 text-foreground font-semibold">
                                <Activity className="w-3.5 h-3.5 text-primary" />
                                <span>Sandbox Resource Telemetry</span>
                              </div>
                              {run.resource_telemetry_available ? (
                                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                                  Empirical Telemetry Captured
                                </span>
                              ) : (
                                <span className="text-[10px] text-muted-foreground bg-secondary/50 px-1.5 py-0.5 rounded border border-border/40">
                                  Resource Telemetry Unavailable
                                </span>
                              )}
                            </div>

                            {run.resource_telemetry_available ? (
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
                                <div className="p-2 rounded bg-secondary/30 border border-border/30">
                                  <span className="text-[10px] text-muted-foreground block">Peak Memory RSS</span>
                                  <span className="font-semibold text-foreground">
                                    {typeof run.peak_memory_rss_mb === "number" ? `${run.peak_memory_rss_mb.toFixed(1)} MB` : "N/A"}
                                    {run.memory_limit_mb && ` / ${run.memory_limit_mb.toFixed(0)} MB`}
                                  </span>
                                </div>
                                <div className="p-2 rounded bg-secondary/30 border border-border/30">
                                  <span className="text-[10px] text-muted-foreground block">CPU Time</span>
                                  <span className="font-semibold text-foreground">
                                    {typeof run.cpu_time_seconds === "number" ? `${run.cpu_time_seconds.toFixed(3)}s` : "N/A"}
                                    {run.cpu_limit && ` (${run.cpu_limit} cores)`}
                                  </span>
                                </div>
                                <div className="p-2 rounded bg-secondary/30 border border-border/30">
                                  <span className="text-[10px] text-muted-foreground block">Wall-Clock Time</span>
                                  <span className="font-semibold text-foreground">
                                    {(run.wall_time_seconds ?? run.duration_seconds).toFixed(2)}s
                                  </span>
                                </div>
                                <div className="p-2 rounded bg-secondary/30 border border-border/30">
                                  <span className="text-[10px] text-muted-foreground block">OOM State</span>
                                  <span className={`font-semibold ${run.oom_killed ? "text-destructive" : "text-emerald-400"}`}>
                                    {run.oom_killed ? "OOM Detected" : "No OOM"}
                                  </span>
                                </div>
                              </div>
                            ) : (
                              <p className="text-[11px] text-muted-foreground font-mono">
                                Container resource metrics were not reported by the host environment for this execution.
                              </p>
                            )}
                          </div>

                          {/* Missing Runner Diagnostic Warning */}
                          {isUnavailable && (
                            <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
                              <p className="font-semibold">Test Runner Tool Unavailable</p>
                              <p className="text-[11px] text-muted-foreground mt-0.5">
                                The required test runner or runtime was not found in the execution sandbox. Check container image configuration or install required dependencies.
                              </p>
                            </div>
                          )}

                          {/* Test metrics grid */}
                          <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono">
                            <div className="p-2 rounded bg-secondary/40 border border-border/40">
                              <span className="text-muted-foreground text-[10px] block">Total</span>
                              <span className="text-sm font-bold text-foreground">{run.total_tests}</span>
                            </div>
                            <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20">
                              <span className="text-emerald-400 text-[10px] block">Passed</span>
                              <span className="text-sm font-bold text-emerald-400">{run.passed_tests}</span>
                            </div>
                            <div className="p-2 rounded bg-destructive/10 border border-destructive/20">
                              <span className="text-destructive text-[10px] block">Failed</span>
                              <span className="text-sm font-bold text-destructive">{run.failed_tests}</span>
                            </div>
                            <div className="p-2 rounded bg-secondary/40 border border-border/40">
                              <span className="text-muted-foreground text-[10px] block">Skipped</span>
                              <span className="text-sm font-bold text-muted-foreground">{run.skipped_tests ?? Math.max(0, run.total_tests - run.passed_tests - run.failed_tests)}</span>
                            </div>
                          </div>

                          {/* Stdout / Stderr logs */}
                          {run.stdout && (
                            <div className="space-y-1">
                              <span className="text-[10px] font-mono text-muted-foreground">Standard Output:</span>
                              <pre className="p-3 bg-black/80 rounded font-mono text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap max-h-48 border border-border/40">
                                {run.stdout}
                              </pre>
                            </div>
                          )}
                          {run.stderr && (
                            <div className="space-y-1">
                              <span className="text-[10px] font-mono text-muted-foreground">Standard Error:</span>
                              <pre className="p-3 bg-black/80 rounded font-mono text-[11px] text-destructive overflow-x-auto whitespace-pre-wrap max-h-48 border border-border/40">
                                {run.stderr}
                              </pre>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-10 text-center border border-dashed border-border rounded-lg bg-card/20">
                      <CheckCircle2 className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-xs font-medium text-foreground mb-1">
                        No Tests Executed Yet
                      </p>
                      <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                        Test runs and assertion exit codes from the isolated sandbox will appear here with execution metrics.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Tab 4: Live Sandbox Terminal */}
            {activeTab === "terminal" && (
              <Card className="bg-card/40 border-border">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center justify-between">
                    <span>Isolated Execution Terminal</span>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      Docker &bull; &ndash;&ndash;network none
                    </Badge>
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Real-time execution log and specialist agent transitions streamed via SSE.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="bg-black/90 rounded-lg p-4 font-mono text-xs text-emerald-400 min-h-[350px] max-h-[500px] overflow-y-auto border border-border/80 flex flex-col justify-between space-y-2">
                    <div className="space-y-1.5">
                      <p className="text-muted-foreground"># Devora Autonomous Sandbox Container Runner</p>
                      <p className="text-muted-foreground">
                        # Task ID: {task.id} &bull; Target Branch: {task.target_branch}
                      </p>
                      <p className="text-muted-foreground">
                        # Resource Limits: 1.5GB RAM &bull; 2 vCPUs &bull; Read-only Root &bull; Confined PATH
                      </p>
                      <div className="border-b border-border/40 my-2" />

                      {streamEvents.length === 0 ? (
                        <p className="text-yellow-400/80">
                          [STANDBY] Awaiting workflow initiation. Real-time events will stream here live.
                        </p>
                      ) : (
                        streamEvents.map((evt, idx) => (
                          <div key={idx} className="space-y-0.5">
                            <span className="text-[10px] text-muted-foreground">
                              [{evt.created_at ? new Date(evt.created_at).toLocaleTimeString() : "NOW"}]
                            </span>{" "}
                            <span className="text-cyan-400 font-semibold">[{evt.agent_name || "system"}]:</span>{" "}
                            <span className="text-foreground">{evt.message}</span>
                          </div>
                        ))
                      )}
                      <div ref={terminalEndRef} />
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-muted-foreground border-t border-border/40 pt-2 shrink-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${sseConnected ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground"}`} />
                        <span>{sseConnected ? "Stream Active" : "Stream Idle"}</span>
                      </div>
                      <span>{streamEvents.length} events logged</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Tab 5: Final Engineering Report */}
            {activeTab === "report" && (
              <Card className="bg-card/40 border-border">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Engineering Synthesis Report</CardTitle>
                  <CardDescription className="text-xs">
                    Comprehensive technical audit report authored by the Reporting Agent.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {report ? (
                    <div className="space-y-4">
                      <div className="p-4 rounded-lg bg-secondary/30 border border-border space-y-2">
                        <h3 className="text-base font-bold text-foreground">{report.title}</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">{report.summary}</p>
                      </div>

                      {report.root_cause_analysis && (
                        <div className="p-4 rounded-lg bg-secondary/20 border border-border space-y-1.5">
                          <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-primary">
                            Root Cause Analysis
                          </h4>
                          <p className="text-xs text-foreground leading-relaxed">
                            {report.root_cause_analysis}
                          </p>
                        </div>
                      )}

                      <div className="p-4 rounded-lg bg-black/50 border border-border font-mono text-xs text-foreground whitespace-pre-wrap leading-relaxed overflow-x-auto">
                        {report.markdown_content}
                      </div>
                    </div>
                  ) : (
                    <div className="p-10 text-center border border-dashed border-border rounded-lg bg-card/20">
                      <FileText className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-xs font-medium text-foreground mb-1">
                        Report Not Yet Generated
                      </p>
                      <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
                        The final audit report will be generated automatically once all tests pass and changes are approved.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Developer Feedback for Adaptive Learning */}
            {task.status === "COMPLETED" && (
              <Card className="bg-card/40 border-indigo-500/30">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Brain className="w-4 h-4 text-indigo-400" />
                      <CardTitle className="text-sm font-semibold">Adaptive Learning Feedback</CardTitle>
                    </div>
                    <Badge variant="outline" className="text-[10px] font-mono border-indigo-500/40 text-indigo-400">
                      Experience Distillation
                    </Badge>
                  </div>
                  <CardDescription className="text-xs">
                    Help Devora learn and calibrate future engineering decisions for this repository.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  {feedbackSubmitted ? (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center gap-2 text-emerald-400 font-mono">
                      <Check className="w-4 h-4 shrink-0" />
                      <span>Thank you! Your feedback has been incorporated into repository experience memory.</span>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-muted-foreground">Solution Rating:</span>
                        <div className="flex items-center gap-1.5">
                          <Button
                            size="sm"
                            variant={feedbackRating === "ACCEPTED" ? "default" : "outline"}
                            onClick={() => setFeedbackRating("ACCEPTED")}
                            className={`h-7 text-xs gap-1 font-mono ${
                              feedbackRating === "ACCEPTED" ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""
                            }`}
                          >
                            <ThumbsUp className="w-3 h-3" />
                            <span>Accepted</span>
                          </Button>
                          <Button
                            size="sm"
                            variant={feedbackRating === "NEEDS_CHANGES" ? "default" : "outline"}
                            onClick={() => setFeedbackRating("NEEDS_CHANGES")}
                            className={`h-7 text-xs gap-1 font-mono ${
                              feedbackRating === "NEEDS_CHANGES" ? "bg-amber-600 hover:bg-amber-700 text-white" : ""
                            }`}
                          >
                            <span>Needs Changes</span>
                          </Button>
                          <Button
                            size="sm"
                            variant={feedbackRating === "REJECTED" ? "default" : "outline"}
                            onClick={() => setFeedbackRating("REJECTED")}
                            className={`h-7 text-xs gap-1 font-mono ${
                              feedbackRating === "REJECTED" ? "bg-destructive hover:bg-destructive/90 text-white" : ""
                            }`}
                          >
                            <ThumbsDown className="w-3 h-3" />
                            <span>Rejected</span>
                          </Button>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Optional feedback notes for the intelligence engine..."
                          value={feedbackComments}
                          onChange={(e) => setFeedbackComments(e.target.value)}
                          className="text-xs bg-background/80 border border-border rounded-md px-3 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary flex-1 font-sans"
                        />
                        <Button
                          size="sm"
                          onClick={() => feedbackMutation.mutate()}
                          disabled={feedbackMutation.isPending}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs gap-1.5 font-mono shrink-0"
                        >
                          {feedbackMutation.isPending ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5" />
                          )}
                          <span>Submit Feedback</span>
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

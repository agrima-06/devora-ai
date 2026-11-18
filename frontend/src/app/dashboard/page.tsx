"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  GitBranch,
  CheckSquare,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  Plus,
  Play,
  Terminal,
  Layers,
  Activity,
  AlertCircle,
  Shield,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { repositoryService } from "@/services/repository-service";
import { taskService } from "@/services/task-service";
import { formatDate } from "@/lib/utils";
import { TaskStatus } from "@/types";

export default function DashboardPage() {
  const {
    data: repositories = [],
    isLoading: reposLoading,
    error: reposError,
  } = useQuery({
    queryKey: ["repositories"],
    queryFn: () => repositoryService.list(),
  });

  const {
    data: tasks = [],
    isLoading: tasksLoading,
    error: tasksError,
  } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => taskService.list(),
  });

  const totalRepos = repositories.length;
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter((t) => t.status === "COMPLETED").length;
  const failedTasks = tasks.filter((t) => t.status === "FAILED").length;
  const runningTasks = tasks.filter((t) =>
    ["PLANNING", "IN_PROGRESS", "TESTING"].includes(t.status)
  ).length;

  const successRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 100;

  const getStatusBadge = (status: TaskStatus) => {
    switch (status) {
      case "COMPLETED":
        return <Badge variant="success">Completed</Badge>;
      case "FAILED":
        return <Badge variant="destructive">Failed</Badge>;
      case "IN_PROGRESS":
      case "TESTING":
      case "PLANNING":
        return <Badge variant="info">Running</Badge>;
      case "WAITING_APPROVAL":
        return <Badge variant="warning">Awaiting Approval</Badge>;
      case "CANCELLED":
        return <Badge variant="secondary">Cancelled</Badge>;
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  return (
    <AppLayout>
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Welcome & Action Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Autonomous Engineering Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Real-time monitoring of connected repositories, agent runs, and verification states.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/repositories">
              <Button variant="outline" size="sm" className="gap-2 border-border">
                <GitBranch className="w-3.5 h-3.5" />
                <span>Manage Repos</span>
              </Button>
            </Link>
            <Link href="/tasks/new">
              <Button size="sm" className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]">
                <Plus className="w-3.5 h-3.5" />
                <span>New Engineering Task</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Top Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card className="bg-card/40 border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <span className="text-xs font-medium text-muted-foreground">Repositories</span>
              <GitBranch className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono">
                {reposLoading ? "-" : totalRepos}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Connected for analysis</p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <span className="text-xs font-medium text-muted-foreground">Total Tasks</span>
              <CheckSquare className="w-4 h-4 text-blue-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono">
                {tasksLoading ? "-" : totalTasks}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Dispatched jobs</p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <span className="text-xs font-medium text-muted-foreground">Running</span>
              <Play className="w-4 h-4 text-amber-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono text-amber-400">
                {tasksLoading ? "-" : runningTasks}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Currently executing</p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <span className="text-xs font-medium text-muted-foreground">Completed</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono text-emerald-400">
                {tasksLoading ? "-" : completedTasks}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Verified & green</p>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <span className="text-xs font-medium text-muted-foreground">Verification Rate</span>
              <Activity className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono text-primary">
                {tasksLoading ? "-" : `${successRate}%`}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Passing tests</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Grid: Recent Activity & Quick Launcher */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Recent Activity List (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-foreground flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary" />
                <span>Recent Engineering Activity</span>
              </h2>
              <Link href="/tasks" className="text-xs text-primary hover:underline font-mono">
                View all &rarr;
              </Link>
            </div>

            {tasksLoading ? (
              <div className="p-12 rounded-lg border border-border bg-card/20 flex flex-col items-center justify-center">
                <div className="w-6 h-6 border-2 border-primary/20 border-t-primary rounded-full animate-spin mb-3" />
                <span className="text-xs text-muted-foreground font-mono">Loading tasks...</span>
              </div>
            ) : tasks.length === 0 ? (
              <div className="p-12 rounded-lg border border-dashed border-border bg-card/20 text-center">
                <Terminal className="w-8 h-8 text-muted-foreground mx-auto mb-3 opacity-60" />
                <h3 className="text-sm font-semibold text-foreground mb-1">No tasks created yet</h3>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
                  Connect a repository and dispatch an autonomous bug fix or feature task.
                </p>
                <Link href="/tasks/new">
                  <Button size="sm" variant="outline">
                    Create First Task
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border border border-border rounded-lg bg-card/40 overflow-hidden">
                {tasks.slice(0, 5).map((task) => (
                  <Link
                    key={task.id}
                    href={`/tasks/${task.id}`}
                    className="p-4 flex items-center justify-between hover:bg-secondary/40 transition-colors block group"
                  >
                    <div className="space-y-1 pr-4 truncate">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-muted-foreground">
                          TASK-{task.id.substring(0, 6)}
                        </span>
                        {getStatusBadge(task.status)}
                      </div>
                      <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">
                        {task.title}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono">
                        <span>Target: {task.target_branch}</span>
                        <span>•</span>
                        <span>{formatDate(task.created_at)}</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0" />
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Quick Context & Connected Repos (1 col) */}
          <div className="space-y-4">
            <h2 className="text-base font-semibold tracking-tight text-foreground flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-primary" />
              <span>Connected Repositories</span>
            </h2>

            {reposLoading ? (
              <div className="p-8 rounded-lg border border-border bg-card/20 text-center">
                <span className="text-xs text-muted-foreground font-mono">Loading repositories...</span>
              </div>
            ) : repositories.length === 0 ? (
              <div className="p-8 rounded-lg border border-dashed border-border bg-card/20 text-center">
                <p className="text-xs text-muted-foreground mb-3">No repositories connected.</p>
                <Link href="/repositories">
                  <Button size="sm" variant="secondary">
                    Add Repository
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {repositories.slice(0, 4).map((repo) => (
                  <Link
                    key={repo.id}
                    href={`/repositories/${repo.id}`}
                    className="p-3.5 rounded-lg border border-border bg-card/40 hover:border-primary/40 transition-all flex items-center justify-between block group"
                  >
                    <div className="truncate">
                      <p className="text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                        {repo.name}
                      </p>
                      <p className="text-[11px] text-muted-foreground font-mono truncate">
                        {repo.full_name}
                      </p>
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {repo.language || "code"}
                    </Badge>
                  </Link>
                ))}

                <Link href="/repositories" className="block text-center">
                  <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground">
                    View all repositories ({repositories.length})
                  </Button>
                </Link>
              </div>
            )}

            {/* Architecture Governance Box */}
            <Card className="bg-primary/5 border-primary/20">
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-xs font-mono uppercase tracking-wider text-primary flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" />
                  <span>Sandbox Guardrails</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0 text-xs text-muted-foreground space-y-1.5">
                <p>• Network isolated by default (&ndash;&ndash;network none)</p>
                <p>• 1.5GB RAM & 2 CPU quota limits</p>
                <p>• Human approval required for PR publishing</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

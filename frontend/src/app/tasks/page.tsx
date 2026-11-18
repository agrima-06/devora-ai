"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  CheckSquare,
  Plus,
  Search,
  Filter,
  ArrowRight,
  Terminal,
  Clock,
  CheckCircle2,
  XCircle,
  Play,
  Loader2,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { taskService } from "@/services/task-service";
import { formatDate } from "@/lib/utils";
import { TaskStatus } from "@/types";

export default function TasksPage() {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => taskService.list(),
  });

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

  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || task.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <AppLayout>
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Engineering Tasks
            </h1>
            <p className="text-sm text-muted-foreground">
              Autonomous bug fixes, feature spikes, and refactoring jobs dispatched to Devora AI.
            </p>
          </div>
          <Link href="/tasks/new">
            <Button size="sm" className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]">
              <Plus className="w-3.5 h-3.5" />
              <span>Create Task</span>
            </Button>
          </Link>
        </div>

        {/* Filters & Search */}
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search tasks by title, ID, or prompt..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-card/40 border-border text-xs"
            />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-2 sm:pb-0">
            {["ALL", "PENDING", "IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED", "FAILED"].map(
              (status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 rounded-md text-xs font-mono transition-colors whitespace-nowrap ${
                    statusFilter === status
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "bg-secondary/40 text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
                  }`}
                >
                  {status}
                </button>
              )
            )}
          </div>
        </div>

        {/* Tasks Table / List */}
        {isLoading ? (
          <div className="p-16 rounded-lg border border-border bg-card/20 flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" />
            <span className="text-xs text-muted-foreground font-mono">Loading task registry...</span>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="p-16 rounded-lg border border-dashed border-border bg-card/20 text-center">
            <CheckSquare className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-60" />
            <h3 className="text-base font-semibold text-foreground mb-1">No tasks found</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">
              {searchQuery || statusFilter !== "ALL"
                ? "No tasks matched your active filters."
                : "Create an autonomous engineering task to start working alongside Devora AI."}
            </p>
            {statusFilter === "ALL" && !searchQuery && (
              <Link href="/tasks/new">
                <Button size="sm">Create First Task</Button>
              </Link>
            )}
          </div>
        ) : (
          <div className="border border-border rounded-lg bg-card/40 overflow-hidden divide-y divide-border">
            {filteredTasks.map((task) => (
              <Link
                key={task.id}
                href={`/tasks/${task.id}`}
                className="p-5 flex items-center justify-between hover:bg-secondary/40 transition-colors group block"
              >
                <div className="space-y-1.5 pr-4 truncate">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-muted-foreground">
                      TASK-{task.id.substring(0, 8)}
                    </span>
                    {getStatusBadge(task.status)}
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {task.task_type}
                    </Badge>
                  </div>

                  <p className="text-base font-medium text-foreground truncate group-hover:text-primary transition-colors">
                    {task.title}
                  </p>

                  <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
                    <span>Branch: {task.target_branch}</span>
                    <span>•</span>
                    <span>Iterations: {task.iterations_count}/3</span>
                    <span>•</span>
                    <span>Created: {formatDate(task.created_at)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-primary font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                    Open Workspace &rarr;
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

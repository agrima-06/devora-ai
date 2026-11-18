"use client";

import React from "react";
import Link from "next/link";
import { Plus, FolderGit2, Activity, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQuery } from "@tanstack/react-query";
import { projectService } from "@/services/project-service";

export function Header() {
  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectService.list(),
  });

  const activeProject = projects.length > 0 ? projects[0] : null;

  return (
    <header className="h-16 border-b border-border bg-card/40 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-4">
        {/* Workspace / Project Badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary/60 border border-border text-xs text-muted-foreground font-mono">
          <FolderGit2 className="w-3.5 h-3.5 text-primary" />
          <span>Project:</span>
          <span className="font-semibold text-foreground">
            {activeProject ? activeProject.name : "Default Workspace"}
          </span>
        </div>

        {/* System Status Pill */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-400 font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Backend v0.1.0 Active</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Link href="/tasks/new">
          <Button size="sm" className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.2)]">
            <Plus className="w-3.5 h-3.5" />
            <span>Create Task</span>
          </Button>
        </Link>
      </div>
    </header>
  );
}

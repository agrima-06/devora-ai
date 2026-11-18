"use client";

import React from "react";
import {
  User as UserIcon,
  Settings as SettingsIcon,
  GitBranch,
  Shield,
  Key,
  CheckCircle2,
  Cpu,
  Database,
  Terminal,
  LogOut,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <AppLayout>
      <div className="space-y-8 max-w-4xl mx-auto">
        <div className="border-b border-border/80 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Settings & Integrations
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage your developer profile, GitHub connectivity, and AI model configurations.
          </p>
        </div>

        {/* User Profile Card */}
        <Card className="bg-card/40 border-border">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <UserIcon className="w-4 h-4 text-primary" />
              <span>Developer Profile</span>
            </CardTitle>
            <CardDescription className="text-xs">
              Personal authentication credentials and account metadata.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-3 rounded-md bg-secondary/40 border border-border">
                <span className="text-muted-foreground block text-[11px] mb-1">Full Name</span>
                <span className="text-foreground font-semibold font-sans">{user?.full_name}</span>
              </div>
              <div className="p-3 rounded-md bg-secondary/40 border border-border">
                <span className="text-muted-foreground block text-[11px] mb-1">Email Address</span>
                <span className="text-foreground">{user?.email}</span>
              </div>
              <div className="p-3 rounded-md bg-secondary/40 border border-border">
                <span className="text-muted-foreground block text-[11px] mb-1">User Identifier</span>
                <span className="text-foreground text-[10px] truncate block">{user?.id}</span>
              </div>
              <div className="p-3 rounded-md bg-secondary/40 border border-border">
                <span className="text-muted-foreground block text-[11px] mb-1">Account Created</span>
                <span className="text-foreground">{formatDate(user?.created_at)}</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button variant="destructive" size="sm" onClick={logout} className="gap-2">
                <LogOut className="w-3.5 h-3.5" />
                <span>Log Out</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* GitHub Integration Card */}
        <Card className="bg-card/40 border-border">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-primary" />
              <span>GitHub Integration</span>
            </CardTitle>
            <CardDescription className="text-xs">
              Manage personal access tokens or GitHub App permissions for repository read/write
              access.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg bg-secondary/30 border border-border flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-foreground">GitHub PAT / Installation Token</p>
                <p className="text-[11px] text-muted-foreground">
                  Grants Devora permissions to clone repositories, create task branches, and draft
                  pull requests.
                </p>
              </div>
              <Badge variant="success" className="font-mono text-xs">
                Connected
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* System & Architecture Integration Status */}
        <Card className="bg-card/40 border-border">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Cpu className="w-4 h-4 text-primary" />
              <span>Devora System Integration Status</span>
            </CardTitle>
            <CardDescription className="text-xs">
              Live status of backend microservices and computational runtimes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 divide-y divide-border/60">
              {[
                {
                  service: "FastAPI Backend Gateway",
                  version: "v0.1.0",
                  status: "ACTIVE",
                  desc: "REST APIs, JWT Auth, Pydantic v2 schemas",
                },
                {
                  service: "PostgreSQL & pgvector",
                  version: "PostgreSQL 16+",
                  status: "ACTIVE",
                  desc: "Relational persistence and vector memory tables",
                },
                {
                  service: "Execution Sandbox Runner",
                  version: "Docker / Process Fallback",
                  status: "STANDBY",
                  desc: "Network-isolated container environment for pytest/ruff",
                },
                {
                  service: "Gemini Model Gateway",
                  version: "Gemini 1.5 Pro / Flash",
                  status: "PHASE 3",
                  desc: "Centralized LLM router with rate limits and schema enforcement",
                },
              ].map((item, i) => (
                <div key={i} className="pt-3 first:pt-0 flex items-center justify-between text-xs">
                  <div>
                    <p className="font-medium text-foreground">{item.service}</p>
                    <p className="text-[11px] text-muted-foreground">{item.desc}</p>
                  </div>
                  <div className="text-right">
                    <Badge
                      variant={
                        item.status === "ACTIVE"
                          ? "success"
                          : item.status === "STANDBY"
                          ? "warning"
                          : "secondary"
                      }
                      className="font-mono text-[10px]"
                    >
                      {item.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}

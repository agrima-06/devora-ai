"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  GitPullRequest,
  GitBranch,
  Shield,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Plus,
  RefreshCw,
  Trash2,
  Lock,
  Globe,
  Loader2,
  Terminal,
  Cpu,
} from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { githubService } from "@/services/github-service";
import { formatDate } from "@/lib/utils";

export default function GitHubPage() {
  const queryClient = useQueryClient();
  const [selectedInstId, setSelectedInstId] = useState<number | null>(null);
  const [connectIdInput, setConnectIdInput] = useState<string>("");
  const [connectAccountInput, setConnectAccountInput] = useState<string>("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Status query
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["github-status"],
    queryFn: () => githubService.getStatus(),
  });

  // Installations query
  const { data: installations = [], isLoading: instLoading } = useQuery({
    queryKey: ["github-installations"],
    queryFn: () => githubService.listInstallations(),
  });

  // Active installation ID: either selected or first available
  const activeInstId = selectedInstId || (installations.length > 0 ? installations[0].installation_id : null);

  // Repositories query for active installation
  const { data: repositories = [], isLoading: reposLoading } = useQuery({
    queryKey: ["github-installation-repos", activeInstId],
    queryFn: () => (activeInstId ? githubService.listInstallationRepositories(activeInstId) : Promise.resolve([])),
    enabled: !!activeInstId,
  });

  // Connect mutation
  const connectMutation = useMutation({
    mutationFn: (data: { installation_id: number; account_login?: string }) =>
      githubService.connectInstallation(data),
    onSuccess: (newInst) => {
      queryClient.invalidateQueries({ queryKey: ["github-installations"] });
      setSelectedInstId(newInst.installation_id);
      setIsConnecting(false);
      setConnectIdInput("");
      setConnectAccountInput("");
      setActionSuccess(`Successfully connected installation #${newInst.installation_id} (${newInst.account_login})`);
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err: any) => {
      setActionError(err?.message || "Failed to connect installation.");
      setTimeout(() => setActionError(null), 5000);
    },
  });

  // Disconnect mutation
  const disconnectMutation = useMutation({
    mutationFn: (id: number) => githubService.disconnectInstallation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["github-installations"] });
      setSelectedInstId(null);
      setActionSuccess("Installation disconnected.");
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err: any) => {
      setActionError(err?.message || "Failed to disconnect installation.");
      setTimeout(() => setActionError(null), 5000);
    },
  });

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    const instIdNum = parseInt(connectIdInput.trim(), 10);
    if (isNaN(instIdNum) || instIdNum <= 0) {
      setActionError("Please enter a valid numeric GitHub installation ID.");
      return;
    }
    connectMutation.mutate({
      installation_id: instIdNum,
      account_login: connectAccountInput.trim() || undefined,
    });
  };

  const handleSimulateQuickConnect = () => {
    const mockId = Math.floor(100000 + Math.random() * 900000);
    connectMutation.mutate({
      installation_id: mockId,
      account_login: "devora-preview-org",
    });
  };

  return (
    <AppLayout>
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-primary">
                <GitPullRequest className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  GitHub App Integration
                  {status?.is_mock && (
                    <Badge variant="outline" className="text-xs bg-amber-500/10 text-amber-400 border-amber-500/20">
                      Sandbox Simulation Mode
                    </Badge>
                  )}
                  {status?.app_configured && !status?.is_mock && (
                    <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                      GitHub App Active
                    </Badge>
                  )}
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Autonomous branch creation, commit signing, and pull request generation with least-privilege security.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => queryClient.invalidateQueries({ queryKey: ["github-installations"] })}
              className="gap-2 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => setIsConnecting(!isConnecting)}
              className="gap-2 text-xs bg-primary hover:bg-primary/90"
            >
              <Plus className="w-3.5 h-3.5" />
              Connect Installation
            </Button>
          </div>
        </div>

        {/* Notifications */}
        {actionSuccess && (
          <div className="flex items-center gap-2 p-3 text-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
        )}
        {actionError && (
          <div className="flex items-center gap-2 p-3 text-sm bg-destructive/10 border border-destructive/20 text-destructive rounded-lg">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Quick Connect Form Modal / Drawer */}
        {isConnecting && (
          <Card className="border-primary/30 bg-primary/5 shadow-lg">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                Connect GitHub Installation
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Authorize Devora AI to interact with your GitHub repositories. Enter your GitHub App installation ID.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleConnect} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-muted-foreground">Installation ID *</label>
                    <Input
                      placeholder="e.g. 12345678"
                      value={connectIdInput}
                      onChange={(e) => setConnectIdInput(e.target.value)}
                      className="h-9 font-mono text-xs"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-muted-foreground">Account / Org Name</label>
                    <Input
                      placeholder="e.g. your-org-name"
                      value={connectAccountInput}
                      onChange={(e) => setConnectAccountInput(e.target.value)}
                      className="h-9 font-mono text-xs"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleSimulateQuickConnect}
                    className="text-xs text-primary hover:bg-primary/10 gap-1.5"
                  >
                    <Terminal className="w-3.5 h-3.5" />
                    Quick Connect (Test Mock)
                  </Button>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setIsConnecting(false)}
                      className="text-xs"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={connectMutation.isPending}
                      className="text-xs bg-primary"
                    >
                      {connectMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />}
                      Register Installation
                    </Button>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Integration Architecture Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-card/40 border-border">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-muted-foreground uppercase">Auth Architecture</span>
                <Shield className="w-4 h-4 text-primary" />
              </div>
              <div className="text-lg font-bold text-foreground">Dual-Stage Isolation</div>
              <p className="text-xs text-muted-foreground mt-1">
                Docker `--network none` runs untrusted code; Git pushes strictly host-side with ephemeral installation tokens.
              </p>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-muted-foreground uppercase">Token Lifespan</span>
                <Cpu className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-lg font-bold text-foreground">60-Min Scoped Access</div>
              <p className="text-xs text-muted-foreground mt-1">
                Zero long-lived tokens stored in workspace. Subprocess logs sanitized via token scrub regex.
              </p>
            </CardContent>
          </Card>
          <Card className="bg-card/40 border-border">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-muted-foreground uppercase">Branch Lifecycle</span>
                <GitBranch className="w-4 h-4 text-blue-400" />
              </div>
              <div className="text-lg font-bold text-foreground">devora/{'{type}-{id[:8]}'}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Every task runs on a dedicated branch branched from the default branch. Never commits directly to main.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Installations & Repositories Split View */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Connected Installations */}
          <div className="lg:col-span-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                Installations ({installations.length})
              </h2>
            </div>

            {instLoading ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg text-muted-foreground text-xs">
                <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-primary" />
                Loading installations...
              </div>
            ) : installations.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-lg text-muted-foreground text-xs space-y-3">
                <GitPullRequest className="w-8 h-8 mx-auto text-muted-foreground/40" />
                <p>No GitHub installations connected yet.</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSimulateQuickConnect}
                  className="text-xs gap-1.5"
                >
                  <Terminal className="w-3.5 h-3.5" />
                  Connect Sample Mock Org
                </Button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {installations.map((inst) => {
                  const isSelected = inst.installation_id === activeInstId;
                  return (
                    <div
                      key={inst.id}
                      onClick={() => setSelectedInstId(inst.installation_id)}
                      className={`p-4 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? "bg-primary/10 border-primary/40 shadow-sm"
                          : "bg-card/40 border-border hover:bg-card/70 hover:border-border/80"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-md bg-secondary/80 flex items-center justify-center font-bold text-xs text-primary">
                            {inst.account_login.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground flex items-center gap-2">
                              {inst.account_login}
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                {inst.account_type}
                              </Badge>
                            </div>
                            <div className="text-xs font-mono text-muted-foreground">
                              ID: #{inst.installation_id} • {inst.repository_selection}
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Disconnect installation for ${inst.account_login}?`)) {
                              disconnectMutation.mutate(inst.installation_id);
                            }
                          }}
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                      <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          Contents: Read & Write
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          PRs: Read & Write
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Repositories for selected installation */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                Authorized Repositories {activeInstId ? `(Installation #${activeInstId})` : ""}
              </h2>
            </div>

            {reposLoading ? (
              <div className="p-12 text-center border border-border bg-card/20 rounded-lg text-muted-foreground text-xs">
                <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-primary" />
                Querying GitHub repository metadata...
              </div>
            ) : repositories.length === 0 ? (
              <div className="p-12 text-center border border-dashed border-border rounded-lg text-muted-foreground text-xs">
                Select an installation or connect one to explore authorized repositories.
              </div>
            ) : (
              <div className="space-y-3">
                {repositories.map((repo) => (
                  <Card key={repo.id} className="bg-card/40 border-border hover:border-primary/30 transition-all">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-foreground">{repo.name}</span>
                            {repo.private ? (
                              <Badge variant="outline" className="text-[10px] gap-1 text-amber-400 border-amber-500/20 bg-amber-500/10">
                                <Lock className="w-2.5 h-2.5" /> Private
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] gap-1 text-emerald-400 border-emerald-500/20 bg-emerald-500/10">
                                <Globe className="w-2.5 h-2.5" /> Public
                              </Badge>
                            )}
                            {repo.language && (
                              <Badge variant="secondary" className="text-[10px]">
                                {repo.language}
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs font-mono text-muted-foreground">{repo.full_name}</div>
                          <div className="text-xs text-muted-foreground flex items-center gap-2 pt-1 font-mono">
                            <GitBranch className="w-3 h-3 text-primary" />
                            Default branch: <span className="text-foreground">{repo.default_branch}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <a
                            href={repo.clone_url.replace(".git", "")}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                            title="View on GitHub"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

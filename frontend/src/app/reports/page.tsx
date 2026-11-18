"use client";

import React from "react";
import Link from "next/link";
import { FileText, CheckCircle2, Shield, AlertTriangle, ExternalLink, ArrowRight } from "lucide-react";
import { AppLayout } from "@/components/layout/app-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function ReportsPage() {
  return (
    <AppLayout>
      <div className="space-y-8 max-w-6xl mx-auto">
        <div className="border-b border-border/80 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Engineering Reports
          </h1>
          <p className="text-sm text-muted-foreground">
            Audit-ready technical documentation synthesized by the Reporting Agent for completed
            tasks.
          </p>
        </div>

        {/* Phase Notification Banner */}
        <div className="p-4 rounded-lg bg-card/60 border border-border flex items-start gap-3">
          <FileText className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <p className="font-semibold text-foreground">
              Audit-Ready Report Generator (Reporting Agent)
            </p>
            <p className="text-muted-foreground leading-relaxed">
              When an autonomous task completes verification in Phase 7, Devora compiles:
              Original Developer Request &bull; Root Cause Analysis &bull; Surgical Diffs &bull; Pytest
              Results &bull; Semgrep Security Review findings. Reports are embedded into GitHub Pull
              Request descriptions.
            </p>
          </div>
        </div>

        {/* Empty State / Demonstration preview */}
        <div className="p-16 text-center border border-dashed border-border rounded-lg bg-card/20">
          <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-60" />
          <h3 className="text-base font-semibold text-foreground mb-1">
            No Engineering Reports Published Yet
          </h3>
          <p className="text-xs text-muted-foreground max-w-md mx-auto mb-6 leading-relaxed">
            Reports will be generated once tasks complete execution and pass automated verification
            in the isolated sandbox.
          </p>
          <Link href="/tasks">
            <Button size="sm" variant="outline">
              View Active Tasks
            </Button>
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}

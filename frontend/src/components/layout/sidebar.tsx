"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  GitPullRequest,
  CheckSquare,
  FileText,
  Settings,
  Terminal,
  Cpu,
  Sparkles,
  Activity,
  ShieldCheck,
  Gauge,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

const navItems = [
  { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { name: "Repositories", href: "/repositories", icon: GitBranch },
  { name: "GitHub Apps", href: "/github", icon: GitPullRequest },
  { name: "Tasks", href: "/tasks", icon: CheckSquare },
  { name: "Benchmarks", href: "/benchmarks", icon: Gauge },
  { name: "Reliability", href: "/reliability", icon: ShieldCheck },
  { name: "Adaptive Engine", href: "/adaptive", icon: Activity },
  { name: "ML Intelligence", href: "/ml", icon: Sparkles },
  { name: "Reports", href: "/reports", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  return (
    <aside className="w-64 border-r border-border bg-card/50 backdrop-blur-xl flex flex-col justify-between h-screen sticky top-0 shrink-0">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-border gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary shadow-[0_0_15px_rgba(37,99,235,0.25)]">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-foreground text-base block leading-none">
              Devora<span className="text-primary font-mono text-sm ml-0.5">.AI</span>
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">
              AI Engineer
            </span>
          </div>
        </div>

        {/* Navigation Items */}
        <div className="px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase font-mono">
            Platform
          </div>
          {navItems.map((item) => {
            const isActive =
              pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all group",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20 shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                )}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 transition-colors",
                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Footer / User Profile snippet */}
      <div className="p-4 border-t border-border bg-card/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 truncate">
            <div className="w-8 h-8 rounded-full bg-secondary border border-border flex items-center justify-center text-xs font-mono font-medium text-foreground">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
            </div>
            <div className="truncate">
              <p className="text-xs font-medium text-foreground truncate">
                {user?.full_name || "Engineer"}
              </p>
              <p className="text-[11px] text-muted-foreground truncate font-mono">
                {user?.email || "dev@devora.ai"}
              </p>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="text-muted-foreground hover:text-destructive p-1.5 rounded-md hover:bg-destructive/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

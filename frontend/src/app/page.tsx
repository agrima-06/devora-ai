import React from "react";
import Link from "next/link";
import {
  Cpu,
  ArrowRight,
  Shield,
  Terminal,
  GitBranch,
  Layers,
  Sparkles,
  CheckCircle2,
  Lock,
  Workflow,
  Search,
  Code2,
  Bug,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary/30">
      {/* Top Navbar */}
      <header className="h-16 border-b border-border/60 bg-background/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary shadow-[0_0_15px_rgba(37,99,235,0.25)]">
            <Cpu className="w-4 h-4" />
          </div>
          <span className="font-bold tracking-tight text-foreground text-lg">
            Devora<span className="text-primary font-mono text-sm ml-0.5">.AI</span>
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
          <a href="#capabilities" className="hover:text-foreground transition-colors">
            Capabilities
          </a>
          <a href="#how-it-works" className="hover:text-foreground transition-colors">
            Architecture
          </a>
          <a href="#security" className="hover:text-foreground transition-colors">
            Security & Sandbox
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Sign In
            </Button>
          </Link>
          <Link href="/signup">
            <Button size="sm" className="gap-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]">
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative px-6 pt-24 pb-20 md:pt-32 md:pb-28 max-w-6xl mx-auto text-center flex flex-col items-center">
        {/* Glow ambient background effect */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-primary/10 blur-[120px] pointer-events-none rounded-full" />

        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-secondary/80 border border-border text-xs text-muted-foreground mb-6 font-mono">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Devora AI Engineering Platform — Phase 2 Online</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-foreground max-w-4xl leading-[1.15] mb-6">
          The Autonomous AI Software Engineer Operating{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-primary to-indigo-400">
            Alongside You
          </span>
        </h1>

        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mb-10 leading-relaxed font-sans">
          Devora understands repositories, plans multi-step development tasks, classifies bugs,
          modifies code in isolated sandboxes, executes automated tests, and verifies changes before
          requesting human approval.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link href="/signup">
            <Button size="lg" className="gap-2 shadow-[0_0_25px_rgba(37,99,235,0.35)] px-8">
              <span>Launch Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="outline" size="lg" className="px-8 border-border">
              Developer Sign In
            </Button>
          </Link>
        </div>

        {/* Guiding Principle Banner */}
        <div className="mt-12 p-4 rounded-lg bg-card/40 border border-border/80 max-w-xl text-xs font-mono text-muted-foreground flex items-center gap-3">
          <Shield className="w-4 h-4 text-primary shrink-0" />
          <span>Core Invariant: &ldquo;Never claim success without execution evidence.&rdquo;</span>
        </div>
      </section>

      {/* Capabilities Section */}
      <section id="capabilities" className="px-6 py-20 border-t border-border/60 bg-card/20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mb-3">
              Comprehensive Engineering Capabilities
            </h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto">
              Engineered with specialized cognitive agents, classical ML, and sandboxed execution.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: Search,
                title: "Codebase Understanding",
                desc: "Tree-sitter and AST symbol extraction with pgvector semantic similarity search.",
              },
              {
                icon: Bug,
                title: "ML Bug Classification",
                desc: "Dedicated Scikit-learn model predicting 8 error taxonomies from tracebacks.",
              },
              {
                icon: Workflow,
                title: "Autonomous Planning",
                desc: "Directed acyclic graph (DAG) task decomposition with verification criteria.",
              },
              {
                icon: Terminal,
                title: "Isolated Sandbox",
                desc: "Resource-constrained Docker execution with network isolation and timeouts.",
              },
              {
                icon: CheckCircle2,
                title: "Iterative Debugging",
                desc: "Bounded 3-iteration fix-and-test loop analyzing stdout and compiler errors.",
              },
              {
                icon: Shield,
                title: "Quality & Security Review",
                desc: "Automated Semgrep OWASP/CWE static vulnerability scanning and Ruff linting.",
              },
            ].map((cap, i) => {
              const Icon = cap.icon;
              return (
                <div
                  key={i}
                  className="p-6 rounded-lg border border-border bg-card/60 hover:border-primary/40 transition-colors group"
                >
                  <div className="w-10 h-10 rounded-md bg-secondary flex items-center justify-center text-primary mb-4 group-hover:bg-primary/20 transition-colors">
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="font-semibold text-foreground text-base mb-2">{cap.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{cap.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="px-6 py-20 border-t border-border/60">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mb-3">
              The Devora Engineering Loop
            </h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto">
              How a developer ticket progresses to an audit-ready, verified pull request.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[
              {
                step: "01",
                title: "Intake & Diagnose",
                desc: "Ingests requirements and traceback. ML classifier tags bug category and localizes files.",
              },
              {
                step: "02",
                title: "Plan & Modify",
                desc: "Planner drafts step DAG. Coding agent applies surgical diffs in an isolated ephemeral workspace.",
              },
              {
                step: "03",
                title: "Sandbox Test",
                desc: "Tester executes Pytest inside a zero-network sandbox. Loops up to 3 times on failures.",
              },
              {
                step: "04",
                title: "Review & Publish",
                desc: "Semgrep verifies security. Synthesizes Markdown report and yields for Human Approval.",
              },
            ].map((item, idx) => (
              <div key={idx} className="p-6 rounded-lg bg-card/40 border border-border relative">
                <span className="font-mono text-3xl font-extrabold text-primary/30 block mb-3">
                  {item.step}
                </span>
                <h3 className="text-base font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-border/60 py-8 px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-muted-foreground gap-4">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-primary" />
          <span className="font-mono">Devora AI Platform — Built for Senior Engineers</span>
        </div>
        <p>&copy; {new Date().getFullYear()} Devora AI. All rights reserved.</p>
      </footer>
    </div>
  );
}

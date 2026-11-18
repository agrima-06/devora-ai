"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Cpu, ArrowRight, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authService } from "@/services/auth-service";
import { useAuth } from "@/lib/auth-context";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);
    try {
      const response = await authService.login(data.email, data.password);
      login(response.access_token, response.user);
      router.push("/dashboard");
    } catch (err: any) {
      setServerError(err.message || "Failed to sign in. Please verify your credentials.");
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center px-4">
      {/* Brand Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary shadow-[0_0_20px_rgba(37,99,235,0.3)]">
          <Cpu className="w-5 h-5" />
        </div>
        <span className="font-bold tracking-tight text-foreground text-2xl">
          Devora<span className="text-primary font-mono text-base ml-0.5">.AI</span>
        </span>
      </div>

      <Card className="w-full max-w-md border-border/80 bg-card/60 backdrop-blur-xl shadow-2xl">
        <CardHeader className="space-y-1">
          <CardTitle className="text-xl font-bold tracking-tight">Engineer Sign In</CardTitle>
          <CardDescription className="text-xs">
            Authenticate to access your repository workspaces and autonomous agents.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {serverError && (
            <div className="mb-4 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Email Address</label>
              <Input
                type="email"
                placeholder="developer@company.com"
                {...register("email")}
                className="bg-secondary/40 font-mono text-xs"
              />
              {errors.email && (
                <p className="text-[11px] text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Password</label>
              <Input
                type="password"
                placeholder="••••••••••••"
                {...register("password")}
                className="bg-secondary/40 font-mono text-xs"
              />
              {errors.password && (
                <p className="text-[11px] text-destructive">{errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full gap-2 mt-2 shadow-[0_0_15px_rgba(37,99,235,0.25)]"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-xs text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-primary hover:underline font-medium">
              Create an account
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

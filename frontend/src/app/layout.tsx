import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "Devora AI — Autonomous AI Software Engineer",
  description:
    "Autonomous AI Software Engineer that understands codebases, plans tasks, modifies code in isolated sandboxes, executes tests, and reviews changes.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

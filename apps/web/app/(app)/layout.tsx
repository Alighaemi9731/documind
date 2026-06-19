"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/Button";
import { useAuth } from "@/lib/auth-context";

/**
 * Authenticated app shell. The middleware gates routes cheaply on the refresh
 * cookie; this layer is the authoritative client check: once auth bootstrap
 * finishes, an unauthenticated user is redirected to /login.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center" aria-busy="true">
        <span
          className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
          aria-hidden="true"
        />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="text-lg font-semibold tracking-tight text-foreground">
            DocuMind
          </Link>
          <nav className="flex items-center gap-4 text-sm" aria-label="Primary">
            <Link
              href="/dashboard"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Projects
            </Link>
            <Link
              href="/settings"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Settings
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
          <Button variant="secondary" onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}

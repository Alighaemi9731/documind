"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui/Spinner";
import { useAuth } from "@/lib/auth-context";

/**
 * Admin-only gate. The app shell already requires authentication; this layer
 * additionally requires `role === "admin"` and redirects non-admins to the
 * dashboard once auth has bootstrapped (the API enforces the same via the
 * `require_admin` chain, so this is purely a UX guard).
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user && user.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user || user.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center" aria-busy="true">
        <Spinner size="lg" className="text-muted-foreground" />
      </div>
    );
  }

  return <>{children}</>;
}

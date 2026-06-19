"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { Nav } from "@/components/ui/Nav";
import { Spinner } from "@/components/ui/Spinner";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/cn";
import { usePendingCount } from "@/lib/use-pending-count";

/**
 * Authenticated app shell with the glass nav. The middleware gates routes
 * cheaply; this layer is the authoritative client check: once auth bootstrap
 * finishes, an unauthenticated user is redirected to /login. The Admin entry is
 * rendered only for `role === "admin"` and carries a pending-registrations badge
 * when the install is in approval mode.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isAdmin = user?.role === "admin";
  const pendingCount = usePendingCount(!!isAdmin);

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
        <Spinner size="lg" className="text-muted-foreground" />
      </div>
    );
  }

  const links: { href: string; label: string; badge?: number }[] = [
    { href: "/dashboard", label: "Projects" },
    { href: "/settings", label: "Settings" },
  ];
  if (isAdmin) {
    links.push({ href: "/admin", label: "Admin", badge: pendingCount || undefined });
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Nav>
        <div className="flex items-center gap-6">
          <Link
            href="/dashboard"
            className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 text-sm sm:flex" aria-label="Primary">
            {links.map((link) => (
              <NavLink
                key={link.href}
                href={link.href}
                label={link.label}
                badge={link.badge}
                active={pathname === link.href || pathname.startsWith(`${link.href}/`)}
              />
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden max-w-[12rem] truncate text-sm text-muted-foreground md:inline">
            {user.email}
          </span>
          <ThemeToggle />
          <Button variant="secondary" size="sm" onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </Nav>

      {/* Mobile nav row */}
      <nav
        className="flex items-center gap-1 overflow-x-auto border-b border-border px-4 py-2 text-sm sm:hidden"
        aria-label="Primary mobile"
      >
        {links.map((link) => (
          <NavLink
            key={link.href}
            href={link.href}
            label={link.label}
            badge={link.badge}
            active={pathname === link.href || pathname.startsWith(`${link.href}/`)}
          />
        ))}
      </nav>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}

function NavLink({
  href,
  label,
  active,
  badge,
}: {
  href: string;
  label: string;
  active: boolean;
  badge?: number;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
      {badge ? (
        <span
          className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-xs font-semibold text-accent-foreground"
          aria-label={`${badge} pending`}
        >
          {badge}
        </span>
      ) : null}
    </Link>
  );
}

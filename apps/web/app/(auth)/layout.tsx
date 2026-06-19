import Link from "next/link";

import { LandingBrandName } from "@/components/LandingBrand";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <Link
          href="/"
          className="rounded text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <LandingBrandName />
        </Link>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-8">
        <section className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 shadow-lg">
          {children}
        </section>
      </main>
    </div>
  );
}

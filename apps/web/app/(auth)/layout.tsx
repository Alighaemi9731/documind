import Link from "next/link";

import { HeroArt } from "@/components/HeroArt";
import { LandingBrandName } from "@/components/LandingBrand";
import { MotionDiv } from "@/components/ui/motion";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

/**
 * Split-panel auth shell. On large screens a branded aside (aurora + a compact
 * version of the hero art) sits alongside the form card; on small screens the
 * aside collapses and only the centered card shows. The shell is a server
 * component — the only client islands are the theme toggle, branded name, and
 * the lazy `MotionDiv` entrance, so first paint stays instant.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative grid min-h-screen lg:grid-cols-2">
      {/* ---- Branded aside (decorative, lg+) ---- */}
      <aside className="relative hidden overflow-hidden border-e border-border bg-card lg:flex lg:flex-col">
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="aurora" />
          <div className="hero-dots" />
        </div>

        <div className="relative flex flex-1 flex-col p-10 xl:p-14">
          <Link
            href="/"
            className="inline-flex w-fit rounded text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
          >
            <LandingBrandName />
          </Link>

          <div className="flex flex-1 flex-col items-center justify-center">
            <MotionDiv variant="scale" duration={0.6} className="w-full max-w-md">
              <HeroArt className="h-auto w-full" />
            </MotionDiv>
          </div>

          <MotionDiv variant="fade-up" duration={0.5} className="max-w-md">
            <p className="text-balance text-2xl font-semibold leading-snug tracking-tight">
              Answers from your documents — grounded and cited.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Upload your files, ask in plain language, and get answers drawn strictly from your
              sources — with citations, or a plain &ldquo;not in your documents.&rdquo;
            </p>
          </MotionDiv>
        </div>
      </aside>

      {/* ---- Form panel ---- */}
      <div className="relative flex min-h-screen flex-col">
        {/* Faint ambience on small screens where the aside is hidden. */}
        <div className="pointer-events-none absolute inset-0 lg:hidden" aria-hidden="true">
          <div className="aurora opacity-70" />
        </div>

        <header className="relative mx-auto flex w-full max-w-md items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="rounded text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:invisible"
          >
            <LandingBrandName />
          </Link>
          <ThemeToggle />
        </header>

        <main className="relative flex flex-1 items-center justify-center px-6 pb-12 pt-2">
          <MotionDiv variant="fade-up" duration={0.45} className="w-full max-w-sm">
            <section className="rounded-3xl border border-border bg-card p-8 shadow-xl">
              {children}
            </section>
          </MotionDiv>
        </main>
      </div>
    </div>
  );
}

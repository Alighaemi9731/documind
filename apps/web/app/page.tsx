import Link from "next/link";

import { HeroArt } from "@/components/HeroArt";
import { LandingBrandName } from "@/components/LandingBrand";
import { Button } from "@/components/ui/Button";
import { MotionDiv } from "@/components/ui/motion";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

/**
 * Marketing landing. The page itself is a SERVER component with no data work, so
 * it first-paints instantly and stays correct without JS (ARCHITECTURE.md §11).
 * The only client islands are the theme toggle, the branded app name, and the
 * lazy `MotionDiv` entrance wrappers — Framer is never in the initial chunk and
 * the layout is fully resolved by CSS before (and without) hydration.
 */
export default function HomePage() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      {/* Ambient backdrop (decorative, non-interactive). */}
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <div className="aurora" />
        <div className="hero-grid" />
      </div>

      <SiteHeader />

      <main className="flex-1">
        <Hero />
        <HowItWorks />
        <Features />
      </main>

      <SiteFooter />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function SiteHeader() {
  return (
    <header className="sticky top-0 z-20">
      <div className="mx-auto mt-3 flex w-full max-w-6xl items-center justify-between gap-4 rounded-2xl border border-border/70 px-4 py-2.5 shadow-sm glass-surface sm:px-5">
        <span className="text-lg font-semibold tracking-tight">
          <LandingBrandName />
        </span>
        <nav className="hidden items-center gap-1 text-sm text-muted-foreground sm:flex">
          <a href="#how" className="rounded-md px-3 py-1.5 transition-colors hover:text-foreground">
            How it works
          </a>
          <a
            href="#features"
            className="rounded-md px-3 py-1.5 transition-colors hover:text-foreground"
          >
            Features
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Sign in
            </Button>
          </Link>
          <Link href="/register" className="hidden sm:block">
            <Button size="sm">Get started</Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero() {
  return (
    <section className="mx-auto grid w-full max-w-6xl items-center gap-10 px-6 pb-12 pt-14 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-8 lg:pb-20">
      {/* Copy column */}
      <MotionDiv variant="fade-up" duration={0.5} className="flex flex-col items-start text-start">
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          Self-hostable · grounded · cited
        </span>

        <h1 className="mt-6 text-balance text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
          Answers from <span className="text-accent">your</span> documents — grounded and cited.
        </h1>

        <p className="mt-6 max-w-xl text-balance text-lg leading-relaxed text-muted-foreground">
          <LandingBrandName /> is an open, multi-tenant RAG platform you run yourself. Upload your
          files, ask in plain language, and get answers drawn strictly from your documents — each
          with citations, or a plain &ldquo;not in your documents.&rdquo;
        </p>

        <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Link href="/register">
            <Button size="lg" className="w-full sm:w-auto">
              Get started — it&apos;s free
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg" className="w-full sm:w-auto">
              Sign in
            </Button>
          </Link>
        </div>

        <dl className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
          <TrustItem label="Private by default" />
          <TrustItem label="Bring your own keys" />
          <TrustItem label="فارسی & English" />
        </dl>
      </MotionDiv>

      {/* Art column */}
      <MotionDiv
        variant="scale"
        duration={0.6}
        className="relative mx-auto w-full max-w-[34rem] lg:max-w-none"
      >
        <div className="relative rounded-3xl border border-border/70 bg-card/40 p-3 shadow-xl glass-surface">
          <HeroArt className="h-auto w-full" />
        </div>
      </MotionDiv>
    </section>
  );
}

function TrustItem({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2">
      <CheckIcon />
      <dt>{label}</dt>
    </div>
  );
}

/* ----------------------------------------------------------- how it works */

const STEPS = [
  {
    n: "1",
    title: "Upload",
    body: "Drop in PDF, DOCX, TXT, or Markdown. We parse and index them privately — no network egress during parsing.",
  },
  {
    n: "2",
    title: "Ask",
    body: "Ask anything in plain language, in Persian or English. Retrieval matches the exact passages that matter.",
  },
  {
    n: "3",
    title: "Get a cited answer",
    body: "Read a grounded answer with citations to the source chunk — or a plain “it isn’t in your documents.”",
  },
] as const;

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-24 border-t border-border/60">
      <div className="mx-auto w-full max-w-6xl px-6 py-16 sm:py-20">
        <MotionDiv variant="fade-up" duration={0.5} className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            From documents to grounded answers — in three steps.
          </h2>
          <p className="mt-3 text-balance text-muted-foreground">
            No prompt engineering, no hallucinations. Just your sources, retrieved and cited.
          </p>
        </MotionDiv>

        <ol className="mt-12 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, i) => (
            <MotionDiv key={step.n} variant="fade-up" duration={0.5}>
              <li className="relative h-full rounded-2xl border border-border bg-card/80 p-6 shadow-sm">
                <span
                  className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-sm font-semibold text-accent ring-1 ring-inset ring-accent/25"
                  aria-hidden="true"
                >
                  {step.n}
                </span>
                <h3 className="mt-4 text-lg font-semibold tracking-tight">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
                {i < STEPS.length - 1 ? <ArrowConnector /> : null}
              </li>
            </MotionDiv>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- features */

const FEATURES = [
  {
    title: "Strictly grounded",
    body: "Every answer is drawn only from your files, with citations to the exact chunk. Below the confidence threshold, it refuses instead of guessing.",
    icon: <ShieldIcon />,
  },
  {
    title: "Bring your own keys",
    body: "Use the shared free Gemini tier or your own OpenAI, Anthropic, Gemini, or Groq keys — encrypted at rest and never returned.",
    icon: <KeyIcon />,
  },
  {
    title: "Persian & English",
    body: "First-class multilingual retrieval and a fully RTL-correct interface, light or dark, out of the box.",
    icon: <GlobeIcon />,
  },
] as const;

function Features() {
  return (
    <section id="features" className="scroll-mt-24 border-t border-border/60">
      <div className="mx-auto w-full max-w-6xl px-6 py-16 sm:py-20">
        <ul className="grid gap-4 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <MotionDiv key={f.title} variant="fade-up" duration={0.5}>
              <li className="group h-full rounded-2xl border border-border bg-card/80 p-6 shadow-sm transition-shadow hover:shadow-md">
                <span
                  className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 text-accent ring-1 ring-inset ring-accent/20"
                  aria-hidden="true"
                >
                  {f.icon}
                </span>
                <h3 className="mt-4 text-base font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
              </li>
            </MotionDiv>
          ))}
        </ul>

        {/* Closing call-to-action band */}
        <MotionDiv variant="fade-up" duration={0.5}>
          <div className="relative mt-12 overflow-hidden rounded-3xl border border-border bg-card/70 p-8 text-center shadow-md sm:p-12">
            <div className="aurora opacity-70" aria-hidden="true" />
            <div className="relative">
              <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
                Your documents, answered with receipts.
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-balance text-muted-foreground">
                Spin up your own private instance and start asking in minutes.
              </p>
              <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link href="/register">
                  <Button size="lg" className="w-full sm:w-auto">
                    Create your account
                  </Button>
                </Link>
                <Link href="/login">
                  <Button variant="ghost" size="lg" className="w-full sm:w-auto">
                    Sign in
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </MotionDiv>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ footer */

function SiteFooter() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-xs text-muted-foreground sm:flex-row">
        <span className="font-medium text-foreground">
          <LandingBrandName />
        </span>
        <span>AGPL-3.0 · self-hosted · grounded &amp; cited</span>
      </div>
    </footer>
  );
}

/* -------------------------------------------------------------- icons (inline) */

function CheckIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="shrink-0 text-accent"
    >
      <path
        d="M5 12.5l4.2 4.2L19 7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ArrowConnector() {
  // Positioned at the inline-end edge with a logical translate, and the glyph
  // mirrors under RTL via the scoped `.step-arrow` rule in globals.css.
  return (
    <span
      aria-hidden="true"
      className="step-arrow pointer-events-none absolute end-0 top-1/2 hidden -translate-y-1/2 text-border sm:block"
    >
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
        <path
          d="M5 12h14M13 6l6 6-6 6"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

function ShieldIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3l7 3v5c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6l7-3z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M8.6 12.2l2.4 2.4 4.4-4.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function KeyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="4" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M11 11l8 8M16 16l2-2M19 19l2-2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M3 12h18M12 3c2.5 2.4 2.5 15.6 0 18M12 3c-2.5 2.4-2.5 15.6 0 18"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

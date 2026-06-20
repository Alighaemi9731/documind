import Link from "next/link";

import { ChatDemo } from "@/components/ChatDemo";
import { LandingBrandName } from "@/components/LandingBrand";
import { Reveal } from "@/components/Reveal";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

/**
 * Marketing landing — immersive + scroll-driven. A fixed, animated full-page
 * backdrop (drifting accent orbs + a fading grid) sits behind a narrative of
 * scroll-revealed sections. The page is a SERVER component; the only client
 * islands are the theme toggle and the `Reveal` scroll wrappers, so first paint
 * is instant and correct without JS (ARCHITECTURE.md §11) — Framer is never
 * pulled in. All effects are token-driven (light/dark + operator branding) and
 * disabled under prefers-reduced-motion.
 */
export default function HomePage() {
  return (
    <div className="relative flex min-h-screen flex-col">
      {/* Fixed immersive backdrop. */}
      <div className="bg-page" aria-hidden="true">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <Statement />
        <HowItWorks />
        <Features />
        <Providers />
        <CTA />
      </main>
      <SiteFooter />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 px-4 pt-3 sm:px-6">
      <div className="glass-surface mx-auto flex w-full max-w-6xl items-center justify-between gap-4 rounded-2xl border border-border/70 px-4 py-2.5 shadow-sm sm:px-5">
        <span className="text-lg font-semibold tracking-tight">
          <LandingBrandName />
        </span>
        <nav className="hidden items-center gap-1 text-sm text-muted-foreground md:flex">
          <HeaderLink href="#how">How it works</HeaderLink>
          <HeaderLink href="#features">Features</HeaderLink>
          <HeaderLink href="#providers">Providers</HeaderLink>
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

function HeaderLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} className="rounded-md px-3 py-1.5 transition-colors hover:text-foreground">
      {children}
    </a>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero() {
  return (
    <section className="mx-auto grid w-full max-w-6xl items-center gap-12 px-6 pb-20 pt-16 sm:pt-24 lg:grid-cols-[1.02fr_0.98fr] lg:gap-10 lg:pb-28">
      <div className="flex flex-col items-start text-start">
        <Reveal className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          Self-hostable · grounded · cited
        </Reveal>

        <Reveal as="div" delay={60}>
          <h1 className="mt-6 text-balance text-5xl font-semibold leading-[1.04] tracking-tight sm:text-6xl lg:text-[4.25rem]">
            Chat with <span className="gradient-text">your documents</span>.<br />
            Every answer, cited.
          </h1>
        </Reveal>

        <Reveal as="div" delay={120}>
          <p className="mt-6 max-w-xl text-balance text-lg leading-relaxed text-muted-foreground">
            <LandingBrandName /> is an open, self-hosted RAG platform. Upload your files, ask in
            plain language — Persian or English — and get answers drawn{" "}
            <span className="font-medium text-foreground">strictly</span> from your sources, each
            with citations. If it isn’t in your documents, it says so.
          </p>
        </Reveal>

        <Reveal
          as="div"
          delay={180}
          className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center"
        >
          <Link href="/register">
            <Button size="lg" className="w-full sm:w-auto">
              Get started — it’s free
            </Button>
          </Link>
          <a href="#how">
            <Button variant="secondary" size="lg" className="w-full sm:w-auto">
              See how it works
            </Button>
          </a>
        </Reveal>

        <Reveal
          as="div"
          delay={240}
          className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-3 text-sm text-muted-foreground"
        >
          <Trust label="Private by default" />
          <Trust label="Bring your own keys" />
          <Trust label="فارسی & English" />
        </Reveal>
      </div>

      {/* Visual */}
      <div className="relative">
        <div
          className="pointer-events-none absolute -inset-6 -z-10 rounded-[2.5rem] bg-accent/15 blur-3xl"
          aria-hidden="true"
        />
        <Reveal as="div" className="flex justify-center lg:justify-end">
          <ChatDemo />
        </Reveal>
      </div>
    </section>
  );
}

function Trust({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-2">
      <Check />
      <span>{label}</span>
    </span>
  );
}

/* --------------------------------------------------------------- statement */

function Statement() {
  return (
    <section className="mx-auto w-full max-w-5xl px-6 py-20 sm:py-28">
      <Reveal className="text-center">
        <h2 className="mx-auto max-w-3xl text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
          Most AI confidently makes things up.
          <br />
          <span className="text-muted-foreground">This one shows its receipts</span> — or admits it
          doesn’t know.
        </h2>
      </Reveal>

      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        <Reveal as="div">
          <div className="h-full rounded-2xl border border-[hsl(142_50%_45%)]/30 bg-[hsl(142_55%_45%)]/[0.06] p-6">
            <Badge tone="ok">Grounded</Badge>
            <p className="mt-3 text-sm leading-relaxed text-foreground">
              “Annual plans are refundable within <span className="font-semibold">30 days</span>.”
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              ↳ cited to <span className="font-medium text-foreground">handbook.pdf · p.12</span>
            </p>
          </div>
        </Reveal>
        <Reveal as="div" delay={90}>
          <div className="h-full rounded-2xl border border-border bg-card/70 p-6">
            <Badge tone="muted">Not in your documents</Badge>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              “I can’t find anything about that in your documents.”
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              ↳ refuses below the confidence threshold — <em>before</em> calling the model.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- how it works */

const STEPS = [
  {
    n: "01",
    title: "Upload",
    body: "Drop in PDF, DOCX, TXT, or Markdown. Parsed and indexed privately — no network egress during parsing.",
  },
  {
    n: "02",
    title: "Ask",
    body: "Ask anything in plain language, Persian or English. Hybrid retrieval finds the exact passages that matter.",
  },
  {
    n: "03",
    title: "Get a cited answer",
    body: "Read a grounded answer with citations to the source chunk — streamed live, with the sources shown.",
  },
] as const;

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-24 border-t border-border/50">
      <div className="mx-auto w-full max-w-6xl px-6 py-20 sm:py-28">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent">
            How it works
          </p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            From a pile of documents to answers you can trust — in three steps.
          </h2>
        </Reveal>

        <ol className="mt-14 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal as="li" key={s.n} delay={i * 110}>
              <div className="relative h-full overflow-hidden rounded-2xl border border-border bg-card/70 p-6">
                <span className="text-5xl font-bold tracking-tight text-accent/15">{s.n}</span>
                <h3 className="mt-2 text-lg font-semibold tracking-tight">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </Reveal>
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
    body: "Answers are drawn only from your files, cited to the exact chunk. Below the threshold it refuses instead of guessing.",
    icon: <Shield />,
  },
  {
    title: "Bring your own keys",
    body: "Shared free Gemini tier, or your own OpenAI, Anthropic, Gemini, or Groq keys — encrypted at rest, never returned.",
    icon: <Key />,
  },
  {
    title: "Persian & English",
    body: "First-class multilingual retrieval and a fully RTL-correct interface, light or dark, out of the box.",
    icon: <Globe />,
  },
  {
    title: "Private & self-hosted",
    body: "Runs entirely on your own server. Your documents and questions never leave your infrastructure.",
    icon: <Lock />,
  },
  {
    title: "Injection-resistant",
    body: "Uploaded text is treated as untrusted and fenced — a poisoned document can’t hijack the model or forge a citation.",
    icon: <Bug />,
  },
  {
    title: "Light on resources",
    body: "One Postgres for relational + vectors. Installs in minutes on a small VPS with a single command.",
    icon: <Bolt />,
  },
] as const;

function Features() {
  return (
    <section id="features" className="scroll-mt-24 border-t border-border/50">
      <div className="mx-auto w-full max-w-6xl px-6 py-20 sm:py-28">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent">
            Why DocuMind
          </p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything you need to trust the answer.
          </h2>
        </Reveal>

        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal as="li" key={f.title} delay={(i % 3) * 90}>
              <div className="group h-full rounded-2xl border border-border bg-card/70 p-6 transition-all hover:-translate-y-1 hover:border-accent/40 hover:shadow-lg">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 text-accent ring-1 ring-inset ring-accent/20 transition-colors group-hover:bg-accent/15">
                  {f.icon}
                </span>
                <h3 className="mt-4 text-base font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- providers */

const PROVIDERS = ["Gemini", "OpenAI", "Anthropic", "Groq"] as const;

function Providers() {
  return (
    <section id="providers" className="scroll-mt-24 border-t border-border/50">
      <div className="mx-auto w-full max-w-6xl px-6 py-16 text-center sm:py-20">
        <Reveal>
          <p className="text-sm text-muted-foreground">
            Use the free shared tier, or plug in your own provider keys
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            {PROVIDERS.map((p) => (
              <span
                key={p}
                className="provider-pill rounded-full px-4 py-2 text-sm font-medium text-foreground/80"
              >
                {p}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------------- CTA */

function CTA() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 pb-24">
      <Reveal>
        <div className="relative overflow-hidden rounded-3xl border border-border bg-card/70 p-10 text-center shadow-xl sm:p-16">
          <div className="aurora opacity-80" aria-hidden="true" />
          <div className="relative">
            <h2 className="mx-auto max-w-2xl text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              Your documents, answered with receipts.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-balance text-muted-foreground">
              Spin up your own private instance and start asking in minutes — one command, automatic
              HTTPS, your keys.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
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
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ footer */

function SiteFooter() {
  return (
    <footer className="border-t border-border/50">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-xs text-muted-foreground sm:flex-row">
        <span className="font-medium text-foreground">
          <LandingBrandName />
        </span>
        <span>AGPL-3.0 · self-hosted · grounded &amp; cited</span>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------- small parts */

function Badge({ tone, children }: { tone: "ok" | "muted"; children: React.ReactNode }) {
  return (
    <span
      className={
        tone === "ok"
          ? "inline-flex items-center gap-1.5 rounded-full bg-[hsl(142_55%_45%)]/12 px-2.5 py-1 text-xs font-semibold text-[hsl(142_60%_38%)] dark:text-[hsl(142_55%_62%)]"
          : "inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground"
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

function Check() {
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

function Shield() {
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

function Key() {
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

function Globe() {
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

function Lock() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="10" width="16" height="11" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M8 10V7a4 4 0 0 1 8 0v3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Bug() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="7" y="8" width="10" height="11" rx="5" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M9 8a3 3 0 0 1 6 0M3 12h3M18 12h3M4 18h3M17 18h3M4 6l3 2M20 6l-3 2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Bolt() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

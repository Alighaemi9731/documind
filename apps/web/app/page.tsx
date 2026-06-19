import Link from "next/link";

import { LandingBrandName } from "@/components/LandingBrand";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

/**
 * Marketing landing — intentionally STATIC (no Framer, no data work) so it
 * first-paints instantly and stays in the lean initial chunk (ARCHITECTURE.md
 * §11). The only client islands are the theme toggle and the branded app name.
 */
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <span className="text-lg font-semibold tracking-tight">
          <LandingBrandName />
        </span>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Sign in
            </Button>
          </Link>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
          Self-hostable · grounded · cited
        </span>
        <h1 className="max-w-3xl text-balance text-5xl font-semibold tracking-tight sm:text-6xl">
          Answers from <span className="text-accent">your</span> documents — grounded and cited.
        </h1>
        <p className="mt-6 max-w-xl text-balance text-lg leading-relaxed text-muted-foreground">
          <LandingBrandName /> is an open, multi-tenant RAG platform you run yourself. Upload your
          files, ask in plain language, and get answers drawn strictly from your documents — with
          citations, or a plain &ldquo;not in your documents.&rdquo;
        </p>
        <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
          <Link href="/register">
            <Button size="lg" className="w-full sm:w-auto">
              Get started
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg" className="w-full sm:w-auto">
              Sign in
            </Button>
          </Link>
        </div>

        <ul className="mt-16 grid w-full max-w-3xl gap-4 text-start sm:grid-cols-3">
          <Feature
            title="Strictly grounded"
            body="Every answer is drawn only from your files, with citations to the exact chunk."
          />
          <Feature
            title="Bring your own keys"
            body="Use the shared free tier or your own provider keys — encrypted at rest."
          />
          <Feature
            title="Persian & English"
            body="Multilingual retrieval and a fully RTL-correct interface out of the box."
          />
        </ul>
      </main>

      <footer className="mx-auto w-full max-w-5xl px-6 py-8 text-center text-xs text-muted-foreground">
        AGPL-3.0 · self-hosted
      </footer>
    </div>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <li className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{body}</p>
    </li>
  );
}

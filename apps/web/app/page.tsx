export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-16">
      <section className="w-full max-w-xl rounded-3xl border border-border bg-card p-12 text-center shadow-sm">
        <h1 className="text-5xl font-semibold tracking-tight text-card-foreground">DocuMind</h1>
        <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
          A self-hostable, multi-tenant platform for grounded answers over your own documents.
        </p>
      </section>
    </main>
  );
}

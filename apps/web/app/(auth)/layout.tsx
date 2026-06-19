export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-16">
      <section className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 shadow-sm">
        {children}
      </section>
    </main>
  );
}

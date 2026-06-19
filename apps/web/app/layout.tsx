import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

import { ToastProvider } from "@/components/ui/Toast";
import { AuthProvider } from "@/lib/auth-context";
import { BrandingProvider } from "@/lib/branding";
import { ThemeProvider, ThemeScript } from "@/lib/theme";

export const metadata: Metadata = {
  title: "DocuMind",
  description: "Self-hostable multi-tenant RAG platform.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // The middleware sets a per-request CSP nonce; the pre-hydration ThemeScript
  // must carry it to run under the strict no-unsafe-inline policy.
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ThemeScript nonce={nonce} />
      </head>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <ThemeProvider>
          <BrandingProvider>
            <ToastProvider>
              <AuthProvider>{children}</AuthProvider>
            </ToastProvider>
          </BrandingProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

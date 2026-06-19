import type { NextConfig } from "next";

// In production, Caddy routes /api/* straight to the FastAPI backend and the
// Next server never sees those paths (so this rewrite is inert). Under
// `next dev` (no Caddy) it proxies /api/* to the backend so the SPA stays
// same-origin in local development.
const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

export default {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${INTERNAL_API_URL}/api/:path*` }];
  },
} satisfies NextConfig;

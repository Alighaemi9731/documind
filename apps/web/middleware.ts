import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Security-headers + CSP-nonce middleware.
 *
 * Generates a per-request CSP nonce (exposed via the `x-nonce` request header)
 * and sets baseline security headers. The authoritative auth guard is
 * client-side in the `(app)` layout (redirects to /login once bootstrap shows
 * no user) plus the API itself; we deliberately do NOT gate here on the refresh
 * cookie, because it is Path-scoped to /api/auth and is therefore never sent on
 * an app navigation like /dashboard (a cookie check here would misfire). The
 * matcher skips /api, static assets, and image optimization.
 */

export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID().replace(/-/g, "");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  response.headers.set("x-nonce", nonce);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("X-DNS-Prefetch-Control", "off");

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes, incl. the auth cookie-proxy route handler)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, and common static asset extensions
     */
    {
      source:
        "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)",
    },
  ],
};

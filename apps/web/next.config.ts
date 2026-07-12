import type { NextConfig } from "next";

// Security headers applied to every response. CSP is intentionally
// conservative but allows what this app needs: wallet-adapter injects
// inline styles, token logos load from arbitrary image hosts, and the app
// talks to the API/RPC over HTTPS + WSS.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next.js requires 'unsafe-inline' (and 'unsafe-eval' in dev) for its
      // runtime; wallet adapters inline small scripts.
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      // API + Solana RPC live on other https/wss origins; localhost covers
      // dev/test where the API is served over http (prod never uses it).
      "connect-src 'self' https: wss: http://localhost:* ws://localhost:*",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;

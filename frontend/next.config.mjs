/** @type {import('next').NextConfig} */

// The API lives on its own service, the app on this one. Requests are made
// directly with a bearer token rather than proxied, so CORS on the backend is
// the single place origins are controlled.
//
// NEXT_PUBLIC_API_URL wins when set. Render's blueprint instead injects
// NEXT_PUBLIC_API_HOST, a bare hostname with no scheme, because a service
// reference can only yield a host.
function resolveApiUrl() {
  const explicit = process.env.NEXT_PUBLIC_API_URL;
  if (explicit) return explicit.replace(/\/$/, "");

  const host = process.env.NEXT_PUBLIC_API_HOST;
  if (host) {
    const trimmed = host.replace(/\/$/, "");
    return /^https?:\/\//.test(trimmed) ? trimmed : `https://${trimmed}`;
  }

  return "http://localhost:8000";
}

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: resolveApiUrl(),
  },
  // Next's dev tools badge sits in the bottom-left corner, on top of the
  // terminal's own chrome, which gets in the way of checking layout. It is a
  // development-only overlay and never present in a production build, so this
  // only affects `next dev`. Set to `{}` (or remove the line) to bring it back.
  devIndicators: false,
};

export default nextConfig;

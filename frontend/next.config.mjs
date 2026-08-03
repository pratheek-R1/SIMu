/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The API lives on Railway, the app on Vercel. Requests are made directly
  // with a bearer token rather than proxied, so CORS on the backend is the
  // single place origins are controlled.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;

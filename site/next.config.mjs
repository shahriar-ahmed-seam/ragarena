/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fully static: the leaderboard reads committed JSON at build time, so the
  // deployment needs no server, no database and no API keys.
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;

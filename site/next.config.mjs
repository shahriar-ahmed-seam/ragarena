// GitHub Pages serves a project site from /<repo>, Vercel serves from the root.
// Setting NEXT_PUBLIC_BASE_PATH lets one build target both.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fully static: the leaderboard reads committed JSON at build time, so the
  // deployment needs no server, no database and no API keys.
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;

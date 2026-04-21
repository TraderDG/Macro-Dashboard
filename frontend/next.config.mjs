/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },

  output: process.env.VERCEL ? "export" : "standalone",
  images: { unoptimized: true },

  // rewrites not supported with static export; frontend calls Railway directly via NEXT_PUBLIC_API_URL
  ...( !process.env.VERCEL && {
    async rewrites() {
      const backendUrl =
        process.env.BACKEND_INTERNAL_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        "http://localhost:8000";
      return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
    },
  }),
};

export default nextConfig;

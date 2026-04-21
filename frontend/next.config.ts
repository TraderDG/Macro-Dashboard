import type { NextConfig } from "next";

const isVercel = !!process.env.VERCEL;

const nextConfig: NextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },

  // standalone only for Docker builds; Vercel uses its own output format
  ...(isVercel ? {} : { output: "standalone" }),

  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;

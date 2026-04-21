/** @type {import('next').NextConfig} */
const isCI = !!(process.env.VERCEL || process.env.NETLIFY || process.env.CI);

const nextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  output: isCI ? "export" : "standalone",
  images: { unoptimized: true },

  ...(!isCI && {
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

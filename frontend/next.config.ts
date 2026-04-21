import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output — smaller Docker image, no node_modules needed at runtime
  output: "standalone",

  // Dev: proxy /api/* to local backend (avoids CORS).
  // Prod: nginx handles /api/* routing directly — rewrites are ignored.
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||   // docker-compose dev: http://backend:8000
      process.env.NEXT_PUBLIC_API_URL ||     // local dev: http://localhost:8001
      "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/forge/:path*",
        destination: `${process.env.FORGE_API_URL ?? "http://localhost:8001"}/:path*`,
      },
    ];
  },
  experimental: {
    optimizePackageImports: ["framer-motion", "lucide-react"],
  },
};

export default nextConfig;

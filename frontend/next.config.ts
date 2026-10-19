import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
  turbopack: {
    resolveAlias: {
      canvas: "./lib/empty-module.js",
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.INTERNAL_API_URL || "http://backend:8000/api"}/:path*`,
      },
    ];
  },
};

export default nextConfig;

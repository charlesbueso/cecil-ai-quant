import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // In production on Vercel, routes in vercel.json handle /api/* → Python.
  // Rewrites are only needed in local development to proxy to FastAPI.
  async rewrites() {
    if (process.env.VERCEL) return [];
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`
            : "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;

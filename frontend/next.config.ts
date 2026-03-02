import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles only the files needed to run the app.
  // This produces a much smaller Docker image (~200 MB vs ~1 GB with node_modules).
  // Required for the Docker build — do not remove.
  output: "standalone",

  // Proxy API calls to the backend server during local development.
  // This allows the frontend preview to reach the backend even in
  // sandboxed browser contexts that cannot access other localhost ports.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles only the files needed to run the app.
  // This produces a much smaller Docker image (~200 MB vs ~1 GB with node_modules).
  // Required for the Docker build — do not remove.
  output: "standalone",
};

export default nextConfig;

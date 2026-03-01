/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so we can drop the built site into Flask without a Node server
  output: "export",
  basePath: "/model",
  assetPrefix: "/model",
  // Skip local type and lint checks in this export-only build to avoid toolchain downloads
  typescript: {
    ignoreBuildErrors: true,
  },
  allowedDevOrigins: ["http://10.1.82.76:3000"],
};

export default nextConfig;

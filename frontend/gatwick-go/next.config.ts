/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so we can drop the built site into Flask without a Node server
  output: "export",
  // Skip local type and lint checks in this export-only build to avoid toolchain downloads
  typescript: {
    ignoreBuildErrors: true,
  },
  turbopack: {
    root: __dirname,
  },
  allowedDevOrigins: ["http://10.1.82.76:3000"],
};

export default nextConfig;

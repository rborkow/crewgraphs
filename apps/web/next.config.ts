import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The contracts and charts packages ship raw TypeScript
  // (`exports: "./src/index.ts"`), so Next must transpile them rather than
  // treat them as prebuilt dependencies.
  transpilePackages: ["@crewgraphs/contracts", "@crewgraphs/charts"]
};

export default nextConfig;

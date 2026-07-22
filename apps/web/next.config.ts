import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The contracts package ships raw TypeScript (`exports: "./src/index.ts"`),
  // so Next must transpile it rather than treat it as a prebuilt dependency.
  transpilePackages: ["@crewgraphs/contracts"]
};

export default nextConfig;

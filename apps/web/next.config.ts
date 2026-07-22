import type { NextConfig } from "next";
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

const nextConfig: NextConfig = {
  // The contracts and charts packages ship raw TypeScript
  // (`exports: "./src/index.ts"`), so Next must transpile them rather than
  // treat them as prebuilt dependencies.
  transpilePackages: ["@crewgraphs/contracts", "@crewgraphs/charts"]
};

// Populate the Cloudflare bindings (Hyperdrive, KV) inside `next dev` so
// `getCloudflareContext()` resolves the same way it does on Workers. Wrangler
// supplies the Hyperdrive local connection string from
// CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE.
initOpenNextCloudflareForDev();

export default nextConfig;

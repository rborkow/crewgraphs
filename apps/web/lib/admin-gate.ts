import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { isAdminDatabaseConfigured } from "@/lib/admin-db";

/**
 * Cloudflare Access is the perimeter; this keeps the routes dark before that
 * policy and the separate read-only connection are configured.
 *
 * Known follow-up: validate the Access JWT signature and claims in-app.
 */
export async function requireAdminAccess(): Promise<void> {
  const requestHeaders = await headers();
  if (!requestHeaders.get("Cf-Access-Jwt-Assertion")) notFound();
  if (!(await isAdminDatabaseConfigured())) notFound();
}

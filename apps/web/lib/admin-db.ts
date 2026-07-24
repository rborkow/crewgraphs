import postgres from "postgres";

async function resolveAdminConnectionString(): Promise<string | null> {
  try {
    const { getCloudflareContext } = await import("@opennextjs/cloudflare");
    const { env } = getCloudflareContext();
    const adminUrl = (env as { ADMIN_DATABASE_URL?: string }).ADMIN_DATABASE_URL;
    if (adminUrl) return adminUrl;
  } catch {
    // No Cloudflare request context here; fall through to the Node environment.
  }

  return process.env.ADMIN_DATABASE_URL ?? null;
}

export async function isAdminDatabaseConfigured(): Promise<boolean> {
  return (await resolveAdminConnectionString()) !== null;
}

/** Run a parameterized query using the separately provisioned admin_ro connection. */
export async function adminQuery<T = Record<string, unknown>>(
  text: string,
  params: readonly unknown[] = []
): Promise<T[]> {
  const connectionString = await resolveAdminConnectionString();
  if (!connectionString) throw new Error("ADMIN_DATABASE_URL is unset.");

  const sql = postgres(connectionString, { max: 1, fetch_types: false });
  try {
    const rows = await sql.unsafe(text, params as never[]);
    return rows as unknown as T[];
  } finally {
    await sql.end();
  }
}

import postgres from "postgres";

/**
 * The single I/O primitive for the web tier's read-model queries.
 *
 * Connection-string resolution has two paths:
 *
 *  1. Workers runtime (production) and `next dev` (via `initOpenNextCloudflareForDev`
 *     in next.config.ts): the Hyperdrive binding exposes a pooled connection
 *     string on `getCloudflareContext().env.HYPERDRIVE.connectionString`. In
 *     `next dev`, OpenNext wires that binding to the local Postgres URL that
 *     wrangler reads from `CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE`.
 *  2. Any context without a Cloudflare platform proxy (a bare Node process, or a
 *     dev run where the platform proxy isn't up yet): fall back to reading
 *     `CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE` from `process.env`.
 *     For local dev this variable must be exported into the shell (Next does not
 *     auto-load the repo-root `.env`).
 *
 * Vitest never reaches this module: the read-model seams are mocked and the pure
 * mappers live in `read-model.ts`, so no test opens a connection.
 *
 * A fresh postgres.js client is created, queried, and closed per call —
 * Hyperdrive owns the real connection pool, so per-request clients are the
 * recommended pattern. postgres.js (not `pg`) because it is pure JS and
 * bundles cleanly for Workers — `pg` lazy-requires pg-cloudflare, which
 * Next's file tracing cannot resolve. Only parameterized queries are issued.
 */

interface HyperdriveBinding {
  connectionString: string;
}

async function resolveConnectionString(): Promise<string> {
  try {
    const { getCloudflareContext } = await import("@opennextjs/cloudflare");
    const { env } = getCloudflareContext();
    const hyperdrive = (env as { HYPERDRIVE?: HyperdriveBinding }).HYPERDRIVE;
    if (hyperdrive?.connectionString) return hyperdrive.connectionString;
  } catch {
    // No Cloudflare platform proxy in this context — fall through to the env var.
  }

  const local = process.env.CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE;
  if (local) return local;

  throw new Error(
    "No database connection string available: the HYPERDRIVE binding is not present and " +
      "CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE is unset. For local dev, export it " +
      "from the repo-root .env before running `next dev`."
  );
}

/** Run a parameterized read query ($1-style placeholders) and return its rows. */
export async function query<T = Record<string, unknown>>(
  text: string,
  params: readonly unknown[] = []
): Promise<T[]> {
  const connectionString = await resolveConnectionString();
  const sql = postgres(connectionString, { max: 1, fetch_types: false });
  try {
    const rows = await sql.unsafe(text, params as never[]);
    return rows as unknown as T[];
  } finally {
    await sql.end();
  }
}

# CrewGraphs owner setup

Complete these owner-managed steps before deploying the application:

1. Create a Neon project and the `pipeline_rw`, `curator`, and `web_ro` database roles.
2. Create the Cloudflare R2 bucket `crewgraphs-raw`.
3. Create a Cloudflare Hyperdrive configuration pointing at Neon, then paste its ID into `apps/web/wrangler.jsonc`.
4. Create a Cloudflare KV namespace, then paste its ID into `apps/web/wrangler.jsonc`.
5. Create the GitHub repository and add these secrets: `NEON_DATABASE_URL`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`.
6. Run `wrangler login` on the owner workstation.
7. Bind `crewgraphs.com` to the Worker with a Cloudflare custom domain (the domain is already on the Cloudflare account).
8. Add a Cloudflare Access policy for `/admin/*` for the owner email.

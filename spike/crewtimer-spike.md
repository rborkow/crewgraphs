# CrewTimer spike — unpark criteria and investigation plan

**Date:** 2026-07-23 · **Status:** Parked (Phase 7 of the results-ingestion plan)
**Context:** `docs/superpowers/specs/2026-07-23-results-ingestion-design.md` §Phase 7; survey `docs/superpowers/research/2026-07-23-results-timing-providers.md`.

## What we know (verified 2026-07-23)

- crewtimer.com is a React SPA; regatta pages at `/regatta/r{id}` (e.g. r16088 = 2026 Summer Festival of Rowing). Largest single share of row2k's current live-results links (18/79).
- Data loads via Firebase — the only non-asset network request observed was Firebase Storage on project **`crewtimer-results`** (`firebasestorage.googleapis.com/v0/b/crewtimer-results.appspot.com/...`). Race data itself moves over Firebase channels (RTDB or Firestore websockets), which don't appear as inspectable REST calls.
- Regatta ids are sequential-ish `r#####` (r15322–r16088 observed in 2026 links).
- No robots.txt, no ToU found.

## Investigation steps (in order, ~half a day)

1. **Identify the Firebase backend type.** Load a regatta page with devtools; look for `wss://*.firebaseio.com/.ws?...` (RTDB) vs `firestore.googleapis.com/google.firestore.v1.Firestore/Listen` (Firestore). The SPA bundle's firebase config object (apiKey, databaseURL, projectId) is embedded client-side — extract it from the JS bundle.
2. **Test public REST readability.**
   - RTDB: `curl 'https://<databaseURL>/.json?shallow=true'` then probe paths like `/results/r16088.json`, `/regatta/r16088.json`. Rules allowing public client reads usually allow REST reads with the same (no) auth.
   - Firestore: REST `GET https://firestore.googleapis.com/v1/projects/crewtimer-results/databases/(default)/documents/<collection>` with the web apiKey.
3. **Map the document shape** for one regatta (events, entries, times, penalties, club fields) and compare against `core.regatta*` mapping needs.
4. **Enumerate the id space**: probe r1..r{max} shallow keys or a results index document if one exists.
5. **Check the mobile app / site for an export path** — CrewTimer publishes CSV exports for organizers; a public per-regatta CSV endpoint would beat Firebase RE.

## Unpark criteria (both required)

1. Public unauthenticated REST read of full results confirmed (step 2), stable across two regattas.
2. `results-gap-report` (Phase 5) shows CrewTimer-hosted regattas materially overlap the cohort (clubs we publish) — i.e., the corpus gap is worth an adapter.

## Already reserved

`crewtimer` value in `core.source_type` (migration 014) · R2 prefix `raw/crewtimer/regatta/{rId}/…` · provider host mapping in the row2k registry (`crewtimer.com → crewtimer`).

## Posture

Same as other providers: honest UA, polite rates, quarantine on block. Firebase config keys embedded in a public web app are not secrets, but reading through them is a client-protocol read — prefer an official export path if one exists, and include CrewTimer in the courtesy-email round if unparked.

# CrewGraphs Athlete PII Policy

**Date:** 2026-07-23
**Status:** Approved (owner-confirmed: ecosystem-norm stance)
**Applies to:** all person-level data acquired from results sources (`docs/superpowers/specs/2026-07-23-results-ingestion-design.md`). IRS Part VII people are governed by the existing spike-5 display rule and are out of scope here.

## Grounding: what the ecosystem does

Verified 2026-07-23:

- Every rowing results publisher — HereNow, Time-Team (incl. USRowing's white-label), RegattaTiming, row2k, RegattaCentral — publishes full athlete names at all ages; confirmed down to U15 events with full names.
- MaxPreps (CBS) publishes minors' profiles (name, height/weight, grad year) by default and honors deletion requests. MileSplit publishes first/last/gender/grad-year publicly. Athletic.net likewise builds public HS athlete pages.
- GameChanger draws its line at under-13 (the COPPA age): no U13 accounts, last names of U13 team members removed.
- USRowing's waiver grants a license to use athletes' names/likenesses; sanctioned-regatta results are the public sporting record, and USRowing's own timing contractors publish them.
- COPPA is inapplicable to CrewGraphs' results ingestion: COPPA governs online collection of personal information *from* children by operators; we collect nothing from any athlete and offer no accounts. Publishing factual results of public competitions is the long-standing practice of news and sports-statistics publishers.

## Policy

1. **Race-result context only.** Athlete names appear solely inside a race result (role + name, e.g. stroke/cox), mirroring the official published record. Names never appear as standalone content.
2. **No person pages.** No person profile pages, person URLs, or cross-regatta person aggregation for anyone in v1. (A future masters person-level feature would revisit this for adults only, under its own spec.)
3. **No person search.** Person names are excluded from site search and from `read.org_directory.search_text`. Enforced by a fatal publish invariant + test.
4. **Removal on request, any age, no questions.** A curator-managed suppression list (`core.person_suppression`) is honored at every publish; the next snapshot redacts the name from all published surfaces. Raw R2 archives (private, non-published) retain the official record. Takedown contact and expected turnaround are documented on the methods page.
5. **Proactive U13 redaction.** Entries in events designated U13 or younger publish without athlete names (GameChanger precedent at the COPPA line). Effectively free — rowing has almost no U13 racing — and it puts our line at the strictest peer practice.
6. **Data minimization.** No dates of birth, no photos, no contact details, no school-grade data. Masters ages appear only as published in handicap context (adults). Person data lives in exactly one core table (`core.result_person`), which has no web-role grant and can be purged or partially redacted without touching results. Provider payloads can carry registration metadata beyond the official record (verified: HereNow entries expose a `RegEmail` registrant-email field) — adapters strip email/contact fields from everything persisted to Postgres, staging included; only the private R2 archive retains original bytes.

## Enforcement points (technical)

| Policy § | Mechanism |
| --- | --- |
| 1, 2 | Names exist in read models only inside `read.org_regatta_result.crew jsonb`; no person-keyed table, route, or page exists |
| 3 | Publish fatal invariant: no `result_person` name appears in `org_directory.search_text` or directory payloads; unit test pins the publish SQL surface |
| 4, 5 | Publish assembles crew via `result_person LEFT JOIN person_suppression` + U13 event rule; fatal invariant: zero suppressed names in any assembled payload |
| 6 | Schema: `core.result_person` is the only **core** person store; `REVOKE ALL FROM web_ro`; FK direction (person → entry) makes the table purgeable |
| 6 (staging) | `staging.*` provider payloads are raw-archive tier: they necessarily retain published person names (they are the load input for `result_person`) but carry no web grants and have contact/registration fields stripped at write time; the takedown SOP includes deleting the affected staging rows alongside the `result_person` redaction |

## Posture notes

- We publish *less* person data than every peer site (no profiles, no search, proactive U13 redaction) while matching the norm of showing the official result as it was published.
- The methods page carries: sources and attribution, this policy in plain language, and the takedown contact.
- If a provider or event organizer asks us to stop publishing names from their events, treat it as a scoped suppression (source/club scope on `person_suppression`) — the schema already supports it.

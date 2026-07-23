# Results ecosystem survey: timing providers (2026-07-23)

**Question:** RegattaCentral frequently links out to third-party timing systems rather
than hosting results. Is the timing-provider layer a viable, less permission-gated
path to results data? Candidates: row2k results directory, Time-Team, HereNow
(+ two more discovered during the survey: CrewTimer, Regatta Timing).

**Method:** link-graph analysis of row2k's 2026 results directory (79 "Live Results"
links → hosts), then direct probing of each provider: page structure, network/API
inspection in-browser, robots.txt, terms-of-use search, coverage sampling.

## Headline

The prior "all results sources are permission-gated" conclusion applies to the
**aggregator layer** (RegattaCentral, row2k, Concept2). The **timing-provider layer
is open**: Time-Team and HereNow both serve complete, structured, unauthenticated
JSON with no stated usage restrictions, no robots.txt disallows, and no login. Both
are viable ingestion paths today. HereNow is the cheapest start; USRowing's
white-label Time-Team instance is the championship backbone.

## Market share (row2k 2026 "Live Results" links, n=79)

| Host | Links | Layer |
|---|---:|---|
| legacy.herenow.com | 17 | Northeast club/masters/juniors + misc national |
| crewtimer.com (both hosts) | 18 | mid-tier club/scholastic, West+Midwest heavy |
| usrowing.regatta.time-team.com | 12 | USRowing national + regional championships |
| results.regattatiming.com | 11 | collegiate/scholastic majors (IRA, Dad Vail, SRAA) |
| rowtown.org, clockcaster, qra.org, worldrowing, misc | ~21 | long tail |

RegattaCentral itself: **1 of 79**. The user's hypothesis is confirmed — RC is an
entries/registration layer; results live with the timers.

## 1. Time-Team (`regatta.time-team.nl`, `usrowing.regatta.time-team.com`) — STRONG GO

Dutch timing outfit ("TIME TEAM Regatta Systems", © 2002–2026, info@time-team.nl).
USRowing is a first-class client with a dedicated white-label domain.

**USRowing coverage (year selector: 2020–2026):** Youth National Championships,
all regional youth championships (Mid-Atlantic, Northeast, Northwest, Southeast,
Southwest, Central), Masters regionals, RowFest National Championships, Indoor
Nationals, Youth Beach Sprints, International Rowing Challenge, NYS HS Championships.
This is exactly the juniors/masters championship layer the ratings north star needs.

**Two generations of platform:**
- Legacy server-rendered PHP: `regatta.time-team.nl/{slug}/{year}/results/events.php`,
  per-event UUID pages, `[matrix] [per event] [per race] [per club]` views. Older
  US events (e.g. `usrowing-midatlantic-youth/2024`) live here.
- New Next.js app with clean versioned JSON API:
  - `https://api.usrowing.regatta.time-team.com/api/1/{slug}/{year}/race` — full
    schedule, 229 races for Youth Nats 2026, incl. progression rules
    (`rules[].target_round_id` graph), timing layouts w/ split locations.
  - `.../race/{uuid}` — the results document: `race_crew` + `round_crew` with bib,
    lane, status vocabulary (DNS/DNF/DSQ/withdrawn/relegated/OOC...),
    `adjusted_pos`, `adjusted_result`, `+delta`, `penalty`, `correction`, and
    per-location `times[]` (splits).
  - `.../event`, `.../search` also exist (`/club`, `/crew`, `/result` 404).
- Live updates via socket.io (`pallas.push.regatta-systems.com`).

**Identity gold:** entries carry `club` objects with **stable platform-wide UUIDs**,
club code, shortname, federation, and near-legal names ("Miami Rowing and
Watersports Center, Inc.") — direct join candidates for the IRS/BMF EIN cohort.
Person names present (stroke names in entries; UI supports full rosters incl.
cox/coach, person pages, cross-regatta club/person search).

**Usage posture:** no robots.txt on either regatta domain; no ToU found on regatta
sites (footer i18n has `terms-and-conditions` keys but no page located). Contact
info@time-team.nl for a courtesy note.

**Effort:** low–medium. Enumerate slugs per year from the white-label homepage,
walk `race` → `race/{uuid}`. Raw JSON → R2 fits existing acquire rails.

## 2. HereNow (`legacy.herenow.com`, Cambridge MA) — STRONG GO, cheapest start

Angular 1.x SPA over a **wide-open Breeze/OData API** — server-side curl works, no
auth, no CORS games:

- Base: `https://newwebrole2023.azurewebsites.net/breeze/BreezeApi/`
- `Metadata` — full entity model (Races, Events, Flights, Entries, EntryResults,
  Competitors, PersonInfoes, Rosters, Penalties, Progressions, Venues, Records...)
- `Races?$filter=...&$select=...&$orderby=...&$top=...&$inlinecount=allpages` —
  the whole catalog is enumerable (verified: 1,407 rows incl. 2 test rows)
- `GetBaseRaceData?raceId={id}` — full race entity (incl. `LastYearRaceId`
  chaining editions year-over-year)
- `GetScopedRaceFlights?raceId={id}&scopeStartTime=...&scopeEndTime=...` — results
- SignalR `racinghub` for live.

**Coverage (measured from the catalog):** 1,405 real races, 2007→2026; ~100–155/yr
since 2019; 910 tagged Rowing (most untagged rows are also rowing; tags are messy:
"Rowinf", "owing"). Heavy Northeast club scene: Charles River series, Cromwell Cup,
Head of the Charles 2012-era, masters + juniors events nationwide (17 of row2k's
79 current live links).

**Masters ratings bonus:** result rows carry raw time, **age handicap, and adjusted
time** (verified on Cromwell Cup masters events) — direct input for the masters
rank-ordered-field model. Full athlete names are present.

**Usage posture:** robots.txt = allow all; no ToU found anywhere on herenow.com
(main site is a near-empty SPA shell). Instagram: @herenowsports, Cambridge MA.

**Effort:** low. Snapshot the `Races` catalog, then ~1.4k `GetBaseRaceData` +
flight calls, politely rate-limited, raw → R2.

## 3. row2k results directory — INDEX ONLY

- Explicit policy on the results page: schools/clubs may copy their own results;
  everyone else: "*LINK TO* these results ... link to, and not copy" + credit
  row2k as source. robots.txt carries Cloudflare content signals
  (`search=yes, ai-train=no, use=reference`).
- Archives back to **1997**; entries categorized (JUNIOR / MASTERS / COLLEGIATE /
  HIGH SCHOOL / etc.), dated, with location strings.
- 403s generic fetchers (Cloudflare); fine in a real browser.

**Verdict:** don't ingest row2k-hosted result content. Use it as a **discovery
index**: regatta name → date → category → external timing-provider URL. That
mapping (facts + outbound links) powers provider-side enumeration and gap
detection, and linking back with credit is exactly what row2k asks for. Keep
row2k in the Track-D outreach list for anything deeper (their hosted PDFs/pages
reach back decades).

## 4. Regatta Timing (`results.regattatiming.com`) — GO, collegiate layer

- Server-rendered JSP; small **sequential raceIds** (369 = 2014 Dad Vail …
  644 = 2026 IRA) → trivially enumerable.
- `summary.jsp?raceId=N` (all events, heats→finals, place/lane/club/stroke/time/
  margin), `result.jsp?eventId=&raceId=`, heatsheet PDFs, `staticRaceResults.jsp`
  for older years.
- Hosts the collegiate/scholastic majors: IRA National Championship, Dad Vail,
  SRAA, plus Waco etc.
- Cloudflare content-signal robots like row2k's; 403s non-browser UAs.
- Not the ratings north star (collegiate), but cheap completeness + club identity.

## 5. CrewTimer (`crewtimer.com/regatta/r{id}`) — PARK (medium effort)

Largest single share of current live links (18/79), mid-tier club/scholastic
regattas. React SPA on **Firebase** (`crewtimer-results.appspot.com`); data loads
via Firebase channels, not inspectable REST in the page. No robots.txt. Extraction
requires reverse-engineering Firebase REST paths or headless rendering — doable,
but do Time-Team/HereNow first. Sequential `r#####` regatta ids.

## Cross-cutting notes

- **PII/juniors caution:** both open APIs expose full athlete names, including
  minors. Club-level ratings need no person names; if/when person-level data is
  stored, decide a PII policy first (store hashed/internal, don't republish names
  of minors without a policy).
- **Posture:** absence of ToU ≠ affirmative permission. Recommended stance:
  polite rate limits, honest UA, raw snapshots to R2 with SourceRef provenance
  (consistent with the IRS pipeline), attribution on the site, and a courtesy
  email to info@time-team.nl and HereNow once ingestion is real — from the
  live-site position, per Track D. Timing providers publish on behalf of event
  organizers (USRowing etc.), which is a materially better position than
  scraping an aggregator against stated terms.
- **Identity join:** Time-Team club UUID + legal-ish name → EIN candidates;
  HereNow club strings are short ("Riverside", "Community") → route through the
  existing alias-resolution machinery.
- **Suggested sequencing:**
  1. HereNow catalog snapshot + raw archive (days of work, immediate corpus).
  2. USRowing Time-Team archive 2020–2026 (championship backbone for ratings).
  3. row2k index scrape → regatta↔provider registry + gap detection.
  4. Regatta Timing (collegiate), then CrewTimer (Firebase RE) as expansion.

## Verified endpoints (quick reference)

```
# HereNow catalog (server-side curl works)
https://newwebrole2023.azurewebsites.net/breeze/BreezeApi/Races?$orderby=Id&$select=Id,Name,StartDate,Sport,IsListed,IsPublished
https://newwebrole2023.azurewebsites.net/breeze/BreezeApi/GetBaseRaceData?raceId=21464
https://newwebrole2023.azurewebsites.net/breeze/BreezeApi/GetScopedRaceFlights?raceId=21464&scopeStartTime=...&scopeEndTime=...
https://newwebrole2023.azurewebsites.net/breeze/BreezeApi/Metadata

# Time-Team / USRowing white-label
https://usrowing.regatta.time-team.com/            # year selector 2020-2026
https://api.usrowing.regatta.time-team.com/api/1/usrowing-youth-national/2026/race
https://api.usrowing.regatta.time-team.com/api/1/usrowing-youth-national/2026/race/{race-uuid}
https://regatta.time-team.nl/{slug}/{year}/results/events.php   # legacy gen

# Regatta Timing
https://results.regattatiming.com/backoffice/webpages/results/summary.jsp?raceId=625   # 2025 IRA

# CrewTimer
https://www.crewtimer.com/regatta/r16088   # Firebase-backed SPA
```

Raw HereNow catalog snapshot from this survey: scratchpad `herenow_races.json`
(1,407 rows; re-pull is one curl).

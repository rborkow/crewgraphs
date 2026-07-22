# CrewGraphs Phase-Zero IRS Data Spike — Findings

*Run 2026-07-21. Cohort: 10 US rowing-club nonprofits (plus 1 documented
substitute + 1 related entity). All data keyless/anonymous. Detail lives in
`output/`; this file answers the 10 spike questions and gives a go/no-go.*

## Cohort as resolved

| # | Racing identity | Legal filer | EIN | Sub | XML? | Confidence |
|---|---|---|---|---|---|---|
| 1 | Vesper Boat Club | Vesper Boat Club Inc (Philadelphia PA) | 23-7397498 | c3 | yes | high |
| 2 | Undine Barge Club | The Undine Barge Club Of Philadelphia | 23-2744491 | c3 | yes | high |
| 3 | Potomac Boat Club | Potomac Boat Club (Washington DC) | 53-0127820 | **c7** | yes | high |
| 4 | Community Rowing, Inc. | Community Rowing Inc (Brighton MA) | 04-2863756 | c3 | yes | high |
| 5 | Row New York | Row New York Inc | 11-3632924 | c3 | yes | high |
| 6 | Saugatuck Rowing | *Olympic Athletes Rowing At Saugatuck* (OARS) | 33-1055179 | c3 | **no** (dormant) | low |
| 6-sub | *(substitute)* | Marin Rowing Association (Greenbrae CA) | 23-7448092 | c3 | yes | high |
| 7 | Lincoln Park Boat Club | Lincoln Park Boat Club (Chicago IL) | 36-3508216 | **c4** | 2015 only | medium |
| 7-arm | *(financial filer)* | Lincoln Park Boat Club Charitable Outreach | 27-2334832 | c3 | yes | medium |
| 8 | Austin Rowing Club | Austin Rowing Club | 74-2219650 | c3 | yes | high |
| 9 | Concord Crew (booster) | Friends Of Concord Crew (NH) | 03-0388282 | c3 | yes (EZ->990) | high |
| 10 | Washington Rowing / Husky Crew | Husky Rowing Foundation (Seattle WA) | 81-1495108 | c3 | **no** (990-N) | medium |

28 XML filings fetched across 10 EINs; **14 distinct return_versions** (2015v2.0 -> 2025v4.0).

---

## 1. Coverage reality

**7 of 10** racing identities map, on the *originally-named legal entity*, to an
XML filer with returns for >=3 of the last 5 tax years (2019-2023): Vesper, Undine,
Potomac, CRI, Row NY, Austin, Concord — each has an unbroken structured history
2011->2023 in ProPublica, and we pulled 3 spread years of XML for each.

The other 3 are the interesting ones:
- **Saugatuck (OARS, #6):** the nonprofit filed 990/990-EZ only in **2003-2008
  (PDF images, no XML)** and has been dark since. The live racing brand
  "Saugatuck Rowing Club" is a **for-profit**. Per the brief we substituted
  **Marin Rowing** for extraction and documented the entanglement.
- **Lincoln Park (#7):** the recognizable **c4** club dropped to 990-N after
  2015; its financials live in a **separate c3 arm** (27-2334832) which *does*
  have XML 2012->2023. Counting the sibling entity, Lincoln "has" coverage.
- **Husky Rowing Foundation (#10):** **990-N only — no structured data, no XML,
  ever.** Under $50k gross receipts; files postcards. Racing identity present,
  financials absent.

So: **8/10 recover XML through the best available filer** (accepting one
substitute and one sibling entity); **2/10 have no XML on the primary entity**
(OARS dormant/PDF-only; Husky 990-N). This is the headline: for a real cohort,
plan for ~20% of "known clubs" to be **990-N or dormant** and therefore invisible
in the financial corpus.

**2021-2022 corpus hole:** I fetched and grepped the IRS `index_2021.csv`
(71.3 MB) and `index_2022.csv` (68.9 MB) — the processing years the ~400k
removal hit. **Every active cohort org's tax-2020 and tax-2021 return is present
in those indices.** The removal did not touch this cohort. The real freshness gap
is elsewhere (Q10: the GT lake, not the IRS indices).

## 2. Concept-map validity

24 concepts x 28 filings. **Zero xpath failures.** Every concept applicable to a
form type either resolved or was *legitimately blank* (IRS e-file omits $0/optional
lines — an "absent", not a failure). The distinction is enforced in `extract.py`:
`resolved` / `absent` (valid xpath, $0 line) / `not_on_form` (990-only line on an EZ).

Resolve-rate **of applicable concepts** per return_version:

| version | filings | resolved | absent($0) | not_on_form | rate |
|---|---|---|---|---|---|
| 2015v2.0 | 1 | 8 | 12 | 4 | 40% <- dormant $0 EZ, not a map failure |
| 2018v3.1 | 1 | 22 | 2 | 0 | 92% |
| 2019v5.0/5.2 | 3 | 22/44 | 2/4 | 0 | 92% |
| 2020v4.0/4.1/4.2 | 9 | — | — | 0-4 | 87-92% |
| 2021v4.0/4.1/4.2 | 7 | — | — | 0-4 | 83-87% |
| 2023v6.0 | 1 | 21 | 3 | 0 | 88% |
| 2024v5.0/5.2 | 5 | — | — | 0 | 79-82% |
| 2025v4.0 | 1 | 22 | 2 | 0 | 92% |

The map is **stable across all 14 versions** because the modern (2013+) 990 schema
kept element names constant (`CYTotalRevenueAmt`, `TotalFunctionalExpensesGrp/...`,
`TotalAssetsGrp/EOYAmt`, etc.). No per-version xpath forks were needed. The only
structural fork is **990 vs 990-EZ**, which is a clean two-map switch.

Concepts that are structurally sparse (not map bugs):
- `professional_fundraising_fees`: **0/24** resolved on 990 — none of these clubs
  hire pro fundraisers (legit $0); `not_on_form` on EZ.
- `membership_dues`: resolves only for member clubs (Undine, Potomac-c7, CRI,
  Lincoln-c3) — 7/28; blank elsewhere because those orgs report member income as
  program-service revenue instead. **Concept works; the line is genuinely optional.**
- `fundraising_events_gross/net`: 16/14 of 28 — only orgs running events populate it.

## 3. Cross-check exactness (the decisive result)

`output/crosscheck.csv`: 168 anchor comparisons (28 filings x 6). Of the **118
comparisons where both XML and ProPublica carry a value, all 118 match to the
dollar — zero disagreements.** The apparent "8 mismatches" and "42 no-row" are
**not** extraction errors:

- **8 "mismatches" = ProPublica NULLs, not conflicts.** For every **990-EZ**
  filing, ProPublica populates `totrevenue/totfuncexpns/totassetsend/totliabend`
  but leaves **`totcntrbgfts` and `totprgmrevnue` = `null`** — even though the XML
  clearly reports them (e.g. Concord FY2021: contributions $46,115, program
  $51,960). **Our extractor fills a gap ProPublica leaves open for EZ filers.**
- **42 "no ProPublica row" = ingestion lag.** The newest filings we pulled via
  `latest_object_id` (tax 2024/2025) aren't in ProPublica's `filings_with_data`
  yet. Concrete: **Concord's TaxYr-2024 return (FY ending 2025-06-30, and it
  graduated EZ->full-990) is fully parseable from XML, while ProPublica's
  structured data still stops at TaxYr 2022** — a ~2-year lag.

Bottom line: on the six anchors, **XML-vs-ProPublica agreement is exact wherever
comparable**; the only divergences are places where **XML is more complete or more
current than ProPublica**. This is the strongest possible signal for the concept-map
approach.

## 4. EZ / 990 mix

4 of 28 filings (**14%**) are 990-EZ (Concord x2, Lincoln-c3 x1, Lincoln-c4 x1);
Concord's third is a full 990 (it crossed the $200k EZ ceiling in FY2024). The
**990-only concepts** correctly flag `not_on_form` on EZ, not `absent`:
`professional_fundraising_fees`, `management_general_expense`, `fundraising_expense`,
`employee_count` (no functional-expense split and no Part V employee count on the EZ).
`program_service_expense` **exists** on the EZ but equals total expenses (the EZ
doesn't break expenses out by function). The availability matrix holds up: **20 of
24 concepts are EZ-applicable, 4 are 990-only**, and the extractor encodes exactly
that. Any cross-org comparison must therefore treat the 4 990-only columns as
structurally missing for EZ filers — not as data quality gaps.

## 5. Amendments

**None encountered** in the 28 fetched XMLs (`AmendedReturnInd` absent on all).
The precedence rule is therefore **untested against real amended XML.** But
amendments *do* exist in these orgs' histories: ProPublica's
`filings_without_data` carries an **"R" suffix** on `formtype_str` for several
(Undine `990R`, Row NY `990R`/`990ER`, Potomac `990OR`) — that suffix flags
amended/restated returns in older (PDF) filings. **Recommended precedence for the
build (to be validated later):** key filings by `(EIN, tax_period_end)`; when >1
return exists, prefer `AmendedReturnInd=true`, tie-break by latest `SUB_DATE` /
highest `OBJECT_ID`. Treat the "R" suffix as a discovery hint that an amendment
chain exists for that EIN/period.

## 6. Structural identity (booster #9 and foundation #10)

Both resolve cleanly as **one Org (EIN) + one typed relationship to a racing
identity** — "racing identity != legal filer" is representable and, in this cohort,
*common*:

- **Booster (#9):** racing identity **"Concord Crew"** (a public high-school team,
  not itself an entity) — `supported_by` -> **Org "Friends of Concord Crew"
  (03-0388282)**. Single c3, deep EZ history. Trivial one-to-one.
- **Foundation (#10):** racing identity **"Washington Rowing" / "Husky Crew"** (the
  University of Washington varsity program) — `funded_by` -> **Org "Husky Rowing
  Foundation" (81-1495108)**. Note **no entity named "Washington Rowing Foundation"
  exists** (search = 0 hits); the real filer's name shares no tokens with the racing
  brand. The university's own 990 covers *all* athletics and can't isolate rowing.
  The foundation is 990-N, so the relationship models cleanly even though financials
  are absent.
- **Bonus cases proving the pattern is pervasive:** **Saugatuck** (racing brand ->
  `affiliated_forprofit` for-profit club + dormant nonprofit OARS) and **Lincoln
  Park** (recognizable c4 club -> `has_charitable_arm` -> the c3 that actually files
  financials, itself indexed under a *third* name "Lincoln Park Boating Community").

**Conclusion:** model as `(RacingIdentity)-[rel]->(Org{ein})` with rel in
{`is_filer`, `supported_by`, `program_of`, `has_charitable_arm`,
`affiliated_forprofit`}. A racing identity maps to **0, 1, or 2+ orgs**. Joins must
be on **EIN only** — names disagree across ProPublica vs IRS index vs racing brand.

## 7. Fiscal-year spread

FYE months in the cohort: **December (7 orgs**: Vesper, Undine, Potomac, Marin,
Lincoln-c3, Lincoln-c4, Austin), **June (2**: Row New York, Concord), **October
(1**: Community Rowing). Consequence for "latest common fiscal year": **IRS
`TaxYr` != fiscal-year-end year for June/Oct filers.** Concord's `TaxYr 2024` spans
2024-07-01 -> 2025-06-30; Vesper's `TaxYr 2023` is calendar 2023. Naively comparing
"everyone's 2024" mixes reporting periods offset by up to 11 months. **Align on IRS
`TaxYr` (from the header, not the object-id year), surface `fye_month`, and define
"latest common year" as the most recent `TaxYr` for which *all* compared orgs have
filed** (today that is ~TaxYr 2022-2023, because CRI/June-FYE orgs and ProPublica
lag pull the common frontier back).

## 8. Compensation data quality

Officer/key-employee rows (990 Part VII-A / EZ Part IV): **337 rows across 28
filings, 0 blank names, titles present, `avg_hours` present.** Names/titles are
**clean enough to publish as-is.** But **304/337 (90%) rows are $0 compensation** —
volunteer directors, correct and expected for rowing clubs. **Needs a suppression
rule, not raw publication:** show only `comp > 0` individuals (~33 rows cohort-wide),
and render the rest as an aggregate ("N volunteer board members, $0 comp"). This
both avoids a wall of $0s and minimizes PII exposure (publishing named unpaid
volunteers adds no transparency value). No garbage rows, no malformed names —
suppression is a display policy, not a data-cleaning problem.

## 9. Ops envelope

- **Bytes downloaded:** retained ~= **193 MB** = concordance 3.2 MB + `index_2020`
  48.3 MB + `index_2021` 71.3 MB + `index_2022` 68.9 MB + 28 XMLs 1.1 MB + 12
  ProPublica JSONs (~0.4 MB). Gross wire ~= **267 MB** incl. one throwaway index
  probe. **Cap 500 MB — comfortably under.**
- **Wall clock (approx, polite sleeps included):** ProPublica resolve+fetch ~2 min;
  3 IRS index downloads + grep ~2-3 min (whole-file, ~50-90 MB each); 28 XML fetches
  ~30 s; extract + crosscheck < 10 s. **End-to-end ~= 6-8 min.**
- **150-org backfill projection:** IRS index CSVs are a **fixed, cohort-independent
  cost** — covering ~7 processing years (2018-2024) is ~**455 MB one-time**,
  serving any number of EINs. XML at ~3-5 filings x 150 orgs x ~50 KB ~= **25-40 MB**.
  ProPublica: 150 small JSONs. **Total ~= 500 MB, dominated by index CSVs**, ~15-25
  min wall clock. **Optimization:** replace per-year CSV re-downloads with a
  persistent `EIN -> [object_id]` lookup built once from the GT lake all-years index
  (parquet, ~1 GB, single pull) or from a one-time index ingest into SQLite; then
  per-org cost is just the tiny XMLs. A full every-year backfill (not just 3 years)
  raises XML count but not size materially (XMLs are 8-65 KB each).

## 10. Plumbing gaps the build plan must account for

1. **GT lake lags the IRS by months — freshest filings 404.** Row NY's and Marin's
   newest returns (object-ids `2026...`) are **absent from the lake**; 2025-processed
   objects are present. There is **no live fallback**: the classic
   `s3://irs-form-990` bucket is **dead (404)**. For "latest filing" freshness,
   either accept the lag, poll the lake for backfill, or add the IRS bulk ZIPs as a
   secondary source. **This is the single biggest gap.**
2. **ProPublica is not a substitute for XML.** `filings_with_data` lags
   `latest_object_id` by **1-2 tax years**, and **NULLs `totcntrbgfts`/
   `totprgmrevnue` for all EZ filers.** Use it for discovery/EIN resolution and as a
   cross-check oracle, **not** as the financial source of record.
3. **Index disagreement / fragmentation.** An org's tax-year return appears in the
   **processing-year** index (when the IRS *processed* it), which — with fiscal-year
   and extension timing — scatters one org across multiple yearly indices (e.g.
   Vesper's tax-2019 return is **not** in `index_2020`; it landed in `index_2021`).
   **990-T** returns also sit in the same index next to the 990 and must be filtered
   (Row NY, Marin, Austin each filed separate 990-Ts). Join on **EIN + return_type +
   tax_period**, never assume "one filing per index-year."
4. **IRS index server ignores HTTP Range** — no partial fetch; each year is a full
   50-90 MB download. Budget accordingly or move to the GT lake index.
5. **Name variance across sources for the same EIN.** 27-2334832 is "Lincoln Park
   Boat Club Charitable Outreach" in ProPublica but "**Lincoln Park Boating
   Community**" in the IRS index. **Name-based joins are unsafe — key on EIN.**
6. **Concordance CSV is Windows-1252, not UTF-8** — naive `utf-8` read throws on a
   smart-quote byte. Read with `errors="replace"` or `encoding="latin-1"`.
7. **Racing-identity != filer is the norm, not the exception** (4 of 10 here:
   Saugatuck, Husky/Washington, Lincoln, plus every "Friends of X" booster). The
   identity/relationship layer (Q6) is **not optional** — it's core plumbing.
8. **ProPublica search is strict-AND / no fuzzy.** "friends of princeton rowing" and
   "washington rowing foundation" both return 0; discovery needs token-minimal
   queries ("rowing foundation", "husky rowing") plus manual disambiguation.

---

## Go / No-Go

**GO on the concept-map approach.** The 24-concept map, built as an ordered
candidate-xpath set with a clean 990/990-EZ fork, resolved **every applicable
concept with zero xpath failures across 14 return_versions (2015->2025)**, and its
six anchors agree **to the dollar with ProPublica on 100% of comparable values** —
diverging only where the XML is *more* complete (EZ breakdowns) or *more* current
(ProPublica's 1-2-year lag) than ProPublica. Extraction is cheap (~1 MB of XML for
the whole cohort) and the map needs no per-version maintenance.

**Plan revisions to fold in before scaling:**
1. **XML source of record = GT lake, keyed by object_id**, with an explicit
   staleness policy and a backfill poller for the ~months-long lag; **do not** rely
   on the dead classic IRS bucket, and **do not** treat ProPublica as the financial
   source (discovery + cross-check oracle only).
2. **Build a persistent `EIN -> object_id[]` index once** (from the GT all-years
   index or a one-time SQLite ingest of yearly CSVs) instead of re-downloading
   50-90 MB CSVs per run; filter out 990-T and non-990 return types at ingest.
3. **First-class identity/relationship layer** — `(RacingIdentity)-[rel]->(Org{ein})`
   with 0/1/many orgs per identity; join strictly on EIN; expect ~20% of "known
   clubs" to be **990-N/dormant -> financials genuinely absent** (surface this as a
   state, not an error).
4. **Alignment + display rules:** compare on IRS `TaxYr` with `fye_month` surfaced;
   define "latest common year" as the newest TaxYr all compared orgs have filed;
   **suppress $0-comp volunteer officer rows** (publish only compensated
   individuals + an aggregate count).
5. **Amendment precedence remains to be validated** against a real amended return —
   wire the `(EIN, tax_period)` + `AmendedReturnInd` + latest-`SUB_DATE` rule now,
   and add an amended filing to the next test batch (the "R"-suffix orgs are a
   ready source).

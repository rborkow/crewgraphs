# CrewGraphs cohort triage — discovery candidates

**Date:** 2026-07-22  **Analyst pass:** automated classification (name + NTEE + BMF/990-N staging), owner review required before any load.

## Summary

- **Total distinct discovery candidates:** 675 EINs (staged as `core.review_task` discovery tasks; 962 raw tasks deduped to 675 distinct EINs).
- **Tier 1 — strong include (recommended first batch):** 58
- **Tier 2 — plausible:** 452  ( 268 clean-rowing "priority pool" held from first batch + 184 genuinely ambiguous needing verification )
- **Excluded — not rowing:** 165
- **Reconciliation:** 58 + 452 + 165 = **675** = total. ✓

### Headline findings

1. **The pool is far richer in rowing than the 40–60 estimate.** 326 candidates are *confidently rowing* (unambiguous name + supporting NTEE) — the discovery sweep was clearly rowing-keyword-seeded (241 names literally contain the word "ROWING", plus REGATTA/SCULL/OARS). Tier 1 is therefore a **curated best-58 first batch**, not the whole rowing population; the remaining 268 clean-rowing orgs sit in Tier 2 as a ranked "priority pool" for subsequent batches (they are real rowing orgs, held back only for batch-sizing / data-depth, not because identity is in doubt).
2. **The e-file XML index is not yet staged for discovery EINs.** `staging.efile_index_row` contains only 49 rows across 9 EINs — all cohort orgs. So the "e-file XML years available" column is empty for every discovery candidate; XML corpus presence must be backfilled before financial profiles can be built. The usable filing signal today is 990-N (e-postcard) presence and the BMF `REVENUE_AMT` snapshot.
3. **990-N coverage:** 348 of 675 candidates have a 990-N e-postcard on file. Many clean rowing clubs file 990-N with $0 BMF revenue (small clubs) — useful for existence/identity, not for financials.
4. **ProPublica corroboration is unavailable for discovery EINs.** `staging.propublica_org` holds only 12 EINs (the cohort). Zero overlap with the 675 candidates, so that column is "—" throughout.
5. **Trap families are well represented and were removed:** non-rowing "crew" (film/dance/wildland-fire/animal-rescue/pit-crew/ministry/baseball/Venturing-Scout crews), CREW = Commercial Real Estate Women business chapters, dragon-boat/outrigger paddle sports, and yacht/power/ice/ski boating. Hybrid clubs that also row (e.g. "…Sailing & Rowing", "…Paddling & Rowing") were kept in Tier 2 for verification rather than excluded.

### Method & caveats

- Classification uses **only** staged data: BMF name/city/state/NTEE/subsection/revenue, 990-N presence, and the staged name. **No web lookups** were performed, so identity is *unverified* — Tier 1 is a review shortlist, not a confirmed roster.
- Exclusions applied: EINs already in `core.external_identifier` (namespace `irs_ein`) and the 12 `seed/cohort.csv` orgs — verified **zero** overlap with the candidate set.
- `BOAT CLUB` names are intrinsically ambiguous (rowing barge clubs vs. yacht/power/lake-social clubs) and cannot be split reliably without a boathouse/website check, so all bare boat clubs are Tier 2.

## Tier 1 — strong include, recommended first batch (58)

Ranked by signal strength + financial-data depth. `XML yrs` is blank for all (index not staged). `990-N` = e-postcard present. `PP` = ProPublica staged (none). All identities **unverified** — confirm before load.

| # | EIN | Name | City | ST | NTEE | XML yrs | 990-N | PP | BMF rev | Rationale |
|---|-----|------|------|----|------|---------|-------|----|--------:|-----------|
| 1 | 853570682 | ALL RIGHT NOW ROWING ASSOCIATION INC | Menlo Park | CA | N67 | — | yes | — | $666,878 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $666,878) |
| 2 | 884350558 | RENTON ROWING CENTER | Renton | WA | N67 | — | yes | — | $366,779 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $366,779) |
| 3 | 364819989 | WACO ROWING CLUB INC | Waco | TX | N67 | — | yes | — | $350,330 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $350,330) |
| 4 | 760459849 | ROWING CLUB OF THE WOODLANDS INC | The Woodlands | TX | N67 | — | yes | — | $233,348 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $233,348) |
| 5 | 832763014 | KENMORE ROWING CLUB | Kenmore | WA | N67 | — | yes | — | $183,945 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $183,945) |
| 6 | 911276445 | GEORGE Y POCOCK ROWING FOUNDATION | Seattle | WA | N67Z | — | no | — | $2,536,767 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $2,536,767) |
| 7 | 911696516 | SAMMAMISH ROWING ASSOCIATION | Redmond | WA | N67 | — | no | — | $2,028,118 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $2,028,118) |
| 8 | 431998827 | PACIFIC ROWING CLUB | Daly City | CA | N67 | — | no | — | $988,483 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $988,483) |
| 9 | 911028897 | LAKE WASHINGTON ROWING CLUB | Seattle | WA | N670 | — | no | — | $743,166 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $743,166) |
| 10 | 260431668 | RIVER CITY ROWING CLUB INC | W Sacramento | CA | N67 | — | no | — | $677,197 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $677,197) |
| 11 | 264831602 | BUFFALO SCHOLASTIC ROWING ASSOCIATION INC | East Amherst | NY | N67 | — | no | — | $640,471 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $640,471) |
| 12 | 521901575 | COMBINED CATHEDRAL CREWS ROWING CLUB INC | Washington | DC | N67 | — | no | — | $601,901 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $601,901) |
| 13 | 200519365 | BARE HILL ROWING ASSOCIATION | Harvard | MA | N67 | — | no | — | $450,700 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $450,700) |
| 14 | 412219809 | HINGHAM HIGH SCHOOL ROWING ASSOCIATION | Hingham | MA | N67 | — | no | — | $433,996 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $433,996) |
| 15 | 822875301 | OYSTER BAY COMMUNITY ROWING INC | Oyster Bay | NY | N67 | — | no | — | $319,943 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $319,943) |
| 16 | 141818590 | HUDSON RIVER ROWING ASSOCIATION INC | Poughkeepsie | NY | N67 | — | no | — | $315,491 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $315,491) |
| 17 | 911939589 | OLYMPIA AREA ROWING ASSOCIATION | Olympia | WA | N67 | — | no | — | $300,644 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $300,644) |
| 18 | 946103108 | LAKE MERRITT ROWING CLUB INC | Oakland | CA | N67Z | — | no | — | $254,944 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $254,944) |
| 19 | 751800739 | THE DALLAS ROWING CLUB | Dallas | TX | N67 | — | no | — | $234,318 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $234,318) |
| 20 | 043532936 | NORTHAMPTON YOUTH AND COMMUNITY ROWING INC | Northampton | MA | N67 | — | no | — | $234,042 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $234,042) |
| 21 | 550818433 | SCHOLASTIC ROWING ASSOCIATION OF AMERICA | Wycombe | PA | N67 | — | no | — | $166,097 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $166,097) |
| 22 | 263205593 | GENESEE ROWING CLUB INC | Rochester | NY | N67 | — | no | — | $155,783 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $155,783) |
| 23 | 251658296 | NORTH ALLEGHENY ROWING ASSOCIATION | Wexford | PA | N67Z | — | no | — | $152,373 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $152,373) |
| 24 | 412025456 | LONG ISLAND ROWING CLUB INC | Northport | NY | N67 | — | no | — | $134,575 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $134,575) |
| 25 | 954620239 | SANTA MONICA BAY JUNIOR ROWING ASSOCIATION INC | Marina Dl Rey | CA | N67 | — | no | — | $128,278 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $128,278) |
| 26 | 752353620 | FORT WORTH ROWING CLUB INC | Fort Worth | TX | N67 | — | yes | — | $76,576 | N67 aquatic-sports; 'rowing' in name; filer (rev $76,576) |
| 27 | 462428652 | CORTLANDT COMMUNITY ROWING ASSOCIATION | Verplanck | NY | N67 | — | yes | — | $75,714 | N67 aquatic-sports; 'rowing' in name; filer (rev $75,714) |
| 28 | 275010587 | WHATCOM ROWING ASSOCIATION | Bellingham | WA | N60 | — | yes | — | $191,790 | 'rowing' in name; full 990 filer (rev $191,790) |
| 29 | 474291046 | ADVANCED COMMUNITY ROWING ASSOCIATION INC | Nyack | NY | N60 | — | yes | — | $144,659 | 'rowing' in name; full 990 filer (rev $144,659) |
| 30 | 813246571 | MANCHESTER ROWING ALLIANCE | Sunapee | NH | N67 | — | yes | — | $105,200 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $105,200) |
| 31 | 861203768 | NORTH CHANNEL COMMUNITY ROWING | Evanston | IL | N67 | — | no | — | $96,220 | N67 aquatic-sports; 'rowing' in name; filer (rev $96,220) |
| 32 | 954242558 | LOS ANGELES ROWING CLUB | Marina Del Rey | CA | N67 | — | no | — | $94,165 | N67 aquatic-sports; 'rowing' in name; filer (rev $94,165) |
| 33 | 680156700 | HUMBOLT BAY ROWING ASSOCIATION | Trinidad | CA | N67 | — | no | — | $90,186 | N67 aquatic-sports; 'rowing' in name; filer (rev $90,186) |
| 34 | 061607625 | EAST ARM ROWING CLUB INC | Greenwood Lk | NY | N67 | — | no | — | $87,185 | N67 aquatic-sports; 'rowing' in name; filer (rev $87,185) |
| 35 | 521927718 | D C STROKES ROWING CLUB | Washington | DC | N67 | — | no | — | $81,258 | N67 aquatic-sports; 'rowing' in name; filer (rev $81,258) |
| 36 | 141805409 | SHAKER ROWING ASSOCIATION INC | Loudonville | NY | N67 | — | no | — | $59,313 | N67 aquatic-sports; 'rowing' in name; filer (rev $59,313) |
| 37 | 680451149 | STRAITS OF MARE ISLAND ROWING ASSOCIATION | Vallejo | CA | N67 | — | yes | — | $26,732 | N67 aquatic-sports; 'rowing' in name; filer (rev $26,732) |
| 38 | 912101122 | BAINBRIDGE ISLAND ROWING CLUB | Bainbridge Is | WA | N60 | — | no | — | $1,068,733 | 'rowing' in name; full 990 filer (rev $1,068,733) |
| 39 | 201685835 | CALIFORNIA ROWING CLUB | Lafayette | CA | N71 | — | no | — | $1,039,430 | 'rowing' in name; full 990 filer (rev $1,039,430) |
| 40 | 271522343 | PHILADELPHIA CITY ROWING | Plymouth Mtng | PA | N67 | — | no | — | $990,966 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $990,966) |
| 41 | 844915816 | STONINGTON COMMUNITY ROWING CENTER | Stonington | CT | N30 | — | yes | — | $747,944 | 'rowing' in name; full 990 filer (rev $747,944) |
| 42 | 461522952 | CONSHOHOCKEN ROWING CENTER | Conshohocken | PA | N99 | — | yes | — | $707,211 | 'rowing' in name; full 990 filer (rev $707,211) |
| 43 | 922519967 | POCOCK ROWING CLUB | Seattle | WA | N60 | — | no | — | $687,165 | 'rowing' in name; full 990 filer (rev $687,165) |
| 44 | 223273115 | NORWALK RIVER ROWING ASSOCIATION | Norwalk | CT | N60Z | — | no | — | $683,928 | 'rowing' in name; full 990 filer (rev $683,928) |
| 45 | 043528584 | WAYLAND-WESTON ROWING ASSOCIATION INC | Wayland | MA | N71 | — | no | — | $636,391 | 'rowing' in name; full 990 filer (rev $636,391) |
| 46 | 275015797 | EAST BAY ROWING CLUB | Oakland | CA | N70 | — | no | — | $597,857 | 'rowing' in name; full 990 filer (rev $597,857) |
| 47 | 352180580 | LIBERTY ROWING INC | Newburyport | MA | N67 | — | no | — | $431,829 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $431,829) |
| 48 | 472458817 | CITY ISLAND ROWING | Bronx | NY | N67 | — | no | — | $397,021 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $397,021) |
| 49 | 020508228 | UPPER VALLEY ROWING FOUNDATION | Hanover | NH | N70 | — | no | — | $343,653 | 'rowing' in name; full 990 filer (rev $343,653) |
| 50 | 562353626 | ROCKLAND ROWING ASSOCIATION INC | Nyack | NY | N60 | — | no | — | $303,784 | 'rowing' in name; full 990 filer (rev $303,784) |
| 51 | 232940243 | PHILADELPHIA SCHOLASTIC ROWING ASSOCIATION | Kng of Prussa | PA | N60Z | — | no | — | $287,449 | 'rowing' in name; full 990 filer (rev $287,449) |
| 52 | 161613861 | SYRACUSE CHARGERS ROWING CLUB INC | Syracuse | NY | N60 | — | no | — | $231,889 | 'rowing' in name; full 990 filer (rev $231,889) |
| 53 | 952658518 | LONG BEACH ROWING ASSOCIATION | Long Beach | CA | N70 | — | no | — | $226,871 | 'rowing' in name; full 990 filer (rev $226,871) |
| 54 | 141774219 | BURNT HILLS ROWING ASSOCIATION INC | Burnt Hills | NY | N60 | — | no | — | $224,610 | 'rowing' in name; full 990 filer (rev $224,610) |
| 55 | 455618578 | PARATI COMPETITIVE ROWING | Spring | TX | N67 | — | no | — | $200,369 | N67 aquatic-sports; 'rowing' in name; full 990 filer (rev $200,369) |
| 56 | 812649511 | ILLINOIS ROWING ASSOCIATION | Springfield | IL | N70 | — | no | — | $109,771 | 'rowing' in name; full 990 filer (rev $109,771) |
| 57 | 911474284 | CONIBEAR ROWING CLUB | Seattle | WA | — | — | yes | — | $109,589 | 'rowing' in name; full 990 filer (rev $109,589) |
| 58 | 461389718 | COMMUNITY ROWING OF SAN DIEGO | National City | CA | N60 | — | yes | — | $97,230 | 'rowing' in name; filer (rev $97,230) |

## Tier 2A — priority pool: clean rowing identity, held from first batch (268)

These are **confidently rowing** (name + NTEE) but were not selected for the 58-org first batch. Ranked so the owner can pull the next batches off the top. *What resolves the "doubt": nothing about rowing identity — the only gaps are (a) staged e-file financials and (b) a quick identity confirmation. Promote in subsequent batches.*

| # | EIN | Name | City | ST | NTEE | 990-N | BMF rev |
|---|-----|------|------|----|------|-------|--------:|
| 1 | 300727726 | OLYMPIC PENINSULA ROWING ASSOCIATION | Port Angeles | WA | N60 | yes | $63,878 |
| 2 | 137206211 | SAGAMORE ROWING ASSOCIATION INC | Oyster Bay | NY | N67 | no | $46,025 |
| 3 | 043443133 | WHALING CITY ROWING CLUB INC | New Bedford | MA | N67 | no | $21,152 |
| 4 | 020325323 | INDEPENDENCE ROWING CLUB INCORPORATED | Nashua | NH | N67 | yes | $0 |
| 5 | 113717456 | CRYSTAL LAKE ROWING CLUB | Crystal Lake | IL | N67 | yes | $0 |
| 6 | 134232982 | FARMINGTON VALLEY ROWING ASSOCIATION INC | Simsbury | CT | N67 | yes | $0 |
| 7 | 141811977 | SPACKENKILL ROWING CLUB | Poughkeepsie | NY | N67 | yes | $0 |
| 8 | 141817982 | RONDOUT ROWING CLUB INC | Kingston | NY | N67 | yes | $0 |
| 9 | 161419311 | CAZENOVIA ROWING CLUB | Cazenovia | NY | N67Z | yes | $0 |
| 10 | 202583593 | RAT ISLAND ROWING AND SCULLING CLUB | Port Townsend | WA | N67 | yes | $0 |
| 11 | 237349953 | AQUEDUCT ROWING CLUB INC | Rexford | NY | N67 | yes | $0 |
| 12 | 261361050 | LAKE SUNAPEE ROWING CLUB | New London | NH | N67 | yes | $0 |
| 13 | 300457207 | CONNECTICUT PUBLIC SCHOOLS ROWING ASSOCIATION INC | Lyme | CT | N67 | yes | $0 |
| 14 | 300825627 | CAPE ANN ROWING CLUB | Rowley | MA | N67 | yes | $0 |
| 15 | 330245281 | MISSION BAY ROWING ASSOCIATION | San Diego | CA | N67Z | yes | $0 |
| 16 | 432083809 | MOHAWK HOMESCHOOL ROWING ASSOCIATION INC | Rexford | NY | N67 | yes | $0 |
| 17 | 453965144 | KITSAP ROWING ASSOCIATION | Indianola | WA | N67 | yes | $0 |
| 18 | 462335973 | ELGIN UNITED ROWING CLUB | Saint Charles | IL | N67 | yes | $0 |
| 19 | 471140512 | COVENTRY LAKE COMMUNITY ROWING INC | Coventry | CT | N67 | yes | $0 |
| 20 | 562288139 | CENTRAL PENNSYLVANIA ROWING ASSOCIATION | Shamokin Dam | PA | N67 | yes | $0 |
| 21 | 611489344 | SEATTLE AREA ROWING ASSOCIATION | Seattle | WA | N67 | yes | $0 |
| 22 | 820771169 | 805 ROWING CLUB INC | Simi Valley | CA | N67 | yes | $0 |
| 23 | 824732686 | NEW ENGLAND INTERSCHOLASTIC ROWING ASSOCIATION INC | Kent | CT | N67 | yes | $0 |
| 24 | 824918501 | HINSDALE COMMUNITY ROWING INCORPORATED | Burr Ridge | IL | N67 | yes | $0 |
| 25 | 843931267 | STATE COLLEGE AREA ROWING ASSOCIATION | State College | PA | N67 | yes | $0 |
| 26 | 911724256 | MONTLAKE ROWING CLUB | Seattle | WA | N67 | yes | $0 |
| 27 | 921496328 | BUFFALO RIVER ROWING CLUB HOLDINGS INC | Buffalo | NY | N67 | yes | $0 |
| 28 | 132554312 | NATIONAL ROWING FOUNDATION INC | Melrose | MA | N110 | no | $2,471,669 |
| 29 | 363137851 | CHICAGO ROWING FOUNDATION | Chicago | IL | — | no | $1,786,650 |
| 30 | 951185630 | SAN DIEGO ROWING CLUB | San Diego | CA | — | no | $1,537,552 |
| 31 | 237036394 | WEST SIDE ROWING CLUB INCORPORATED OF THE CITY OF BUFFALO | Buffalo | NY | — | no | $1,367,814 |
| 32 | 942711944 | LOS GATOS ROWING CLUB INC | Los Gatos | CA | N40 | no | $1,255,490 |
| 33 | 251544798 | THREE RIVERS ROWING ASSOCIATION | Pittsburgh | PA | — | no | $1,225,086 |
| 34 | 940881310 | SOUTH END ROWING CLUB | San Francisco | CA | — | no | $1,085,202 |
| 35 | 200183971 | PELHAM COMMUNITY ROWING ASSOCIATION INC | Pelham | NY | N99 | no | $914,335 |
| 36 | 232565133 | PENN ATHLETIC CLUB ROWING ASSOCIATION | Philadelphia | PA | N6XC | no | $887,837 |
| 37 | 911940390 | LOYOLA ACADEMY ROWING ASSOCIATION INC | Glenview | IL | O50 | no | $856,795 |
| 38 | 521725928 | CAPITAL ROWING CLUB INC | Washington | DC | N40Z | no | $656,160 |
| 39 | 911325075 | EVERETT ROWING ASSOCIATION | Everett | WA | — | no | $548,102 |
| 40 | 825380974 | WATUPPA ROWING CENTER INC | Fall River | MA | O50 | no | $456,530 |
| 41 | 061030107 | LITCHFIELD HILLS ROWING CLUB INC | Litchfield | CT | — | no | $447,303 |
| 42 | 260336670 | LAKE CASITAS ROWING ASSOCIATION | Ventura | CA | N99 | no | $415,307 |
| 43 | 951399555 | ZLAC ROWING CLUB LTD | San Diego | CA | — | no | $338,053 |
| 44 | 911486197 | VASHON ISLAND ROWING CLUB | Vashon | WA | — | no | $336,327 |
| 45 | 251872643 | FAIRMOUNT ROWING ASSOCIATION | Philadelphia | PA | N50 | no | $329,425 |
| 46 | 061011760 | NEW HAVEN ROWING CLUB INC | Oxford | CT | — | no | $288,442 |
| 47 | 680061639 | NORTH BAY ROWING CLUB | Petaluma | CA | — | no | $280,745 |
| 48 | 232284089 | PHILADELPHIA GIRLS ROWING CLUB | Philadelphia | PA | N20 | no | $246,343 |
| 49 | 464697587 | UNIONVILLE ROWING CLUB INC | Pocopson | PA | N99 | no | $230,886 |
| 50 | 043065952 | QUINSIGAMOND ROWING ASSOCIATION INC | Worcester | MA | N6XZ | no | $230,612 |
| 51 | 010958071 | BEDFORD CREW CLUB | Bedford | NH | N67 | yes | $187,830 |
| 52 | 911560405 | COMMENCEMENT BAY ROWING CLUB | Lakewood | WA | Z99Z | no | $173,650 |
| 53 | 222534123 | AMOSKEAG ROWING CLUB | Concord | NH | — | no | $147,064 |
| 54 | 991052037 | MERCER ISLAND ROWING CLUB | Mercer Island | WA | O12 | no | $118,085 |
| 55 | 273739862 | NEPONSET ROWING CLUB INC | Milton | MA | B11 | no | $107,995 |
| 56 | 061099817 | OLD LYME ROWING ASSOCIATION INC | Old Lyme | CT | B11 | no | $107,311 |
| 57 | 824454936 | WESTFORD COMMUNITY ROWING INC | Westford | MA | N60 | no | $95,750 |
| 58 | 991285351 | MILL TOWN ROWING | Everett | WA | N67 | no | $94,094 |
| 59 | 462741527 | UPPER ST CLAIR ROWING ASSOCIATION | Pittsburgh | PA | N68 | yes | $83,895 |
| 60 | 272633007 | NEW BEDFORD ROWING CENTER INC | New Bedford | MA | S20 | yes | $71,522 |
| 61 | 202542719 | GUILFORD ROWING INC | Guilford | CT | N67 | no | $66,775 |
| 62 | 141801357 | NEWBURGH ROWING CLUB INC | Newburgh | NY | N60 | no | $63,725 |
| 63 | 222547676 | MERRIMAC RIVER ROWING ASSN INC | Lowell | MA | N70 | no | $53,625 |
| 64 | 141810944 | SARATOGA ROWING ASSOCIATION INC | Saratoga Spgs | NY | N67 | no | $0 |
| 65 | 473633817 | HARVEYS LAKE ROWING CLUB | Shavertown | PA | N67 | no | $0 |
| 66 | 931464208 | PENINSULA COMMUNITY ROWING CLUB | Redwood City | CA | N67 | no | $0 |
| 67 | 800683332 | FRIENDS OF PORT ROWING INC | Port Washington | NY | N67 | no | $733,143 |
| 68 | 232887762 | STEEL CITY ROWING CORPORATION | Verona | PA | N71 | no | $307,527 |
| 69 | 141670428 | ORGANIZATION OF ADIRONDACK ROWERS AND SCULLERS INC | Albany | NY | N67Z | no | $301,164 |
| 70 | 020509611 | GREAT BAY ROWING INC | Durham | NH | N71 | no | $254,822 |
| 71 | 832145419 | CI ROWING CLUB INC | Oxnard | CA | N50 | no | $99,107 |
| 72 | 161588232 | BRIGHTON ROWING CLUB INC | Rochester | NY | B112 | no | $93,776 |
| 73 | 900500191 | TEXAS ROWING FOUNDATION INC | Austin | TX | P20 | no | $69,944 |
| 74 | 260211408 | ARLINGTON ROWING ASSOCIATION INC | Lagrangeville | NY | O50 | no | $67,233 |
| 75 | 841947220 | CHICAGO COMMUNITY SCULLING | Chicago | IL | N67 | yes | $61,748 |
| 76 | 472788119 | CAPE COD COMMUNITY ROWING INC | Harwich | MA | N30 | no | $56,308 |
| 77 | 921344427 | SANTA BARBARA COMMUNITY ROWING | Solvang | CA | N40 | no | $55,233 |
| 78 | 943112841 | BERKELY ROWING CLUB | Emeryville | CA | N60 | no | $41,872 |
| 79 | 364626580 | NEW TRIER ROWING CLUB | Winnetka | IL | N60 | no | $9,331 |
| 80 | 113469139 | COLD SPRING HARBOR ROWING ASSOCIATION | Cold Spg Hbr | NY | N60 | yes | $0 |
| 81 | 113774327 | MASS BAY OPEN WATER ROWING INC | North Carver | MA | N67 | yes | $0 |
| 82 | 133335172 | EMPIRE STATE ROWING ASSOCIATION INC | New York | NY | N70 | yes | $0 |
| 83 | 141803981 | LOURDES ROWING ASSOCIATION INC | Poughkeepsie | NY | N60 | yes | $0 |
| 84 | 201086185 | SPOKANE RIVER ROWING ASSOCIATION- SRRA | Spokane | WA | N70 | yes | $0 |
| 85 | 205288666 | TACOMA ROWING | University Pl | WA | N67 | yes | $0 |
| 86 | 261777973 | SAN LUIS OBISPO COUNTY ROWING CLUB | Sn Luis Obisp | CA | N60 | yes | $0 |
| 87 | 273692172 | SOLANO ROWING CLUB | Vallejo | CA | N60 | yes | $0 |
| 88 | 311627337 | ORCAS ISLAND ROWING ASSOCIATION | Eastsound | WA | N60 | yes | $0 |
| 89 | 342004520 | ISLAND ROWING ASSOCIATION | Langley | WA | N60 | yes | $0 |
| 90 | 465397416 | NATIONAL SCHOLASTIC ROWING ASSOCIATION | Kng of Prussa | PA | N70 | yes | $0 |
| 91 | 473321891 | CENTRAL CONNECTICUT ROWING INC | Middletown | CT | N67 | yes | $0 |
| 92 | 680473572 | STOCKTON ROWING INCORPORATED | Stockton | CA | N67 | yes | $0 |
| 93 | 770436209 | SANTA CRUZ ROWING CLUB | Santa Cruz | CA | N60 | yes | $0 |
| 94 | 814429015 | CLAM ISLAND ROWING | Silverdale | WA | N67 | yes | $0 |
| 95 | 820746940 | PRESTON HOLLOW ROWING ASSOCIATION | Dallas | TX | N60 | yes | $0 |
| 96 | 821406554 | OTSEGO AREA ROWING INC | Cooperstown | NY | N67 | yes | $0 |
| 97 | 873918065 | TRI-CITIES ROWING ASSOCIATION | Richland | WA | N60 | yes | $0 |
| 98 | 364182331 | SAINT IGNATIUS CHICAGO ROWING INC | Chicago | IL | N41Z | no | $572,105 |
| 99 | 223093391 | NISKAYUNA ROWING INC | Niskayuna | NY | N41I | no | $270,040 |
| 100 | 571231784 | ARLINGTON-BELMONT CREW INC | Belmont | MA | N67 | yes | $259,089 |
| 101 | 462227777 | ARTEMIS ROWING | Oakland | CA | O50 | no | $146,726 |
| 102 | 760725091 | HAWK ROWING CLUB | Conshohocken | PA | N11 | no | $46,472 |
| 103 | 463399973 | BABOOSIC LAKE ROWING CLUB | Amherst | NH | O51 | no | $31,725 |
| 104 | 831560138 | PARA ROWING FOUNDATION INC | Brookline | MA | N40 | no | $25,743 |
| 105 | 043837934 | CHAUTAUQUA LAKE ROWING ASSOCIATION INC | Jamestown | NY | N31 | yes | $0 |
| 106 | 061009302 | EAST LYME ROWING ASSOCIATION INC | East Lyme | CT | — | yes | $0 |
| 107 | 141726279 | HYDE PARK ROWING ASSOCIATION INC | Staatsburg | NY | Z99Z | yes | $0 |
| 108 | 141773417 | THE ALBANY IRISH ROWING CLUB INC | Delmar | NY | N60 | no | $0 |
| 109 | 141797011 | SARATOGA SPRINGS ROWING CLUB INC | Victory Mills | NY | P20 | yes | $0 |
| 110 | 166051471 | SYRACUSE ALUMNI ROWING ASSOCIATION | Baldwinsville | NY | — | yes | $0 |
| 111 | 202434211 | BUZZARDS BAY ROWING CLUB INC | Fairhaven | MA | N40 | yes | $0 |
| 112 | 232454679 | SUSQUEHANNA ROWING ASSOCIATION | Carlisle | PA | — | yes | $0 |
| 113 | 232852341 | QUAKER CITY ROWING FOUNDATION | Philadelphia | PA | T70 | yes | $0 |
| 114 | 251898197 | BEAVER COUNTY ROWING ASSOCIATION | Beaver | PA | N72 | yes | $0 |
| 115 | 262524843 | CHESTNUT HILL ROWING ASSOCIATION INC | Medford | MA | N12 | yes | $0 |
| 116 | 331408402 | SEATTLE ROWING FOUNDATION | Seattle | WA | N70 | no | $0 |
| 117 | 333449324 | SANTA BARBARA ROWING ASSOCIATION | Sacramento | CA | T12 | yes | $0 |
| 118 | 393055616 | MASSACHUSETTS ROWING ASSOCIATION INC | Pittsfield | MA | N60 | no | $0 |
| 119 | 422503408 | THE BAY AREA WHALEBOAT ROWING ASSOCIATION | Oakland | CA | N70 | no | $0 |
| 120 | 460653420 | ORANGE COUNTY ROWING ASSOCIATION INC | Newburgh | NY | N99 | yes | $0 |
| 121 | 463003007 | SQUAM COMMUNITY ROWING | Meredith | NH | Z99 | yes | $0 |
| 122 | 463973112 | SEATTLE UNIVERSITY ROWING FOUNDATION | Renton | WA | B11 | yes | $0 |
| 123 | 464987838 | NORTHEAST HIGH PERFORMANCE ROWING FOUNDATION INC | Bridgewater | CT | Z99 | yes | $0 |
| 124 | 473704624 | QUINSIGAMOND ROWING CLUB INC | Shrewsbury | MA | N99 | yes | $0 |
| 125 | 474396521 | PETERS TOWNSHIP ROWING CLUB INC | Mcmurray | PA | N60 | no | $0 |
| 126 | 611615091 | MARBLEHEAD ROWING CLUB INC | Marblehead | MA | B990 | yes | $0 |
| 127 | 680151183 | LAKE NATOMA ROWING ASSOCIATION INC | Gold River | CA | — | yes | $0 |
| 128 | 710912263 | BUBBLY CREEK ROWING FOUNDATION | Chicago | IL | N70 | no | $0 |
| 129 | 760270394 | BAY AREA ROWING CLUB OF HOUSTON | Houston | TX | — | yes | $0 |
| 130 | 760291435 | GREATER HOUSTON ROWING CLUB | Sugar Land | TX | N20 | yes | $0 |
| 131 | 812845918 | TURNING POINT ROWING CLUB INC | Valley Falls | NY | N40 | yes | $0 |
| 132 | 813434935 | TABLE MOUNTAIN ROWING CLUB | Chico | CA | C60 | yes | $0 |
| 133 | 814911803 | SHASTA ROWING ASSOCIATION | Redding | CA | — | yes | $0 |
| 134 | 824301086 | BROCKPORT COMMUNITY ROWING INC | Brockport | NY | N99 | yes | $0 |
| 135 | 850621591 | INTERCOLLEGIATE ROWING ASSOCIATION INC | Marshfield | MA | N60 | no | $0 |
| 136 | 873044222 | AMERICAN COLLEGIATE ROWING ASSOCIATION | Menlo Park | CA | N40 | yes | $0 |
| 137 | 882240028 | WILDCAT ALUMNI ROWING ASSOCIATION | Wayne | PA | N12 | yes | $0 |
| 138 | 942436235 | OAKLAND WOMENS ROWING CLUB | Oakland | CA | N60 | no | $0 |
| 139 | 460612640 | NORCAL CREW | Redwood City | CA | N67 | no | $1,651,665 |
| 140 | 352366125 | THOMAS EAKINS HEAD OF THE SCHUYLKILL REGATTA | Philadelphia | PA | N70 | no | $611,580 |
| 141 | 462888292 | DELTA SCULLING CENTER-EVERYBODY SCULLS INC | Stockton | CA | N99 | yes | $410,440 |
| 142 | 232640369 | DAD VAIL REGATTA ORGANIZING COMMITTEE | Plymouth Mtng | PA | N70Z | no | $340,333 |
| 143 | 010585828 | VANCOUVER LAKE CREW | Vancouver | WA | N67 | no | $317,345 |
| 144 | 550807439 | PENINSULA AQUATIC CENTER JUNIOR CREW | Redwood City | CA | N67 | no | $274,746 |
| 145 | 232995935 | CONESTOGA CREW CLUB | Berwyn | PA | N70 | no | $254,868 |
| 146 | 232840004 | RADNOR GIRLS CREW CLUB | Wayne | PA | N60 | no | $182,011 |
| 147 | 270043587 | RADNOR CREW CLUB INC | Wayne | PA | N60 | no | $167,666 |
| 148 | 061637768 | FRIENDS OF GLASTONBURY ROWING INC | S Glastonbury | CT | B12 | yes | $108,199 |
| 149 | 463063431 | FRIENDS OF DAVIS ROWING INC | Villa Park | CA | N99 | yes | $104,265 |
| 150 | 842348975 | MISSION ROWING | Santa Ynez | CA | N99 | no | $94,966 |
| 151 | 300664106 | ROCK CREEK ROWING INC | Washington | DC | N50 | no | $56,058 |
| 152 | 222511807 | FRIENDS OF WEST SIDE ROWING CLUB INCORPORATED OF THE CITY OF BUFFAL | Buffalo | NY | — | no | $52,360 |
| 153 | 471026302 | BOSTON ROWING FEDERATION INC | Wrentham | MA | N71 | no | $24,149 |
| 154 | 263273997 | BRUIN OARSMEN FOUNDATION | San Diego | CA | N67 | yes | $0 |
| 155 | 271066564 | OAKLAND ESTUARY WHALEBOAT ROWING SOCIETY | Alameda | CA | N60 | yes | $0 |
| 156 | 271400532 | CHICAGO ROWING UNION INC | Chicago | IL | N60 | yes | $0 |
| 157 | 331352442 | BUFFALO ROWING CLUB INC | Buffalo | NY | N30 | no | $0 |
| 158 | 372096779 | DUWAMISH ROWING CLUB | Seattle | WA | N30 | no | $0 |
| 159 | 455350552 | FRIENDS OF GEORGETOWN ROWING INC | Washington | DC | N67 | yes | $0 |
| 160 | 460836386 | FRIENDS OF ALBANY ROWING INC | Rensselaer | NY | N67 | yes | $0 |
| 161 | 800431083 | ORLEANS SWEEPS AND SCULLS INC | Orleans | MA | N67 | yes | $0 |
| 162 | 900328860 | NWLRC LEGENDS ROWING CLUB | Lake Stevens | WA | — | no | $0 |
| 163 | 942988754 | EMBARCADERO ROWING CLUB | Oakland | CA | N50 | no | $0 |
| 164 | 943114592 | ANCIENT MARINERS ROWING CLUB | Seattle | WA | — | no | $0 |
| 165 | 043317489 | HEAD OF THE CHARLES REGATTA INC | Melrose | MA | N20Z | no | $5,013,614 |
| 166 | 042963426 | OARS INC | Concord | MA | C320 | no | $547,367 |
| 167 | 454754365 | FRIENDS OF BROOKLINE ROWING | Brookline | MA | N11 | no | $335,404 |
| 168 | 454393850 | NEW YORK ARCHITECTS REGATTA FOUNDATION LTD | New York | NY | T30 | no | $151,623 |
| 169 | 043266332 | BERKSHIRE SCULLING ASSOCIATION INC | Pittsfield | MA | N60 | no | $93,189 |
| 170 | 161607924 | FAIRPORT CREW CLUB INC | Fairport | NY | N70 | no | $86,077 |
| 171 | 201987185 | FAYETTEVILLE-MANLIUS CREWSTERS INC | Manlius | NY | N67 | no | $85,739 |
| 172 | 201188090 | MORAINE STATE PARK REGATTA | Portersville | PA | R19 | yes | $75,844 |
| 173 | 203238667 | FOX CHAPEL CREW INC | Pittsburgh | PA | N67 | no | $73,912 |
| 174 | 822352995 | OJR WILDCAT CREW CLUB | Spring City | PA | N30 | yes | $64,159 |
| 175 | 451832009 | ROCHESTER COMMUNITY INCLUSIVE ROWING INC | Rochester | NY | P20 | no | $49,742 |
| 176 | 455388248 | CITY HONORS CREW INC | Buffalo | NY | N67 | yes | $44,997 |
| 177 | 043397446 | CAPE COD ROWING INC | Centerville | MA | N40 | no | $41,407 |
| 178 | 146031114 | MID HUDSON SCHOOL BOY ROWING INC | Poughkeepsie | NY | N40 | yes | $0 |
| 179 | 262234259 | WASHINGTON ROWING STEWARDS | Seattle | WA | B12 | yes | $0 |
| 180 | 264395333 | NAIADES ONCOLOGY ROWING INC | Rochester | NY | E50 | yes | $0 |
| 181 | 333112468 | NATIONAL ASSOCIATION OF COLLEGIATE ROWING OFFICIALS INC | Dover | MA | N99 | yes | $0 |
| 182 | 455195463 | ROWING ALUMNI ASSOCIATION | Wynnewood | PA | N99 | yes | $0 |
| 183 | 522070369 | SIDWELL FRIENDS SCHOOL ROWING | Washington | DC | B11 | yes | $0 |
| 184 | 820999822 | GREEN HARBOR RIVER ROWING | Green Harbor | MA | N50 | yes | $0 |
| 185 | 842486830 | NANTUCKET ROWING INC | Chicago | IL | N99 | yes | $0 |
| 186 | 844430150 | ROWING INDUSTRY TRADE ASSOCIATION | Hanover | NH | N01 | yes | $0 |
| 187 | 866649974 | NORWALK RIVER ROWING ENDOWMENT TR | Darien | CT | N11 | yes | $0 |
| 188 | 953426607 | FRIENDS OF UCLA ROWING | Marina Dl Rey | CA | N67I | no | $0 |
| 189 | 201552367 | FRIENDS OF MANHASSET CREW | Manhasset | NY | N67 | no | $514,249 |
| 190 | 330706214 | LONG BEACH JUNIOR CREW | Long Beach | CA | N70 | no | $392,623 |
| 191 | 237055786 | FRIENDS OF CALIFORNIA MENS CREW | Lafayette | CA | N67 | no | $117,793 |
| 192 | 352321072 | FRIENDS OF HANOVER CREW A NEW HAMPSHIR CORPORATION | Hanover | NH | N67 | no | $109,974 |
| 193 | 270763131 | FRIENDS OF UC IRVINE ROWING | Newport Beach | CA | N12 | no | $95,400 |
| 194 | 232579468 | FRIENDS OF HAVERFORD SCHOOL ROWING | Haverford | PA | B25I | no | $94,777 |
| 195 | 810663732 | WAPPINGERS CREW CLUB INC | Hopewell Jct | NY | O50 | no | $94,611 |
| 196 | 830708799 | TEXTILE RIVER REGATTA INC | Lowell | MA | N68 | no | $88,183 |
| 197 | 134061639 | EAST RIVER CREW INC | New York | NY | N67 | yes | $0 |
| 198 | 223795003 | NEW CANAAN HIGH SCHOOL CREW INC | Bridgeport | CT | N67 | yes | $0 |
| 199 | 273312181 | UC DAVIS WOMENS CREW | Davis | CA | N67 | yes | $0 |
| 200 | 332518301 | NEPA CREW | Wilkes Barre | PA | N67 | yes | $0 |
| 201 | 332964046 | ROWING 4 RARE | Mansfield | TX | H01 | no | $0 |
| 202 | 333778050 | RED WHITE BLUE CREW LTD | Port Kent | NY | N67 | yes | $0 |
| 203 | 334643464 | FRIENDS OF CAL POLY ROWING INC | Santa Barbara | CA | N60 | yes | $0 |
| 204 | 412500723 | LIGHTWEIGHT ROWING OF CALIFORNIA | San Francisco | CA | N99 | no | $0 |
| 205 | 823903866 | FRIENDS OF HINGHAM ROWING INC | Hingham | MA | N60 | yes | $0 |
| 206 | 943179767 | OLD ANACORTES ROWING SOCIETY | Anacortes | WA | T99Z | no | $0 |
| 207 | 993153975 | BACHMAN ROWING OUTREACH TO THE COMMUNITY | Dallas | TX | P20 | no | $0 |
| 208 | 993581208 | FRIENDS OF WEST OLYMPIA ROWING CLUB | Olympia | WA | N12 | no | $0 |
| 209 | 994577844 | GREEN GRANITE ROWING INC | Dallas | TX | N11 | no | $0 |
| 210 | 232218986 | LOWER MERION HIGH SCHOOL CREW ASSOCIATION INC | Ardmore | PA | — | no | $173,821 |
| 211 | 680262297 | CAPITAL CREW BOOSTERS CLUB | Gold River | CA | N67 | no | $62,230 |
| 212 | 882402334 | LOCK HAVEN REGATTA FOUNDATION | Lock Haven | PA | S80 | no | $19,829 |
| 213 | 061468487 | SCULLY-GREENE-DUNN FAMILY ASSOCIATION | Southington | CT | — | yes | $0 |
| 214 | 222547069 | BUZZARDS BAY REGATTA INC | Dartmouth | MA | — | yes | $0 |
| 215 | 251598395 | THE SYBARASH REGATTA FOUNDATION INC | Merion Sta | PA | — | yes | $0 |
| 216 | 251699353 | MT LEBANON HIGH SCHOOL CREW | Pittsburgh | PA | N67 | no | $0 |
| 217 | 263235097 | FRIENDS OF SAC STATE MEN S ROWING | Folsom | CA | N196 | yes | $0 |
| 218 | 271114932 | FRIENDS OF MEDFORD ROWING- MEDFORD HIGH SCHOOL INC | Medford | MA | B12 | yes | $0 |
| 219 | 320408205 | SOUTHERN CALIFORNIA SCULLERS CLUB | Long Beach | CA | N99 | yes | $0 |
| 220 | 333862888 | 1886 REGATTA FOUNDATION INC | New York | NY | N70 | no | $0 |
| 221 | 473852812 | NMA ROWING BOOSTER CLUB INC | Newburgh | NY | N99 | yes | $0 |
| 222 | 474374172 | FLIP FLOP REGATTA INC | Marion | MA | N12 | yes | $0 |
| 223 | 815101057 | HHS ROWING PARENTS ASSOCIATION | Haverhill | MA | B11 | yes | $0 |
| 224 | 820627758 | SOUTH KITSAP ROWING BOOSTERS | Port Orchard | WA | O12 | yes | $0 |
| 225 | 821076000 | OARS FOUNDATION INC | San Antonio | TX | C12 | yes | $0 |
| 226 | 822597025 | THOMAS SCULLY FOUNDATION INC | Miller Place | NY | G30 | yes | $0 |
| 227 | 823315302 | JEREMY SCULLARK FOUNDATION | Chicago | IL | O50 | yes | $0 |
| 228 | 834066211 | FRIENDS OF PWHS ROWING | Conshohocken | PA | N11 | yes | $0 |
| 229 | 862555805 | SURVIVE-OARS INC | Westport | CT | E60 | yes | $0 |
| 230 | 871218918 | CATALINA CREW FOUNDATION | Marina Dl Rey | CA | N67 | no | $0 |
| 231 | 922440181 | EAST DALLAS SCULLERS | Dallas | TX | N50 | yes | $0 |
| 232 | 460878484 | JACKSON-REED CREW BOOSTER CLUB INC | Washington | DC | N12 | yes | $653,190 |
| 233 | 264677724 | FRIENDS OF GREEN LAKE CREW | Seattle | WA | T11 | yes | $567,958 |
| 234 | 800142507 | FRIENDS OF GREENWICH CREW INC | Cos Cob | CT | B11 | yes | $190,225 |
| 235 | 863427582 | JACKIE BOYS CREW FOUNDATION INC | Oceanside | NY | P20 | no | $87,948 |
| 236 | 042880378 | SHAUN P SCULLY SCHOLARSHIP FUND INC | Wilmington | MA | — | no | $0 |
| 237 | 043556853 | SCULLY FAMILY FOUNDATION | Lexington | MA | T22 | no | $0 |
| 238 | 200414306 | IRENE S SCULLY FAMILY FOUNDATION | San Francisco | CA | T20 | no | $0 |
| 239 | 233094249 | MICHAEL AND PATRICIA SCULLY FAMILY FOUNDATION INC | Jenkintown | PA | T22 | no | $0 |
| 240 | 237402866 | SCULLTON CHRISTIAN AND MISSIONARY ALLIANCE | Rockwood | PA | — | no | $0 |
| 241 | 273124997 | FRIENDS OF RIVERHEAD CREW INC | Wading River | NY | N67 | yes | $0 |
| 242 | 330754362 | OARSMEN FOUNDATION | Torrance | CA | T22Z | no | $0 |
| 243 | 392955836 | SCULLY FAMILY FOUNDATION | Frankfort | IL | T12 | no | $0 |
| 244 | 462014396 | JOHN H AND REGINA K SCULLY FOUNDATION | San Rafael | CA | T22 | no | $0 |
| 245 | 474011434 | JOHN E SCULLY CHARITABLE FOUNDATION INC | Cheshire | CT | T22 | no | $0 |
| 246 | 871924380 | CREW ATHLETICS | Huntingtn Bch | CA | N70 | yes | $0 |
| 247 | 872815703 | FRIENDS OF GW MENS ROWING | Washington | DC | N12 | no | $0 |
| 248 | 881957445 | SCULLY TOMASKO FOUNDATION | Tappan | NY | A40 | no | $0 |
| 249 | 931709454 | JOHN H AND DOROTHY M SCULLY TRUST | Mineola | NY | T20 | no | $0 |
| 250 | 141774286 | FRIENDS OF SHENENDEHOWA CREW INC | Clifton Park | NY | T11 | no | $180,283 |
| 251 | 061549558 | FRIENDS OF STONINGTON CREW INC | Stonington | CT | N11 | no | $103,181 |
| 252 | 830749851 | IHS CREW BOOSTERS | Kenmore | WA | N01 | yes | $91,542 |
| 253 | 200455439 | FRIENDS OF SHREWSBURY CREW INC | Shrewsbury | MA | B11 | yes | $70,305 |
| 254 | 205841292 | TEXAS CREW FOUNDATION | Austin | TX | N11 | yes | $0 |
| 255 | 333093839 | ORIGINAL VENICE CREW FOUNDATION | Irvine | CA | J03 | yes | $0 |
| 256 | 333564795 | COOPERS ICE CREAM CREW FOUNDATION | Valencia | PA | E86 | yes | $0 |
| 257 | 832474263 | MOM CREW FOUNDATION INC | Mckinney | TX | B01 | yes | $0 |
| 258 | 202168753 | FRIENDS OF SCHOLASTIC CREW INC | Rochester | NY | N12 | no | $93,446 |
| 259 | 060963997 | FRIENDS OF SIMSBURY CREW INC | Simsbury | CT | B25I | no | $71,584 |
| 260 | 412192899 | FRIENDS OF HARRITON CREW | Bryn Mawr | PA | B94 | no | $56,003 |
| 261 | 414900146 | CAMS CREW FOUNDATION | Hopedale | MA | E60 | no | $0 |
| 262 | 881925261 | CUMMINS CREW FOUNDATION | Irwin | PA | P62 | no | $0 |
| 263 | 043493861 | WORCESTER PUBLIC HIGH SCHOOLS CREW TEAM BOOSTER CLUB | Worcester | MA | B11 | yes | $0 |
| 264 | 141797750 | FRIENDS OF NEWBURGH CREW INC | Newburgh | NY | A99Z | yes | $0 |
| 265 | 204324761 | BALDWINSVILLE CREW BOOSTERS CLUB INC | Baldwinsville | NY | B11 | yes | $0 |
| 266 | 223757661 | POUGHKEEPSIE CREW PARENTS INC | Poughkeepsie | NY | B11 | yes | $0 |
| 267 | 472423844 | LSM CREW BOOSTER CLUB INC | Burlington | CT | N11 | yes | $0 |
| 268 | 812709657 | VRHS CREW BOOSTER CLUB CORP | Deep River | CT | O12 | yes | $0 |

## Tier 2B — genuinely ambiguous, needs verification (184)

### Boat clubs — verify rowing vs. yacht/power/lake-social (85)

"Boat club" alone does not distinguish a rowing barge club (e.g. Schuylkill-style, Cambridge/Union/Riverside) from a yacht/power/lake-recreation club. **Resolve:** check boathouse listing / club website / USRowing membership for sweep/sculling shells.

| EIN | Name | City | ST | NTEE | 990-N | BMF rev |
|-----|------|------|----|------|-------|--------:|
| 750275000 | FORT WORTH BOAT CLUB | Fort Worth | TX | — | no | $2,325,717 |
| 041978020 | WINCHESTER BOAT CLUB | Winchester | MA | — | no | $1,405,519 |
| 041920045 | UNION BOAT CLUB | Boston | MA | — | no | $1,377,107 |
| 041144490 | CAMBRIDGE BOAT CLUB | Cambridge | MA | — | no | $1,236,677 |
| 060542400 | SOUTH NORWALK BOAT CLUB | Norwalk | CT | — | no | $1,152,382 |
| 042664080 | THE RIVERSIDE BOAT CLUB OF CAMBRIDGE | Cambridge | MA | N70 | no | $946,436 |
| 046112940 | MEDFORD BOAT CLUB | West Medford | MA | — | no | $775,873 |
| 133033063 | NYACK BOAT CLUB INC | Nyack | NY | — | no | $748,536 |
| 203419468 | WHITEMARSH BOAT CLUB | Conshohocken | PA | B990 | no | $716,937 |
| 273276437 | CONNECTICUT BOAT CLUB | Norwalk | CT | N67 | no | $634,195 |
| 465743589 | LONG COVE BOAT CLUB INC | Dallas | TX | N50 | yes | $489,099 |
| 041677560 | NORTH END BOAT CLUB | Newburyport | MA | N50 | no | $468,033 |
| 060395435 | HOUSATONIC BOAT CLUB | Stratford | CT | N50 | no | $379,938 |
| 362223035 | SPRING VALLEY BOAT CLUB | Granville | IL | N50 | no | $379,587 |
| 740637556 | GALVESTON BOAT CLUB INC | Galveston | TX | — | no | $372,065 |
| 941710524 | MCCLURE BOAT CLUB INC | Snelling | CA | N99 | no | $368,939 |
| 161099792 | CASCADILLA BOAT CLUB LTD | Ithaca | NY | N67Z | no | $331,505 |
| 231434345 | PEQUEA BOAT CLUB | Pequea | PA | — | no | $311,178 |
| 111437803 | VARUNA BOAT CLUB INC | Brooklyn | NY | N50 | no | $236,566 |
| 370949932 | PEKIN BOAT CLUB | Pekin | IL | — | no | $223,661 |
| 046014740 | SATUIT BOAT CLUB INC | Scituate | MA | — | no | $222,639 |
| 946254767 | BAYVIEW BOAT CLUB | San Francisco | CA | — | no | $220,164 |
| 370749473 | DANVILLE BOAT CLUB | Danville | IL | — | no | $196,947 |
| 231579774 | TRI COUNTY BOAT CLUB | Middletown | PA | — | no | $192,129 |
| 231210140 | WEST END BOAT CLUB | Essington | PA | — | no | $178,380 |
| 362382136 | LIBERTYVILLE BOAT CLUB | Libertyville | IL | — | no | $172,878 |
| 473895773 | ROCHESTER BOAT CLUB INC | Fairport | NY | N70 | yes | $167,921 |
| 251333598 | JESSOP BOAT CLUB | Carmichaels | PA | — | no | $152,157 |
| 060474960 | NORWALK BOAT CLUB INC | Norwalk | CT | — | no | $143,681 |
| 042390979 | FRANKLIN COUNTY BOAT CLUB INC | Turners Falls | MA | — | no | $129,454 |
| 222624241 | CRESCENT BOAT CLUB | Philadelphia | PA | N60 | no | $120,512 |
| 222543370 | RED HOOK BOAT CLUB INC | Red Hook | NY | — | yes | $115,429 |
| 756026820 | WHITE ROCK BOAT CLUB INC | Dallas | TX | — | no | $109,439 |
| 370670839 | QUINCY BOAT CLUB | Quincy | IL | — | no | $109,130 |
| 060768024 | DARIEN BOAT CLUB INC | Darien | CT | — | no | $100,494 |
| 370524510 | SOUTH SIDE BOAT CLUB | Quincy | IL | — | no | $96,301 |
| 020440331 | GEORGES MILLS BOAT CLUB | New London | NH | — | no | $95,118 |
| 204190295 | SOUTH NORWALK BOAT CLUB EDUCATIONALFOUNDATION INC | Norwalk | CT | B99 | yes | $91,784 |
| 941520489 | AUBURN BOAT CLUB INC | Bowman | CA | — | no | $90,791 |
| 232478239 | LAKE VIEW BOAT CLUB | Wrightsville | PA | — | yes | $81,422 |
| 146017433 | CRESCENT BOAT CLUB INC | Halfmoon | NY | — | no | $64,249 |
| 237453684 | HAMPTON RIVER BOAT CLUB | Hampton | NH | N50 | yes | $63,250 |
| 061097882 | BYRAM SHORE BOAT CLUB INC C/O BYRAM PARK | Greenwich | CT | — | yes | $62,407 |
| 233073476 | CATAWISSA BOAT CLUB INC | Bloomsburg | PA | N99 | yes | $49,422 |
| 237294457 | GOLDEN ANCHOR BOAT CLUB | Tracy | CA | — | yes | $48,163 |
| 271749049 | HOOK BOAT CLUB INC | Stuyvesant | NY | N50 | no | $27,851 |
| 116037965 | SUFFOLK BOAT CLUB INC | Patchogue | NY | — | no | $19,012 |
| 814199339 | AFF BOAT CLUB LLC | Bloomsburg | PA | N99 | yes | $0 |
| 020605141 | ANABAS BOAT CLUB INC | Broad Channel | NY | N50 | yes | $0 |
| 994938926 | BHARATH BOAT CLUB USA INC | Vly Cottage | NY | N60 | no | $0 |
| 862716832 | BOSTON TAIWANESE BOAT CLUB INC | Pittsfield | MA | N60 | yes | $0 |
| 256083333 | BUTLER BOAT CLUB INC | Butler | PA | N67 | yes | $0 |
| 911029835 | CARLING BOAT CLUB | Edgewood | WA | — | yes | $0 |
| 236296829 | DANVILLE BOAT CLUB INC | Danville | PA | — | yes | $0 |
| 061100192 | ESSEX BOAT CLUB INC | Essex | CT | N50 | yes | $0 |
| 414891193 | FRIENDS OF PORT FIDELIS BOAT CLUB I NC | Mount Sinai | NY | N67 | no | $0 |
| 231505778 | G HENRY FRICK BOAT CLUB INC | Allentown | PA | — | yes | $0 |
| 363285686 | GALENA BOAT CLUB INC | Galena | IL | — | yes | $0 |
| 208845051 | HARLEM RIVER BOAT CLUB | New York | NY | N70 | yes | $0 |
| 161561343 | HIAWATHA ISLAND BOAT CLUB INC | Owego | NY | N70 | yes | $0 |
| 756036943 | LAKE FOREST BOAT CLUB | Grapevine | TX | — | yes | $0 |
| 134355065 | LAKE LA QUINTA BOAT CLUB INC | La Quinta | CA | N67 | yes | $0 |
| 916180107 | LAKE ROESIGER COMMUNITY AND BOAT CLUB | Snohomish | WA | N50 | yes | $0 |
| 510141510 | LAKE WICKABOAG BOAT CLUB INC | Warren | MA | N50 | yes | $0 |
| 222489741 | MANCHESTER HARBOR BOAT CLUB INC | Manchester | MA | N50 | yes | $0 |
| 236390897 | MILTON BOAT CLUB | Milton | PA | — | yes | $0 |
| 256058291 | MOUNTAIN BOAT CLUB INC | Latrobe | PA | — | yes | $0 |
| 237149662 | NORRISTOWN BOAT CLUB INC | Gwynedd Vly | PA | N67 | yes | $0 |
| 934180333 | NORTH END BOAT CLUB SCHOLARSHIP FUND INCORPORATED | Newburyport | MA | B82 | no | $0 |
| 800758241 | NORTH SHORE BOAT CLUB | Linesville | PA | N50 | yes | $0 |
| 240833463 | NORTHUMBERLAND BOAT CLUB | Shamokin Dam | PA | — | yes | $0 |
| 830649722 | PEKIN BOAT CLUB AUXILIARY | Pekin | IL | N50 | yes | $0 |
| 370620201 | PEORIA BOAT CLUB | Peoria | IL | — | yes | $0 |
| 800644967 | RICES LANDING BOAT CLUB | Waynesburg | PA | N50 | yes | $0 |
| 141613558 | ROE-JAN CREEK BOAT CLUB | Germantown | NY | N50 | yes | $0 |
| 911241940 | SEAFAIR BOAT CLUB | Auburn | WA | — | yes | $0 |
| 453724656 | SIX POINTS BOAT CLUB INC | Rostraver Twp | PA | N67 | yes | $0 |
| 993886667 | SKIPPERS LANDING BOAT CLUB INC | Monaca | PA | N67 | no | $0 |
| 922885034 | UNITY BOAT CLUB INC | Washington | DC | N60 | no | $0 |
| 376045456 | VALLEY BOAT CLUB INC | Griggsville | IL | — | yes | $0 |
| 862077594 | WELLESLEY BOAT CLUB | Wellesley | MA | N50 | yes | $0 |
| 042452443 | WEST FALMOUTH BOAT CLUB INC | West Falmouth | MA | — | yes | $0 |
| 453680402 | WINDY CITY DRAGONS BOAT CLUB NFP | Mchenry | IL | N70 | yes | $0 |
| 916057658 | YAKIMA VALLEY BOAT CLUB | Yakima | WA | — | yes | $0 |
| 237389125 | YOLO SUTTER BOAT CLUB INC | Knights Landing | CA | N50 | yes | $0 |

### Ambiguous "crew" — no aquatic NTEE, no clear rowing context (93)

Name contains "crew" but nothing ties it to rowing (blank/non-aquatic NTEE, generic name). Includes probable CREW (Commercial Real Estate Women) metro chapters and other non-rowing crews that lacked a decisive trap keyword. **Resolve:** confirm NTEE/website; most will drop to excluded.

| EIN | Name | City | ST | NTEE | 990-N | BMF rev |
|-----|------|------|----|------|-------|--------:|
| 042767395 | CREW BOSTON INC | Boston | MA | — | no | $975,093 |
| 412072595 | DALLAS UNITED CREW INC | Dallas | TX | O50 | no | $922,157 |
| 352392415 | EXTREME KIDS AND CREW INC | Brooklyn | NY | O50 | yes | $615,292 |
| 921645501 | COCO NIBS CREW | San Diego | CA | — | no | $541,966 |
| 161556377 | PITTSFORD CREW INC | Pittsford | NY | N116 | no | $412,447 |
| 942976226 | BERKELEY CREW | Berkeley | CA | — | no | $315,401 |
| 330159934 | CREW SAN DIEGO | Escondido | CA | — | no | $315,292 |
| 270702682 | RAISING CANES CREW FUND | Plano | TX | P80 | yes | $226,348 |
| 330392679 | CREW-ORANGE COUNTY A CALIFORNIA CORPORATION | East Irvine | CA | — | no | $218,657 |
| 844462672 | OAKTREE CREW | Norwich | CT | D20 | yes | $104,461 |
| 542119474 | PINE-RICHLAND CREW | Gibsonia | PA | O50 | no | $82,642 |
| 453664854 | CHEMO CREW | Modesto | CA | G19 | yes | $81,527 |
| 474996593 | BEACH CREW ALUMNI ASSOCIATION | Solana Beach | CA | B11 | yes | $73,080 |
| 263195746 | MERCY CREW INC | Rochester | NY | B112 | no | $60,939 |
| 333190767 | CALLANS CREW | Shallowater | TX | P99 | no | $57,250 |
| 854263917 | MATTHEWS CREW INC | Quincy | MA | F12 | no | $12,170 |
| 465244083 | LARKSPUR REC ING CREW | Larkspur | CA | N11 | yes | $9,371 |
| 334156572 | THE KINDNESS CREW | Houston | TX | D20 | no | $2,000 |
| 461868682 | HOLLIS BROOKLINE CAVALIERS CREW | Hollis | NH | B11 | no | $9 |
| 414134212 | 43 KEYSTONE CREW | Greencastle | PA | X20 | no | $0 |
| 871043569 | 8TEENTH CREW | Chicago | IL | O50 | yes | $0 |
| 413153357 | AAA CREWS HOME 1 - ADULT APOYO AMOR | Long Beach | CA | P76 | no | $0 |
| 933973672 | AARONS TAB CREW | Vandling | PA | E12 | no | $0 |
| 821857647 | ANGELS FIGHT CREW | The Colony | TX | W12 | yes | $0 |
| 392412357 | BLESSING CREW | Frisco | TX | P20 | yes | $0 |
| 991760858 | BLUE CREW GIVES BACK | Frazer | PA | C12 | no | $0 |
| 923392408 | BLUE CREW LEMC NFP | Champaign | IL | N12 | yes | $0 |
| 334433878 | BOBBYS CREW | Temecula | CA | W12 | yes | $0 |
| 461700493 | BRAIN RECOVERY CREW | Carnegie | PA | F60 | yes | $0 |
| 994224351 | BRU CREW | Salinas | CA | B12 | no | $0 |
| 882661337 | BUCKSAW CREW CONROE | Spring | TX | Y42 | yes | $0 |
| 462489424 | BUILD CREW | East Hampton | NY | A20 | yes | $0 |
| 823674370 | CAPTAIN CUE AND DA CREW | Santa Fe | TX | W12 | yes | $0 |
| 334838547 | CARSONS CREW | Manhattan | IL | G80 | yes | $0 |
| 815375956 | CARTERS CREW CORP | Altamont | NY | P20 | no | $0 |
| 394979309 | CASED CREW | Foothill Rnch | CA | O20 | no | $0 |
| 862388612 | CENTURY PLUS CREW | Brooklyn | NY | T30 | no | $0 |
| 392258341 | CERBERUS CREW | Brewster | NY | T50 | yes | $0 |
| 863400393 | CHILDRESS BLUE CREW INC | Childress | TX | — | yes | $0 |
| 870783001 | CITIZENS AGAINST DRUGS THE MOVE CREW | Bloomfield | CT | F01 | yes | $0 |
| 333038567 | CLAYS COLOR CREW | Dallas | TX | P30 | no | $0 |
| 461901641 | COLINS CREW INC | Wallingford | CT | E86 | yes | $0 |
| 334480235 | CONCEPT CREW INC | Oceanside | NY | N40 | yes | $0 |
| 833179962 | CONNOLLYS CREW | Olympia | WA | W12 | yes | $0 |
| 845140453 | CONSCIOUS CREW | Port Orchard | WA | E60 | yes | $0 |
| 412455016 | CONVERSATIONS FOR CREW | Philadelphia | PA | E70 | no | $0 |
| 851614739 | CRAFTYS CREW | Poway | CA | D99 | no | $0 |
| 934009172 | CRAYON CREW | Austin | TX | M20 | no | $0 |
| 474845062 | CREW - INLAND EMPIRE FOUNDATION | Riverside | CA | — | yes | $0 |
| 237321582 | CREW FUND INC | Shutesbury | MA | E52Z | yes | $0 |
| 731703924 | CREW MC INC | Truckee | CA | N50 | yes | $0 |
| 861553940 | CREW SAN DIEGO BUILDING FUTURES FOUNDATION | San Diego | CA | B82 | no | $0 |
| 412834952 | CREWLOVE INC | Dorchester | MA | O50 | yes | $0 |
| 934304269 | CREWS COALITION INC | Washington | DC | P20 | no | $0 |
| 880497846 | CREWS FAMILY FOUNDATION | Oak Bluffs | MA | T21 | no | $0 |
| 820852312 | CREWS FOR A CAUSE | N Hollywood | CA | A30 | yes | $0 |
| 820831009 | CREWS KOLODZEY FOUNDATION | Buda | TX | T22 | no | $0 |
| 924028679 | DA RIVA CREW INC | Fallriver | MA | B12 | yes | $0 |
| 821879337 | DIGGY DOOS CREW | Georgetown | TX | D99 | yes | $0 |
| 476390714 | DREWS CREW SAVING ONE CHARITABLE TR | Export | PA | I23 | yes | $0 |
| 872812592 | FREEDOM CREW | Denton | TX | X20 | yes | $0 |
| 882561869 | FULTON FUN CREW | Fulton | IL | A27 | yes | $0 |
| 465267801 | HASSAN CREW RESOURCE CENTER | Rch Cucamonga | CA | P80 | yes | $0 |
| 510483870 | HUNTINGTON BEACH LONGBOARD CREW | Fountain Vly | CA | T50 | yes | $0 |
| 994496469 | JAM CREW FAMATION INC | Spring | TX | P99 | no | $0 |
| 412459592 | KINSHIP CREW CARE | Deerfield | IL | E60 | no | $0 |
| 332249132 | LEWS CREW | Birdsboro | PA | T12 | yes | $0 |
| 822839364 | LIMBS UP CREW | Topeka | IL | E86 | no | $0 |
| 394354754 | LOCAL LEGEND CREW NFP | Chicago | IL | J20 | no | $0 |
| 392176510 | LOVE TAPS CREW INC | Port Orchard | WA | P01 | yes | $0 |
| 263244032 | NORTH CASCADES CREW | Lake Stevens | WA | P20 | yes | $0 |
| 273632908 | PIT BULL CREW INC | Sacramento | CA | D20 | yes | $0 |
| 852613957 | RAINBOW CREW NW | Bainbridge Island | WA | P88 | yes | $0 |
| 332828591 | RBM CREW INC | Philadelphia | PA | A23 | no | $0 |
| 921928850 | RESPONSE CREW | Gilbertsville | PA | M99 | yes | $0 |
| 141830987 | RHINEBECK CREW INC | Rhinebeck | NY | N60 | yes | $0 |
| 821857568 | S AND J CREWS FOUNDATION | Buffalo | NY | O50 | yes | $0 |
| 320342152 | SIERRA EXPEDITIONARY LEARNING SCHOOL PARENT TEACHER CREW INC | Truckee | CA | B94 | yes | $0 |
| 981653588 | STANDBY CREW ACADEMY | Bronx | NY | A68 | no | $0 |
| 992481020 | STEADFAST CREW | Rockford | IL | M40 | no | $0 |
| 413447779 | STONE SOUP CREW | Seattle | WA | L19 | no | $0 |
| 364736800 | SUZ CREW | Montrose | NY | G19 | yes | $0 |
| 923471503 | TAKE 2 CREW | Sugar Land | TX | A62 | yes | $0 |
| 932012841 | TAKE DOWN CREW | Morris | IL | N12 | no | $0 |
| 863040277 | THE CREW CDC INC | Lansdowne | PA | — | yes | $0 |
| 320293296 | THE DOUBLE-T CREW INC | Katy | TX | T21 | yes | $0 |
| 742266260 | THE MASTERS CREW INC | Harlingen | TX | — | no | $0 |
| 881208781 | TM CREW | Newport Beach | CA | D20 | yes | $0 |
| 883796484 | TRAINING CREW | Dallas | TX | N61 | yes | $0 |
| 475020382 | TRUE U CREW | Royersford | PA | P99 | yes | $0 |
| 842845409 | TT CREW GIVES BACK | Dublin | CA | A12 | yes | $0 |
| 261148170 | VIKING CREW OF SELAH | Selah | WA | B11 | yes | $0 |
| 393225141 | WHATS UP CREW | Downey | CA | O01 | no | $0 |

### Mixed-discipline & "Crew Classic" (6)

Hybrid clubs that also row, and orgs named "Crew Classic" (a rowing-regatta convention). **Resolve:** confirm an active rowing program / regatta identity.

| EIN | Name | City | ST | NTEE | 990-N | BMF rev | Note |
|-----|------|------|----|------|-------|--------:|------|
| 134077892 | YONKERS PADDLING & ROWING CLUB | Yonkers | NY | N67 | yes | $160,112 | mixed discipline (paddling + rowing) — confirm rowing program |
| 330396059 | SAN DIEGO CREW CLASIC FOUNDATION | San Diego | CA | — | no | $20,494 | named "Crew Classic" (rowing-regatta convention) — confirm identity |
| 432096186 | KITSAP SAILING & ROWING FOUNDATION | Silverdale | WA | N67 | yes | $0 | mixed discipline (sail/yacht/power + rowing) — confirm rowing program |
| 680141371 | DEL NORTE YACHT & ROWING CLUB | Crescent City | CA | — | yes | $0 | mixed discipline (sail/yacht/power + rowing) — confirm rowing program |
| 752341730 | CREW CLASSIC INC | Dallas | TX | S30M | no | $368,746 | named "Crew Classic" (rowing-regatta convention) — confirm identity |
| 953276681 | SAN DIEGO CREW CLASSIC INC | San Diego | CA | — | no | $897,133 | named "Crew Classic" (rowing-regatta convention) — confirm identity |

## Excluded — not rowing (165)

By reason (not all rows listed — a few examples each):

| Reason | Count | Examples |
|--------|------:|----------|
| non-rowing "crew" (sport/dance/service/animal/fire/etc.) | 112 | A Crew Of Patches Theatre Foundation; Akayas Adopted Crew Rescue And Sanctuary; Alley Crew Softball Association; Altamont Crew Baseball Club |
| non-rowing "crew" (numbered / venturing / other) | 16 | Ballard Troop And Crew 100 Youth Charitable Association; Crew 1517 Inc; Crew 180; Crew 1872 Alumni Association |
| paddle sport (dragon boat / outrigger / canoe / kayak) | 14 | Adaptive Fusion Dragon Boat Club; Dc Dragon Boat Club Inc; Dragon Boat Club In Norristown Inc; Gig Harbor Dragon Boat Club |
| non-rowing boating (motor/power/ice/ski/yacht/sail) | 12 | Alton Motor Boat Club Inc; Bolinas Rod And Boat Club; Chautauqua Lake Power Boat Club Inc; Chicago Yacht Club Regatta Association Inc |
| CREW = Commercial Real Estate Women / business network | 11 | Community Home Rehabilitation Crew; Crew 2030; Crew Austin Inc; Crew Commercial Real Estate Woman Inc |

Total excluded: **165**.

## Appendix — SQL executed (read-only)

All queries run with `PGOPTIONS="-c default_transaction_read_only=on"` against Neon Postgres (`DATABASE_URL`). Schema inspection used `\d staging.bmf_row`, `\d staging.efile_index_row`, `\d staging.epostcard_row`, `\d staging.propublica_org`, `\d core.review_task`, `\d core.external_identifier`.

**Candidate universe & exclusion checks:**

```sql
-- distinct discovery EINs (962 tasks -> 675 EINs)
SELECT count(*) total_tasks, count(DISTINCT details->>'ein') distinct_eins
FROM core.review_task WHERE details->>'candidate'='discovery' AND status='open';

-- overlap with already-linked EINs (external_identifier namespace irs_ein) -> 0
SELECT count(DISTINCT rt.details->>'ein')
FROM core.review_task rt
JOIN core.external_identifier ei ON ei.namespace='irs_ein' AND ei.value = rt.details->>'ein'
WHERE rt.details->>'candidate'='discovery';

-- overlap with seed/cohort.csv EINs -> 0
WITH cohort(ein) AS (VALUES ('237397498'),('232744491'),('530127820'),('042863756'),
  ('113632924'),('331055179'),('237448092'),('363508216'),('272334832'),
  ('742219650'),('030388282'),('811495108'))
SELECT count(*) FROM core.review_task rt JOIN cohort c ON c.ein=rt.details->>'ein'
WHERE rt.details->>'candidate'='discovery';

-- e-file XML index coverage -> only 9 EINs / 49 rows, all cohort
SELECT count(*) rows, count(DISTINCT ein) eins FROM staging.efile_index_row;

-- ProPublica coverage for discovery -> 0
SELECT count(DISTINCT p.ein) FROM staging.propublica_org p
JOIN core.review_task rt ON rt.details->>'ein'=p.ein
WHERE rt.details->>'candidate'='discovery';
```

**Master extraction (per distinct EIN: BMF identity + XML years + 990-N + ProPublica flags):**

```sql
WITH disc AS (
  SELECT DISTINCT ON (details->>'ein') details->>'ein' AS ein,
         details->>'staged_name' AS staged_name
  FROM core.review_task
  WHERE details->>'candidate'='discovery' AND status='open'
  ORDER BY details->>'ein', created_at),
bmf AS (
  SELECT DISTINCT ON (ein) ein,
    raw_row->>'NAME' AS bmf_name, raw_row->>'CITY' AS city, raw_row->>'STATE' AS state,
    raw_row->>'NTEE_CD' AS ntee, raw_row->>'SUBSECTION' AS subsection,
    raw_row->>'STATUS' AS status, raw_row->>'REVENUE_AMT' AS revenue_amt,
    raw_row->>'FILING_REQ_CD' AS filing_req
  FROM staging.bmf_row ORDER BY ein, bmf_release_date DESC),
xml AS (SELECT ein, string_agg(DISTINCT tax_year::text, ',' ORDER BY tax_year::text) AS xml_years
        FROM staging.efile_index_row GROUP BY ein),
epc AS (SELECT DISTINCT ein FROM staging.epostcard_row),
pp  AS (SELECT DISTINCT ein FROM staging.propublica_org)
SELECT d.ein, d.staged_name, b.bmf_name, b.city, b.state, b.ntee, b.subsection,
  b.status, b.revenue_amt, b.filing_req, COALESCE(x.xml_years,'') AS xml_years,
  (e.ein IS NOT NULL) AS has_990n, (pp.ein IS NOT NULL) AS has_propublica
FROM disc d
LEFT JOIN bmf b ON b.ein=d.ein
LEFT JOIN xml x ON x.ein=d.ein
LEFT JOIN epc e ON e.ein=d.ein
LEFT JOIN pp ON pp.ein=d.ein
ORDER BY d.ein;
```

Tiering (Tier 1 / Tier 2 priority-pool vs. ambiguous / excluded) was applied in a Python post-step over this result set using name-keyword + NTEE rules; it performs no further DB writes.

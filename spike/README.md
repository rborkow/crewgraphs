# CrewGraphs — Phase-Zero IRS Data Spike

A throwaway-but-reproducible probe of whether we can build a US rowing-nonprofit
reference site on public IRS 990 e-file data. Everything here is self-contained,
keyless, and re-runnable. **See `report.md` for the findings and go/no-go.**

## Layout

```
spike/
  cohort.py            # the 10-org cohort + documented alternates (EINs)
  fetch_propublica.py  # ProPublica Nonprofit Explorer org JSON -> output/{ein}/propublica.json
  fetch_indices.py     # IRS yearly index CSVs -> cache/, grep cohort EINs -> cache/index_matches.csv
  fetch_xml.py         # GivingTuesday 990 lake -> output/{ein}/{object_id}.xml
  extract.py           # 24-concept extractor -> output/{ein}/{object_id}.parsed.json
  crosscheck.py        # 6 anchors vs ProPublica normals -> output/crosscheck.csv
  build_orgs_csv.py    # -> output/orgs.csv
  cache/               # downloads (gitignored via repo .gitignore: spike/cache/)
  output/{ein}/        # propublica.json, raw *.xml, *.parsed.json, filings_index.json
  output/orgs.csv, output/crosscheck.csv
  report.md            # THE deliverable
```

## Data sources (all anonymous, no keys)

| Source | Use | Notes |
|---|---|---|
| ProPublica Nonprofit Explorer API v2 | EIN resolution + normalized filing totals + `latest_object_id` | `filings_with_data` lags `latest_object_id` by 1–2 tax years; NULLs EZ breakdown fields |
| GivingTuesday 990 data lake (S3 `gt990datalake-rawdata`) | raw e-file XML by object_id | `EfileData/XmlFiles/{OBJECT_ID}_public.xml`; **lags IRS by months — freshest filings 404** |
| IRS yearly index CSVs (`apps.irs.gov/.../index_{YYYY}.csv`) | EIN → object_id per processing year | ~50–90 MB/year; server **ignores Range requests** (whole-file only) |
| NODC master concordance (GitHub) | xpath reference across schema versions | `cache/concordance.csv` is **Windows-1252**, not UTF-8 |

The classic `s3://irs-form-990` public bucket is **dead (404)** — the GT lake is its replacement.

## Rerun everything

```bash
cd /Users/rborkows/projects/crewgraphs        # repo root
uv run --with httpx spike/fetch_propublica.py  # 11 org JSONs (~12s, polite 1.1s sleep)
uv run --with httpx spike/fetch_indices.py 2020 2021 2022   # ~190 MB to cache/, greps EINs
uv run --with httpx spike/fetch_xml.py         # 28 XMLs (~1.1 MB); idempotent (skips cached)
uv run --with lxml  spike/extract.py           # writes *.parsed.json + prints resolution summary
uv run            python3 spike/crosscheck.py  # writes output/crosscheck.csv
uv run            python3 spike/build_orgs_csv.py
```

Every fetch step is idempotent: existing cache files and XMLs are skipped, so
reruns cost almost no bandwidth. `fetch_indices.py` accepts any list of years.

## Budget

Retained downloads ≈ **193 MB** (dominated by 3 IRS index CSVs at ~48–71 MB
each; concordance 3.2 MB; 28 XMLs = 1.1 MB). Gross over-the-wire ≈ 267 MB
including a one-time throwaway index probe. Cap was 500 MB.

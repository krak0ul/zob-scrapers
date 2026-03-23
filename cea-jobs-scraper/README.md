# CEA Job Scraper

A scraper to retrieve job listings from [emploi.cea.fr](https://www.emploi.cea.fr/offre-de-emploi/liste-offres.aspx).
Supports filtering by contract type, location, and keywords.

## Project layout

```
cea_jobs/
├── cea_jobs/
│   ├── spiders/
│   │   └── cea_spider.py     ← spider + card parser + pagination
│   ├── contract_types.py     ← contract type codes
│   ├── filters.py            ← filter engine (keywords / location / contract)
│   ├── items.py              ← data model
│   ├── pipelines.py          ← dedup + CSV + JSONL export
│   └── settings.py           ← Scrapy settings
├── cea_filters.yml           ← EDIT THIS — your search criteria
├── scrapy.cfg
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

---

## Running

### Option A — YAML config (recommended)

Edit `cea_filters.yml`, then:

```bash
scrapy crawl cea_jobs -a config=cea_filters.yml
```

### Option B — CLI arguments

```bash
# Keywords only
scrapy crawl cea_jobs -a keywords="machine learning,python"

# Full example
scrapy crawl cea_jobs \
  -a keywords="data,science" \
  -a locations="Paris,Grenoble" \
  -a contract_types="CDI,CDD" \
  -a keyword_mode=any
```

### Option C — YAML base + CLI override

```bash
scrapy crawl cea_jobs -a config=cea_filters.yml -a keyword_mode=all
```

---

## Contract types

| Code | Label |
|------|-------|
| `CDI` | CDI |
| `CDD` | CDD |
| `Alternance` | Alternance |
| `Stage` | Stage |
| `Post-Doctorat` | Post-doctorat |

---

## Locations

When location filters are specified, the spider submits server-side search queries to filter results directly from the website. Multiple locations are handled via separate requests.

| Region | Code |
|--------|------|
| France | `France` |
| Auvergne-Rhône-Alpes | `Auvergne-Rhône-Alpes` |
| Isère | `Isère` |
| Essonne | `Essonne` |
| Paris | `Paris` |
| Hauts-de-Seine | `Hauts-de-Seine` |
| Gard | `Gard` |
| Bouches du Rhône | `Bouches du Rhône` |
| Savoie | `Savoie` |
| Nord | `Nord` |
| Gironde | `Gironde` |

Example:
```bash
scrapy crawl cea_jobs -a locations="Isère,Paris"
```

---

## Output fields

### JobItem (listing page)

| Field | Source | Description |
|-------|--------|-------------|
| `reference` | URL / data attr | Job reference (e.g. `2026-39065`) |
| `title` | Card | Job title |
| `contract_type` | Card label | Normalized type (e.g. `CDD`) |
| `contract_label` | Card label | Human label (e.g. "CDD") |
| `location` | Card | City |
| `department` | Card | Department (e.g. Savoie (73)) |
| `lab` | Card | Research unit name |
| `duration` | Card label | Contract duration |
| `degree` | Card label | Required degree |
| `is_new` | Card tag | True if "Nouveau" badge present |
| `published_ago` | Card footer | Publication time |
| `match_reasons` | Filter | Which criteria triggered the match |
| `url` | Card link | Full URL to detail page |

### DetailItem (detail page)

| Field | Description |
|-------|-------------|
| `url` | Detail page URL |
| `reference` | Job reference |
| `title` | Job title |
| `lab` | Entity/unit |
| `location` | City |
| `department` | Department |
| `contract_label` | Contract type |
| `contract_type` | Normalized type |
| `description` | Full HTML description |
| `missions` | Mission/role description |
| `activities` | Activities section |
| `profile` | Candidate profile |
| `work_environment` | Work environment |
| `salary` | Salary information |
| `deadline` | Application deadline |
| `start_date` | Start date |
| `duration` | Contract duration |
| `work_time` | Full-time/part-time |
| `activity_sector` | Activity sector |
| `job_type` | Job type classification |
| `disability_access` | Accessibility info |

Results are written to `output/cea_jobs_YYYYMMDD_HHMMSS.csv` and `.jsonl`.
Detail items go to `output/cea_detail_YYYYMMDD_HHMMSS.csv` and `.jsonl`.

---

## Tips

- Delete `.scrapy_cache/` to force a completely fresh crawl.
- All filtering (keywords, location, contract type) is done server-side — the spider yields all results returned by the server
- match_reasons field shows which server filters matched each item
- Pagination uses URL parameters (`?page=N`) and terminates correctly after the last page
- Both listing and detail items can exist for the same URL (no deduplication conflict)

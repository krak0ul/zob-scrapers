# Sanofi Job Scraper

A Scrapy spider to scrape job listings from [jobs.sanofi.com](https://jobs.sanofi.com/en/search_jobs), Sanofi's global career portal (Radancy platform). Supports filtering by keywords, countries, regions, job families, and employment types.

## Project layout

```
sanofi-job-scraper/
├── sanofi_jobs/
│   ├── spiders/
│   │   └── sanofi_spider.py    ← SanofiSpider
│   ├── contract_types.py       ← employment type mappings
│   ├── filters.py              ← filter engine (keywords / countries / regions / job families)
│   ├── items.py                ← data model (JobItem, DetailItem)
│   ├── pipelines.py            ← dedup + CSV + JSONL export
│   └── settings.py             ← Scrapy settings
├── sanofi_filter.yml           ← EDIT THIS — your search criteria
├── run_sanofi.py               ← Runner script
├── scrapy.cfg
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

---

## Running

### Option A — Using the runner script (recommended)

```bash
# Run with default settings
python run_sanofi.py

# With keywords
python run_sanofi.py -k "data scientist"

# With config file
python run_sanofi.py -c sanofi_filter.yml

# With limit for testing
python run_sanofi.py -k "scientist" -l 10
```

### Option B — Using scrapy directly

```bash
# Keywords only
scrapy crawl sanofi_jobs -a keywords="data scientist"

# Full example
scrapy crawl sanofi_jobs \
  -a keywords="scientist,researcher" \
  -a countries="France" \
  -a regions="Ile-de-France" \
  -a employment_types="Regular" \
  -a keyword_mode=any
```

### Option C — YAML config with scrapy

```bash
scrapy crawl sanofi_jobs -a config=sanofi_filter.yml
```

---

## Filter parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `keywords` | Job title or description keywords (comma-separated) | `data scientist,machine learning` |
| `countries` | Filter by country | `France,Germany` |
| `regions` | Filter by region | `Ile-de-France` |
| `locations` | Filter by city | `Paris,Lyon` |
| `job_families` | Filter by job family | `Research,Quality` |
| `employment_types` | Filter by contract type | `Regular,Fixed Term` |
| `keyword_mode` | Match all or any keyword | `any` (default) or `all` |

### Employment type codes

| Code | Label |
|------|-------|
| `Regular` | CDI / Permanent |
| `Fixed Term` | CDD / Fixed Term |
| `Apprentice` | Apprenticeship |
| `Intern` | Internship |
| `VIE` | Voluntary International Exchange |
| `Temporary` | Temporary |
| `Sales Force` | Sales Force |
| `Contingent Worker` | Contingent Worker |

**Group shortcuts** (expand automatically):

| Shortcut | Expands to |
|----------|-----------|
| `cdi` | Regular |
| `cdd` | Fixed Term |
| `apprentissage` | Apprentice |
| `stage` | Intern, Intern/Trainee/Co-Op |
| `vie` | VIE |
| `temporaire` | Temporary, Contingent Worker |

---

## Output fields

### JobItem (listing page)

| Field | Source | Description |
|-------|--------|-------------|
| `reference` | data-job-id attribute | Job ID (e.g. `36315474816`) |
| `title` | h2 element | Job title |
| `location` | span.job-location | City and country |
| `department` | span.job-category | Job category/family |
| `contract_type` | Filter or empty | Employment type code |
| `contract_label` | Empty on listing | (filled on detail page) |
| `lab` | Empty | (reserved for compatibility) |
| `duration` | Empty | (reserved for compatibility) |
| `degree` | Empty | (reserved for compatibility) |
| `is_new` | Always false | (reserved for compatibility) |
| `published_ago` | Empty | (reserved for compatibility) |
| `match_reasons` | Filter | Which criteria triggered the match |
| `url` | Card link | Full URL to the detail page |

### DetailItem (detail page)

| Field | Source | Description |
|-------|--------|-------------|
| All JobItem fields | | |
| `description` | Job description | Full description HTML |
| `missions` | Missions section | Mission details |
| `activities` | Activities section | Required activities |
| `profile` | Profile section | Profile/candidate requirements |
| `work_environment` | Work environment | Work environment description |
| `salary` | Salary info | Salary range (if available) |
| `deadline` | Closing date | Application deadline |
| `start_date` | Start date | Job start date |
| `work_time` | Work time | Full-time/part-time |
| `activity_sector` | Activity sector | Industry/sector |
| `job_type` | Job type | Type of position |
| `disability_access` | Accessibility | Disability accessibility info |

Results are written to `output/sanofi_jobs_YYYYMMDD_HHMMSS.csv` and `.jsonl`.

---

## Tips

- Delete `.scrapy_cache/` to force a completely fresh crawl.
- The spider uses URL parameters (`?k=...&country=...`) to filter results server-side.
- Pagination uses `?p=N` query parameters (up to ~80 pages).
- For best performance, specify filters to reduce the number of pages to crawl.
- The spider automatically follows detail pages to collect full job descriptions.
- Both listings and detail pages are exported to separate CSV/JSONL files.

# CNRS Job Scraper v3

A scraper built with scrapy to make my pookie's job search easier. It retrieves and parses job listings from the [cnrs](https://emploi.cnrs.fr/Offres/Recherche.aspx) website made with this bs asp framework.
It allows filtering by contract type, location, and keywords.

## TODO
- Retrieve more info from the job listings
- Dockerize

## Project layout

```
cnrs_jobs/
├── cnrs_jobs/
│   ├── spiders/
│   │   └── cnrs_spider.py    ← spider + card parser + pagination
│   ├── contract_types.py     ← exact form values + group shortcuts
│   ├── filters.py            ← filter engine (keywords / location / contract)
│   ├── items.py              ← data model
│   ├── pipelines.py          ← dedup + CSV + JSONL export
│   └── settings.py           ← Scrapy settings
├── cnrs_filter.yml           ← EDIT THIS — your search criteria
├── scrapy.cfg
└── requirements.txt
```

## Setup
Make a venv and we're rolling
```bash
pip install -r requirements.txt
```

---

## Running

### Option A — YAML config (recommended)

Edit `cnrs_filter.yml`, then:

```bash
scrapy crawl cnrs_jobs -a config=cnrs_filter.yml
```

### Option B — CLI arguments

```bash
# Keywords only
scrapy crawl cnrs_jobs -a keywords="machine learning,python"

# Full example
scrapy crawl cnrs_jobs \
  -a keywords="deep learning,NLP" \
  -a locations="Paris,Grenoble" \
  -a contract_types="ITCDD,CHRCDD,DOCTOR" \
  -a keyword_mode=any

# Use a group shortcut
scrapy crawl cnrs_jobs -a contract_types="all_phd" -a keywords="bioinformatique"
```

### Option C — YAML base + CLI override

```bash
scrapy crawl cnrs_jobs -a config=cnrs_filter.yml -a keyword_mode=all
```

---

## Contract type codes

These are the exact values the search form submits:

| Code | Label |
|------|-------|
| `ITCDD` | CDD (Ingé + Techniciens) |
| `ITCDDM` | Contrat de projet (Ingé + Techniciens) |
| `ITCDI` | CDI (Ingé + Techniciens) |
| `ITCDIM` | CDI de mission (Ingé + Techniciens) |
| `FILDELEAU` | Mobilité Service Public (Fil de l'eau) |
| `NOEMI` | Mobilité Service Public (NOEMI) |
| `FSEP` | Mobilité CNRS (FSEP) |
| `STAG` | Convention de stage |
| `APPR` | Contrat d'apprentissage |
| `CHRCDD` | CDD (Chercheur) |
| `CHRCDDM` | Contrat de projet (Chercheur) |
| `CHRCDI` | CDI (Chercheur) |
| `CHRCDIM` | CDI de mission (Chercheur) |
| `DOCTOR` | Contrat doctoral |
| `CPJ` | Chaire de Professeur Junior |

**Group shortcuts** (expand automatically):

| Shortcut | Expands to |
|----------|-----------|
| `all_cdd` | ITCDD + CHRCDD |
| `all_cdi` | ITCDI + CHRCDI |
| `all_postdoc` | CHRCDD |
| `all_phd` | DOCTOR |
| `all_it` | ITCDD + ITCDDM + ITCDI + ITCDIM |
| `all_chercheur` | Tous codes chercheur |
| `mobility` | FILDELEAU + NOEMI + FSEP |

---

## Output fields

| Field | Source | Description |
|-------|--------|-------------|
| `reference` | URL | e.g. `UAR3282-ALEVAI-008` |
| `title` | Card | Job title |
| `contract_type` | URL path | Normalised code (e.g. `ITCDD`) |
| `contract_label` | Card label | Human label (e.g. "IT en contrat CDD") |
| `location` | Card meta | City |
| `department` | Card meta | Département (e.g. Hérault) |
| `lab` | Card meta | Research unit name |
| `duration` | Card label | e.g. "12 mois" |
| `degree` | Card label | e.g. "BAC + 2" |
| `is_new` | Card tag | True if "Nouveau" badge present |
| `published_ago` | Card footer | e.g. "Publiée il y a 0 heure(s)" |
| `match_reasons` | Filter | Which criteria triggered the match |
| `url` | Card link | Full URL to the detail page |

Results are written to `output/cnrs_jobs_YYYYMMDD_HHMMSS.csv` and `.jsonl`.

---

## Tips

- Delete `.scrapy_cache/` to force a completely fresh crawl.
- The spider pushes keywords and location into the server-side search when only
  one value is specified, which reduces how many pages are returned.
- The contract-type checkboxes are submitted directly as POST form data, so the
  server pre-filters by contract type before returning results.

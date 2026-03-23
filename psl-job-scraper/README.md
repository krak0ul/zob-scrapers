# PSL Job Scraper

A Scrapy spider to scrape job listings from [recrutement.psl.eu](https://recrutement.psl.eu/nos-offres), the recruitment portal of Université PSL. Built on Drupal 10, it supports filtering by keywords, contract type (profil), and establishments.

## Project layout

```
psl_job-scraper/
├── psl_jobs/
│   ├── spiders/
│   │   └── cnrs_spider.py     ← PslSpider (renamed to psl_jobs)
│   ├── contract_types.py      ← form values + group shortcuts + etablissements
│   ├── filters.py            ← filter engine (keywords / location / contract / etablissement)
│   ├── items.py              ← data model (JobItem, DetailItem)
│   ├── pipelines.py          ← dedup + CSV + JSONL export
│   └── settings.py           ← Scrapy settings
├── psl_filter.yml            ← EDIT THIS — your search criteria
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

Edit `psl_filter.yml`, then:

```bash
scrapy crawl psl_jobs -a config=psl_filter.yml
```

### Option B — CLI arguments

```bash
# Keywords only
scrapy crawl psl_jobs -a keywords="machine learning,python"

# Full example
scrapy crawl psl_jobs \
  -a keywords="deep learning,NLP" \
  -a locations="Paris" \
  -a contract_types="fiche_academique" \
  -a keyword_mode=any

# Filter by establishments (see table below)
scrapy crawl psl_jobs -a etablissements="146,149,157"

# Use a group shortcut
scrapy crawl psl_jobs -a contract_types="research" -a keywords="bioinformatique"
```

### Option C — YAML base + CLI override

```bash
scrapy crawl psl_jobs -a config=psl_filter.yml -a keyword_mode=all
```

---

## Contract type codes (profil)

These are the form checkbox values for the search form:

| Code | Label |
|------|-------|
| `fiche_administrative` | Administratif/Technique/Bibliothèque |
| `fiche_academique` | Enseignement & Recherche |

**Group shortcuts** (expand automatically):

| Shortcut | Expands to |
|----------|-----------|
| `admin` | fiche_administrative |
| `research` | fiche_academique |
| `all` | fiche_administrative + fiche_academique |

---

## Establishment filter

Filter by specific PSL establishments using their IDs:

| ID | Establishment |
|----|---------------|
| 146 | CNRS |
| 149 | Collège de France |
| 10 | Conservatoire national supérieur de musique et de danse de Paris |
| 148 | Conservatoire National Supérieur d'Art Dramatique - PSL |
| 150 | Dauphine - PSL |
| 205 | ESPCI Paris - PSL |
| 606 | Inria |
| 607 | Inserm |
| 209 | Institut Curie |
| 166 | Institut Louis Bachelier |
| 2445 | Institut national du service public |
| 190 | La Fémis |
| 160 | Les Beaux-Arts de Paris |
| 605 | Lycée Henri-IV |
| 24 | MINES Paris - PSL |
| 206 | Observatoire de Paris - PSL |
| 706 | PSL |
| 158 | École des arts décoratifs Paris - PSL |
| 153 | École française d'Extrême-Orient |
| 155 | École nationale des chartes - PSL |
| 2648 | École nationale supérieure d'architecture Paris-Malaquais - PSL |
| 147 | École nationale supérieure de Chimie de Paris - PSL |
| 157 | École normale supérieure - PSL |
| 193 | École Pratique des Hautes Études - PSL |

---

## Output fields

### JobItem (listing page)

| Field | Source | Description |
|-------|--------|-------------|
| `reference` | URL path | Job reference code (e.g. `pauwerkjbq`) |
| `title` | div.title | Job title |
| `lab` | div.title_etablissement | Establishment name |
| `contract_label` | div.profil | Profil type |
| `contract_type` | URL / form | fiche_administrative or fiche_academique |
| `location` | detail page | City and country |
| `published_ago` | div.created | Publication date |
| `start_date` | div.date | Starting date |
| `match_reasons` | Filter | Which criteria triggered the match |
| `url` | Card link | Full URL to the detail page |

### DetailItem (detail page)

| Field | Source | Description |
|-------|--------|-------------|
| All JobItem fields | | |
| `description` | div.desc + div.missions | Full description HTML |
| `missions` | div.missions div.elements | Mission details |
| `activities` | div.savoirs div.elements | Required activities |
| `profile` | div.savoirs div.elements | Profile/candidate requirements |
| `work_environment` | div.desc | Work environment description |
| `duration` | div.infos_supplementer | Contract duration |
| `deadline` | div.information | Application deadline |

Results are written to `output/psl_jobs_YYYYMMDD_HHMMSS.csv` and `.jsonl`.

---

## Tips

- Delete `.scrapy_cache/` to force a completely fresh crawl.
- The spider uses GET parameters (`?keys=...&type[fiche_administrative]=...`) to filter results server-side.
- Pagination uses `?page=N` query parameters.
- For best performance, specify filters to reduce the number of pages to crawl.
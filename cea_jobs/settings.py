BOT_NAME = "cea_jobs"
SPIDER_MODULES    = ["cea_jobs.spiders"]
NEWSPIDER_MODULE  = "cea_jobs.spiders"

# Politeness
ROBOTSTXT_OBEY           = True
DOWNLOAD_DELAY           = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS      = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 4

USER_AGENT = (
    "Mozilla/5.0 (compatible; CeaJobsBot/1.0; "
    "+krak0ul-job-scrapper"
)

DEFAULT_REQUEST_HEADERS = {
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr,en;q=0.5",
}

# HTTP cache
HTTPCACHE_ENABLED            = True
HTTPCACHE_EXPIRATION_SECS    = 3600
HTTPCACHE_DIR                = ".scrapy_cache"
HTTPCACHE_IGNORE_HTTP_CODES  = [500, 502, 503, 504]

# Retry 
RETRY_ENABLED    = True
RETRY_TIMES      = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]

# Pipelines
ITEM_PIPELINES = {
    "cea_jobs.pipelines.DuplicateFilterPipeline": 100,
    "cea_jobs.pipelines.CsvExportPipeline":       200,
    "cea_jobs.pipelines.JsonExportPipeline":      300,
}

LOG_LEVEL = "INFO"

TELNETCONSOLE_ENABLED = False

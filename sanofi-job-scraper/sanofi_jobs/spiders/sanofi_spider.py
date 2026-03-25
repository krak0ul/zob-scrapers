import re
from typing import Generator, Optional, List

import scrapy
from scrapy.http import Response

from itemadapter import ItemAdapter
from sanofi_jobs.items import JobItem, DetailItem
from sanofi_jobs.filters import FilterConfig, JobFilter
from sanofi_jobs.contract_types import EMPLOYMENT_TYPE_MAP

SEARCH_URL = "https://jobs.sanofi.com/en/search_jobs"


class SanofiSpider(scrapy.Spider):
    name = "sanofi_jobs"
    allowed_domains = ["jobs.sanofi.com"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cfg = FilterConfig.from_yaml(kwargs["config"]) if kwargs.get("config") else FilterConfig()
        cli = FilterConfig.from_cli(kwargs)
        if cli.keywords:           cfg.keywords         = cli.keywords
        if cli.locations:          cfg.locations        = cli.locations
        if cli.countries:          cfg.countries       = cli.countries
        if cli.regions:            cfg.regions          = cli.regions
        if cli.job_families:       cfg.job_families     = cli.job_families
        if cli.employment_types:   cfg.employment_types = cli.employment_types
        if "keyword_mode" in kwargs: cfg.keyword_mode = kwargs["keyword_mode"]

        self.filter = JobFilter(cfg)
        self.cfg = cfg
        self._log_filters(cfg)

        self.stats = {"total": 0, "detail_pages": 0}
        self._session_failures = 0
        self._max_session_failures = 3
        self._max_pages = 80

    def _log_filters(self, cfg: FilterConfig):
        if cfg.is_empty():
            self.logger.info("No filters — scraping all offers")
            return
        self.logger.info("Active filters:")
        if cfg.keywords:
            self.logger.info(f"  keywords ({cfg.keyword_mode}): {cfg.keywords}")
        if cfg.countries:
            self.logger.info(f"  countries: {cfg.countries}")
        if cfg.regions:
            self.logger.info(f"  regions: {cfg.regions}")
        if cfg.locations:
            self.logger.info(f"  locations: {cfg.locations}")
        if cfg.job_families:
            self.logger.info(f"  job_families: {cfg.job_families}")
        if cfg.employment_types:
            labels = [EMPLOYMENT_TYPE_MAP.get(e, e) for e in cfg.employment_types]
            self.logger.info(f"  employment_types: {cfg.employment_types} → {labels}")

    def start_requests(self):
        yield scrapy.Request(
            url=self._build_search_url(1),
            callback=self.parse_listing,
            cb_kwargs={"page": 1},
            dont_filter=True,
        )

    def _build_search_url(self, page: int = 1) -> str:
        if page == 1:
            return SEARCH_URL
        
        params = [("p", str(page))]

        if self.cfg.keywords:
            params.append(("k", " ".join(self.cfg.keywords)))

        if self.cfg.countries:
            for country in self.cfg.countries:
                params.append(("country", country))

        if self.cfg.regions:
            for region in self.cfg.regions:
                params.append(("region", region))

        if self.cfg.job_families:
            for jf in self.cfg.job_families:
                params.append(("job_family", jf))

        if self.cfg.employment_types:
            for et in self.cfg.employment_types:
                params.append(("etype", et))

        query_string = "&".join(f"{k}={v}" for k, v in params)
        return f"{SEARCH_URL}?{query_string}"

    def parse_listing(self, response: Response, page: int = 1):
        jobs = self._extract_jobs_from_response(response)
        if not jobs:
            self.logger.info(f"No jobs on page {page} — checking for session issues")
            self._handle_pagination_failure(response, page)
            return

        self._session_failures = 0
        self.logger.info(f"Page {page}: {len(jobs)} jobs")

        for job_data in jobs:
            item = self._create_job_item(job_data, response)
            if not item:
                continue

            matched, reasons = self.filter.match(ItemAdapter(item).asdict())
            if not matched:
                self.logger.debug(f"✗ {item.get('reference','?')}  not matched")
                continue

            item["match_reasons"] = reasons
            self.stats["total"] += 1
            self.logger.debug(f"✓ {item['reference']}  {item['title'][:55]}")
            yield item

            yield response.follow(job_data["url"], callback=self.parse_detail)

        if page < self._max_pages:
            next_page = page + 1
            next_link = response.css("a[rel='next']::attr(href)").get()
            if not next_link:
                next_link = response.css("li.pagination-next a::attr(href)").get()
            if next_link or self._has_more_pages(response):
                yield scrapy.Request(
                    url=self._build_search_url(next_page),
                    callback=self.parse_listing,
                    cb_kwargs={"page": next_page},
                    dont_filter=True,
                )

    def _has_more_pages(self, response: Response) -> bool:
        page_match = re.search(r"page\s+(\d+)\s+/\s+(\d+)", response.text)
        if page_match:
            current = int(page_match.group(1))
            total = int(page_match.group(2))
            return current < total
        return False

    def _extract_jobs_from_response(self, response: Response) -> List[dict]:
        jobs = []
        
        job_links = response.css("a[data-job-id]")
        
        for link in job_links:
            url = link.css("::attr(href)").get("")
            job_id = link.css("::attr(data-job-id)").get("")
            
            title = link.css("h2::text").get("").strip()
            
            link_html = link.get()
            
            location = ""
            loc_match = re.search(r'<span class="job-location"><strong>Location:\s*</strong>([^<]+)</span>', link_html)
            if loc_match:
                location = loc_match.group(1).strip()
            
            category = ""
            cat_match = re.search(r'<span class="job-category">.*?<strong>Category:\s*</strong>(.*?)</span>', link_html, re.DOTALL)
            if cat_match:
                category = cat_match.group(1).strip()
                category = re.sub(r'\s+', ' ', category)
            
            if url and job_id:
                jobs.append({
                    "url": response.urljoin(url),
                    "title": title,
                    "location": location,
                    "category": category,
                    "reference": job_id,
                })
        
        return jobs

    def _create_job_item(self, job_data: dict, response: Response) -> Optional[JobItem]:
        item = JobItem()
        item["url"] = job_data["url"]
        item["reference"] = job_data["reference"]
        item["title"] = job_data["title"]
        item["location"] = job_data["location"]
        item["department"] = job_data["category"]
        item["lab"] = ""
        item["contract_label"] = ""
        item["contract_type"] = self.cfg.employment_types[0] if self.cfg.employment_types else ""
        item["published_ago"] = ""
        item["start_date"] = ""
        item["is_new"] = "false"
        
        return item

    def _handle_pagination_failure(self, response: Response, page: int):
        self._session_failures += 1
        if self._session_failures >= self._max_session_failures:
            self.logger.warning(
                f"Session failure #{self._session_failures} — restarting from page 1"
            )
            self._session_failures = 0
            yield scrapy.Request(
                url=self._build_search_url(1),
                callback=self.parse_listing,
                cb_kwargs={"page": 1},
                dont_filter=True,
            )
        elif page > 1:
            self.logger.info(
                f"Empty page {page}, attempt {self._session_failures}/{self._max_session_failures}"
            )

    def parse_detail(self, response: Response) -> Generator[DetailItem, None, None]:
        self.stats["detail_pages"] += 1

        item = DetailItem()
        item["url"] = response.url

        match = re.search(r"/(\d+)/?$", response.url)
        item["reference"] = match.group(1) if match else ""

        title = response.css("h1::text").get("")
        if not title:
            title = response.css("div.headline h1::text, div.job-header h1::text").get("")
        item["title"] = title.strip() if title else ""

        location = response.css("div.location span::text, div.location::text, span.location::text").getall()
        if location:
            item["location"] = " ".join([loc.strip() for loc in location if loc.strip()])
        else:
            loc_match = re.search(r'Location:</strong>\s*([^<]+)', response.text)
            item["location"] = loc_match.group(1).strip() if loc_match else ""

        item["lab"] = ""

        category = response.css("div.category span::text, div.category::text").get("")
        if not category:
            cat_match = re.search(r'Category:</strong>\s*([^<]+)', response.text)
            category = cat_match.group(1).strip() if cat_match else ""
        item["department"] = category

        job_type = response.css("span.job-type::text, div.job-type::text").get("")
        if not job_type:
            type_match = re.search(r'Job Type:</strong>\s*([^<]+)', response.text)
            job_type = type_match.group(1).strip() if type_match else ""
        item["contract_label"] = job_type
        item["contract_type"] = job_type

        desc_section = response.css("div.content, div.jobdescription, div.description, div.job-details, section.description")
        if desc_section:
            item["description"] = desc_section.get("").strip()
        else:
            desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', response.text, re.DOTALL)
            item["description"] = desc_match.group(1).strip() if desc_match else ""

        item["missions"] = ""
        item["activities"] = ""
        item["profile"] = ""
        item["work_environment"] = ""

        item["salary"] = ""
        deadline_match = re.search(r'(?:Closing|date).*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', response.text, re.IGNORECASE)
        item["deadline"] = deadline_match.group(1) if deadline_match else ""
        
        item["start_date"] = ""
        item["work_time"] = ""
        item["activity_sector"] = ""
        item["job_type"] = ""
        item["disability_access"] = ""
        item["published_ago"] = ""
        item["is_new"] = "false"

        yield item

    def closed(self, reason):
        s = self.stats
        self.logger.info(
            f"\n{'─'*52}\n"
            f"  Crawl done : {reason}\n"
            f"  Items found: {s['total']}\n"
            f"  Detail pages: {s['detail_pages']}\n"
            f"{'─'*52}"
        )

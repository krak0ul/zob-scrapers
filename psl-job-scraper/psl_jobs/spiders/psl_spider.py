"""
psl_spider.py

Scrapes recrutement.psl.eu/nos-offres using GET parameters.
Supports filtering by keywords, contract type (profil), and establishment.

Features:
- GET-based search with query parameters
- Pagination via ?page=N
- Detail page scraping for full job descriptions
- Configurable via YAML or CLI args

Usage:
  scrapy crawl psl_jobs -a config=psl_filter.yml
  scrapy crawl psl_jobs -a keywords="machine learning"
  scrapy crawl psl_jobs -a contract_types=fiche_academique
"""

import re
from typing import Generator, Optional

import scrapy
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor

from psl_jobs.items import JobItem, DetailItem
from psl_jobs.filters import FilterConfig, JobFilter, AdvancedFilterConfig
from psl_jobs.contract_types import CONTRACT_TYPE_MAP, ETABLISSEMENT_MAP

SEARCH_URL = "https://recrutement.psl.eu/nos-offres"


_DETAIL_LINK_EXTRACTOR = LinkExtractor(
    allow=r"^https://recrutement\.psl\.eu/[^/]+$",
    restrict_css="div.offre_row",
)


class PslSpider(scrapy.Spider):
    name = "psl_jobs"
    allowed_domains = ["recrutement.psl.eu"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cfg = FilterConfig.from_yaml(kwargs["config"]) if kwargs.get("config") else FilterConfig()
        cli = FilterConfig.from_cli(kwargs)
        if cli.keywords:       cfg.keywords       = cli.keywords
        if cli.locations:      cfg.locations      = cli.locations
        if cli.contract_types: cfg.contract_types = cli.contract_types
        if "keyword_mode" in kwargs: cfg.keyword_mode = kwargs["keyword_mode"]

        adv_cfg = AdvancedFilterConfig.from_kwargs(kwargs)

        self.filter = JobFilter(cfg)
        self.cfg = cfg
        self.adv_cfg = adv_cfg
        self._log_filters(cfg, adv_cfg)

        self.stats = {"total": 0, "detail_pages": 0}
        self._session_failures = 0
        self._max_session_failures = 3

    def _log_filters(self, cfg: FilterConfig, adv_cfg: AdvancedFilterConfig):
        if cfg.is_empty() and adv_cfg.is_empty():
            self.logger.info("No filters — scraping all offers")
            return
        self.logger.info("Active filters (server-side):")
        if cfg.keywords:
            self.logger.info(f"  keywords ({cfg.keyword_mode}): {cfg.keywords}")
        if cfg.contract_types:
            labels = [CONTRACT_TYPE_MAP.get(c, c) for c in cfg.contract_types]
            self.logger.info(f"  contract_types: {cfg.contract_types} → {labels}")
        if not adv_cfg.is_empty():
            etab_labels = [ETABLISSEMENT_MAP.get(e, e) for e in adv_cfg.etablissements]
            self.logger.info(f"  etablissements: {adv_cfg.etablissements} → {etab_labels}")
        if cfg.locations:
            self.logger.info(f"  locations: {cfg.locations} (client-side only - no server param)")

    def start_requests(self):
        yield scrapy.Request(
            url=self._build_search_url(0),
            callback=self.parse_listing,
            dont_filter=True,
        )

    def _build_search_url(self, page: int = 0) -> str:
        params = [("page", str(page))]

        if self.cfg.keywords:
            params.append(("keys", " ".join(self.cfg.keywords)))

        for ct in self.cfg.contract_types:
            params.append((f"type[{ct}]", ct))

        if self.adv_cfg.etablissements:
            for etab in self.adv_cfg.etablissements:
                params.append((f"etablissement[{etab}]", etab))

        query_string = "&".join(f"{k}={v}" for k, v in params)
        return f"{SEARCH_URL}?{query_string}"

    def parse_listing(self, response: Response, page: int = 0):
        rows = response.css("div.views-row")
        if not rows:
            self.logger.info(f"No rows on page {page} — checking for session issues")
            self._handle_pagination_failure(response, page)
            return

        self._session_failures = 0
        self.logger.info(f"Page {page}: {len(rows)} rows")

        for row in rows:
            card = row.css("div.offre_row")
            if not card:
                continue

            item = self._parse_card(card, response)
            if not item:
                continue

            self.stats["total"] += 1

            if self.cfg.locations:
                location = item.get("location", "")
                if not any(loc.lower() in location.lower() for loc in self.cfg.locations):
                    self.logger.debug(f"✗ {item.get('reference','?')}  location not matched")
                    continue

            self.logger.debug(f"✓ {item['reference']}  {item['title'][:55]}")
            yield item

        for link in _DETAIL_LINK_EXTRACTOR.extract_links(response):
            yield response.follow(link.url, callback=self.parse_detail)

        next_link = response.css("li.pager__item--next a::attr(href)").get()
        if next_link:
            match = re.search(r"page=(\d+)", next_link)
            if match:
                next_page = int(match.group(1))
                yield scrapy.Request(
                    url=self._build_search_url(next_page),
                    callback=self.parse_listing,
                    cb_kwargs={"page": next_page},
                    dont_filter=True,
                )

    def _handle_pagination_failure(self, response: Response, page: int):
        self._session_failures += 1
        if self._session_failures >= self._max_session_failures:
            self.logger.warning(
                f"Session failure #{self._session_failures} — restarting from page 0"
            )
            self._session_failures = 0
            yield scrapy.Request(
                url=self._build_search_url(0),
                callback=self.parse_listing,
                dont_filter=True,
            )
        elif page > 0:
            self.logger.info(
                f"Empty page {page}, attempt {self._session_failures}/{self._max_session_failures}"
            )

    def _parse_card(self, card, response: Response) -> Optional[JobItem]:
        link = card.css("a")
        href = link.css("::attr(href)").get("")
        if not href:
            return None

        item = JobItem()
        item["url"] = response.urljoin(href)

        title = link.css("div.title::text").get("")
        item["title"] = title.strip() if title else ""

        etab = link.css("div.title_etablissement::text").get("")
        item["lab"] = etab.strip() if etab else ""

        profil = link.css("div.profil::text").get("")
        item["contract_label"] = profil.strip() if profil else ""

        date_el = link.css("div.date::text").get()
        if date_el:
            item["start_date"] = date_el.strip()

        created_el = link.css("div.created::text").get()
        if created_el:
            item["published_ago"] = created_el.strip()

        match = re.search(r"/([^/]+)$", href)
        item["reference"] = match.group(1) if match else ""

        if self.cfg.contract_types:
            item["contract_type"] = self.cfg.contract_types[0]
        else:
            item["contract_type"] = ""

        return item

    def parse_detail(self, response: Response) -> Generator[DetailItem, None, None]:
        self.stats["detail_pages"] += 1

        item = DetailItem()

        item["url"] = response.url

        match = re.search(r"/([^/]+)$", response.url)
        item["reference"] = match.group(1) if match else ""

        title = response.css("div.head_visuel h1 span::text").get("")
        item["title"] = title.strip() if title else ""

        item["lab"] = self._extract_lab(response)

        location = response.css("div.etablisment div.adress").get("")
        parts = [p.strip() for p in location.split(",") if p.strip()]
        item["location"] = ", ".join(parts[:2]) if parts else ""

        item["contract_label"] = self._extract_profil(response)

        start_date = response.css("div.create_post div.date::text").get("")
        item["start_date"] = start_date.strip() if start_date else ""

        item["description"] = self._extract_description(response)

        item["missions"] = self._extract_section(response, "div.missions")
        item["activities"] = self._extract_section(response, "div.savoirs")
        item["profile"] = self._extract_profile(response)

        item["work_environment"] = self._extract_section(response, "div.desc")

        contract_type = response.css("div.infos_supplementer div.contrat_poste span::text").getall()
        item["contract_type"] = contract_type[1] if len(contract_type) > 1 else ""

        duration = response.css("div.infos_supplementer div.duree span::text").getall()
        item["duration"] = duration[1] if len(duration) > 1 else ""

        item["deadline"] = self._extract_deadline(response)

        published = response.css("div.create_date::text").get("")
        item["published_ago"] = published.strip() if published else ""

        yield item

    def _extract_lab(self, response: Response) -> str:
        logo_link = response.css("div.information a.etablissement_element img::attr(alt)").get("")
        return logo_link.strip() if logo_link else ""

    def _extract_profil(self, response: Response) -> str:
        if "fiche-administrative" in response.url:
            return "Administratif/Technique/Bibliothèque"
        elif "fiche-academique" in response.url:
            return "Enseignement & Recherche"

        profil = response.css("div.content_offre div.information div.desc p::text").get("")
        return profil.strip() if profil else ""

    def _extract_description(self, response: Response) -> str:
        sections = []
        desc = response.css("div.content_offre div.desc").get("")
        if desc:
            sections.append(desc)
        missions = response.css("div.missions").get("")
        if missions:
            sections.append(missions)
        return " ".join(sections)

    def _extract_section(self, response: Response, section_selector: str) -> str:
        section = response.css(section_selector)
        if not section:
            return ""
        content = section.css("div.elements").get("")
        return content.strip() if content else ""

    def _extract_profile(self, response: Response) -> str:
        profile = response.css("div.savoirs div.elements").get("")
        return profile.strip() if profile else ""

    def _extract_deadline(self, response: Response) -> str:
        deadline = response.css("div.information div.create_post div.date::text").get("")
        return deadline.strip() if deadline else ""

    def closed(self, reason):
        s = self.stats
        self.logger.info(
            f"\n{'─'*52}\n"
            f"  Crawl done : {reason}\n"
            f"  Items found: {s['total']}\n"
            f"  Detail pages: {s['detail_pages']}\n"
            f"{'─'*52}"
        )
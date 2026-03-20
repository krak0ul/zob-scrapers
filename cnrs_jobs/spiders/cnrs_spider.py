"""
cnrs_spider.py

Scrapes emploi.cnrs.fr/Offres/Recherche.aspx using ASPX form submission.
Supports both basic filters (keywords, location, contract type) and advanced
filters (research field, corps, activity, etc.).

Features:
- FormRequest.from_response for robust form handling
- Advanced filter support via hidden ASPX fields
- Session recovery on timeouts
- Detail page scraping for full job descriptions
- Configurable via YAML or CLI args

Usage:
  scrapy crawl cnrs_jobs -a config=cnrs_filter.yml
  scrapy crawl cnrs_jobs -a keywords="machine learning" -a locations="Paris"
  scrapy crawl cnrs_jobs -a config=cnrs_filter.yml -a research_field=Informatique
"""

import re
from typing import Generator, Optional

import scrapy
from scrapy import FormRequest, Request
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor

from cnrs_jobs.items import JobItem, DetailItem
from cnrs_jobs.filters import FilterConfig, JobFilter, AdvancedFilterConfig
from cnrs_jobs.contract_types import CONTRACT_TYPE_MAP

SEARCH_URL = "https://emploi.cnrs.fr/Offres/Recherche.aspx"

_URL_TO_CODE = {
    "/CDD/":       "ITCDD",
    "/CDDM/":      "ITCDDM",
    "/CDI/":       "ITCDI",
    "/CDIM/":      "ITCDIM",
    "/Doctorant/": "DOCTOR",
    "/MOBINT/":    "FILDELEAU",
    "/Emploi/":    "CPJ",
    "/Stage/":     "STAG",
    "/Apprent/":   "APPR",
}

_DETAIL_LINK_EXTRACTOR = LinkExtractor(
    allow=r"/Offres/[^/]+/[^/]+/Default\.aspx$",
    restrict_css="#CphMain_UlResultOffer",
)


def _code_from_url(url: str) -> str:
    for seg, code in _URL_TO_CODE.items():
        if seg in url:
            return code
    return ""


class CnrsSpider(scrapy.Spider):
    name = "cnrs_jobs"
    allowed_domains = ["emploi.cnrs.fr"]
    
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

        self.stats = {"total": 0, "matched": 0, "skipped": 0, "detail_pages": 0}
        self._session_failures = 0
        self._max_session_failures = 3

    def _log_filters(self, cfg: FilterConfig, adv_cfg: AdvancedFilterConfig):
        if cfg.is_empty() and adv_cfg.is_empty():
            self.logger.info("No filters — scraping all offers")
            return
        self.logger.info("Active filters:")
        if cfg.keywords:
            self.logger.info(f"  keywords ({cfg.keyword_mode}): {cfg.keywords}")
        if cfg.locations:
            self.logger.info(f"  locations: {cfg.locations}")
        if cfg.contract_types:
            labels = [CONTRACT_TYPE_MAP.get(c, c) for c in cfg.contract_types]
            self.logger.info(f"  contract_types: {cfg.contract_types} → {labels}")
        if not adv_cfg.is_empty():
            self.logger.info(f"  advanced filters: {adv_cfg.to_dict()}")

    def start_requests(self):
        yield scrapy.Request(
            url=SEARCH_URL,
            callback=self._init_form_session,
            dont_filter=True,
        )

    def _init_form_session(self, response: Response):
        yield self._make_search_request(response, page=0)

    def _make_search_request(self, response: Response, page: int) -> FormRequest:
        formdata = {
            "ctl00$CphMain$FormSearch$InputSearchBy": "",
            "ctl00$CphMain$FormSearch$InputLocation": "",
            "Page": str(page),
            "ctl00$CphMain$FormSearch$FiltersResearchField": self.adv_cfg.research_field or "",
            "ctl00$CphMain$FormSearch$FiltersCorps": self.adv_cfg.corps or "",
            "ctl00$CphMain$FormSearch$FiltersActivity": self.adv_cfg.activity or "",
            "ctl00$CphMain$FormSearch$FiltersJob": self.adv_cfg.job_name or "",
            "ctl00$CphMain$FormSearch$FiltersDegree": self.adv_cfg.degree or "",
            "ctl00$CphMain$FormSearch$FiltersExperience": self.adv_cfg.experience or "",
            "ctl00$CphMain$FormSearch$FiltersDuration": self.adv_cfg.duration or "",
            "ctl00$CphMain$FormSearch$FiltersQuotity": self.adv_cfg.quotity or "",
        }

        if self.cfg.keywords and self.cfg.keyword_mode == "any" and len(self.cfg.keywords) == 1:
            formdata["ctl00$CphMain$FormSearch$InputSearchBy"] = self.cfg.keywords[0]
        if self.cfg.locations and len(self.cfg.locations) == 1:
            formdata["ctl00$CphMain$FormSearch$InputLocation"] = self.cfg.locations[0]

        pairs = list(formdata.items())
        for code in self.cfg.contract_types:
            pairs.append(("ContractType", code))

        if self.cfg.is_researcher_only:
            pairs.append(("ctl00$CphMain$FormSearch$ChxIsResearcher", "on"))

        return FormRequest.from_response(
            response,
            formid="SearchForm",
            formdata=pairs,
            callback=self._parse_listing,
            cb_kwargs={"page": page},
            dont_filter=True,
        )

    def _parse_listing(self, response: Response, page: int):
        cards = response.css("div.card.card-shadow")
        if not cards:
            self.logger.info(f"No cards on page {page} — checking for session issues")
            self._handle_pagination_failure(response, page)
            return

        self._session_failures = 0
        self.logger.info(f"Page {page}: {len(cards)} cards")

        for card in cards:
            item = self._parse_card(card, response)
            if not item:
                continue

            self.stats["total"] += 1
            matched, reasons = self.filter.match(dict(item))

            if matched:
                self.stats["matched"] += 1
                item["match_reasons"] = ", ".join(reasons)
                self.logger.debug(f"✓ {item['reference']}  {item['title'][:55]}")
                yield item
            else:
                self.stats["skipped"] += 1
                self.logger.debug(f"✗ {item.get('reference','?')}  {item.get('title','')[:55]}")

        for link in _DETAIL_LINK_EXTRACTOR.extract_links(response):
            yield response.follow(link.url, callback=self.parse_detail)

        has_next = response.css("li.next a").attrib.get("onclick")
        if has_next:
            yield self._make_search_request(response, page=page + 1)

    def _handle_pagination_failure(self, response: Response, page: int):
        self._session_failures += 1
        if self._session_failures >= self._max_session_failures:
            self.logger.warning(
                f"Session failure #{self._session_failures} — restarting from page 0"
            )
            self._session_failures = 0
            yield scrapy.Request(
                url=SEARCH_URL,
                callback=self._init_form_session,
                dont_filter=True,
            )
        elif page > 0:
            self.logger.info(
                f"Empty page {page}, attempt {self._session_failures}/{self._max_session_failures}"
            )

    def _parse_card(self, card, response: Response) -> Optional[JobItem]:
        href = card.css("h3.h5 a::attr(href)").get("")
        if not href:
            return None

        item = JobItem()
        item["url"] = response.urljoin(href)
        item["title"] = card.css("h3.h5 a::text").get("").strip()
        item["is_new"] = bool(card.css("p.tag span").get())
        item["published_ago"] = card.css("p.maj::text").get("").strip()

        meta_paras = card.css("div.meta p")
        item["lab"] = meta_paras[0].css("strong::text").get("").strip() if meta_paras else ""

        location_raw = meta_paras[1].css("::text").get("").strip() if len(meta_paras) > 1 else ""
        parts = [p.strip() for p in location_raw.split("•")]
        item["location"]   = parts[0] if parts else ""
        item["department"] = parts[1] if len(parts) > 1 else ""

        labels = card.css("ul.list-unstyled li.label span::text").getall()
        labels = [l.strip() for l in labels if l.strip()]
        item["contract_label"] = labels[0] if len(labels) > 0 else ""
        item["duration"]       = labels[1] if len(labels) > 1 else ""
        item["degree"]         = labels[2] if len(labels) > 2 else ""

        item["contract_type"] = _code_from_url(href)

        m = re.search(r"/Offres/[^/]+/([^/]+)/Default\.aspx", href)
        item["reference"] = m.group(1) if m else ""

        return item

    def parse_detail(self, response: Response) -> Generator[DetailItem, None, None]:
        self.stats["detail_pages"] += 1

        item = DetailItem()

        item["url"] = response.url

        m = re.search(r"/Offres/[^/]+/([^/]+)/Default\.aspx", response.url)
        item["reference"] = m.group(1) if m else ""

        item["title"] = response.css("h1::text").get("").strip()
        item["lab"] = response.css("header.post-header div.meta strong::text").get("").strip()

        location_raw = response.css("header.post-header div.meta p::text").get("").strip()
        parts = [p.strip() for p in location_raw.split("•")]
        item["location"] = parts[0] if parts else ""
        item["department"] = parts[1] if len(parts) > 1 else ""

        item["contract_label"] = response.css(
            "header.post-header ul.list-inline li.label span::text"
        ).get("").strip()

        desc_section = response.css("#CphMain_FullOfferDisplay_Description")
        item["description"] = desc_section.get("").strip() if desc_section else ""

        item["missions"] = self._extract_section(desc_section, "Mission")
        item["activities"] = self._extract_section(desc_section, "Activité")
        item["profile"] = self._extract_section(desc_section, "Profil")
        item["work_environment"] = self._extract_section(desc_section, "Environnement")

        item["salary"] = self._extract_card_dark_value(response, "Rémun")
        item["deadline"] = self._extract_deadline(response)
        item["start_date"] = self._extract_card_dark_value(response, "Date d")
        item["work_time"] = self._extract_card_dark_value(response, "Temps de Travail")
        item["activity_sector"] = self._extract_table_value(response, "Secteur")
        item["job_type"] = self._extract_table_value(response, "Emploi type")

        disability_msg = response.xpath('//*[contains(@class, "message")][contains(text(), "handicap")]')
        item["disability_access"] = bool(disability_msg)

        yield item

    def _extract_section(self, section, heading: str) -> str:
        if not section:
            return ""
        headings = section.xpath(
            f'.//*[self::h3[contains(@class, "h4")] or self::h2]'
            f'[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{heading.lower()}")]'
        )
        for h in headings:
            text = h.xpath("string()").get("").lower()
            if heading.lower() in text:
                siblings = h.xpath("following-sibling::*")
                paragraphs = []
                for sibling in siblings:
                    if sibling.css("h2, h3.h4"):
                        break
                    p_text = sibling.xpath("string()").get("").strip()
                    if p_text:
                        paragraphs.append(p_text)
                return " ".join(paragraphs)
        return ""

    def _extract_card_dark_value(self, response: Response, label: str) -> str:
        value = response.xpath(
            f'//div[contains(@class, "card-dark")]'
            f'//h3[contains(., "{label}")]/following-sibling::p[1]//text()'
        ).get("")
        return value.strip()

    def _extract_table_value(self, response: Response, label: str) -> str:
        row = response.xpath(
            f'//table[contains(@class, "table")]'
            f'//tr[th[contains(text(), "{label}")]]/td//text()'
        ).get("")
        return row.strip()

    def _extract_deadline(self, response: Response) -> str:
        icon_elem = response.xpath('//span[contains(@class, "fa-exclamation-circle")]')
        if icon_elem:
            container = icon_elem.xpath("ancestor::span[1]")
            if container:
                return container.xpath("string()").get("").strip()
        return ""

    def closed(self, reason):
        s = self.stats
        self.logger.info(
            f"\n{'─'*52}\n"
            f"  Crawl done : {reason}\n"
            f"  Cards seen : {s['total']}\n"
            f"  Matched    : {s['matched']}\n"
            f"  Skipped    : {s['skipped']}\n"
            f"  Detail pages: {s['detail_pages']}\n"
            f"{'─'*52}"
        )

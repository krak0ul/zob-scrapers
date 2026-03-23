"""
cea_spider.py

Scrapes www.emploi.cea.fr for job listings.
Supports basic filters (keywords, location, contract type).

Features:
- ASPX form submission for server-side filtering
- Multiple form submissions for multiple locations
- Simple URL-based pagination
- Listing card parsing
- Detail page scraping for full job descriptions
- Configurable via YAML or CLI args

Usage:
  scrapy crawl cea_jobs -a config=cea_filter.yml
  scrapy crawl cea_jobs -a keywords="machine learning" -a locations="Paris"
"""

import re
from typing import Generator, Optional

import scrapy
from scrapy.http import Response, FormRequest
from scrapy.linkextractors import LinkExtractor

from cea_jobs.items import JobItem, DetailItem
from cea_jobs.filters import FilterConfig, JobFilter
from cea_jobs.contract_types import CONTRACT_TYPE_MAP, LOCATION_ID_TO_NAME

SEARCH_URL = "https://www.emploi.cea.fr/offre-de-emploi/liste-offres.aspx"

_DETAIL_LINK_EXTRACTOR = LinkExtractor(
    allow=r"/offre-de-emploi/[^/]+_\d+\.aspx$",
)


def _extract_reference(url: str) -> str:
    m = re.search(r"_(\d+)\.aspx", url)
    return m.group(1) if m else ""


def _extract_contract_type(contract_label: str) -> str:
    label_upper = contract_label.upper()
    for name in CONTRACT_TYPE_MAP:
        if name.upper() in label_upper:
            return name
    return contract_label


class CeaSpider(scrapy.Spider):
    name = "cea_jobs"
    allowed_domains = ["emploi.cea.fr"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cfg = FilterConfig.from_yaml(kwargs["config"]) if kwargs.get("config") else FilterConfig()
        cli = FilterConfig.from_cli(kwargs)
        if cli.keywords:       cfg.keywords       = cli.keywords
        if cli.locations:      cfg.locations      = cli.locations
        if cli.contract_types: cfg.contract_types = cli.contract_types
        if "keyword_mode" in kwargs: cfg.keyword_mode = kwargs["keyword_mode"]

        self.cfg = cfg
        self.filter = JobFilter(cfg, server_side_location=bool(cfg.location_ids))
        self._log_filters(cfg)

        self.stats = {"total": 0, "matched": 0, "detail_pages": 0}
        self._first_search_done = False
        self.requested_pages = set()

    def _log_filters(self, cfg: FilterConfig):
        if cfg.is_empty():
            self.logger.info("No filters — scraping all offers")
            return
        self.logger.info("Active filters:")
        if cfg.keywords:
            self.logger.info(f"  keywords ({cfg.keyword_mode}): {cfg.keywords}")
        if cfg.locations:
            loc_ids = cfg.location_ids
            loc_names = [LOCATION_ID_TO_NAME.get(id, str(id)) for id in loc_ids]
            self.logger.info(f"  locations (server-side): {loc_names}")
        if cfg.contract_types:
            self.logger.info(f"  contract_types: {cfg.contract_types}")

    def start_requests(self):
        yield scrapy.Request(
            url=SEARCH_URL,
            callback=self._parse_form_page,
            dont_filter=True,
        )

    def _parse_form_page(self, response: Response):
        location_ids = self.cfg.location_ids

        if not location_ids:
            yield from self._submit_search_form(response)
        else:
            for loc_id in location_ids:
                self.logger.info(f"Submitting search for location: {LOCATION_ID_TO_NAME.get(loc_id, loc_id)}")
                yield from self._submit_search_form(response, location_id=loc_id)

    def _submit_search_form(self, response: Response, location_id: Optional[int] = None):
        vs = response.css("input[name=__VIEWSTATE]::attr(value)").get("")
        vsg = response.css("input[name=__VIEWSTATEGENERATOR]::attr(value)").get("")
        ev = response.css("input[name=__EVENTVALIDATION]::attr(value)").get("")

        formdata = {
            "__VIEWSTATE": vs,
            "__VIEWSTATEGENERATOR": vsg,
            "__EVENTVALIDATION": ev,
            "ctl00$ctl00$moteurRapideOffre$ctl00$OfferCriteria_Keywords": "",
            "ctl00$ctl00$moteurRapideOffre$ctl00$EngineCriteriaCollection$Contract": "0",
            "ctl00$ctl00$moteurRapideOffre$ctl01$OfferCriteria$Location$GeographicalAreaCollection": "0",
            "ctl00$ctl00$moteurRapideOffre$ctl01$OfferCriteria$PrimaryProfile": "0",
            "ctl00$ctl00$moteurRapideOffre$ctl02$EngineCriteriaCollection$ApplicantCriteria$CustomCodeTableValue3": "0",
            "ctl00$ctl00$moteurRapideOffre$BT_recherche": "Lancer ma Recherche",
        }

        if self.cfg.keywords:
            formdata["ctl00$ctl00$moteurRapideOffre$ctl00$OfferCriteria_Keywords"] = ", ".join(self.cfg.keywords)

        if location_id:
            formdata["ctl00$ctl00$moteurRapideOffre$ctl01$OfferCriteria$Location$GeographicalAreaCollection"] = str(location_id)

        if self.cfg.contract_types:
            for ct_name, ct_id in CONTRACT_TYPE_MAP.items():
                if ct_name in self.cfg.contract_types:
                    formdata["ctl00$ctl00$moteurRapideOffre$ctl00$EngineCriteriaCollection$Contract"] = str(ct_id)
                    break

        yield FormRequest(
            url=SEARCH_URL,
            formdata=formdata,
            callback=self._parse_listing,
            cb_kwargs={"page": 1, "location_id": location_id},
            dont_filter=True,
            meta={"dont_cache": True},
        )

    def _get_match_reasons(self) -> str:
        reasons = []
        if self.cfg.keywords:
            reasons.append(f"kw:{','.join(self.cfg.keywords)}")
        if self.cfg.locations:
            loc_names = [LOCATION_ID_TO_NAME.get(id, str(id)) for id in self.cfg.location_ids]
            reasons.append(f"location:{','.join(loc_names)}")
        if self.cfg.contract_types:
            reasons.append(f"contract:{','.join(self.cfg.contract_types)}")
        return ", ".join(reasons) if reasons else "no filters"

    def _parse_listing(self, response: Response, page: int, location_id: Optional[int] = None):
        cards = response.css("div.ts-offer-card.Layer")
        if not cards:
            loc_name = LOCATION_ID_TO_NAME.get(location_id, location_id) if location_id else "all"
            self.logger.info(f"No cards on page {page} (location: {loc_name})")
            return

        self.logger.info(f"Page {page}: {len(cards)} cards")

        for card in cards:
            item = self._parse_card(card, response)
            if not item:
                continue

            self.stats["total"] += 1
            self.stats["matched"] += 1
            item["match_reasons"] = self._get_match_reasons()
            self.logger.debug(f"✓ {item['reference']}  {item['title'][:55]}")
            yield item

        for link in _DETAIL_LINK_EXTRACTOR.extract_links(response):
            yield response.follow(link.url, callback=self.parse_detail)

        page_numbers = response.css("a.ts-ol-pagination-list-item__link[href*=page]::attr(href)").re(r"page=(\d+)")

        for page_num_str in page_numbers:
            next_page_num = int(page_num_str)
            if next_page_num > page and next_page_num not in self.requested_pages:
                self.requested_pages.add(f"page_{next_page_num}_{location_id}")
                yield self._make_pagination_request(next_page_num, location_id)

    def _make_pagination_request(self, page_num: int, location_id: Optional[int] = None):
        params = [f"page={page_num}", "LCID=1036"]

        if self.cfg.keywords:
            params.append(f"Keywords={','.join(self.cfg.keywords)}")

        if location_id:
            params.append(f"JobGeographicalArea={location_id}")

        if self.cfg.contract_types:
            for ct_name, ct_id in CONTRACT_TYPE_MAP.items():
                if ct_name in self.cfg.contract_types:
                    params.append(f"Contract={ct_id}")
                    break

        url = f"{SEARCH_URL}?{'&'.join(params)}"

        if url in self.requested_pages:
            return None
        self.requested_pages.add(url)

        return scrapy.Request(
            url=url,
            callback=self._parse_listing,
            cb_kwargs={"page": page_num, "location_id": location_id},
            dont_filter=True,
        )

    def _parse_card(self, card, response: Response) -> Optional[JobItem]:
        link = card.css("h3.ts-offer-card__title a")
        href = link.css("::attr(href)").get("")
        if not href:
            return None

        item = JobItem()
        item["url"] = response.urljoin(href)
        item["title"] = link.css("::text").get("").strip()
        item["reference"] = _extract_reference(href)

        ref_from_data = card.css("span.ts-offer-card__favorite-link::attr(data-reference)").get()
        if ref_from_data:
            item["reference"] = ref_from_data

        details = card.css("ul.ts-offer-card-content__list li::text").getall()
        details = [d.strip() for d in details if d.strip()]

        for d in details:
            if d.startswith("Réf. :"):
                item["reference"] = d.replace("Réf. :", "").strip()
            elif d in CONTRACT_TYPE_MAP:
                item["contract_label"] = d
                item["contract_type"] = _extract_contract_type(d)
            elif "(" in d and ")" in d:
                item["department"] = d.strip()
            elif d not in ["Réf. :"]:
                if not item.get("location"):
                    item["location"] = d.strip()

        item.setdefault("contract_label", "")
        item.setdefault("contract_type", "")
        item.setdefault("location", "")
        item.setdefault("department", "")

        return item

    def parse_detail(self, response: Response) -> Generator[DetailItem, None, None]:
        self.stats["detail_pages"] += 1

        item = DetailItem()

        item["url"] = response.url
        item["reference"] = _extract_reference(response.url)

        item["title"] = response.css("h1.ts-offer-page__title span::text").get("").strip()
        if not item["title"]:
            item["title"] = response.css("h1 span::text").get("").strip()
        if not item["title"]:
            item["title"] = response.css("h1::text").get("").strip()

        desc_div = response.css("div.description-offre")
        if desc_div:
            item["description"] = desc_div.get("")
        else:
            item["description"] = response.css("#CphMain_FullOfferDisplay_Description").get("")

        item["missions"] = self._extract_section(response, "Description de l'offre")
        item["profile"] = self._extract_section(response, "Profil du candidat")

        item["lab"] = self._extract_section(response, "Description de l'unité")
        if not item["lab"]:
            item["lab"] = response.xpath(
                '//*[contains(text(), "Entité de rattachement")]/following-sibling::div[1]//text()'
            ).get("").strip()

        labels = response.css("ul.list-inline li::text").getall()
        for label in labels:
            label = label.strip()
            if label in CONTRACT_TYPE_MAP:
                item["contract_label"] = label
                item["contract_type"] = _extract_contract_type(label)
                break

        location_parts = response.css("div.fiche-offre-infos p::text").getall()
        location_text = " ".join([p.strip() for p in location_parts])
        
        site_match = re.search(r"Site\s*([^\n]+)", location_text)
        if site_match:
            item["location"] = site_match.group(1).strip()

        dept_match = re.search(r"France,\s*([^,]+)", location_text)
        if dept_match:
            item["department"] = dept_match.group(1).strip()

        location = response.css("div.fiche-offre-infos p::text").getall()
        if not item.get("location"):
            for loc in location:
                loc = loc.strip()
                if loc and loc not in ["France,"]:
                    item["location"] = loc
                    break

        duration = response.xpath(
            '//*[contains(text(), "Durée du contrat")]/following-sibling::p[1]//text()'
        ).get("")
        item["duration"] = duration.strip() if duration else ""

        start_date = response.xpath(
            '//*[contains(text(), "Disponibilité")]/following-sibling::p[1]//text()'
        ).get("")
        item["start_date"] = start_date.strip() if start_date else ""

        item["deadline"] = ""
        item["work_time"] = ""
        item["activity_sector"] = ""
        item["job_type"] = ""
        item["disability_access"] = False
        item["work_environment"] = ""
        item["salary"] = ""

        yield item

    def _extract_section(self, response: Response, heading: str) -> str:
        heading_elem = response.xpath(
            f'//h3[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{heading.lower()}")]'
        )
        if not heading_elem:
            heading_elem = response.xpath(
                f'//h2[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{heading.lower()}")]'
            )
        if not heading_elem:
            heading_elem = response.xpath(
                f'//*[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{heading.lower()}")]'
            )
        if not heading_elem:
            return ""

        siblings = heading_elem.xpath("following-sibling::*")
        paragraphs = []
        for sibling in siblings:
            if sibling.css("h2, h3, h4"):
                break
            p_text = sibling.xpath("string()").get("").strip()
            if p_text:
                paragraphs.append(p_text)
        return " ".join(paragraphs)

    def closed(self, reason):
        s = self.stats
        self.logger.info(
            f"\n{'─'*52}\n"
            f"  Crawl done : {reason}\n"
            f"  Cards seen : {s['total']}\n"
            f"  Detail pages: {s['detail_pages']}\n"
            f"{'─'*52}"
        )

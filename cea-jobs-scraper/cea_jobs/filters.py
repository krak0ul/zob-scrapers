"""
filters.py — Keyword & criteria matching engine

FilterConfig holds basic search criteria (keywords, locations, contract types).
JobFilter.match(item) returns (matched: bool, reasons: list[str]).

Basic criteria:
  keywords       searched in: title, lab, contract_label
  locations      matched against item["location"] (city, case-insensitive)
  location_ids   list of location IDs for server-side filtering
  contract_types matched against item["contract_type" or "contract_label"]
  keyword_mode   "any" (OR) | "all" (AND) across the keyword list
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional

from cea_jobs.contract_types import LOCATION_MAP


CONTRACT_TYPE_GROUPS = {
    "CDI": ["CDI"],
    "CDD": ["CDD"],
    "Alternance": ["Alternance"],
    "Stage": ["Stage"],
    "Post-Doctorat": ["Post-Doctorat"],
    "CDI_CDD": ["CDI", "CDD"],
    "ALL": ["CDI", "CDD", "Alternance", "Stage", "Post-Doctorat"],
}


def _expand_groups(types: List[str]) -> List[str]:
    result = []
    for t in types:
        result.extend(CONTRACT_TYPE_GROUPS.get(t, [t]))
    return list(dict.fromkeys(result))


def _location_to_id(location_name: str) -> Optional[int]:
    normalized = location_name.strip()
    if normalized.isdigit():
        return int(normalized)
    for name, loc_id in LOCATION_MAP.items():
        if name.lower() == normalized.lower():
            return loc_id
        if normalized.lower() in name.lower():
            return loc_id
    return None


def _expand_locations(location_names: List[str]) -> List[int]:
    result = []
    for name in location_names:
        loc_id = _location_to_id(name)
        if loc_id is not None:
            result.append(loc_id)
    return result


@dataclass
class FilterConfig:
    keywords:       List[str] = field(default_factory=list)
    locations:      List[str] = field(default_factory=list)
    contract_types: List[str] = field(default_factory=list)
    keyword_mode:   str = "any"

    @property
    def location_ids(self) -> List[int]:
        return _expand_locations(self.locations)

    @classmethod
    def from_yaml(cls, path: str) -> "FilterConfig":
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        f = data.get("filters", data)
        raw_types = [str(v) for v in (f.get("contract_types") or [])]
        return cls(
            keywords=        [str(v) for v in (f.get("keywords") or [])],
            locations=       [str(v) for v in (f.get("locations") or [])],
            contract_types=  _expand_groups(raw_types),
            keyword_mode=    str(f.get("keyword_mode", "any")).lower(),
        )

    @classmethod
    def from_cli(cls, spider_args: dict) -> "FilterConfig":
        def _split(val: str) -> List[str]:
            return [v.strip() for v in val.split(",") if v.strip()]
        raw_types = _split(spider_args.get("contract_types", ""))
        return cls(
            keywords=        _split(spider_args.get("keywords", "")),
            locations=       _split(spider_args.get("locations", "")),
            contract_types=  _expand_groups(raw_types),
            keyword_mode=    spider_args.get("keyword_mode", "any").lower(),
        )

    def is_empty(self) -> bool:
        return not any([self.keywords, self.locations, self.contract_types])


class JobFilter:
    def __init__(self, config: FilterConfig, server_side_location: bool = False):
        self.cfg = config
        self.server_side_location = server_side_location
        self._kw_patterns = [
            re.compile(re.escape(kw), re.IGNORECASE)
            for kw in config.keywords
        ]

    def match(self, item: dict) -> tuple[bool, list[str]]:
        if self.cfg.is_empty():
            return True, ["no filters"]

        reasons: list[str] = []

        if self._kw_patterns:
            ok, kw_reasons = self._match_keywords(item)
            if not ok:
                return False, []
            reasons.extend(kw_reasons)

        if self.cfg.locations and not self.server_side_location:
            city = item.get("location", "")
            if not any(loc.lower() in city.lower() for loc in self.cfg.locations):
                return False, []
            reasons.append(f"location:{city}")

        if self.cfg.contract_types:
            ct = item.get("contract_type", "")
            cl = item.get("contract_label", "")
            ct_match = ct.upper() if ct else ""
            cl_match = cl.upper() if cl else ""
            if not any(code.upper() in (ct_match, cl_match) for code in self.cfg.contract_types):
                return False, []
            reasons.append(f"contract:{cl_match or ct_match}")

        return True, reasons

    def _haystack(self, item: dict) -> str:
        return " ".join(filter(None, [
            item.get("title", ""),
            item.get("lab", ""),
            item.get("contract_label", ""),
        ]))

    def _match_keywords(self, item: dict) -> tuple[bool, list[str]]:
        haystack = self._haystack(item)
        matched = [p.pattern for p in self._kw_patterns if p.search(haystack)]
        if self.cfg.keyword_mode == "all":
            ok = len(matched) == len(self._kw_patterns)
        else:
            ok = len(matched) > 0
        return ok, [f"kw:{k}" for k in matched]

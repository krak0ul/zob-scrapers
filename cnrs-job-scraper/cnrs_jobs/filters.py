"""
filters.py — Keyword & criteria matching engine

FilterConfig holds basic search criteria (keywords, locations, contract types).
AdvancedFilterConfig holds advanced ASPX form filter values.
JobFilter.match(item) returns (matched: bool, reasons: list[str]).

Basic criteria:
  keywords       searched in: title, lab, contract_label
  locations      matched against item["location"] (city, case-insensitive)
  contract_types matched against item["contract_type"] (form values e.g. ITCDD)
  keyword_mode   "any" (OR) | "all" (AND) across the keyword list

Advanced criteria (ASPX hidden fields):
  research_field  FiltersResearchField
  corps          FiltersCorps
  activity       FiltersActivity
  job_name       FiltersJob
  degree         FiltersDegree
  experience     FiltersExperience
  duration       FiltersDuration
  quotity        FiltersQuotity

All non-empty groups use AND between them.
Within a group (locations, contract_types) the logic is always OR.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional

from cnrs_jobs.contract_types import CONTRACT_GROUPS


@dataclass
class FilterConfig:
    keywords:       List[str] = field(default_factory=list)
    locations:      List[str] = field(default_factory=list)
    contract_types: List[str] = field(default_factory=list)
    keyword_mode:   str = "any"
    is_researcher_only: bool = False

    @classmethod
    def from_yaml(cls, path: str) -> "FilterConfig":
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        f = data.get("filters", data)
        raw_types = [str(v) for v in (f.get("contract_types") or [])]
        return cls(
            keywords=           [str(v) for v in (f.get("keywords") or [])],
            locations=          [str(v) for v in (f.get("locations") or [])],
            contract_types=     cls._expand_groups(raw_types),
            keyword_mode=       str(f.get("keyword_mode", "any")).lower(),
            is_researcher_only= bool(f.get("researcher_only", False)),
        )

    @classmethod
    def from_cli(cls, spider_args: dict) -> "FilterConfig":
        def _split(val: str) -> List[str]:
            return [v.strip() for v in val.split(",") if v.strip()]
        raw_types = _split(spider_args.get("contract_types", ""))
        return cls(
            keywords=           _split(spider_args.get("keywords", "")),
            locations=          _split(spider_args.get("locations", "")),
            contract_types=     cls._expand_groups(raw_types),
            keyword_mode=       spider_args.get("keyword_mode", "any").lower(),
            is_researcher_only= spider_args.get("researcher_only", "").lower() == "true",
        )

    @staticmethod
    def _expand_groups(values: List[str]) -> List[str]:
        out = []
        for v in values:
            if v in CONTRACT_GROUPS:
                out.extend(CONTRACT_GROUPS[v])
            else:
                out.append(v.upper())
        return list(dict.fromkeys(out))

    def is_empty(self) -> bool:
        return not any([
            self.keywords, self.locations, self.contract_types,
            self.is_researcher_only
        ])


@dataclass
class AdvancedFilterConfig:
    research_field: Optional[str] = None
    corps:          Optional[str] = None
    activity:       Optional[str] = None
    job_name:       Optional[str] = None
    degree:         Optional[str] = None
    experience:     Optional[str] = None
    duration:       Optional[str] = None
    quotity:        Optional[str] = None

    @classmethod
    def from_yaml(cls, path: str) -> "AdvancedFilterConfig":
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        f = data.get("advanced_filters", data)
        return cls(
            research_field= f.get("research_field"),
            corps=          f.get("corps"),
            activity=       f.get("activity"),
            job_name=       f.get("job_name"),
            degree=         f.get("degree"),
            experience=     f.get("experience"),
            duration=       f.get("duration"),
            quotity=        f.get("quotity"),
        )

    @classmethod
    def from_kwargs(cls, kwargs: dict) -> "AdvancedFilterConfig":
        return cls(
            research_field= kwargs.get("research_field"),
            corps=          kwargs.get("corps"),
            activity=       kwargs.get("activity"),
            job_name=       kwargs.get("job_name"),
            degree=         kwargs.get("degree"),
            experience=     kwargs.get("experience"),
            duration=       kwargs.get("duration"),
            quotity=        kwargs.get("quotity"),
        )

    def is_empty(self) -> bool:
        return all([
            not self.research_field,
            not self.corps,
            not self.activity,
            not self.job_name,
            not self.degree,
            not self.experience,
            not self.duration,
            not self.quotity,
        ])

    def to_dict(self) -> dict:
        return {
            k: v for k, v in {
                "research_field": self.research_field,
                "corps": self.corps,
                "activity": self.activity,
                "job_name": self.job_name,
                "degree": self.degree,
                "experience": self.experience,
                "duration": self.duration,
                "quotity": self.quotity,
            }.items() if v
        }


class JobFilter:
    def __init__(self, config: FilterConfig):
        self.cfg = config
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

        if self.cfg.locations:
            city = item.get("location", "")
            if not any(loc.lower() in city.lower() for loc in self.cfg.locations):
                return False, []
            reasons.append(f"location:{city}")

        if self.cfg.contract_types:
            ct = item.get("contract_type", "")
            if not any(code.upper() == ct.upper() for code in self.cfg.contract_types):
                return False, []
            reasons.append(f"contract:{ct}")

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

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional

from sanofi_jobs.contract_types import CONTRACT_GROUPS


@dataclass
class FilterConfig:
    keywords:       List[str] = field(default_factory=list)
    locations:      List[str] = field(default_factory=list)
    countries:      List[str] = field(default_factory=list)
    regions:        List[str] = field(default_factory=list)
    job_families:   List[str] = field(default_factory=list)
    employment_types: List[str] = field(default_factory=list)
    keyword_mode:   str = "any"

    @classmethod
    def from_yaml(cls, path: str) -> "FilterConfig":
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        f = data.get("filters", data)
        raw_types = [str(v) for v in (f.get("employment_types") or [])]
        return cls(
            keywords=         [str(v) for v in (f.get("keywords") or [])],
            locations=        [str(v) for v in (f.get("locations") or [])],
            countries=        [str(v) for v in (f.get("countries") or [])],
            regions=          [str(v) for v in (f.get("regions") or [])],
            job_families=     [str(v) for v in (f.get("job_families") or [])],
            employment_types= cls._expand_groups(raw_types),
            keyword_mode=    str(f.get("keyword_mode", "any")).lower(),
        )

    @classmethod
    def from_cli(cls, spider_args: dict) -> "FilterConfig":
        def _split(val: str) -> List[str]:
            return [v.strip() for v in val.split(",") if v.strip()]
        raw_types = _split(spider_args.get("employment_types", ""))
        return cls(
            keywords=         _split(spider_args.get("keywords", "")),
            locations=        _split(spider_args.get("locations", "")),
            countries=        _split(spider_args.get("countries", "")),
            regions=          _split(spider_args.get("regions", "")),
            job_families=     _split(spider_args.get("job_families", "")),
            employment_types= cls._expand_groups(raw_types),
            keyword_mode=    spider_args.get("keyword_mode", "any").lower(),
        )

    @staticmethod
    def _expand_groups(values: List[str]) -> List[str]:
        out = []
        for v in values:
            if v in CONTRACT_GROUPS:
                out.extend(CONTRACT_GROUPS[v])
            else:
                out.append(v)
        return list(dict.fromkeys(out))

    def is_empty(self) -> bool:
        return not any([
            self.keywords, self.locations, self.countries, self.regions,
            self.job_families, self.employment_types
        ])


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

        if self.cfg.countries:
            country = item.get("country", "")
            if not country:
                location = item.get("location", "")
                if "," in location:
                    country = location.split(",")[-1].strip()
            if not any(c.lower() in country.lower() for c in self.cfg.countries):
                return False, []
            reasons.append(f"country:{country}")

        if self.cfg.regions:
            region = item.get("region", "")
            if not any(r.lower() in region.lower() for r in self.cfg.regions):
                return False, []
            reasons.append(f"region:{region}")

        if self.cfg.locations:
            location = item.get("location", "")
            if not any(loc.lower() in location.lower() for loc in self.cfg.locations):
                return False, []
            reasons.append(f"location:{location}")

        if self.cfg.job_families:
            job_family = item.get("job_family", "")
            if not any(jf.lower() in job_family.lower() for jf in self.cfg.job_families):
                return False, []
            reasons.append(f"job_family:{job_family}")

        if self.cfg.employment_types:
            emp_type = item.get("employment_type", "")
            if not any(et.lower() in emp_type.lower() for et in self.cfg.employment_types):
                return False, []
            reasons.append(f"employment_type:{emp_type}")

        return True, reasons

    def _haystack(self, item: dict) -> str:
        return " ".join(filter(None, [
            item.get("title", ""),
            item.get("lab", ""),
            item.get("contract_label", ""),
            item.get("job_family", ""),
        ]))

    def _match_keywords(self, item: dict) -> tuple[bool, list[str]]:
        haystack = self._haystack(item)
        matched = [p.pattern for p in self._kw_patterns if p.search(haystack)]
        if self.cfg.keyword_mode == "all":
            ok = len(matched) == len(self._kw_patterns)
        else:
            ok = len(matched) > 0
        return ok, [f"kw:{k}" for k in matched]

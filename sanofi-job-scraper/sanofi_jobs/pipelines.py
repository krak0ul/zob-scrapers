import csv
import json
import os
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

OUTPUT_DIR = "output"
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")

JOB_FIELDS = [
    "reference", "title", "contract_type", "contract_label",
    "location", "department", "lab",
    "duration", "degree", "is_new", "published_ago",
    "match_reasons", "url",
]

DETAIL_FIELDS = [
    "url", "reference", "title", "lab", "location", "department",
    "contract_label", "description", "missions", "activities",
    "profile", "work_environment", "salary", "deadline", "start_date",
    "work_time", "activity_sector", "job_type", "disability_access",
]


def _ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


class DuplicateFilterPipeline:
    def open_spider(self, spider):
        self.seen_jobs = set()
        self.seen_details = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get("url", "")
        is_detail = adapter.get("description") is not None

        if is_detail:
            if url in self.seen_details:
                raise DropItem(f"Duplicate detail: {url}")
            self.seen_details.add(url)
            self.seen_jobs.discard(url)
        else:
            if url in self.seen_details:
                raise DropItem(f"Listing duplicate (detail exists): {url}")
            if url in self.seen_jobs:
                raise DropItem(f"Duplicate listing: {url}")
            self.seen_jobs.add(url)

        return item


class CsvExportPipeline:
    def open_spider(self, spider):
        _ensure_dir()
        self.job_path = os.path.join(OUTPUT_DIR, f"sanofi_jobs_{TIMESTAMP}.csv")
        self.detail_path = os.path.join(OUTPUT_DIR, f"sanofi_detail_{TIMESTAMP}.csv")
        
        self.job_file = open(self.job_path, "w", newline="", encoding="utf-8")
        self.job_writer = csv.DictWriter(self.job_file, fieldnames=JOB_FIELDS, extrasaction="ignore")
        self.job_writer.writeheader()
        
        self.detail_file = open(self.detail_path, "w", newline="", encoding="utf-8")
        self.detail_writer = csv.DictWriter(self.detail_file, fieldnames=DETAIL_FIELDS, extrasaction="ignore")
        self.detail_writer.writeheader()
        
        spider.logger.info(f"CSV  → {self.job_path} (jobs), {self.detail_path} (details)")

    def close_spider(self, spider):
        self.job_file.close()
        self.detail_file.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        item_dict = adapter.asdict()
        
        if "description" in item_dict:
            self.detail_writer.writerow(item_dict)
        else:
            self.job_writer.writerow(item_dict)
        return item


class JsonExportPipeline:
    def open_spider(self, spider):
        _ensure_dir()
        self.job_path = os.path.join(OUTPUT_DIR, f"sanofi_jobs_{TIMESTAMP}.jsonl")
        self.detail_path = os.path.join(OUTPUT_DIR, f"sanofi_detail_{TIMESTAMP}.jsonl")
        
        self.job_file = open(self.job_path, "w", encoding="utf-8")
        self.detail_file = open(self.detail_path, "w", encoding="utf-8")
        
        spider.logger.info(f"JSONL → {self.job_path} (jobs), {self.detail_path} (details)")

    def close_spider(self, spider):
        self.job_file.close()
        self.detail_file.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        item_dict = adapter.asdict()
        
        if "description" in item_dict:
            self.detail_file.write(json.dumps(item_dict, ensure_ascii=False) + "\n")
        else:
            self.job_file.write(json.dumps(item_dict, ensure_ascii=False) + "\n")
        return item

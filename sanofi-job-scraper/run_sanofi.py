#!/usr/bin/env python3
"""Run Sanofi Job Scraper"""
import sys
import argparse

os_env = __import__('os')
os_env.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'sanofi_jobs.settings')

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def main():
    parser = argparse.ArgumentParser(description='Run Sanofi Job Scraper')
    parser.add_argument('-k', '--keywords', help='Comma-separated keywords')
    parser.add_argument('-c', '--config', help='Path to filter YAML config')
    parser.add_argument('-l', '--limit', type=int, help='Limit number of items')
    args = parser.parse_args()
    
    settings = get_project_settings()
    settings.setmodule('sanofi_jobs.settings')
    
    if args.limit:
        settings.set('CLOSESPIDER_ITEMCOUNT', args.limit)
    
    kwargs = {}
    if args.config:
        kwargs['config'] = args.config
    if args.keywords:
        kwargs['keywords'] = args.keywords
    
    process = CrawlerProcess(settings)
    process.crawl('sanofi_jobs', **kwargs)
    process.start()


if __name__ == '__main__':
    main()

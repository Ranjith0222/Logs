"""Log scraping, filtering, and extract builder utilities."""

__version__ = "0.2.0"

from logs.extract import ExtractBuilder, ExtractSpec, format_extract
from logs.scraper import LogEntry, format_entries, scrape_logs

__all__ = [
    "ExtractBuilder",
    "ExtractSpec",
    "LogEntry",
    "format_entries",
    "format_extract",
    "scrape_logs",
]

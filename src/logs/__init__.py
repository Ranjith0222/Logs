"""Log scraping, filtering, and extract builder utilities."""

__version__ = "0.3.0"

from logs.extract import ExtractBuilder, ExtractSpec, format_extract, format_ruleset_extract
from logs.ruleset import RulesetLogExtract, extract_rulesets
from logs.scraper import LogEntry, format_entries, scrape_logs

__all__ = [
    "ExtractBuilder",
    "ExtractSpec",
    "LogEntry",
    "RulesetLogExtract",
    "extract_rulesets",
    "format_entries",
    "format_extract",
    "format_ruleset_extract",
    "scrape_logs",
]

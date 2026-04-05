from __future__ import annotations

from app.scrapers.search_api import SerpApiGoogleJobsScraper


class IndeedScraper(SerpApiGoogleJobsScraper):
    source_name = "indeed"
    _source_domains = ("indeed.com",)

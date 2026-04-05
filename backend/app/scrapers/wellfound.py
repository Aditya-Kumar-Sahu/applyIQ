from __future__ import annotations

from app.scrapers.search_api import SerpApiGoogleJobsScraper


class WellfoundScraper(SerpApiGoogleJobsScraper):
    source_name = "wellfound"
    _source_domains = ("wellfound.com", "angel.co")

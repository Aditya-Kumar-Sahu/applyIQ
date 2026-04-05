from __future__ import annotations

from app.scrapers.search_api import SerpApiGoogleJobsScraper


class SerpApiJobsScraper(SerpApiGoogleJobsScraper):
    source_name = "serpapi"

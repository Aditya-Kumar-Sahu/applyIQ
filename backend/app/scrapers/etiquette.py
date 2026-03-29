import asyncio
import random
from typing import Any, Callable
import structlog
import httpx
from urllib.robotparser import RobotFileParser

logger = structlog.get_logger(__name__)


class EtiquettePolicy:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.rp = RobotFileParser()
        self.rp.set_url(f"{base_url}/robots.txt")
        self._robots_loaded = False
        
    async def load_robots(self) -> None:
        if self._robots_loaded:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self.rp.url)
                if resp.status_code == 200:
                    self.rp.parse(resp.text.splitlines())
        except Exception as e:
            logger.warning("etiquette.robots.fetch_failed", error=str(e), url=self.rp.url)
        self._robots_loaded = True

    async def can_fetch(self, user_agent: str, url: str) -> bool:
        await self.load_robots()
        return self.rp.can_fetch(user_agent, url)


class TolerantAsyncClient(httpx.AsyncClient):
    """Client with backoff, limits, and random human-like headers."""
    def __init__(self, base_url: str, *args, **kwargs):
        self.policy = EtiquettePolicy(base_url)
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        kwargs["headers"] = headers
        super().__init__(*args, base_url=base_url, **kwargs)

    async def get_with_etiquette(self, url: str, *args, **kwargs):
        user_agent = self.headers.get("User-Agent", "*")
        if not await self.policy.can_fetch(user_agent, url):
            logger.warning("etiquette.robots.blocked", url=url)
            raise ValueError(f"Blocked by robots.txt for {url}")
            
        retries = kwargs.pop("retries", 3)
        backoff_factor = kwargs.pop("backoff_factor", 1.5)
        last_resp: httpx.Response | None = None
        
        for attempt in range(retries):
            try:
                # Add humanized random delay before request
                await asyncio.sleep(random.uniform(0.5, 2.0))
                resp = await self.get(url, *args, **kwargs)
                last_resp = resp
                if resp.status_code == 429:
                    logger.warning("etiquette.rate_limited", attempt=attempt, url=url)
                    retry_after_header = resp.headers.get("Retry-After")
                    if attempt == retries - 1:
                        raise httpx.HTTPStatusError(
                            f"Retries exhausted after rate limit: status={resp.status_code}, Retry-After={retry_after_header}, url={url}",
                            request=resp.request,
                            response=resp,
                        )
                    retry_after = int(retry_after_header or 2 ** attempt)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(backoff_factor ** attempt)

        # Defensive guard for retry configurations such as retries=0.
        if last_resp is not None:
            raise httpx.HTTPStatusError(
                f"Request failed without success after retries: status={last_resp.status_code}, Retry-After={last_resp.headers.get('Retry-After')}, url={url}",
                request=last_resp.request,
                response=last_resp,
            )
        raise RuntimeError(f"Request failed without attempts: status=None, Retry-After=None, url={url}")

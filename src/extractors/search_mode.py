thonimport logging
from typing import Any, Dict, List, Optional

import requests

from utils.parser import parse_search_items
from utils.rate_limit import RateLimiter

LOGGER = logging.getLogger("rednote.search")

class SearchModeExtractor:
    """
    Extracts posts from Xiaohongshu based on a keyword search.
    """

    def __init__(self, settings: Dict[str, Any], rate_limiter: RateLimiter) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter

        search_cfg = settings.get("search", {})
        self.base_url: str = search_cfg.get(
            "baseUrl",
            "https://www.xiaohongshu.com/web_api/sns/v1/search/notes",
        )
        self.page_size: int = int(search_cfg.get("pageSize", 20))
        self.timeout: int = int(search_cfg.get("timeoutSeconds", 10))

        headers = settings.get("http", {}).get("headers", {})
        self.session = requests.Session()
        self.session.headers.update(headers)

    def run(self, keyword: str, max_items: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page = 1

        LOGGER.info("Starting search for keyword=%r max_items=%d", keyword, max_items)

        while len(results) < max_items:
            self.rate_limiter.wait()

            params = {
                "keyword": keyword,
                "page": page,
                "page_size": self.page_size,
            }

            try:
                resp = self.session.get(
                    self.base_url, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                LOGGER.error("HTTP error during search (page=%d): %s", page, exc)
                break

            if not resp.ok:
                LOGGER.warning(
                    "Non-OK status from search API (status=%s, page=%d)",
                    resp.status_code,
                    page,
                )
                break

            try:
                payload = resp.json()
            except ValueError:
                LOGGER.error("Failed to decode JSON from search response (page=%d)", page)
                break

            items = parse_search_items(payload, keyword)
            if not items:
                LOGGER.info("No more items returned from API; stopping at page=%d", page)
                break

            for item in items:
                results.append(item)
                if len(results) >= max_items:
                    break

            LOGGER.debug("Collected %d/%d items so far", len(results), max_items)
            page += 1

        LOGGER.info("Search completed. Total items collected: %d", len(results))
        return results
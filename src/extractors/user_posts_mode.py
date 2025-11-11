thonimport logging
from typing import Any, Dict, List

import requests

from utils.parser import parse_user_posts
from utils.rate_limit import RateLimiter

LOGGER = logging.getLogger("rednote.user_posts")

class UserPostsModeExtractor:
    """
    Extracts posts for given user IDs.
    """

    def __init__(self, settings: Dict[str, Any], rate_limiter: RateLimiter) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter

        posts_cfg = settings.get("userPosts", {})
        self.base_url: str = posts_cfg.get(
            "baseUrl",
            "https://www.xiaohongshu.com/web_api/sns/v1/user/posts",
        )
        self.page_size: int = int(posts_cfg.get("pageSize", 20))
        self.timeout: int = int(posts_cfg.get("timeoutSeconds", 10))

        headers = settings.get("http", {}).get("headers", {})
        self.session = requests.Session()
        self.session.headers.update(headers)

    def _fetch_posts_for_user(
        self, user_id: str, max_items: int
    ) -> List[Dict[str, Any]]:
        posts: List[Dict[str, Any]] = []
        page = 1

        LOGGER.info("Fetching posts for user_id=%s", user_id)

        while len(posts) < max_items:
            self.rate_limiter.wait()

            params = {
                "user_id": user_id,
                "page": page,
                "page_size": self.page_size,
            }

            try:
                resp = self.session.get(
                    self.base_url, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                LOGGER.error(
                    "HTTP error during user posts fetch for user_id=%s page=%d: %s",
                    user_id,
                    page,
                    exc,
                )
                break

            if not resp.ok:
                LOGGER.warning(
                    "Non-OK status from user posts API (status=%s, user_id=%s, page=%d)",
                    resp.status_code,
                    user_id,
                    page,
                )
                break

            try:
                payload = resp.json()
            except ValueError:
                LOGGER.error(
                    "Failed to decode JSON from user posts response (user_id=%s, page=%d)",
                    user_id,
                    page,
                )
                break

            items = parse_user_posts(payload, user_id)
            if not items:
                LOGGER.info(
                    "No more posts returned from API for user_id=%s at page=%d",
                    user_id,
                    page,
                )
                break

            for item in items:
                posts.append(item)
                if len(posts) >= max_items:
                    break

            LOGGER.debug(
                "Collected %d/%d posts for user_id=%s",
                len(posts),
                max_items,
                user_id,
            )
            page += 1

        return posts

    def run(self, user_ids: List[str], max_items: int) -> List[Dict[str, Any]]:
        all_posts: List[Dict[str, Any]] = []
        per_user_limit = max_items

        for user_id in user_ids:
            user_posts = self._fetch_posts_for_user(user_id, per_user_limit)
            all_posts.extend(user_posts)

        LOGGER.info(
            "User posts scraping completed. Total posts collected across %d users: %d",
            len(user_ids),
            len(all_posts),
        )
        return all_posts
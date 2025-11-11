thonimport logging
from typing import Any, Dict, List

import requests

from utils.parser import parse_profile
from utils.rate_limit import RateLimiter

LOGGER = logging.getLogger("rednote.profile")

class ProfileModeExtractor:
    """
    Extracts user profile details including follower counts and engagement metrics.
    """

    def __init__(self, settings: Dict[str, Any], rate_limiter: RateLimiter) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter

        profile_cfg = settings.get("profile", {})
        self.base_url: str = profile_cfg.get(
            "baseUrl",
            "https://www.xiaohongshu.com/web_api/sns/v3/user/detail",
        )
        self.timeout: int = int(profile_cfg.get("timeoutSeconds", 10))

        headers = settings.get("http", {}).get("headers", {})
        self.session = requests.Session()
        self.session.headers.update(headers)

    def _fetch_profile(self, user_id: str) -> Dict[str, Any]:
        self.rate_limiter.wait()
        params = {"user_id": user_id}

        try:
            resp = self.session.get(self.base_url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            LOGGER.error("HTTP error during profile fetch for user_id=%s: %s", user_id, exc)
            return {}

        if not resp.ok:
            LOGGER.warning(
                "Non-OK status from profile API (status=%s, user_id=%s)",
                resp.status_code,
                user_id,
            )
            return {}

        try:
            payload = resp.json()
        except ValueError:
            LOGGER.error("Failed to decode JSON from profile response (user_id=%s)", user_id)
            return {}

        return parse_profile(payload, user_id)

    def run(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        profiles: List[Dict[str, Any]] = []

        for user_id in user_ids:
            LOGGER.info("Fetching profile for user_id=%s", user_id)
            profile = self._fetch_profile(user_id)
            if profile:
                profiles.append(profile)

        LOGGER.info("Profile scraping completed. Profiles collected: %d", len(profiles))
        return profiles
thonimport logging
from typing import Any, Dict, List

import requests

from utils.parser import parse_comment_items
from utils.rate_limit import RateLimiter

LOGGER = logging.getLogger("rednote.comment")

class CommentModeExtractor:
    """
    Extracts comments (including replies where available) for a list of note IDs.
    """

    def __init__(self, settings: Dict[str, Any], rate_limiter: RateLimiter) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter

        comment_cfg = settings.get("comment", {})
        self.base_url: str = comment_cfg.get(
            "baseUrl",
            "https://www.xiaohongshu.com/web_api/sns/v5/note/comments",
        )
        self.page_size: int = int(comment_cfg.get("pageSize", 20))
        self.timeout: int = int(comment_cfg.get("timeoutSeconds", 10))

        headers = settings.get("http", {}).get("headers", {})
        self.session = requests.Session()
        self.session.headers.update(headers)

    def _fetch_comments_for_note(
        self, note_id: str, max_items: int
    ) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        page = 1

        LOGGER.info("Fetching comments for note_id=%s", note_id)

        while len(comments) < max_items:
            self.rate_limiter.wait()

            params = {"note_id": note_id, "page": page, "page_size": self.page_size}

            try:
                resp = self.session.get(
                    self.base_url, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                LOGGER.error(
                    "HTTP error during comment fetch for note_id=%s page=%d: %s",
                    note_id,
                    page,
                    exc,
                )
                break

            if not resp.ok:
                LOGGER.warning(
                    "Non-OK status from comment API (status=%s, note_id=%s, page=%d)",
                    resp.status_code,
                    note_id,
                    page,
                )
                break

            try:
                payload = resp.json()
            except ValueError:
                LOGGER.error(
                    "Failed to decode JSON from comment response (note_id=%s, page=%d)",
                    note_id,
                    page,
                )
                break

            items = parse_comment_items(payload, note_id)
            if not items:
                LOGGER.info(
                    "No more comments returned from API for note_id=%s at page=%d",
                    note_id,
                    page,
                )
                break

            for item in items:
                comments.append(item)
                if len(comments) >= max_items:
                    break

            LOGGER.debug(
                "Collected %d/%d comments for note_id=%s",
                len(comments),
                max_items,
                note_id,
            )
            page += 1

        return comments

    def run(self, note_ids: List[str], max_items: int) -> List[Dict[str, Any]]:
        all_comments: List[Dict[str, Any]] = []
        per_note_limit = max_items

        for note_id in note_ids:
            note_comments = self._fetch_comments_for_note(note_id, per_note_limit)
            all_comments.extend(note_comments)

        LOGGER.info(
            "Comment scraping completed. Total comments collected across %d notes: %d",
            len(note_ids),
            len(all_comments),
        )
        return all_comments
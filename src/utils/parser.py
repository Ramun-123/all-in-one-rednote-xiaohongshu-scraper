thonimport datetime as _dt
from typing import Any, Dict, List, Optional

def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _safe_get(dct: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    cur: Any = dct
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur

def parse_search_items(payload: Dict[str, Any], keyword: str) -> List[Dict[str, Any]]:
    """
    Normalize search API response into the common note structure.
    """
    data = payload.get("data") or payload
    items = data.get("items") or data.get("notes") or []

    normalized: List[Dict[str, Any]] = []

    for raw in items:
        item_id = _safe_get(raw, ["id"]) or _safe_get(raw, ["note_id"]) or ""
        note_card = raw.get("note_card") or raw.get("noteCard") or {}
        user = note_card.get("user") or raw.get("user") or {}

        display_title = note_card.get("display_title") or note_card.get("title") or ""
        interact_info = note_card.get("interact_info") or note_card.get("interactInfo") or {}
        cover = note_card.get("cover") or {}

        liked_count = interact_info.get("liked_count") or interact_info.get("likeCount") or 0
        cover_url = (
            cover.get("url_default")
            or cover.get("url")
            or cover.get("thumbUrl")
            or ""
        )

        link = f"https://www.xiaohongshu.com/explore/{item_id}" if item_id else ""

        normalized.append(
            {
                "keyword": keyword,
                "item": {
                    "id": item_id,
                    "note_card": {
                        "display_title": display_title,
                        "user": {
                            "nickname": user.get("nickname") or user.get("name") or "",
                            "user_id": user.get("user_id") or user.get("id") or "",
                        },
                        "interact_info": {
                            "liked_count": str(liked_count),
                        },
                        "cover": {
                            "url_default": cover_url,
                        },
                    },
                },
                "link": link,
                "scrapedAt": _now_iso(),
            }
        )

    return normalized

def parse_comment_items(payload: Dict[str, Any], note_id: str) -> List[Dict[str, Any]]:
    """
    Normalize comment API response for a specific note.
    """
    data = payload.get("data") or payload
    comments = data.get("comments") or data.get("items") or []

    normalized: List[Dict[str, Any]] = []

    for raw in comments:
        content = raw.get("content") or raw.get("text") or ""
        like_count = raw.get("like_count") or raw.get("likes") or 0

        normalized.append(
            {
                "noteId": note_id,
                "comment": {
                    "content": content,
                    "like_count": like_count,
                },
                "scrapedAt": _now_iso(),
            }
        )

        # Nested replies, if present
        replies = raw.get("replies") or raw.get("subComments") or []
        for reply in replies:
            r_content = reply.get("content") or reply.get("text") or ""
            r_like_count = reply.get("like_count") or reply.get("likes") or 0

            normalized.append(
                {
                    "noteId": note_id,
                    "comment": {
                        "content": r_content,
                        "like_count": r_like_count,
                    },
                    "scrapedAt": _now_iso(),
                }
            )

    return normalized

def parse_profile(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Normalize user profile API response.
    """
    data = payload.get("data") or payload

    basic_info = data.get("basicInfo") or data.get("basic_info") or {}
    interactions = data.get("interactions") or data.get("stats") or {}

    nickname = basic_info.get("nickname") or basic_info.get("name") or ""
    followers = (
        interactions.get("followers")
        or interactions.get("fans")
        or interactions.get("followerCount")
        or 0
    )
    likes = (
        interactions.get("likes")
        or interactions.get("liked")
        or interactions.get("likeCount")
        or 0
    )
    posts = (
        interactions.get("posts")
        or interactions.get("notes")
        or interactions.get("noteCount")
        or 0
    )

    return {
        "userId": user_id,
        "profileData": {
            "basicInfo": {"nickname": nickname},
            "interactions": {
                "followers": followers,
                "likes": likes,
                "posts": posts,
            },
        },
        "scrapedAt": _now_iso(),
    }

def parse_user_posts(payload: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
    """
    Normalize 'user posts' API response for a specific user.
    """
    data = payload.get("data") or payload
    posts = data.get("items") or data.get("notes") or []

    normalized: List[Dict[str, Any]] = []

    for raw in posts:
        note_id = raw.get("id") or raw.get("note_id") or ""
        link = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""

        normalized.append(
            {
                "userId": user_id,
                "postData": {
                    "id": note_id,
                    "postUrl": link,
                },
                "scrapedAt": _now_iso(),
            }
        )

    return normalized
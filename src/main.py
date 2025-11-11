thonimport argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from extractors.search_mode import SearchModeExtractor
from extractors.comment_mode import CommentModeExtractor
from extractors.profile_mode import ProfileModeExtractor
from extractors.user_posts_mode import UserPostsModeExtractor
from output.exporter import JsonExporter
from utils.rate_limit import RateLimiter

LOGGER = logging.getLogger("rednote.main")

def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_settings() -> Dict[str, Any]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(base_dir, "config", "settings.json")
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Settings file not found at {settings_path}")

    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_sample_input() -> Dict[str, Any]:
    # repo root is one level up from src
    base_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(base_dir, ".."))
    sample_path = os.path.join(repo_root, "data", "sample_input.json")
    if not os.path.exists(sample_path):
        raise FileNotFoundError(f"Sample input file not found at {sample_path}")

    with open(sample_path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="All-in-One RedNote (Xiaohongshu) Scraper"
    )
    parser.add_argument(
        "--mode",
        choices=["search", "comment", "profile", "userPosts"],
        help="Scraping mode. If omitted, falls back to data/sample_input.json",
    )
    parser.add_argument("--keyword", help="Keyword for search mode")
    parser.add_argument(
        "--note-id",
        action="append",
        help="Note ID for comment mode. Can be specified multiple times.",
    )
    parser.add_argument(
        "--user-id",
        action="append",
        help="User ID for profile or userPosts mode. Can be specified multiple times.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to scrape (per mode).",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit output file path. If omitted, default from settings is used.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()

def build_rate_limiter(settings: Dict[str, Any]) -> RateLimiter:
    rate_cfg = settings.get("rateLimit", {})
    calls_per_minute = int(rate_cfg.get("callsPerMinute", 30))
    burst = int(rate_cfg.get("burst", 5))
    return RateLimiter(calls_per_minute=calls_per_minute, burst=burst)

def resolve_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if args.mode:
        # CLI-driven config
        cfg: Dict[str, Any] = {
            "mode": args.mode,
        }
        if args.keyword:
            cfg["keyword"] = args.keyword
        if args.note_id:
            cfg["noteIds"] = args.note_id
        if args.user_id:
            cfg["userIds"] = args.user_id
        if args.max_items is not None:
            cfg["maxItems"] = args.max_items
        return cfg

    # Fallback to sample_input.json when mode is not set
    LOGGER.info("No mode provided on CLI. Falling back to data/sample_input.json.")
    return load_sample_input()

def run_search_mode(
    cfg: Dict[str, Any], settings: Dict[str, Any], limiter: RateLimiter
) -> List[Dict[str, Any]]:
    keyword = cfg.get("keyword")
    if not keyword:
        raise ValueError("Search mode requires a 'keyword' in config or CLI.")
    max_items = int(cfg.get("maxItems", settings["search"].get("maxItems", 100)))

    extractor = SearchModeExtractor(settings=settings, rate_limiter=limiter)
    return extractor.run(keyword=keyword, max_items=max_items)

def run_comment_mode(
    cfg: Dict[str, Any], settings: Dict[str, Any], limiter: RateLimiter
) -> List[Dict[str, Any]]:
    note_ids = cfg.get("noteIds") or []
    if not note_ids:
        raise ValueError("Comment mode requires at least one 'noteId' in config or CLI.")
    max_items = int(cfg.get("maxItems", settings["comment"].get("maxItemsPerNote", 200)))

    extractor = CommentModeExtractor(settings=settings, rate_limiter=limiter)
    return extractor.run(note_ids=note_ids, max_items=max_items)

def run_profile_mode(
    cfg: Dict[str, Any], settings: Dict[str, Any], limiter: RateLimiter
) -> List[Dict[str, Any]]:
    user_ids = cfg.get("userIds") or []
    if not user_ids:
        raise ValueError("Profile mode requires at least one 'userId' in config or CLI.")

    extractor = ProfileModeExtractor(settings=settings, rate_limiter=limiter)
    return extractor.run(user_ids=user_ids)

def run_user_posts_mode(
    cfg: Dict[str, Any], settings: Dict[str, Any], limiter: RateLimiter
) -> List[Dict[str, Any]]:
    user_ids = cfg.get("userIds") or []
    if not user_ids:
        raise ValueError(
            "User posts mode requires at least one 'userId' in config or CLI."
        )
    max_items = int(cfg.get("maxItems", settings["userPosts"].get("maxItemsPerUser", 200)))

    extractor = UserPostsModeExtractor(settings=settings, rate_limiter=limiter)
    return extractor.run(user_ids=user_ids, max_items=max_items)

def main() -> None:
    args = parse_args()
    configure_logging(verbose=bool(args.verbose))

    try:
        settings = load_settings()
    except Exception as exc:
        LOGGER.error("Failed to load settings.json: %s", exc)
        sys.exit(1)

    try:
        cfg = resolve_config_from_args(args)
    except Exception as exc:
        LOGGER.error("Failed to load configuration: %s", exc)
        sys.exit(1)

    mode = cfg.get("mode")
    if mode not in {"search", "comment", "profile", "userPosts"}:
        LOGGER.error("Invalid or missing mode in configuration: %r", mode)
        sys.exit(1)

    limiter = build_rate_limiter(settings)
    exporter = JsonExporter(settings=settings)

    try:
        if mode == "search":
            LOGGER.info("Running in SEARCH mode.")
            data = run_search_mode(cfg, settings, limiter)
        elif mode == "comment":
            LOGGER.info("Running in COMMENT mode.")
            data = run_comment_mode(cfg, settings, limiter)
        elif mode == "profile":
            LOGGER.info("Running in PROFILE mode.")
            data = run_profile_mode(cfg, settings, limiter)
        else:
            LOGGER.info("Running in USER POSTS mode.")
            data = run_user_posts_mode(cfg, settings, limiter)
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        LOGGER.exception("Scraping failed: %s", exc)
        sys.exit(1)

    if not data:
        LOGGER.warning("No data was scraped. Exiting without writing output.")
        sys.exit(0)

    try:
        output_path: Optional[str] = args.output
        final_path = exporter.export(data, output_path=output_path)
        LOGGER.info("Scraped %d records. Output written to %s", len(data), final_path)
    except Exception as exc:
        LOGGER.exception("Failed to export data: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()
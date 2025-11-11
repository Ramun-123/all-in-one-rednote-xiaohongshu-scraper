thonimport json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("rednote.exporter")

class JsonExporter:
    """
    Writes scraped items to JSON files.
    """

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.output_cfg = settings.get("output", {})
        self.default_dir = self.output_cfg.get("directory", "data")
        self.prefix = self.output_cfg.get("filenamePrefix", "rednote_output_")

    def _ensure_directory(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _default_output_path(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"{self.prefix}{timestamp}.json"
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        return os.path.join(base_dir, self.default_dir, filename)

    def export(self, data: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
        if not data:
            raise ValueError("No data supplied for export.")

        path = output_path or self._default_output_path()
        self._ensure_directory(path)

        LOGGER.debug("Writing %d records to %s", len(data), path)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return path
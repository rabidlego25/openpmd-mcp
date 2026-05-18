from __future__ import annotations

import re
from pathlib import Path

def _normalize_series(path: Path) -> str:
    """Replace numeric iteration index with %T placeholder."""
    return re.sub(r'_\d+\.', '_%T.', str(path))

def register_discovery_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_find_series(search_dir: str) -> dict:
        """
        Search for openPMD series files under a given directory.
        Returns a deduplicated list of series paths suitable for use
        with openpmd_get_structure and other tools.

        Args:
            search_dir Directory to search recursively for openPMD files.
        """
        base = Path(search_Dir).expanduser().resolve()
        if not base.exists():
            raise ValueError(f"Path does not exist: {base}")

        patterns = ["**/*.bp", "**/*.h5", "**/*.json"]
        found = []
        for pattern in patterns:
            found.extend(base.glob(pattern))

        series = set()
        for f in found:
            series.add(_normalize_series(f))

        return {
            "search_dir": str(base),
            "series": sorted(series),
            "count": len(series)
        }

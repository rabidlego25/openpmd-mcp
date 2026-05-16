from __future__ import annotations

import os
import time
from pathlib import Path

def _run_status(run_path: Path) -> str:
    stderr = run_path / "stderr"
    if not stderr.exists():
        return "unknown"
    text = stderr.read_text(errors="ignore")
    if "error" in text.lower() or "exception" in text.lower():
        return "failed"
    stdout = run_path / "stdout"
    if stdout.exists():
        return "done"
    return "running"

def _count_snapshots(run_path: Path) -> int:
    bp_files = list(run_path.glob("simOutput/openPMD/*.bp"))
    return len(bp_files)

def _dir_size_gb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / 1e9, 2)

def register_run_tools(mcp) -> None:

    @mcp.tool()
    def list_runs(base_path: str) -> dict:
        """
        List all PIConGPU runs under a base directory.
        Returns status, snapshot count, disk size, and modification time
        for each run found.

        Args:
            base_path: Directory containing PIConGPU run folders
        """
        base = Path(base_path).expanduser().resolve()
        if not base.exists():
            raise ValueError(f"PAth does not exist: {base}")

        runs = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            try:
                mtime = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(entry.stat().st_mtime)
                )
                runs.append({
                    "name": entry.name,
                    "path": str(entry),
                    "status": _run_status(entry),
                    "snapshots": _count_snapshots(entry),
                    "size_gb": _dir_size_gb(entry),
                    "modified": mtime,
                })
            except PermissionError:
                continue

        return {"base_path": str(base), "runs": runs}

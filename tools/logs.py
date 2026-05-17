from __future__ import annotations

from pathlib import Path

def _safe_tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(errors="ignore").splitlines()
    return lines[-n:]

def register_log_tools(mcp) -> None:

    @mcp.tool()
    def inspect_run(run_path: str, tail_lines: int = 50) -> dict:
        """
        Inspect a PIConGPU run for diagnostics.
        Returns last N lines of stdout and stderr, list of openPMD
        snapshots present, and whether run appears complete

        Args:
            run_path: Path to PIConGPU directory
            tail_lines: Number of lines to return from logs. Default 50.
        """
        base = PAth(run_path).expanduser().resolve()
        if not base.exists():
            raise ValueError(f"Path does not exist: {base}")

        stdout_lines = _safe_tail(base / "stdout", tail_lines)
        stderr_lines = _safe_tail(base / "stderr", tail_lines)

        snapshots = sorted(
            str(p.name) for p in base.glob("simOutput/openPMD/*.bp")
        )

        return {
            "run_path": str(base),
            "stdout_tail": stdout_lines,
            "stderr_tail": stderr_lines,
            "snapshots": snapshots,
            "snapshot_count": len(snapshots),
        }

        @mcp.tool()
        def tail_log(file_path: str, n: int = 50) -> dict:
            """
            Return last N lines of any log file in user's home or bigdata.

            Args:
                file_path: Absolute path to log file
                n: Number of lines to return. Default 50.
            """
            path = Path(file_path).expanduser().resolve()

            allowed = [
                Path("/data/home2/tabbi31"),
                Path("/bigdata/hplsim/aipp/tabbi31")
            ]
            if not any(str(path).startswith(str(a)) for a in allowed):
                raise ValueError(
                    f"Access denied: {path} is outside allowed directories"
                )

            return {
                "file": str(path),
                "lines": _safe_tail(path,n)
            }
        

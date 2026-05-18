from __future__ import annotations

from pathlib import Path
from typing import Any

import openpmd_api as io

from lib.path_validators import validate_path


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_series_path(series_path: str) -> str:
    p = Path(series_path).expanduser()
    if "%T" in p.name:
        validate_path(p.parent)
        return str(p.parent.resolve() / p.name)
    return str(validate_path(p))


def _safe_attr(obj, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


# ── Tool registration ────────────────────────────────────────────────────────

def register_list_iterations_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_list_iterations(
        series_path: str,
        include_time: bool = True,
        include_summary: bool = True,
    ) -> dict:
        """
        Lightweight iteration listing for an openPMD series.

        Avoids the full structural scan of openpmd_get_structure — only walks
        the iteration index and (optionally) reads each iteration's `time`
        and `dt` attributes.

        Args:
            series_path: Path or %T-template path to the openPMD series.
            include_time: If True, include `time` and `dt` for each iteration.
                          Reads only iteration-level attributes, not field
                          data. Default True.
            include_summary: If True, include first/last iteration, count, and
                             approximate stride (step between consecutive
                             iterations) at the top level. Default True.

        Returns:
            Dict with:
              - series_path:      resolved path
              - n_iterations:     total count
              - iterations:       list of integers, sorted ascending
              - first, last, stride: present if include_summary
              - times:            list of {iteration, time, dt} dicts if
                                  include_time
        """
        path = _resolve_series_path(series_path)
        series = io.Series(path, io.Access.read_only)
        try:
            iter_keys = sorted(series.iterations)
            result: dict[str, Any] = {
                "series_path": path,
                "n_iterations": len(iter_keys),
                "iterations": iter_keys,
            }

            if include_summary and iter_keys:
                first = iter_keys[0]
                last = iter_keys[-1]
                stride: int | None = None
                if len(iter_keys) >= 2:
                    diffs = {iter_keys[i + 1] - iter_keys[i] for i in range(len(iter_keys) - 1)}
                    if len(diffs) == 1:
                        stride = next(iter(diffs))
                    else:
                        stride = None  # non-uniform spacing
                result.update({
                    "first": first,
                    "last": last,
                    "stride": stride,
                })

            if include_time:
                times: list[dict] = []
                for it_index in iter_keys:
                    it = series.iterations[it_index]
                    t = _safe_attr(it, "time", default=None)
                    dt = _safe_attr(it, "dt", default=None)
                    t_unit_SI = _safe_attr(it, "timeUnitSI", default=None)
                    times.append({
                        "iteration": it_index,
                        "time": float(t) if t is not None else None,
                        "dt": float(dt) if dt is not None else None,
                        "timeUnitSI": float(t_unit_SI) if t_unit_SI is not None else None,
                    })
                result["times"] = times

            return result
        finally:
            try:
                series.close()
            except AttributeError:
                del series

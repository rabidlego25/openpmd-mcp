from __future__ import annotations

from pathlib import Path
from typing import Any

import openpmd_api as io

from lib.path_validators import validate_path


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_series_path(series_path: str) -> str:
    """Resolve a path; tolerate %T templates by validating the parent directory."""
    p = Path(series_path).expanduser()
    if "%T" in p.name:
        validate_path(p.parent)
        return str(p.parent.resolve() / p.name)
    return str(validate_path(p))


def _parse_slice(s: str | None, size: int) -> slice:
    """
    Parse a string of the form 'start:stop' or 'start:stop:step' into a slice.
    Empty fields are allowed. None returns a full slice (everything).
    """
    if s is None or s == "":
        return slice(0, size, 1)
    parts = s.split(":")
    if len(parts) > 3:
        raise ValueError(f"Bad slice spec '{s}': expected start:stop[:step]")
    try:
        start = int(parts[0]) if parts[0] else 0
        stop = int(parts[1]) if len(parts) > 1 and parts[1] else size
        step = int(parts[2]) if len(parts) > 2 and parts[2] else 1
    except ValueError as e:
        raise ValueError(f"Bad slice spec '{s}': {e}") from e
    if step == 0:
        raise ValueError("step must be non-zero")
    # Clamp to bounds
    start = max(0, min(start, size))
    stop = max(0, min(stop, size))
    return slice(start, stop, step)


def _array_summary(arr) -> dict:
    """Lightweight stats for a numpy array — kept cheap for large arrays."""
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
    }


# ── Tool registration ────────────────────────────────────────────────────────

def register_read_field_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_read_field(
        series_path: str,
        iteration: int,
        mesh: str,
        component: str,
        slices: list[str] | None = None,
        return_data: bool = False,
        apply_unit_SI: bool = True,
        max_return_elements: int = 100_000,
    ) -> dict:
        """
        Read a single mesh component from an openPMD series at a chosen iteration.

        By default returns shape, dtype, and basic per-array statistics
        (min, max, mean) — cheap and safe even for very large fields.

        Set return_data=True to return the actual values; in that case the
        result is bounded by max_return_elements to keep payloads sane.

        Args:
            series_path: Path or %T-template path to the openPMD series.
            iteration: Iteration number to read.
            mesh: Mesh name, e.g. "E", "B", "J", "rho".
            component: Component name, e.g. "x", "y", "z", or
                       openpmd_api.Mesh_Record_Component.SCALAR for scalars.
            slices: Optional list of "start:stop[:step]" strings, one per
                    spatial dim. Use None for full extent on that axis.
                    Example: ["::2", ":", "32:48"] for stride-2 in x, all of y,
                    z=32..47.
            return_data: If True, include the (possibly sliced) array values
                         in the result. Default False.
            apply_unit_SI: If True, multiply values by the component's unit_SI
                           so returned data is in SI units. Default True.
            max_return_elements: Cap on the number of elements returned when
                                 return_data=True. The tool refuses to return
                                 a larger array; reduce slice or set the cap
                                 higher to override.

        Returns:
            Dict containing:
              - series_path, iteration, mesh, component
              - shape:        list of int, the read region's shape
              - dtype:        string, the array dtype
              - unit_SI:      float, openPMD unit-to-SI scaling for this component
              - stats:        dict with min, max, mean (always included)
              - data:         list (nested) of values, only if return_data=True
        """
        scalar_marker = io.Mesh_Record_Component.SCALAR

        path = _resolve_series_path(series_path)
        series = io.Series(path, io.Access.read_only)
        try:
            if iteration not in series.iterations:
                avail = sorted(series.iterations)
                raise ValueError(
                    f"Iteration {iteration} not in series. "
                    f"Available range: {avail[0] if avail else 'none'} … "
                    f"{avail[-1] if avail else 'none'}"
                )
            it = series.iterations[iteration]

            if mesh not in it.meshes:
                raise ValueError(
                    f"Mesh '{mesh}' not found. "
                    f"Available: {list(it.meshes)}"
                )
            m = it.meshes[mesh]

            # Resolve component (scalar mesh vs vector mesh)
            if component in ("SCALAR", "scalar"):
                comp = m[scalar_marker]
            elif component in m:
                comp = m[component]
            else:
                # Maybe the mesh itself is scalar and the caller passed nothing useful
                try:
                    comp = m[scalar_marker]
                except Exception as e:
                    raise ValueError(
                        f"Component '{component}' not found in mesh '{mesh}'. "
                        f"Available: {list(m)}"
                    ) from e

            full_shape = tuple(comp.shape)
            ndim = len(full_shape)

            # Build slice tuple
            if slices is None:
                slc = tuple(slice(0, s, 1) for s in full_shape)
            else:
                if len(slices) != ndim:
                    raise ValueError(
                        f"slices length {len(slices)} does not match mesh "
                        f"rank {ndim} (shape={full_shape})"
                    )
                slc = tuple(_parse_slice(s, full_shape[d]) for d, s in enumerate(slices))

            # Compute resulting region size
            region_shape = tuple(
                max(0, (s.stop - s.start + (s.step - (1 if s.step > 0 else -1))) // s.step)
                for s in slc
            )
            region_size = 1
            for d in region_shape:
                region_size *= d

            # Load (lazy → chunk → flush)
            data = comp.load_chunk(
                [s.start for s in slc],
                [max(0, s.stop - s.start) for s in slc],
            )
            series.flush()

            # Apply stride if any axis has step != 1 (load_chunk only does contiguous)
            if any(s.step != 1 for s in slc):
                stride = tuple(slice(None, None, s.step) for s in slc)
                data = data[stride]

            # Unit conversion
            unit_SI = float(comp.unit_SI)
            if apply_unit_SI:
                data = data * unit_SI

            result: dict[str, Any] = {
                "series_path": path,
                "iteration": iteration,
                "mesh": mesh,
                "component": component,
                "shape": list(data.shape),
                "dtype": str(data.dtype),
                "unit_SI": unit_SI,
                "stats": _array_summary(data),
            }

            if return_data:
                if data.size > max_return_elements:
                    raise ValueError(
                        f"Refusing to return {data.size} elements "
                        f"(cap={max_return_elements}). Tighten the slice "
                        f"or raise max_return_elements."
                    )
                result["data"] = data.tolist()

            return result
        finally:
            try:
                series.close()
            except AttributeError:
                del series

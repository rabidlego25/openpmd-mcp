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


def _parse_slice(s: str | None, size: int) -> slice:
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
    start = max(0, min(start, size))
    stop = max(0, min(stop, size))
    return slice(start, stop, step)


def _array_summary(arr) -> dict:
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
    }


def _iter_components(record) -> list[str]:
    """List component names in a particle record (handles scalar records too)."""
    comps = list(record)
    if not comps:
        return ["SCALAR"]
    return comps


def _get_component(record, component_name: str):
    """Resolve a component object inside a particle record."""
    scalar_marker = io.Record_Component.SCALAR
    if component_name in ("SCALAR", "scalar"):
        return record[scalar_marker]
    if component_name in record:
        return record[component_name]
    # Fall back to scalar marker if the record is scalar
    try:
        return record[scalar_marker]
    except Exception as e:
        raise ValueError(
            f"Component '{component_name}' not found. "
            f"Available: {list(record)}"
        ) from e


# ── Tool registration ────────────────────────────────────────────────────────

def register_read_particles_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_read_particles(
        series_path: str,
        iteration: int,
        species: str,
        records: list[str] | None = None,
        particle_slice: str | None = None,
        return_data: bool = False,
        apply_unit_SI: bool = True,
        combine_position_offset: bool = True,
        max_return_elements: int = 200_000,
    ) -> dict:
        """
        Read particle records for a species at a chosen iteration.

        By default returns shape, dtype, and basic stats per component.
        Set return_data=True to include the actual values (bounded by
        max_return_elements).

        Args:
            series_path: Path or %T-template path to the openPMD series.
            iteration: Iteration number to read.
            species: Particle species name, e.g. "e_left", "e_right".
            records: Optional list of record names to read, e.g.
                     ["position", "momentum", "charge"]. If None, reads
                     all records present for the species.
            particle_slice: Optional "start:stop[:step]" slice along the
                            particle index. Useful for subsampling large
                            populations.
            return_data: If True, include the values in the result. Default False.
            apply_unit_SI: If True, multiply each component by its unit_SI.
            combine_position_offset: If True and both 'position' and
                                     'positionOffset' are requested (or read by
                                     default), return an additional record
                                     'absolute_position' = position + offset
                                     in SI units. Default True.
            max_return_elements: Cap on the number of total elements returned
                                 across all components when return_data=True.

        Returns:
            Dict containing:
              - series_path, iteration, species
              - n_particles_total:  total count for this species at this iter
              - n_particles_read:   count after slicing
              - records: dict keyed by record name; each entry contains a dict
                         keyed by component name with shape, dtype, unit_SI,
                         stats, and (if return_data) data.
              - absolute_position: if combine_position_offset is True and both
                                   position and positionOffset are present.
        """
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

            if species not in it.particles:
                raise ValueError(
                    f"Species '{species}' not found. "
                    f"Available: {list(it.particles)}"
                )
            sp = it.particles[species]

            available_records = list(sp)
            if records is None:
                records_to_read = available_records
            else:
                missing = [r for r in records if r not in available_records]
                if missing:
                    raise ValueError(
                        f"Records not found in species '{species}': {missing}. "
                        f"Available: {available_records}"
                    )
                records_to_read = list(records)

            # Determine particle count from the first component we encounter
            n_total = None
            for rname in available_records:
                for cname in _iter_components(sp[rname]):
                    comp = _get_component(sp[rname], cname)
                    n_total = int(comp.shape[0])
                    break
                if n_total is not None:
                    break
            if n_total is None:
                raise RuntimeError(
                    f"Could not determine particle count for species '{species}'"
                )

            slc = _parse_slice(particle_slice, n_total)
            n_read = max(0, (slc.stop - slc.start + (slc.step - 1)) // slc.step)

            # Read everything requested
            out_records: dict[str, dict] = {}
            running_total = 0
            data_buffers: dict[tuple[str, str], Any] = {}

            for rname in records_to_read:
                record = sp[rname]
                comp_block: dict[str, dict] = {}
                for cname in _iter_components(record):
                    comp = _get_component(record, cname)
                    unit_SI = float(comp.unit_SI)
                    chunk = comp.load_chunk(
                        [slc.start], [max(0, slc.stop - slc.start)]
                    )
                    series.flush()
                    if slc.step != 1:
                        chunk = chunk[::slc.step]
                    if apply_unit_SI:
                        chunk = chunk * unit_SI

                    info: dict[str, Any] = {
                        "shape": list(chunk.shape),
                        "dtype": str(chunk.dtype),
                        "unit_SI": unit_SI,
                        "stats": _array_summary(chunk),
                    }
                    data_buffers[(rname, cname)] = chunk
                    if return_data:
                        running_total += chunk.size
                        if running_total > max_return_elements:
                            raise ValueError(
                                f"Refusing to return >{max_return_elements} "
                                f"elements. Subsample with particle_slice or "
                                f"raise max_return_elements."
                            )
                        info["data"] = chunk.tolist()
                    comp_block[cname] = info
                out_records[rname] = comp_block

            result: dict[str, Any] = {
                "series_path": path,
                "iteration": iteration,
                "species": species,
                "n_particles_total": n_total,
                "n_particles_read": n_read,
                "records": out_records,
            }

            # Combined absolute position if available
            if (
                combine_position_offset
                and "position" in out_records
                and "positionOffset" in out_records
            ):
                abs_pos: dict[str, dict] = {}
                for axis in ("x", "y", "z"):
                    if (
                        ("position", axis) in data_buffers
                        and ("positionOffset", axis) in data_buffers
                    ):
                        p = data_buffers[("position", axis)]
                        o = data_buffers[("positionOffset", axis)]
                        # Both already include their unit_SI if apply_unit_SI=True
                        if not apply_unit_SI:
                            p_unit = float(
                                _get_component(sp["position"], axis).unit_SI
                            )
                            o_unit = float(
                                _get_component(sp["positionOffset"], axis).unit_SI
                            )
                            abs_axis = p * p_unit + o * o_unit
                        else:
                            abs_axis = p + o
                        entry: dict[str, Any] = {
                            "shape": list(abs_axis.shape),
                            "dtype": str(abs_axis.dtype),
                            "stats": _array_summary(abs_axis),
                            "units": "SI (m)",
                        }
                        if return_data:
                            entry["data"] = abs_axis.tolist()
                        abs_pos[axis] = entry
                if abs_pos:
                    result["absolute_position"] = abs_pos

            return result
        finally:
            try:
                series.close()
            except AttributeError:
                del series

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpmd_api as io

from lib.path_validators import validate_path


# ── Helpers ──────────────────────────────────────────────────────────────────

# openPMD unit_dimension is a 7-tuple of exponents:
#   (length L, mass M, time T, current I, temperature theta, amount N, lum. J)
_UNIT_DIMENSION_LABELS = ("L", "M", "T", "I", "theta", "N", "J")


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


def _dim_tuple(value) -> dict | None:
    """
    Convert a 7-vector unit_dimension into a labelled dict.
    Returns None if the value is missing or unparseable.
    """
    if value is None:
        return None
    try:
        seq = list(value)
    except TypeError:
        return None
    if len(seq) != 7:
        return None
    return {label: float(seq[i]) for i, label in enumerate(_UNIT_DIMENSION_LABELS)}


def _dim_repr(dim: dict | None) -> str | None:
    """
    Build a human-readable string for a unit_dimension dict, e.g.
    {L: 1, T: -2} -> 'L T^-2'. Returns None if dim is None.
    """
    if dim is None:
        return None
    parts = []
    for label, exp in dim.items():
        if exp == 0:
            continue
        if exp == 1:
            parts.append(label)
        else:
            # int-looking floats print cleaner
            if float(exp).is_integer():
                exp_str = str(int(exp))
            else:
                exp_str = f"{exp:g}"
            parts.append(f"{label}^{exp_str}")
    return " ".join(parts) if parts else "1"


def _iter_record_components(record) -> list[str]:
    """List component names; treat scalar records as a single 'SCALAR'."""
    comps = list(record)
    return comps if comps else ["SCALAR"]


def _component_units(comp) -> dict:
    """Extract unit-related metadata from any openPMD component object."""
    unit_SI = _safe_attr(comp, "unit_SI", default=None)
    dim = _dim_tuple(_safe_attr(comp, "unit_dimension", default=None))
    return {
        "unit_SI": float(unit_SI) if unit_SI is not None else None,
        "unit_dimension": dim,
        "unit_dimension_str": _dim_repr(dim),
    }


# ── Tool registration ────────────────────────────────────────────────────────

def register_units_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_get_units(
        series_path: str,
        iteration: int | None = None,
        mesh: str | None = None,
        species: str | None = None,
    ) -> dict:
        """
        Return SI conversion factors and unit dimensions for the meshes
        and particle records in an openPMD series.

        Each entry includes:
          - unit_SI:              float, multiply raw values by this for SI
          - unit_dimension:       dict of base-SI exponents {L,M,T,I,theta,N,J}
          - unit_dimension_str:   human-readable form, e.g. 'L T^-2'

        Args:
            series_path: Path or %T-template path to the openPMD series.
            iteration:   Iteration to inspect. Defaults to first available.
            mesh:        If given, return only this mesh (and its components).
            species:     If given, return only this particle species
                         (and its records / components).

        Returns:
            Dict with:
              - series_path, iteration
              - meshes:    dict keyed by mesh name → dict of components
              - particles: dict keyed by species → dict of records → dict of comps
        """
        path = _resolve_series_path(series_path)
        series = io.Series(path, io.Access.read_only)
        try:
            iter_keys = sorted(series.iterations)
            if not iter_keys:
                raise ValueError(f"No iterations found in series: {path}")

            if iteration is None:
                selected = iter_keys[0]
            else:
                if iteration not in iter_keys:
                    raise ValueError(
                        f"Iteration {iteration} not in series. "
                        f"Available range: {iter_keys[0]} … {iter_keys[-1]}"
                    )
                selected = iteration

            it = series.iterations[selected]

            # Meshes
            meshes_out: dict[str, dict] = {}
            mesh_names = [mesh] if mesh else list(it.meshes)
            for mname in mesh_names:
                if mname not in it.meshes:
                    raise ValueError(
                        f"Mesh '{mname}' not found. "
                        f"Available: {list(it.meshes)}"
                    )
                m = it.meshes[mname]
                comp_units: dict[str, dict] = {}
                # Mesh-level dimension may also exist
                mesh_dim = _dim_tuple(_safe_attr(m, "unit_dimension", default=None))
                for cname in m:
                    comp_units[cname] = _component_units(m[cname])
                meshes_out[mname] = {
                    "unit_dimension": mesh_dim,
                    "unit_dimension_str": _dim_repr(mesh_dim),
                    "components": comp_units,
                }

            # Particles
            particles_out: dict[str, dict] = {}
            species_names = [species] if species else list(it.particles)
            for sname in species_names:
                if sname not in it.particles:
                    raise ValueError(
                        f"Species '{sname}' not found. "
                        f"Available: {list(it.particles)}"
                    )
                sp = it.particles[sname]
                records_out: dict[str, dict] = {}
                for rname in sp:
                    record = sp[rname]
                    rec_dim = _dim_tuple(_safe_attr(record, "unit_dimension", default=None))
                    comp_units = {}
                    for cname in _iter_record_components(record):
                        try:
                            comp = record[cname] if cname != "SCALAR" else record[io.Record_Component.SCALAR]
                        except Exception:
                            continue
                        comp_units[cname] = _component_units(comp)
                    records_out[rname] = {
                        "unit_dimension": rec_dim,
                        "unit_dimension_str": _dim_repr(rec_dim),
                        "components": comp_units,
                    }
                particles_out[sname] = records_out

            return {
                "series_path": path,
                "iteration": selected,
                "meshes": meshes_out,
                "particles": particles_out,
            }
        finally:
            try:
                series.close()
            except AttributeError:
                del series

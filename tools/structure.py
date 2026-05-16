from __future__ import annotations

from pathlib import Path
from typing import Any

# ── Helpers ──────────────────────────────────────────────────────────────────
def _component_info(component: Any) -> dict:
    """Extract serializable metadata from an OpenPMD mesh / particle componenet"""
    return {
        'shape': list(getattr(component, 'shape', [])),
        'dtype': str(getattr(component, 'dtype', 'unknown'))
    }

def _resolve_path(series_path: str) -> str:
    return str(Path(series_path).expanduser().resolve())

def _read_meshes(it: io.Iteration) -> dict:
    return {
        mesh_name: {
            comp_name: _component_info(comp)
            for comp_name, comp in mesh.items()
        }
        for mesh_name, mesh in it.meshes.items()
    }

def _read_particles(it: io.Iteration) -> dict:
    return {
        species_name: {
            record_name: {
                comp_name: _component_info(comp)
                for comp_name, comp in record.items()
            }
            for record_name, record in species.items()
        }
        for species_name, species in it.particles.items()
    }

# ── Tool registration ─────────────────────────────────────────────────────────

def register_structure_tools(mcp) -> None:

    @mcp.tool()
    def openpmd_get_structure(
        series_path: str,
        iteration: int | None = None,
    ) -> dict:
        """
        Return the mesh and particle structure of an openPMD series.

        Args:
            series_path: Path (or glob pattern) to the openPMD series file.
            iteration: Iteration to inspect. Defaults to the first available.

        Returns:
            Dict with keys: path, available_iterations, selected_iteration,
            meshes, particles.
        """
        import openpmd_api as io
        path = _resolve_path(series_path)

        # Context manager ensures the Series is closed even on error

        series = io.Series(path, io.Access.read_only)
        iteration_keys = list(series.iterations)

        if not iteration_keys:
            raise ValueError(f"No iterations found in series: {path}")

        if iteration is not None and iteration not in iteration_keys:
            raise ValueError(
                f"Iteration {iteration} not in series. "
                f"Available: {iteration_keys}"
            )

        selected = iteration if iteration is not None else iteration_keys[0]
        it = series.iterations[selected]

        del series
        return {
            "path": path,
            "available_iterations": iteration_keys,
            "selected_iteration": selected,
            "meshes": _read_meshes(it),
            "particles": _read_particles(it),
        }

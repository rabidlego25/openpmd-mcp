# openpmd-mcp

A local [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for inspecting [openPMD](https://www.openPMD.org) simulation data, with a focus on [PIConGPU](https://picongpu.hzdr.de) output.

Instead of manually exploring large HDF5 or ADIOS2 files, you can ask an AI assistant to summarise the data structure for you — before writing loaders, preprocessing pipelines, or analysis scripts.

## What it does

The server exposes MCP tools that let an AI assistant:

- List available iterations in a series
- Enumerate mesh fields and their components
- Enumerate particle species, records, and components
- Report array shapes and dtypes for every component

The result is a clear **data contract** you can reason about without touching the files directly.

## Example

```
You:     What fields are available in my PIConGPU run?

Agent:  The series at `/scratch/run_001/simOutput/%T.bp` has 1200 iterations.
         Iteration 0 contains:
           Meshes:   E (x, y, z), B (x, y, z), rho
           Particles: e⁻ → position (x,y,z) float64 [512,512,1024]
                           momentum (x,y,z) float64 [512,512,1024]
```

## Requirements

- Python ≥ 3.10
- [`openpmd-api`](https://openpmd-api.readthedocs.io) with the backends your files use (HDF5, ADIOS2, …)
- [`mcp[cli]`](https://github.com/modelcontextprotocol/python-sdk)

## Installation

```bash
git clone https://github.com/yourname/openpmd-mcp
cd openpmd-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[cli]"
```

## Usage

### Development / interactive testing

```bash
mcp dev server.py
```

### Install into Claude Desktop

```bash
mcp install server.py --name "openPMD"
```

### Run directly (e.g. from a cluster login node)

```bash
mcp run server.py
```

## Available tools

| Tool | Description |
|---|---|
| `openpmd_get_structure` | Returns the full mesh and particle structure for a given iteration |

More tools planned — see [Roadmap](#roadmap).

## Roadmap

- [ ] `openpmd_read_field` — read a mesh component into a numpy array slice
- [ ] `openpmd_read_particles` — read a particle record for a given species
- [ ] `openpmd_list_iterations` — lightweight iteration listing without full structure scan
- [ ] Support for remote paths / streaming via ADIOS2

## Project structure

```
openpmd-mcp/
├── server.py          # MCP server entry point
├── tools/
│   └── structure.py   # register_structure_tools()
├── pyproject.toml
└── README.md
```

## Licence

MIT

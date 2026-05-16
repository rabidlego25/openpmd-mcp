import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from tools.structure import register_structure_tools
from tools.runs import register_run_tools

mcp = FastMCP('openpmd-inspector')

register_structure_tools(mcp)
register_run_tools(mcp)

if __name__ == '__main__':
    mcp.run()

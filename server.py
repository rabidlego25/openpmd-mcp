import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from tools.structure import register_structure_tools
from tools.runs import register_run_tools
from tools.logs import register_log_tools
from tools.scheduler import register_scheduler_tools
from tools.discovery import register_discovery_tools

mcp = FastMCP('openpmd-inspector')

register_structure_tools(mcp)
register_run_tools(mcp)
register_log_tools(mcp)
register_scheduler_tools(mcp)
register_discovery_tools(mcp)

if __name__ == '__main__':
    mcp.run()

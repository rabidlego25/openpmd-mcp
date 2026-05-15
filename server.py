from mcp.server.fastmcp import FastMCP
from tools.structure import register_structure_tools

mcp = FastMCP('openpmd-inspector')

register_structure_tools(mcp)

if __name__ == '__main__':
    mcp.run()

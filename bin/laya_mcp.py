# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.2.0"]
# ///
"""Stdio MCP server exposing three token-frugal Laya tools to Claude Code."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from laya_connector import config, tools  # noqa: E402
from laya_connector.client import DaemonClient  # noqa: E402
from laya_connector.schemas import load_schemas  # noqa: E402

CFG = config.load(ROOT)
SCHEMAS = load_schemas(CFG.schemas_dir)
CLIENT = DaemonClient(CFG.daemon_url, CFG.remote_key, timeout=CFG.mcp_timeout_base)

server = MCPServer("laya", instructions=tools.instructions(SCHEMAS))


@server.tool(name="laya_classify",
             description="Label many items with a registered schema. Give exactly one of: items, "
                         "paths (globs inside the project), lines ({file, from?, to?}).")
def laya_classify(schema: str, items: list[str] | None = None, paths: list[str] | None = None,
                  lines: dict | None = None) -> str:
    return tools.classify(CFG, CLIENT, SCHEMAS, schema, items, paths, lines)


@server.tool(name="laya_filter_sources",
             description="Keep only sources relevant to a query. Give sources [{id, text}] or paths.")
def laya_filter_sources(query: str, sources: list[dict] | None = None, paths: list[str] | None = None,
                        top_k: int | None = None, min: float = 0.5) -> str:
    return tools.filter_sources(CFG, CLIENT, SCHEMAS, query, sources, paths, top_k, min)


@server.tool(name="laya_check_claim",
             description="Check whether passages entail or contradict a claim. Give passages [{id, text}] or paths.")
def laya_check_claim(claim: str, passages: list[dict] | None = None, paths: list[str] | None = None) -> str:
    return tools.check_claim(CFG, CLIENT, SCHEMAS, claim, passages, paths)


if __name__ == "__main__":
    server.run()

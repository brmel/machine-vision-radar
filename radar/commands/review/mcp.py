from __future__ import annotations

import argparse
import os
import sys

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands

TOKEN = "MVR_AGENT_TOKEN"

def run(args: argparse.Namespace) -> int:
    secret = os.environ.get(TOKEN, "")
    if not secret:
        return log.error(f"{TOKEN} holds the agent's token",
                         fix="radar agent-token create <name> --scope read --expires YYYY-MM-DD", code=2)
    server = args.wiring.mcp()
    for line in sys.stdin:
        if line.strip():
            answer = server.handle(secret, line.encode())
            if answer.body is not None:
                output.line(answer.body)
    return 0

def register(commands: Commands) -> None:
    commands.verb("mcp", "serve",
                  help=f"serve the MCP tools over stdio, one JSON-RPC message a line, with the agent token in {TOKEN}",
                  func=run)

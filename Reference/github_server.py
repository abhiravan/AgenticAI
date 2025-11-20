from __future__ import annotations

import argparse
import os
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..agent import orchestrate
from ..config import AgentConfig

app = FastAPI(title="Agentic Todo MCP Bridge")


class FixRequest(BaseModel):
    issue: str
    repo: Optional[str] = None
    tests: Optional[List[str]] = None
    base_branch: Optional[str] = None
    dry_run: bool = False


class FixResponse(BaseModel):
    status: str
    branch: Optional[str]
    pr_url: Optional[str] = None


@app.post("/fix", response_model=FixResponse)
async def run_fix(request: FixRequest):
    cfg = AgentConfig.from_env(
        issue_url=request.issue,
        repo_path=request.repo or os.getenv("AGENT_REPO_BASE", "."),
        base_branch=request.base_branch,
        test_commands=request.tests,
        dry_run=request.dry_run,
    )
    try:
        result = orchestrate(cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FixResponse(status="ok", branch=result.get("branch"), pr_url=result.get("pr_url"))


class WhoAmIResponse(BaseModel):
    status: str = "ok"
    message: str = "Server alive"


@app.get("/health", response_model=WhoAmIResponse)
async def health():
    return WhoAmIResponse()


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Run MCP GitHub server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args(argv)
    uvicorn.run("agentic_todo.mcp.github_server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

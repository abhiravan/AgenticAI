from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import run_workflow
from .config import AgentConfig
from .jira_api import (
    fetch_issue,
    fetch_issues_by_priority,
    format_issue_dict,
    get_default_priorities,
    get_default_project,
)


@dataclass
class SessionState:
    session_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    last_issue_key: Optional[str] = None
    last_issue: Optional[Dict[str, Any]] = None


SESSION_STORE: Dict[str, SessionState] = {}

DEFAULT_CONTEXT = {
    "repo_path": os.getenv("AGENT_REPO_BASE", str(Path.cwd())),
    "base_branch": os.getenv("AGENT_BASE_BRANCH"),
    "jira_project": get_default_project(),
    "priorities": get_default_priorities(),
    "notes": "",
}

app = FastAPI(title="Agentic Todo Chat")

WEB_DIR = Path(__file__).resolve().parents[2] / "web" / "chat"
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="chat-static")


def _fresh_context() -> Dict[str, Any]:
    return {
        **DEFAULT_CONTEXT,
        "priorities": list(DEFAULT_CONTEXT["priorities"]),
    }


class ContextPayload(BaseModel):
    repo_path: Optional[str] = None
    base_branch: Optional[str] = None
    jira_project: Optional[str] = None
    priorities: Optional[List[str]] = None
    notes: Optional[str] = None


class IssueLookupPayload(BaseModel):
    issue_key: Optional[str] = None
    priority: Optional[str] = None
    limit: int = 10


class RunAgentPayload(BaseModel):
    issue_key: Optional[str] = None
    priority: Optional[str] = None
    repo_path: Optional[str] = None
    base_branch: Optional[str] = None
    dry_run: bool = False


def _get_session(session_id: str) -> SessionState:
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


def _merge_context(state: SessionState, payload: ContextPayload) -> Dict[str, Any]:
    data = {**DEFAULT_CONTEXT, **state.context}
    updates = payload.dict(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            data[key] = value
    state.context = data
    return data


@app.post("/api/chat/sessions")
def create_session(payload: ContextPayload | None = None):
    session_id = uuid.uuid4().hex
    state = SessionState(session_id=session_id, context=_fresh_context())
    SESSION_STORE[session_id] = state
    if payload:
        _merge_context(state, payload)
    return {"session_id": session_id, "context": state.context}


@app.get("/api/chat/sessions/{session_id}")
def get_session(session_id: str):
    state = _get_session(session_id)
    return {
        "session_id": state.session_id,
        "context": state.context,
        "issue": state.last_issue,
    }


@app.patch("/api/chat/sessions/{session_id}")
def update_session(session_id: str, payload: ContextPayload):
    state = _get_session(session_id)
    context = _merge_context(state, payload)
    return {"session_id": session_id, "context": context}


@app.post("/api/chat/sessions/{session_id}/issues")
def lookup_issue(session_id: str, payload: IssueLookupPayload):
    state = _get_session(session_id)
    events: List[Dict[str, Any]] = []
    if payload.issue_key:
        issue = fetch_issue(payload.issue_key)
        state.last_issue_key = issue.key
        state.last_issue = format_issue_dict(issue)
        events.append({
            "event": "issue_fetched",
            "payload": state.last_issue,
        })
        return {
            "session_id": session_id,
            "issue": state.last_issue,
            "events": events,
        }

    priorities = (
        [payload.priority] if payload.priority else state.context.get("priorities") or DEFAULT_CONTEXT["priorities"]
    )
    issues = fetch_issues_by_priority(
        priorities=priorities,
        project=state.context.get("jira_project"),
        limit=payload.limit,
    )
    board = [format_issue_dict(item) for item in issues]
    events.append({
        "event": "board_refreshed",
        "payload": {"count": len(board), "priorities": priorities},
    })
    return {
        "session_id": session_id,
        "issues": board,
        "events": events,
    }


@app.post("/api/chat/sessions/{session_id}/run")
async def run_agent(session_id: str, payload: RunAgentPayload):
    state = _get_session(session_id)
    issue_key = payload.issue_key or state.last_issue_key
    selected_issue_event: Optional[Dict[str, Any]] = None

    if not issue_key and payload.priority:
        issues = fetch_issues_by_priority(
            priorities=[payload.priority],
            project=state.context.get("jira_project"),
            limit=1,
        )
        if issues:
            issue = issues[0]
            issue_key = issue.key
            state.last_issue_key = issue.key
            state.last_issue = format_issue_dict(issue)
            selected_issue_event = {"event": "issue_fetched", "payload": {"issue": state.last_issue}}
        else:
            raise HTTPException(status_code=404, detail=f"No issues found for priority {payload.priority}")

    if not issue_key:
        raise HTTPException(status_code=400, detail="Provide an issue key before running the agent.")

    repo_path = payload.repo_path or state.context.get("repo_path") or DEFAULT_CONTEXT["repo_path"]
    cfg = AgentConfig.from_env(
        issue_url=issue_key,
        repo_path=repo_path,
        base_branch=payload.base_branch or state.context.get("base_branch"),
        test_commands=None,
        dry_run=payload.dry_run,
    )

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    if selected_issue_event:
        await queue.put(selected_issue_event)

    def enqueue(event: Dict[str, Any]):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def runner():
        try:
            result = await loop.run_in_executor(None, lambda: run_workflow(cfg, progress_cb=enqueue))
            state.last_issue_key = result.get("issue")
            await queue.put({"event": "run_complete", "payload": result})
        except Exception as exc:  # pragma: no cover - surfaced to UI
            await queue.put({"event": "run_error", "payload": {"error": str(exc)}})
        finally:
            await queue.put(None)

    asyncio.create_task(runner())

    async def streamer():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield json.dumps(item) + "\n"

    return StreamingResponse(streamer(), media_type="application/x-ndjson")


def _read_static(name: str) -> str:
    path = WEB_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Static asset missing")
    return path.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def chat_page():
    return HTMLResponse(_read_static("index.html"))


@app.get("/board", response_class=HTMLResponse)
def board_page():
    return HTMLResponse(_read_static("board.html"))


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="Run Agentic Todo chat server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8082)
    args = parser.parse_args(argv)
    uvicorn.run("agentic_todo.chat_server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

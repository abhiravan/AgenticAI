from __future__ import annotations

import argparse
import json
import sys
import textwrap
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import difflib

from .config import AgentConfig
from .context import collect_issue_context, collect_plan_file_context
from .gitops import (
    GitError,
    PatchApplyError,
    apply_patch,
    changed_files,
    commit_all,
    ensure_branch,
    push_branch,
    run_tests,
)
from .jira_api import fetch_issue, format_issue_dict
from .llm_utils import load_llm
from .patch_utils import extract_patches, parse_diff_files, extract_code_block
from .pr_client import GitHubClient
from .repo_manager import resolve_repo_path, get_repo_test_commands, prepare_repo


def build_branch_name(prefix: str, issue_key: str | None) -> str:
    slug = (issue_key or "issue").lower().replace(" ", "-")
    return f"{prefix}/{slug}-{uuid.uuid4().hex[:6]}"


def format_test_results(results: Optional[List[dict]], commands: Optional[List[str]]) -> str:
    def clip(text: Optional[str]) -> str:
        snippet = (text or "").strip()
        if not snippet:
            return ""
        lines = snippet.splitlines()
        snippet = "\n".join(lines[:20])
        if len(lines) > 20:
            snippet += "\n..."
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "..."
        return snippet

    if results:
        lines = []
        for res in results:
            status = "PASS" if res["returncode"] == 0 else "FAIL"
            snippet = clip(res.get("stdout") or res.get("stderr"))
            if snippet:
                fenced = "\n".join(f"  {line}" for line in snippet.splitlines())
                lines.append(f"- `{res['command']}` {status}\n  ```\n{fenced}\n  ```")
            else:
                lines.append(f"- `{res['command']}` {status}")
        return "\n".join(lines)
    if commands:
        return "\n".join(f"- `{cmd}` (skipped)" for cmd in commands)
    return "Tests skipped"


def apply_with_refinement(
    llm,
    issue,
    plan,
    repo_context,
    repo_path,
    patch_text,
    max_attempts: int = 3,
    progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
):
    current_patch = patch_text
    attempts = 0
    rewrite_attempted = False
    while attempts < max_attempts:
        try:
            if progress:
                progress("patch_apply_start", {"attempt": attempts + 1})
            apply_patch(current_patch, repo_path)
            if progress:
                progress("patch_apply_success", {"attempt": attempts + 1})
            return
        except PatchApplyError as exc:
            attempts += 1
            if progress:
                progress(
                    "patch_apply_error",
                    {"attempt": attempts, "error": str(exc)},
                )
            if attempts >= max_attempts:
                try:
                    if rewrite_attempted:
                        raise RuntimeError("Rewrite already attempted and failed")
                    fallback_patch = attempt_file_rewrite(llm, issue, plan, repo_path, current_patch)
                    apply_patch(fallback_patch, repo_path)
                    if progress:
                        progress("patch_rewrite_applied", {"attempt": attempts})
                    return
                except RuntimeError as rewrite_error:
                    if progress:
                        progress("patch_rewrite_failed", {"error": str(rewrite_error)})
                    rewrite_attempted = True
                    refined = llm.refine_patch(
                        issue_prompt=issue.to_prompt(),
                        plan=plan,
                        repo_context=repo_context,
                        failed_patch=current_patch,
                        error_message=str(rewrite_error),
                    )
                    new_patches = extract_patches(refined) or [refined.strip()]
                    current_patch = new_patches[0]
                    attempts = max_attempts - 1
                    continue
            print(f"Patch apply failed (attempt {attempts}): {exc}. Requesting refinement...")
            refined = llm.refine_patch(
                issue_prompt=issue.to_prompt(),
                plan=plan,
                repo_context=repo_context,
                failed_patch=current_patch,
                error_message=str(exc),
            )
            new_patches = extract_patches(refined) or [refined.strip()]
            current_patch = new_patches[0]
            if progress:
                progress("patch_refined", {"attempt": attempts})


def attempt_file_rewrite(llm, issue, plan, repo_path: Path, patch_text: str) -> str:
    files = parse_diff_files(patch_text)
    target = files[0][1] if files else None
    if not target:
        raise RuntimeError("Unable to determine target file for rewrite fallback")
    file_path = repo_path / target
    if not file_path.exists():
        raise RuntimeError(f"Cannot rewrite missing file: {file_path}")
    current_text = file_path.read_text()
    rewritten = llm.rewrite_file(issue.to_prompt(), plan, target, current_text)
    new_text = extract_code_block(rewritten)
    diff = difflib.unified_diff(
        current_text.splitlines(),
        new_text.splitlines(),
        fromfile=f"a/{target}",
        tofile=f"b/{target}",
        lineterm="",
    )
    diff_text = "\n".join(diff)
    if not diff_text.strip():
        raise RuntimeError("Rewrite produced no changes")
    return diff_text + "\n"


def ensure_github(cfg: AgentConfig) -> GitHubClient:
    if not cfg.github_token or not cfg.github_repo:
        raise RuntimeError("GitHub token or repo missing.")
    return GitHubClient(cfg.github_token, cfg.github_repo, cfg.github_base_url)


def _diff_snippet(diff_text: str, max_lines: int = 80) -> str:
    lines = diff_text.strip().splitlines()
    if not lines:
        return ""
    snippet = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        snippet += "\n..."
    return snippet


def run_workflow(
    cfg: AgentConfig,
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
):
    def emit(event: str, payload: Optional[Dict[str, Any]] = None):
        if not progress_cb:
            return
        progress_cb({
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload or {},
        })

    def progress_wrapper(event: str, payload: Dict[str, Any]):
        emit(event, payload)

    issue = fetch_issue(cfg.issue_url)
    print(f"Fetched issue {issue.key}: {issue.summary}")
    emit("issue_fetched", {"issue": format_issue_dict(issue)})

    repo_path = resolve_repo_path(issue, Path(cfg.repo_path))
    prepare_repo(issue.repo_hint, repo_path)
    emit("repo_ready", {"path": str(repo_path)})
    base_context = collect_issue_context(issue, repo_path)
    emit("context_collected", {"length": len(base_context)})

    llm = load_llm(cfg)
    plan = llm.generate_plan(issue.to_prompt(), base_context)
    plan_file_context = collect_plan_file_context(plan, repo_path)
    repo_context = base_context + ("\n\n" + plan_file_context if plan_file_context else "")
    print("LLM plan:\n", json.dumps(plan, indent=2))
    emit("plan_generated", {"plan": plan, "summary": plan.get("analysis"), "tests": plan.get("tests")})
    emit("plan_stage_done", {"stage": "plan", "status": "done"})
    emit("stage_transition", {"stage": "patch", "status": "in_progress"})

    patch_resp = llm.propose_patch(issue.to_prompt(), plan, repo_context)
    patches = extract_patches(patch_resp)
    if not patches:
        raise RuntimeError("LLM returned no patch")
    emit("patches_proposed", {"count": len(patches)})

    branch = build_branch_name(cfg.work_branch_prefix, issue.key)
    result = {"issue": issue.key, "branch": branch, "pr_url": None}
    ensure_branch(repo_path, cfg.base_branch, branch)
    emit("branch_ready", {"branch": branch})

    for idx, patch in enumerate(patches, start=1):
        emit("patch_apply_queue", {"index": idx, "total": len(patches)})
        emit("patch_preview", {"index": idx, "diff": _diff_snippet(patch)})
        apply_with_refinement(
            llm,
            issue,
            plan,
            repo_context,
            repo_path,
            patch,
            progress=progress_wrapper if progress_cb else None,
        )
        emit("patch_applied", {"index": idx})

    if not changed_files(repo_path):
        raise RuntimeError("No changes detected after applying patch")
    emit("workspace_changed", {})
    emit("stage_transition", {"stage": "tests", "status": "in_progress"})

    tests_to_run = cfg.test_commands or get_repo_test_commands(issue.repo_hint)
    test_results = None
    if tests_to_run:
        print("Running tests...")
        test_results = run_tests(tests_to_run, repo_path)
        emit("tests_completed", {"commands": tests_to_run, "results": test_results})
    else:
        emit("tests_skipped", {})

    emit("stage_transition", {"stage": "pr", "status": "in_progress"})
    commit_message = f"{issue.key or 'ISSUE'}: {issue.summary or 'Auto fix'}"
    commit_all(commit_message, repo_path)
    emit("commit_created", {"message": commit_message})

    if cfg.dry_run:
        print("Dry run mode - skipping push and PR.")
        emit("dry_run_complete", {"branch": branch})
        return result

    push_branch(repo_path, branch)
    emit("branch_pushed", {"branch": branch})

    if cfg.github_token and cfg.github_repo:
        pr_client = ensure_github(cfg)
        pr_title = commit_message
        summary_line = plan.get("analysis") if isinstance(plan, dict) else None
        if not summary_line:
            summary_line = f"Automated fix for {issue.key}"
        body = textwrap.dedent(
            """
            ## Summary
            - Issue: {issue_url}
            - Fix: {summary}

            ## Tests
            {tests}
            """
        ).format(
            issue_url=issue.url,
            summary=summary_line,
            tests=format_test_results(test_results, tests_to_run),
        ).strip()
        pr = pr_client.create_pull_request(
            title=pr_title,
            body=body,
            head=branch,
            base=cfg.base_branch,
            reviewers=cfg.github_default_reviewers or None,
            draft=False,
        )
        pr_url = pr.get('html_url')
        print(f"PR created: {pr_url}")
        result["pr_url"] = pr_url
        emit("pr_created", {"url": pr_url})
    else:
        print("GitHub credentials missing - push completed without PR.")
        emit("push_complete", {"branch": branch})

    return result


def orchestrate(cfg: AgentConfig):
    return run_workflow(cfg)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal agentic workflow for Jira issues.")
    parser.add_argument("issue_url", help="Jira issue URL or key")
    parser.add_argument("--repo", dest="repo", default=str(Path.cwd()))
    parser.add_argument("--base-branch", dest="base_branch", default=None)
    parser.add_argument("--test", dest="tests", action="append", help="Test command (repeatable)")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv or sys.argv[1:])
    cfg = AgentConfig.from_env(
        issue_url=args.issue_url,
        repo_path=args.repo,
        base_branch=args.base_branch,
        test_commands=args.tests or None,
        dry_run=args.dry_run,
    )
    orchestrate(cfg)


if __name__ == "__main__":
    main()

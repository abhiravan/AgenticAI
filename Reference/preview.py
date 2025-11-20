from __future__ import annotations

import argparse
from pathlib import Path

from .agent import build_branch_name  # reuse naming helper
from .config import AgentConfig
from .context import collect_issue_context
from .gitops import working_tree_summary
from .jira_api import fetch_issue
from .llm_utils import load_llm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview LLM plan/patch without applying changes")
    parser.add_argument("issue", help="Jira issue key or URL")
    parser.add_argument("--repo", help="Override repo path if Jira description lacks Repo hint")
    parser.add_argument("--max-context", type=int, default=10, help="Not used currently (reserved)")
    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    issue = fetch_issue(args.issue)
    repo_path = Path(issue.repo_path or args.repo or ".").resolve()
    cfg = AgentConfig.from_env(
        issue_url=issue.key,
        repo_path=str(repo_path),
        test_commands=None,
        dry_run=True,
    )
    llm = load_llm(cfg)

    repo_context = collect_issue_context(issue, repo_path)

    plan = llm.generate_plan(issue.to_prompt(), repo_context)
    print("## LLM Plan\n", plan)

    diff = llm.propose_patch(issue.to_prompt(), plan, repo_context)
    print("\n## Proposed Patch\n", diff)


if __name__ == "__main__":
    main()

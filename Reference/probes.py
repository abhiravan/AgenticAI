from __future__ import annotations

import argparse
import json
import os

from .jira_api import JiraConfig, connect, fetch_issue, serialize
from .pr_client import GitHubClient


def probe_jira(args: argparse.Namespace):
    cfg = JiraConfig.from_env()
    jira_client = connect(cfg)
    issue = fetch_issue(args.issue, jira_client=jira_client)
    print(json.dumps(serialize(issue), indent=2, ensure_ascii=False))


def probe_github(args: argparse.Namespace):
    token = args.token or os.getenv("GITHUB_TOKEN")
    repo = args.repo or os.getenv("GITHUB_REPO")
    base_url = args.base_url or os.getenv("GITHUB_API_URL", "https://api.github.com")
    if not token or not repo:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPO are required for the GitHub probe.")

    client = GitHubClient(token=token, repo=repo, base_url=base_url)
    user = client.get_user()
    repo_info = client.get_repository()

    print(
        json.dumps(
            {
                "user": {
                    "login": user.get("login"),
                    "name": user.get("name"),
                },
                "repo": {
                    "name": repo_info.get("full_name"),
                    "default_branch": repo_info.get("default_branch"),
                    "open_prs": repo_info.get("open_issues_count"),
                },
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe integrations for the agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    jira_cmd = subparsers.add_parser("jira", help="Fetch and print a Jira issue via API")
    jira_cmd.add_argument("issue", help="Issue key or URL")
    jira_cmd.set_defaults(func=probe_jira)

    gh_cmd = subparsers.add_parser("github", help="Validate GitHub credentials and repo access")
    gh_cmd.add_argument("--repo", help="org/name repo (defaults to GITHUB_REPO)")
    gh_cmd.add_argument("--token", help="GitHub token override")
    gh_cmd.add_argument("--base-url", help="GitHub API base URL override")
    gh_cmd.set_defaults(func=probe_github)

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from typing import Optional

from .jira_api import (
    JiraConfig,
    build_bug_jql,
    connect,
    format_issue_dict,
    get_default_priorities,
    get_default_project,
    serialize,
    to_issue,
)


def list_bugs(args: argparse.Namespace):
    cfg = JiraConfig.from_env(site=args.site, email=args.email, token=args.token)
    jira_client = connect(cfg)

    if args.whoami:
        emit(jira_client.myself(), args)
        return

    priorities = (
        [priority.strip() for priority in args.priorities.split(",") if priority.strip()]
        if args.priorities
        else get_default_priorities()
    )
    project = args.project or get_default_project()
    jql = args.jql or build_bug_jql(project, priorities)
    issues = jira_client.search_issues(jql, maxResults=args.max)
    server = jira_client._options.get("server", "")
    payload = [format_issue_dict(to_issue(issue, server)) for issue in issues]
    emit(payload, args)


def emit(data, args):
    if args.json:
        print(json.dumps(serialize(data), indent=2, ensure_ascii=False))
    else:
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    line = " | ".join(f"{k}:{item.get(k)}" for k in item.keys())
                    print(line)
                else:
                    print(item)
            print(f"\nTotal: {len(data)} records")
        else:
            print(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch low-priority Jira bugs")
    parser.add_argument("--site", help="Override Jira site (defaults to JIRA_SITE env)")
    parser.add_argument("--email", help="Override Jira email (defaults to JIRA_EMAIL env)")
    parser.add_argument("--token", help="Override Jira token (defaults to JIRA_API_TOKEN env)")
    parser.add_argument("--project", help="Project key (defaults to JIRA_PROJECT_KEY or ACI)")
    parser.add_argument("--priorities", help="Comma separated priority names (defaults to env or 'Low,Lowest')")
    parser.add_argument("--max", type=int, default=25, help="Max issues to return")
    parser.add_argument("--jql", help="Optional custom JQL (overrides project/priorities)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--whoami", action="store_true", help="Show current Jira identity and exit")
    return parser


def main(argv: Optional[list[str]] = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    list_bugs(args)


if __name__ == "__main__":
    main()

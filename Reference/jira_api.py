from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from jira import JIRA

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ISSUE_KEY_PATTERN = re.compile(r"([A-Z][A-Z0-9]+-\d+)", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"^([A-Za-z ]{3,30}):\s*(.*)$")
SECTION_ALIASES = {
    "repo": "repo",
    "repo url": "repo",
    "repository": "repo",
    "repo path": "repo",
    "codebase": "repo",
    "description": "description",
    "details": "description",
    "error": "error_code",
    "error code": "error_code",
    "stack": "stack_trace",
    "stack trace": "stack_trace",
}
def load_repo_aliases() -> Dict[str, str]:
    raw = os.getenv("JIRA_REPO_ALIAS", "")
    mapping = {
        "poc-ui": "poc-ui",
        "ui": "poc-ui",
        "frontend": "poc-ui",
        "web": "poc-ui",
        "poc-service": "poc-service",
        "service": "poc-service",
        "backend": "poc-service",
        "api": "poc-service",
    }
    for entry in raw.split(","):
        if "=" in entry:
            alias, repo = entry.split("=", 1)
            mapping[alias.strip().lower()] = repo.strip()
    return mapping

REPO_ALIASES = load_repo_aliases()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def get_default_project() -> str:
    return _env("JIRA_PROJECT_KEY", "ACI")


def get_default_priorities() -> List[str]:
    raw = _env("JIRA_PRIORITIES", "Low,Lowest")
    return [priority.strip() for priority in raw.split(",") if priority.strip()]


@dataclass
class JiraConfig:
    site: str
    email: str
    token: str

    @classmethod
    def from_env(
        cls,
        site: Optional[str] = None,
        email: Optional[str] = None,
        token: Optional[str] = None,
    ) -> "JiraConfig":
        site_val = site or _env("JIRA_SITE")
        email_val = email or _env("JIRA_EMAIL")
        token_val = token or _env("JIRA_API_TOKEN")
        missing = [
            name
            for name, value in [
                ("JIRA_SITE", site_val),
                ("JIRA_EMAIL", email_val),
                ("JIRA_API_TOKEN", token_val),
            ]
            if not value
        ]
        if missing:
            raise SystemExit(f"Missing Jira environment variables: {', '.join(missing)}")
        return cls(site=site_val, email=email_val, token=token_val)


def connect(cfg: JiraConfig) -> JIRA:
    return JIRA(options={"server": cfg.site}, basic_auth=(cfg.email, cfg.token))


def build_bug_jql(project: str, priorities: List[str]) -> str:
    quoted = ", ".join(f'"{p}"' for p in priorities)
    return (
        f"project = {project} AND issuetype = Bug AND priority in ({quoted}) "
        f"ORDER BY priority ASC, created ASC"
    )


def extract_issue_key(issue_ref: str) -> str:
    match = ISSUE_KEY_PATTERN.search(issue_ref)
    if not match:
        raise ValueError(f"Unable to determine issue key from '{issue_ref}'")
    return match.group(1).upper()


@dataclass
class JiraIssue:
    key: str
    summary: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    assignee: Optional[str]
    reporter: Optional[str]
    description: Optional[str]
    repo_hint: Optional[str]
    repo_path: Optional[str]
    error_code: Optional[str]
    stack_trace: Optional[str]
    structured_description: Dict[str, str]
    url: str

    def to_prompt(self) -> str:
        return (
            f"Issue {self.key}: {self.summary or ''}\n"
            f"Status: {self.status} | Priority: {self.priority}\n"
            f"Assignee: {self.assignee} | Reporter: {self.reporter}\n"
            f"Repo hint: {self.repo_hint} | Repo path: {self.repo_path}\n"
            f"Description:\n{self.description or ''}\n"
            f"Error Code: {self.error_code or 'n/a'}\n"
            f"Stack Trace:\n{self.stack_trace or 'n/a'}\n"
            f"URL: {self.url}"
        )


def to_issue(issue, server: str) -> JiraIssue:
    fields = issue.raw.get("fields", {})
    status = (fields.get("status") or {}).get("name")
    priority = (fields.get("priority") or {}).get("name")
    assignee = (fields.get("assignee") or {}).get("displayName")
    reporter = (fields.get("reporter") or {}).get("displayName")
    description = extract_description(issue)
    sections = parse_description_sections(description or "")
    repo_hint, repo_path = resolve_repo_hint(sections.get("repo"))
    return JiraIssue(
        key=issue.key,
        summary=fields.get("summary"),
        status=status,
        priority=priority,
        assignee=assignee,
        reporter=reporter,
        description=description,
        repo_hint=repo_hint,
        repo_path=str(repo_path) if repo_path else None,
        error_code=sections.get("error_code"),
        stack_trace=sections.get("stack_trace"),
        structured_description=sections,
        url=f"{server.rstrip('/')}/browse/{issue.key}",
    )


def fetch_issue(
    issue_ref: str,
    jira_client: Optional[JIRA] = None,
    cfg: Optional[JiraConfig] = None,
) -> JiraIssue:
    key = extract_issue_key(issue_ref)
    client = jira_client or connect(cfg or JiraConfig.from_env())
    issue = client.issue(key, expand="renderedFields")
    return to_issue(issue, client._options.get("server", ""))


def fetch_issues_by_priority(
    priorities: Optional[List[str]] = None,
    project: Optional[str] = None,
    limit: int = 10,
    jira_client: Optional[JIRA] = None,
    cfg: Optional[JiraConfig] = None,
) -> List[JiraIssue]:
    client = jira_client or connect(cfg or JiraConfig.from_env())
    project_key = project or get_default_project()
    priority_list = priorities or get_default_priorities()
    jql = build_bug_jql(project_key, priority_list)
    issues = client.search_issues(jql, maxResults=limit)
    return [to_issue(issue, client._options.get("server", "")) for issue in issues]


def format_issue_dict(issue: JiraIssue) -> Dict[str, Any]:
    return {
        "key": issue.key,
        "summary": issue.summary,
        "status": issue.status,
        "priority": issue.priority,
        "assignee": issue.assignee,
        "reporter": issue.reporter,
        "description": issue.description,
        "repo_hint": issue.repo_hint,
        "repo_path": issue.repo_path,
        "error_code": issue.error_code,
        "stack_trace": issue.stack_trace,
        "structured_description": issue.structured_description,
        "url": issue.url,
    }


def serialize(obj: Any):
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, list):
        return [serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: serialize(value) for key, value in obj.items()}
    if hasattr(obj, "_asdict"):
        return serialize(obj._asdict())
    if hasattr(obj, "raw"):
        return serialize(obj.raw)
    if hasattr(obj, "__dict__"):
        return serialize({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


def extract_description(issue) -> Optional[str]:
    rendered = issue.raw.get("renderedFields", {}).get("description")
    if rendered:
        return unescape(strip_html(rendered)).strip()
    fields = issue.raw.get("fields", {})
    desc = fields.get("description")
    if isinstance(desc, str):
        return desc.strip()
    return None


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def parse_description_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    for line in text.splitlines():
        match = SECTION_PATTERN.match(line.strip())
        if match:
            alias = SECTION_ALIASES.get(match.group(1).strip().lower())
            if alias:
                current_key = alias
                sections[current_key] = match.group(2).strip()
                continue
        if current_key:
            sections[current_key] = (sections[current_key] + "\n" + line.rstrip()).strip()
    if "description" not in sections and text.strip():
        sections["description"] = text.strip()
    return sections


def resolve_repo_hint(value: Optional[str]) -> Tuple[Optional[str], Optional[Path]]:
    if not value:
        return None, None
    slug = value.strip()
    slug_lower = slug.lower()
    if slug_lower.startswith("http"):
        slug_lower = slug_lower.rstrip("/").split("/")[-1]
    slug_lower = slug_lower.replace(".git", "")
    repo_hint = None
    for alias, repo in REPO_ALIASES.items():
        if alias in slug_lower:
            repo_hint = repo
            break
    if repo_hint is None and slug_lower in REPO_ALIASES.values():
        repo_hint = slug_lower
    if repo_hint:
        candidate = PROJECT_ROOT / repo_hint
        if candidate.exists():
            return repo_hint, candidate
        return repo_hint, None
    return None, None

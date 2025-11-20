from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _split_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(',') if part.strip()]


@dataclass
class AgentConfig:
    issue_url: str
    repo_path: Path = field(default_factory=lambda: Path.cwd())
    base_branch: str = "main"
    work_branch_prefix: str = "agent"
    test_commands: List[str] = field(default_factory=list)

    azure_endpoint: Optional[str] = None
    azure_key: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: str = "2024-05-01-preview"

    github_token: Optional[str] = None
    github_repo: Optional[str] = None  # e.g. org/project
    github_base_url: str = "https://api.github.com"
    github_default_reviewers: List[str] = field(default_factory=list)

    dry_run: bool = False

    @classmethod
    def from_env(cls, issue_url: str, repo_path: Optional[str] = None, **overrides):
        repo = Path(repo_path or os.getenv("AGENT_REPO", Path.cwd()))
        tests_env = os.getenv("AGENT_TEST_COMMANDS")
        test_commands = overrides.pop("test_commands", None)
        if test_commands is None:
            test_commands = [cmd.strip() for cmd in tests_env.split(';')] if tests_env else []

        cfg = cls(
            issue_url=issue_url,
            repo_path=repo,
            base_branch=overrides.get("base_branch") or os.getenv("AGENT_BASE_BRANCH", "main"),
            work_branch_prefix=overrides.get("work_branch_prefix") or os.getenv("AGENT_BRANCH_PREFIX", "agent"),
            test_commands=test_commands,
            azure_endpoint=overrides.get("azure_endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_key=overrides.get("azure_key") or os.getenv("AZURE_OPENAI_KEY"),
            azure_deployment=overrides.get("azure_deployment") or os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            azure_api_version=overrides.get("azure_api_version") or os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            github_token=overrides.get("github_token") or os.getenv("GITHUB_TOKEN"),
            github_repo=overrides.get("github_repo") or os.getenv("GITHUB_REPO"),
            github_base_url=overrides.get("github_base_url") or os.getenv("GITHUB_API_URL", "https://api.github.com"),
            github_default_reviewers=_split_env_list(
                overrides.get("github_default_reviewers") or os.getenv("GITHUB_REVIEWERS")
            ),
            dry_run=bool(overrides.get("dry_run") or os.getenv("AGENT_DRY_RUN")),
        )
        return cfg

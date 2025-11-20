from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .jira_api import JiraIssue
from .gitops import run_cmd


def parse_remote_map(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    mapping: Dict[str, str] = {}
    entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
    for entry in entries:
        if "=" in entry:
            key, value = entry.split("=", 1)
        elif ":" in entry:
            key, value = entry.split(":", 1)
        else:
            continue
        mapping[key.strip()] = value.strip()
    return mapping


def parse_subdir_map(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    mapping: Dict[str, str] = {}
    for entry in raw.split(","):
        if ":" not in entry:
            continue
        key, value = entry.split(":", 1)
        mapping[key.strip()] = value.strip()
    return mapping


def ensure_monorepo(base_dir: Optional[Path] = None) -> Optional[Path]:
    remote = os.getenv("MONOREPO_REMOTE") or os.getenv("GITHUB_MONOREPO_REMOTE")
    if not remote:
        return None
    base = base_dir or Path(os.getenv("AGENT_REPO_BASE", Path.cwd()))
    base.mkdir(parents=True, exist_ok=True)
    default_name = Path(remote.rstrip("/").split("/")[-1]).stem or "monorepo"
    repo_dir = Path(os.getenv("MONOREPO_DIR", str(base / default_name))).resolve()

    if not repo_dir.exists():
        subprocess.run(["git", "clone", remote, str(repo_dir)], check=True)
    else:
        run_cmd(["git", "fetch", "--all"], repo_dir, check=False)
    run_cmd(["git", "checkout", "master"], repo_dir, check=False)
    run_cmd(["git", "pull", "--ff-only"], repo_dir, check=False)
    return repo_dir


def ensure_repo(repo_hint: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or Path(os.getenv("AGENT_REPO_BASE", Path.cwd()))
    base.mkdir(parents=True, exist_ok=True)
    repo_dir = base / repo_hint

    remote_map = parse_remote_map(os.getenv("GITHUB_REPO_REMOTE_MAP"))
    remote = remote_map.get(repo_hint)
    if not remote:
        raise RuntimeError(
            f"No remote mapping for repo '{repo_hint}'. Set GITHUB_REPO_REMOTE_MAP (e.g. poc-ui=git@github.com:org/poc-ui.git)."
        )

    if not repo_dir.exists():
        subprocess.run(["git", "clone", remote, str(repo_dir)], check=True)
    else:
        run_cmd(["git", "fetch", "--all"], repo_dir, check=False)
    return repo_dir


def resolve_repo_path(issue: JiraIssue, fallback: Path) -> Path:
    if issue.repo_path and Path(issue.repo_path).exists():
        return Path(issue.repo_path).resolve()

    if issue.repo_hint:
        monorepo_root = ensure_monorepo()
        subdir_map = parse_subdir_map(os.getenv("MONOREPO_SUBDIRS"))
        if monorepo_root and subdir_map:
            subdir = subdir_map.get(issue.repo_hint)
            if subdir:
                candidate = monorepo_root / subdir
                if candidate.exists():
                    return candidate
        try:
            return ensure_repo(issue.repo_hint)
        except RuntimeError as error:
            print(f"Warning: {error}")

    return fallback.resolve()


def parse_test_command_map(raw: Optional[str]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    if not raw:
        return mapping
    for entry in raw.split(","):
        if ":" not in entry:
            continue
        repo, commands = entry.split(":", 1)
        mapping[repo.strip()] = [cmd.strip() for cmd in commands.split(";") if cmd.strip()]
    return mapping


DEFAULT_REPO_TESTS = {
    "poc-ui": ["npm test"],
    "poc-service": ["mvn test"],
}

DEFAULT_REPO_PREP = {
    "poc-ui": ["npm install"],
    "poc-service": [],
}


def get_repo_test_commands(repo_hint: Optional[str]) -> List[str]:
    mapping = parse_test_command_map(os.getenv("REPO_TEST_COMMANDS"))
    if repo_hint and repo_hint in mapping:
        return mapping[repo_hint]
    if repo_hint and repo_hint in DEFAULT_REPO_TESTS:
        return DEFAULT_REPO_TESTS[repo_hint]
    return []


def get_repo_prep_commands(repo_hint: Optional[str]) -> List[str]:
    mapping = parse_test_command_map(os.getenv("REPO_PREP_COMMANDS"))
    if repo_hint and repo_hint in mapping:
        return mapping[repo_hint]
    if repo_hint and repo_hint in DEFAULT_REPO_PREP:
        return DEFAULT_REPO_PREP[repo_hint]
    return []


def prepare_repo(repo_hint: Optional[str], path: Path):
    commands = get_repo_prep_commands(repo_hint)
    for command in commands:
        tokens = command.split()
        run_cmd(tokens, path, check=False)

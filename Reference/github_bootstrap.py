from __future__ import annotations

import argparse
import os
from pathlib import Path

from .gitops import run_cmd


def ensure_remote(remote_url: str, cwd: Path, remote_name: str = "origin"):
    result = run_cmd(["git", "remote"], cwd)
    existing = result.stdout.split()
    if remote_name not in existing:
        run_cmd(["git", "remote", "add", remote_name, remote_url], cwd)


def make_authed_url(remote_url: str, token: str) -> str:
    if remote_url.startswith("https://"):
        return remote_url.replace("https://", f"https://{token}@", 1)
    if remote_url.startswith("http://"):
        return remote_url.replace("http://", f"http://{token}@", 1)
    raise ValueError("Use https:// URL for PAT-based push")


def push_initial(remote_url: str, branch: str, token_env: str, cwd: Path):
    token = os.getenv(token_env)
    if not token:
        raise SystemExit(f"Environment variable {token_env} is missing")
    ensure_remote(remote_url, cwd)
    authed = make_authed_url(remote_url, token)
    run_cmd(["git", "push", authed, branch], cwd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap repo to GitHub via PAT")
    parser.add_argument("remote", help="GitHub https remote (e.g. https://github.com/org/repo.git)")
    parser.add_argument("--branch", default="master", help="Branch to push (default master)")
    parser.add_argument("--token-env", default="GITHUB_TOKEN", help="Env var holding PAT")
    parser.add_argument("--repo-path", default=".", help="Path to repo (default cwd)")
    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    push_initial(args.remote, args.branch, args.token_env, Path(args.repo_path).resolve())
    print(f"Pushed {args.branch} to {args.remote}")


if __name__ == "__main__":
    main()

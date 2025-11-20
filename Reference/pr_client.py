from __future__ import annotations

from typing import List, Optional

import requests


class GitHubClient:
    def __init__(self, token: str, repo: str, base_url: str = "https://api.github.com"):
        self.token = token
        self.repo = repo
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.base_url}/repos/{self.repo}{path}"

    def get_repository(self) -> dict:
        response = self.session.get(self._url(""), timeout=15)
        response.raise_for_status()
        return response.json()

    def get_user(self) -> dict:
        response = self.session.get(f"{self.base_url}/user", timeout=15)
        response.raise_for_status()
        return response.json()

    def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        reviewers: Optional[List[str]] = None,
        draft: bool = False,
    ) -> dict:
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
        }
        response = self.session.post(self._url("/pulls"), json=payload, timeout=30)
        response.raise_for_status()
        pr = response.json()

        if reviewers:
            self.session.post(
                self._url(f"/pulls/{pr['number']}/requested_reviewers"),
                json={"reviewers": reviewers},
                timeout=15,
            )
        return pr

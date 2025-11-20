from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI

from .patch_utils import extract_patches
from .patch_utils import parse_diff_files


class LLMClient:
    def __init__(self, *, endpoint: str, api_key: str, deployment: str, api_version: str):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.deployment = deployment

    def _chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            temperature=temperature,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def generate_plan(self, issue_prompt: str, repo_summary: str) -> Dict[str, Any]:
        system = {
            "role": "system",
            "content": "You are a senior engineer. Produce a terse JSON plan for fixing the bug.",
        }
        user = {
            "role": "user",
            "content": (
                "Jira Issue:\n" + issue_prompt + "\n\n" + "Repository status:\n" + repo_summary + "\n" +
                "Respond with JSON containing keys analysis, proposed_changes, tests. Tests section must describe the concrete regression test you will add or update."
            ),
        }
        raw = self._chat([system, user])
        return self._safe_json(raw)

    def _patch_prompt(self, issue_prompt: str, plan: Dict[str, Any], file_context: str) -> Dict[str, Dict[str, str]]:
        return {
            "role": "user",
            "content": (
                "Issue:\n" + issue_prompt + "\nPlan:\n" + json.dumps(plan, indent=2) +
                "\nRepository context:\n" + file_context +
                "\nReturn diff relative to working tree."
            ),
        }

    def propose_patch(self, issue_prompt: str, plan: Dict[str, Any], file_context: str) -> str:
        system = {
            "role": "system",
            "content": (
                "You output unified diff patches compatible with git apply. Each file must start with "
                "'diff --git' and include proper context. Wrap the entire response in one ```diff code fence. "
                "Only modify the minimal lines related to the bug; do not rewrite unrelated code. Always include the test changes required to prove the fix."
            ),
        }
        user = self._patch_prompt(issue_prompt, plan, file_context)
        return self._chat([system, user], temperature=0.1)

    def refine_patch(
        self,
        issue_prompt: str,
        plan: Dict[str, Any],
        repo_context: str,
        failed_patch: str,
        error_message: str,
    ) -> str:
        system = {
            "role": "system",
            "content": (
                "You output unified diff patches compatible with git apply."
                " Each file must begin with diff --git and include context."
                " Wrap everything in a ```diff fence and only touch lines relevant to the failure. Include or fix the corresponding test case."
            ),
        }
        user = {
            "role": "user",
            "content": (
                "Issue:\n" + issue_prompt + "\nPlan:\n" + json.dumps(plan, indent=2) +
                "\nRepository context:\n" + repo_context +
                "\nThe previous patch failed to apply with error:\n" + error_message +
                "\nHere is the failing patch:\n```diff\n" + failed_patch + "\n```" +
                "\nReturn a corrected patch."
            ),
        }
        return self._chat([system, user], temperature=0.1)

    def rewrite_file(
        self,
        issue_prompt: str,
        plan: Dict[str, Any],
        file_path: str,
        current_text: str,
    ) -> str:
        system = {
            "role": "system",
            "content": (
                "Rewrite the provided file to fix the bug. Return the full file content only, inside a single "
                "code fence (use ```jsx for JS/TS files). Do not include explanations."
            ),
        }
        user = {
            "role": "user",
            "content": (
                f"Issue:\n{issue_prompt}\nPlan:\n{json.dumps(plan, indent=2)}\n\n"
                f"File path: {file_path}\nCurrent contents:\n```\n{current_text}\n```\n"
                "Return the corrected file contents.")
        }
        return self._chat([system, user], temperature=0.1)

    @staticmethod
    def _safe_json(raw: str) -> Dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except json.JSONDecodeError:
                    pass
        return {"analysis": raw.strip()}

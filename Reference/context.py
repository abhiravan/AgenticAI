from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .gitops import working_tree_summary
from .jira_api import JiraIssue

RG_AVAILABLE = shutil.which("rg") is not None
STACK_FILE_PATTERN = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:js|jsx|ts|tsx|java|kt|py|rb|go))(?::(\d+))?")
FILE_REF_PATTERN = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:js|jsx|ts|tsx|java|kt|py|rb|go|css|scss|json))")
KEYWORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{4,}")
ALLOWED_EXTS = {".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".py", ".rb", ".go", ".css", ".scss", ".json"}
TEST_GUIDANCE = {
    "poc-ui": (
        "Add or update Vitest suites under src/components/__tests__ to cover the regression scenario. "
        "Use React Testing Library helpers from '@testing-library/react' and Vitest globals "
        "(`vi`, `describe`, `it`, `expect`). Do not reference `jest.*`. "
        "When importing components (e.g., TodoForm), include the `.jsx` extension so the bundler resolves the file."
    ),
    "poc-service": (
        "Add or update JUnit tests under src/test/java/com/agentdemo/... to cover the regression scenario."
    ),
}


def collect_issue_context(issue: JiraIssue, repo_path: Path) -> str:
    sections: List[str] = []
    sections.append("## Repo Status\n" + working_tree_summary(repo_path))

    stack_snippets = extract_stack_snippets(issue.stack_trace, repo_path)
    if stack_snippets:
        sections.append("## Stack Trace Matches\n" + "\n\n".join(stack_snippets))

    desc_files = extract_description_files(issue, repo_path)
    if desc_files:
        sections.append("## Files Mentioned in Jira\n" + "\n\n".join(desc_files))

    keyword_files = find_keyword_files(issue, repo_path)
    if keyword_files:
        sections.append("## Files Inferred from Keywords\n" + "\n\n".join(keyword_files))

    error_snippets = []
    if issue.error_code:
        error_snippets.extend(search_tokens([issue.error_code], repo_path))
    if issue.summary:
        keywords = [token for token in re.split(r"[^A-Za-z0-9_]", issue.summary) if len(token) > 4]
        error_snippets.extend(search_tokens(keywords[:3], repo_path))
    if error_snippets:
        sections.append("## Keyword Matches\n" + "\n\n".join(error_snippets))

    if issue.description:
        sections.append("## Jira Description\n```\n" + issue.description.strip() + "\n```")

    if issue.stack_trace:
        sections.append("## Jira Stack Trace\n```\n" + issue.stack_trace.strip() + "\n```")

    guidance = TEST_GUIDANCE.get(issue.repo_hint or "")
    if guidance:
        sections.append("## Testing Guidance\n" + guidance)

    return "\n\n".join(sections)


def collect_plan_file_context(plan: Dict[str, Any], repo_path: Path) -> str:
    files_section: List[str] = []
    proposed = plan.get("proposed_changes") if isinstance(plan, dict) else None
    if not isinstance(proposed, list):
        return ""
    seen: set[Path] = set()
    for change in proposed:
        if not isinstance(change, dict):
            continue
        file_ref = change.get("file")
        if not file_ref:
            continue
        candidate = (repo_path / file_ref.strip(" ./"))
        if candidate.exists() and candidate.is_file() and candidate not in seen:
            seen.add(candidate)
            files_section.append(render_file(candidate))
            for sibling in _related_test_files(candidate):
                if sibling not in seen and sibling.exists():
                    seen.add(sibling)
                    files_section.append(render_file(sibling))
    if files_section:
        return "## Files Referenced in Plan\n" + "\n\n".join(files_section)
    return ""


def _related_test_files(source_file: Path) -> List[Path]:
    related: List[Path] = []
    suffix = source_file.suffix
    if not suffix:
        return related
    tests_dir = source_file.parent / "__tests__"
    if not tests_dir.exists():
        return related
    for middle in (".test", ".spec"):
        candidate = tests_dir / f"{source_file.stem}{middle}{suffix}"
        if candidate.exists():
            related.append(candidate)
    return related


def extract_stack_snippets(stack_trace: Optional[str], repo_path: Path, context: int = 5) -> List[str]:
    if not stack_trace:
        return []
    snippets: List[str] = []
    seen: set[Path] = set()
    for match in STACK_FILE_PATTERN.finditer(stack_trace):
        rel_path = match.group(1)
        line = int(match.group(2) or 1)
        candidate = repo_path / rel_path
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            snippets.append(render_snippet(candidate, line, context))
        if len(snippets) >= 5:
            break
    return snippets


def extract_description_files(issue: JiraIssue, repo_path: Path, max_files: int = 5) -> List[str]:
    snippets: List[str] = []
    seen_paths: set[Path] = set()
    text_blobs = [issue.description or ""] + list(issue.structured_description.values())
    for blob in text_blobs:
        for match in FILE_REF_PATTERN.finditer(blob):
            rel_path = match.group(1).strip(" .,:;\"'\n\t")
            rel_path = rel_path.lstrip("./")
            candidate = (repo_path / rel_path).resolve()
            if candidate.exists() and candidate not in seen_paths:
                seen_paths.add(candidate)
                snippets.append(render_file(candidate))
                if len(snippets) >= max_files:
                    return snippets
    return snippets


def find_keyword_files(issue: JiraIssue, repo_path: Path, max_files: int = 5) -> List[str]:
    snippets: List[str] = []
    seen_paths: set[Path] = set()
    texts = [issue.summary or "", issue.description or ""] + list(issue.structured_description.values())
    tokens: List[str] = []
    for text in texts:
        tokens.extend(KEYWORD_PATTERN.findall(text))
    seen_tokens: set[str] = set()
    ordered_tokens: List[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in seen_tokens:
            seen_tokens.add(lowered)
            ordered_tokens.append(token)
    for token in ordered_tokens[:10]:
        matches = repo_path.rglob(f"*{token}*")
        for match_path in matches:
            if match_path in seen_paths or not match_path.is_file():
                continue
            if match_path.suffix and match_path.suffix not in ALLOWED_EXTS:
                continue
            seen_paths.add(match_path)
            snippets.append(render_file(match_path))
            if len(snippets) >= max_files:
                return snippets
    return snippets


def render_snippet(path: Path, line: int, context: int = 5) -> str:
    try:
        lines = path.read_text().splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return f"{path}:<unreadable>"
    start = max(line - context - 1, 0)
    end = min(line + context, len(lines))
    body = "\n".join(f"{start + idx + 1:4}: {content}" for idx, content in enumerate(lines[start:end]))
    return f"File: {path}\n{body}"


def render_file(path: Path, max_lines: int = 400) -> str:
    try:
        lines = path.read_text().splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return f"File: {path} (unable to read)"
    snippet = []
    for idx, line in enumerate(lines[:max_lines]):
        snippet.append(f"{idx + 1:4}: {line}")
    if len(lines) > max_lines:
        snippet.append("... (truncated)")
    ext = path.suffix.lower()
    language = "json" if ext == ".json" else "jsx" if ext in {".js", ".jsx", ".ts", ".tsx"} else ""
    fence = f"```{language}\n" if language else "```\n"
    body = "\n".join(snippet)
    return f"File: {path}\n{fence}{body}\n```"


def search_tokens(tokens: Iterable[str], repo_path: Path) -> List[str]:
    if not RG_AVAILABLE:
        return []
    snippets: List[str] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        try:
            result = subprocess.run(
                [
                    "rg",
                    "--no-heading",
                    "--line-number",
                    "--color",
                    "never",
                    "--max-count",
                    "5",
                    token,
                    str(repo_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            break
        if result.returncode == 0 and result.stdout.strip():
            snippets.append(f"Token '{token}' matches:\n" + result.stdout.strip())
    return snippets

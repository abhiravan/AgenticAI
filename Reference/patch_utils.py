from __future__ import annotations

import re
from typing import List, Tuple

PATCH_BLOCK = re.compile(r"```(?:patch|diff)?\n(.*?)```", re.DOTALL)
FILE_SPLIT = re.compile(r"(diff --git .*?)(?=diff --git |$)", re.DOTALL)
DIFF_FILE_PATTERN = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)
CODE_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")


def extract_patches(response: str) -> List[str]:
    matches = PATCH_BLOCK.findall(response)
    if matches:
        patches: List[str] = []
        for match in matches:
            match = match.strip()
            if match.startswith("diff --git"):
                for chunk in FILE_SPLIT.findall(match):
                    patches.append(chunk.strip())
            elif match:
                patches.append(match)
        if patches:
            return patches
    if response.strip().startswith('---') or response.strip().startswith('diff --git'):
        chunks = FILE_SPLIT.findall(response.strip())
        if chunks:
            return [chunk.strip() for chunk in chunks]
        return [response.strip()]
    if response.strip().startswith('```'):
        return [response.strip('`')]
    return []


def parse_diff_files(patch_text: str) -> List[Tuple[str, str]]:
    files: List[Tuple[str, str]] = []
    for match in DIFF_FILE_PATTERN.finditer(patch_text):
        files.append((match.group(1), match.group(2)))
    return files


def extract_code_block(text: str) -> str:
    match = CODE_FENCE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def normalize_patch(patch_text: str) -> str:
    sanitized = patch_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = sanitized.splitlines()
    changed = False
    i = 0
    while i < len(lines):
        line = lines[i]
        match = HUNK_HEADER.match(line)
        if match:
            old_start = match.group(1)
            old_len = int(match.group(2) or "1")
            new_start = match.group(3)
            new_len = int(match.group(4) or "1")
            suffix = match.group(5) or ""
            j = i + 1
            old_count = 0
            new_count = 0
            while j < len(lines):
                candidate = lines[j]
                if HUNK_HEADER.match(candidate) or candidate.startswith("diff --git "):
                    break
                if candidate.startswith("--- ") and lines[j - 1].startswith("diff --git "):
                    break
                if candidate.startswith("\\ No newline at end of file"):
                    j += 1
                    continue
                if candidate.startswith("+"):
                    new_count += 1
                elif candidate.startswith("-"):
                    old_count += 1
                else:
                    old_count += 1
                    new_count += 1
                j += 1
            if old_count != old_len or new_count != new_len:
                lines[i] = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{suffix}"
                changed = True
        i += 1
    normalized = "\n".join(lines) if changed else sanitized
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized

from __future__ import annotations

import subprocess
import tempfile
import shlex
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .patch_utils import normalize_patch, parse_diff_files


class GitError(RuntimeError):
    pass


class PatchApplyError(GitError):
    def __init__(self, message: str, patch_text: str):
        super().__init__(message)
        self.patch_text = patch_text
        self.details = message


def _patch_target_paths(patch_text: str) -> List[str]:
    targets: List[str] = []
    try:
        files = parse_diff_files(patch_text)
    except Exception:
        files = []
    for old_path, new_path in files:
        if old_path and old_path != "/dev/null":
            targets.append(old_path)
        if new_path and new_path != "/dev/null" and new_path != old_path:
            targets.append(new_path)
    return targets


def cleanup_patch_artifacts(cwd: Path, patch_text: str):
    paths = _patch_target_paths(patch_text)
    suffixes = (".orig", ".rej", ".rej.orig", ".orig.rej")
    for rel in paths:
        base = cwd / rel
        for suffix in suffixes:
            candidate = Path(f"{base}{suffix}")
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass


def _snapshot_files(cwd: Path, paths: List[str]) -> Dict[str, Tuple[bool, Optional[bytes]]]:
    snapshot: Dict[str, Tuple[bool, Optional[bytes]]] = {}
    for rel in paths:
        file_path = cwd / rel
        if file_path.exists():
            try:
                snapshot[rel] = (True, file_path.read_bytes())
            except OSError:
                snapshot[rel] = (True, None)
        else:
            snapshot[rel] = (False, None)
    return snapshot


def _files_changed(cwd: Path, paths: List[str], before: Dict[str, Tuple[bool, Optional[bytes]]]) -> bool:
    if not paths:
        return True
    for rel in paths:
        file_path = cwd / rel
        exists = file_path.exists()
        try:
            data = file_path.read_bytes() if exists else None
        except OSError:
            data = None
        prev_exists, prev_data = before.get(rel, (False, None))
        if exists != prev_exists:
            return True
        if exists and data != prev_data:
            return True
    return False


def run_cmd(cmd: List[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise GitError(f"Command {' '.join(cmd)} failed: {details}")
    return result


def current_branch(cwd: Path) -> str:
    return run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd).stdout.strip()


def ensure_branch(cwd: Path, base: str, new_branch: str):
    base_branch = base or "master"
    run_cmd(["git", "fetch", "--all"], cwd, check=False)
    run_cmd(["git", "checkout", base_branch], cwd)
    run_cmd(["git", "pull", "--ff-only"], cwd, check=False)
    run_cmd(["git", "checkout", "-B", new_branch, base_branch], cwd)


def working_tree_summary(cwd: Path) -> str:
    status = run_cmd(["git", "status", "-sb"], cwd).stdout
    diffstat = run_cmd(["git", "diff", "--stat"], cwd, check=False).stdout
    return f"Status:\n{status}\nDiff:\n{diffstat}"


def apply_patch(patch_text: str, cwd: Path):
    normalized_patch = normalize_patch(patch_text)
    target_paths = _patch_target_paths(normalized_patch)
    before_state = _snapshot_files(cwd, target_paths)
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(normalized_patch)
        tmp_path = tmp.name
    applied = False
    try:
        try:
            run_cmd(["git", "apply", "--whitespace=fix", tmp_path], cwd)
            applied = True
        except GitError as exc:
            fallback = subprocess.run(
                ["patch", "--forward", "-p1"],
                cwd=cwd,
                text=True,
                input=normalized_patch,
                capture_output=True,
            )
            if fallback.returncode == 0:
                applied = True
            else:
                failure_path = Path(tempfile.mkstemp(prefix="agent_patch_error_", suffix=".diff")[1])
                failure_path.write_text(normalized_patch)
                raise PatchApplyError(
                    f"Failed to apply patch via git apply and patch. "
                    f"Git error: {exc}. Patch stderr: {fallback.stderr.strip()}\n"
                    f"Patch saved to {failure_path}",
                    patch_text=normalized_patch,
                ) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        cleanup_patch_artifacts(cwd, normalized_patch)
    if not applied:
        raise PatchApplyError("Patch failed to apply", normalized_patch)
    if not _files_changed(cwd, target_paths, before_state):
        raise PatchApplyError("Patch applied but produced no file changes", normalized_patch)


def changed_files(cwd: Path) -> List[str]:
    result = run_cmd(["git", "status", "-sb"], cwd)
    files = []
    for line in result.stdout.splitlines():
        if not line or line.startswith("##"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def run_tests(commands: Iterable[str], cwd: Path):
    results = []
    for command in commands:
        tokens = shlex.split(command)
        proc = subprocess.run(tokens, cwd=cwd, text=True, capture_output=True)
        results.append({
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        })
        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr)
        if proc.returncode != 0:
            raise RuntimeError(f"Test command '{command}' failed with code {proc.returncode}: {proc.stderr.strip()}")
    return results


def push_branch(cwd: Path, branch: str):
    run_cmd(["git", "push", "-u", "origin", branch], cwd)


def commit_all(message: str, cwd: Path):
    run_cmd(["git", "add", "."], cwd)
    run_cmd(["git", "commit", "-m", message], cwd)

#!/usr/bin/env python3
"""
AK-Threads-Booster: safely check or apply upstream skill updates.

Usage:
    python scripts/check_skill_update.py
    python scripts/check_skill_update.py --apply --validate
    python scripts/check_skill_update.py --remote origin --branch main

This script never stashes, resets, rebases, or overwrites local changes.
It only applies updates when the working tree is clean and the update can
fast-forward.
"""

import argparse
import json
import py_compile
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def run_git(args: List[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=check,
    )


def lines(value: str) -> List[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def git_output(args: List[str], cwd: Path, check: bool = True) -> str:
    return run_git(args, cwd, check=check).stdout.strip()


def validate_python_files(repo: Path, changed_files: List[str]) -> Dict[str, Any]:
    py_files = [repo / path for path in changed_files if path.endswith(".py") and (repo / path).exists()]
    results = []
    for path in py_files:
        try:
            py_compile.compile(str(path), doraise=True)
            results.append({"file": str(path.relative_to(repo)), "status": "ok"})
        except py_compile.PyCompileError as exc:
            results.append({"file": str(path.relative_to(repo)), "status": "failed", "error": str(exc)})
        except OSError as exc:
            # File vanished between scan and compile (e.g. concurrent merge).
            results.append({"file": str(path.relative_to(repo)), "status": "missing", "error": str(exc)})
    return {
        "checked_python_files": [item["file"] for item in results],
        "passed": all(item["status"] == "ok" for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or apply AK-Threads-Booster upstream updates safely.")
    parser.add_argument("--repo", default=".", help="Repository path. Defaults to current directory.")
    parser.add_argument("--remote", default="origin", help="Git remote to fetch from.")
    parser.add_argument("--branch", default="main", help="Remote branch to compare against.")
    parser.add_argument("--apply", action="store_true", help="Apply update with fast-forward only when safe.")
    parser.add_argument("--validate", action="store_true", help="Run lightweight validation after a successful update.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    result: Dict[str, Any] = {
        "repo": str(repo),
        "remote": args.remote,
        "branch": args.branch,
        "applied": False,
        "status": "unknown",
        "blockers": [],
    }

    try:
        git_output(["rev-parse", "--is-inside-work-tree"], repo)
    except subprocess.CalledProcessError as exc:
        result.update({"status": "not_git_repo", "error": exc.stderr.strip()})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    remote_ref = f"{args.remote}/{args.branch}"
    try:
        run_git(["fetch", "--prune", args.remote], repo)
    except subprocess.CalledProcessError as exc:
        # The whole script's value is the JSON-status contract. A network
        # blip during fetch should produce a structured failure, not a raw
        # CalledProcessError stack trace that breaks downstream parsers.
        result.update(
            {
                "status": "fetch_failed",
                "error": (exc.stderr or "").strip() or str(exc),
            }
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    current_branch = git_output(["branch", "--show-current"], repo, check=False) or "detached"
    local_head = git_output(["rev-parse", "HEAD"], repo)
    remote_head = git_output(["rev-parse", remote_ref], repo)
    dirty = lines(git_output(["status", "--porcelain"], repo, check=False))
    local_only = lines(git_output(["log", "--oneline", f"{remote_ref}..HEAD"], repo, check=False))
    upstream_only = lines(git_output(["log", "--oneline", f"HEAD..{remote_ref}"], repo, check=False))
    changed_files = lines(git_output(["diff", "--name-only", "HEAD", remote_ref], repo, check=False))

    result.update({
        "current_branch": current_branch,
        "local_head": local_head,
        "remote_head": remote_head,
        "dirty_files": dirty,
        "local_only_commits": local_only,
        "upstream_commits": upstream_only,
        "changed_files": changed_files,
    })

    if local_head == remote_head:
        result["status"] = "up_to_date"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not upstream_only:
        result["status"] = "local_ahead_or_diverged"
        result["blockers"].append("No fast-forward update is available from upstream.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if dirty:
        result["status"] = "blocked_dirty_worktree"
        result["blockers"].append("Working tree has uncommitted or untracked files.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if local_only:
        result["status"] = "blocked_local_commits"
        result["blockers"].append("Local-only commits exist; automatic update would need a human decision.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if not args.apply:
        result["status"] = "update_available"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    merge = run_git(["merge", "--ff-only", remote_ref], repo, check=False)
    result["merge_stdout"] = merge.stdout.strip()
    result["merge_stderr"] = merge.stderr.strip()
    if merge.returncode != 0:
        result["status"] = "blocked_fast_forward_failed"
        result["blockers"].append("Fast-forward merge failed.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    result["applied"] = True
    result["status"] = "updated"
    result["new_head"] = git_output(["rev-parse", "HEAD"], repo)

    if args.validate:
        result["validation"] = validate_python_files(repo, changed_files)
        if not result["validation"]["passed"]:
            result["status"] = "updated_validation_failed"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

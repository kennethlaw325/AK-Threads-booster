#!/usr/bin/env python
"""Append a sub-skill input/output capture to ``eval_candidates.jsonl``.

Opt-in: requires ``AK_THREADS_EVAL_CAPTURE=1`` in the environment.
PII-scrubbed before write per ``skills/eval/references/eval-format.md``.

Usage:
    python scripts/eval_capture.py \\
        --sub-skill draft \\
        --input-file path/to/input.json \\
        --output-file path/to/output.json \\
        [--latency-ms 12345] \\
        [--working-dir .]

The two input files may be plain text or JSON; both are loaded as raw
strings and embedded in the capture record's ``content`` field.

Append-only per ``templates/FAILSAFE.md`` log policy. No backup file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# Reuse the shared utf-8 stdout shim (cp950 console safety on Windows).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _atomic import configure_utf8_stdout  # noqa: E402

KNOWN_SUB_SKILLS = {
    "draft", "predict", "analyze", "topics",
    "refresh", "review", "voice", "setup",
}

PII_RULES: List[Tuple[str, str, str]] = [
    # (label, pattern, replacement)
    ("discord_user_id", r"<@!?\d{17,20}>", "<@REDACTED_USER>"),
    ("discord_channel_id", r"<#\d{17,20}>", "<#REDACTED_CHANNEL>"),
    ("threads_token", r"THAFZ[A-Za-z0-9_-]{100,}", "THAFZ_REDACTED"),
    ("bearer_token", r"Bearer [A-Za-z0-9_.\-]{20,}", "Bearer REDACTED"),
    ("openai_key", r"sk-[A-Za-z0-9_-]{20,}", "REDACTED_API_KEY"),
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_-]{20,}", "REDACTED_API_KEY"),
    ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "REDACTED_EMAIL"),
    ("phone_hk", r"\+852[\s-]?\d{4}[\s-]?\d{4}", "REDACTED_PHONE"),
    ("phone_e164", r"\+\d{1,3}[\s-]?\d{4,14}", "REDACTED_PHONE"),
]


def scrub(text: str) -> Tuple[str, List[str]]:
    """Apply PII rules. Return (scrubbed_text, fired_labels)."""
    fired: List[str] = []
    for label, pattern, replacement in PII_RULES:
        compiled = re.compile(pattern)
        if compiled.search(text):
            fired.append(label)
            text = compiled.sub(replacement, text)
    return text, fired


def compute_rules_hash(skill_root: Path, sub_skill: str) -> str:
    """SHA-256 over sub-skill SKILL.md + references/*.md + shared knowledge."""
    sha = hashlib.sha256()
    files: List[Path] = []
    sub_dir = skill_root / "skills" / sub_skill
    if sub_dir.exists():
        files.append(sub_dir / "SKILL.md")
        refs = sub_dir / "references"
        if refs.is_dir():
            files.extend(sorted(refs.glob("*.md")))
    shared = skill_root / "knowledge" / "_shared"
    if shared.is_dir():
        files.extend(sorted(shared.glob("*.md")))
    for f in files:
        if f.is_file():
            sha.update(f.relative_to(skill_root).as_posix().encode("utf-8"))
            sha.update(b"\0")
            sha.update(f.read_bytes())
            sha.update(b"\0")
    return sha.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    configure_utf8_stdout()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sub-skill", required=True, choices=sorted(KNOWN_SUB_SKILLS))
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument("--input-type", default="raw")
    parser.add_argument("--output-type", default="raw")
    parser.add_argument("--latency-ms", type=int, default=0)
    parser.add_argument("--context-refs", nargs="*", default=[])
    parser.add_argument("--working-dir", type=Path, default=Path("."))
    parser.add_argument("--skill-root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="AK-Threads-booster repo root (default: parent of scripts/).")
    parser.add_argument("--sub-skill-version", default="unknown",
                        help="Sub-skill version at capture time (read frontmatter manually).")
    parser.add_argument("--root-skill-version", default="unknown")
    args = parser.parse_args()

    if os.environ.get("AK_THREADS_EVAL_CAPTURE", "") != "1":
        sys.stderr.write(
            "eval-capture: AK_THREADS_EVAL_CAPTURE is not set. "
            "Set it to 1 to opt in to capture. No-op.\n"
        )
        return 0

    if not args.input_file.is_file():
        sys.stderr.write(f"eval-capture: input file missing: {args.input_file}\n")
        return 2
    if not args.output_file.is_file():
        sys.stderr.write(f"eval-capture: output file missing: {args.output_file}\n")
        return 2

    raw_input = read_text(args.input_file)
    raw_output = read_text(args.output_file)

    scrubbed_input, in_fired = scrub(raw_input)
    scrubbed_output, out_fired = scrub(raw_output)
    fired = sorted(set(in_fired + out_fired))

    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": str(uuid.uuid4()),
        "sub_skill": args.sub_skill,
        "input": {
            "type": args.input_type,
            "content": scrubbed_input,
            "context_refs": list(args.context_refs),
        },
        "output": {
            "type": args.output_type,
            "content": scrubbed_output,
            "latency_ms": args.latency_ms,
        },
        "version": {
            "sub_skill": args.sub_skill_version,
            "root_skill": args.root_skill_version,
            "rules_hash": compute_rules_hash(args.skill_root, args.sub_skill),
        },
        "consented": True,
        "scrubbed": fired,
    }

    log_path = args.working_dir / "eval_candidates.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False))
        fh.write("\n")

    print(
        f"captured: {record['id']} | sub_skill={args.sub_skill} | "
        f"scrubbed={fired or 'none'} | log={log_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

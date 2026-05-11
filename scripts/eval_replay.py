#!/usr/bin/env python
"""Replay captured sub-skill outputs against current rules; score drift.

Reads a snapshot file produced by ``/eval export`` (or any
``eval_candidates.jsonl`` slice) and computes:

- Jaccard@k token-set overlap (k=20 for /draft, k=5 for /topics, full for others)
- Exact-match (after whitespace normalization)
- Score-band stability (predict only)
- Latency Δ (when the new output's latency is supplied)

This script does NOT itself invoke sub-skills (sub-skills are markdown
SKILL.md files executed by Claude in the loop). It expects the user (or
an orchestration script) to provide a ``replayed.jsonl`` file with
fields ``{"candidate_id", "output_content", "latency_ms"}`` per line —
i.e. the new output for each captured input.

For deterministic sub-skills backed by Python scripts (e.g. /refresh's
``fetch_threads.py`` ingest), an automated replay harness can produce
the ``replayed.jsonl`` programmatically. For judgment-heavy sub-skills
(/draft, /analyze prose), the user replays manually in another session
and pastes the new output into the replayed.jsonl file.

Output: ``eval_replays/<run_id>/report.md`` + ``raw.jsonl``.

Usage:
    python scripts/eval_replay.py \\
        --against snapshot.jsonl \\
        --replayed replayed.jsonl \\
        [--working-dir .] \\
        [--sub-skill draft]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _atomic import configure_utf8_stdout  # noqa: E402

JACCARD_K_DEFAULTS = {
    "draft": 20,
    "topics": 5,
    "analyze": 30,
    "predict": 0,  # exact-band comparison instead
}

WS_NORMALIZE = re.compile(r"\s+")
TOKEN_SPLIT = re.compile(r"[\s,，。.!?！？;:、\(\)\[\]【】「」『』]+")


def normalize_ws(text: str) -> str:
    return WS_NORMALIZE.sub(" ", text).strip()


def tokens_top_k(text: str, k: int) -> set:
    """Return top-k unique tokens by first-occurrence order. k=0 means all."""
    toks = [t for t in TOKEN_SPLIT.split(text) if t]
    if k == 0:
        return set(toks)
    seen = []
    seen_set = set()
    for t in toks:
        if t not in seen_set:
            seen.append(t)
            seen_set.add(t)
            if len(seen) >= k:
                break
    return set(seen)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def parse_predict_band(content: str) -> Optional[Tuple[int, int, int]]:
    """Extract a (low, mid, high) view triple from a /predict output.

    Looks for the first three integers in the text. Returns None if it
    cannot find a clean triple.
    """
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", content)
            if n.replace(",", "").isdigit()]
    if len(nums) < 3:
        return None
    # Heuristic: take the first three "view-shaped" numbers (≥ 100)
    candidates = [n for n in nums if n >= 100][:3]
    if len(candidates) < 3:
        return None
    return tuple(sorted(candidates))


def band_stable(old_band: Optional[Tuple[int, int, int]],
                new_band: Optional[Tuple[int, int, int]]) -> Tuple[bool, bool]:
    """Return (stable, near_miss). near_miss = within one band (factor 2)."""
    if old_band is None or new_band is None:
        return (False, False)
    if old_band == new_band:
        return (True, False)
    # near miss: each pair within factor of 2
    for o, n in zip(old_band, new_band):
        if not (0.5 <= (n + 1) / (o + 1) <= 2.0):
            return (False, False)
    return (False, True)


def classify(jaccard_k: float, exact_match: bool) -> str:
    if exact_match or jaccard_k >= 0.9:
        return "stable"
    if jaccard_k >= 0.5:
        return "drift"
    return "regression"


def load_jsonl(path: Path) -> List[dict]:
    entries: List[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                sys.stderr.write(
                    f"eval-replay: skipping malformed line {path}:{lineno}: {exc}\n"
                )
    return entries


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def render_report(report_path: Path, run_id: str,
                  snapshot_path: Path, totals: Dict[str, dict],
                  raw_rows: List[dict]) -> None:
    lines: List[str] = []
    lines.append(f"# Eval Replay Report — `{run_id}`\n")
    lines.append(f"- Snapshot: `{snapshot_path}`")
    lines.append(f"- Total candidates: {sum(t['n'] for t in totals.values())}")
    lines.append(f"- Sub-skills: {', '.join(sorted(totals.keys())) or '(none)'}")
    lines.append(f"- Replay run id: `{run_id}`\n")

    lines.append("## Summary\n")
    lines.append("| Sub-skill | N  | Jaccard@k mean | Exact-match | Stable | Drift | Regression | Failed | Latency Δ p50 |")
    lines.append("|-----------|----|----------------|-------------|--------|-------|------------|--------|---------------|")
    for sub_skill, t in sorted(totals.items()):
        lines.append(
            f"| {sub_skill} | {t['n']} | "
            f"{t['jaccard_mean']:.2f} | "
            f"{t['exact_match']} / {t['n']} | "
            f"{t['stable']} | {t['drift']} | {t['regression']} | {t['failed']} | "
            f"{t['latency_p50']:+d}ms |"
        )

    lines.append("\n## Per-candidate verdicts\n")
    for row in raw_rows:
        lines.append(
            f"- `{row['candidate_id'][:8]}` "
            f"({row['sub_skill']}) — **{row['verdict']}** "
            f"jaccard={row['metrics']['jaccard_k']:.2f} "
            f"exact={row['metrics']['exact_match']} "
            f"latency_Δ={row['metrics']['latency_delta_ms']:+d}ms"
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round(pct / 100 * (len(s) - 1)))))
    return s[idx]


def main() -> int:
    configure_utf8_stdout()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--against", required=True, type=Path,
                        help="Snapshot file (JSONL of captured candidates).")
    parser.add_argument("--replayed", required=True, type=Path,
                        help="JSONL with replayed outputs: candidate_id, output_content, latency_ms.")
    parser.add_argument("--working-dir", type=Path, default=Path("."))
    parser.add_argument("--sub-skill", default=None,
                        help="Filter to one sub-skill (default: all).")
    args = parser.parse_args()

    if not args.against.is_file():
        sys.stderr.write(f"eval-replay: snapshot missing: {args.against}\n")
        return 2
    if not args.replayed.is_file():
        sys.stderr.write(f"eval-replay: replayed file missing: {args.replayed}\n")
        return 2

    snapshot = load_jsonl(args.against)
    replayed_raw = load_jsonl(args.replayed)
    replayed_by_id = {r["candidate_id"]: r for r in replayed_raw if "candidate_id" in r}

    if args.sub_skill:
        snapshot = [c for c in snapshot if c.get("sub_skill") == args.sub_skill]

    run_id = str(uuid.uuid4())
    raw_rows: List[dict] = []
    by_subskill: Dict[str, dict] = {}

    for cand in snapshot:
        cid = cand.get("id")
        sub_skill = cand.get("sub_skill", "unknown")
        if cid not in replayed_by_id:
            metrics = {
                "jaccard_k": 0.0, "exact_match": False,
                "band_stable": None, "near_miss_band": None,
                "latency_delta_ms": 0,
            }
            verdict = "replay_failed"
            note = "no replayed output supplied for this candidate_id"
        else:
            replayed = replayed_by_id[cid]
            old_text = cand["output"]["content"]
            new_text = replayed.get("output_content", "")
            old_norm = normalize_ws(old_text)
            new_norm = normalize_ws(new_text)
            exact = (old_norm == new_norm)

            if sub_skill == "predict":
                old_band = parse_predict_band(old_text)
                new_band = parse_predict_band(new_text)
                stable, near = band_stable(old_band, new_band)
                jacc = 1.0 if stable else (0.7 if near else 0.0)
                metrics = {
                    "jaccard_k": jacc,
                    "exact_match": exact,
                    "band_stable": stable,
                    "near_miss_band": near,
                    "latency_delta_ms": int(replayed.get("latency_ms", 0))
                                        - int(cand["output"].get("latency_ms", 0)),
                }
                verdict = "stable" if stable else ("drift" if near else "regression")
            else:
                k = JACCARD_K_DEFAULTS.get(sub_skill, 0)
                jacc = jaccard(tokens_top_k(old_text, k), tokens_top_k(new_text, k))
                metrics = {
                    "jaccard_k": jacc,
                    "exact_match": exact,
                    "band_stable": None,
                    "near_miss_band": None,
                    "latency_delta_ms": int(replayed.get("latency_ms", 0))
                                        - int(cand["output"].get("latency_ms", 0)),
                }
                verdict = classify(jacc, exact)
                note = ""

        rules_after = ""  # would re-compute hash if we knew skill_root path
        row = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "replay_run_id": run_id,
            "candidate_id": cid,
            "sub_skill": sub_skill,
            "rules_hash_before": cand.get("version", {}).get("rules_hash", ""),
            "rules_hash_after": rules_after,
            "outputs_changed": not metrics["exact_match"],
            "metrics": metrics,
            "verdict": verdict,
            "notes": note if "note" in dir() else "",
        }
        raw_rows.append(row)

        bucket = by_subskill.setdefault(sub_skill, {
            "n": 0, "jaccard_sum": 0.0, "exact_match": 0,
            "stable": 0, "drift": 0, "regression": 0, "failed": 0,
            "latencies": [],
        })
        bucket["n"] += 1
        bucket["jaccard_sum"] += metrics["jaccard_k"]
        if metrics["exact_match"]:
            bucket["exact_match"] += 1
        bucket[verdict if verdict != "replay_failed" else "failed"] += 1
        bucket["latencies"].append(metrics["latency_delta_ms"])

    totals = {}
    for sub_skill, bucket in by_subskill.items():
        totals[sub_skill] = {
            "n": bucket["n"],
            "jaccard_mean": (bucket["jaccard_sum"] / bucket["n"]) if bucket["n"] else 0.0,
            "exact_match": bucket["exact_match"],
            "stable": bucket["stable"],
            "drift": bucket["drift"],
            "regression": bucket["regression"],
            "failed": bucket["failed"],
            "latency_p50": percentile(bucket["latencies"], 50),
        }

    out_dir = args.working_dir / "eval_replays" / run_id
    write_jsonl(out_dir / "raw.jsonl", raw_rows)
    render_report(out_dir / "report.md", run_id, args.against, totals, raw_rows)

    print(f"replay complete: run_id={run_id}")
    print(f"  report: {out_dir / 'report.md'}")
    for sub_skill, t in sorted(totals.items()):
        print(
            f"  {sub_skill}: N={t['n']} jaccard={t['jaccard_mean']:.2f} "
            f"exact={t['exact_match']}/{t['n']} regressions={t['regression']} "
            f"failed={t['failed']}"
        )

    # Non-zero exit if any regressions detected — useful for CI gating.
    total_regressions = sum(t["regression"] for t in totals.values())
    return 1 if total_regressions > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

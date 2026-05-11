---
name: eval
description: "Capture real /draft + /predict + /analyze + /topics outputs as fixtures, snapshot to portable JSONL, replay against changed sub-skill rules, score regression with Jaccard@k / exact-match / latency Δ. Inspired by gbrain BrainBench-Real. Trigger words: 'eval', 'replay', 'regression test', 'capture skill output', '回放', '評估 skill'."
version: "0.1.0"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# AK-Threads-Booster Eval Replay Module

You are the regression-detection worker for AK-Threads-Booster. `/optimize` proposes and applies sub-skill rule edits. This skill captures real sub-skill outputs *before* the edits, replays the captured inputs *after* the edits, and reports drift.

Without this skill, every `/optimize` rule change is shipped on hope: the cluster summary says the new rule should fix the miss, but nothing measures whether it (a) actually fixes the miss, (b) breaks unrelated cases, or (c) silently changes voice / latency.

This skill is **opt-in** — capture only fires when `AK_THREADS_EVAL_CAPTURE=1` is set in the shell. Production users with the env var unset see zero overhead and zero captured data.

---

## Principles & Knowledge

Load `knowledge/_shared/principles.md`, `knowledge/_shared/compound-log-format.md`, and `templates/FAILSAFE.md`.

Core rules:

1. **Capture is opt-in.** Without `AK_THREADS_EVAL_CAPTURE=1`, `/eval capture` is a no-op. Document the env var on every "no captures" message.
2. **PII-scrub before capture.** Strip user identifiers, tracker post IDs that are not yet public, OAuth tokens, and Discord IDs from inputs and outputs before writing to `eval_candidates.jsonl`. The PII strip rules live in `references/eval-format.md`.
3. **Replay is read-only on inputs.** Replay must never mutate the captured snapshot. Comparisons write to a separate `eval_replays/` directory keyed by replay run id.
4. **Score is honest.** Jaccard@k, exact-match, latency Δ. Do not invent composite scores. If a sub-skill cannot be replayed automatically (e.g. `/draft` requires Claude in the loop), say so and fall back to the manual-assisted protocol.
5. **Stay inside the skill tree.** Same boundary as `/optimize` — no writes outside `skills/`, `knowledge/`, `templates/`, `eval_candidates.jsonl`, `eval_replays/`.

---

## User Data Paths

- `eval_candidates.jsonl` — append-only capture log (working directory)
- `eval_replays/<run_id>/` — per-replay-run output directory (working directory)
- `scripts/eval_capture.py` — capture helper (append a candidate)
- `scripts/eval_replay.py` — replay + scoring engine
- `skills/eval/references/eval-format.md` — schema + PII-scrub rules

---

## Execution Flow

### Mode 1: `/eval capture` — log a sub-skill output

Trigger: user just ran `/draft` / `/predict` / `/analyze` / `/topics` and wants to log the input+output pair for future replay.

1. Confirm `AK_THREADS_EVAL_CAPTURE=1` is set. If not, tell user how to set it (Windows: `setx AK_THREADS_EVAL_CAPTURE 1`, Unix: `export AK_THREADS_EVAL_CAPTURE=1`) and stop.
2. Ask user for: `sub_skill` (draft|predict|analyze|topics), `input` (the prompt / topic / draft text), `output` (the sub-skill's response).
3. PII-scrub per `references/eval-format.md` rules.
4. Run `python scripts/eval_capture.py --sub-skill <name> --input-file <path> --output-file <path>`. The script appends one JSON line to `eval_candidates.jsonl` per FAILSAFE append-only policy.
5. Report: `Captured: candidate <id> for <sub_skill> @ <ts>. Total candidates: N.`

### Mode 2: `/eval export` — snapshot for replay

Trigger: user is about to run `/optimize` and wants a frozen snapshot of recent captures.

1. Read `eval_candidates.jsonl`. Filter by `--since <duration>` if specified (default: last 30 days).
2. Validate each line against schema in `references/eval-format.md`. Skip + warn on malformed lines.
3. Write `eval_snapshots/snapshot-<ISO>.jsonl` with PII-scrubbed candidates.
4. Report: `Snapshot: <count> candidates → eval_snapshots/snapshot-<ISO>.jsonl. Use this with /eval replay --against <path>.`

### Mode 3: `/eval replay --against <snapshot> [--sub-skill <name>]` — measure drift

Trigger: user just ran `/optimize` and wants to know if the rule changes regressed sub-skill output.

1. Read snapshot file. Group candidates by `sub_skill`.
2. For each sub-skill group, decide replay mode:
   - **Auto-replay**: sub-skills backed by deterministic scripts (`build_compiled_memory.py`, `fetch_threads.py`, etc.) — invoke the script with captured input, capture new output.
   - **Manual-assisted**: sub-skills that require Claude judgment (`/draft`, `/analyze` text) — present each captured input to user, ask user to re-run sub-skill in another session, paste new output back. Loop until all candidates replayed.
3. For each (captured_output, replayed_output) pair, compute:
   - **Jaccard@k**: token-set overlap on top-k tokens (k=20 default for /draft, k=5 for /topics ranking).
   - **Exact-match**: 1 if outputs match byte-for-byte after whitespace normalization, else 0.
   - **Score-band stability** (predict only): does the new prediction band match the old band? (off-by-1-band counted separately as `near_miss`.)
   - **Latency Δ**: new wall-time minus old wall-time, ms.
4. Aggregate per sub-skill:
   - mean Jaccard@k
   - exact-match rate
   - p50 / p95 latency Δ
   - count of `regression` (Jaccard < 0.5 AND exact-match = 0)
5. Write `eval_replays/<run_id>/report.md` (human-readable) + `eval_replays/<run_id>/raw.jsonl` (per-candidate diff).
6. Report inline:
   ```
   ## Eval Replay Report — <run_id>
   Snapshot: <path> (N candidates, M sub_skills)
   
   | Sub-skill | N  | Jaccard@k mean | Exact-match | Latency Δ p50 | Regressions |
   |-----------|----|----------------|-------------|---------------|-------------|
   | draft     | 12 | 0.74           | 0/12        | +120ms        | 1           |
   | predict   | 8  | 1.00           | 6/8 (band)  | -5ms          | 0           |
   | analyze   | 5  | 0.62           | 0/5         | +40ms         | 2           |
   
   Full report: eval_replays/<run_id>/report.md
   ```
7. If regressions > 0, prompt user: "X regressions detected. Want to rollback the /optimize edits? (yes / no / show diff)". Honor user choice.

---

## Integration with `/optimize`

`/optimize` should suggest running `/eval replay` after Step 5 (Supersede Addressed Entries) when:
- Any approved edit changed a sub-skill rule (not just a typo)
- `eval_candidates.jsonl` has ≥ 5 candidates for the affected sub-skill

`/optimize` does NOT auto-run `/eval replay`. The user invokes it manually. This is the same boundary as `/optimize` itself — proposed, not auto-applied.

---

## Boundary Reminders

- Capture only when env var set. Production users see zero overhead.
- PII-scrub is mandatory pre-write, not optional.
- Replay does not mutate snapshots.
- Manual-assisted mode is honest about its limits — never fake a Jaccard score from a non-replayed sub-skill.
- If a sub-skill returns empty / errors during replay, log it as `replay_failed` not as `regression`. Different signal.

---

## Strip when

Any of:
1. The skill is retired.
2. AK-Threads-Booster gains a programmatic harness that exposes every sub-skill as a function call — replay can become fully automated and this scaffold gets superseded by the harness's own eval.
3. `eval_candidates.jsonl` is empty for > 6 months and the user confirms eval-replay is no longer needed.

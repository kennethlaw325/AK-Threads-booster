# `eval_candidates.jsonl` — Sub-Skill Output Capture Schema

Append-only JSONL log of sub-skill input/output pairs, captured opt-in via `AK_THREADS_EVAL_CAPTURE=1`. Snapshot via `/eval export`, replay against rule changes via `/eval replay`.

Version: 0.1.0

---

## File location

- Default: `eval_candidates.jsonl` in working directory (sibling to `threads_skill_learnings.log`).
- Only `/eval capture` (or the `scripts/eval_capture.py` helper) writes this file.
- It is read by `/eval export` and `/eval replay`.

---

## When to capture

Only when **the user explicitly invokes** `/eval capture` after a sub-skill run, AND `AK_THREADS_EVAL_CAPTURE=1` is set. Never auto-capture silently. Every entry traces to a deliberate user action.

---

## Line schema

One JSON object per line, newline-terminated. All fields required unless marked optional.

```json
{
  "ts": "2026-05-11T11:30:12Z",
  "id": "<uuid4 for this capture>",
  "sub_skill": "draft|predict|analyze|topics|refresh|review|voice|setup",
  "input": {
    "type": "<input variant — e.g. 'topic_brief', 'post_text', 'tracker_subset'>",
    "content": "<verbatim input text or structured JSON>",
    "context_refs": ["<filename or compiled/* path the sub-skill read>"]
  },
  "output": {
    "type": "<output variant — e.g. 'draft_text', 'prediction_band', 'analyze_flags', 'topic_list'>",
    "content": "<verbatim output — markdown / JSON / list>",
    "latency_ms": 12345
  },
  "version": {
    "sub_skill": "1.1.0",
    "root_skill": "2.0.0",
    "rules_hash": "<sha256 of sub-skill's SKILL.md + references + shared knowledge at capture time>"
  },
  "consented": true,
  "scrubbed": ["<list of PII fields removed — e.g. 'discord_user_id', 'access_token'>"]
}
```

### Field rules

- `ts`: ISO 8601 UTC with trailing `Z`.
- `id`: uuid4. Used as cross-reference in replay reports.
- `sub_skill`: one of the known sub-skill names. Unknown values are rejected by `/eval export`.
- `input.content` and `output.content`: verbatim post-scrub. No paraphrasing.
- `rules_hash`: lets replay detect whether the sub-skill's rules have actually changed since capture. If hash matches at replay time, replay is a sanity check (should be 100% match); if it differs, replay measures drift.
- `consented`: always `true` at write time. The field exists to make capture intent explicit.
- `scrubbed`: list of PII categories removed. Empty array if nothing was scrubbed.

---

## PII-scrub rules

Before writing to `eval_candidates.jsonl`, redact these patterns in BOTH `input.content` and `output.content`:

| Pattern | Replacement |
|---------|-------------|
| Discord user IDs (`<@[0-9]{17,20}>`) | `<@REDACTED_USER>` |
| Discord channel IDs (`<#[0-9]{17,20}>`) | `<#REDACTED_CHANNEL>` |
| Threads access tokens (`THAFZ[A-Za-z0-9_-]{100,}`) | `THAFZ_REDACTED` |
| Bearer tokens (`Bearer [A-Za-z0-9_.-]{20,}`) | `Bearer REDACTED` |
| Email addresses | `REDACTED_EMAIL` |
| Phone numbers (HK +852 / generic E.164) | `REDACTED_PHONE` |
| OpenAI / Anthropic / Google API keys (`sk-[a-zA-Z0-9_-]{20,}`, `sk-ant-[a-zA-Z0-9_-]{20,}`, etc.) | `REDACTED_API_KEY` |

Record each category that fired in the `scrubbed` array. If `scrubbed` is non-empty, the user has visibility on what was removed before snapshot/replay.

Threads post IDs (`[0-9]{17,20}` that match the user's own published posts) are NOT redacted — they're public on threads.net and form the join key with `threads_daily_tracker.json`.

---

## Append policy

Follow `templates/FAILSAFE.md` append-only log rules:

- Open in append mode. Write one line, close.
- Never rewrite prior entries.
- No backup files — append-only is the safety mechanism.
- If `eval_candidates.jsonl` exceeds 50 MB, prompt user to archive (move to `eval_candidates.archive-<ISO>.jsonl`) — large files slow down `/eval export`.

---

## Replay output schema (`eval_replays/<run_id>/raw.jsonl`)

One JSON object per replayed candidate:

```json
{
  "ts": "<replay ts>",
  "replay_run_id": "<uuid4 of this replay run>",
  "candidate_id": "<original capture id>",
  "sub_skill": "draft",
  "rules_hash_before": "<at capture>",
  "rules_hash_after": "<at replay>",
  "outputs_changed": true,
  "metrics": {
    "jaccard_k": 0.74,
    "exact_match": false,
    "band_stable": null,
    "near_miss_band": null,
    "latency_delta_ms": 120
  },
  "verdict": "stable|drift|regression|replay_failed",
  "notes": "<optional human-readable note>"
}
```

`verdict` rules:
- `stable`: `jaccard_k >= 0.9 OR exact_match`
- `drift`: `0.5 <= jaccard_k < 0.9 AND NOT exact_match`
- `regression`: `jaccard_k < 0.5 AND NOT exact_match`
- `replay_failed`: sub-skill errored or returned empty

---

## Reason to keep

Without this log + replay protocol, every `/optimize` ships on hope. With it, the user sees concrete drift numbers per sub-skill per rule change, and can rollback before the regression compounds.

## Strip when

Same conditions as `skills/eval/SKILL.md` Strip section.

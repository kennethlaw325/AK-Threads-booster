# `threads_skill_learnings.log` — Skill-Level Compound Log

The post-level feedback loop (`/review` writing to the tracker) catches what to write next. This log catches what the **skill itself** should do differently next time.

Version: 1.0.0

---

## Why this exists

The Every.to Compound loop is Plan → Work → Review → **Compound**. `ak-threads-booster` already does the first three at post level:

- Plan = `/topics` + `/draft` freshness gate
- Work = `/draft` producing a post
- Review = `/review` after publish

The fourth step — learning about the skill's own failure modes — had no landing point. When an earlier `/analyze` suggestion turned out wrong, or a `/draft` freshness-gate "Green" decision led to a saturated post, nothing captured that signal.

This log fills that gap. It is deliberately small: one JSON line per user-confirmed skill-level learning.

---

## File location

- Default: `threads_skill_learnings.log` in the working directory (sibling to `threads_freshness.log` and `threads_refresh.log`).
- Only `/review` writes this file. No other sub-skill writes it.
- It is read when the user (or the skill maintainer) runs a compound review pass. Any tool that can read JSON-line logs will work — the file is deliberately simple so it is not tied to a specific meta-skill.

---

## When to write an entry

Only when **the user explicitly confirms** a skill-level miss. Examples:

- User says "your /analyze told me to drop claim X, but after publishing it turned out keeping it would have helped."
- User says "the freshness gate said Green but the topic was already saturated — I should have been warned."
- User says "the brand_voice Manual Refinements didn't catch this drift, please add a rule."

Do **not** write entries based on the sub-skill's own guess that it did something wrong. Every entry must trace to a clear user signal in the conversation. `/review` is prohibited from fabricating learnings.

---

## Line schema

One JSON object per line, newline-terminated. All fields required unless marked optional.

```json
{
  "ts": "2026-04-22T14:30:12Z",
  "run_id": "<uuid4 of this /review session>",
  "skill": "ak-threads-booster",
  "sub_skill": "analyze|draft|predict|review|voice|topics|refresh|setup",
  "category": "false_positive|false_negative|rule_gap|voice_drift|freshness_miss|prediction_miss|other",
  "summary": "one-sentence plain-English description",
  "evidence_post_id": "<tracker post id, or null if not tied to a post>",
  "evidence_quote": "verbatim snippet from the sub-skill's output that was wrong (optional)",
  "user_signal": "verbatim quote of what the user said that triggered this capture",
  "suggested_fix": "user's suggestion, or 'none' if they only reported the miss",
  "status": "logged"
}
```

### Category definitions

- `false_positive` — sub-skill flagged a problem that wasn't a problem (e.g. R1 triggered on a phrase that wasn't engagement bait).
- `false_negative` — sub-skill missed a problem that was there (e.g. a hook/body mismatch slipped through).
- `rule_gap` — existing rule is ambiguous or absent; sub-skill's behavior was technically compliant but the user disagrees with the outcome.
- `voice_drift` — output drifted from `brand_voice.md` Manual Refinements in a way the rules should have caught.
- `freshness_miss` — freshness gate decision proved wrong post-publish.
- `prediction_miss` — `/predict` band was systematically off in a way that suggests a rule change, not just normal noise.
- `other` — everything else. If `other` is used more than twice for the same pattern, promote it to a new category in the next version.

### Field rules

- `user_signal` is verbatim, not paraphrased. This is the audit evidence.
- `evidence_quote` may be omitted when the miss is structural (rule gap) rather than textual.
- `status` is always `"logged"` at write time. Future values (e.g. `"addressed"`) will be added when the COMPOUND loop closes a ticket — not implemented in v1.

---

## Append policy

Follow `templates/FAILSAFE.md` append-only log rules:

- Open in append mode. Write one line, close.
- Never rewrite prior entries. Supersede via a new entry with `supersedes: <prior run_id>` if needed.
- No backup files — append-only is the safety mechanism.

---

## Threshold → review reminder

When `/review` finishes and the log has **≥ 10 entries** (any time, not just new ones):

- Surface in the final report: "Skill-learnings log now has N entries. Worth reviewing — recurring patterns are candidates for rule changes to the sub-skills."
- Tell the user to run `/optimize` — it ships with this skill, clusters entries by `(sub_skill, category)`, drafts concrete rule-edit proposals grounded in verbatim `user_signal` quotes, and applies only what the user approves per-proposal.
- Do **not** auto-patch sub-skills. The trigger is advisory only. `/optimize` still requires explicit user approval on every proposed edit.

> **Note:** The 10-entry log threshold is *necessary but not sufficient*
> to produce proposals. `/optimize` separately requires **≥ 2 entries
> in the same `(sub_skill, category)` cluster** before drafting a
> rule-edit proposal. A log with 11 entries spread across 11 different
> clusters will produce zero proposals; tell the user that explicitly
> rather than letting `/optimize` say "nothing to do" without context.

---

## Reason to keep

Without this log, skill-level learnings die in conversation transcripts the user will never re-read. With it, the learnings are concrete, timestamped, and greppable — and the COMPOUND pass has actual material to work with instead of vibes.

## Strip when

Any of:

1. The skill is retired.
2. Sub-skill failure capture moves to a more structured store (e.g. an eval dashboard with per-fixture miss tracking).
3. The log is empty for > 6 months and the user confirms compound-capture is no longer needed.

Until then, one line per confirmed miss. No inflation, no speculation.

# `/optimize` — Rejected Proposals Log

> One entry per proposal the user rejected. `/optimize` reads this file
> at the start of every run to dedupe — a proposal that was already
> rejected with the same `(sub_skill, category, rule_text_hash)` will
> not be re-surfaced unless `--force-resurface` is passed.

## Schema

Append-only Markdown. Each rejected proposal is one block:

```markdown
### YYYY-MM-DDTHH:MM:SSZ — <sub_skill> / <category>

- **rule_text_hash:** `<sha1[:16]>`
- **proposal:** <one-line summary of the rule edit>
- **user_signal_quote:** "<verbatim user quote that drove the proposal>"
- **rejection_reason:** "<verbatim user quote rejecting the proposal>"
- **cluster_size_at_rejection:** <int>

---
```

## Why this file exists

Without dedupe, `/optimize` would surface the same edit on every run as
long as the underlying log entries remain unresolved. That trains the
user to ignore `/optimize` output. By logging rejections, future runs
know the proposal was considered and explicitly turned down.

## When to skip dedupe

`--force-resurface` re-evaluates rejected proposals against fresh log
entries. Use only when the rejection reason no longer applies (e.g. the
sub-skill behaviour changed in an unrelated PR and the original
rejection rationale is moot).

## Strip when

This file is created on-demand by `/optimize` Step 3 if it does not
already exist. The stub above is the empty-state shape; do not
hand-edit unless you are pruning genuinely stale rejections.

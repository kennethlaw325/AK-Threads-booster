# AI-Tone Quick Card

Version: 1.0.0

Use this for `lite` and `standard` runtime. Load `knowledge/ai-detection.md` only in `deep` mode or when the user asks for a sentence-level AI-tone audit.

---

## Definite AI-Tone Patterns

### English templates

- Fixed phrase clusters: "not just X, but Y", "in today's world", "the key is".
- Over-balanced contrast pairs repeated across paragraphs.
- Consecutive quote-like lines with identical rhythm.
- Formal connectors stacked in casual writing: moreover, furthermore, ultimately.
- Philosophical ending that does not grow from the body.
- Abstract judgment without a concrete example.
- "In summary" / "to summarize" closers when the body did not need a summary.

### Chinese templates (繁中 / 简中)

The deterministic `AI_TONE_PATTERNS` list in
`scripts/build_compiled_memory.py` checks both forms; the quick card
should mirror them so card-mode flagging matches what
`compiled/account_state.md` reports:

- `不只是` / `關鍵是` / `关键是` — the X-不只是-Y template
- `最重要的是`
- `總結來說` / `总结来说` / `綜上所述` / `综上所述` — wrap-up tells
- `換句話說` / `换句话说`
- `身為一個` / `身为一个` — formal opener rarely seen in casual voice
- `總而言之` / `总而言之` / `值得一提` / `值得一提的是` — closers that lean AI
- `讓我們` / `让我们` — instructive lead-in LLMs over-use

## Possible AI-Tone Patterns

- Too many complete, polished sentences in a row.
- Repeated rhetorical questions that replace argument.
- Even paragraph lengths across the whole post.
- Emotion labels instead of felt details.
- One-sided explanation that never shows friction or constraint.
- Generic "valuable lesson" closure.

## Density Rule

- Low: 0-2 possible items, no definite pattern.
- Medium: 1 definite or 3-5 possible items.
- High: 2+ definite patterns, or the whole structure reads templated.

## Report Discipline

Flag only materially noticeable patterns. Do not rewrite unless the user explicitly asks. Name the sentence or phrase that triggered the flag.

## Load Full AI Detection When

- The user asks to humanize/de-AI deeply.
- Output mode is `full`.
- The post is high-stakes or unusually polished.
- Quick card produces a Medium/High density call and needs sentence-level support.

## reason + strip_when

Reason: Most AI-tone checks only need a compact trigger list; the full file is too expensive for default runs.

Strip when: AI-tone detection moves to a separate evaluator or retrieval can fetch exact trigger sections cheaply.

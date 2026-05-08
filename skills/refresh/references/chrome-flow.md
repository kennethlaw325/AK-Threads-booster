# Chrome Execution Flow (`/refresh` Steps 1–7)

Only run this flow when the API path is unavailable or the user explicitly asks for Chrome. Selectors come from `knowledge/chrome-selectors.md` — never hard-code them in the skill.

---

## Step 1: Load or Create Tracker

1. Glob for `threads_daily_tracker.json`.
2. If found, read it and record existing post IDs plus `last_updated`.
3. If not found, create a minimal skeleton:

```json
{
  "schema_version": 1,
  "account": { "handle": "", "source": "chrome-scrape", "timezone": "UTC" },
  "posts": [],
  "last_updated": null
}
```

`schema_version: 1` is required by `skills/setup/references/tracker-schema.md`; downstream skills validate it.

Interactive mode may ask for the handle if needed.

## Step 2: Navigate to the Profile

Navigate to `https://www.threads.com/@<handle>` and confirm the header handle matches the requested handle.

## Step 2.5: Selector Health Check (mandatory)

Run the selector health check defined in `knowledge/chrome-selectors.md`:

1. Count elements matching the post-card selector.
2. If zero and a login-wall selector matches, abort with `login_wall`.
3. If zero and no login wall matches, abort with `selector_health_failed`.
4. If one or more cards are present, continue.

Do not continue if this step fails.

## Step 3: Scroll and Collect Posts

Use `javascript_tool` to scroll until:

- no new posts load
- `--max-posts` is reached
- `--max-minutes` is reached

Use the post-card selector from `chrome-selectors.md` as the count target.

## Step 4: Extract Post Data

Extract a JSON array with:

- `id`
- `text`
- `created_at`
- `permalink`
- `media_type`
- `metrics.likes` / `replies` / `reposts` / `quotes` / `shares`
- `metrics.views` when visible

If a metric token cannot be parsed, preserve the last-known tracker value instead of writing a bad value.

## Step 5: Extract Replies

For each post that is new or whose reply count changed:

1. Open the permalink in a new tab.
2. Extract replies.
3. If a reply author matches the logged-in handle, append it to `author_replies[]` and set `my_replies = true`.
4. Close the tab.

Skip reply scraping when the reply count has not changed since the last refresh.

## Step 5.5: Sweep Expired Prediction Placeholders

Before merging, scan `posts[]` for expired `pending-` placeholders:

- move expired ones into `discarded_drafts[]`
- preserve `prediction_snapshot` and text
- add `discarded_at = now`
- remove them from `posts[]`

If a pending placeholder matches a newly scraped post, merge the prediction snapshot into the real post entry and remove the placeholder.

## Step 6: Merge Into Tracker

1. Existing post, same metrics → leave unchanged.
2. Existing post, new metrics → update metrics and append a new snapshot.
3. Existing post, new replies → append replies, do not delete old ones.
4. New post → insert with the current tracker skeleton.
5. Existing `prediction_snapshot` → keep untouched.
6. If the snapshot lands near 24h / 72h / 7d, also fill `performance_windows`.

Always update `last_updated` to the refresh timestamp.

## Step 7: Persist

Persistence intentionally writes more than one file. Backup, audit, and companion files are part of the refresh contract. Follow `templates/FAILSAFE.md`.

Before writing:

1. Copy the current tracker to `threads_daily_tracker.json.bak-<ISO>`.
2. Keep only the 5 newest backups.
3. If backup fails, abort and report the error (headless: log `backup_failed`).

Then:

1. Write the merged tracker back to `threads_daily_tracker.json` (write temp + atomic rename).
2. Regenerate companion files with `scripts/render_companions.py`.
3. Rebuild compiled memory with `scripts/build_compiled_memory.py`.
4. In headless mode, write success or failure to `threads_refresh.log`.

Companion and compiled-memory regeneration failures are non-fatal. Note them in the summary but do not roll back a successful tracker write.

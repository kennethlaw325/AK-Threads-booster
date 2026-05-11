"""Unit tests for eval_capture + eval_replay."""

from __future__ import annotations

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))

from eval_capture import scrub  # noqa: E402
from eval_replay import (  # noqa: E402
    band_stable, classify, jaccard, normalize_ws,
    parse_predict_band, tokens_top_k,
)


# ---- scrub ----

def test_scrub_discord_user_id():
    text = "hey <@!548857897933602836> check this"
    out, fired = scrub(text)
    assert "<@!548857897933602836>" not in out
    assert "<@REDACTED_USER>" in out
    assert "discord_user_id" in fired


def test_scrub_threads_token():
    token = "THAFZ" + "A" * 150
    text = f"my token: {token}"
    out, fired = scrub(text)
    assert token not in out
    assert "THAFZ_REDACTED" in out
    assert "threads_token" in fired


def test_scrub_email():
    text = "ping kenneth@example.com"
    out, fired = scrub(text)
    assert "kenneth@example.com" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_no_pii_returns_unchanged():
    text = "this is a normal post about AI safety"
    out, fired = scrub(text)
    assert out == text
    assert fired == []


def test_scrub_multiple_categories():
    text = "user <@!12345678901234567> sent sk-abcdefghijklmnopqrstuvwxyz to alice@test.com"
    out, fired = scrub(text)
    assert "discord_user_id" in fired
    assert "openai_key" in fired
    assert "email" in fired
    assert len(set(fired)) == 3


# ---- token / jaccard ----

def test_normalize_ws_collapses_whitespace():
    assert normalize_ws("a   b\t\nc  d") == "a b c d"


def test_tokens_top_k_respects_limit():
    text = "alpha beta gamma delta epsilon zeta"
    out = tokens_top_k(text, 3)
    assert out == {"alpha", "beta", "gamma"}


def test_tokens_top_k_zero_returns_all():
    text = "a b c d"
    assert tokens_top_k(text, 0) == {"a", "b", "c", "d"}


def test_jaccard_identical():
    a = {"x", "y", "z"}
    assert jaccard(a, a) == 1.0


def test_jaccard_disjoint():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial():
    a = {"x", "y", "z"}
    b = {"y", "z", "w"}
    assert jaccard(a, b) == pytest.approx(2 / 4)


def test_jaccard_empty_inputs_match():
    assert jaccard(set(), set()) == 1.0


# ---- predict band ----

def test_parse_predict_band_basic():
    text = "Predicted views: 600 / 1500 / 4500 (low/mid/high)"
    assert parse_predict_band(text) == (600, 1500, 4500)


def test_parse_predict_band_with_commas():
    text = "Predicted views: 1,200 / 3,500 / 8,000"
    assert parse_predict_band(text) == (1200, 3500, 8000)


def test_parse_predict_band_too_few_numbers_returns_none():
    assert parse_predict_band("just one 5") is None


def test_band_stable_identical():
    stable, near = band_stable((600, 1500, 4500), (600, 1500, 4500))
    assert stable is True
    assert near is False


def test_band_stable_near_miss_within_factor_2():
    stable, near = band_stable((600, 1500, 4500), (700, 1800, 5000))
    assert stable is False
    assert near is True


def test_band_stable_regression_outside_factor_2():
    stable, near = band_stable((600, 1500, 4500), (100, 200, 300))
    assert stable is False
    assert near is False


def test_band_stable_handles_none_inputs():
    stable, near = band_stable(None, (1, 2, 3))
    assert stable is False
    assert near is False


# ---- classify ----

def test_classify_stable_on_exact_match():
    assert classify(0.0, True) == "stable"


def test_classify_stable_on_high_jaccard():
    assert classify(0.95, False) == "stable"


def test_classify_drift_on_mid_jaccard():
    assert classify(0.7, False) == "drift"


def test_classify_regression_on_low_jaccard():
    assert classify(0.3, False) == "regression"


# ---- end-to-end CLI smoke ----

def test_capture_no_op_without_env(tmp_path: Path):
    """Without AK_THREADS_EVAL_CAPTURE=1, capture is a no-op (exit 0)."""
    inp = tmp_path / "in.txt"
    out = tmp_path / "out.txt"
    inp.write_text("input text")
    out.write_text("output text")

    env = {k: v for k, v in os.environ.items() if k != "AK_THREADS_EVAL_CAPTURE"}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "eval_capture.py"),
         "--sub-skill", "draft",
         "--input-file", str(inp),
         "--output-file", str(out),
         "--working-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0
    assert not (tmp_path / "eval_candidates.jsonl").exists()


def test_capture_writes_when_env_set(tmp_path: Path):
    inp = tmp_path / "in.txt"
    out = tmp_path / "out.txt"
    inp.write_text("topic about AI safety")
    out.write_text("draft post about safety")

    env = dict(os.environ)
    env["AK_THREADS_EVAL_CAPTURE"] = "1"
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "eval_capture.py"),
         "--sub-skill", "draft",
         "--input-file", str(inp),
         "--output-file", str(out),
         "--working-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    log = tmp_path / "eval_candidates.jsonl"
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert rec["sub_skill"] == "draft"
    assert rec["input"]["content"] == "topic about AI safety"
    assert rec["consented"] is True


def test_replay_end_to_end(tmp_path: Path):
    """Synthetic snapshot + identical replayed → all stable."""
    snap = tmp_path / "snap.jsonl"
    rep = tmp_path / "rep.jsonl"

    snap.write_text(json.dumps({
        "ts": "2026-05-11T11:00:00Z",
        "id": "cand-1",
        "sub_skill": "draft",
        "input": {"type": "raw", "content": "input"},
        "output": {"type": "raw", "content": "alpha beta gamma delta",
                   "latency_ms": 100},
        "version": {"sub_skill": "1.0.0", "root_skill": "2.0.0", "rules_hash": ""},
        "consented": True, "scrubbed": [],
    }) + "\n", encoding="utf-8")

    rep.write_text(json.dumps({
        "candidate_id": "cand-1",
        "output_content": "alpha beta gamma delta",
        "latency_ms": 100,
    }) + "\n", encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "eval_replay.py"),
         "--against", str(snap),
         "--replayed", str(rep),
         "--working-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, check=False,
    )
    # Exit 0 = no regressions
    assert result.returncode == 0, result.stderr
    replay_dirs = list((tmp_path / "eval_replays").iterdir())
    assert len(replay_dirs) == 1
    report = (replay_dirs[0] / "report.md").read_text(encoding="utf-8")
    assert "draft" in report
    assert "stable" in report.lower()


def test_replay_detects_regression(tmp_path: Path):
    """Snapshot content vs totally different replayed → regression exit 1."""
    snap = tmp_path / "snap.jsonl"
    rep = tmp_path / "rep.jsonl"

    snap.write_text(json.dumps({
        "ts": "2026-05-11T11:00:00Z",
        "id": "cand-2",
        "sub_skill": "draft",
        "input": {"type": "raw", "content": "input"},
        "output": {"type": "raw", "content": "alpha beta gamma",
                   "latency_ms": 100},
        "version": {"sub_skill": "1.0.0", "root_skill": "2.0.0", "rules_hash": ""},
        "consented": True, "scrubbed": [],
    }) + "\n", encoding="utf-8")

    rep.write_text(json.dumps({
        "candidate_id": "cand-2",
        "output_content": "completely different unrelated text words",
        "latency_ms": 200,
    }) + "\n", encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "eval_replay.py"),
         "--against", str(snap),
         "--replayed", str(rep),
         "--working-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert result.returncode == 1, "expected non-zero exit on regression"

#!/usr/bin/env python3
"""
Verification gates + JSON extraction — regression test
======================================================
Three defects found on 2026-08-17 while reviewing the Groq migration:

  1. `full_analysis` never passed verify_ai_text, although this module's header
     claimed every AI-generated text did. It is the longer text users read.
  2. T4 was documented in verify_ai_text's docstring and never implemented.
  3. _parse_json discarded two UNFENCED JSON objects, losing an answer the model
     had committed to — reasoning models draft and revise in prose, not only in
     fenced blocks.

Contacts no provider and spends no quota.

Usage:
  python3 test_verification_gates.py
"""
import os
import sys

os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data.cache as cache_mod                                   # noqa: E402

cache_mod.cache_get = lambda *a, **k: None
cache_mod.cache_set = lambda *a, **k: None

import intelligence.claude_ai as ai                              # noqa: E402
from intelligence.verification import verify_ai_text             # noqa: E402

ai.cache_get = lambda *a, **k: None
ai.cache_set = lambda *a, **k: None

results = []


def check(label, condition, detail=""):
    results.append((label, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))


# ── 1. _parse_json ────────────────────────────────────────────────────────────
print("\n_parse_json")
PARSE = [
    ("plain object",              '{"verdict":"BUY 12%"}',                            "BUY 12%"),
    ("fenced, last wins",         '```json\n{"verdict":"D"}\n```\n```json\n{"verdict":"F"}\n```', "F"),
    ("<think> hides a draft",     '<think>{"verdict":"D"}</think>{"verdict":"F"}',    "F"),
    ("unterminated <think>",      '{"verdict":"F"}\n<think>{"verdict":"D"}',          "F"),
    ("two UNFENCED, last wins",   '{"verdict":"FIRST"} then {"verdict":"SECOND"}',    "SECOND"),
    ("three UNFENCED",            '{"verdict":"A"} x {"verdict":"B"} y {"verdict":"C"}', "C"),
    ("malformed last falls back", '{"verdict":"GOOD"} then {"verdict": broken',       "GOOD"),
    ("brace inside a string",     '{"verdict":"use { carefully"}',                    "use { carefully"),
    ("escaped quotes",            '{"verdict":"say \\"hi\\" now"}',                   'say "hi" now'),
    ("array is not a verdict",    '[1,2,3]',                                          None),
    ("garbage",                   'nope',                                             None),
    ("unbalanced brace",          '{"verdict":"x"',                                   None),
]
for label, raw, want in PARSE:
    got = ai._parse_json(raw)
    val = got.get("verdict") if isinstance(got, dict) else got
    check(label, val == want, f"-> {val!r}")

# ── 2. T4 warns, never suppresses ─────────────────────────────────────────────
print("\nT4 — names the stock (warn only)")
LONG = "This is a sufficiently long sentence to clear the fifty character minimum, "
ok, out = verify_ai_text("AMZN", LONG + "and it cites 20% growth for AMZN.", "verdict")
check("ticker present -> approved", ok and "AMZN" in out)

ok, out = verify_ai_text("AMZN", LONG + "Amazon grew 20% last year.", "verdict",
                         company_name="Amazon.com Inc")
check("company name matches via company_name", ok)

ok, out = verify_ai_text("TCS.NS", LONG + "TCS grew 20% last year.", "verdict")
check("base symbol matches (TCS.NS -> TCS)", ok)

text = LONG + "The company grew 20% last year."
ok, out = verify_ai_text("AMZN", text, "verdict")
check("stock never named -> STILL APPROVED (warn, not suppress)", ok and out == text,
      "T4 says 'should'; suppressing would kill readable prose")

# ── 3. T1/T2 still suppress ───────────────────────────────────────────────────
print("\nT1 / T2 still suppress")
ok, out = verify_ai_text("AMZN", "Too short.", "verdict")
check("T1 short text suppressed", (not ok) and "Analysis pending" in out)

ok, out = verify_ai_text("AMZN", LONG + "It has no figures whatsoever for AMZN.", "verdict")
check("T2 no-digit suppressed", (not ok) and "Insufficient specific data" in out)

# ── 4. full_analysis is gated ─────────────────────────────────────────────────
print("\nfull_analysis passes the gate")
PRICE = {"price": 100.0, "change_pct": 1.0, "name": "Amazon.com Inc"}
FUND = {"revenue_growth": 0.2, "gaap_profitable": True, "earnings_surprise_pct": 5.0}

ai._call_ai = lambda s, u, max_tokens=500: (
    '{"verdict":"AMZN grew 20% and holds a 72/100 trust score, a solid result overall.",'
    ' "full_analysis":"short"}'
)
v = ai.get_verdict("AMZN", 72, [], PRICE, FUND, {"1Y": 5.0}, None)
check("weak full_analysis replaced by fallback",
      v.get("full_analysis", "").startswith("Analysis pending"),
      f"-> {v.get('full_analysis','')[:48]!r}")
check("a weak full_analysis does NOT discard a good verdict",
      "20%" in v.get("verdict", ""), f"-> {v.get('verdict','')[:48]!r}")

ai._call_ai = lambda s, u, max_tokens=500: (
    '{"verdict":"AMZN grew 20% and holds a 72/100 trust score, a solid result overall.",'
    ' "full_analysis":"Amazon grew revenue 20% year over year while margins held at 17%,'
    ' and the 6 month move reflects that trajectory rather than sentiment alone."}'
)
v = ai.get_verdict("AMZN", 72, [], PRICE, FUND, {"1Y": 5.0}, None)
check("good full_analysis survives untouched", "20%" in v.get("full_analysis", ""))

# ── summary ───────────────────────────────────────────────────────────────────
failed = [label for label, ok, _ in results if not ok]
print()
if failed:
    print(f"{len(failed)}/{len(results)} FAILED:")
    for label in failed:
        print(f"  - {label}")
    raise SystemExit(1)
print(f"all {len(results)} checks passed")

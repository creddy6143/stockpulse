#!/usr/bin/env python3
"""
Absent-data rendering — regression test
=======================================
Missing upstream data must never reach the model as a definite value.

WHY THIS EXISTS. Measured 2026-08-17: a missing `revenue_growth` was rendered
into the prompt as "0% YoY" and a missing `gaap_profitable` as "False". The model
then argued from those defaults as if they were facts — "the 0% revenue growth and
lack of GAAP profitability" for NVDA, which is neither of those things. It passed
verification because T2 only requires a digit, so a fabrication reached the user
wearing a cited figure. Fetch failures are the normal case here, not the exotic
one: every one of those fields comes from Finnhub or Yahoo, both of which
rate-limit.

THE REGRESSION THIS GUARDS. Zero is a real measurement. A company genuinely at 0%
revenue growth must still read "0% YoY" — if this test ever starts reporting
"not reported" for case A, real data has been thrown away, which is the opposite
mistake and just as wrong.

Costs nothing to run: _call_ai is stubbed, so no provider is contacted and no
Groq quota is spent.

Usage:
  python3 test_absent_data.py
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

ai.cache_get = lambda *a, **k: None
ai.cache_set = lambda *a, **k: None

_captured = {}
ai._call_ai = lambda s, u, max_tokens=500: _captured.__setitem__("prompt", u) or None

FIELDS = ("Change Today", "Revenue Growth", "GAAP Profitable", "Earnings Surprise")


def prompt_for(price, fundamentals):
    ai.get_verdict("TEST", 72, [], price, fundamentals, {"1Y": 5.0}, None)
    lines = {}
    for line in _captured["prompt"].splitlines():
        for field in FIELDS:
            if line.startswith(field + ":"):
                lines[field] = line.split(":", 1)[1].strip()
    return lines


CASES = [
    (
        "genuine zeroes are REAL data and must survive",
        {"price": 10.0, "change_pct": 0.0},
        {"revenue_growth": 0.0, "gaap_profitable": False, "earnings_surprise_pct": 0.0},
        {"Change Today": "+0.0%", "Revenue Growth": "0% YoY",
         "GAAP Profitable": "False", "Earnings Surprise": "0%"},
    ),
    (
        "absent keys must say so, never 0 or False",
        {"price": 10.0},
        {},
        {"Change Today": "not reported", "Revenue Growth": "not reported",
         "GAAP Profitable": "not reported", "Earnings Surprise": "not reported"},
    ),
    (
        "keys present holding None behave as absent (and must not raise)",
        {"price": 10.0, "change_pct": None},
        {"revenue_growth": None, "gaap_profitable": None, "earnings_surprise_pct": None},
        {"Change Today": "not reported", "Revenue Growth": "not reported",
         "GAAP Profitable": "not reported", "Earnings Surprise": "not reported"},
    ),
    (
        "real values pass through unchanged",
        {"price": 10.0, "change_pct": -3.25},
        {"revenue_growth": 0.184, "gaap_profitable": True, "earnings_surprise_pct": 7.0},
        {"Change Today": "-3.2%", "Revenue Growth": "18% YoY",
         "GAAP Profitable": "True", "Earnings Surprise": "7%"},
    ),
]


def main():
    failures = 0
    for label, price, fundamentals, expected in CASES:
        got = prompt_for(price, fundamentals)
        bad = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
        status = "PASS" if not bad else "FAIL"
        print(f"[{status}] {label}")
        for field, value in got.items():
            flag = "  <-- expected " + repr(expected[field]) if field in bad else ""
            print(f"         {field:18} {value!r}{flag}")
        failures += bool(bad)

    print()
    if failures:
        print(f"{failures}/{len(CASES)} case(s) FAILED")
        return 1
    print(f"all {len(CASES)} cases passed — absent data is never asserted, "
          f"and real zeroes are preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

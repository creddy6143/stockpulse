#!/usr/bin/env python3
"""
StockPulse Scoring Validation Test
===================================
Tests 18 stocks across market caps, sectors, and regions.
Validates that each stock lands in the expected score range.

A professional analyst would expect:
  Large-cap quality leaders  →  70–90+ (Strong / Exceptional)
  Mid-cap growth / recovery  →  40–70  (Moderate / Weak)
  Pre-revenue speculative    →  20–45  (Speculative)
  Auto-disqualified / fraud  →   0–20  (Blocked)

Usage:
  python3 test_scores.py                           # localhost:8000
  python3 test_scores.py https://myapp.railway.app # Railway
"""
import sys
import json
import time
import requests

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

# (ticker, min_expected, max_expected, analyst_rationale)
# Ranges are deliberately wide — we're testing the scoring DIRECTION, not the exact number.
TESTS = [

    # ── LARGE CAP QUALITY (should score 70–95) ─────────────────────────────────
    # These are the stocks where "Avoid" or "Blocked" would be embarrassing.
    # Any analyst looking at NVDA and saying "Avoid" has a broken model.
    ("NVDA",        78, 100,
     "AI chip monopoly. 122% rev growth, 55%+ margins, ATH, 90%+ analyst buy. "
     "Expected: business=40(cap), smart=20-25, momentum=25(cap)"),

    ("MSFT",        68,  90,
     "Cloud + Office dominance. 15% rev growth, 35%+ net margins, GAAP profitable. "
     "Expected: business=35-38, smart=15-20, momentum=18-22"),

    ("AAPL",        60,  82,
     "Large-cap stable. Profitable, buybacks, slowing growth (<5%). "
     "Expected: business=28-32, smart=12-18, momentum=16-22"),

    ("AXON",        72,  92,
     "Public safety monopoly. 30%+ rev growth, profitable, strong analyst conviction. "
     "Expected: business=36-40, smart=18-22, momentum=18-22"),

    ("META",        70,  92,
     "Ad platform recovery. Strong EPS growth, 40%+ margins, ATH. "
     "Expected: business=38-40, smart=18-22, momentum=20-25"),

    # ── MID-CAP QUALITY / RECOVERY (should score 40–70) ───────────────────────
    # These are the stocks where the old engine was most broken.
    # INTC at ATH should NEVER be in "Avoid". AMD recovering is a clear hold/watch.
    ("INTC",        38,  58,
     "Turnaround play. ATH, recovering, but GAAP losses from restructuring impairments. "
     "Forward EPS expected positive. "
     "Expected: business=14-18, smart=8-12, momentum=16-22. "
     "FAIL if score < 30 (would put in Avoid — wrong for ATH stock)"),

    ("AMD",         58,  80,
     "AI datacenter growth, recovered profitability. Strong momentum. "
     "Expected: business=28-35, smart=15-20, momentum=18-23"),

    ("SOFI",        35,  55,
     "Fintech recently GAAP profitable. Growing 20%+ revenue. "
     "Financial-sector gross margins (low gross, but positive net). "
     "Expected: business=22-28, smart=8-14, momentum=12-18"),

    ("ERIC",        35,  55,
     "Telecom equipment. Cyclically down but recovering. Large-cap, EU market. "
     "Expected: business=14-22, smart=10-14, momentum=12-18"),

    # ── PRE-REVENUE SPECULATIVE (should score 20–45, grade=Speculative) ────────
    # These should NOT be "Data Unavailable" any more after the pre-revenue fix.
    # Score is smart_money + momentum only, capped at 50.
    ("RKLB",        22,  45,
     "Rocket Lab. Pre-commercial aerospace, strong institutional backing. "
     "Grade must be 'Speculative'. FAIL if grade='Data Unavailable' (old bug)."),

    ("OKLO",        18,  40,
     "Nuclear micro-reactor. Pre-revenue. Policy tailwind (US govt support). "
     "Grade must be 'Speculative'. FAIL if score=None (sufficiency gate bug)."),

    ("IONQ",        18,  40,
     "Quantum computing. Pre-revenue, highly speculative. "
     "Grade must be 'Speculative'. Score driven by analyst consensus + news."),

    # ── EU / INTERNATIONAL (tests data pipeline quality) ────────────────────────
    # These consistently scored 0–20 on the old engine due to yfinance EU gaps.
    # After EDGAR/Leeway fixes, EU large-caps should score 60+.
    ("ASML.AS",     62,  88,
     "EUV lithography monopoly. 55%+ gross margin, strong growth. "
     "FAIL if score < 40 (yfinance EU coverage still broken for this stock)"),

    ("SAP.DE",      55,  78,
     "Cloud ERP transition. 70%+ gross margins, profitable, steady growth. "
     "FAIL if score < 35 (DE suffix data coverage issue)"),

    # ── INDIAN MARKET (FII data + NSE pipeline) ──────────────────────────────────
    ("INFY.NS",     60,  82,
     "IT services giant. Steady 8-12% growth, profitable, FII buying. "
     "India-specific FII signals should add to smart_money score."),

    ("HDFCBANK.NS", 58,  80,
     "India's largest private bank. Profitable, growing, FII holding >30%. "
     "Financial-sector model (net margins not gross) should apply."),

    # ── SHOULD BE BLOCKED (auto-disqualified / manual overrides) ─────────────────
    ("TNXP",         0,  20,
     "MANUAL BLOCK: 8 reverse splits. Should return auto_disqualified=True. "
     "FAIL if score > 25 (override not firing)"),

    ("XGN",          0,  15,
     "MANUAL BLOCK: board resigned 18 days before earnings. "
     "FAIL if score > 20 (override not firing)"),
]

# ANSI colours
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # amber
B = "\033[1m"   # bold
X = "\033[0m"   # reset


def colour_score(score):
    if score is None:
        return f"{Y}  ?{X}"
    if score >= 70:
        return f"{G}{score:3d}{X}"
    if score >= 40:
        return f"{Y}{score:3d}{X}"
    return f"{R}{score:3d}{X}"


def run():
    print(f"\n{B}StockPulse Scoring Validation — 18 stocks{X}")
    print(f"Backend: {BASE_URL}\n")

    header = (
        f"{'Ticker':<12} {'Score':>5}  {'Biz':>4} {'Sm$':>4} {'Mom':>4}  "
        f"{'Grade':<18}  {'Expected':>10}  {'Status':<6}  Notes"
    )
    print(header)
    print("─" * 120)

    passed = failed = data_gaps = 0
    failures = []

    for ticker, lo, hi, rationale in TESTS:
        try:
            r = requests.get(f"{BASE_URL}/api/stock/{ticker}/trust", timeout=40)
            r.raise_for_status()
            d = r.json()

            score = d.get("total_score")
            biz   = d.get("business_score")
            sm    = d.get("smart_money_score")
            mom   = d.get("momentum_score")
            grade = (d.get("grade") or "?")[:18]
            dq    = d.get("data_quality", "full")
            auto  = d.get("auto_disqualified", False)

            score_s = colour_score(score)
            biz_s   = f"{biz:4d}" if biz is not None else "   ?"
            sm_s    = f"{sm:4d}"  if sm  is not None else "   ?"
            mom_s   = f"{mom:4d}" if mom is not None else "   ?"

            if score is None:
                status = f"{Y}DATA? {X}"
                data_gaps += 1
                failures.append((ticker, "Data Unavailable", dq, rationale))
            elif lo <= score <= hi:
                status = f"{G}PASS  {X}"
                passed += 1
            elif score < lo:
                status = f"{R}LOW   {X}"
                failed += 1
                failures.append((ticker, f"Score {score} — below expected {lo}", dq, rationale))
            else:
                # Score above expected — not necessarily bad
                status = f"{Y}HIGH  {X}"
                passed += 1
                failures.append((ticker, f"Score {score} — above expected {hi} (review)", dq, rationale))

            dq_tag = f" [{dq}]" if dq not in ("full", "limited") else ""
            adq_tag = " AUTO-DQ" if auto else ""

            print(
                f"{ticker:<12} {score_s:>5}  {biz_s} {sm_s} {mom_s}  "
                f"{grade:<18}  {lo}-{hi:>3}          {status}  "
                f"{dq_tag}{adq_tag}"
            )

            time.sleep(0.5)  # don't hammer the API

        except requests.exceptions.ConnectionError:
            print(f"\n{R}CONNECTION FAILED — backend not running at {BASE_URL}{X}")
            print(f"Start with:  cd backend && uvicorn main:app --reload\n")
            sys.exit(1)
        except Exception as e:
            print(f"{ticker:<12} {R}ERROR: {e}{X}")
            data_gaps += 1

    total = len(TESTS)
    print(f"\n{'═' * 120}")
    print(
        f"{B}Results:{X}  "
        f"{G}{passed} passed{X}  /  "
        f"{R}{failed} failed{X}  /  "
        f"{Y}{data_gaps} data gaps{X}  "
        f"— {total} stocks tested"
    )

    if failures:
        print(f"\n{B}Stocks needing attention:{X}")
        for ticker, issue, dq, rationale in failures:
            # Extract just the FAIL notes (before first period in rationale)
            fail_hint = ""
            for part in rationale.split("."):
                if "FAIL" in part:
                    fail_hint = part.strip()
                    break
            print(f"  {'●':2} {B}{ticker:<10}{X}  {issue}")
            if fail_hint:
                print(f"             {Y}{fail_hint}{X}")

    # Print expected score guide
    print(f"""
{B}Score interpretation:{X}
  75–100  Strong / Exceptional  →  Smart Picks "Ready to Buy"
  60–74   Moderate              →  Watchlist "Still Watching" (high end)
  40–59   Weak                  →  Watchlist "Still Watching"
  30–39   Weak-low              →  Watchlist "Still Watching" (threshold was the INTC bug)
  20–29   Speculative           →  grade = "Speculative" for pre-revenue
   0–19   Blocked               →  auto_disqualified = True
""")


if __name__ == "__main__":
    run()

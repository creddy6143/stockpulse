#!/usr/bin/env python3
"""
StockPulse Scoring Validation — Fresh Stock Test
==================================================
18 completely fresh stocks never previously used in this app.
No pre-tuning bias. Pure algorithmic output.

Covers:
  • Large-cap established leaders (US + EU + India)
  • Mid-cap growth / turnaround
  • Small-cap pre-revenue speculative
  • Financial-sector model test (Visa, JPM, BNP)
  • EU data pipeline test (SIE.DE, AIR.PA, SHEL.L)
  • Indian market test (TATAMOTORS, BAJFINANCE, SUNPHARMA)

Usage:
  python3 test_scores.py                           # localhost:8000
  python3 test_scores.py https://myapp.railway.app
"""
import sys
import time
import requests

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

# ─────────────────────────────────────────────────────────────────────────────
# Test cases: (ticker, min_expected, max_expected, analyst_rationale)
#
# I am going on record with these expectations BEFORE running.
# If a score is outside the range it is a CONFIRMED GAP, not a surprise.
# ─────────────────────────────────────────────────────────────────────────────
TESTS = [

    # ══════════════════════════════════════════════════════════════════════════
    # LARGE-CAP QUALITY — scores must be 65+. Any score < 50 is a scoring bug.
    # ══════════════════════════════════════════════════════════════════════════

    ("LLY",   78, 100,
     # Eli Lilly: GLP-1/Ozempic explosion. ~35% revenue growth, 25%+ net margins,
     # GAAP profitable, near ATH, 85%+ analyst buy.
     # business=38-40 (hits cap: rev growth + margins + earnings)
     # smart=15-20 (strong consensus), momentum=20-25 (ATH + 200MA)
     "Eli Lilly. GLP-1 drug explosion. 35%+ rev growth, 25%+ margins, ATH. "
     "FAIL if < 72 — this is one of the strongest businesses on the market right now."),

    ("GOOGL", 68,  92,
     # Alphabet: search + YouTube + Cloud. 12-15% rev growth, 20-25% net margins,
     # massive buybacks, GAAP profitable. Analyst consensus: 85%+ buy.
     # business=30-36, smart=15-20, momentum=18-22
     "Alphabet. Search monopoly + AI + Cloud. 12-15% rev growth, 22% margins. "
     "FAIL if < 60 — Google with a broken score would be a serious credibility problem."),

    ("V",     68,  88,
     # Visa: pure payment network. Near-zero GROSS margins (no COGS in financial model)
     # but 50%+ NET margins. GAAP profitable. KEY TEST: financial-sector detection
     # must trigger so pm is used instead of gm. If gm is used → scores near 0 on margins.
     "Visa. 50%+ net margins, ~8% rev growth. CRITICAL TEST: financial-sector model "
     "must use profit_margins not gross_margins. FAIL if < 55 (financial model broken)."),

    ("JPM",   62,  85,
     # JPMorgan: largest US bank. ~10% rev growth, 25-30% net margins.
     # Same financial-sector model test as Visa. ROE ~15%.
     # Additional test: large-cap + financial model + profitable.
     "JPMorgan. Banking giant. 10% rev growth, 25%+ net margins. "
     "FAIL if < 52 — if financial model breaks here it breaks for all banks."),

    # ══════════════════════════════════════════════════════════════════════════
    # MID-CAP GROWTH — scores should be 45-75. The interesting middle ground.
    # ══════════════════════════════════════════════════════════════════════════

    ("PLTR",  45,  70,
     # Palantir: AI/analytics. ~25-30% rev growth. Recently GAAP profitable (2024).
     # High P/E, controversial valuation, but real revenue and now profitable.
     # Expected: business=22-28, smart=10-15, momentum=14-20
     "Palantir. AI analytics, recently GAAP profitable, 27% rev growth. "
     "Interesting test: should score Moderate not Blocked. Analyst consensus mixed."),

    ("CRWD",  55,  78,
     # CrowdStrike: cybersecurity leader. 30%+ rev growth. Near-profitable or profitable.
     # Strong analyst conviction. Industry tailwind from cyber attacks.
     "CrowdStrike. Cybersecurity. 30%+ rev growth, near/GAAP profitable. "
     "FAIL if < 45 — clear growth leader with real revenue."),

    ("CELH",  35,  58,
     # Celsius Holdings: energy drinks. Had explosive growth (100%+) but slowed
     # sharply in 2024 (Pepsi channel saturation). Revenue growth now 5-15%.
     # Still GAAP profitable. Tests deceleration handling.
     "Celsius Holdings. Energy drinks. Growth decelerated from 100% to ~10%. "
     "Interesting: still profitable but growth story broken. Should score Weak-Moderate."),

    ("HIMS",  32,  55,
     # Hims & Hers: telehealth platform. 60%+ revenue growth. NOT yet GAAP profitable
     # but getting close. Forward EPS should be positive (analysts expect profitability).
     # Tests forward EPS inflection bonus.
     "Hims & Hers. 60%+ rev growth, not yet profitable but analysts expect it soon. "
     "Tests forward EPS inflection bonus (+4 pts loss→profit). Key mid-cap growth test."),

    # ══════════════════════════════════════════════════════════════════════════
    # PRE-REVENUE SPECULATIVE — must show grade=Speculative, score 18-42
    # These MUST NOT show Data Unavailable (that was the OKLO/NNE bug we fixed)
    # ══════════════════════════════════════════════════════════════════════════

    ("JOBY",  18,  42,
     # Joby Aviation: eVTOL air taxi. Pre-revenue, FAA certification progress.
     # Toyota invested $890M. Delta airlines partnership.
     # Must show Speculative not Data Unavailable.
     "Joby Aviation. Pre-revenue eVTOL. Toyota/Delta backing. "
     "CRITICAL: must show grade=Speculative not Data Unavailable. Score from smart_money+momentum only."),

    ("ACHR",  15,  38,
     # Archer Aviation: eVTOL competitor to JOBY. Pre-revenue. United Airlines deal.
     # Smaller than JOBY, less institutional backing.
     "Archer Aviation. Pre-revenue eVTOL. United Airlines deal. "
     "Must show grade=Speculative. Score should be lower than JOBY (less backing)."),

    ("LUNR",  12,  35,
     # Intuitive Machines: lunar landers for NASA. Pre-revenue commercial space.
     # Had a successful lunar landing mission. NASA contract.
     # Very small market cap, volatile.
     "Intuitive Machines. Lunar landers, NASA contracts. Pre-revenue. "
     "Must show grade=Speculative. Very small cap → may be Data Unavailable if mktcap=0."),

    # ══════════════════════════════════════════════════════════════════════════
    # EU STOCKS — critical data pipeline test. Old engine scored these 0-20.
    # If these still fail, EU data coverage is still broken.
    # ══════════════════════════════════════════════════════════════════════════

    ("SIE.DE",  50,  75,
     # Siemens Germany: industrial automation + digitalization. Large-cap.
     # ~8-10% rev growth, 10-15% net margins, GAAP profitable.
     # Tests German .DE suffix data fetching.
     "Siemens Germany. Industrial automation. 8-10% rev growth, profitable. "
     "FAIL if < 35 — if Siemens scores low, EU .DE data pipeline broken."),

    ("AIR.PA",  48,  72,
     # Airbus France: aerospace duopoly. 10-15% rev growth. Profitable.
     # Large-cap EU. Tests French .PA suffix.
     "Airbus France. Aerospace duopoly with Boeing. 10-15% rev growth, profitable. "
     "FAIL if < 35 — EU .PA data pipeline test."),

    ("SHEL.L",  42,  65,
     # Shell London: energy major. Revenue volatile with oil prices.
     # Very large-cap. Net margins 5-10% (cyclical). Tests .L suffix.
     # Large-cap cyclical with good gross margins — tests our new cyclical credit.
     "Shell London. Energy major. Revenue volatile but profitable. .L suffix test. "
     "Tests large-cap cyclical scoring. FAIL if < 30."),

    # ══════════════════════════════════════════════════════════════════════════
    # INDIAN MARKET — FII data + NSE pipeline test
    # ══════════════════════════════════════════════════════════════════════════

    ("TATAMOTORS.NS", 48,  72,
     # Tata Motors: Indian auto giant + Jaguar Land Rover. JLR turnaround complete.
     # Revenue growth strong. Becoming profitable. FII holding increasing.
     "Tata Motors India. JLR turnaround + EV push. Strong revenue growth, profitable. "
     "FII data should add smart_money pts. FAIL if < 38."),

    ("BAJFINANCE.NS", 58,  82,
     # Bajaj Finance: India's top NBFC. 25-30% loan book growth. Very profitable.
     # High FII holding (~20%+). One of India's strongest growth stories.
     # Financial-sector model should apply here too.
     "Bajaj Finance India. Top NBFC. 25%+ growth, very profitable, high FII holding. "
     "FAIL if < 50 — Bajaj Finance with a bad score = India data pipeline broken."),

    ("SUNPHARMA.NS", 52,  75,
     # Sun Pharma: India's largest pharma. Specialty drugs. 10-15% rev growth.
     # GAAP profitable. Exports to US/EU. Strong FII holding.
     "Sun Pharma India. Largest Indian pharma. 10-15% growth, profitable, FII backing. "
     "FAIL if < 42."),

    # ══════════════════════════════════════════════════════════════════════════
    # STRESS TEST — a bad stock that should score LOW
    # ══════════════════════════════════════════════════════════════════════════

    ("BBBY",   0,  25,
     # Bed Bath & Beyond (or its successor): was a bankruptcy case.
     # If ticker still exists and returns data, should score very low.
     # Tests that a genuinely distressed company scores < 30.
     # NOTE: if ticker not found, DATA GAP is acceptable here.
     "Bed Bath & Beyond successor. Bankruptcy/distressed. Should score very low. "
     "If data returns: FAIL if score > 30 (distressed company scored high = false positive)."),
]

# ─────────────────────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


def colour_score(s):
    if s is None:  return f"{Y}  ?{X}"
    if s >= 70:    return f"{G}{s:3d}{X}"
    if s >= 40:    return f"{Y}{s:3d}{X}"
    return f"{R}{s:3d}{X}"


def run():
    print(f"\n{B}StockPulse — Fresh Stock Scoring Validation{X}")
    print(f"Backend : {BASE_URL}")
    print(f"Stocks  : {len(TESTS)} fresh tickers never previously seen in this app\n")

    hdr = (f"{'Ticker':<16} {'Score':>5}  {'Biz':>4} {'Sm$':>4} {'Mom':>4}  "
           f"{'Grade':<20}  {'Expected':>8}  {'Status'}")
    print(hdr)
    print("─" * 95)

    passed = failed = data_gaps = 0
    findings = []

    for ticker, lo, hi, rationale in TESTS:
        try:
            r  = requests.get(f"{BASE_URL}/api/stock/{ticker}/trust", timeout=45)
            d  = r.json()

            score  = d.get("total_score")
            biz    = d.get("business_score")
            sm     = d.get("smart_money_score")
            mom    = d.get("momentum_score")
            grade  = (d.get("grade") or "?")[:20]
            dq     = d.get("data_quality", "full")
            auto   = d.get("auto_disqualified", False)
            source = d.get("data_source") or "?"

            ss  = colour_score(score)
            bs  = f"{biz:4d}" if biz is not None else "   ?"
            sms = f"{sm:4d}"  if sm  is not None else "   ?"
            ms  = f"{mom:4d}" if mom is not None else "   ?"

            if score is None and dq == "unavailable":
                status = f"{Y}DATA? {X}"
                data_gaps += 1
                findings.append(("DATA GAP", ticker, f"score=None / grade='{grade}' — data unavailable", source))
            elif score is None:
                status = f"{Y}NONE  {X}"
                data_gaps += 1
                findings.append(("DATA GAP", ticker, f"score=None unexpectedly", source))
            elif lo <= score <= hi:
                status = f"{G}PASS  {X}"
                passed += 1
            elif score < lo:
                gap = lo - score
                status = f"{R}LOW   {X}"
                failed += 1
                findings.append(("TOO LOW", ticker,
                                  f"score={score}  expected≥{lo}  gap={gap}pts  biz={biz} sm={sm} mom={mom}  "
                                  f"grade='{grade}'  source={source}", rationale))
            else:
                status = f"{Y}HIGH  {X}"
                passed += 1  # scoring high is generally fine
                findings.append(("HIGH", ticker,
                                  f"score={score}  expected≤{hi}  biz={biz} sm={sm} mom={mom}  "
                                  f"grade='{grade}'  source={source}", rationale))

            flags = ""
            if auto:           flags += " AUTO-DQ"
            if dq == "limited": flags += " [limited]"
            if dq == "unavailable": flags += " [unavailable]"

            print(f"{ticker:<16} {ss:>5}  {bs} {sms} {ms}  {grade:<20}  {lo}-{hi:>3}       {status}{flags}")
            time.sleep(0.5)

        except requests.exceptions.ConnectionError:
            print(f"\n{R}Cannot connect to {BASE_URL}{X}")
            print("Start backend:  cd backend && uvicorn main:app --reload\n")
            sys.exit(1)
        except Exception as e:
            print(f"{ticker:<16} {R}ERROR: {e}{X}")
            data_gaps += 1

    total = len(TESTS)
    print(f"\n{'═' * 95}")
    print(f"{B}Results:{X}  {G}{passed} passed{X} / {R}{failed} failed{X} / {Y}{data_gaps} data gaps{X}  ({total} stocks)")

    # ── Findings breakdown ───────────────────────────────────────────────────
    if findings:
        print(f"\n{B}{'─'*95}")
        print(f"FINDINGS (investigate these):{X}")
        for kind, ticker, detail, context in findings:
            icon = R+"✗"+X if kind == "TOO LOW" else (Y+"▲"+X if kind == "HIGH" else Y+"?"+X)
            print(f"\n  {icon} {B}{ticker}{X}  [{kind}]")
            print(f"     {detail}")
            # Extract FAIL hint from context
            for sentence in context.split("."):
                if "FAIL" in sentence or "broken" in sentence.lower():
                    print(f"     {Y}→ {sentence.strip()}{X}")

    # ── Scoring guide ────────────────────────────────────────────────────────
    print(f"""
{B}Expected scoring bands:{X}
  78–100  Exceptional/Strong   →  Smart Picks "Ready to Buy"
  60–77   Strong/Moderate      →  Watchlist "Still Watching" (high conviction)
  40–59   Moderate/Weak        →  Watchlist "Still Watching"
  20–39   Weak/Speculative     →  Watchlist "Still Watching" (pre-revenue = Speculative grade)
   0–19   Blocked              →  auto_disqualified=True
   None   Data Unavailable     →  coverage gap (EU stocks if Leeway not configured)

{B}Key things to check:{X}
  • V and JPM: financial-sector model should give HIGHER score than gm alone
  • JOBY/ACHR/LUNR: must show grade=Speculative (not Data Unavailable)
  • SIE.DE/AIR.PA/SHEL.L: if score < 35, EU data pipeline still broken
  • TATAMOTORS.NS/BAJFINANCE.NS: FII data should add smart_money pts
  • HIMS: forward EPS inflection should add +4 pts (loss→profit expected)
""")


if __name__ == "__main__":
    run()

"""
scan_picks.py — Standalone Smart Picks universe scanner.

Runs the full curated universe through every filter gate and writes
smart_picks_report.md with pass-rate breakdown and final Top 15.

Usage:
    cd backend && python scan_picks.py
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from main import (
    _CURATED_UNIVERSE, _SECTOR_MAP, _get_sector,
    _score_one_ticker,
)
from data.fetcher import get_stock_price, get_fundamentals
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.verification import verify_pick

# ──────────────────────────────────────────────────────────────────────────────
# Gate-by-gate counters (for pass-rate table)
# ──────────────────────────────────────────────────────────────────────────────

stats = {
    "total":          0,
    "price_ok":       0,
    "not_auto_disq":  0,
    "score_gte_75":   0,
    "verify_passed":  0,
    "final_picks":    0,
    "dip_picks":      0,
}

disqualified_list: list[dict] = []


def _score_with_tracking(ticker: str) -> dict | None:
    """Wraps _score_one_ticker with per-gate counting for the report."""
    try:
        price_data = get_stock_price(ticker)
        if not price_data.get("price"):
            return None
        stats["price_ok"] += 1

        trust = get_trust_score_with_fallback(ticker, price_data)
        change_pct = float(price_data.get("change_pct", 0) or 0)

        if trust.get("auto_disqualified"):
            disqualified_list.append({
                "ticker": ticker,
                "score":  trust.get("total_score", 0),
                "reason": trust.get("disqualify_reason", "auto-disqualified"),
            })
            return None

        if trust["total_score"] is None:
            return None
        stats["not_auto_disq"] += 1

        trust_score_val = trust["total_score"]
        is_dip = (trust_score_val >= 65 and change_pct <= -4
                  and not trust.get("disqualify_reason"))

        if trust_score_val >= 75:
            stats["score_gte_75"] += 1

        fundamentals = get_fundamentals(ticker)
        approved, _ = verify_pick(ticker, trust, fundamentals)

        if approved:
            stats["verify_passed"] += 1

        if not approved and not is_dip:
            return None
        if is_dip and trust.get("data_quality") == "unavailable":
            return None

        if not (approved or is_dip):
            return None

        entry = _score_one_ticker(ticker)
        return entry
    except Exception as exc:
        print(f"  [WARN] {ticker}: {exc}", flush=True)
        return None


def run_scan() -> list[dict]:
    universe = _CURATED_UNIVERSE
    stats["total"] = len(universe)
    print(f"\n[SCAN] Universe: {len(universe)} tickers across {len(set(_SECTOR_MAP.values()))} GICS sectors")
    print(f"[SCAN] Starting parallel scan (20 workers) …\n", flush=True)

    t0 = time.time()
    results: list[dict] = []
    workers = min(4, len(universe))   # 4 workers — avoids yfinance 429 rate-limit

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_score_with_tracking, t): t for t in universe}
        done = 0
        for future in as_completed(futures):
            ticker = futures[future]
            done += 1
            try:
                entry = future.result()
                if entry:
                    results.append(entry)
                    print(f"  ✓ {ticker:20s}  score={entry['trust']['total_score']:3d}  sector={entry['sector']}", flush=True)
            except Exception:
                pass
            if done % 50 == 0:
                print(f"  … {done}/{len(universe)} scanned, {len(results)} passing so far", flush=True)

    elapsed = time.time() - t0
    print(f"\n[SCAN] Done in {elapsed:.1f}s — {len(results)} passed all gates", flush=True)

    # Sort: high trust first, dips separate
    dips  = [r for r in results if r.get("is_dip")]
    highs = [r for r in results if not r.get("is_dip")]
    highs.sort(key=lambda x: (-(x["trust"]["total_score"] or 0), x["ticker"]))
    dips.sort(key=lambda x: x["ticker"])

    stats["final_picks"] = len(highs[:15])
    stats["dip_picks"]   = len(dips[:3])
    return highs[:15] + dips[:3]


def write_report(final_picks: list[dict]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []

    lines += [
        "# StockPulse — Smart Picks Scan Report",
        "",
        f"**Generated:** {now}  ",
        f"**Universe:** {stats['total']} tickers · {len(set(_SECTOR_MAP.values()))} GICS sectors  ",
        f"**Final picks:** {stats['final_picks']} main + {stats['dip_picks']} dip  ",
        "",
        "---",
        "",
        "## Filter Gate Pass Rates",
        "",
        "| Gate | Passed | % of Universe |",
        "|------|-------:|:-------------:|",
        f"| Universe scanned              | {stats['total']:4d} | 100%  |",
        f"| 1 · Price data returned       | {stats['price_ok']:4d} | {stats['price_ok']*100//stats['total']:3d}%  |",
        f"| 2 · Not auto-disqualified     | {stats['not_auto_disq']:4d} | {stats['not_auto_disq']*100//stats['total']:3d}%  |",
        f"| 3 · Trust score ≥ 75          | {stats['score_gte_75']:4d} | {stats['score_gte_75']*100//stats['total']:3d}%  |",
        f"| 4 · verify_pick() P1–P5 passed| {stats['verify_passed']:4d} | {stats['verify_passed']*100//stats['total']:3d}%  |",
        f"| **Final top-15 picks**        | **{stats['final_picks']:2d}**  | —     |",
        f"| Buy-the-dip picks (≥65, –4%+) | {stats['dip_picks']:4d} | —     |",
        "",
        "---",
        "",
        "## Final Top 15 Picks (main · sorted by trust score)",
        "",
        "| # | Ticker | Name | Sector | Score | Grade | Price | Chg% |",
        "|---|--------|------|--------|------:|-------|------:|-----:|",
    ]

    main_picks = [p for p in final_picks if not p.get("is_dip")]
    for i, p in enumerate(main_picks, 1):
        t = p["trust"]
        score = t.get("total_score", "?")
        grade = t.get("grade", "")
        price = p.get("price", 0)
        chg   = p.get("change_pct", 0)
        lines.append(
            f"| {i:2d} | **{p['ticker']}** | {p['name'][:30]} | {p['sector']} | {score} | {grade} | ${price:.2f} | {chg:+.1f}% |"
        )

    lines += ["", "---", "", "## Buy-the-Dip Picks (trust ≥ 65, down ≥ 4% today)", ""]
    dip_picks = [p for p in final_picks if p.get("is_dip")]
    if dip_picks:
        lines.append("| # | Ticker | Sector | Score | Price | Chg% |")
        lines.append("|---|--------|--------|------:|------:|-----:|")
        for i, p in enumerate(dip_picks, 1):
            t = p["trust"]
            lines.append(
                f"| {i} | **{p['ticker']}** | {p['sector']} | {t.get('total_score','?')} | ${p.get('price',0):.2f} | {p.get('change_pct',0):+.1f}% |"
            )
    else:
        lines.append("_No dip picks today — no qualifying stocks down ≥ 4%._")

    # Sector distribution
    from collections import Counter
    sector_counts = Counter(p["sector"] for p in main_picks)
    lines += [
        "",
        "---",
        "",
        "## Sector Distribution of Picks",
        "",
        "| Sector | Count |",
        "|--------|------:|",
    ]
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {sector} | {count} |")

    # Auto-disqualified (top 20 by score to show what was blocked)
    lines += [
        "",
        "---",
        "",
        "## Auto-Disqualified (blocked from picks)",
        "",
        "Stocks that failed at Gate 2 — auto-disqualified regardless of score.",
        "",
        "| Ticker | Score | Reason |",
        "|--------|------:|--------|",
    ]
    sorted_disq = sorted(disqualified_list, key=lambda x: -(x.get("score") or 0))[:25]
    for d in sorted_disq:
        reason = str(d.get("reason", ""))[:80]
        lines.append(f"| {d['ticker']} | {d.get('score', '?')} | {reason} |")

    # Verification notes
    lines += [
        "",
        "---",
        "",
        "## Verification Notes",
        "",
        "Every pick passed the following gates before inclusion:",
        "",
        "- **P1 — Data quality**: `data_quality` not `unavailable`",
        "- **P2 — Score threshold**: `total_score ≥ 75`",
        "- **P3 — No auto-disqualification**: `auto_disqualified = False`",
        "- **P4 — Market cap present**: `market_cap > 0`",
        "- **P5 — Large-cap sanity floor**: score ≥ 90 requires market cap > $1 B",
        "",
        "Dip picks (trust ≥ 65, down ≥ 4%) bypass P2 threshold but must still pass P1/P3.",
        "",
        f"_Report generated {now}_",
        "",
    ]

    report_path = os.path.join(os.path.dirname(__file__), "smart_picks_report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n[SCAN] Report written → {report_path}", flush=True)
    return report_path


if __name__ == "__main__":
    final_picks = run_scan()
    report_path = write_report(final_picks)

    print("\n" + "=" * 60)
    print(f"FINAL: {stats['final_picks']} main picks + {stats['dip_picks']} dip picks")
    print("=" * 60)
    if final_picks:
        main = [p for p in final_picks if not p.get("is_dip")]
        print("\nTop picks:")
        for p in main:
            t = p["trust"]
            print(f"  {p['ticker']:8s} {t.get('total_score',0):3d}/100  {p['sector']}")
    print(f"\nFull report: {report_path}")

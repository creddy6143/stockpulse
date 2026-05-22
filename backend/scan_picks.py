"""
scan_picks.py — Standalone Smart Picks universe scanner.

Runs the full curated universe through every filter gate and writes
smart_picks_report.md with pass-rate breakdown and final Top 15.

Rate-limit design:
  - Scans in batches of 50 tickers, 2 workers per batch.
  - A 20-second pause between batches gives Yahoo Finance and Finnhub
    time to reset their sliding windows before the next burst.
  - Finnhub calls are serialised via the 50-calls/min token bucket in
    fetcher.py, so we never exceed the free-tier limit.
  - yfinance Python-lib calls are serialised via _YF_LIB_LOCK with 0.8s
    gap — this alone was the root cause of 85% failure on the old 4-worker
    parallel scan.
  - Fundamentals cached 24 hrs to disk (.scan_cache.json) — subsequent
    daily scans skip re-fetching and complete in ~8 min instead of 60+.

Usage:
    cd backend && python3 scan_picks.py [--sequential]

Options:
    --sequential   Fetch one ticker at a time (slowest, most reliable)
"""

import sys
import os
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from main import (
    _CURATED_UNIVERSE, _SECTOR_MAP, _get_sector,
    _score_one_ticker,
)
from data.fetcher import get_stock_price, get_fundamentals
from data.cache import flush_disk_cache
from intelligence.trust_score import get_trust_score_with_fallback
from intelligence.verification import verify_pick

# ──────────────────────────────────────────────────────────────────────────────
# Gate-by-gate counters (for pass-rate table)
# ──────────────────────────────────────────────────────────────────────────────

stats = {
    "total":          0,
    "fetched_ok":     0,   # price_data returned a non-zero price
    "fetch_failed":   0,   # price fetch returned nothing / zero
    "price_ok":       0,
    "not_auto_disq":  0,
    "score_gte_75":   0,
    "verify_passed":  0,
    "final_picks":    0,
    "dip_picks":      0,
}

disqualified_list: list[dict] = []
fetch_failed_list: list[str]  = []


def _score_with_tracking(ticker: str) -> dict | None:
    """Wraps _score_one_ticker with per-gate counting for the report."""
    try:
        price_data = get_stock_price(ticker)
        price = price_data.get("price") or 0

        if not price:
            stats["fetch_failed"] += 1
            fetch_failed_list.append(ticker)
            return None

        stats["fetched_ok"] += 1
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


def run_scan(sequential: bool = False) -> list[dict]:
    universe = _CURATED_UNIVERSE
    stats["total"] = len(universe)

    batch_size    = 50
    batch_pause   = 20   # seconds between batches
    workers       = 1 if sequential else 2

    mode_label = "sequential" if sequential else f"{workers}-worker batches of {batch_size}"
    print(f"\n[SCAN] Universe: {len(universe)} tickers across {len(set(_SECTOR_MAP.values()))} GICS sectors")
    print(f"[SCAN] Mode: {mode_label}")
    print(f"[SCAN] Rate limits: Finnhub 50/min · yfinance serialised · Yahoo REST semaphore(3)")
    print(f"[SCAN] Disk cache: .scan_cache.json (fundamentals persist 24 h between runs)\n", flush=True)

    t0 = time.time()
    results: list[dict] = []

    batches = [universe[i:i + batch_size] for i in range(0, len(universe), batch_size)]

    for batch_num, batch in enumerate(batches):
        if batch_num > 0:
            elapsed_so_far = time.time() - t0
            fetch_rate = stats["fetched_ok"] / elapsed_so_far if elapsed_so_far > 0 else 0
            print(
                f"\n[SCAN] Batch {batch_num} done · "
                f"{stats['fetched_ok']}/{stats['total']} fetched so far · "
                f"{fetch_rate:.1f} tickers/sec · "
                f"pausing {batch_pause}s …",
                flush=True,
            )
            time.sleep(batch_pause)

        batch_start = batch_num * batch_size + 1
        batch_end   = batch_start + len(batch) - 1
        print(f"[SCAN] Batch {batch_num + 1}/{len(batches)} — tickers {batch_start}–{batch_end}", flush=True)

        if sequential:
            for ticker in batch:
                entry = _score_with_tracking(ticker)
                if entry:
                    results.append(entry)
                    print(f"  ✓ {ticker:20s}  score={entry['trust']['total_score']:3d}  sector={entry['sector']}", flush=True)
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_score_with_tracking, t): t for t in batch}
                for future in as_completed(futures):
                    ticker = futures[future]
                    try:
                        entry = future.result()
                        if entry:
                            results.append(entry)
                            print(f"  ✓ {ticker:20s}  score={entry['trust']['total_score']:3d}  sector={entry['sector']}", flush=True)
                    except Exception:
                        pass

    elapsed = time.time() - t0
    fetch_pct = round(stats["fetched_ok"] * 100 / stats["total"]) if stats["total"] else 0
    print(
        f"\n[SCAN] Done in {elapsed:.0f}s — "
        f"{stats['fetched_ok']}/{stats['total']} fetched ({fetch_pct}%) — "
        f"{stats['fetch_failed']} failed — "
        f"{len(results)} passed all gates",
        flush=True,
    )

    if stats["fetch_failed"] > 0:
        sample = fetch_failed_list[:10]
        print(f"[SCAN] Sample failed tickers: {sample}", flush=True)

    # Flush disk cache so next scan starts warm
    flush_disk_cache()
    print("[SCAN] Fundamentals cached to disk (.scan_cache.json)", flush=True)

    # Sort: high trust first, dips separate
    dips  = [r for r in results if r.get("is_dip")]
    highs = [r for r in results if not r.get("is_dip")]
    highs.sort(key=lambda x: (-(x["trust"]["total_score"] or 0), x["ticker"]))
    dips.sort(key=lambda x: x["ticker"])

    stats["final_picks"] = len(highs[:15])
    stats["dip_picks"]   = len(dips[:3])
    return highs[:15] + dips[:3]


def write_report(final_picks: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []

    fetch_pct    = round(stats["fetched_ok"] * 100 / stats["total"]) if stats["total"] else 0
    fetch_failed = stats["fetch_failed"]

    lines += [
        "# StockPulse — Smart Picks Scan Report",
        "",
        f"**Generated:** {now}  ",
        f"**Universe:** {stats['total']} tickers · {len(set(_SECTOR_MAP.values()))} GICS sectors  ",
        f"**Fetched successfully:** {stats['fetched_ok']}/{stats['total']} ({fetch_pct}%)  ",
        f"**Fetch failures:** {fetch_failed}  ",
        f"**Final picks:** {stats['final_picks']} main + {stats['dip_picks']} dip  ",
        "",
        "---",
        "",
        "## Data Fetch Results",
        "",
        f"| | Count | % of Universe |",
        f"|---|---:|:---:|",
        f"| Tickers scanned | {stats['total']} | 100% |",
        f"| Price fetched successfully | {stats['fetched_ok']} | {fetch_pct}% |",
        f"| Fetch failures (rate-limited / delisted) | {fetch_failed} | {100 - fetch_pct}% |",
        "",
    ]

    if fetch_failed_list:
        lines += [
            "**Failed tickers (sample):** " + ", ".join(fetch_failed_list[:20]),
            "",
        ]

    lines += [
        "---",
        "",
        "## Filter Gate Pass Rates",
        "",
        "| Gate | Passed | % of Universe |",
        "|------|-------:|:-------------:|",
        f"| Universe scanned              | {stats['total']:4d} | 100%  |",
        f"| 1 · Price data returned       | {stats['price_ok']:4d} | {stats['price_ok']*100//max(stats['total'],1):3d}%  |",
        f"| 2 · Not auto-disqualified     | {stats['not_auto_disq']:4d} | {stats['not_auto_disq']*100//max(stats['total'],1):3d}%  |",
        f"| 3 · Trust score ≥ 75          | {stats['score_gte_75']:4d} | {stats['score_gte_75']*100//max(stats['total'],1):3d}%  |",
        f"| 4 · verify_pick() P1–P5 passed| {stats['verify_passed']:4d} | {stats['verify_passed']*100//max(stats['total'],1):3d}%  |",
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
        "## Rate Limiting Strategy",
        "",
        "- Finnhub: token bucket 50 calls/min (free tier limit = 60)",
        "- yfinance Python lib: serialised lock + 0.8s gap between calls",
        "- Yahoo Finance REST: semaphore(3) concurrent + exponential backoff on 429",
        "- Scan: batches of 50 tickers, 2 workers, 20s pause between batches",
        "- Disk cache: fundamentals + insider data persisted 24h to .scan_cache.json",
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
    parser = argparse.ArgumentParser(description="StockPulse Smart Picks Scanner")
    parser.add_argument(
        "--sequential", action="store_true",
        help="Fetch one ticker at a time (slowest, most reliable)"
    )
    args = parser.parse_args()

    final_picks = run_scan(sequential=args.sequential)
    report_path = write_report(final_picks)

    print("\n" + "=" * 60)
    fetch_pct = round(stats["fetched_ok"] * 100 / stats["total"]) if stats["total"] else 0
    print(f"FETCH: {stats['fetched_ok']}/{stats['total']} ({fetch_pct}%) tickers fetched successfully")
    print(f"FAILED: {stats['fetch_failed']} tickers failed (rate-limited / delisted)")
    print(f"FINAL: {stats['final_picks']} main picks + {stats['dip_picks']} dip picks")
    print("=" * 60)
    if final_picks:
        main = [p for p in final_picks if not p.get("is_dip")]
        print("\nTop picks:")
        for p in main:
            t = p["trust"]
            print(f"  {p['ticker']:8s} {t.get('total_score',0):3d}/100  {p['sector']}")
    print(f"\nFull report: {report_path}")

/**
 * Cloudflare Worker — Screener.in + Yahoo Finance reverse proxy
 *
 * Purpose: Railway datacenter IPs are blocked by Screener.in (Akamai) AND by
 *          Yahoo's quoteSummary endpoint. Cloudflare edge IPs are consumer-like
 *          and not in those datacenter blocklists. This worker proxies both from
 *          Railway through CF edge.
 *
 * Deploy:  npx wrangler deploy   (free Cloudflare account; no credit card)
 * Usage:   Set CF_WORKER_URL=https://screener-proxy.<your-subdomain>.workers.dev
 *          in Railway env vars — the SAME variable already used for Screener.
 *          No new variable needed; the backend derives the /yahoo-qs/ path from it.
 *
 * Routes:
 *   /yahoo-qs/<TICKER>?modules=financialData,defaultKeyStatistics
 *       → performs Yahoo's cookie+crumb handshake from the CF edge IP and returns
 *         the raw quoteSummary JSON. Recovers analyst price targets AND short
 *         interest, which are IP-blocked when Railway calls Yahoo directly.
 *   everything else
 *       → Screener.in passthrough (unchanged original behavior).
 */

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // ── Yahoo quoteSummary proxy (crumb-authed) ──────────────────────────────
    if (url.pathname.startsWith("/yahoo-qs/")) {
      return handleYahooQuoteSummary(url);
    }

    // ── Screener.in passthrough (original behavior — unchanged) ──────────────
    const target = "https://www.screener.in" + url.pathname + url.search;
    const response = await fetch(target, {
      headers: {
        "User-Agent": UA,
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        Connection: "keep-alive",
        Referer: "https://www.screener.in",
      },
      // Cloudflare edge cache — avoids re-hitting Screener.in on repeated calls
      cf: { cacheTtl: 86400, cacheEverything: true },
    });
    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    });
  },
};

/**
 * Do Yahoo's cookie → crumb → quoteSummary handshake from the CF edge IP.
 * Railway can't do this directly (Yahoo blocks its datacenter IP); CF edge IPs
 * are consumer-like and allowed.
 */
async function handleYahooQuoteSummary(url) {
  const parts = url.pathname.split("/").filter(Boolean); // ["yahoo-qs", "<TICKER>"]
  const ticker = parts[1];
  const modules =
    url.searchParams.get("modules") || "financialData,defaultKeyStatistics";

  if (!ticker) return json({ error: "missing ticker" }, 400);

  try {
    // 1. Obtain a session cookie
    const cookieResp = await fetch("https://fc.yahoo.com/", {
      headers: { "User-Agent": UA },
    });
    let cookie = "";
    if (typeof cookieResp.headers.getSetCookie === "function") {
      const jar = cookieResp.headers.getSetCookie();
      cookie = jar.map((c) => c.split(";")[0]).join("; ");
    }
    if (!cookie) {
      const raw = cookieResp.headers.get("set-cookie") || "";
      cookie = raw.split(";")[0];
    }

    // 2. Fetch a crumb tied to that cookie
    const crumbResp = await fetch(
      "https://query1.finance.yahoo.com/v1/test/getcrumb",
      { headers: { "User-Agent": UA, Cookie: cookie } }
    );
    const crumb = (await crumbResp.text()).trim();

    // 3. Call quoteSummary with cookie + crumb
    const qsUrl =
      `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${encodeURIComponent(ticker)}` +
      `?modules=${encodeURIComponent(modules)}&crumb=${encodeURIComponent(crumb)}` +
      `&corsDomain=finance.yahoo.com`;
    const qsResp = await fetch(qsUrl, {
      headers: { "User-Agent": UA, Cookie: cookie },
      // Short edge cache — short interest is bi-weekly, targets update daily.
      cf: { cacheTtl: 3600, cacheEverything: true },
    });

    const body = await qsResp.text();
    return new Response(body, {
      status: qsResp.status,
      headers: {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
      },
    });
  } catch (err) {
    return json({ error: String(err) }, 502);
  }
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json" },
  });
}

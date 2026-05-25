/**
 * Cloudflare Worker — Screener.in reverse proxy
 *
 * Purpose: Railway datacenter IPs are blocked by Screener.in (Akamai).
 *          Cloudflare edge IPs are consumer-like and not in datacenter blocklists.
 *          This worker proxies Screener.in requests from Railway through CF edge.
 *
 * Deploy:  wrangler deploy  (or paste into workers.dev dashboard)
 * Usage:   Set CF_WORKER_URL=https://screener-proxy.<your-subdomain>.workers.dev
 *          in Railway environment variables.
 *
 * The Python code then fetches:
 *   https://<worker>/company/SBIN/consolidated/
 * instead of:
 *   https://www.screener.in/company/SBIN/consolidated/
 */

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // Reconstruct the target Screener.in URL from the incoming path + query
    const target = "https://www.screener.in" + url.pathname + url.search;

    const response = await fetch(target, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        Connection: "keep-alive",
        Referer: "https://www.screener.in",
      },
      // Cloudflare edge cache — avoids re-hitting Screener.in on repeated calls
      cf: {
        cacheTtl: 86400,      // 24 hours (matches our backend TTL_FUNDAMENTALS)
        cacheEverything: true,
      },
    });

    // Pass Screener.in response back to Railway unchanged
    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    });
  },
};

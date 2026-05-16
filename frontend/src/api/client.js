/**
 * StockPulse API client
 * All calls to the FastAPI backend at localhost:8000
 */

const BASE = process.env.REACT_APP_API_URL || '';

async function request(path, options = {}) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (err) {
    console.error(`API error: ${path}`, err);
    throw err;
  }
}

// ── MARKET ───────────────────────────────────────────────────────────────────

export const getMarket = () => request('/api/market');

// ── PORTFOLIO ────────────────────────────────────────────────────────────────

export const getPortfolio = () => request('/api/portfolio');

export const addPosition = (ticker, shares, buyPrice, buyDate, notes) =>
  request('/api/portfolio', {
    method: 'POST',
    body: JSON.stringify({ ticker, shares, buy_price: buyPrice, buy_date: buyDate, notes }),
  });

export const updatePosition = (id, data) =>
  request(`/api/portfolio/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });

export const deletePosition = (id) =>
  request(`/api/portfolio/${id}`, { method: 'DELETE' });

// ── WATCHLIST ────────────────────────────────────────────────────────────────

export const getWatchlist = () => request('/api/watchlist');

export const addToWatchlist = (ticker, notes) =>
  request('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify({ ticker, notes }),
  });

export const removeFromWatchlist = (ticker) =>
  request(`/api/watchlist/${ticker}`, { method: 'DELETE' });

// ── STOCK ────────────────────────────────────────────────────────────────────

export const getStock = (ticker) => request(`/api/stock/${ticker}`);
export const getStockTrust = (ticker) => request(`/api/stock/${ticker}/trust`);
export const getStockSignals = (ticker) => request(`/api/stock/${ticker}/signals`);
export const getStockVerdict = (ticker) => request(`/api/stock/${ticker}/verdict`);

// ── ALERTS ───────────────────────────────────────────────────────────────────

export const getAlerts = () => request('/api/alerts');
export const markAlertRead = (id) => request(`/api/alerts/${id}/read`, { method: 'PUT' });

// ── PICKS ────────────────────────────────────────────────────────────────────

export const getPicks = () => request('/api/picks');
export const getDisqualified = () => request('/api/picks/disqualified');

// ── ACCURACY ─────────────────────────────────────────────────────────────────

export const getAccuracy = () => request('/api/accuracy');

// ── STRATEGY ─────────────────────────────────────────────────────────────────

export const getStrategy = () => request('/api/strategy');

// ── HEALTH ───────────────────────────────────────────────────────────────────

export const getHealth = () => request('/api/health');

// ── EARNINGS ─────────────────────────────────────────────────────────────────

export const getEarnings = () => request('/api/earnings');
export const searchTicker = (q) => request(`/api/search?q=${encodeURIComponent(q)}`);
export const clearAllPortfolio = () => request('/api/portfolio/all', { method: 'DELETE' });

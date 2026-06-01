/**
 * StockPulse API client
 * All calls to the FastAPI backend at localhost:8000
 */
import { auth } from '../firebase';

const BASE = process.env.REACT_APP_API_URL || '';

async function getToken() {
  const user = auth.currentUser;
  if (!user) return null;
  try { return await user.getIdToken(); } catch (_) { return null; }
}

async function request(path, options = {}) {
  try {
    const token = await getToken();
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      // Token rejected — sign out so the auth screen appears
      await auth.signOut();
      return null;
    }
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
export const getStockDetail = (ticker) => request(`/api/stock/${ticker}/detail`);
export const getStockSignals = (ticker) => request(`/api/stock/${ticker}/signals`);
export const getStockVerdict = (ticker) => request(`/api/stock/${ticker}/verdict`);

// ── ALERTS ───────────────────────────────────────────────────────────────────

export const getAlerts = () => request('/api/alerts');
export const markAlertRead = (id) => request(`/api/alerts/${id}/read`, { method: 'PUT' });
export const deleteAlert = (id) => request(`/api/alerts/${id}`, { method: 'DELETE' });
export const deleteAllAlerts = () => request('/api/alerts', { method: 'DELETE' });

// ── PICKS ────────────────────────────────────────────────────────────────────

export const getPicks = () => request('/api/picks');
export const refreshPicksScan = () => request('/api/picks/refresh', { method: 'POST' });
export const getPicksStatus = () => request('/api/picks/status');
export const getPicksBySector = (sector) => request(`/api/picks/sector/${encodeURIComponent(sector)}`);
export const getDisqualified = () => request('/api/picks/disqualified');
export const getPicksUniverse = () => request('/api/picks/universe');
export const addPicksUniverse = (ticker) =>
  request('/api/picks/universe', { method: 'POST', body: JSON.stringify({ ticker }) });
export const removePicksUniverse = (ticker) =>
  request(`/api/picks/universe/${encodeURIComponent(ticker)}`, { method: 'DELETE' });

// ── ACCURACY ─────────────────────────────────────────────────────────────────

export const getAccuracy = () => request('/api/accuracy');

// ── STRATEGY ─────────────────────────────────────────────────────────────────

export const getStrategy = () => request('/api/strategy');

export const getStrategyPlaybook = (ticker, situationData) =>
  request(`/api/strategy/${ticker}/playbook`, {
    method: 'POST',
    body: JSON.stringify(situationData),
  });

// ── HEALTH ───────────────────────────────────────────────────────────────────

export const getHealth = () => request('/api/health');
export const clearDataCache = () => request('/api/cache/clear', { method: 'POST' });

// ── EARNINGS ─────────────────────────────────────────────────────────────────

export const getEarnings = () => request('/api/earnings');
export const searchTicker = (q) => request(`/api/search?q=${encodeURIComponent(q)}`);
export const clearAllPortfolio = () => request('/api/portfolio/all', { method: 'DELETE' });

// ── DIPS ─────────────────────────────────────────────────────────────────────

export const getDips = () => request('/api/dips');

// ── PRICE ALERTS ─────────────────────────────────────────────────────────────

export const getPriceAlerts = () => request('/api/price-alerts');
export const createPriceAlert = (data) => request('/api/price-alerts', {method:'POST', body:JSON.stringify(data)});
export const deletePriceAlert = (id) => request(`/api/price-alerts/${id}`, {method:'DELETE'});
export const togglePriceAlert = (id, isActive) => request(`/api/price-alerts/${id}`, {method:'PUT', body:JSON.stringify({is_active:isActive})});

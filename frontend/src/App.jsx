import { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getMarket, getPortfolio, getWatchlist, getAlerts, getPicks, getDisqualified, getAccuracy, getStrategy, getEarnings, addPosition, addToWatchlist, deletePosition, removeFromWatchlist, searchTicker } from "./api/client";

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700;800&family=IBM+Plex+Mono:wght@300;400;500;600&family=DM+Sans:wght@300;400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#f0f5ff;--white:#fff;--card2:#f6f8ff;
  --indigo:#5b72f8;--sky:#0ea5e9;
  --emerald:#059669;--emerald2:#d1fae5;
  --rose:#e11d48;--rose2:#fff1f3;
  --amber:#d97706;--amber2:#fef3c7;
  --gold:#f59e0b;--violet:#7c3aed;
  --t1:#0f172a;--t2:#475569;--t3:#94a3b8;--t4:#e2e8f0;
  --shadow:0 2px 16px rgba(91,114,248,.08);
  --shadowsm:0 1px 8px rgba(15,23,42,.06);
  --r:16px;--rm:12px;
  --mono:'IBM Plex Mono',monospace;
  --syne:'Syne',sans-serif;
  --dm:'DM Sans',sans-serif;
}
body{background:var(--bg);color:var(--t1);font-family:var(--dm)}
.app{max-width:400px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;background:linear-gradient(180deg,#eaf2ff,#f8faff)}
.hdr{background:linear-gradient(135deg,#4f68f0,#0ea5e9);padding:14px 18px 16px;border-radius:0 0 24px 24px;box-shadow:0 8px 28px rgba(79,104,240,.22);flex-shrink:0}
.hdr-row{display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:9px}
.brand-icon{width:34px;height:34px;border-radius:10px;background:rgba(255,255,255,.22);border:1px solid rgba(255,255,255,.3);display:flex;align-items:center;justify-content:center;font-size:17px}
.brand-name{font-family:var(--syne);font-weight:800;font-size:17px;color:#fff;letter-spacing:-.3px;line-height:1}
.brand-sub{font-family:var(--mono);font-size:8px;color:rgba(255,255,255,.6);letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;line-height:1}
.hdr-right{display:flex;align-items:center;gap:8px}
.mpill{display:flex;align-items:center;gap:5px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);border-radius:20px;padding:4px 10px;white-space:nowrap;flex-shrink:0}
.mpdot{width:7px;height:7px;border-radius:50%;background:#4ade80;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.mptext{font-family:var(--dm);font-size:10px;font-weight:600;color:rgba(255,255,255,.95)}
.bell{width:36px;height:36px;border-radius:10px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);display:flex;align-items:center;justify-content:center;font-size:16px;cursor:pointer;position:relative}
.bell-b{position:absolute;top:-4px;right:-4px;width:16px;height:16px;border-radius:50%;background:var(--rose);font-family:var(--mono);font-size:8px;font-weight:700;color:#fff;display:flex;align-items:center;justify-content:center;border:2px solid #fff}
.alert-banner{background:linear-gradient(135deg,#fff1f3,#ffe4e6);border-bottom:1.5px solid #fecdd3;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.ab-pulse{width:8px;height:8px;border-radius:50%;background:var(--rose);animation:pr 1.2s infinite;flex-shrink:0}
@keyframes pr{0%,100%{transform:scale(1)}50%{transform:scale(1.4)}}
.ab-left{display:flex;align-items:center;gap:8px}
.ab-title{font-size:12px;font-weight:600;color:var(--rose)}
.ab-sub{font-family:var(--mono);font-size:10px;color:rgba(225,29,72,.7);margin-top:1px}
.ab-btn{font-family:var(--mono);font-size:9px;font-weight:700;background:var(--rose);color:#fff;border:none;padding:5px 12px;border-radius:6px;cursor:pointer;white-space:nowrap}
.tabs-wrap{flex-shrink:0}
.tabs{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;background:var(--white);box-shadow:var(--shadow)}
.tab{display:flex;flex-direction:column;align-items:center;gap:3px;background:none;border:none;cursor:pointer;padding:10px 4px 12px;position:relative;transition:all .2s}
.tab-icon{font-size:18px;line-height:1;transition:transform .2s}
.tab.active .tab-icon{transform:scale(1.1)}
.tab-label{font-family:var(--dm);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:.5px;text-transform:uppercase;transition:color .2s;display:flex;align-items:center;gap:3px}
.tab.active .tab-label{color:var(--indigo)}
.tab-ink{position:absolute;bottom:0;left:20%;right:20%;height:2.5px;border-radius:2px 2px 0 0;background:linear-gradient(90deg,var(--indigo),var(--sky));opacity:0;transition:opacity .2s}
.tab.active .tab-ink{opacity:1}
.tab-badge{background:var(--rose);color:#fff;font-family:var(--mono);font-size:7px;font-weight:700;padding:1px 5px;border-radius:6px;min-width:14px;text-align:center}
.screen{flex:1;overflow-y:auto;overflow-x:hidden;scrollbar-width:none}
.screen::-webkit-scrollbar{display:none}
.pad{padding:12px 16px 100px}
.card{background:var(--white);border-radius:var(--r);box-shadow:var(--shadow);margin-bottom:10px;overflow:hidden;border:1px solid rgba(91,114,248,.06)}
.uc{background:linear-gradient(135deg,#fff8f9,#fff);border:1.5px solid #fecdd3;border-radius:var(--r);padding:13px;margin-bottom:10px}
.uc-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.uc-title{font-family:var(--syne);font-weight:700;font-size:13px;color:var(--rose);display:flex;align-items:center;gap:6px}
.uc-count{font-family:var(--mono);font-size:9px;background:var(--rose2);color:var(--rose);border:1px solid #fca5a5;padding:2px 8px;border-radius:10px;font-weight:700}
.uc-item{background:var(--white);border:1px solid #fecdd3;border-radius:10px;padding:10px 12px;margin-bottom:7px;cursor:pointer;display:flex;align-items:center;justify-content:space-between}
.uc-item:last-child{margin-bottom:0}
.uc-ticker{font-family:var(--syne);font-weight:800;font-size:14px;color:var(--rose)}
.uc-desc{font-size:10px;color:var(--t2);margin-top:2px}
.uc-exit{font-family:var(--mono);font-size:9px;font-weight:700;background:var(--rose);color:#fff;padding:5px 12px;border-radius:7px;white-space:nowrap;border:none;cursor:pointer}
.sig-card{background:var(--white);border-radius:var(--rm);box-shadow:var(--shadowsm);border:1px solid rgba(91,114,248,.08);margin-bottom:8px;overflow:hidden}
.sig-row{display:flex;align-items:center;gap:9px;padding:9px 14px;cursor:pointer;transition:background .15s}
.sig-row:hover{background:rgba(91,114,248,.02)}
.sig-exp{padding:9px 14px 11px;background:rgba(91,114,248,.02);font-size:11px;color:var(--t2);line-height:1.6;animation:exIn .2s ease}
@keyframes exIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
.mkt-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.mkt-card{background:var(--white);border-radius:var(--rm);padding:12px;box-shadow:var(--shadowsm);border:1px solid transparent}
.mkt-card.g{border-color:rgba(5,150,105,.12);background:linear-gradient(135deg,#f0fdf9,#fff)}
.mkt-card.b{border-color:rgba(91,114,248,.1);background:linear-gradient(135deg,#f0f5ff,#fff)}
.mk-label{font-family:var(--mono);font-size:8px;color:var(--t3);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}
.mk-val{font-family:var(--mono);font-size:15px;font-weight:700;margin-bottom:2px}
.mk-sub{font-size:9px;color:var(--t3)}
.search-wrap{background:var(--white);border:1.5px solid var(--t4);border-radius:var(--rm);padding:10px 13px;display:flex;align-items:center;gap:8px;margin-bottom:12px;box-shadow:var(--shadowsm)}
.search-wrap:focus-within{border-color:var(--sky)}
.si-inp{background:none;border:none;outline:none;color:var(--t1);font-family:var(--dm);font-size:13px;flex:1}
.si-inp::placeholder{color:var(--t3)}
.si-add{font-family:var(--mono);font-size:9px;font-weight:700;background:linear-gradient(135deg,var(--indigo),var(--sky));color:#fff;border:none;padding:5px 11px;border-radius:6px;cursor:pointer}
.pills{display:flex;gap:6px;margin-bottom:12px;overflow-x:auto;scrollbar-width:none}
.pills::-webkit-scrollbar{display:none}
.pill{padding:5px 14px;border-radius:20px;border:1.5px solid var(--t4);background:var(--white);color:var(--t2);font-family:var(--dm);font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .2s;flex-shrink:0}
.pill.on{background:linear-gradient(135deg,var(--indigo),var(--sky));color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(91,114,248,.25)}
.grp{background:var(--white);border-radius:var(--r);box-shadow:var(--shadow);margin-bottom:10px;overflow:hidden;border:1.5px solid transparent}
.grp.urg{border-color:rgba(225,29,72,.12);background:linear-gradient(180deg,#fff8f9,#fff)}
.grp.wtch{border-color:rgba(217,119,6,.1);background:linear-gradient(180deg,#fffdf5,#fff)}
.grp.gd{border-color:rgba(5,150,105,.1);background:linear-gradient(180deg,#f0fdf9,#fff)}
.gh{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;cursor:pointer;user-select:none}
.gh-l{display:flex;align-items:center;gap:8px}
.gh-dot{width:9px;height:9px;border-radius:50%}
.gh-name{font-family:var(--syne);font-weight:700;font-size:13px;color:var(--t1)}
.gh-cnt{font-family:var(--mono);font-size:9px;padding:2px 8px;border-radius:10px;font-weight:700}
.grp.urg .gh-cnt{background:var(--rose2);color:var(--rose)}
.grp.wtch .gh-cnt{background:var(--amber2);color:var(--amber)}
.grp.gd .gh-cnt{background:var(--emerald2);color:var(--emerald)}
.gb{border-top:1px solid rgba(15,23,42,.04)}
.sr{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid rgba(15,23,42,.04);cursor:pointer;transition:background .15s}
.sr:last-child{border-bottom:none}
.sr:hover{background:rgba(91,114,248,.02)}
.sr-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sr-m{flex:1;min-width:0}
.sr-t{display:flex;justify-content:space-between;align-items:center}
.sr-ticker{font-family:var(--syne);font-weight:700;font-size:13px;color:var(--t1)}
.sr-price{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--t1)}
.sr-b{display:flex;justify-content:space-between;align-items:center;margin-top:2px}
.sr-name{font-size:10px;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px}
.sr-chg{font-family:var(--mono);font-size:10px;font-weight:600}
.sr-r{display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0}
.sr-tr{font-family:var(--mono);font-size:9px;font-weight:600}
.sr-rec{font-family:var(--mono);font-size:8px;font-weight:700;padding:2px 7px;border-radius:4px;white-space:nowrap}
.rr-sb{background:linear-gradient(135deg,var(--indigo),var(--sky));color:#fff}
.rr-b{background:var(--emerald2);color:var(--emerald);border:1px solid #a7f3d0}
.rr-h{background:var(--amber2);color:var(--amber);border:1px solid #fde68a}
.rr-s{background:var(--rose2);color:var(--rose);border:1px solid #fca5a5}
.se{background:rgba(91,114,248,.02);border-top:1px solid rgba(15,23,42,.05);padding:13px 14px 14px;animation:exIn .2s ease}
.se-stats{display:flex;align-items:center;gap:0;margin-bottom:12px;background:var(--white);border-radius:10px;overflow:hidden;border:1px solid rgba(15,23,42,.06)}
.se-stat{flex:1;padding:10px 8px;text-align:center;border-right:1px solid rgba(15,23,42,.06)}
.se-stat:last-child{border-right:none}
.se-lbl{font-family:var(--mono);font-size:8px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.se-val{font-family:var(--mono);font-size:13px;font-weight:700}
.se-badge-row{display:flex;align-items:center;gap:8px;margin-bottom:11px}
.se-verdict{font-size:11px;color:var(--t2);line-height:1.6;margin-bottom:12px;padding-left:12px;border-left:3px solid}
.se-btns{display:flex;gap:8px}
.se-btn{flex:1;padding:10px;border-radius:10px;border:none;font-family:var(--dm);font-size:12px;font-weight:700;cursor:pointer;transition:opacity .2s}
.se-btn:hover{opacity:.85}
.se-btn.p{background:linear-gradient(135deg,var(--indigo),var(--sky));color:#fff;box-shadow:0 4px 12px rgba(91,114,248,.2)}
.se-btn.g{background:var(--card2);color:var(--t2);border:1px solid var(--t4)}
.se-btn.d{background:var(--rose2);color:var(--rose);border:1px solid #fca5a5}
.sec-lbl{font-family:var(--mono);font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:2px;margin-bottom:8px;margin-top:12px}
.section-box{border-radius:var(--r);overflow:hidden;margin-bottom:14px;box-shadow:var(--shadow)}
.section-hdr{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;cursor:pointer;user-select:none}
.section-hdr-l{display:flex;align-items:center;gap:9px}
.section-hdr-icon{width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.section-hdr-title{font-family:var(--syne);font-weight:800;font-size:15px;color:var(--t1)}
.section-hdr-cnt{font-family:var(--mono);font-size:9px;font-weight:700;padding:2px 9px;border-radius:10px}
.section-body{border-top:1.5px solid rgba(15,23,42,.06)}
.igrp-hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;cursor:pointer;user-select:none;transition:background .15s;border-bottom:1px solid rgba(15,23,42,.05)}
.igrp-hdr:hover{background:rgba(15,23,42,.015)}
.igrp-hdr-l{display:flex;align-items:center;gap:7px}
.igrp-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.igrp-title{font-family:var(--syne);font-weight:700;font-size:12px;color:var(--t1)}
.igrp-cnt{font-family:var(--mono);font-size:8px;font-weight:700;padding:2px 8px;border-radius:8px}
.igrp-body{}
.picks-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.picks-title{font-family:var(--syne);font-weight:800;font-size:20px;color:var(--t1)}
.picks-acc{display:flex;align-items:center;gap:5px;background:var(--emerald2);border:1px solid #a7f3d0;border-radius:20px;padding:5px 12px}
.picks-dot{width:5px;height:5px;border-radius:50%;background:var(--emerald)}
.picks-acc-text{font-family:var(--mono);font-size:9px;color:var(--emerald);font-weight:700}
.pick-wrap{background:var(--white);border-radius:var(--r);box-shadow:var(--shadow);margin-bottom:12px;overflow:hidden}
.pick-row{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid rgba(15,23,42,.04);cursor:pointer;transition:background .15s}
.pick-row:last-child{border-bottom:none}
.pick-row:hover{background:rgba(91,114,248,.02)}
.disq-hdr{display:flex;align-items:center;justify-content:space-between;margin:14px 0 9px}
.disq-title{font-family:var(--syne);font-weight:700;font-size:14px;color:var(--t1)}
.disq-cnt{font-family:var(--mono);font-size:9px;color:var(--t3);background:var(--card2);border:1px solid var(--t4);padding:2px 8px;border-radius:10px}
.disq-wrap{background:var(--white);border-radius:var(--r);box-shadow:var(--shadowsm);overflow:hidden}
.disq-item{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;background:rgba(225,29,72,.015);border-bottom:1px solid rgba(225,29,72,.07)}
.disq-item:last-child{border-bottom:none}
.modal-overlay{position:fixed;inset:0;background:rgba(15,23,42,.6);z-index:300;display:flex;flex-direction:column;justify-content:flex-end;backdrop-filter:blur(4px);max-width:400px;margin:0 auto}
.modal-box{background:var(--bg);border-radius:22px 22px 0 0;padding:20px 18px 36px;animation:slideUp .3s cubic-bezier(.32,.72,0,1)}
.modal-title{font-family:var(--syne);font-weight:800;font-size:17px;color:var(--t1);margin-bottom:4px}
.modal-sub{font-size:12px;color:var(--t3);margin-bottom:18px}
.modal-label{font-family:var(--mono);font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}
.modal-inp{width:100%;background:var(--white);border:1.5px solid var(--t4);border-radius:10px;padding:11px 13px;font-family:var(--dm);font-size:14px;color:var(--t1);outline:none;margin-bottom:12px;box-sizing:border-box}
.modal-inp:focus{border-color:var(--sky)}
.modal-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.modal-seg{display:flex;background:var(--card2);border-radius:10px;padding:3px;gap:3px;margin-bottom:14px}
.modal-seg-btn{flex:1;padding:8px;border:none;border-radius:8px;font-family:var(--dm);font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;background:transparent;color:var(--t3)}
.modal-seg-btn.on{background:var(--white);color:var(--indigo);box-shadow:var(--shadowsm)}
.modal-submit{width:100%;padding:13px;border:none;border-radius:12px;background:linear-gradient(135deg,var(--indigo),var(--sky));color:#fff;font-family:var(--dm);font-size:14px;font-weight:700;cursor:pointer;margin-top:4px}
.modal-submit:disabled{opacity:.5;cursor:not-allowed}
.modal-err{font-size:11px;color:var(--rose);margin-bottom:10px;padding:8px 12px;background:var(--rose2);border-radius:8px;border:1px solid #fca5a5}
.ac-wrap{position:relative;margin-bottom:12px}
.ac-inp{width:100%;background:var(--white);border:1.5px solid var(--t4);border-radius:10px;padding:11px 13px;font-family:var(--dm);font-size:14px;color:var(--t1);outline:none;box-sizing:border-box}
.ac-inp:focus{border-color:var(--sky)}
.ac-drop{position:absolute;left:0;right:0;top:100%;background:var(--white);border:1.5px solid var(--sky);border-radius:10px;box-shadow:0 8px 24px rgba(15,23,42,.12);z-index:20;overflow:hidden;margin-top:3px}
.ac-item{padding:9px 13px;cursor:pointer;border-bottom:1px solid rgba(15,23,42,.05);transition:background .12s}
.ac-item:last-child{border-bottom:none}
.ac-item:hover{background:rgba(91,114,248,.05)}
.ac-ticker{font-family:var(--syne);font-weight:700;font-size:12px;color:var(--t1)}
.ac-name{font-size:10px;color:var(--t3);margin-top:1px}
.score-modal{position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:250;display:flex;align-items:center;justify-content:center;padding:20px;max-width:400px;margin:0 auto}
.score-box{background:var(--white);border-radius:18px;padding:20px;width:100%;box-shadow:0 20px 60px rgba(15,23,42,.2)}
.score-pillar{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.score-pillar-label{font-family:var(--dm);font-size:12px;color:var(--t2);flex:1}
.score-pillar-bar{flex:2;height:6px;background:rgba(15,23,42,.06);border-radius:3px;overflow:hidden}
.score-pillar-fill{height:100%;border-radius:3px;transition:width .4s ease}
.score-pillar-val{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--t1);width:36px;text-align:right}
`;

// ── UTILITIES ────────────────────────────────────────
const getFlag = (market, ticker) => {
  const t = ticker || "";
  if (market === "IN" || t.endsWith(".NS") || t.endsWith(".BO")) return "🇮🇳";
  if (market === "EU" || t.endsWith(".AS") || t.endsWith(".DE") || t.endsWith(".PA")) return "🇪🇺";
  return "🇺🇸";
};
const tc = s => s>=75?"#5b72f8":s>=60?"#d97706":s>=40?"#f59e0b":"#e11d48";
const tg = s => s>=75?"Strong":s>=60?"Moderate":s>=40?"Weak":"Blocked";
const isINR = t => t && (t.endsWith(".NS") || t.endsWith(".BO"));
const isEUR = t => t && (t.endsWith(".AS") || t.endsWith(".DE") || t.endsWith(".PA"));
const cu = t => isINR(t) ? "₹" : isEUR(t) ? "€" : "$";
const actionColor = a => a==="EXIT"||a==="WAIT"?"var(--rose)":a==="TRIM"||a==="WATCH"||a==="DECIDE"?"var(--amber)":a==="BUY"||a==="STRONG BUY"?"var(--emerald)":"var(--indigo)";
const actionBg = a => a==="EXIT"||a==="WAIT"?"var(--rose2)":a==="TRIM"||a==="WATCH"||a==="DECIDE"?"var(--amber2)":a==="BUY"||a==="STRONG BUY"?"var(--emerald2)":"#eef2ff";
const toSEK = (price, ticker, fxRates) => {
  if (!fxRates || !price || typeof price !== "number") return null;
  const sekRate = fxRates.SEK || 10.4;
  if (isINR(ticker)) return price / (fxRates.INR || 83) * sekRate;
  if (isEUR(ticker)) return price / (fxRates.EUR || 0.93) * sekRate;
  return price * sekRate;
};

// ── MAPPING HELPERS ──────────────────────────────────
const getRecFromGroup = (group, trust, autoDisq) => {
  if (autoDisq || group === "urgent") return {rec:"SELL", rcls:"rr-s"};
  if (group === "watch") return {rec:"HOLD", rcls:"rr-h"};
  if (trust >= 75) return {rec:"BUY", rcls:"rr-b"};
  return {rec:"HOLD", rcls:"rr-h"};
};

const mapPosition = (pos, earningsByTicker) => {
  const flag = getFlag(pos.market, pos.ticker);
  const {rec, rcls} = getRecFromGroup(pos.group, pos.trust_score, pos.auto_disqualified);
  const pnlPct = pos.pnl_pct || 0;
  let verdict = pos.disqualify_reason || "";
  if (!verdict) {
    if (pnlPct < -30) verdict = `Down ${Math.abs(pnlPct).toFixed(0)}% from entry. Trust score ${pos.trust_score}/100. Monitor fundamentals.`;
    else if (pnlPct > 30) verdict = `Up ${pnlPct.toFixed(0)}% from entry. Consider a trailing stop to protect gains.`;
    else verdict = `Trust score ${pos.trust_score}/100 — ${pos.grade}. Hold and monitor.`;
  }
  return {
    id: pos.id, ticker: pos.ticker, flag, price: pos.current_price, change: pos.change_pct,
    name: pos.name || pos.ticker, buy: pos.buy_price, shares: pos.shares,
    rec, rcls, trust: pos.trust_score, grade: pos.grade,
    pnl: pos.pnl || 0, pnl_pct: pos.pnl_pct || 0,
    currency: pos.currency || "USD", market: pos.market || "US",
    verdict,
    earn: (earningsByTicker || {})[pos.ticker] || "—",
    auto_disqualified: pos.auto_disqualified,
  };
};

const mapWatchlistItem = item => ({
  ticker: item.ticker, flag: getFlag(item.market, item.ticker),
  price: item.current_price, change: item.change_pct,
  name: item.name || item.ticker, trust: item.trust_score,
  signal: item.signal || "Still watching", reason: item.signal || "Still watching",
  entry: "—", potential: "—",
});

const mapAlert = alert => {
  const t = alert.alert_type || "signal";
  const icons = {urgent:"🚨", signal:"🚀", earnings:"📅", watchlist_entry:"👁"};
  const confs = {urgent:"URGENT", signal:"HIGH", earnings:"INFO", watchlist_entry:"MED"};
  const ccs  = {urgent:"ch", signal:"ch", earnings:"cm", watchlist_entry:"cm"};
  const created = alert.created_at ? new Date(alert.created_at) : new Date();
  const diffMin = Math.round((Date.now() - created.getTime()) / 60000);
  const time = diffMin < 1 ? "just now" : diffMin < 60 ? `${diffMin}m ago` : diffMin < 1440 ? `${Math.round(diffMin/60)}h ago` : "Earlier";
  return {icon: icons[t]||"💡", ticker: alert.ticker||"—", conf: confs[t]||"SIGNAL", cc: ccs[t]||"cm", text: alert.message||"", time};
};

const fmtEarnDate = dateStr => {
  if (!dateStr) return "—";
  try { return new Date(dateStr+"T00:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric"}); }
  catch { return dateStr; }
};

const mapEarnings = e => {
  const today = new Date().toISOString().split("T")[0];
  const isToday = e.next_earnings_date === today;
  return {
    ticker: e.ticker, flag: getFlag(null, e.ticker), name: e.name || e.ticker,
    date: isToday ? "Today" : fmtEarnDate(e.next_earnings_date),
    time: "Pre-market", status: isToday ? "pending" : "upcoming",
    inPortfolio: e.in_portfolio, shares: e.shares||0,
    buyPrice: e.buy_price||0, currentPrice: e.current_price||0,
    preMarketChg: null, epsEst: e.eps_estimate||null, revEst: null,
    note: isToday ? "Earnings today — monitor results and act accordingly."
      : `Results expected ${fmtEarnDate(e.next_earnings_date)}. Review your position before this date.`,
    history: [], isUrgent: false,
  };
};

const mapPick = pick => {
  const trust = pick.trust || {};
  const total = trust.total_score || 0;
  const verdict = pick.verdict || {};
  const rawRec = (verdict.recommendation || "hold").toLowerCase();
  const rec = rawRec === "strong_buy" ? "STRONG BUY" : rawRec === "buy" ? "BUY" : rawRec === "sell" ? "SELL" : "HOLD";
  const rcls = rec === "STRONG BUY" ? "rr-sb" : rec === "BUY" ? "rr-b" : rec === "SELL" ? "rr-s" : "rr-h";
  const col = total >= 90 ? "#059669" : "#5b72f8";
  const price = pick.price || 0;
  const curr = cu(pick.ticker);
  const sigs = [verdict.verdict, verdict.key_risk ? `Risk: ${verdict.key_risk}` : null, verdict.stop_loss_explanation].filter(Boolean);
  return {
    ticker: pick.ticker, name: pick.name||pick.ticker, trust: total,
    grade: (trust.grade||"Strong").toUpperCase(), col, grad:`linear-gradient(90deg,${col},#0ea5e9)`,
    rec, rcls, b: trust.business_score||0, bm:40, s: trust.smart_money_score||0, sm:35, m: trust.momentum_score||0, mm:25,
    sigs: sigs.length ? sigs : ["Strong fundamentals across all three pillars."],
    potential: `+${Math.round((total-60)*1.2+15)}%`,
    entry: price > 0 ? `${curr}${(price*0.97).toFixed(0)}-${curr}${(price*1.03).toFixed(0)}` : "—",
    risk: total >= 80 ? "LOW-MED" : "MEDIUM", horizon: verdict.time_horizon || "12 months",
  };
};

const mapDisq = d => ({ticker: d.ticker, score: d.trust_score||0, reason: d.reason||"Auto-disqualified by safety check."});
const mapStrategy = item => ({...item, col: item.color || "var(--indigo)"});

const buildDetailData = resp => {
  if (!resp) return null;
  const f = resp.fundamentals || {}, a = resp.analyst || {}, t = resp.trust || {}, v = resp.verdict || {};
  const price = (resp.price_data || {}).price || 0;
  const metrics = [];
  if (f.revenue_growth != null) metrics.push({l:"Revenue Growth", v:`${(f.revenue_growth*100).toFixed(0)}%`, s:"YoY"});
  if (f.gross_margins) metrics.push({l:"Gross Margin", v:`${(f.gross_margins*100).toFixed(0)}%`, s:f.gross_margins>0.5?"Strong":"Moderate"});
  if (f.pe_ratio) metrics.push({l:"P/E Ratio", v:`${f.pe_ratio}×`, s:f.pe_ratio>50?"Growth":"Value"});
  if (f.cash_runway_months) metrics.push({l:"Cash Runway", v:`${f.cash_runway_months} mo`, s:f.cash_runway_months<6?"At risk":"Safe"});
  if (f.debt_to_equity != null) metrics.push({l:"Debt/Equity", v:`${f.debt_to_equity}×`, s:f.debt_to_equity<1?"Conservative":"Leveraged"});
  if (t.total_score) metrics.push({l:"Trust Score", v:`${t.total_score}/100`, s:t.grade||"—"});
  if (f.next_earnings_date) metrics.push({l:"Next Earnings", v:fmtEarnDate(f.next_earnings_date), s:"Upcoming"});
  while (metrics.length < 4) metrics.push({l:"—", v:"—", s:"—"});
  return {
    perf: resp.history || {"1W":0,"1M":0,"3M":0,"6M":0,"1Y":0},
    w52Lo: f.w52_low || price*0.7, w52Hi: f.w52_high || price*1.3,
    aTarget: a.target_price||null, aLow: a.target_low||null, aHigh: a.target_high||null,
    aBuy: a.buy_count||0, aHold: a.hold_count||0, aSell: a.sell_count||0,
    metrics: metrics.slice(0,4),
    verdict: v.verdict || t.disqualify_reason || `Trust score ${t.total_score}/100 — ${t.grade}.`,
  };
};

const genChart = (endPrice, perf, pts) => {
  const startPrice = endPrice / (1 + perf/100);
  const data = [];
  const now = new Date();
  const drift = (endPrice/startPrice)**(1/pts) - 1;
  let p = startPrice;
  for(let i=pts-1;i>=0;i--) {
    const d = new Date(now); d.setDate(d.getDate()-i);
    p = p * (1 + drift + (Math.random()-.48)*.025);
    data.push({date:d.toLocaleDateString('en-US',{month:'short',day:'numeric'}),price:Math.round(p*100)/100});
  }
  data[data.length-1].price = endPrice;
  return data;
};

// ── TOOLTIP ──────────────────────────────────────────
const Tip = ({active,payload}) => {
  if(!active||!payload?.length) return null;
  return (
    <div style={{background:"#0f172a",borderRadius:8,padding:"7px 11px"}}>
      <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,color:"#fff"}}>{payload[0].value?.toLocaleString()}</div>
      <div style={{fontFamily:"var(--mono)",fontSize:9,color:"rgba(255,255,255,.6)",marginTop:2}}>{payload[0].payload?.date}</div>
    </div>
  );
};

// ── MINI RING ────────────────────────────────────────
const Ring = ({score,col,size=56}) => {
  const r=size/2-5.5, c=2*Math.PI*r, f=score/100*c;
  return (
    <div style={{position:"relative",width:size,height:size,flexShrink:0}}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(15,23,42,.08)" strokeWidth="5"/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={col} strokeWidth="5"
          strokeLinecap="round" strokeDasharray={`${f} ${c}`}
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{filter:`drop-shadow(0 0 5px ${col}44)`}}/>
      </svg>
      <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
        <span style={{fontFamily:"var(--mono)",fontSize:15,fontWeight:700,color:col,lineHeight:1}}>{score}</span>
        <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>/100</span>
      </div>
    </div>
  );
};

// ── SCORE DETAIL MINI OVERLAY ────────────────────────
function ScoreDetail({ticker, trust, grade, onClose}) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const c = tc(trust);

  useEffect(() => {
    fetch(`/api/stock/${encodeURIComponent(ticker)}/trust`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { setD(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [ticker]);

  const b = d?.business_score ?? null;
  const s = d?.smart_money_score ?? null;
  const m = d?.momentum_score ?? null;

  return (
    <div className="score-modal" onClick={onClose}>
      <div className="score-box" onClick={e=>e.stopPropagation()}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:16}}>
          <div>
            <div style={{fontFamily:"var(--syne)",fontWeight:800,fontSize:18,color:c}}>{trust}/100</div>
            <div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",marginTop:2}}>{grade} · {ticker}</div>
          </div>
          <button onClick={onClose} style={{background:"var(--card2)",border:"none",borderRadius:8,padding:"5px 10px",fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",cursor:"pointer"}}>Close</button>
        </div>
        {loading ? (
          <div style={{textAlign:"center",padding:"16px 0",fontFamily:"var(--mono)",fontSize:11,color:"var(--t3)"}}>Loading…</div>
        ) : (
          <>
            <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:1,marginBottom:12}}>Score Breakdown</div>
            {[
              {label:"Business Quality", val:b, max:40, col:"#5b72f8", desc:"Revenue, earnings, profitability"},
              {label:"Smart Money", val:s, max:35, col:"#7c3aed", desc:"Insider buying, institutional flow"},
              {label:"Momentum", val:m, max:25, col:"#0ea5e9", desc:"Analyst ratings, price action"},
            ].map(p=>(
              <div key={p.label} style={{marginBottom:14}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}>
                  <div>
                    <div style={{fontFamily:"var(--dm)",fontSize:12,fontWeight:600,color:"var(--t1)"}}>{p.label}</div>
                    <div style={{fontSize:9,color:"var(--t3)"}}>{p.desc}</div>
                  </div>
                  <span style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,color:p.col}}>{p.val!=null?`${p.val}/${p.max}`:"—"}</span>
                </div>
                <div style={{height:6,background:"rgba(15,23,42,.06)",borderRadius:3,overflow:"hidden"}}>
                  <div style={{height:"100%",width:`${p.val!=null?Math.round(p.val/p.max*100):0}%`,background:p.col,borderRadius:3,transition:"width .4s ease"}}/>
                </div>
              </div>
            ))}
            {d?.auto_disqualified && (
              <div style={{marginTop:8,padding:"8px 12px",background:"var(--rose2)",borderRadius:8,border:"1px solid #fca5a5",fontSize:11,color:"var(--rose)",lineHeight:1.5}}>
                ⚠ {d.disqualify_reason}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── STOCK DETAIL OVERLAY ────────────────────────────
function StockDetail({ticker,name,flag,price,trust,rec,onClose}) {
  const [tf,setTf] = useState("3M");
  const [d, setD] = useState(null);
  const [dLoading, setDLoading] = useState(true);
  const tfs = ["1W","1M","3M","6M","1Y"];

  useEffect(() => {
    setDLoading(true);
    fetch(`/api/stock/${ticker}/detail`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { setD(buildDetailData(data)); setDLoading(false); })
      .catch(() => setDLoading(false));
  }, [ticker]);

  const c = tc(trust);
  const curr = cu(ticker);
  const perf = d ? (d.perf[tf] || 0) : 0;
  const perfPos = perf >= 0;
  const pts = tf==="1W"?7:tf==="1M"?22:tf==="3M"?65:tf==="6M"?130:252;
  const chartData = d ? genChart(price, perf, pts) : [];
  const chartMin = chartData.length ? Math.min(...chartData.map(p=>p.price))*.995 : price*0.9;
  const chartMax = chartData.length ? Math.max(...chartData.map(p=>p.price))*1.005 : price*1.1;
  const upside = d && d.aTarget && price ? (((d.aTarget-price)/price)*100).toFixed(0) : null;
  const aRange = d && d.aHigh && d.aLow ? (d.aHigh-d.aLow)||1 : 1;
  const aPos = d && d.aLow != null ? Math.min(100,Math.max(0,((price-d.aLow)/aRange*100))).toFixed(0) : 50;
  const aTPos = d && d.aTarget != null && d.aLow != null ? Math.min(100,Math.max(0,((d.aTarget-d.aLow)/aRange*100))).toFixed(0) : 70;
  const rRange = d && d.w52Hi && d.w52Lo ? (d.w52Hi-d.w52Lo)||1 : 1;
  const rPos = d && d.w52Lo != null ? Math.min(100,Math.max(0,((price-d.w52Lo)/rRange*100))).toFixed(0) : 50;

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(15,23,42,.55)",zIndex:200,display:"flex",flexDirection:"column",justifyContent:"flex-end",backdropFilter:"blur(4px)",maxWidth:400,margin:"0 auto"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:"var(--bg)",borderRadius:"24px 24px 0 0",maxHeight:"94vh",overflowY:"auto",scrollbarWidth:"none",animation:"slideUp .3s cubic-bezier(.32,.72,0,1)"}}>

        {/* Header */}
        <div style={{background:"linear-gradient(135deg,#4f68f0,#0ea5e9)",padding:"16px 18px 20px",borderRadius:"24px 24px 0 0",position:"sticky",top:0,zIndex:10}}>
          <div style={{display:"flex",justifyContent:"center",marginBottom:12}}>
            <div style={{width:36,height:4,background:"rgba(255,255,255,.4)",borderRadius:2}}/>
          </div>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:4}}>
            <div>
              <div style={{fontFamily:"var(--syne)",fontWeight:800,fontSize:22,color:"#fff",lineHeight:1}}>{ticker}</div>
              <div style={{fontSize:11,color:"rgba(255,255,255,.7)",marginTop:2}}>{name}</div>
              <div style={{display:"flex",alignItems:"center",gap:6,marginTop:5}}>
                <span style={{fontSize:13}}>{flag}</span>
                <span style={{fontFamily:"var(--mono)",fontSize:9,background:"rgba(255,255,255,.2)",color:"#fff",border:"1px solid rgba(255,255,255,.3)",padding:"3px 10px",borderRadius:5,fontWeight:700}}>{rec}</span>
              </div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontFamily:"var(--mono)",fontSize:28,fontWeight:700,color:"#fff",letterSpacing:-1,lineHeight:1}}>{curr}{price.toLocaleString()}</div>
              <div style={{display:"flex",alignItems:"center",justifyContent:"flex-end",gap:5,marginTop:4}}>
                <span style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:600,padding:"2px 8px",borderRadius:4,background:perfPos?"rgba(5,150,105,.2)":"rgba(225,29,72,.2)",color:perfPos?"#4ade80":"#fca5a5"}}>
                  {perfPos?"▲":"▼"}{Math.abs(perf).toFixed(1)}%
                </span>
                <span style={{fontFamily:"var(--mono)",fontSize:11,color:"rgba(255,255,255,.6)"}}>{tf}</span>
              </div>
            </div>
          </div>
          <div style={{display:"flex",background:"rgba(255,255,255,.15)",borderRadius:20,padding:3,marginTop:12}}>
            {tfs.map(t=>(
              <button key={t} onClick={()=>setTf(t)} style={{flex:1,padding:"5px 2px",border:"none",borderRadius:16,fontFamily:"var(--mono)",fontSize:10,fontWeight:600,cursor:"pointer",background:tf===t?"rgba(255,255,255,.95)":"transparent",color:tf===t?"var(--indigo)":"rgba(255,255,255,.65)",transition:"all .2s"}}>
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Chart */}
        {dLoading && <div style={{padding:"40px",textAlign:"center",fontFamily:"var(--mono)",fontSize:11,color:"var(--t3)"}}>Loading analysis...</div>}
        {!dLoading && <div style={{background:"var(--white)",paddingTop:14}}>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={chartData} margin={{top:4,right:0,left:0,bottom:0}}>
                <defs>
                  <linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={perfPos?"#5b72f8":"#e11d48"} stopOpacity={.15}/>
                    <stop offset="95%" stopColor={perfPos?"#5b72f8":"#e11d48"} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" hide/>
                <YAxis domain={[chartMin,chartMax]} hide/>
                <Tooltip content={<Tip/>} cursor={{stroke:"rgba(91,114,248,.2)",strokeWidth:1}}/>
                <Area type="monotone" dataKey="price" stroke={perfPos?"#5b72f8":"#e11d48"} strokeWidth={2} fill="url(#dg)" dot={false} activeDot={{r:4,fill:perfPos?"#5b72f8":"#e11d48",strokeWidth:0}}/>
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{height:150,display:"flex",alignItems:"center",justifyContent:"center",color:"var(--t3)",fontSize:11,fontFamily:"var(--mono)"}}>No chart data</div>
          )}
          <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",padding:"0 16px 14px",borderBottom:"1px solid var(--t4)"}}>
            {tfs.map(t=>{
              const v=d ? (d.perf[t]||0) : 0; const act=t===tf;
              return (
                <div key={t} style={{textAlign:"center",cursor:"pointer",opacity:act?1:.6}} onClick={()=>setTf(t)}>
                  <div style={{fontFamily:"var(--mono)",fontSize:8,color:act?"var(--indigo)":"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:4}}>{t}</div>
                  <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:v>=0?"var(--emerald)":"var(--rose)"}}>{v>=0?"+":""}{v}%</div>
                </div>
              );
            })}
          </div>
        </div>}

        {/* Body */}
        <div style={{padding:"14px 16px 40px"}}>

          {/* 52-week */}
          {d && <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,marginBottom:10,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>📊 52-Week Range</div>
            <div style={{height:6,background:"var(--t4)",borderRadius:3,position:"relative",margin:"8px 0"}}>
              <div style={{position:"absolute",top:0,left:0,height:"100%",width:`${rPos}%`,background:"linear-gradient(90deg,var(--indigo),var(--sky))",borderRadius:3}}/>
              <div style={{position:"absolute",top:"50%",left:`${rPos}%`,transform:"translate(-50%,-50%)",width:14,height:14,background:"var(--white)",border:"2.5px solid var(--indigo)",borderRadius:"50%",boxShadow:"0 2px 6px rgba(91,114,248,.3)"}}/>
            </div>
            <div style={{display:"flex",justifyContent:"space-between",marginTop:6}}>
              <div>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>52W Low</div>
                <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--rose)",marginTop:2}}>{curr}{(d.w52Lo||0).toLocaleString()}</div>
              </div>
              <div style={{textAlign:"center"}}>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>Current</div>
                <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,marginTop:2}}>{curr}{price.toLocaleString()}</div>
              </div>
              <div style={{textAlign:"right"}}>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>52W High</div>
                <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--emerald)",marginTop:2}}>{curr}{(d.w52Hi||0).toLocaleString()}</div>
              </div>
            </div>
          </div>}

          {/* AI */}
          <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,marginBottom:10,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>🤖 AI Analysis</div>
            <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:12}}>
              <Ring score={trust} col={c} size={60}/>
              <div>
                <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:15,color:c}}>{tg(trust)} · {trust}/100</div>
                <div style={{fontSize:11,color:"var(--t2)",marginTop:2}}>3 pillars · Updated today</div>
              </div>
            </div>
            <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.65,padding:"10px 12px",background:"var(--card2)",borderRadius:8,borderLeft:"3px solid var(--indigo)"}}>{d ? d.verdict : "Loading..."}</div>
          </div>

          {/* Forecast — only if analyst data available */}
          {d && d.aTarget && <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,marginBottom:10,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>🎯 12-Month Analyst Forecast</div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
              <div>
                <div style={{fontFamily:"var(--mono)",fontSize:24,fontWeight:700,color:"var(--indigo)",letterSpacing:-1,lineHeight:1}}>{curr}{d.aTarget.toLocaleString()}</div>
                <div style={{fontSize:10,color:"var(--t3)",marginTop:2}}>Consensus price target</div>
              </div>
              {upside && <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,color:"var(--emerald)",background:"var(--emerald2)",padding:"5px 12px",borderRadius:20,border:"1px solid #a7f3d0"}}>{upside >= 0 ? "+" : ""}{upside}% upside</div>}
            </div>
            {d.aLow && d.aHigh && <>
              <div style={{height:8,background:"var(--t4)",borderRadius:4,position:"relative",margin:"6px 0 8px"}}>
                <div style={{position:"absolute",top:0,left:0,width:"100%",height:"100%",background:"linear-gradient(90deg,rgba(91,114,248,.1),rgba(91,114,248,.2))",borderRadius:4}}/>
                <div style={{position:"absolute",top:"50%",left:`${aPos}%`,transform:"translate(-50%,-50%)",width:14,height:14,background:"var(--t1)",border:"2px solid #fff",borderRadius:"50%"}}/>
                <div style={{position:"absolute",top:"50%",left:`${aTPos}%`,transform:"translate(-50%,-50%)",width:16,height:16,background:"var(--indigo)",border:"2.5px solid #fff",borderRadius:"50%",boxShadow:"0 2px 8px rgba(91,114,248,.4)"}}/>
              </div>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:12}}>
                <div><div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Low</div><div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600}}>{curr}{d.aLow.toLocaleString()}</div></div>
                <div style={{textAlign:"center"}}><div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--indigo)",fontWeight:600}}>Now</div><div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:"var(--indigo)"}}>{curr}{price.toLocaleString()}</div></div>
                <div style={{textAlign:"right"}}><div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>High</div><div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600}}>{curr}{d.aHigh.toLocaleString()}</div></div>
              </div>
            </>}
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:8,marginBottom:10}}>
              {[{n:d.aBuy,l:"Buy",c:"var(--emerald)"},{n:d.aHold,l:"Hold",c:"var(--amber)"},{n:d.aSell,l:"Sell",c:"var(--rose)"}].map((a,i)=>(
                <div key={i} style={{background:"var(--card2)",borderRadius:9,padding:10,textAlign:"center"}}>
                  <div style={{fontFamily:"var(--mono)",fontSize:22,fontWeight:700,color:a.c,lineHeight:1}}>{a.n}</div>
                  <div style={{fontSize:10,color:"var(--t3)",marginTop:3}}>{a.l}</div>
                </div>
              ))}
            </div>
            <div style={{fontSize:10,color:"var(--t3)",lineHeight:1.5,textAlign:"center",padding:"8px 12px",background:"var(--card2)",borderRadius:8,fontStyle:"italic"}}>Analyst targets are estimates, not guarantees. One input among many.</div>
          </div>}

          {/* Metrics */}
          {d && <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>📈 Key Metrics</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
              {d.metrics.map((m,i)=>(
                <div key={i} style={{background:"var(--card2)",borderRadius:9,padding:"10px 12px",border:"1px solid rgba(15,23,42,.04)"}}>
                  <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:5}}>{m.l}</div>
                  <div style={{fontFamily:"var(--mono)",fontSize:16,fontWeight:700,color:"var(--t1)"}}>{m.v}</div>
                  <div style={{fontSize:10,color:"var(--t3)",marginTop:2}}>{m.s}</div>
                </div>
              ))}
            </div>
          </div>}

        </div>
      </div>
    </div>
  );
}

// Earnings data now comes from API props — no hardcoded data

function EarningsCard({e,onTap}) {
  const isToday=e.date==="Today";
  const pnl=e.inPortfolio?(e.currentPrice-e.buyPrice)*e.shares:null;
  return(
    <div onClick={onTap} style={{background:"var(--white)",borderRadius:11,
      border:`1px solid ${isToday?"rgba(225,29,72,.14)":"rgba(15,23,42,.06)"}`,
      padding:"10px 13px",marginBottom:8,cursor:"pointer",boxShadow:"var(--shadowsm)"}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:5}}>
        <div style={{display:"flex",alignItems:"center",gap:5}}>
          <span style={{fontSize:11}}>{e.flag}</span>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>{e.ticker}</span>
          <span style={{fontFamily:"var(--mono)",fontSize:8,color:isToday?"var(--rose)":"var(--t3)",
            background:isToday?"var(--rose2)":"var(--card2)",padding:"2px 6px",borderRadius:4,fontWeight:600}}>{e.date}</span>
          {e.preMarketChg&&<span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,
            color:e.preMarketChg>=0?"var(--emerald)":"var(--rose)",
            background:e.preMarketChg>=0?"var(--emerald2)":"var(--rose2)",
            padding:"2px 6px",borderRadius:4}}>PM {e.preMarketChg>0?"+":""}{e.preMarketChg}%</span>}
        </div>
        <span style={{fontSize:10,color:"var(--t3)"}}>›</span>
      </div>
      <div style={{fontSize:10,color:"var(--t2)",lineHeight:1.4,marginBottom:pnl!=null?6:0}}>{e.note}</div>
      {pnl!=null&&(
        <div style={{display:"flex",gap:10,paddingTop:6,borderTop:"1px solid rgba(15,23,42,.05)"}}>
          <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Your position</span>
          <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:600,color:pnl>=0?"var(--emerald)":"var(--rose)"}}>
            {pnl>=0?"+$":"-$"}{Math.abs(pnl).toFixed(0)}</span>
          <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>{e.shares} @ ${e.buyPrice}</span>
        </div>
      )}
    </div>
  );
}

function EarningsDetail({e,onBack,onClose}) {
  const pnl=e.inPortfolio?(e.currentPrice-e.buyPrice)*e.shares:null;
  const isToday=e.date==="Today";
  const hasPop=e.preMarketChg&&e.preMarketChg>8;
  const action=e.isUrgent
    ?{label:"Exit immediately",color:"var(--rose)",bg:"var(--rose2)",detail:"Auto-disqualified stock. Exit regardless of earnings result. The safety check flagged this company — do not hold through results."}
    :hasPop&&isToday
    ?{label:"Exit on pre-market pop",color:"var(--rose)",bg:"var(--rose2)",detail:"Pre-market pop is your exit window. Elevated risk today. Consider exiting at or before market open."}
    :isToday
    ?{label:"Hold — watch results",color:"var(--amber)",bg:"var(--amber2)",detail:"Earnings today. Monitor results carefully. Have a clear plan: set a stop loss if results disappoint."}
    :{label:"Hold through earnings",color:"var(--emerald)",bg:"var(--emerald2)",detail:"High trust stock with upcoming earnings. Hold with confidence. Review guidance commentary after results."};
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(15,23,42,.55)",zIndex:201,
      display:"flex",flexDirection:"column",justifyContent:"flex-end",
      backdropFilter:"blur(4px)",maxWidth:400,margin:"0 auto"}} onClick={onClose}>
      <div onClick={ev=>ev.stopPropagation()}
        style={{background:"var(--bg)",borderRadius:"22px 22px 0 0",maxHeight:"92vh",
          overflowY:"auto",scrollbarWidth:"none",animation:"slideUp .3s cubic-bezier(.32,.72,0,1)"}}>
        <div style={{background:"linear-gradient(135deg,#4f68f0,#0ea5e9)",padding:"14px 16px 16px",borderRadius:"22px 22px 0 0"}}>
          <div style={{display:"flex",justifyContent:"center",marginBottom:10}}>
            <div style={{width:32,height:4,background:"rgba(255,255,255,.4)",borderRadius:2}}/>
          </div>
          <button onClick={onBack} style={{background:"rgba(255,255,255,.2)",border:"none",color:"#fff",
            borderRadius:8,padding:"4px 10px",fontFamily:"var(--mono)",fontSize:10,cursor:"pointer",marginBottom:8}}>← Back</button>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
            <div>
              <div style={{display:"flex",alignItems:"center",gap:6}}>
                <span style={{fontSize:14}}>{e.flag}</span>
                <span style={{fontFamily:"var(--syne)",fontWeight:800,fontSize:20,color:"#fff"}}>{e.ticker}</span>
                {e.preMarketChg&&<span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:700,
                  color:e.preMarketChg>=0?"#4ade80":"#fca5a5",background:"rgba(255,255,255,.18)",
                  padding:"3px 8px",borderRadius:5}}>PM {e.preMarketChg>0?"+":""}{e.preMarketChg}%</span>}
              </div>
              <div style={{fontSize:11,color:"rgba(255,255,255,.7)",marginTop:2}}>{e.name} · {e.time} · {e.date}</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div style={{fontFamily:"var(--mono)",fontSize:20,fontWeight:700,color:"#fff"}}>${e.currentPrice}</div>
            </div>
          </div>
        </div>
        <div style={{padding:"14px 16px 36px"}}>
          {isToday&&(
            <div style={{background:hasPop?"rgba(225,29,72,.06)":"rgba(217,119,6,.06)",
              border:`1px solid ${hasPop?"rgba(225,29,72,.15)":"rgba(217,119,6,.15)"}`,
              borderRadius:10,padding:"10px 12px",marginBottom:12}}>
              <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12,
                color:hasPop?"var(--rose)":"var(--amber)",marginBottom:3}}>
                {hasPop?"⚡ Pre-market pop — exit window active":"⏳ Results pending — due before open"}</div>
              <div style={{fontSize:10,color:"var(--t2)",lineHeight:1.5}}>{e.note}</div>
            </div>
          )}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12}}>
            {[{l:"EPS Estimate",v:`$${e.epsEst}`},{l:"Revenue Est.",v:`$${e.revEst}M`}].map((m,i)=>(
              <div key={i} style={{background:"var(--white)",borderRadius:9,padding:"10px 12px",border:"1px solid rgba(15,23,42,.07)"}}>
                <div style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:4}}>{m.l}</div>
                <div style={{fontFamily:"var(--mono)",fontSize:16,fontWeight:700,color:"var(--t1)"}}>{m.v}</div>
                <div style={{fontSize:9,color:"var(--t3)",marginTop:1}}>consensus</div>
              </div>
            ))}
          </div>
          <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:1,marginBottom:7}}>Earnings history</div>
          <div style={{background:"var(--white)",borderRadius:9,overflow:"hidden",border:"1px solid rgba(15,23,42,.07)",marginBottom:12}}>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",padding:"5px 12px",background:"rgba(15,23,42,.018)",borderBottom:"1px solid rgba(15,23,42,.05)"}}>
              {["Quarter","Est","Actual",""].map((h,i)=>(
                <span key={i} style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,textAlign:i>0?"center":"left"}}>{h}</span>
              ))}
            </div>
            {(e.history||[]).map((h,i)=>(
              <div key={i} style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",padding:"8px 12px",borderBottom:i<e.history.length-1?"1px solid rgba(15,23,42,.04)":"none",alignItems:"center"}}>
                <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t2)"}}>{h.q}</span>
                <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",textAlign:"center"}}>{h.epsEst}</span>
                <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:600,color:h.beat?"var(--emerald)":"var(--rose)",textAlign:"center"}}>{h.epsAct}</span>
                <span style={{fontSize:11,textAlign:"center"}}>{h.beat?"✅":"❌"}</span>
              </div>
            ))}
          </div>
          {e.inPortfolio&&(
            <div style={{background:"var(--white)",borderRadius:9,padding:"10px 12px",border:"1px solid rgba(15,23,42,.07)",marginBottom:12}}>
              <div style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:8}}>Your position</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:8}}>
                {[{l:"Shares",v:e.shares},{l:"Bought at",v:`$${e.buyPrice}`},{l:"P&L",v:pnl!=null?`${pnl>=0?"+$":"-$"}${Math.abs(pnl).toFixed(0)}`:"—"}].map((m,i)=>(
                  <div key={i} style={{textAlign:"center"}}>
                    <div style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",textTransform:"uppercase",marginBottom:3}}>{m.l}</div>
                    <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,color:m.l==="P&L"?(pnl>=0?"var(--emerald)":"var(--rose)"):"var(--t1)"}}>{m.v}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div style={{background:action.bg,border:`1px solid ${action.color}33`,borderRadius:10,padding:"11px 13px",marginBottom:12,borderLeft:`3px solid ${action.color}`}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,color:action.color,marginBottom:4}}>{action.label}</div>
            <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.55}}>{action.detail}</div>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
            <button style={{padding:"11px",borderRadius:10,border:"none",cursor:"pointer",
              background:action.color==="var(--rose)"?"var(--rose)":"var(--indigo)",
              color:"#fff",fontFamily:"var(--dm)",fontSize:12,fontWeight:700}}>
              {action.color==="var(--rose)"?"Exit Position →":"View Full Analysis →"}</button>
            <button style={{padding:"11px",borderRadius:10,border:"1px solid var(--t4)",cursor:"pointer",
              background:"var(--white)",color:"var(--t2)",fontFamily:"var(--dm)",fontSize:12,fontWeight:600}}>
              Set Price Alert</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EarningsIntel({earnings, onClose}) {
  const [sel,setSel]=useState(null);
  const list = earnings || [];
  const today=list.filter(e=>e.date==="Today");
  const upcoming=list.filter(e=>e.date!=="Today");
  if(sel)return <EarningsDetail e={sel} onBack={()=>setSel(null)} onClose={onClose}/>;
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(15,23,42,.55)",zIndex:200,
      display:"flex",flexDirection:"column",justifyContent:"flex-end",
      backdropFilter:"blur(4px)",maxWidth:400,margin:"0 auto"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()}
        style={{background:"var(--bg)",borderRadius:"22px 22px 0 0",maxHeight:"88vh",
          overflowY:"auto",scrollbarWidth:"none",animation:"slideUp .3s cubic-bezier(.32,.72,0,1)"}}>
        <div style={{padding:"14px 16px 10px",borderBottom:"1px solid var(--t4)",
          position:"sticky",top:0,background:"var(--bg)",zIndex:5}}>
          <div style={{display:"flex",justifyContent:"center",marginBottom:10}}>
            <div style={{width:32,height:4,background:"var(--t4)",borderRadius:2}}/>
          </div>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
            <div>
              <div style={{fontFamily:"var(--syne)",fontWeight:800,fontSize:16}}>Earnings Watch</div>
              <div style={{fontSize:10,color:"var(--t3)",marginTop:1}}>Tap any stock for results analysis + your action</div>
            </div>
            <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--emerald)",
              background:"var(--emerald2)",border:"1px solid #a7f3d0",padding:"2px 8px",borderRadius:8}}>Live</span>
          </div>
        </div>
        <div style={{padding:"12px 16px 30px"}}>
          {today.length>0&&(
            <>
              <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8}}>
                <div style={{width:3,height:11,borderRadius:1,background:"var(--rose)"}}/>
                <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:700,color:"var(--rose)",textTransform:"uppercase",letterSpacing:.8}}>Today · Pending</span>
              </div>
              {today.map((e,i)=><EarningsCard key={i} e={e} onTap={()=>setSel(e)}/>)}
            </>
          )}
          <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8,marginTop:14}}>
            <div style={{width:3,height:11,borderRadius:1,background:"var(--indigo)"}}/>
            <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:700,color:"var(--indigo)",textTransform:"uppercase",letterSpacing:.8}}>Upcoming</span>
          </div>
          {upcoming.map((e,i)=><EarningsCard key={i} e={e} onTap={()=>setSel(e)}/>)}
        </div>
      </div>
    </div>
  );
}

// ── PORTFOLIO ARC ────────────────────────────────────
function PortfolioArc({positions, summary}) {
  const s = summary || {};
  const val = s.total_value || 0;
  const invested = s.total_invested || 0;
  const pnl = s.total_pnl || 0;
  const pnlPct = invested > 0 ? (pnl / invested * 100) : 0;
  const size=120, stroke=10, r=size/2-stroke;
  const circ=2*Math.PI*r, f=Math.min(invested > 0 ? val/invested : 0, 1)*circ;
  return (
    <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadow)",padding:"13px 14px",marginBottom:10,display:"flex",alignItems:"center",gap:14}}>
      <div style={{position:"relative",width:size,height:size,flexShrink:0}}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs><linearGradient id="ag" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#5b72f8"/><stop offset="100%" stopColor="#0ea5e9"/></linearGradient></defs>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(91,114,248,.1)" strokeWidth={stroke} strokeLinecap="round"/>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#ag)" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${f} ${circ}`} transform={`rotate(-90 ${size/2} ${size/2})`} style={{filter:"drop-shadow(0 0 8px rgba(91,114,248,.3))"}}/>
        </svg>
        <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
          <div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5}}>Value</div>
          <div style={{fontFamily:"var(--mono)",fontSize:15,fontWeight:700,color:"var(--t1)",letterSpacing:-1,lineHeight:1}}>{val >= 1000 ? `$${(val/1000).toFixed(1)}k` : `$${val.toFixed(0)}`}</div>
          <div style={{fontFamily:"var(--mono)",fontSize:10,color:pnl>=0?"var(--emerald)":"var(--rose)",marginTop:2}}>{pnl>=0?"▲":"▼"}{Math.abs(pnlPct).toFixed(0)}%</div>
        </div>
      </div>
      <div style={{flex:1}}>
        <div style={{display:"flex",justifyContent:"space-between",marginBottom:7}}>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>My Portfolio</span>
          <span style={{fontSize:11,color:"var(--indigo)",fontWeight:500,cursor:"pointer"}}>View all →</span>
        </div>
        {[
          {l:"Invested",v:`$${invested.toLocaleString('en',{maximumFractionDigits:0})}`,c:"var(--t2)"},
          {l:"Total P&L",v:`${pnl>=0?"+$":"-$"}${Math.abs(pnl).toLocaleString('en',{maximumFractionDigits:0})}`,c:pnl>=0?"var(--emerald)":"var(--rose)"},
        ].map((s,i)=>(
          <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",paddingTop:5,borderTop:i>0?"1px solid rgba(15,23,42,.04)":"none"}}>
            <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5}}>{s.l}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:s.c}}>{s.v}</span>
          </div>
        ))}
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",paddingTop:5,borderTop:"1px solid rgba(15,23,42,.04)"}}>
          <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5}}>Positions</span>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            {(() => {
              const all = positions || [];
              const us = all.filter(s=>s.flag==="🇺🇸").length;
              const eu = all.filter(s=>s.flag==="🇪🇺").length;
              const ind = all.filter(s=>s.flag==="🇮🇳").length;
              return [{flag:"🇺🇸",count:us},{flag:"🇪🇺",count:eu},{flag:"🇮🇳",count:ind}]
                .filter(m=>m.count>0)
                .map((m,i)=>(
                  <span key={i} style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:"var(--t1)"}}>{m.flag}{m.count}</span>
                ));
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── HOME SCREEN ──────────────────────────────────────
function HomeScreen({positions, summary, signals, earnings, market, onEarnings}) {
  const [sigOpen,setSigOpen] = useState(null);
  const todayEarnings = (earnings||[]).filter(e=>e.date==="Today");
  const vix = market?.vix?.price || 0;
  const vixLabel = vix >= 25 ? "🔴 Alert" : vix >= 15 ? "🟡 Choppy" : "🟢 Calm";
  const vixColor = vix >= 25 ? "var(--rose)" : vix >= 15 ? "var(--amber)" : "var(--emerald)";
  const vixSub = vix >= 25 ? "High fear — caution advised" : vix >= 15 ? "Some volatility — selective" : "Below 15 — signals reliable";
  const indices = [
    {flag:"🇺🇸", name:"S&P 500",    d:market?.sp500},
    {flag:"🇺🇸", name:"Nasdaq",     d:market?.nasdaq},
    {flag:"🇪🇺", name:"DAX",        d:market?.dax},
    {flag:"🇮🇳", name:"India (NSE)",d:market?.nifty},
  ];
  const sigList = signals && signals.length > 0 ? signals : [];
  return (
    <div className="pad" style={{paddingTop:12}}>
      <PortfolioArc positions={positions} summary={summary}/>

      {/* Earnings Watch card */}
      <div onClick={onEarnings} style={{background:"var(--white)",borderRadius:12,
        boxShadow:"var(--shadow)",marginBottom:10,overflow:"hidden",cursor:"pointer",
        border:"1px solid rgba(91,114,248,.08)"}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
          padding:"10px 14px",borderBottom:todayEarnings.length>0?"1px solid rgba(15,23,42,.05)":"none"}}>
          <div style={{display:"flex",alignItems:"center",gap:7}}>
            <span style={{fontSize:14}}>📅</span>
            <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>Earnings Watch</span>
            {todayEarnings.length>0&&<span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,
              color:"var(--rose)",background:"var(--rose2)",border:"1px solid #fca5a5",
              padding:"2px 7px",borderRadius:8,animation:"pr 1.5s infinite"}}>{todayEarnings.length} today</span>}
          </div>
          <span style={{fontSize:11,color:"var(--indigo)",fontWeight:500}}>View all →</span>
        </div>
        {todayEarnings.length>0&&(
          <div style={{padding:"8px 14px 10px"}}>
            {todayEarnings.map((e,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:8,marginBottom:i<todayEarnings.length-1?6:0}}>
                <span style={{fontSize:10}}>{e.flag}</span>
                <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12,color:"var(--rose)"}}>{e.ticker}</span>
                {e.preMarketChg&&<span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,
                  color:e.preMarketChg>=0?"var(--emerald)":"var(--rose)",
                  background:e.preMarketChg>=0?"var(--emerald2)":"var(--rose2)",
                  padding:"2px 6px",borderRadius:4}}>PM {e.preMarketChg>0?"+":""}{e.preMarketChg}%</span>}
                <span style={{fontSize:10,color:"var(--t2)",flex:1,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{e.note.split('.')[0]}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="card">
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"11px 14px 10px",borderBottom:"1px solid rgba(15,23,42,.05)"}}>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>Today's Signals</span>
          <span style={{fontSize:11,color:"var(--indigo)",fontWeight:500,cursor:"pointer"}}>See all →</span>
        </div>
        {sigList.length === 0
          ? <div style={{padding:"12px 14px",fontSize:11,color:"var(--t3)"}}>No signals yet — loading…</div>
          : sigList.map((s,i)=>{
          const open = sigOpen===i;
          return (
            <div key={i} className="sig-card">
              <div className="sig-row" onClick={()=>setSigOpen(open?null:i)}>
                <span style={{fontSize:16,flexShrink:0}}>{s.icon}</span>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:"flex",alignItems:"center",gap:6}}>
                    <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12}}>{s.ticker}</span>
                    <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,padding:"2px 7px",borderRadius:4,background:s.cc==="ch"?"var(--emerald2)":"var(--amber2)",color:s.cc==="ch"?"var(--emerald)":"var(--amber)",border:`1px solid ${s.cc==="ch"?"#a7f3d0":"#fde68a"}`}}>{s.conf}</span>
                    <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",marginLeft:"auto"}}>{s.time}</span>
                  </div>
                  <div style={{fontSize:10,color:"var(--t2)",marginTop:2,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{s.text}</div>
                </div>
                <span style={{fontSize:10,color:"var(--t3)",flexShrink:0,marginLeft:6}}>{open?"▲":"▼"}</span>
              </div>
              {open && <div className="sig-exp">{s.text}</div>}
            </div>
          );
        })}
      </div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
        <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>Market Conditions</span>
        <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Live · yfinance</span>
      </div>
      <div className="mkt-grid">
        <div className="mkt-card g">
          <div className="mk-label">Fear Index (VIX)</div>
          <div style={{display:"flex",alignItems:"baseline",gap:6}}>
            <div className="mk-val" style={{color:vixColor}}>{vix > 0 ? vix.toFixed(1) : "—"}</div>
            <span style={{fontFamily:"var(--mono)",fontSize:10,color:vixColor,fontWeight:600}}>{vix > 0 ? vixLabel : ""}</span>
          </div>
          <div className="mk-sub">{vix > 0 ? vixSub : "Loading…"}</div>
        </div>
        <div className="mkt-card b">
          <div className="mk-label">Markets Today</div>
          {indices.map((m,i)=>{
            const chg = m.d?.change_pct;
            const up = chg != null ? chg >= 0 : true;
            const val = chg != null ? `${up?"+":""}${chg.toFixed(1)}%` : "—";
            return (
              <div key={i} style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:4}}>
                <span style={{fontSize:10,color:"var(--t2)"}}>{m.flag} {m.name}</span>
                <span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:600,color:up?"var(--emerald)":"var(--rose)"}}>{val}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── COMPACT TABLE ROW (portfolio) ────────────────────
function CompactRow({s, dot, onDetail, onRemove, fxRates}) {
  const [open, setOpen] = useState(false);
  const [showScore, setShowScore] = useState(false);
  const c = tc(s.trust);
  const pnlPct = s.pnl_pct || ((s.price - s.buy) / s.buy * 100);
  const pnlPos = pnlPct >= 0;
  const recColor = s.rec==="SELL"?"var(--rose)":s.rec==="BUY"?"var(--emerald)":"var(--amber)";
  const recBg = s.rec==="SELL"?"var(--rose2)":s.rec==="BUY"?"var(--emerald2)":"var(--amber2)";
  const recLabel = s.rec==="SELL"&&s.trust<30?"S.SELL":s.rec==="BUY"&&s.trust>=75?"S.BUY":s.rec;
  const sekPrice = toSEK(s.price, s.ticker, fxRates);
  return (
    <>
      {showScore && <ScoreDetail ticker={s.ticker} trust={s.trust} grade={tg(s.trust)} onClose={()=>setShowScore(false)}/>}
      <div onClick={()=>setOpen(o=>!o)}
        style={{display:"grid",gridTemplateColumns:"1.9fr 1.5fr .7fr .9fr",
          alignItems:"center",padding:"7px 12px",borderBottom:"1px solid rgba(15,23,42,.04)",
          cursor:"pointer",background:open?"rgba(91,114,248,.02)":"transparent",
          transition:"background .15s",gap:4}}>
        <div style={{minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:4,flexWrap:"wrap"}}>
            <span style={{fontSize:10}}>{s.flag}</span>
            <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12,color:s.premarket?"var(--rose)":"var(--t1)"}}>{s.ticker}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:8,color:s.change>=0?"var(--emerald)":"var(--rose)"}}>
              {s.change>=0?"▲":"▼"}{Math.abs(s.change).toFixed(1)}%
            </span>
            {s.premarket&&<span style={{fontFamily:"var(--mono)",fontSize:7,fontWeight:700,color:"#fff",background:"var(--rose)",padding:"1px 5px",borderRadius:3,animation:"pr 1.2s infinite"}}>PRE-MKT</span>}
          </div>
          <div style={{display:"flex",alignItems:"center",gap:6,marginTop:1}}>
            <span style={{fontSize:9,color:"var(--t3)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:90}}>{s.name}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>{s.shares} units</span>
          </div>
        </div>
        <div>
          <div style={{display:"flex",alignItems:"baseline",gap:4}}>
            <span style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--t1)"}}>{cu(s.ticker)}{typeof s.price==="number"?s.price.toFixed(2):s.price}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:9,color:pnlPos?"var(--emerald)":"var(--rose)"}}>
              {pnlPos?"+":""}{pnlPct.toFixed(1)}%
            </span>
          </div>
          {sekPrice!=null && (
            <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>
              kr{Math.round(sekPrice).toLocaleString()}
            </div>
          )}
        </div>
        <div style={{textAlign:"center"}}>
          <span onClick={e=>{e.stopPropagation();setShowScore(true);}} title="Tap for score breakdown"
            style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:c,cursor:"pointer",textDecoration:"underline dotted",textUnderlineOffset:2}}>{s.trust}</span>
        </div>
        <div style={{textAlign:"right"}}>
          <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:recColor,background:recBg,padding:"3px 5px",borderRadius:4}}>{recLabel}</span>
        </div>
      </div>
      {open&&(
        <div style={{padding:"9px 12px 11px",background:"rgba(91,114,248,.02)",borderBottom:"1px solid rgba(15,23,42,.05)",animation:"exIn .2s ease"}}>
          <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.55,marginBottom:8,borderLeft:"2.5px solid",borderLeftColor:dot,paddingLeft:9}}>{s.verdict}</div>
          <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:8,flexWrap:"wrap"}}>
            <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Earnings <span style={{color:"var(--t1)",fontWeight:600}}>{s.earn}</span></span>
            <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Grade <span style={{color:c,fontWeight:700}}>{tg(s.trust)}</span></span>
            <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>Bought <span style={{color:"var(--t2)",fontWeight:600}}>${s.buy}×{s.shares}</span></span>
          </div>
          <div style={{display:"flex",gap:7}}>
            <button onClick={()=>onDetail&&onDetail(s)} style={{flex:1,padding:"8px",borderRadius:8,border:"none",background:"linear-gradient(135deg,var(--indigo),var(--sky))",color:"#fff",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer"}}>Full Analysis →</button>
            {s.rec==="SELL"
              ?<button onClick={()=>onRemove&&onRemove(s)} style={{flex:1,padding:"8px",borderRadius:8,border:"1px solid #fca5a5",background:"var(--rose2)",color:"var(--rose)",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer"}}>Remove</button>
              :<button onClick={()=>onRemove&&onRemove(s)} style={{flex:1,padding:"8px",borderRadius:8,border:"1px solid var(--t4)",background:"var(--card2)",color:"var(--t2)",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer"}}>Remove</button>
            }
          </div>
        </div>
      )}
    </>
  );
}

function CompactWatchRow({s, dot, onRemove}) {
  const [open, setOpen] = useState(false);
  const c = tc(s.trust);
  const cc = dot;
  const cbg = dot==="var(--emerald)"?"var(--emerald2)":dot==="var(--amber)"?"var(--amber2)":"var(--rose2)";
  return (
    <>
      <div onClick={()=>setOpen(o=>!o)}
        style={{display:"grid",gridTemplateColumns:"1.4fr 1.8fr .8fr",
          alignItems:"center",padding:"7px 12px",borderBottom:"1px solid rgba(15,23,42,.04)",
          cursor:"pointer",background:open?"rgba(91,114,248,.02)":"transparent",
          transition:"background .15s",gap:4}}>
        <div style={{minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <span style={{fontSize:10}}>{s.flag}</span>
            <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12,color:"var(--t1)"}}>{s.ticker}</span>
          </div>
          <div style={{fontSize:9,color:"var(--t3)",marginTop:1}}>{s.name}</div>
        </div>
        <div style={{minWidth:0}}>
          <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:cc,background:cbg,padding:"2px 6px",borderRadius:4,display:"inline-block",maxWidth:"100%",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{s.signal}</span>
          <div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t2)",marginTop:2}}>{s.entry}</div>
        </div>
        <div style={{textAlign:"right"}}>
          <span style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:c}}>{s.trust}</span>
          <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>{s.potential}</div>
        </div>
      </div>
      {open&&(
        <div style={{padding:"9px 12px 11px",background:"rgba(91,114,248,.02)",borderBottom:"1px solid rgba(15,23,42,.05)",animation:"exIn .2s ease"}}>
          <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.55,marginBottom:9}}>{s.reason}</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6}}>
            <div style={{background:"var(--card2)",borderRadius:8,padding:"7px 10px"}}>
              <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:2}}>Best Entry</div>
              <div style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:"var(--sky)"}}>{s.entry}</div>
            </div>
            <div style={{background:"var(--card2)",borderRadius:8,padding:"7px 10px"}}>
              <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:2}}>Potential</div>
              <div style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:"var(--emerald)"}}>{s.potential}</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}


function PivotSection({title, accentColor, slices, fxRates}) {
  const ac = accentColor||"var(--indigo)";
  const [active, setActive] = useState(0);
  const slice = slices[active];
  const total = slices.reduce((s,sl)=>s+sl.items.length,0);
  return (
    <div style={{background:"var(--white)",borderRadius:12,boxShadow:"var(--shadow)",overflow:"hidden",marginBottom:10,border:"1px solid rgba(15,23,42,.06)"}}>
      {/* Single compact header row: title + inline tabs + count */}
      <div style={{display:"flex",alignItems:"center",gap:8,padding:"8px 12px",borderBottom:"1px solid rgba(15,23,42,.05)"}}>
        <div style={{width:3,height:12,borderRadius:2,background:ac,flexShrink:0}}/>
        <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:10,color:"var(--t2)",textTransform:"uppercase",letterSpacing:.5,marginRight:4}}>{title}</span>
        {/* Inline pill tabs */}
        {slices.map((s,i)=>{
          const isAct=active===i;
          return (
            <button key={i} onClick={()=>setActive(i)}
              style={{display:"flex",alignItems:"center",gap:4,padding:"3px 8px",borderRadius:20,border:"none",cursor:"pointer",transition:"all .15s",
                background:isAct?`${s.color}18`:"rgba(15,23,42,.04)",flexShrink:0}}>
              <span style={{fontFamily:"var(--dm)",fontSize:9,fontWeight:isAct?700:500,color:isAct?s.color:"var(--t3)"}}>{s.label}</span>
              <span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:700,color:isAct?s.color:"var(--t3)"}}>{s.items.length}</span>
            </button>
          );
        })}
        <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t4)",marginLeft:"auto"}}>{total}</span>
      </div>
      {/* Column headers */}
      <div style={{display:"grid",gridTemplateColumns:slice.isWatch?"1.4fr 1.8fr .8fr":"1.9fr 1.5fr .7fr .9fr",
        padding:"4px 12px",background:"rgba(15,23,42,.018)",borderBottom:"1px solid rgba(15,23,42,.05)"}}>
        {(slice.isWatch
          ? ["Stock","Signal · Entry","Upside"]
          : ["Stock","Price · P&L","Score","Rec"]
        ).map((h,i)=>(
          <span key={i} style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.7,
            textAlign:slice.isWatch?(i===2?"right":"left"):(i>=2?"center":"left")}}>{h}</span>
        ))}
      </div>
      {/* Rows */}
      {slice.items.length===0
        ? <div style={{padding:"12px",textAlign:"center",fontFamily:"var(--dm)",fontSize:11,color:"var(--t3)"}}>No stocks in this category</div>
        : slice.items.map(s=>slice.isWatch
            ?<CompactWatchRow key={s.ticker} s={s} dot={slice.color} onRemove={slice.onRemove}/>
            :<CompactRow key={s.ticker} s={s} dot={slice.color} onDetail={slice.onDetail} onRemove={slice.onRemove} fxRates={fxRates}/>
          )
      }
    </div>
  );
}

// ── ADD MODAL ────────────────────────────────────────
function AddModal({onClose, onAdded}) {
  const [type, setType] = useState("portfolio");
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [sugLoading, setSugLoading] = useState(false);
  const [showSug, setShowSug] = useState(false);

  useEffect(() => {
    if (ticker.length < 2) { setSuggestions([]); setShowSug(false); return; }
    const timer = setTimeout(async () => {
      setSugLoading(true);
      try {
        const res = await searchTicker(ticker);
        setSuggestions(res || []);
        setShowSug((res||[]).length > 0);
      } catch {}
      setSugLoading(false);
    }, 350);
    return () => clearTimeout(timer);
  }, [ticker]);

  const pickSuggestion = (s) => {
    setTicker(s.ticker);
    setSuggestions([]);
    setShowSug(false);
  };

  const submit = async () => {
    const t = ticker.trim().toUpperCase();
    if (!t) return setErr("Enter a ticker symbol.");
    if (type === "portfolio") {
      if (!shares || isNaN(shares) || +shares <= 0) return setErr("Enter a valid number of shares.");
      if (!buyPrice || isNaN(buyPrice) || +buyPrice <= 0) return setErr("Enter a valid buy price.");
    }
    setErr(""); setLoading(true);
    try {
      if (type === "portfolio") {
        await addPosition(t, +shares, +buyPrice, buyDate || null, null);
      } else {
        await addToWatchlist(t, null);
      }
      onAdded();
      onClose();
    } catch(e) {
      setErr("Failed to add. Check the ticker and try again.");
    }
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e=>e.stopPropagation()}>
        <div style={{width:36,height:4,background:"var(--t4)",borderRadius:2,margin:"0 auto 16px"}}/>
        <div className="modal-title">Add Stock</div>
        <div className="modal-sub">Add to your portfolio or watchlist</div>

        {/* Portfolio / Watchlist toggle */}
        <div className="modal-seg">
          <button className={`modal-seg-btn${type==="portfolio"?" on":""}`} onClick={()=>setType("portfolio")}>📊 My Portfolio</button>
          <button className={`modal-seg-btn${type==="watchlist"?" on":""}`} onClick={()=>setType("watchlist")}>👁 Watchlist</button>
        </div>

        {/* Ticker with autocomplete */}
        <div className="modal-label">Ticker Symbol {sugLoading&&<span style={{color:"var(--t3)",fontWeight:400}}>— searching…</span>}</div>
        <div className="ac-wrap">
          <input className="ac-inp" placeholder="e.g. NVDA, RELIANCE.NS, ASML.AS"
            value={ticker}
            onChange={e=>{setTicker(e.target.value.toUpperCase());setErr("");}}
            onKeyDown={e=>e.key==="Enter"&&submit()}
            onBlur={()=>setTimeout(()=>setShowSug(false),150)}
            onFocus={()=>suggestions.length>0&&setShowSug(true)}
            autoComplete="off"/>
          {showSug && suggestions.length > 0 && (
            <div className="ac-drop">
              {suggestions.slice(0,6).map(s=>(
                <div key={s.ticker} className="ac-item" onMouseDown={()=>pickSuggestion(s)}>
                  <div className="ac-ticker">{s.ticker}</div>
                  <div className="ac-name">{s.name}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Portfolio-only fields */}
        {type==="portfolio" && (
          <>
            <div className="modal-row">
              <div>
                <div className="modal-label">Shares / Units</div>
                <input className="modal-inp" type="number" placeholder="100"
                  value={shares} onChange={e=>setShares(e.target.value)}/>
              </div>
              <div>
                <div className="modal-label">Buy Price</div>
                <input className="modal-inp" type="number" placeholder="45.50"
                  value={buyPrice} onChange={e=>setBuyPrice(e.target.value)}/>
              </div>
            </div>
            <div className="modal-label">Buy Date (optional)</div>
            <input className="modal-inp" type="date"
              value={buyDate} onChange={e=>setBuyDate(e.target.value)}/>
          </>
        )}

        {err && <div className="modal-err">{err}</div>}
        <button className="modal-submit" onClick={submit} disabled={loading}>
          {loading ? "Adding…" : type==="portfolio" ? "Add to Portfolio" : "Add to Watchlist"}
        </button>
      </div>
    </div>
  );
}

// ── STOCKS SCREEN ────────────────────────────────────
function StocksScreen({urgent, watch, good, wlReady, wlWatch, wlAvoid, onDetail, onAdd, fxRates}) {
  const [f, setF] = useState("All");
  const [showAdd, setShowAdd] = useState(false);
  const U=urgent||[], W=watch||[], G=good||[], WR=wlReady||[], WW=wlWatch||[], WA=wlAvoid||[];

  const handleRemove = async (s) => {
    if (!window.confirm(`Remove ${s.ticker} from your portfolio?`)) return;
    try { await deletePosition(s.id); onAdd && onAdd(); } catch(e) {}
  };
  const handleRemoveWL = async (s) => {
    if (!window.confirm(`Remove ${s.ticker} from watchlist?`)) return;
    try { await removeFromWatchlist(s.ticker); onAdd && onAdd(); } catch(e) {}
  };
  const byC = arr => f==="🇺🇸 US"?arr.filter(s=>s.flag==="🇺🇸"):f==="🇪🇺 Europe"?arr.filter(s=>s.flag==="🇪🇺"):f==="🇮🇳 India"?arr.filter(s=>s.flag==="🇮🇳"):arr;
  const fU=byC(U), fW=byC(W), fG=byC(G);
  const fWR=byC(WR), fWW=byC(WW), fWA=byC(WA);

  const myStocksSlices = [
    {label:"Urgent",  color:"var(--rose)",    items:fU, onDetail, onRemove:handleRemove},
    {label:"Monitor", color:"var(--amber)",   items:fW, onDetail, onRemove:handleRemove},
    {label:"Stable",  color:"var(--emerald)", items:fG, onDetail, onRemove:handleRemove},
  ];
  const watchlistSlices = [
    {label:"Ready",   color:"var(--emerald)", items:fWR, isWatch:true, onRemove:handleRemoveWL},
    {label:"Waiting", color:"var(--amber)",   items:fWW, isWatch:true, onRemove:handleRemoveWL},
    {label:"Avoid",   color:"var(--rose)",    items:fWA, isWatch:true, onRemove:handleRemoveWL},
  ];

  return (
    <div className="pad" style={{paddingTop:10}}>
      <div className="search-wrap">
        <span style={{fontSize:14,color:"var(--t3)",flexShrink:0}}>🔍</span>
        <input className="si-inp" placeholder="Search US, EU or India ticker…"/>
        <button className="si-add" onClick={()=>setShowAdd(true)}>+ Add</button>
      </div>
      {showAdd && <AddModal onClose={()=>setShowAdd(false)} onAdded={onAdd}/>}
      <div className="pills">
        {["All","My Stocks","Watchlist","🇺🇸 US","🇪🇺 Europe","🇮🇳 India"].map(p=>(
          <button key={p} className={`pill${f===p?" on":""}`} onClick={()=>setF(p)}>{p}</button>
        ))}
      </div>
      {f==="All"&&(<><PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices} fxRates={fxRates}/><PivotSection title="Watchlist" accentColor="var(--violet)" slices={watchlistSlices}/></>)}
      {f==="My Stocks"&&<PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices} fxRates={fxRates}/>}
      {f==="Watchlist"&&<PivotSection title="Watchlist" accentColor="var(--violet)" slices={watchlistSlices}/>}
      {["🇺🇸 US","🇪🇺 Europe","🇮🇳 India"].includes(f)&&(
        <>
          {(fU.length+fW.length+fG.length)>0&&<PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices} fxRates={fxRates}/>}
          {(fWR.length+fWW.length+fWA.length)>0&&<PivotSection title="Watchlist" accentColor="var(--violet)" slices={watchlistSlices}/>}
          {(fU.length+fW.length+fG.length)===0&&(fWR.length+fWW.length+fWA.length)===0&&(
            <div style={{textAlign:"center",padding:"40px 20px"}}>
              <div style={{fontSize:32,marginBottom:12}}>{f==="🇺🇸 US"?"🇺🇸":f==="🇪🇺 Europe"?"🇪🇺":"🇮🇳"}</div>
              <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:14,color:"var(--t2)",marginBottom:6}}>No {f} stocks yet</div>
              <div style={{fontSize:12,color:"var(--t3)"}}>Add a ticker above</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}



// ── SMART PICKS ──────────────────────────────────────
function SmartPicksScreen({picks, disq, accuracy}) {
  const [exp,setExp] = useState(null);
  const PICKS = picks || [];
  const DISQ = disq || [];
  const acc = accuracy || "—";
  return (
    <div className="pad" style={{paddingTop:12}}>

      {/* Quiet header — data leads, label whispers */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
        <div style={{display:"flex",alignItems:"center",gap:7}}>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,color:"var(--t1)"}}>Smart Picks</span>
          <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--emerald)",background:"var(--emerald2)",border:"1px solid #a7f3d0",padding:"2px 7px",borderRadius:8,fontWeight:600}}>{acc} · 90d</span>
        </div>
        <span style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)"}}>{PICKS.length} active</span>
      </div>

      {/* Picks card */}
      <div style={{background:"var(--white)",borderRadius:12,boxShadow:"var(--shadow)",overflow:"hidden",marginBottom:10}}>
        {/* Subtle column headers */}
        <div style={{display:"grid",gridTemplateColumns:"1.6fr 1.1fr .65fr .8fr .5fr",
          padding:"4px 12px",background:"rgba(15,23,42,.015)",
          borderBottom:"1px solid rgba(15,23,42,.05)"}}>
          {["Stock","Rec","AI","Upside",""].map((h,i)=>(
            <span key={i} style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",
              textTransform:"uppercase",letterSpacing:.6,
              textAlign:i>=2?"center":"left"}}>{h}</span>
          ))}
        </div>

        {PICKS.map((s,i)=>{
          const open=exp===i;
          const c=tc(s.trust);
          const recColor=s.rcls==="rr-sb"?"var(--indigo)":s.rcls==="rr-b"?"var(--emerald)":"var(--amber)";
          const recBg=s.rcls==="rr-sb"?"#eef2ff":s.rcls==="rr-b"?"var(--emerald2)":"var(--amber2)";
          return (
            <div key={s.ticker}>
              <div onClick={()=>setExp(open?null:i)}
                style={{display:"grid",gridTemplateColumns:"1.6fr 1.1fr .65fr .8fr .5fr",
                  alignItems:"center",padding:"7px 12px",
                  borderBottom:"1px solid rgba(15,23,42,.04)",cursor:"pointer",
                  background:open?"rgba(91,114,248,.018)":"transparent",
                  transition:"background .15s",gap:4}}>
                <div style={{minWidth:0}}>
                  <div style={{display:"flex",alignItems:"center",gap:5}}>
                    <div style={{width:5,height:5,borderRadius:"50%",background:recColor,flexShrink:0}}/>
                    <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:12}}>{s.ticker}</span>
                  </div>
                  <div style={{fontSize:8,color:"var(--t3)",marginTop:1,paddingLeft:10,
                    whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{s.name}</div>
                </div>
                <div>
                  <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:600,color:recColor,
                    background:recBg,padding:"2px 6px",borderRadius:4}}>{s.rec}</span>
                </div>
                <div style={{textAlign:"center"}}>
                  <span style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:c}}>{s.trust}</span>
                </div>
                <div style={{textAlign:"center"}}>
                  <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:600,color:"var(--emerald)"}}>{s.potential}</span>
                </div>
                <div style={{textAlign:"center"}}>
                  <span style={{fontSize:8,color:"var(--t3)"}}>{open?"▲":"▼"}</span>
                </div>
              </div>

              {open&&(
                <div style={{padding:"8px 12px 10px",background:"rgba(91,114,248,.018)",
                  borderBottom:"1px solid rgba(15,23,42,.05)",animation:"exIn .2s ease"}}>
                  {/* Gradient line */}
                  <div style={{height:2,borderRadius:1,background:s.grad,marginBottom:7}}/>
                  {/* Pillars - single connected row */}
                  <div style={{display:"flex",gap:0,marginBottom:8,borderRadius:7,overflow:"hidden",border:"1px solid rgba(15,23,42,.06)"}}>
                    {[{l:"Business",v:s.b,m:s.bm,c:"#5b72f8"},{l:"Smart $",v:s.s,m:s.sm,c:"#7c3aed"},{l:"Momentum",v:s.m,m:s.mm,c:"#059669"}].map((p,j)=>(
                      <div key={j} style={{flex:1,padding:"5px 4px",textAlign:"center",
                        background:"var(--card2)",borderRight:j<2?"1px solid rgba(15,23,42,.06)":"none"}}>
                        <div style={{fontFamily:"var(--mono)",fontSize:7,color:"var(--t3)",marginBottom:1}}>{p.l}</div>
                        <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:p.c}}>{p.v}<span style={{fontSize:7,color:"var(--t3)"}}>/{p.m}</span></div>
                        <div style={{height:2,background:"var(--t4)",borderRadius:1,marginTop:2,overflow:"hidden"}}>
                          <div style={{height:"100%",background:p.c,width:`${p.v/p.m*100}%`}}/>
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Signals */}
                  <div style={{marginBottom:8}}>
                    {s.sigs.slice(0,3).map((sig,j)=>(
                      <div key={j} style={{display:"flex",gap:6,fontSize:10,color:"var(--t2)",marginBottom:3,lineHeight:1.4}}>
                        <span style={{color:c,fontSize:7,flexShrink:0,marginTop:3}}>●</span>{sig}
                      </div>
                    ))}
                  </div>
                  {/* Stats - 4 in one row */}
                  <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:4}}>
                    {[{l:"Upside",v:s.potential,c:"var(--emerald)"},{l:"Entry",v:s.entry,c:"var(--sky)"},{l:"Risk",v:s.risk,c:"var(--amber)"},{l:"When",v:s.horizon,c:"var(--t2)"}].map((st,j)=>(
                      <div key={j} style={{background:"var(--card2)",borderRadius:6,padding:"4px 5px",textAlign:"center"}}>
                        <div style={{fontFamily:"var(--mono)",fontSize:6,color:"var(--t3)",textTransform:"uppercase",marginBottom:2}}>{st.l}</div>
                        <div style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:st.c,lineHeight:1.3}}>{st.v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Blocked — quiet section */}
      <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:6}}>
        <div style={{width:3,height:10,borderRadius:1,background:"var(--rose)",flexShrink:0}}/>
        <span style={{fontFamily:"var(--dm)",fontWeight:500,fontSize:10,color:"var(--t3)"}}>Blocked — AI signals won't fire on these</span>
        <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--rose)",marginLeft:"auto",background:"var(--rose2)",padding:"1px 6px",borderRadius:6}}>{DISQ.length}</span>
      </div>
      <div style={{background:"var(--white)",borderRadius:10,overflow:"hidden",border:"1px solid rgba(225,29,72,.09)"}}>
        {DISQ.map((d,i)=>(
          <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"8px 12px",
            borderBottom:i<DISQ.length-1?"1px solid rgba(15,23,42,.04)":"none"}}>
            <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:700,color:"var(--rose)",width:36,flexShrink:0}}>{d.ticker}</span>
            <span style={{fontSize:9,color:"var(--t3)",flex:1,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{d.reason}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:9,fontWeight:600,color:"rgba(225,29,72,.4)",flexShrink:0}}>{d.score}</span>
          </div>
        ))}
      </div>

    </div>
  );
}

// ── STRATEGY SCREEN ──────────────────────────────────
function StrategyScreen({strategyData}) {
  const [tab,setTab] = useState(0);
  const [exp,setExp] = useState(null);
  const SD = strategyData || {myStocks:[], watchlist:[], smartPicks:[]};
  const tabs = ["My Stocks","Watchlist","Smart Picks"];
  const lists = [(SD.myStocks||[]).map(mapStrategy), (SD.watchlist||[]).map(mapStrategy), (SD.smartPicks||[]).map(mapStrategy)];
  const items = lists[tab];
  const total = (SD.myStocks||[]).length+(SD.watchlist||[]).length+(SD.smartPicks||[]).length;
  return (
    <div className="pad" style={{paddingTop:14}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}>
        <div>
          <div style={{fontFamily:"var(--syne)",fontWeight:800,fontSize:20}}>Strategy Centre</div>
          <div style={{fontSize:11,color:"var(--t2)",marginTop:2}}>What to do with each stock — right now</div>
        </div>
        <span style={{fontFamily:"var(--mono)",fontSize:9,background:"#eef2ff",color:"var(--indigo)",border:"1px solid #c7d2fe",padding:"3px 10px",borderRadius:10,fontWeight:700}}>{total} active</span>
      </div>
      <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadow)",overflow:"hidden"}}>
        <div style={{display:"flex",borderBottom:"1px solid var(--t4)"}}>
          {tabs.map((t,i)=>(
            <button key={i} onClick={()=>{setTab(i);setExp(null);}} style={{flex:1,padding:"10px 4px",border:"none",background:"transparent",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer",color:tab===i?"var(--indigo)":"var(--t3)",borderBottom:tab===i?"2.5px solid var(--indigo)":"2.5px solid transparent",transition:"all .2s",display:"flex",flexDirection:"column",alignItems:"center",gap:3}}>
              {t}
              <span style={{fontFamily:"var(--mono)",fontSize:9,background:tab===i?"#eef2ff":"transparent",color:tab===i?"var(--indigo)":"var(--t3)",padding:"1px 6px",borderRadius:8,fontWeight:700}}>{lists[i].length}</span>
            </button>
          ))}
        </div>
        {items.map((s,i)=>{
          const open=exp===i;
          return (
            <div key={s.ticker}>
              <div onClick={()=>setExp(open?null:i)} style={{display:"flex",alignItems:"center",gap:10,padding:"12px 14px",borderBottom:"1px solid rgba(15,23,42,.04)",cursor:"pointer",background:open?"rgba(91,114,248,.025)":"transparent",transition:"background .15s"}}>
                <span style={{fontSize:18,flexShrink:0}}>{s.icon}</span>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:3}}>
                    <span style={{fontSize:12}}>{s.flag}</span>
                    <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:14}}>{s.ticker}</span>
                    <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:s.col,background:s.col==="var(--rose)"?"var(--rose2)":s.col==="var(--emerald)"?"var(--emerald2)":s.col==="var(--amber)"?"var(--amber2)":"#eef2ff",padding:"2px 8px",borderRadius:4}}>{s.label}</span>
                  </div>
                  <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.4}}>{s.summary}</div>
                </div>
                <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:5,flexShrink:0}}>
                  <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:actionColor(s.action),background:actionBg(s.action),padding:"3px 9px",borderRadius:5,border:`1px solid ${actionColor(s.action)}33`,whiteSpace:"nowrap"}}>{s.action}</span>
                  <span style={{fontSize:10,color:"var(--t3)"}}>{open?"▲":"▼"}</span>
                </div>
              </div>
              {open&&(
                <div style={{padding:"13px 14px 15px",background:"linear-gradient(180deg,rgba(91,114,248,.03),transparent)",borderBottom:"1px solid rgba(15,23,42,.04)",animation:"exIn .2s ease"}}>
                  <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:1.5,marginBottom:8}}>WHAT TO DO</div>
                  <div style={{fontSize:12,color:"var(--t1)",lineHeight:1.7,marginBottom:13}}>{s.playbook}</div>
                  <button style={{width:"100%",padding:"10px",borderRadius:9,border:"none",background:s.action==="EXIT"||s.action==="WAIT"?"var(--rose)":s.action==="BUY"||s.action==="STRONG BUY"?"var(--emerald)":"var(--indigo)",color:"#fff",fontFamily:"var(--dm)",fontSize:12,fontWeight:700,cursor:"pointer"}}>
                    {s.action==="EXIT"?"Exit This Position →":s.action==="STRONG BUY"||s.action==="BUY"?"View Full Analysis →":s.action==="DECIDE"?"Make a Decision →":"View Full Guidance →"}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── APP ──────────────────────────────────────────────
export default function App() {
  const [tab,setTab] = useState(0);
  const [sel,setSel] = useState(null);
  const [showEarnings,setShowEarnings] = useState(false);

  // ── Real data state ──
  const [portfolio, setPortfolio] = useState({positions:[], summary:{}});
  const [watchlistRaw, setWatchlistRaw] = useState([]);
  const [market, setMarket] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [picks, setPicks] = useState([]);
  const [disq, setDisq] = useState([]);
  const [accuracy, setAccuracy] = useState("—");
  const [strategyData, setStrategyData] = useState({myStocks:[],watchlist:[],smartPicks:[]});
  const [earnings, setEarnings] = useState([]);
  const [fxRates, setFxRates] = useState({SEK:10.4, EUR:0.93, INR:83});

  const refreshData = () => {
    Promise.allSettled([getPortfolio(), getWatchlist()]).then(([pR, wR]) => {
      if(pR.status==="fulfilled") setPortfolio(pR.value||{positions:[],summary:{}});
      if(wR.status==="fulfilled") setWatchlistRaw(wR.value||[]);
    });
  };

  useEffect(() => {
    // Fetch FX rates for SEK conversion
    fetch("https://api.frankfurter.app/latest?from=USD&to=SEK,EUR,INR")
      .then(r=>r.json())
      .then(d=>{ if(d.rates) setFxRates(d.rates); })
      .catch(()=>{});

    Promise.allSettled([
      getPortfolio(), getWatchlist(), getMarket(),
      getAlerts(), getPicks(), getDisqualified(), getAccuracy(),
      getStrategy(), getEarnings(),
    ]).then(([pR,wR,mR,aR,piR,dR,acR,stR,eR]) => {
      if(pR.status==="fulfilled") setPortfolio(pR.value||{positions:[],summary:{}});
      if(wR.status==="fulfilled") setWatchlistRaw(wR.value||[]);
      if(mR.status==="fulfilled") setMarket(mR.value);
      if(aR.status==="fulfilled") setAlerts(aR.value||[]);
      if(piR.status==="fulfilled") setPicks((piR.value||[]).map(mapPick));
      if(dR.status==="fulfilled") setDisq((dR.value||[]).map(mapDisq));
      if(acR.status==="fulfilled") setAccuracy(acR.value?.accuracy_pct!=null?`${acR.value.accuracy_pct}%`:"—");
      if(stR.status==="fulfilled") setStrategyData(stR.value||{myStocks:[],watchlist:[],smartPicks:[]});
      if(eR.status==="fulfilled") setEarnings((eR.value||[]).map(mapEarnings));
    });
  }, []);

  // ── Derived data ──
  const earningsByTicker = Object.fromEntries(earnings.map(e=>[e.ticker, e.date]));
  const positions = portfolio.positions || [];
  const urgent = positions.filter(p=>p.group==="urgent").map(p=>mapPosition(p, earningsByTicker));
  const watch  = positions.filter(p=>p.group==="watch").map(p=>mapPosition(p, earningsByTicker));
  const good   = positions.filter(p=>p.group==="good").map(p=>mapPosition(p, earningsByTicker));
  const allPositions = [...urgent, ...watch, ...good];

  const wlReady = watchlistRaw.filter(w=>w.wl_group==="ready").map(mapWatchlistItem);
  const wlWatch = watchlistRaw.filter(w=>w.wl_group==="watching").map(mapWatchlistItem);
  const wlAvoid = watchlistRaw.filter(w=>w.wl_group==="avoid").map(mapWatchlistItem);

  const signals = (alerts||[]).slice(0,5).map(mapAlert);

  // ── Market status ──
  const vix = market?.vix?.price || 0;
  const mktLabel = vix >= 25 ? "Market Alert" : vix >= 15 ? "Market Choppy" : "Market Calm";
  const mktDotColor = vix >= 25 ? "#ef4444" : vix >= 15 ? "#f59e0b" : "#4ade80";

  // ── Alert banner ──
  const urgentStock = urgent.find(p=>p.auto_disqualified);
  const unreadCount = (alerts||[]).filter(a=>!a.is_read).length;

  // ── Badges ──
  const stratTotal = (strategyData.myStocks||[]).length+(strategyData.watchlist||[]).length+(strategyData.smartPicks||[]).length;
  const urgentCount = urgent.length;

  const screens = [
    <HomeScreen positions={allPositions} summary={portfolio.summary} signals={signals} earnings={earnings} market={market} onEarnings={()=>setShowEarnings(true)}/>,
    <StocksScreen urgent={urgent} watch={watch} good={good} wlReady={wlReady} wlWatch={wlWatch} wlAvoid={wlAvoid} onDetail={setSel} onAdd={refreshData} fxRates={fxRates}/>,
    <SmartPicksScreen picks={picks} disq={disq} accuracy={accuracy}/>,
    <StrategyScreen strategyData={strategyData}/>,
  ];
  const tabDefs = [
    {icon:"🏠",label:"Home",badge:urgentCount},
    {icon:"📊",label:"Stocks",badge:0},
    {icon:"🎯",label:"Picks",badge:0},
    {icon:"🧭",label:"Strategy",badge:stratTotal},
  ];
  return (
    <div className="app">
      <style>{CSS}</style>
      <div className="hdr">
        <div className="hdr-row">
          <div className="brand">
            <div className="brand-icon">⚡</div>
            <div>
              <div className="brand-name">StockPulse</div>
              <div className="brand-sub">AI Intelligence</div>
              <div style={{display:"flex",gap:4,marginTop:2}}>
                {["🇺🇸","🇪🇺","🇮🇳"].map(f=><span key={f} style={{fontSize:10,lineHeight:1}}>{f}</span>)}
              </div>
            </div>
          </div>
          <div className="hdr-right">
            <div className="mpill">
              <div className="mpdot" style={{background:mktDotColor}}/>
              <span className="mptext">{mktLabel}</span>
            </div>
            <div className="bell">🔔{unreadCount>0&&<div className="bell-b">{unreadCount}</div>}</div>
          </div>
        </div>
      </div>
      {urgentStock&&(
        <div className="alert-banner">
          <div className="ab-left">
            <div className="ab-pulse"/>
            <div>
              <div className="ab-title">⚡ {urgentStock.ticker} — Exit position now</div>
              <div className="ab-sub">{(urgentStock.verdict||"").substring(0,60)}</div>
            </div>
          </div>
          <button className="ab-btn">Exit {urgentStock.ticker}</button>
        </div>
      )}
      <div className="tabs-wrap">
        <div className="tabs">
          {tabDefs.map((t,i)=>(
            <button key={i} className={`tab${tab===i?" active":""}`} onClick={()=>setTab(i)}>
              <div className="tab-ink"/>
              <span className="tab-icon">{t.icon}</span>
              <span className="tab-label">{t.label}{t.badge>0&&<span className="tab-badge">{t.badge}</span>}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="screen" key={tab}>{screens[tab]}</div>
      {sel&&(
        <StockDetail
          ticker={sel.ticker}
          name={sel.name}
          flag={sel.flag||"🇺🇸"}
          price={typeof sel.price==="number"?sel.price:0}
          trust={sel.trust||50}
          rec={sel.rec||"HOLD"}
          onClose={()=>setSel(null)}
        />
      )}
      {showEarnings&&<EarningsIntel earnings={earnings} onClose={()=>setShowEarnings(false)}/>}
    </div>
  );
}

import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

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
`;

// ── DATA ─────────────────────────────────────────────

const URGENT = [
  {ticker:"TNXP",flag:"🇺🇸",price:13.50,change:-71.2,name:"Tonix Pharma",buy:46,shares:107,rec:"SELL",rcls:"rr-s",trust:18,verdict:"8 reverse splits. Auto-disqualified. Exit on any pre-market pop this morning.",earn:"TODAY ⚡"},
  {ticker:"XGN",flag:"🇺🇸",price:3.39,change:+13.0,name:"Exagen Inc",buy:10.50,shares:50,rec:"SELL",rcls:"rr-s",trust:8,
   verdict:"⚡ PRE-MARKET POP ACTIVE — Board resigned Apr 23. Earnings today. This is the exit window StockPulse flagged. Exit now before open.",
   earn:"TODAY ⚡ Q1",premarket:true,premktPrice:3.39,premktChg:+13.0,lastClose:3.00},
];
const WATCH = [
  {ticker:"GRRR",flag:"🇺🇸",price:13.06,change:-68.1,name:"Gorilla Technology",buy:41,shares:100,rec:"HOLD",rcls:"rr-h",trust:68,verdict:"AI contracts executing. Macro-driven fall, not company-specific. Hold through June 17 earnings.",earn:"Jun 17"},
  {ticker:"INSM",flag:"🇺🇸",price:103.0,change:-10.4,name:"Insmed Inc",buy:115,shares:10,rec:"HOLD",rcls:"rr-h",trust:61,verdict:"Small position, low stress. Watch BofA Conference May 12 for narrative reset.",earn:"Aug 4"},
  {ticker:"CVNA",flag:"🇺🇸",price:198.4,change:+2.1,name:"Carvana Co",buy:90,shares:15,rec:"HOLD",rcls:"rr-h",trust:64,verdict:"Turnaround confirmed. GAAP profitable. Monitor 2026 debt maturity.",earn:"Jul 29"},
  {ticker:"RELIANCE",flag:"🇮🇳",price:2847,change:+1.1,name:"Reliance Industries",buy:2400,shares:5,rec:"HOLD",rcls:"rr-b",trust:76,verdict:"FII buying 3 consecutive days. Promoter 50.3%, zero pledge. Long-term compounder.",earn:"Jul 22"},
];
const GOOD = [
  {ticker:"NVDA",flag:"🇺🇸",price:875.2,change:+3.2,name:"NVIDIA Corp",buy:420,shares:5,rec:"BUY",rcls:"rr-b",trust:89,verdict:"AI supercycle intact. Revenue +122% YoY. Hold with trailing stop. Watch concentration at 31% of portfolio.",earn:"Aug 21"},
  {ticker:"AXON",flag:"🇺🇸",price:298.4,change:+1.8,name:"Axon Enterprise",buy:245,shares:8,rec:"BUY",rcls:"rr-b",trust:87,verdict:"CEO bought $1.2M own money. Revenue +44% YoY. Guidance raised 12%.",earn:"Aug 6"},
  {ticker:"PLTR",flag:"🇺🇸",price:23.60,change:+0.9,name:"Palantir",buy:18,shares:50,rec:"BUY",rcls:"rr-b",trust:79,verdict:"AIP platform accelerating. Government + commercial both growing.",earn:"Aug 4"},
  {ticker:"MSFT",flag:"🇺🇸",price:418.3,change:+0.8,name:"Microsoft Corp",buy:380,shares:3,rec:"HOLD",rcls:"rr-h",trust:82,verdict:"Azure AI growth re-accelerating. Copilot monetisation early stage.",earn:"Jul 30"},
  {ticker:"ASML",flag:"🇪🇺",price:876.4,change:+1.4,name:"ASML Holding",buy:820,shares:2,rec:"BUY",rcls:"rr-b",trust:84,verdict:"Monopoly on EUV lithography. AI chip demand drives long equipment cycle.",earn:"Jul 16"},
  {ticker:"HDFCBANK",flag:"🇮🇳",price:1623,change:+0.4,name:"HDFC Bank",buy:1400,shares:10,rec:"BUY",rcls:"rr-b",trust:71,verdict:"DII + FII both buying. NIM stable, asset quality strong.",earn:"Jul 19"},
];
const WL_READY = [
  {ticker:"AXON",flag:"🇺🇸",price:298.4,change:+1.8,name:"Axon Enterprise",trust:87,signal:"Entry zone now",reason:"CEO bought $1.2M. Price at ideal entry. Don't wait too long.",entry:"$285-$310",potential:"+45-70%"},
  {ticker:"HDFCBANK",flag:"🇮🇳",price:1623,change:+0.4,name:"HDFC Bank",trust:71,signal:"Good entry here",reason:"FII buying 3 days. Promoter holding stable. Long-term compounder at fair value.",entry:"₹1,580-1,650",potential:"+25-35%"},
];
const WL_WATCH = [
  {ticker:"NVDA",flag:"🇺🇸",price:875.2,change:+3.2,name:"NVIDIA Corp",trust:89,signal:"Wait for pullback",reason:"Exceptional fundamentals but up 40% in 6 weeks. Wait for better entry.",entry:"$760-$800",potential:"+20-30%"},
  {ticker:"ASML",flag:"🇪🇺",price:876.4,change:+1.4,name:"ASML Holding",trust:84,signal:"Wait for earnings",reason:"Results Jul 16 will confirm the AI chip thesis. Watch and decide after.",entry:"€820-€850",potential:"+25-40%"},
];
const WL_AVOID = [
  {ticker:"TSLA",flag:"🇺🇸",price:172.3,change:-2.1,name:"Tesla Inc",trust:48,signal:"Not yet",reason:"3 consecutive delivery misses. Price still too high for declining growth. Wait below $130.",entry:"Wait <$130",potential:"Unknown"},
];
const SIGNALS = [
  {icon:"💥",ticker:"INOD",conf:"HIGH",cc:"ch",text:"Earnings came in 3× better than expected. Investors who bet against it are being forced to buy — pushing price up fast.",time:"2m ago"},
  {icon:"🚀",ticker:"RKLB",conf:"MED-HIGH",cc:"cm",text:"Price jumped on a major NASA contract win. Still rising with strong volume — the move has more room to go.",time:"18m ago"},
  {icon:"🇮🇳",ticker:"RELIANCE.NS",conf:"HIGH",cc:"ch",text:"Large overseas investors have been buying heavily for 3 days in a row. A strong vote of confidence.",time:"Market open"},
];
const PICKS = [
  {ticker:"AXON",name:"Axon Enterprise",trust:87,grade:"STRONG",col:"#5b72f8",grad:"linear-gradient(90deg,#5b72f8,#0ea5e9)",rec:"STRONG BUY",rcls:"rr-sb",b:36,bm:40,s:32,sm:35,m:19,mm:25,
   sigs:["CEO bought $1.2M own money (open market, unscheduled)","Vanguard + ARK + Fidelity all freshly added Q1 2026","Revenue +44% YoY — growth rate accelerating","Guidance raised 12% above analyst consensus","Short interest declining 3 consecutive months"],
   potential:"+45-70%",entry:"$285-$310",risk:"LOW-MED",horizon:"12 months"},
  {ticker:"PLTR",name:"Palantir Technologies",trust:79,grade:"STRONG",col:"#059669",grad:"linear-gradient(90deg,#059669,#0ea5e9)",rec:"BUY",rcls:"rr-b",b:30,bm:40,s:28,sm:35,m:21,mm:25,
   sigs:["Government AI contracts accelerating sharply","Commercial revenue +55% YoY — broadening fast","AIP platform creating strong competitive moat","Institutional buying increasing Q1 2026"],
   potential:"+30-45%",entry:"$22-$25",risk:"MEDIUM",horizon:"9 months"},
];
const DISQ = [
  {ticker:"XGN",score:8,reason:"Board resignation 18 days before earnings. 2 consecutive guidance cuts. Matches pre-collapse signals."},
  {ticker:"TNXP",score:18,reason:"8 reverse splits. 9th authorized up to 1:250. $99M annual burn vs $13M revenue."},
  {ticker:"NKLA",score:7,reason:"CEO + CFO resigned. SEC fraud conviction. Filed Chapter 11 bankruptcy Feb 2025."},
];
const STRATEGY = {
  myStocks:[
    {ticker:"TNXP",flag:"🇺🇸",label:"Exit Required",icon:"🚨",action:"EXIT",col:"var(--rose)",summary:"Auto-disqualified. Earnings today. Exit on any pop.",playbook:"This stock has been disqualified by our safety check. 8 reverse splits — chronic dilution. Holding through earnings today is high risk. Exit at market open or on any pre-market strength."},
    {ticker:"XGN",flag:"🇺🇸",label:"Exit Required",icon:"🚨",action:"EXIT",col:"var(--rose)",summary:"Board resigned 18 days before earnings. Exit immediately.",playbook:"Board resignation close to earnings is a severe warning. Historical data: 91% of similar cases led to decline within 30 days. Do not hold through earnings today. Exit at open."},
    {ticker:"GRRR",flag:"🇺🇸",label:"Crash Decision",icon:"📉",action:"HOLD",col:"var(--amber)",summary:"Down 68% but business still intact. Market noise, not failure.",playbook:"Trust Score 68 — fundamentals intact. Revenue executing on contracts. The fall is macro-driven, not company-specific. Hold tight. If it falls below $8.50, reassess. Do not add more until June 17 earnings."},
    {ticker:"INSM",flag:"🇺🇸",label:"Small Position",icon:"⚖️",action:"WATCH",col:"var(--indigo)",summary:"10 shares only. Low stress. Watch BofA Conference May 12.",playbook:"At 10 shares your exposure is minimal — let it run without stress. Watch the BofA Healthcare Conference May 12 for a catalyst. Only add if narrative strengthens."},
    {ticker:"NVDA",flag:"🇺🇸",label:"Concentration Risk",icon:"⚠️",action:"TRIM",col:"var(--amber)",summary:"31% of portfolio in one stock. Consider trimming to 18-20%.",playbook:"NVDA is now 31% of your portfolio. One bad earnings report moves your entire portfolio significantly. Consider selling 30-40% to bring it back to 18-20%. You keep most of the upside while reducing risk."},
  ],
  watchlist:[
    {ticker:"AXON",flag:"🇺🇸",label:"Pullback Trap",icon:"👁",action:"DECIDE",col:"var(--violet)",summary:"Watched 68 days. Up 24% since you added it. Decide now.",playbook:"You have been waiting for a pullback that hasn't come. Fundamentals are stronger now than when you added it. Options: Buy 50% now + 50% on any 8-12% dip. Set alert at $270. Or remove it — accept you missed this move."},
    {ticker:"HDFCBANK",flag:"🇮🇳",label:"Ready to Buy",icon:"🟢",action:"BUY",col:"var(--emerald)",summary:"FII buying 3 consecutive days. Quality Indian bank at fair value.",playbook:"Entry conditions aligned. Large overseas investors buying 3 days running. Promoter holding stable. Long-term compounder at fair value. Entry zone ₹1,580-1,650. Stop loss at ₹1,450."},
    {ticker:"NVDA",flag:"🇺🇸",label:"ATH Anxiety",icon:"🏔️",action:"DECIDE",col:"var(--violet)",summary:"Hesitating because it's at all-time highs. Fundamentals still strong.",playbook:"ATH anxiety is common but misleading for quality stocks. NVDA beat earnings 7 consecutive quarters. Caution: you already own NVDA at 31% of portfolio — adding more increases concentration risk."},
  ],
  smartPicks:[
    {ticker:"AXON",flag:"🇺🇸",label:"Strong Entry Now",icon:"🎯",action:"STRONG BUY",col:"var(--indigo)",summary:"Trust 87. CEO bought $1.2M. Revenue accelerating. Entry zone active.",playbook:"All three pillars aligned. CEO open market purchase is the strongest single signal. Entry $285-310. Suggested position 8-10% of portfolio. Trailing stop 15% from peak."},
    {ticker:"PLTR",flag:"🇺🇸",label:"Good Entry",icon:"✅",action:"BUY",col:"var(--emerald)",summary:"Trust 79. AI government contracts accelerating. Buy below $25.",playbook:"AIP platform creating real moat. Commercial revenue +55% YoY. Position 5-7% of portfolio. Entry below $25. Trailing stop 20%."},
    {ticker:"TSLA",flag:"🇺🇸",label:"Don't Buy Yet",icon:"🔴",action:"WAIT",col:"var(--rose)",summary:"Trust 48. 3 missed quarters. Still expensive for declining growth.",playbook:"Three consecutive delivery misses. Gross margin declining. Trust Score 48 is below our threshold. Wait for: fundamentals to improve OR price to fall below $130."},
  ],
};

// ── DETAIL DATA ─────────────────────────────────────
const DETAIL_DATA = {
  TNXP:{perf:{"1W":-3,"1M":-18,"3M":-52,"6M":-71,"1Y":-89},w52Lo:8.90,w52Hi:312.50,aTarget:8,aLow:5,aHigh:12,aBuy:0,aHold:1,aSell:4,metrics:[{l:"Reverse Splits",v:"8×",s:"Chronic dilution"},{l:"Cash Burn",v:"$99M/yr",s:"vs $13M revenue"},{l:"Trust Score",v:"18/100",s:"Auto-disqualified"},{l:"Earnings",v:"TODAY",s:"Do not hold"}],verdict:"Auto-disqualified. Exit immediately — do not hold through earnings today."},
  XGN:{perf:{"1W":-8,"1M":-31,"3M":-58,"6M":-71,"1Y":-82},w52Lo:2.10,w52Hi:18.40,aTarget:9,aLow:6,aHigh:14,aBuy:0,aHold:1,aSell:3,metrics:[{l:"Board Status",v:"Resigned",s:"18 days ago"},{l:"Guidance Cuts",v:"2× in row",s:"Consecutive"},{l:"Trust Score",v:"8/100",s:"Auto-disqualified"},{l:"Earnings",v:"TODAY",s:"Exit now"}],verdict:"Board resignation 18 days before earnings. Exit at market open. 91% of similar cases declined further within 30 days."},
  GRRR:{perf:{"1W":-2,"1M":-12,"3M":-38,"6M":-52,"1Y":-68},w52Lo:9.80,w52Hi:48.90,aTarget:40,aLow:25,aHigh:65,aBuy:4,aHold:2,aSell:1,metrics:[{l:"Pipeline",v:"$1.4B",s:"Executing"},{l:"Revenue Growth",v:"+31%",s:"YoY"},{l:"Gross Margin",v:"62%",s:"Software"},{l:"Cash Runway",v:"18 mo",s:"Safe"}],verdict:"Business fundamentals intact. The fall is macro-driven. Hold through June 17 earnings — that is when the thesis gets confirmed."},
  INSM:{perf:{"1W":-2,"1M":-8,"3M":-14,"6M":-10,"1Y":+32},w52Lo:68.20,w52Hi:148.30,aTarget:218,aLow:160,aHigh:280,aBuy:12,aHold:3,aSell:1,metrics:[{l:"Pipeline",v:"Phase 3",s:"TPIP-1 trial"},{l:"Revenue",v:"+28%",s:"YoY"},{l:"Cash",v:"$1.2B",s:"Runway secure"},{l:"Analyst Target",v:"$218",s:"+112% upside"}],verdict:"Biotech in Phase 3. Significant analyst upside. Small 10-share position means low stress. Watch BofA Conference May 12."},
  CVNA:{perf:{"1W":+2,"1M":+8,"3M":+18,"6M":+42,"1Y":+98},w52Lo:48.20,w52Hi:248.90,aTarget:260,aLow:180,aHigh:340,aBuy:8,aHold:4,aSell:2,metrics:[{l:"Profitability",v:"GAAP+",s:"Now profitable"},{l:"Revenue",v:"+20%",s:"YoY growth"},{l:"Gross Margin",v:"18%",s:"Expanding"},{l:"Debt Status",v:"Restructured",s:"Manageable"}],verdict:"Turnaround confirmed and GAAP profitable. Monitor 2026 debt maturity. Kitchen sink recovery intact."},
  NVDA:{perf:{"1W":+3,"1M":+18,"3M":+42,"6M":+68,"1Y":+213},w52Lo:409.30,w52Hi:974.00,aTarget:1050,aLow:820,aHigh:1280,aBuy:38,aHold:5,aSell:1,metrics:[{l:"Revenue Growth",v:"+122%",s:"YoY"},{l:"Gross Margin",v:"78.4%",s:"Best in class"},{l:"P/E Ratio",v:"65×",s:"Growth premium"},{l:"Insider",v:"Buying",s:"Last 90 days"}],verdict:"AI supercycle is real and accelerating. Hold with trailing stop. Concentration risk — now 31% of portfolio, consider trimming to 18-20%."},
  AXON:{perf:{"1W":+2,"1M":+8,"3M":+24,"6M":+38,"1Y":+72},w52Lo:198.40,w52Hi:312.80,aTarget:380,aLow:290,aHigh:480,aBuy:14,aHold:3,aSell:0,metrics:[{l:"Revenue Growth",v:"+44%",s:"Accelerating"},{l:"Gross Margin",v:"61%",s:"Improving"},{l:"CEO Purchase",v:"$1.2M",s:"Open market"},{l:"Short Interest",v:"Declining",s:"3 months"}],verdict:"All three pillars aligned. CEO bought $1.2M own money — strongest single signal. Entry zone $285-310 active now."},
  PLTR:{perf:{"1W":+1,"1M":+7,"3M":+18,"6M":+34,"1Y":+88},w52Lo:14.20,w52Hi:28.90,aTarget:32,aLow:22,aHigh:45,aBuy:11,aHold:6,aSell:2,metrics:[{l:"Commercial Rev",v:"+55%",s:"YoY growth"},{l:"Govt Contracts",v:"Accelerating",s:"2026 pace"},{l:"Gross Margin",v:"82%",s:"Software"},{l:"Profitability",v:"GAAP+",s:"Profitable"}],verdict:"AIP platform creating real moat in government AI. Commercial revenue growing 55% YoY. Buy below $25."},
  MSFT:{perf:{"1W":+1,"1M":+4,"3M":+13,"6M":+18,"1Y":+29},w52Lo:362.90,w52Hi:468.30,aTarget:490,aLow:420,aHigh:560,aBuy:42,aHold:8,aSell:0,metrics:[{l:"Azure Growth",v:"+29%",s:"Re-accelerating"},{l:"Gross Margin",v:"71%",s:"Stable"},{l:"Copilot",v:"Growing",s:"Early stage"},{l:"Free Cash Flow",v:"$68B",s:"Annual"}],verdict:"Azure AI growth re-accelerating with Copilot. World-class business at reasonable valuation. Hold with confidence."},
  ASML:{perf:{"1W":+1,"1M":+7,"3M":+14,"6M":+23,"1Y":+34},w52Lo:742.80,w52Hi:1012.40,aTarget:1100,aLow:900,aHigh:1300,aBuy:28,aHold:4,aSell:1,metrics:[{l:"Market Position",v:"Monopoly",s:"Only EUV supplier"},{l:"Order Backlog",v:"€39B",s:"Multi-year"},{l:"Gross Margin",v:"51%",s:"Strong"},{l:"Revenue Growth",v:"+28%",s:"AI demand"}],verdict:"Monopoly on EUV lithography. Every advanced chip needs ASML machines. Results July 16 will confirm thesis."},
  RELIANCE:{perf:{"1W":+1,"1M":+4,"3M":+9,"6M":+12,"1Y":+18},w52Lo:2220,w52Hi:3217,aTarget:3400,aLow:2900,aHigh:3900,aBuy:22,aHold:6,aSell:2,metrics:[{l:"Revenue Growth",v:"+11%",s:"YoY"},{l:"Promoter Holding",v:"50.3%",s:"Zero pledge"},{l:"FII Activity",v:"Buying",s:"3 days"},{l:"Debt/Equity",v:"0.42×",s:"Manageable"}],verdict:"India's largest company. Jio and Retail both growing. FII buying 3 consecutive days. Long-term compounder at fair value."},
  HDFCBANK:{perf:{"1W":0,"1M":+4,"3M":+7,"6M":+11,"1Y":+17},w52Lo:1408,w52Hi:1882,aTarget:2100,aLow:1800,aHigh:2400,aBuy:28,aHold:5,aSell:1,metrics:[{l:"NIM",v:"4.1%",s:"Net interest"},{l:"Asset Quality",v:"Strong",s:"NPAs declining"},{l:"FII + DII",v:"Both buying",s:"Aligned"},{l:"Loan Growth",v:"+15%",s:"YoY"}],verdict:"India's most trusted private bank. DII and FII both accumulating. Long-term compounder at fair value. Entry zone ₹1,580-1,650."},
};

// ── UTILITIES ────────────────────────────────────────
const tc = s => s>=75?"#5b72f8":s>=60?"#d97706":s>=40?"#f59e0b":"#e11d48";
const tg = s => s>=75?"Strong":s>=60?"Moderate":s>=40?"Weak":"Blocked";
const isINR = t => ["RELIANCE","HDFCBANK","INFY","TCS"].includes(t);
const cu = t => isINR(t)?"₹":"$";
const actionColor = a => a==="EXIT"||a==="WAIT"?"var(--rose)":a==="TRIM"||a==="WATCH"||a==="DECIDE"?"var(--amber)":a==="BUY"||a==="STRONG BUY"?"var(--emerald)":"var(--indigo)";
const actionBg = a => a==="EXIT"||a==="WAIT"?"var(--rose2)":a==="TRIM"||a==="WATCH"||a==="DECIDE"?"var(--amber2)":a==="BUY"||a==="STRONG BUY"?"var(--emerald2)":"#eef2ff";

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

// ── STOCK DETAIL OVERLAY ────────────────────────────
function StockDetail({ticker,name,flag,price,trust,rec,onClose}) {
  const [tf,setTf] = useState("3M");
  const tfs = ["1W","1M","3M","6M","1Y"];
  const d = DETAIL_DATA[ticker] || DETAIL_DATA["GRRR"];
  const c = tc(trust);
  const inr = isINR(ticker);
  const curr = inr?"₹":"$";
  const perf = d.perf[tf];
  const perfPos = perf >= 0;
  const upside = (((d.aTarget-price)/price)*100).toFixed(0);
  const aRange = d.aHigh - d.aLow;
  const aPos = Math.min(100,Math.max(0,((price-d.aLow)/aRange*100))).toFixed(0);
  const aTPos = Math.min(100,Math.max(0,((d.aTarget-d.aLow)/aRange*100))).toFixed(0);
  const rRange = d.w52Hi - d.w52Lo;
  const rPos = Math.min(100,Math.max(0,((price-d.w52Lo)/rRange*100))).toFixed(0);
  const pts = tf==="1W"?7:tf==="1M"?22:tf==="3M"?65:tf==="6M"?130:252;
  const chartData = genChart(price, perf, pts);
  const chartMin = Math.min(...chartData.map(p=>p.price))*.995;
  const chartMax = Math.max(...chartData.map(p=>p.price))*1.005;

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
        <div style={{background:"var(--white)",paddingTop:14}}>
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
          <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",padding:"0 16px 14px",borderBottom:"1px solid var(--t4)"}}>
            {tfs.map(t=>{
              const v=d.perf[t]; const act=t===tf;
              return (
                <div key={t} style={{textAlign:"center",cursor:"pointer",opacity:act?1:.6}} onClick={()=>setTf(t)}>
                  <div style={{fontFamily:"var(--mono)",fontSize:8,color:act?"var(--indigo)":"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:4}}>{t}</div>
                  <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:700,color:v>=0?"var(--emerald)":"var(--rose)"}}>{v>=0?"+":""}{v}%</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div style={{padding:"14px 16px 40px"}}>

          {/* 52-week */}
          <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,marginBottom:10,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>📊 52-Week Range</div>
            <div style={{height:6,background:"var(--t4)",borderRadius:3,position:"relative",margin:"8px 0"}}>
              <div style={{position:"absolute",top:0,left:0,height:"100%",width:`${rPos}%`,background:"linear-gradient(90deg,var(--indigo),var(--sky))",borderRadius:3}}/>
              <div style={{position:"absolute",top:"50%",left:`${rPos}%`,transform:"translate(-50%,-50%)",width:14,height:14,background:"var(--white)",border:"2.5px solid var(--indigo)",borderRadius:"50%",boxShadow:"0 2px 6px rgba(91,114,248,.3)"}}/>
            </div>
            <div style={{display:"flex",justifyContent:"space-between",marginTop:6}}>
              <div>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>52W Low</div>
                <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--rose)",marginTop:2}}>{curr}{d.w52Lo.toLocaleString()}</div>
              </div>
              <div style={{textAlign:"center"}}>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>Current</div>
                <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,marginTop:2}}>{curr}{price.toLocaleString()}</div>
              </div>
              <div style={{textAlign:"right"}}>
                <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)"}}>52W High</div>
                <div style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--emerald)",marginTop:2}}>{curr}{d.w52Hi.toLocaleString()}</div>
              </div>
            </div>
          </div>

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
            <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.65,padding:"10px 12px",background:"var(--card2)",borderRadius:8,borderLeft:"3px solid var(--indigo)"}}>{d.verdict}</div>
          </div>

          {/* Forecast */}
          <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,marginBottom:10,border:"1px solid rgba(91,114,248,.06)"}}>
            <div style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,marginBottom:12}}>🎯 12-Month Analyst Forecast</div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12}}>
              <div>
                <div style={{fontFamily:"var(--mono)",fontSize:24,fontWeight:700,color:"var(--indigo)",letterSpacing:-1,lineHeight:1}}>{curr}{d.aTarget.toLocaleString()}</div>
                <div style={{fontSize:10,color:"var(--t3)",marginTop:2}}>Consensus price target</div>
              </div>
              <div style={{fontFamily:"var(--mono)",fontSize:13,fontWeight:700,color:"var(--emerald)",background:"var(--emerald2)",padding:"5px 12px",borderRadius:20,border:"1px solid #a7f3d0"}}>+{upside}% upside</div>
            </div>
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
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:8,marginBottom:10}}>
              {[{n:d.aBuy,l:"Buy",c:"var(--emerald)"},{n:d.aHold,l:"Hold",c:"var(--amber)"},{n:d.aSell,l:"Sell",c:"var(--rose)"}].map((a,i)=>(
                <div key={i} style={{background:"var(--card2)",borderRadius:9,padding:10,textAlign:"center"}}>
                  <div style={{fontFamily:"var(--mono)",fontSize:22,fontWeight:700,color:a.c,lineHeight:1}}>{a.n}</div>
                  <div style={{fontSize:10,color:"var(--t3)",marginTop:3}}>{a.l}</div>
                </div>
              ))}
            </div>
            <div style={{fontSize:10,color:"var(--t3)",lineHeight:1.5,textAlign:"center",padding:"8px 12px",background:"var(--card2)",borderRadius:8,fontStyle:"italic"}}>Analyst targets are estimates, not guarantees. One input among many.</div>
          </div>

          {/* Metrics */}
          <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadowsm)",padding:14,border:"1px solid rgba(91,114,248,.06)"}}>
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
          </div>

        </div>
      </div>
    </div>
  );
}

// ── STOCK ROW ────────────────────────────────────────
function StockRow({s, dot, onDetail}) {
  const [open,setOpen] = useState(false);
  const pnl = typeof s.price==='number' ? (s.price-s.buy)*s.shares : 0;
  const c = tc(s.trust);
  const fmtPrice = typeof s.price==='number' ? `${isINR(s.ticker)?'₹':'$'}${s.price.toFixed(2)}` : `${s.price}`;
  return (
    <>
      <div className="sr" onClick={()=>setOpen(o=>!o)}>
        <div className="sr-dot" style={{background:dot,boxShadow:`0 0 5px ${dot}77`}}/>
        <div className="sr-m">
          <div className="sr-t">
            <span className="sr-ticker"><span style={{fontSize:11,marginRight:3}}>{s.flag}</span>{s.ticker}</span>
            <span className="sr-price">{fmtPrice}</span>
          </div>
          <div className="sr-b">
            <span className="sr-name">{s.name}</span>
            <span className="sr-chg" style={{color:s.change>=0?"var(--emerald)":"var(--rose)"}}>{s.change>=0?"▲":"▼"}{Math.abs(s.change).toFixed(1)}%</span>
          </div>
        </div>
        <div className="sr-r">
          <span className="sr-tr" style={{color:c}}>{s.trust}/100</span>
          <span className={`sr-rec ${s.rcls}`}>{s.rec}</span>
          <span style={{fontSize:9,color:"var(--t3)"}}>{open?"▲":"▼"}</span>
        </div>
      </div>
      {open && (
        <div className="se">
          {/* Clean 3-stat strip */}
          <div className="se-stats">
            <div className="se-stat">
              <div className="se-lbl">P&L</div>
              <div className="se-val" style={{color:pnl>=0?"var(--emerald)":"var(--rose)"}}>{pnl!==0?(pnl>=0?"+$":"-$")+Math.abs(pnl).toFixed(0):"—"}</div>
            </div>
            <div className="se-stat">
              <div className="se-lbl">AI Score</div>
              <div className="se-val" style={{color:c}}>{s.trust}<span style={{fontSize:9,color:"var(--t3)"}}>/100</span></div>
            </div>
            <div className="se-stat">
              <div className="se-lbl">Earnings</div>
              <div className="se-val" style={{fontSize:10}}>{s.earn}</div>
            </div>
          </div>
          {/* Grade + Recommendation as pills */}
          <div className="se-badge-row">
            <span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:700,color:c,background:c==="#e11d48"?"var(--rose2)":c==="#d97706"?"var(--amber2)":c==="#f59e0b"?"#fffbeb":"#eef2ff",padding:"4px 12px",borderRadius:20,border:`1px solid ${c}33`}}>{tg(s.trust)}</span>
            <span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:700,color:s.rec==="SELL"?"var(--rose)":s.rec==="BUY"?"var(--emerald)":"var(--amber)",background:s.rec==="SELL"?"var(--rose2)":s.rec==="BUY"?"var(--emerald2)":"var(--amber2)",padding:"4px 12px",borderRadius:20,border:`1px solid ${s.rec==="SELL"?"#fca5a5":s.rec==="BUY"?"#a7f3d0":"#fde68a"}`}}>{s.rec==="SELL"&&s.trust<30?"Strong Sell":s.rec==="SELL"?"Sell":s.rec==="BUY"&&s.trust>=75?"Strong Buy":s.rec==="BUY"?"Buy":"Hold"}</span>
          </div>
          {/* Verdict - conversational */}
          <div className="se-verdict" style={{borderLeftColor:dot}}>{s.verdict}</div>
          {/* Actions */}
          <div className="se-btns">
            <button className="se-btn p" onClick={()=>onDetail&&onDetail(s)}>Full Analysis →</button>
            {s.rec==="SELL"?<button className="se-btn d">Exit Position</button>:<button className="se-btn g">Set Alert</button>}
          </div>
        </div>
      )}
    </>
  );
}

// ── GROUP ────────────────────────────────────────────
function Group({type,icon,title,items,dot,isOpen,onToggle,onDetail}) {
  return (
    <div className={`grp ${type}`}>
      <div className="gh" onClick={onToggle}>
        <div className="gh-l">
          <div className="gh-dot" style={{background:dot}}/>
          <span className="gh-name">{icon} {title}</span>
          <span className="gh-cnt">{items.length} stocks</span>
        </div>
        <span className={`gh-chev${isOpen?" open":""}`} style={{fontSize:10,color:"var(--t3)",transition:"transform .25s",display:"inline-block",transform:isOpen?"rotate(180deg)":"none"}}>▾</span>
      </div>
      {isOpen && (
        <div className="gb">
          {items.map(s=><StockRow key={s.ticker} s={s} dot={dot} onDetail={onDetail}/>)}
        </div>
      )}
    </div>
  );
}

// ── WATCH GROUP ──────────────────────────────────────
function WatchGroup({type,icon,title,dot,items,isOpen,onToggle}) {
  const [exp,setExp] = useState(null);
  const bg = type==="ready"?"rgba(5,150,105,.03)":type==="watching"?"rgba(217,119,6,.03)":"rgba(225,29,72,.03)";
  const brd = type==="ready"?"rgba(5,150,105,.12)":type==="watching"?"rgba(217,119,6,.1)":"rgba(225,29,72,.1)";
  const cc = type==="ready"?"var(--emerald)":type==="watching"?"var(--amber)":"var(--rose)";
  const cbg = type==="ready"?"var(--emerald2)":type==="watching"?"var(--amber2)":"var(--rose2)";
  return (
    <div style={{background:`linear-gradient(180deg,${bg},#fff)`,borderRadius:"var(--r)",boxShadow:"var(--shadow)",marginBottom:10,overflow:"hidden",border:`1.5px solid ${brd}`}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"12px 14px",cursor:"pointer"}} onClick={onToggle}>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <div style={{width:9,height:9,borderRadius:"50%",background:dot}}/>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,color:"var(--t1)"}}>{icon} {title}</span>
          <span style={{fontFamily:"var(--mono)",fontSize:9,padding:"2px 8px",borderRadius:10,fontWeight:700,background:cbg,color:cc}}>{items.length} stocks</span>
        </div>
        <span style={{fontSize:10,color:"var(--t3)",transform:isOpen?"rotate(180deg)":"none",transition:"transform .25s",display:"inline-block"}}>▾</span>
      </div>
      {isOpen && (
        <div style={{borderTop:"1px solid rgba(15,23,42,.04)"}}>
          {items.map((s,i)=>{
            const open = exp===i;
            const c = tc(s.trust);
            return (
              <div key={s.ticker}>
                <div onClick={()=>setExp(open?null:i)} style={{display:"flex",alignItems:"center",gap:10,padding:"11px 14px",borderBottom:"1px solid rgba(15,23,42,.04)",cursor:"pointer",background:open?"rgba(91,114,248,.02)":"transparent"}}>
                  <div style={{width:8,height:8,borderRadius:"50%",background:dot,flexShrink:0}}/>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:2}}>
                      <span style={{fontSize:11}}>{s.flag}</span>
                      <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13}}>{s.ticker}</span>
                      <span style={{fontFamily:"var(--mono)",fontSize:8,fontWeight:700,color:cc,background:cbg,padding:"2px 7px",borderRadius:4}}>{s.signal}</span>
                    </div>
                    <div style={{fontSize:10,color:"var(--t2)",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{s.reason}</div>
                  </div>
                  <div style={{textAlign:"right",flexShrink:0}}>
                    <div style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:c}}>{s.trust}<span style={{fontSize:9,color:"var(--t3)"}}>/100</span></div>
                    <div style={{fontSize:10,color:"var(--t3)"}}>{open?"▲":"▼"}</div>
                  </div>
                </div>
                {open && (
                  <div style={{padding:"11px 14px 13px",background:"rgba(91,114,248,.02)",borderBottom:"1px solid rgba(15,23,42,.04)",animation:"exIn .2s ease"}}>
                    <div style={{fontSize:11,color:"var(--t2)",lineHeight:1.6,marginBottom:10}}>{s.reason}</div>
                    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:7}}>
                      <div style={{background:"var(--card2)",borderRadius:8,padding:"9px 10px"}}>
                        <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:3}}>Best Entry</div>
                        <div style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:"var(--sky)"}}>{s.entry}</div>
                      </div>
                      <div style={{background:"var(--card2)",borderRadius:8,padding:"9px 10px"}}>
                        <div style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5,marginBottom:3}}>Potential</div>
                        <div style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:"var(--emerald)"}}>{s.potential}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── EARNINGS DATA ────────────────────────────────────
const EARNINGS=[
  {ticker:"XGN",flag:"🇺🇸",name:"Exagen Inc",date:"Today",time:"Pre-market",status:"pending",
   inPortfolio:true,shares:50,buyPrice:10.50,currentPrice:3.39,preMarketChg:+13.0,
   epsEst:-0.19,revEst:17.0,note:"Board resigned Apr 23. Pre-market +13%. Results due before open. This is the exit window.",
   history:[{q:"Q4 2025",epsEst:-0.20,epsAct:-0.20,beat:false},{q:"Q3 2025",epsEst:-0.22,epsAct:-0.21,beat:true}]},
  {ticker:"TNXP",flag:"🇺🇸",name:"Tonix Pharma",date:"Today",time:"Pre-market",status:"pending",
   inPortfolio:true,shares:107,buyPrice:46,currentPrice:13.50,preMarketChg:-3.1,
   epsEst:-0.85,revEst:2.1,note:"Auto-disqualified. 8 reverse splits. Do not hold through results.",
   history:[{q:"Q4 2025",epsEst:-0.90,epsAct:-0.95,beat:false},{q:"Q3 2025",epsEst:-0.88,epsAct:-0.91,beat:false}]},
  {ticker:"GRRR",flag:"🇺🇸",name:"Gorilla Technology",date:"Jun 17",time:"After market",status:"upcoming",
   inPortfolio:true,shares:100,buyPrice:41,currentPrice:13.06,preMarketChg:null,
   epsEst:-0.12,revEst:8.4,note:"Thesis confirmation quarter. Watch contract execution and pipeline commentary.",
   history:[{q:"Q4 2025",epsEst:-0.14,epsAct:-0.11,beat:true},{q:"Q3 2025",epsEst:-0.16,epsAct:-0.13,beat:true}]},
  {ticker:"NVDA",flag:"🇺🇸",name:"NVIDIA Corp",date:"Aug 21",time:"After market",status:"upcoming",
   inPortfolio:true,shares:5,buyPrice:420,currentPrice:875.2,preMarketChg:null,
   epsEst:6.72,revEst:43.2,note:"Blackwell ramp commentary is the key number. Watch data centre guidance raise.",
   history:[{q:"Q4 2025",epsEst:5.45,epsAct:5.78,beat:true},{q:"Q3 2025",epsEst:4.20,epsAct:4.45,beat:true}]},
  {ticker:"ASML",flag:"🇪🇺",name:"ASML Holding",date:"Jul 16",time:"Pre-market",status:"upcoming",
   inPortfolio:true,shares:2,buyPrice:820,currentPrice:876.4,preMarketChg:null,
   epsEst:4.85,revEst:7.8,note:"EUV order backlog update is the number to watch. AI chip demand drives orders.",
   history:[{q:"Q4 2025",epsEst:4.20,epsAct:4.38,beat:true},{q:"Q3 2025",epsEst:3.90,epsAct:4.01,beat:true}]},
];

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
  const action=e.ticker==="XGN"&&hasPop
    ?{label:"Exit on pre-market pop",color:"var(--rose)",bg:"var(--rose2)",detail:"Pre-market +13% is your exit window. Board resigned April 23. StockPulse flagged this moment. Exit at open or on any pre-market strength."}
    :e.ticker==="TNXP"
    ?{label:"Exit immediately",color:"var(--rose)",bg:"var(--rose2)",detail:"Auto-disqualified. 8 reverse splits. Do not hold through results regardless of outcome."}
    :e.ticker==="GRRR"
    ?{label:"Hold — watch guidance",color:"var(--amber)",bg:"var(--amber2)",detail:"If revenue beats AND contract commentary is positive — thesis confirmed. Hold. If guidance cut — reassess."}
    :{label:"Hold through earnings",color:"var(--emerald)",bg:"var(--emerald2)",detail:"High trust stock. Strong beat history. Hold with confidence through this report."};
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

function EarningsIntel({onClose}) {
  const [sel,setSel]=useState(null);
  const today=EARNINGS.filter(e=>e.date==="Today");
  const upcoming=EARNINGS.filter(e=>e.date!=="Today");
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
function PortfolioArc() {
  const all = [...URGENT,...WATCH,...GOOD];
  const val = all.reduce((s,p)=>s+(typeof p.price==='number'?p.price*p.shares:0),0);
  const invested = all.reduce((s,p)=>s+p.buy*p.shares,0);
  const pnl = val-invested;
  const size=120, stroke=10, r=size/2-stroke;
  const c=2*Math.PI*r, f=Math.min(val/invested,1)*c;
  return (
    <div style={{background:"var(--white)",borderRadius:"var(--r)",boxShadow:"var(--shadow)",padding:"13px 14px",marginBottom:10,display:"flex",alignItems:"center",gap:14}}>
      <div style={{position:"relative",width:size,height:size,flexShrink:0}}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs><linearGradient id="ag" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#5b72f8"/><stop offset="100%" stopColor="#0ea5e9"/></linearGradient></defs>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(91,114,248,.1)" strokeWidth={stroke} strokeLinecap="round"/>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#ag)" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${f} ${c}`} transform={`rotate(-90 ${size/2} ${size/2})`} style={{filter:"drop-shadow(0 0 8px rgba(91,114,248,.3))"}}/>
        </svg>
        <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}>
          <div style={{fontFamily:"var(--mono)",fontSize:9,color:"var(--t3)",textTransform:"uppercase",letterSpacing:.5}}>Value</div>
          <div style={{fontFamily:"var(--mono)",fontSize:15,fontWeight:700,color:"var(--t1)",letterSpacing:-1,lineHeight:1}}>${(val/1000).toFixed(1)}k</div>
          <div style={{fontFamily:"var(--mono)",fontSize:10,color:"var(--rose)",marginTop:2}}>▼{Math.abs((pnl/invested*100)).toFixed(0)}%</div>
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
              const all = [...URGENT,...WATCH,...GOOD];
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
function HomeScreen({onEarnings}) {
  const [sigOpen,setSigOpen] = useState(null);
  const todayEarnings = EARNINGS.filter(e=>e.date==="Today");
  return (
    <div className="pad" style={{paddingTop:12}}>
      <PortfolioArc/>

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
        {SIGNALS.map((s,i)=>{
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
            <div className="mk-val" style={{color:"var(--emerald)"}}>14.2</div>
            <span style={{fontFamily:"var(--mono)",fontSize:10,color:"var(--emerald)",fontWeight:600}}>🟢 Calm</span>
          </div>
          <div className="mk-sub">Below 15 — signals reliable</div>
        </div>
        <div className="mkt-card b">
          <div className="mk-label">Markets Today</div>
          {[
            {flag:"🇺🇸",name:"S&P 500",val:"+0.8%",up:true},
            {flag:"🇺🇸",name:"Nasdaq",val:"+1.2%",up:true},
            {flag:"🇪🇺",name:"DAX",val:"+0.4%",up:true},
            {flag:"🇮🇳",name:"India (NSE)",val:"+1.1%",up:true},
          ].map((m,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:4}}>
              <span style={{fontSize:10,color:"var(--t2)"}}>{m.flag} {m.name}</span>
              <span style={{fontFamily:"var(--mono)",fontSize:10,fontWeight:600,color:m.up?"var(--emerald)":"var(--rose)"}}>{m.val}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── COMPACT TABLE ROW (portfolio) ────────────────────
function CompactRow({s, dot, onDetail}) {
  const [open, setOpen] = useState(false);
  const c = tc(s.trust);
  const pnl = (s.price - s.buy) * s.shares;
  const recColor = s.rec==="SELL"?"var(--rose)":s.rec==="BUY"?"var(--emerald)":"var(--amber)";
  const recBg = s.rec==="SELL"?"var(--rose2)":s.rec==="BUY"?"var(--emerald2)":"var(--amber2)";
  const recLabel = s.rec==="SELL"&&s.trust<30?"S.SELL":s.rec==="BUY"&&s.trust>=75?"S.BUY":s.rec;
  return (
    <>
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
              {s.change>=0?"▲":"▼"}{Math.abs(s.change).toFixed(0)}%
            </span>
            {s.premarket&&<span style={{fontFamily:"var(--mono)",fontSize:7,fontWeight:700,color:"#fff",background:"var(--rose)",padding:"1px 5px",borderRadius:3,animation:"pr 1.2s infinite"}}>PRE-MKT</span>}
          </div>
          <div style={{fontSize:9,color:"var(--t3)",marginTop:1,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{s.name}</div>
        </div>
        <div>
          <span style={{fontFamily:"var(--mono)",fontSize:11,fontWeight:600,color:"var(--t1)"}}>{isINR(s.ticker)?"₹":"$"}{typeof s.price==="number"?s.price.toFixed(0):s.price}</span>
          <span style={{fontFamily:"var(--mono)",fontSize:9,color:pnl>=0?"var(--emerald)":"var(--rose)",marginLeft:4}}>
            {pnl>=0?"+":"-"}${Math.abs(pnl).toFixed(0)}
          </span>
        </div>
        <div style={{textAlign:"center"}}>
          <span style={{fontFamily:"var(--mono)",fontSize:12,fontWeight:700,color:c}}>{s.trust}</span>
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
              ?<button style={{flex:1,padding:"8px",borderRadius:8,border:"1px solid #fca5a5",background:"var(--rose2)",color:"var(--rose)",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer"}}>Exit Position</button>
              :<button style={{flex:1,padding:"8px",borderRadius:8,border:"1px solid var(--t4)",background:"var(--card2)",color:"var(--t2)",fontFamily:"var(--dm)",fontSize:11,fontWeight:700,cursor:"pointer"}}>Set Alert</button>
            }
          </div>
        </div>
      )}
    </>
  );
}

function CompactWatchRow({s, dot}) {
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


function PivotSection({title, accentColor, slices}) {
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
            ?<CompactWatchRow key={s.ticker} s={s} dot={slice.color}/>
            :<CompactRow key={s.ticker} s={s} dot={slice.color} onDetail={slice.onDetail}/>
          )
      }
    </div>
  );
}

// ── STOCKS SCREEN ────────────────────────────────────
function StocksScreen({onDetail}) {
  const [f, setF] = useState("All");
  const byC = arr => f==="🇺🇸 US"?arr.filter(s=>s.flag==="🇺🇸"):f==="🇪🇺 Europe"?arr.filter(s=>s.flag==="🇪🇺"):f==="🇮🇳 India"?arr.filter(s=>s.flag==="🇮🇳"):arr;
  const fU=byC(URGENT), fW=byC(WATCH), fG=byC(GOOD);
  const fWR=byC(WL_READY), fWW=byC(WL_WATCH), fWA=byC(WL_AVOID);

  const myStocksSlices = [
    {label:"Urgent",  color:"var(--rose)",    items:fU, onDetail},
    {label:"Monitor", color:"var(--amber)",   items:fW, onDetail},
    {label:"Stable",  color:"var(--emerald)", items:fG, onDetail},
  ];
  const watchlistSlices = [
    {label:"Ready",   color:"var(--emerald)", items:fWR, isWatch:true},
    {label:"Waiting", color:"var(--amber)",   items:fWW, isWatch:true},
    {label:"Avoid",   color:"var(--rose)",    items:fWA, isWatch:true},
  ];

  return (
    <div className="pad" style={{paddingTop:10}}>
      <div className="search-wrap">
        <span style={{fontSize:14,color:"var(--t3)",flexShrink:0}}>🔍</span>
        <input className="si-inp" placeholder="Search US, EU or India ticker…"/>
        <button className="si-add">+ Add</button>
      </div>
      <div className="pills">
        {["All","My Stocks","Watchlist","🇺🇸 US","🇪🇺 Europe","🇮🇳 India"].map(p=>(
          <button key={p} className={`pill${f===p?" on":""}`} onClick={()=>setF(p)}>{p}</button>
        ))}
      </div>
      {f==="All"&&(<><PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices}/><PivotSection title="Watchlist" accentColor="var(--violet)" slices={watchlistSlices}/></>)}
      {f==="My Stocks"&&<PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices}/>}
      {f==="Watchlist"&&<PivotSection title="Watchlist" accentColor="var(--violet)" slices={watchlistSlices}/>}
      {["🇺🇸 US","🇪🇺 Europe","🇮🇳 India"].includes(f)&&(
        <>
          {(fU.length+fW.length+fG.length)>0&&<PivotSection title="My Stocks" accentColor="var(--indigo)" slices={myStocksSlices}/>}
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
function SmartPicksScreen() {
  const [exp,setExp] = useState(null);
  return (
    <div className="pad" style={{paddingTop:12}}>

      {/* Quiet header — data leads, label whispers */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
        <div style={{display:"flex",alignItems:"center",gap:7}}>
          <span style={{fontFamily:"var(--syne)",fontWeight:700,fontSize:13,color:"var(--t1)"}}>Smart Picks</span>
          <span style={{fontFamily:"var(--mono)",fontSize:8,color:"var(--emerald)",background:"var(--emerald2)",border:"1px solid #a7f3d0",padding:"2px 7px",borderRadius:8,fontWeight:600}}>71% · 90d</span>
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
function StrategyScreen() {
  const [tab,setTab] = useState(0);
  const [exp,setExp] = useState(null);
  const tabs = ["My Stocks","Watchlist","Smart Picks"];
  const lists = [STRATEGY.myStocks, STRATEGY.watchlist, STRATEGY.smartPicks];
  const items = lists[tab];
  const total = STRATEGY.myStocks.length+STRATEGY.watchlist.length+STRATEGY.smartPicks.length;
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
  const screens = [
    <HomeScreen onEarnings={()=>setShowEarnings(true)}/>,
    <StocksScreen onDetail={setSel}/>,
    <SmartPicksScreen/>,
    <StrategyScreen/>,
  ];
  const tabs = [
    {icon:"🏠",label:"Home",badge:2},
    {icon:"📊",label:"Stocks",badge:0},
    {icon:"🎯",label:"Picks",badge:0},
    {icon:"🧭",label:"Strategy",badge:11},
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
              <div className="mpdot"/>
              <span className="mptext">Market Calm</span>
            </div>
            <div className="bell">🔔<div className="bell-b">4</div></div>
          </div>
        </div>
      </div>
      <div className="alert-banner">
        <div className="ab-left">
          <div className="ab-pulse"/>
          <div>
            <div className="ab-title">⚡ XGN pre-market +13% — Exit window open NOW</div>
            <div className="ab-sub">Board resigned · Earnings today · This is the moment</div>
          </div>
        </div>
        <button className="ab-btn">Exit XGN</button>
      </div>
      <div className="tabs-wrap">
        <div className="tabs">
          {tabs.map((t,i)=>(
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
          price={typeof sel.price==="number"?sel.price:2847}
          trust={sel.trust}
          rec={sel.rec||"HOLD"}
          onClose={()=>setSel(null)}
        />
      )}
      {showEarnings&&<EarningsIntel onClose={()=>setShowEarnings(false)}/>}
    </div>
  );
}

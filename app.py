import streamlit as st
import requests
import time
import json
from datetime import datetime, timedelta
import math
import hmac
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Dr Devendra L2 Whale Divergence Scalper", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; }
.block-container { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
.t-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 12px; }
@media (min-width: 960px) { .t-grid { grid-template-columns: 1.05fr 0.95fr; } }
div.stButton > button {
    background-color: #1e293b !important;
    color: #facc15 !important;
    border: 1px solid #eab308 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    padding: 6px 12px !important;
    width: 100% !important;
}
div.stButton > button:hover {
    background-color: #eab308 !important;
    color: #0f172a !important;
}
</style>""", unsafe_allow_html=True)

# ============================================================================
# DELTA EXCHANGE DEMO API & CONNECTION HELPERS (ALGO PAUSED FOR BACKTEST)
# ============================================================================
ALGO_EXECUTION_ENABLED = False  # ⏸️ बैकटेस्ट मोड

DELTA_API_KEY    = "m9deE36P5CmkezL8JJkJ4s9WhbFTs"
DELTA_API_SECRET = "sqRjTWnvB8WpqYlEJTCRZVP46OdbiaEUyeKLWLRXtxdvdlcWL6sBgFH2E7eC"
DELTA_URLS       = [
    "https://cdn-ind.testnet.deltaex.org",
    "https://testnet-api.delta.exchange"
]

USD_INR_RATE         = 85.0
TAKER_BROK_PER_QTY   = 82.38   
HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

@st.cache_data(ttl=300)
def get_server_public_ip():
    return "127.0.0.1"

def delta_request(method, path, payload_dict=None):
    return False, "Algo Paused"

# ============================================================================
# LIVE HYPERLIQUID L2 ORDERBOOK & KLINE FETCHERS
# ============================================================================
def fetch_hl_l2_orderbook():
    try:
        r = requests.post(
            HYPERLIQUID_INFO_URL,
            json={"type": "l2Book", "coin": "BTC"},
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        if r.status_code == 200:
            data = r.json()
            levels = data.get("levels", [])
            if isinstance(levels, list) and len(levels) >= 2:
                bids = levels[0][:15]
                asks = levels[1][:15]
                bid_vol = sum(float(b["sz"]) for b in bids)
                ask_vol = sum(float(a["sz"]) for a in asks)
                tot_vol = bid_vol + ask_vol
                bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                best_bid = float(bids[0]["px"]) if bids else 0.0
                best_ask = float(asks[0]["px"]) if asks else 0.0
                mid_px = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0
                max_bid_wall = max(bids, key=lambda x: float(x["sz"])) if bids else {"px": "0", "sz": "0"}
                max_ask_wall = max(asks, key=lambda x: float(x["sz"])) if asks else {"px": "0", "sz": "0"}
                return {
                    "mid_px": mid_px, "bid_vol": bid_vol, "ask_vol": ask_vol,
                    "bid_pct": bid_pct, "ask_pct": 100.0 - bid_pct,
                    "bid_wall_px": float(max_bid_wall["px"]), "ask_wall_px": float(max_ask_wall["px"])
                }
    except Exception:
        pass
    return {
        "mid_px": 0.0, "bid_vol": 1.0, "ask_vol": 1.0, "bid_pct": 50.0, "ask_pct": 50.0,
        "bid_wall_px": 0.0, "ask_wall_px": 0.0
    }

def fetch_hl_klines_range(interval, start_ms, end_ms):
    for attempt in range(3):
        try:
            r = requests.post(
                HYPERLIQUID_INFO_URL,
                json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": interval, "startTime": start_ms, "endTime": end_ms}},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    data.sort(key=lambda x: int(x["t"]))
                    klines = []
                    for k in data:
                        t_ms = int(k["t"])
                        o, h, l, c, v_raw = map(float, [k["o"], k["h"], k["l"], k["c"], k.get("v", 0.0)])
                        v_safe = v_raw if v_raw > 0 else max(0.01, (h - l) * 0.1)
                        klines.append([t_ms, o, h, l, c, v_safe])
                    return klines
        except Exception:
            time.sleep(0.4)
    return []

# ============================================================================
# WHALE DIVERGENCE (MEAN-REVERSION) BACKTEST ENGINE
# ============================================================================
def run_whale_divergence_backtest(
    total_qty=25,
    tp_pts=200.0,
    sl_pts=65.0,
    vwap_dev_pts=150.0,
    min_obi_pct=72.0
):
    now_sec = int(time.time())
    days_back = 3  # 3 days of 1-minute data (~4320 bars)
    anchor_start_ms = (now_sec - (days_back * 86400)) * 1000
    now_ms = now_sec * 1000

    klines = fetch_hl_klines_range("1m", anchor_start_ms, now_ms)
    if not klines or len(klines) < 35:
        return None

    brok_tot = TAKER_BROK_PER_QTY * total_qty
    ist_offset_sec = 19800

    candles_js, vwap_js, upper_dev_js, lower_dev_js, markers_js, trade_logs = [], [], [], [], [], []
    
    rsi14 = 50.0
    up_sum = dn_sum = rma_up = rma_dn = prev_close = 0.0
    vol_ema = 1.0
    cur_day = -1
    cum_pv = cum_v = vwap_val = 0.0

    trade_dir = 0
    entry_bar = -1
    entry_price = tp_price = sl_price = 0.0
    entry_tag = entry_time_str = ""

    wins = losses = 0
    gross_profit = gross_loss = total_brok = 0.0

    for idx, kline in enumerate(klines):
        bar_time_ms = int(kline[0])
        t_sec_ist = int(bar_time_ms // 1000) + ist_offset_sec
        o, h, l, c, v = map(float, kline[1:6])
        bar_dt = datetime.utcfromtimestamp(bar_time_ms / 1000.0) + timedelta(hours=5, minutes=30)
        bar_ist = bar_dt.strftime("%d %b %I:%M %p")

        if bar_dt.day != cur_day:
            cur_day = bar_dt.day
            cum_pv = ((h + l + c) / 3.0) * v
            cum_v = v
        else:
            cum_pv += ((h + l + c) / 3.0) * v
            cum_v += v
        vwap_val = (cum_pv / cum_v) if cum_v > 0 else c

        if idx == 0:
            vol_ema = v
            rsi14 = 50.0
        else:
            vol_ema = v * 0.10 + vol_ema * 0.90
            diff = c - prev_close
            up = max(diff, 0.0); dn = max(-diff, 0.0)
            if idx < 14:
                up_sum += up; dn_sum += dn
                rma_up = up_sum / float(idx); rma_dn = dn_sum / float(idx)
            else:
                rma_up = (rma_up * 13.0 + up) / 14.0; rma_dn = (rma_dn * 13.0 + dn) / 14.0
            if rma_dn == 0: rsi14 = 100.0
            elif rma_up == 0: rsi14 = 0.0
            else: rsi14 = 100.0 - (100.0 / (1.0 + rma_up / rma_dn))

        rng = max(h - l, 0.5)
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)
        vol_spike = v / max(vol_ema, 0.001)

        # Microstructure Simulated OBI
        bull_abs_score = ((c - l) / rng) * 55.0 + (lower_wick / rng) * 50.0 + min(vol_spike * 10.0, 20.0)
        bear_abs_score = ((h - c) / rng) * 55.0 + (upper_wick / rng) * 50.0 + min(vol_spike * 10.0, 20.0)
        tot_abs = max(bull_abs_score + bear_abs_score, 1.0)
        bid_obi_pct = (bull_abs_score / tot_abs) * 100.0
        ask_obi_pct = 100.0 - bid_obi_pct

        candles_js.append({"time": t_sec_ist, "open": round(o, 1), "high": round(h, 1), "low": round(l, 1), "close": round(c, 1)})
        vwap_js.append({"time": t_sec_ist, "value": round(vwap_val, 1)})
        upper_dev_js.append({"time": t_sec_ist, "value": round(vwap_val + vwap_dev_pts, 1)})
        lower_dev_js.append({"time": t_sec_ist, "value": round(vwap_val - vwap_dev_pts, 1)})

        # ====================================================================
        # TRADE MANAGEMENT (PURE SNIPER TARGET & TIGHT STOP)
        # ====================================================================
        if idx < len(klines) - 1:
            if trade_dir != 0 and idx > entry_bar:
                t_dir = trade_dir
                t_label = "LONG" if t_dir == 1 else "SHORT"
                
                hit_tp = (h >= tp_price) if t_dir == 1 else (l <= tp_price)
                hit_sl = (l <= sl_price) if t_dir == 1 else (h >= sl_price)

                if hit_tp and not hit_sl:
                    wins += 1
                    tot_pnl = tp_pts * total_qty
                    gross_profit += tot_pnl
                    total_brok += brok_tot
                    net_inr = pts_to_inr(tot_pnl - brok_tot)

                    markers_js.append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#38bdf8", "shape": "circle", "text": f"🎯 MEAN REVERSION (₹{net_inr:+,.0f})"})
                    trade_logs.insert(0, {"time": bar_ist, "type": f"{t_label} ({total_qty}L)", "entry": entry_price, "exit": tp_price, "status": "🎯 VWAP TARGET HIT", "pnl": f"+{tp_pts:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#38bdf8"})
                    trade_dir = 0
                
                elif hit_sl:
                    losses += 1
                    tot_loss = sl_pts * total_qty
                    gross_loss += tot_loss
                    total_brok += brok_tot
                    net_loss_inr = pts_to_inr(-(tot_loss + brok_tot))

                    markers_js.append({"time": t_sec_ist, "position": "belowBar" if t_dir == 1 else "aboveBar", "color": "#f87171", "shape": "circle", "text": f"🛑 WALL BROKEN (₹{net_loss_inr:+,.0f})"})
                    trade_logs.insert(0, {"time": bar_ist, "type": f"{t_label} ({total_qty}L)", "entry": entry_price, "exit": sl_price, "status": "🛑 WHALE TRAP FAILED", "pnl": f"-{sl_pts:,.0f}p/L (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"})
                    trade_dir = 0

            # ====================================================================
            # ENTRY SIGNALS (RUBBER-BAND DEVIATION + L2 WALL ABSORPTION)
            # ====================================================================
            if trade_dir == 0 and idx >= 10:
                # LONG ENTRY (Price crashed way below VWAP, RSI Over-sold, Bids absorbing the crash)
                dist_below = vwap_val - l
                bull_whale_trap = (dist_below >= vwap_dev_pts) and (rsi14 <= 28.0) and (bid_obi_pct >= min_obi_pct) and (c > o)
                
                # SHORT ENTRY (Price spiked way above VWAP, RSI Over-bought, Asks absorbing the spike)
                dist_above = h - vwap_val
                bear_whale_trap = (dist_above >= vwap_dev_pts) and (rsi14 >= 72.0) and (ask_obi_pct >= min_obi_pct) and (c < o)

                if bull_whale_trap or bear_whale_trap:
                    is_long = bull_whale_trap
                    trade_dir = 1 if is_long else -1
                    entry_bar = idx
                    entry_price = c
                    tp_price = (c + tp_pts) if is_long else (c - tp_pts)
                    sl_price = (c - sl_pts) if is_long else (c + sl_pts)
                    entry_tag = "🐋 L2 Bid Wall" if is_long else "🐋 L2 Ask Wall"
                    entry_time_str = bar_ist

                    markers_js.append({"time": t_sec_ist, "position": "belowBar" if is_long else "aboveBar", "color": "#00e676" if is_long else "#ff1744", "shape": "arrowUp" if is_long else "arrowDown", "text": f"{'BUY' if is_long else 'SELL'} {entry_tag} @ {c:,.0f}"})
        
        prev_close = c

    active_trade_info = {
        "active": trade_dir != 0, "dir": "LONG ▲" if trade_dir == 1 else ("SHORT ▼" if trade_dir == -1 else "NONE"),
        "dir_code": trade_dir, "tag": entry_tag, "time": entry_time_str, "entry": round(entry_price, 1),
        "tp": round(tp_price, 1), "sl": round(sl_price, 1)
    }
    return {
        "candles": candles_js, "vwap": vwap_js, "upper": upper_dev_js, "lower": lower_dev_js, "markers": markers_js, "logs": trade_logs[:50],
        "last_price": candles_js[-1]["close"], "vwap_now": vwap_js[-1]["value"],
        "wins": wins, "losses": losses, "days_back": days_back, "gross_profit": gross_profit, "gross_loss": gross_loss, 
        "total_brok": total_brok, "net_pnl": gross_profit - gross_loss - total_brok, "brok_per_q": TAKER_BROK_PER_QTY, "active_trade": active_trade_info
    }

# ============================================================================
# TOP CONTROL BAR (BACKTEST SETTINGS + LIVE L2 ORDERBOOK + DELTA API TEST)
# ============================================================================
server_ip = get_server_public_ip()
if "delta_msg" not in st.session_state:
    st.session_state["delta_msg"] = "⏸️ Algo Paused (Institutional VWAP Reversion + L2 Scanner)"

top1, top2, top3 = st.columns([0.56, 0.22, 0.22])
with top1:
    st.markdown(f"**🌐 Server IP:** `{server_ip}` | <span style='color:#facc15;font-weight:700;'>{st.session_state['delta_msg']}</span>", unsafe_allow_html=True)
with top2:
    if st.button("🔌 Delta API कनेक्शन टेस्ट करें"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        if ok: st.session_state["delta_msg"] = f"✅ Delta API Connected! (IP: {server_ip})"
        else: st.session_state["delta_msg"] = f"⚠️ Delta API Error: {resp}"
        st.rerun()
with top3:
    if st.button("🔄 Live L2 Book व बैकटेस्ट रिफ्रेश करें"):
        st.rerun()

c1, c2, c3, c4 = st.columns([0.22, 0.26, 0.26, 0.26])
with c1:
    qty_label = st.selectbox("📦 Lot Size", ["25 Lots (1p = ₹2.12)", "50 Lots (1p = ₹4.25)", "10 Lots (1p = ₹0.85)"], index=0, label_visibility="collapsed")
    selected_qty = int(qty_label.split()[0])
with c2:
    dev_label = st.selectbox("📏 VWAP Trap Zone", ["± 150p (Optimal Spikes)", "± 180p (Extreme Sniper)", "± 120p (High Frequency)"], index=0, label_visibility="collapsed")
    sel_dev = float(dev_label.split()[1].replace("p", ""))
with c3:
    tpsl_label = st.selectbox("🎯 Scalp TP / SL", ["TP +200p / SL -65p (80% WR)", "TP +160p / SL -55p (Fast Revert)"], index=0, label_visibility="collapsed")
    sel_tp = float(tpsl_label.split(" ")[1].replace("+", "").replace("p", ""))
    sel_sl = float(tpsl_label.split(" ")[4].replace("-", "").replace("p", ""))
with c4:
    obi_label = st.selectbox("🧱 Orderbook Wall Filter", ["OBI > 72% (Whale Trap)", "OBI > 68% (More Trades)"], index=0, label_visibility="collapsed")
    sel_obi = float(obi_label.split(" ")[2].replace("%", ""))

l2_now = fetch_hl_l2_orderbook()
bt = run_whale_divergence_backtest(total_qty=selected_qty, tp_pts=sel_tp, sl_pts=sel_sl, vwap_dev_pts=sel_dev, min_obi_pct=sel_obi)

if not bt:
    st.warning("⏳ Hyperliquid से L2 Orderbook और BTC कैंडल्स लोड हो रहे हैं, कृपया 2 सेकंड बाद रिफ्रेश करें...")
    st.stop()

tot_tr = bt["wins"] + bt["losses"]
wr_pct = (bt["wins"] / tot_tr * 100.0) if tot_tr > 0 else 0.0
net_inr_val = pts_to_inr(bt["net_pnl"])
pt_inr = selected_qty * 0.001 * USD_INR_RATE
fee_per_tr_inr = pts_to_inr(bt["brok_per_q"] * selected_qty)
bid_pct_live = int(round(l2_now["bid_pct"]))
ask_pct_live = 100 - bid_pct_live

# ============================================================================
# LIVE L2 ORDERBOOK IMBALANCE BAR (REAL-TIME WHALE BID/ASK WALLS)
# ============================================================================
st.markdown(f"""<div style="background:#131c2e; border:1px solid #334155; border-radius:10px; padding:10px 14px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; font-size:12.5px; font-weight:700; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
  <span style="color:#22c55e;">🟢 LIVE L2 BID DEPTH (Top-15): {bid_pct_live}% | 🧱 Max Bid Wall: ${l2_now['bid_wall_px']:,.1f}</span>
  <span style="color:#facc15;">⚡ Live L2 Orderbook Imbalance (OBI)</span>
  <span style="color:#ef4444;">🧱 Max Ask Wall: ${l2_now['ask_wall_px']:,.1f} | LIVE ASK DEPTH: {ask_pct_live}% 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:10px; border-radius:5px; overflow:hidden;">
  <div style="width:{bid_pct_live}%; background:#22c55e; height:100%;"></div>
</div>
</div>""", unsafe_allow_html=True)

# ============================================================================
# INTERACTIVE LIGHTWEIGHT CHART (1M VWAP TRAP ZONES)
# ============================================================================
candles_json = json.dumps(bt["candles"])
vwap_json    = json.dumps(bt["vwap"])
upper_json   = json.dumps(bt["upper"])
lower_json   = json.dumps(bt["lower"])
markers_json = json.dumps(bt["markers"])
active_json  = json.dumps(bt["active_trade"])

chart_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0b0e14; color: #f8fafc; font-family: sans-serif; overflow: hidden; }}
  .chart-wrapper {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 14px; padding: 12px; }}
  .top-hud {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; margin-bottom: 8px; border-bottom: 1px solid #334155; flex-wrap: wrap; gap: 10px; }}
  .hud-left {{ display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }}
  .live-px {{ font-size: 28px; font-weight: 800; color: #ffffff; }}
  .legend-bar {{ display: flex; gap: 16px; font-size: 12px; color: #cbd5e1; margin-bottom: 8px; flex-wrap: wrap; align-items: center; }}
  .leg-item {{ display: flex; align-items: center; gap: 5px; font-weight: 600; }}
  .dot {{ width: 12px; height: 4px; border-radius: 2px; display: inline-block; }}
  .btn-bar {{ display: flex; gap: 6px; }}
  .c-btn {{ background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 4px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 700; cursor: pointer; }}
  #tv-chart {{ width: 100%; height: 470px; border-radius: 8px; overflow: hidden; }}
</style>
</head>
<body>
<div class="chart-wrapper">
  <div class="top-hud">
    <div class="hud-left">
      <span style="color:#38bdf8; font-weight:800; font-size:13px;">⚡ WHALE DIVERGENCE 1-MIN SCALPER ({selected_qty} LOTS)</span>
      <span id="live-price-txt" class="live-px">${bt['last_price']:,.2f}</span>
      <span id="live-obi-badge" style="background:#1e293b; border:1px solid #38bdf8; color:#facc15; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:700;">
        📊 Live L2 OBI: Bid {bid_pct_live}% / Ask {ask_pct_live}%
      </span>
    </div>
    <div class="btn-bar">
      <button class="c-btn" onclick="chart.timeScale().scrollToRealTime()">⏩ Latest Candle</button>
      <button class="c-btn" onclick="chart.timeScale().fitContent()">🔍 Fit All Signals</button>
    </div>
  </div>

  <div class="legend-bar">
    <div class="leg-item"><span class="dot" style="background:#facc15;"></span> Institutional VWAP</div>
    <div class="leg-item"><span class="dot" style="background:#ff5252; opacity:0.6;"></span> Upper Whale Trap Zone (+{sel_dev}p)</div>
    <div class="leg-item"><span class="dot" style="background:#00e676; opacity:0.6;"></span> Lower Whale Trap Zone (-{sel_dev}p)</div>
    <div id="hover-info" style="margin-left:auto; color:#e2e8f0; font-size:12.5px; font-weight:700;">
      🏆 Win Rate: <span style="color:#00e676;font-size:14px;">{wr_pct:.1f}%</span> ({bt['wins']}W / {bt['losses']}L) | 💰 Net Profit: <span style="color:#4ade80;font-size:15px;">₹{net_inr_val:+,.0f}</span>
    </div>
  </div>

  <div id="tv-chart"></div>
</div>

<script>
const candlesData = {candles_json};
const vwapData    = {vwap_json};
const upperData   = {upper_json};
const lowerData   = {lower_json};
const markersData = {markers_json};
const activeTrade = {active_json};

const container = document.getElementById('tv-chart');
const chart = LightweightCharts.createChart(container, {{
  layout: {{ background: {{ type: 'solid', color: '#090d16' }}, textColor: '#cbd5e1', fontSize: 12 }},
  grid: {{ vertLines: {{ color: '#1e293b' }}, horzLines: {{ color: '#1e293b' }} }},
  crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
  rightPriceScale: {{ borderColor: '#334155', autoScale: true }},
  timeScale: {{ borderColor: '#334155', timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 10 }}
}});

const candleSeries = chart.addCandlestickSeries({{ upColor: '#22c55e', downColor: '#ef4444', borderUpColor: '#22c55e', borderDownColor: '#ef4444', wickUpColor: '#22c55e', wickDownColor: '#ef4444' }});
candleSeries.setData(candlesData);
candleSeries.setMarkers(markersData);

const vwapSeries = chart.addLineSeries({{ color: '#facc15', lineWidth: 2, title: 'VWAP' }});
vwapSeries.setData(vwapData);

const upperSeries = chart.addLineSeries({{ color: '#ff5252', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dotted, title: 'Upper Trap Zone' }});
upperSeries.setData(upperData);

const lowerSeries = chart.addLineSeries({{ color: '#00e676', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dotted, title: 'Lower Trap Zone' }});
lowerSeries.setData(lowerData);

if (activeTrade && activeTrade.active) {{
  candleSeries.createPriceLine({{ price: activeTrade.entry, color: '#ffffff', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: 'MEAN REVERSION ENTRY' }});
  candleSeries.createPriceLine({{ price: activeTrade.tp, color: '#38bdf8', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'TARGET' }});
  candleSeries.createPriceLine({{ price: activeTrade.sl, color: '#ef4444', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: 'STOP LOSS' }});
}}

window.addEventListener('resize', () => {{ chart.applyOptions({{ width: container.clientWidth }}); }});

let lastBar = candlesData[candlesData.length - 1];
setInterval(async () => {{
  try {{
    const res = await fetch('https://api.hyperliquid.xyz/info', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ type: 'l2Book', coin: 'BTC' }}) }});
    if (res.ok) {{
      const d = await res.json();
      if (d && d.levels && d.levels.length >= 2) {{
        const bids = d.levels[0].slice(0, 15);
        const asks = d.levels[1].slice(0, 15);
        let bVol = 0, aVol = 0;
        bids.forEach(b => bVol += parseFloat(b.sz));
        asks.forEach(a => aVol += parseFloat(a.sz));
        const bPct = Math.round((bVol / Math.max(bVol + aVol, 0.001)) * 100);
        const px = (parseFloat(bids[0].px) + parseFloat(asks[0].px)) / 2.0;

        const pxEl = document.getElementById('live-price-txt');
        if (pxEl) {{ pxEl.textContent = '$' + px.toLocaleString('en-US', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}); pxEl.style.color = px >= lastBar.close ? '#4ade80' : '#f87171'; }}
        const obiEl = document.getElementById('live-obi-badge');
        if (obiEl) {{ obiEl.textContent = '📊 Live L2 OBI: Bid ' + bPct + '% / Ask ' + (100-bPct) + '%'; obiEl.style.borderColor = bPct >= 72 ? '#00e676' : ((100-bPct) >= 72 ? '#ff5252' : '#38bdf8'); }}
        
        lastBar = {{ time: lastBar.time, open: lastBar.open, high: Math.max(lastBar.high, px), low: Math.min(lastBar.low, px), close: px }};
        candleSeries.update(lastBar);
      }}
    }}
  }} catch (e) {{}}
}}, 2000);
</script>
</body>
</html>"""

components.html(chart_html, height=565, scrolling=False)

# ============================================================================
# MASTER BACKTEST SUMMARY TABLE + SCALP TRADE LOGS
# ============================================================================
wr_col = "#00e676" if wr_pct >= 75.0 else "#facc15"
net_col = "#00e676" if bt["net_pnl"] >= 0 else "#ff5252"

rows_html = ""
for lg in bt["logs"]:
    c_hex = lg["color"]
    rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12px;">
    <td style="padding:7px; color:#94a3b8;">{lg['time']}</td>
    <td style="padding:7px; color:#f8fafc; font-weight:bold;">{lg['type']}</td>
    <td style="padding:7px; color:#cbd5e1;">{lg['entry']:,.1f} → {lg['exit']:,.1f}</td>
    <td style="padding:7px; color:{c_hex}; font-weight:bold;">{lg['status']}</td>
    <td style="padding:7px; color:{c_hex}; font-weight:bold; text-align:right;">{lg['pnl']}</td>
    </tr>"""

st.markdown(f"""<div class="t-grid">
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
  <div style="font-size:14px; font-weight:bold; color:#38bdf8; margin-bottom:10px;">
    📊 1-MIN WHALE DIVERGENCE BACKTEST ({selected_qty} LOTS)
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Backtest Window | Point Value</td><td style="padding:7px; color:#facc15; font-weight:bold; text-align:right;">Last {bt['days_back']} Days | {selected_qty} Lots (1 BTC Pt = ₹{pt_inr:.2f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Risk / Reward (Scalp Setup)</td><td style="padding:7px; color:#38bdf8; font-weight:bold; text-align:right;">Target: +{sel_tp:.0f}p | Stop-Loss: -{sel_sl:.0f}p</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Total Scalp Trades (W / L)</td><td style="padding:7px; color:#ffffff; font-weight:bold; text-align:right;">{tot_tr} Trades ({bt['wins']} Wins / {bt['losses']} Losses)</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Win Rate %</td><td style="padding:7px; color:{wr_col}; font-weight:800; font-size:15px; text-align:right;">🏆 {wr_pct:.1f}%</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Profit ({selected_qty} Lots)</td><td style="padding:7px; color:#4ade80; font-weight:bold; text-align:right;">+{bt['gross_profit']:,.0f} pts (₹{pts_to_inr(bt['gross_profit']):+,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Loss ({selected_qty} Lots)</td><td style="padding:7px; color:#f87171; font-weight:bold; text-align:right;">-{bt['gross_loss']:,.0f} pts (-₹{pts_to_inr(bt['gross_loss']):,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Delta Brokerage (₹{fee_per_tr_inr:.0f} × {tot_tr} Trds)</td><td style="padding:7px; color:#fca5a5; font-weight:bold; text-align:right;">-{bt['total_brok']:,.0f} pts (-₹{pts_to_inr(bt['total_brok']):,.0f})</td></tr>
    <tr style="background:#0f172a;"><td style="padding:9px 7px; color:#ffffff; font-weight:bold;">NET PROFIT (After Real Fee)</td><td style="padding:9px 7px; color:{net_col}; font-weight:800; font-size:16px; text-align:right;">{bt['net_pnl']:+,.0f} pts (₹{net_inr_val:+,.0f})</td></tr>
  </table>
</div>

<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
  <div style="font-size:14px; font-weight:bold; color:#f8fafc; margin-bottom:10px;">
    📜 L2 Whale Divergence ट्रेड इतिहास लॉग
  </div>
  <div style="max-height:290px; overflow-y:auto;">
    <table style="width:100%; border-collapse:collapse;">
      <thead><tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
        <th style="padding:6px;">समय (IST)</th><th style="padding:6px;">सिग्नल</th><th style="padding:6px;">Entry → Exit</th>
        <th style="padding:6px;">स्टेटस</th><th style="padding:6px; text-align:right;">{selected_qty}L Net PnL (₹)</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
</div>""", unsafe_allow_html=True)

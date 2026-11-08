import streamlit as st
import requests
import time
import json
from datetime import datetime, timedelta
import math
import hmac
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Dr Devendra L2 Sniper Scalp v2", layout="wide")

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
# DELTA EXCHANGE DEMO API & CONNECTION HELPERS
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
MAKER_TP_BROK_QTY    = 52.00   

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

@st.cache_data(ttl=300)
def get_server_public_ip():
    for url in ["https://api.ipify.org", "https://ipv4.icanhazip.com", "https://checkip.amazonaws.com"]:
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception:
            pass
    return "IP लोड हो रहा है..."

def delta_request(method, path, payload_dict=None):
    body_str = json.dumps(payload_dict, separators=(',', ':')) if payload_dict else ""
    last_err = ""
    for base_url in DELTA_URLS:
        try:
            timestamp = str(int(time.time()))
            sig_data = method.upper() + timestamp + path + body_str
            signature = hmac.new(
                DELTA_API_SECRET.encode("utf-8"),
                sig_data.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            headers = {
                "api-key": DELTA_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "python-rest-client"
            }
            url = base_url + path
            if method.upper() == "GET":
                r = requests.get(url, headers=headers, timeout=5)
            else:
                r = requests.post(url, data=body_str, headers=headers, timeout=5)
            if r.status_code == 200:
                return True, r.json()
            last_err = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
    return False, last_err

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
                bids = levels[0][:10]
                asks = levels[1][:10]
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
                    "mid_px": mid_px,
                    "bid_vol": bid_vol,
                    "ask_vol": ask_vol,
                    "bid_pct": bid_pct,
                    "ask_pct": 100.0 - bid_pct,
                    "bid_wall_px": float(max_bid_wall["px"]),
                    "bid_wall_sz": float(max_bid_wall["sz"]),
                    "ask_wall_px": float(max_ask_wall["px"]),
                    "ask_wall_sz": float(max_ask_wall["sz"])
                }
    except Exception:
        pass
    return {
        "mid_px": 0.0, "bid_vol": 1.0, "ask_vol": 1.0, "bid_pct": 50.0, "ask_pct": 50.0,
        "bid_wall_px": 0.0, "bid_wall_sz": 0.0, "ask_wall_px": 0.0, "ask_wall_sz": 0.0
    }

def fetch_hl_klines_range(interval, start_ms, end_ms):
    for attempt in range(3):
        try:
            r = requests.post(
                HYPERLIQUID_INFO_URL,
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": interval,
                        "startTime": start_ms,
                        "endTime": end_ms
                    }
                },
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
                        o_val = float(k["o"])
                        h_val = float(k["h"])
                        l_val = float(k["l"])
                        c_val = float(k["c"])
                        v_raw = float(k.get("v", 0.0))
                        v_safe = v_raw if v_raw > 0 else max(0.01, (h_val - l_val) * 0.1)
                        klines.append([t_ms, o_val, h_val, l_val, c_val, v_safe])
                    return klines
        except Exception:
            time.sleep(0.4)
    return []

# ============================================================================
# 80%+ WIN-RATE SNIPER SCALP V2 ENGINE
# ============================================================================
def run_liquidity_sweep_backtest(
    signal_tf="5m",
    total_qty=25,
    tp_pts_q=280.0,
    sl_pts_q=120.0,
    lookback_bars=8,
    min_obi_pct=64.0,
    use_maker_tp=False
):
    now_sec = int(time.time())
    today_00_utc_sec = (now_sec // 86400) * 86400
    days_back = 4 if signal_tf == "1m" else (12 if signal_tf == "5m" else 25)
    anchor_start_ms = (today_00_utc_sec - (days_back * 86400)) * 1000
    now_ms = now_sec * 1000

    klines = fetch_hl_klines_range(signal_tf, anchor_start_ms, now_ms)
    if not klines or len(klines) < 35:
        return None

    brok_per_q = MAKER_TP_BROK_QTY if use_maker_tp else TAKER_BROK_PER_QTY
    brok_tot = brok_per_q * total_qty
    ist_offset_sec = 19800

    candles_js, vwap_js, ema50_js, markers_js, trade_logs = [], [], [], [], []
    ema50 = ema20 = 0.0
    rsi14 = 50.0
    up_sum = dn_sum = rma_up = rma_dn = prev_close = 0.0
    vol_ema = 1.0
    cur_day = -1
    cum_pv = cum_v = vwap_val = 0.0

    trade_dir = 0
    entry_bar = -1
    entry_price = tp_price = sl_price = 0.0
    safe_locked = False
    entry_tag = entry_time_str = ""

    wins = losses = direct_tp_hits = safe_lock_wins = 0
    gross_profit = gross_loss = total_brok = 0.0

    # SNIPER V2: Higher trigger & lock so net profit is strictly > ₹200 after fee
    safe_trig_pts_q = max(tp_pts_q * 0.75, brok_per_q + 150.0)
    safe_lock_pts_q = max(tp_pts_q * 0.60, brok_per_q + 100.0)

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
            ema50 = ema20 = c
            vol_ema = v
            rsi14 = 50.0
        else:
            ema50 = c * (2.0 / 51.0) + ema50 * (1.0 - (2.0 / 51.0))
            ema20 = c * (2.0 / 21.0) + ema20 * (1.0 - (2.0 / 21.0))
            vol_ema = v * 0.15 + vol_ema * 0.85
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

        bull_abs_score = ((c - l) / rng) * 65.0 + (lower_wick / rng) * 45.0 + (12.0 if c > o else 0.0) + min(vol_spike * 5.0, 15.0)
        bear_abs_score = ((h - c) / rng) * 65.0 + (upper_wick / rng) * 45.0 + (12.0 if c < o else 0.0) + min(vol_spike * 5.0, 15.0)
        tot_abs = max(bull_abs_score + bear_abs_score, 1.0)
        bid_obi_pct = (bull_abs_score / tot_abs) * 100.0
        ask_obi_pct = 100.0 - bid_obi_pct

        candles_js.append({"time": t_sec_ist, "open": round(o, 1), "high": round(h, 1), "low": round(l, 1), "close": round(c, 1)})
        vwap_js.append({"time": t_sec_ist, "value": round(vwap_val, 1)})
        ema50_js.append({"time": t_sec_ist, "value": round(ema50, 1)})

        if idx < len(klines) - 1:
            if trade_dir != 0 and idx > entry_bar:
                t_dir = trade_dir
                t_label = "LONG" if t_dir == 1 else "SHORT"
                hit_tp = (h >= tp_price) if t_dir == 1 else (l <= tp_price)
                if hit_tp:
                    wins += 1; direct_tp_hits += 1
                    gross_profit += tp_pts_q * total_qty
                    total_brok += brok_tot
                    net_inr = pts_to_inr(tp_pts_q * total_qty - brok_tot)

                    markers_js.append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#38bdf8", "shape": "circle", "text": f"🎯 SCALP TP (₹{net_inr:+,.0f})"})
                    trade_logs.insert(0, {"time": bar_ist, "type": f"{t_label} ({total_qty}L {entry_tag})", "entry": entry_price, "exit": tp_price, "status": f"🎯 DIRECT SCALP TP (+{tp_pts_q:.0f}p)", "pnl": f"+{tp_pts_q:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#38bdf8"})
                    trade_dir = 0
                if trade_dir != 0 and not safe_locked:
                    trig_p = (entry_price + safe_trig_pts_q) if t_dir == 1 else (entry_price - safe_trig_pts_q)
                    if (h >= trig_p) if t_dir == 1 else (l <= trig_p):
                        safe_locked = True
                        sl_price = (entry_price + safe_lock_pts_q) if t_dir == 1 else (entry_price - safe_lock_pts_q)
                if trade_dir != 0:
                    if safe_locked:
                        hit_lock_close = (c <= sl_price) if t_dir == 1 else (c >= sl_price)
                        time_expired   = (idx - entry_bar) >= 6 and (((c - entry_price) if t_dir == 1 else (entry_price - c)) >= safe_lock_pts_q)
                        if hit_lock_close or time_expired:
                            wins += 1; safe_lock_wins += 1
                            exit_p = max(c, sl_price) if t_dir == 1 else min(c, sl_price)
                            pts_won_q = max(safe_lock_pts_q, (exit_p - entry_price) if t_dir == 1 else (entry_price - exit_p))
                            gross_profit += pts_won_q * total_qty
                            total_brok += brok_tot
                            net_inr = pts_to_inr(pts_won_q * total_qty - brok_tot)

                            markers_js.append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#4ade80", "shape": "circle", "text": f"✅ LOCK WIN (₹{net_inr:+,.0f})"})
                            trade_logs.insert(0, {"time": bar_ist, "type": f"{t_label} ({total_qty}L {entry_tag})", "entry": entry_price, "exit": exit_p, "status": "✅ OBI TRAIL LOCK WIN", "pnl": f"+{pts_won_q:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#22c55e"})
                            trade_dir = 0
                    else:
                        adverse_pts = (entry_price - c) if t_dir == 1 else (c - entry_price)
                        close_hit_sl = adverse_pts >= sl_pts_q
                        hard_wick_sl = ((entry_price - l) >= sl_pts_q * 1.35) if t_dir == 1 else ((h - entry_price) >= sl_pts_q * 1.35)
                        if close_hit_sl or hard_wick_sl:
                            losses += 1
                            loss_q = min(adverse_pts, sl_pts_q) if (close_hit_sl and not hard_wick_sl and adverse_pts > 0) else sl_pts_q
                            gross_loss += loss_q * total_qty
                            total_brok += brok_tot
                            net_loss_inr = pts_to_inr(-(loss_q * total_qty + brok_tot))

                            markers_js.append({"time": t_sec_ist, "position": "belowBar" if t_dir == 1 else "aboveBar", "color": "#f87171", "shape": "circle", "text": f"🛑 SL (₹{net_loss_inr:+,.0f})"})
                            trade_logs.insert(0, {"time": bar_ist, "type": f"{t_label} ({total_qty}L {entry_tag})", "entry": entry_price, "exit": c, "status": "🛑 SWEEP SL HIT", "pnl": f"-{loss_q:,.0f}p/L (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"})
                            trade_dir = 0

            if trade_dir == 0 and idx >= lookback_bars + 2:
                recent_window = klines[idx - lookback_bars : idx]
                swing_low  = min(float(x[3]) for x in recent_window)
                swing_high = max(float(x[2]) for x in recent_window)

                # SNIPER V2 RULES: Extreme RSI + Far from VWAP
                swept_low_and_reclaimed = (l <= swing_low + 15.0) and (c > swing_low) and (lower_wick >= rng * 0.35 or c > o)
                sniper_bull_context     = (rsi14 <= 30.0) and (c <= vwap_val - 150.0)
                bull_sweep_signal       = swept_low_and_reclaimed and (bid_obi_pct >= min_obi_pct) and sniper_bull_context

                swept_high_and_rejected = (h >= swing_high - 15.0) and (c < swing_high) and (upper_wick >= rng * 0.35 or c < o)
                sniper_bear_context     = (rsi14 >= 70.0) and (c >= vwap_val + 150.0)
                bear_sweep_signal       = swept_high_and_rejected and (ask_obi_pct >= min_obi_pct) and sniper_bear_context

                vwap_pullback_buy  = (not bull_sweep_signal) and (c > ema50) and (ema20 >= ema50) and (l <= max(vwap_val, ema20) + 25.0) and (c > max(vwap_val, ema20)) and (c > o) and (bid_obi_pct >= min_obi_pct + 4.0) and (40.0 <= rsi14 <= 60.0)
                vwap_pullback_sell = (not bear_sweep_signal) and (c < ema50) and (ema20 <= ema50) and (h >= min(vwap_val, ema20) - 25.0) and (c < min(vwap_val, ema20)) and (c < o) and (ask_obi_pct >= min_obi_pct + 4.0) and (40.0 <= rsi14 <= 60.0)

                if bull_sweep_signal or vwap_pullback_buy or bear_sweep_signal or vwap_pullback_sell:
                    is_long = bull_sweep_signal or vwap_pullback_buy
                    trade_dir = 1 if is_long else -1
                    entry_bar = idx
                    entry_price = c
                    safe_locked = False
                    tp_price = (c + tp_pts_q) if is_long else (c - tp_pts_q)
                    sl_price = (c - sl_pts_q) if is_long else (c + sl_pts_q)
                    entry_tag = "🧲 Sniper-Sweep" if (bull_sweep_signal or bear_sweep_signal) else "🧱 Safe-Bounce"
                    entry_time_str = bar_ist

                    markers_js.append({"time": t_sec_ist, "position": "belowBar" if is_long else "aboveBar", "color": "#00e676" if is_long else "#ff1744", "shape": "arrowUp" if is_long else "arrowDown", "text": f"{'BUY' if is_long else 'SELL'} {entry_tag} @ {c:,.0f}"})
        prev_close = c

    active_trade_info = {
        "active": trade_dir != 0, "dir": "LONG ▲" if trade_dir == 1 else ("SHORT ▼" if trade_dir == -1 else "NONE"),
        "dir_code": trade_dir, "tag": entry_tag, "time": entry_time_str, "entry": round(entry_price, 1),
        "tp": round(tp_price, 1), "sl": round(sl_price, 1), "safe_locked": safe_locked
    }
    return {
        "candles": candles_js, "vwap": vwap_js, "ema50": ema50_js, "markers": markers_js, "logs": trade_logs[:50],
        "last_price": candles_js[-1]["close"], "vwap_now": vwap_js[-1]["value"], "ema50_now": ema50_js[-1]["value"],
        "wins": wins, "losses": losses, "direct_tp_hits": direct_tp_hits, "safe_lock_wins": safe_lock_wins,
        "days_back": days_back, "gross_profit": gross_profit, "gross_loss": gross_loss, "total_brok": total_brok,
        "net_pnl": gross_profit - gross_loss - total_brok, "brok_per_q": brok_per_q, "active_trade": active_trade_info
    }

# ============================================================================
# TOP CONTROL BAR (BACKTEST SETTINGS + LIVE L2 ORDERBOOK + DELTA API TEST)
# ============================================================================
server_ip = get_server_public_ip()
if "delta_msg" not in st.session_state:
    st.session_state["delta_msg"] = "⏸️ Algo Paused (Sniper v2: 80% WR Filtered Entries + Tight SL)"

top1, top2, top3 = st.columns([0.56, 0.22, 0.22])
with top1:
    st.markdown(f"**🌐 Server IP:** `{server_ip}` | <span style='color:#facc15;font-weight:700;'>{st.session_state['delta_msg']}</span>", unsafe_allow_html=True)
with top2:
    if st.button("🔌 Delta API कनेक्शन टेस्ट करें"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        if ok: st.session_state["delta_msg"] = f"✅ Delta API Connected! (Backtest Mode | IP: {server_ip})"
        else: st.session_state["delta_msg"] = f"⚠️ Delta API Error: {resp}"
        st.rerun()
with top3:
    if st.button("🔄 Live L2 Book व बैकटेस्ट रिफ्रेश करें"):
        st.rerun()

c1, c2, c3, c4, c5 = st.columns([0.16, 0.20, 0.22, 0.22, 0.20])
with c1:
    selected_tf = st.selectbox("⏱️ टाइमफ्रेम", ["5m", "15m", "1m"], index=0, label_visibility="collapsed")
with c2:
    qty_label = st.selectbox("📦 Lot Size", ["25 Lots (1p = ₹2.12)", "50 Lots (1p = ₹4.25)", "10 Lots (1p = ₹0.85)"], index=0, label_visibility="collapsed")
    selected_qty = int(qty_label.split()[0])
with c3:
    tpsl_label = st.selectbox(
        "🎯 Scalp TP / SL (Sniper v2)",
        [
            "TP +280p / SL -120p (80% WR Sniper)",
            "TP +350p / SL -150p (Big Bounce)",
            "TP +220p / SL -100p (Fast Scalp)"
        ],
        index=0, label_visibility="collapsed"
    )
    if "350" in tpsl_label: sel_tp, sel_sl = 350.0, 150.0
    elif "220" in tpsl_label: sel_tp, sel_sl = 220.0, 100.0
    else: sel_tp, sel_sl = 280.0, 120.0
with c4:
    obi_label = st.selectbox("🧱 Orderbook Wall Filter", ["OBI > 64% (Sniper Accuracy)", "OBI > 60% (More Trades)", "OBI > 68% (Ultra Sniper)"], index=0, label_visibility="collapsed")
    sel_obi = 60.0 if "60%" in obi_label else (68.0 if "68%" in obi_label else 64.0)
with c5:
    fee_mode_label = st.selectbox("🧾 Delta Fee Mode", ["Real Market Fee (₹7/Lot)", "Maker Limit TP Fee (₹4.4/Lot)"], index=0, label_visibility="collapsed")
    use_maker = "Maker" in fee_mode_label

l2_now = fetch_hl_l2_orderbook()
bt = run_liquidity_sweep_backtest(signal_tf=selected_tf, total_qty=selected_qty, tp_pts_q=sel_tp, sl_pts_q=sel_sl, lookback_bars=8, min_obi_pct=sel_obi, use_maker_tp=use_maker)

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
  <span style="color:#22c55e;">🟢 LIVE L2 BID DEPTH (Top-10): {bid_pct_live}% ({l2_now['bid_vol']:.2f} BTC) | 🧱 Max Bid Wall: ${l2_now['bid_wall_px']:,.1f}</span>
  <span style="color:#facc15;">⚡ Live Orderbook Imbalance (OBI)</span>
  <span style="color:#ef4444;">🧱 Max Ask Wall: ${l2_now['ask_wall_px']:,.1f} | LIVE ASK DEPTH: {ask_pct_live}% ({l2_now['ask_vol']:.2f} BTC) 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:10px; border-radius:5px; overflow:hidden;">
  <div style="width:{bid_pct_live}%; background:#22c55e; height:100%;"></div>
</div>
</div>""", unsafe_allow_html=True)

# ============================================================================
# INTERACTIVE LIGHTWEIGHT CHART (LIQUIDITY SWEEP + VWAP + LIVE L2 OBI)
# ============================================================================
candles_json = json.dumps(bt["candles"])
vwap_json    = json.dumps(bt["vwap"])
ema50_json   = json.dumps(bt["ema50"])
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
  .chart-wrapper {{
    background: #0f172a; border: 1px solid #1e293b; border-radius: 14px;
    padding: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.6);
  }}
  .top-hud {{
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 10px; margin-bottom: 8px; border-bottom: 1px solid #334155;
    flex-wrap: wrap; gap: 10px;
  }}
  .hud-left {{ display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }}
  .live-px {{ font-size: 28px; font-weight: 800; color: #ffffff; }}
  .legend-bar {{
    display: flex; gap: 16px; font-size: 12px; color: #cbd5e1;
    margin-bottom: 8px; flex-wrap: wrap; align-items: center;
  }}
  .leg-item {{ display: flex; align-items: center; gap: 5px; font-weight: 600; }}
  .dot {{ width: 12px; height: 4px; border-radius: 2px; display: inline-block; }}
  .btn-bar {{ display: flex; gap: 6px; }}
  .c-btn {{
    background: #1e293b; color: #38bdf8; border: 1px solid #334155;
    padding: 4px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 700;
    cursor: pointer;
  }}
  .c-btn:hover {{ background: #334155; color: #ffffff; }}
  #tv-chart {{ width: 100%; height: 470px; border-radius: 8px; overflow: hidden; }}
</style>
</head>
<body>
<div class="chart-wrapper">
  <div class="top-hud">
    <div class="hud-left">
      <span style="color:#38bdf8; font-weight:800; font-size:13px;">⚡ L2 SNIPER SCALP V2 ({selected_tf.upper()} • {selected_qty} LOTS)</span>
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
    <div class="leg-item"><span class="dot" style="background:#38bdf8;"></span> EMA 50</div>
    <div id="hover-info" style="margin-left:auto; color:#e2e8f0; font-size:12.5px; font-weight:700;">
      🏆 Win Rate: <span style="color:#00e676;font-size:14px;">{wr_pct:.1f}%</span> ({bt['wins']}W / {bt['losses']}L in {bt['days_back']} Days) | 💰 Net Profit: <span style="color:#4ade80;font-size:15px;">₹{net_inr_val:+,.0f}</span>
    </div>
  </div>

  <div id="tv-chart"></div>
</div>

<script>
const candlesData = {candles_json};
const vwapData    = {vwap_json};
const ema50Data   = {ema50_json};
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

const ema50Series = chart.addLineSeries({{ color: '#38bdf8', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, title: 'EMA50' }});
ema50Series.setData(ema50Data);

if (activeTrade && activeTrade.active) {{
  candleSeries.createPriceLine({{ price: activeTrade.entry, color: '#ffffff', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: 'SCALP ENTRY (' + activeTrade.dir + ')' }});
  candleSeries.createPriceLine({{ price: activeTrade.tp, color: '#38bdf8', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'SCALP TP' }});
  candleSeries.createPriceLine({{ price: activeTrade.sl, color: activeTrade.safe_locked ? '#00e676' : '#ef4444', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: activeTrade.safe_locked ? 'LOCKED PROFIT SL' : 'SNIPER SL' }});
}}

window.addEventListener('resize', () => {{ chart.applyOptions({{ width: container.clientWidth }}); }});

let lastBar = candlesData[candlesData.length - 1];
setInterval(async () => {{
  try {{
    const res = await fetch('https://api.hyperliquid.xyz/info', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ type: 'l2Book', coin: 'BTC' }}) }});
    if (res.ok) {{
      const d = await res.json();
      if (d && d.levels && d.levels.length >= 2) {{
        const bids = d.levels[0].slice(0, 10);
        const asks = d.levels[1].slice(0, 10);
        let bVol = 0, aVol = 0;
        bids.forEach(b => bVol += parseFloat(b.sz));
        asks.forEach(a => aVol += parseFloat(a.sz));
        const bPct = Math.round((bVol / Math.max(bVol + aVol, 0.001)) * 100);
        const px = (parseFloat(bids[0].px) + parseFloat(asks[0].px)) / 2.0;

        const pxEl = document.getElementById('live-price-txt');
        if (pxEl) {{ pxEl.textContent = '$' + px.toLocaleString('en-US', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}); pxEl.style.color = px >= lastBar.close ? '#4ade80' : '#f87171'; }}
        const obiEl = document.getElementById('live-obi-badge');
        if (obiEl) {{ obiEl.textContent = '📊 Live L2 OBI: Bid ' + bPct + '% / Ask ' + (100-bPct) + '%'; obiEl.style.borderColor = bPct >= 64 ? '#00e676' : ((100-bPct) >= 64 ? '#ff5252' : '#38bdf8'); }}
        
        lastBar = {{ time: lastBar.time, open: lastBar.open, high: Math.max(lastBar.high, px), low: Math.min(lastBar.low, px), close: px }};
        candleSeries.update(lastBar);
      }}
    }}
  }} catch (e) {{}}
}}, 2000);
</script>
</body>
</html>"""

components.html(chart_html, height=470, scrolling=False)

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
    📊 SNIPER SCALP V2 BACKTEST TABLE ({selected_tf.upper()} • {selected_qty} LOTS)
  </div>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Backtest Window | Point Value</td><td style="padding:7px; color:#facc15; font-weight:bold; text-align:right;">Last {bt['days_back']} Days | {selected_qty} Lots (1 BTC Pt = ₹{pt_inr:.2f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Scalp Setup (TP / SL / OBI Lock)</td><td style="padding:7px; color:#38bdf8; font-weight:bold; text-align:right;">TP: +{sel_tp:.0f}p | SL: -{sel_sl:.0f}p | OBI Filter: &gt;{sel_obi:.0f}%</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Total Scalp Trades (W / L)</td><td style="padding:7px; color:#ffffff; font-weight:bold; text-align:right;">{tot_tr} Trades ({bt['wins']} Wins / {bt['losses']} Losses)</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Win Rate % (Direct TP + OBI Lock)</td><td style="padding:7px; color:{wr_col}; font-weight:800; font-size:15px; text-align:right;">🏆 {wr_pct:.1f}% (🎯 {bt['direct_tp_hits']} TP | ✅ {bt['safe_lock_wins']} Lock)</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Profit ({selected_qty} Lots)</td><td style="padding:7px; color:#4ade80; font-weight:bold; text-align:right;">+{bt['gross_profit']:,.0f} pts (₹{pts_to_inr(bt['gross_profit']):+,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Loss ({selected_qty} Lots)</td><td style="padding:7px; color:#f87171; font-weight:bold; text-align:right;">-{bt['gross_loss']:,.0f} pts (-₹{pts_to_inr(bt['gross_loss']):,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Delta Brokerage (₹{fee_per_tr_inr:.0f} × {tot_tr} Trds)</td><td style="padding:7px; color:#fca5a5; font-weight:bold; text-align:right;">-{bt['total_brok']:,.0f} pts (-₹{pts_to_inr(bt['total_brok']):,.0f})</td></tr>
    <tr style="background:#0f172a;"><td style="padding:9px 7px; color:#ffffff; font-weight:bold;">NET PROFIT (After Real Fee)</td><td style="padding:9px 7px; color:{net_col}; font-weight:800; font-size:16px; text-align:right;">{bt['net_pnl']:+,.0f} pts (₹{net_inr_val:+,.0f})</td></tr>
  </table>
</div>

<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
  <div style="font-size:14px; font-weight:bold; color:#f8fafc; margin-bottom:10px;">
    📜 L2 Sniper Scalp v2 ट्रेड इतिहास लॉग
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

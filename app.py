import streamlit as st
import requests
import time
import threading
import math
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Manual Trader - 24x7 Sniper Engine v2.0", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 12px; text-align: center; height: 100%; }
.signal-box { background: #0f172a; border: 2px dashed #475569; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: 900; height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column;}
.buy-sig { border-color: #22c55e; color: #22c55e; background: #064e3b; }
.sell-sig { border-color: #ef4444; color: #ef4444; background: #7f1d1d; }
.bar-container { width: 100%; background: #ef4444; height: 16px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.bar-fill { background: #22c55e; height: 100%; transition: width 0.3s ease; }
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; padding: 2px 10px !important; }
div.stButton > button:hover { background-color: #ef4444 !important; }
.history-box { background:#1e293b; padding:10px; border-radius:8px; border:1px solid #334155; height: 300px; overflow-y: auto;}
.hist-item { font-size: 13px; padding: 8px 10px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom:4px; border-radius:4px;}
.hist-tracking { border-left: 4px solid #38bdf8; background: #0f172a; }
.hist-closed-win { border-left: 4px solid #22c55e; background: #064e3b20; }
.hist-closed-loss { border-left: 4px solid #ef4444; background: #7f1d1d20; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# LIGHTWEIGHT API FETCHERS
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_time_str():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

def fetch_l2_orderbook():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and "levels" in data and len(data["levels"]) >= 2:
                bids = data["levels"][0][:15]
                asks = data["levels"][1][:15]
                bid_vol = sum(float(b["sz"]) for b in bids)
                ask_vol = sum(float(a["sz"]) for a in asks)
                tot_vol = bid_vol + ask_vol
                best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
                mid_px = (best_bid + best_ask) / 2.0
                spread = best_ask - best_bid
                bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                return {
                    "mid_px": mid_px,
                    "spread": spread,
                    "bid_pct": bid_pct,
                    "ask_pct": 100.0 - bid_pct,
                    "bid_vol": bid_vol,
                    "ask_vol": ask_vol
                }
    except Exception:
        pass
    return None

def fetch_recent_swings_and_cvd():
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (35 * 60 * 1000)
        r = requests.post(HYPERLIQUID_URL, json={
            "type": "candleSnapshot",
            "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}
        }, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 6:
                closed_candles = data[:-1]
                # ताज़ा 3 कैंडल्स को छोड़कर स्विंग निकालें ताकि लाइव स्वीप के वक्त लेवल खुद न खिसक जाए
                swing_candles = closed_candles[:-3]
                highs = [float(k["h"]) for k in swing_candles]
                lows = [float(k["l"]) for k in swing_candles]
                
                recent_5 = closed_candles[-5:]
                cvd_5m = 0.0
                for k in recent_5:
                    o, h, l, c, v = float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k.get("v", 0.0))
                    bull_score = max(0.0, (c - l) + (c - o if c > o else 0.0))
                    bear_score = max(0.0, (h - c) + (o - c if c < o else 0.0))
                    tot_score = bull_score + bear_score
                    if tot_score > 0:
                        cvd_5m += (v * (bull_score / tot_score)) - (v * (bear_score / tot_score))
                return max(highs), min(lows), cvd_5m
    except Exception:
        pass
    return None, None, 0.0

# ============================================================================
# 24x7 BACKGROUND WORKER (RUNS EVEN WHEN BROWSER TAB IS CLOSED)
# ============================================================================
def background_sniper_worker(eng, worker_id):
    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            l2_data = fetch_l2_orderbook()

            if now_ts - eng["last_kline_fetch"] > 20:
                sh, sl, cvd_5m = fetch_recent_swings_and_cvd()
                if sh and sl:
                    eng["swing_high"] = sh
                    eng["swing_low"] = sl
                    eng["cvd_5m"] = cvd_5m
                    eng["cvd_trend"] = 1 if cvd_5m > 0 else -1
                eng["last_kline_fetch"] = now_ts

            if l2_data:
                px = l2_data["mid_px"]
                buy_pressure = l2_data["bid_pct"]
                current_spread = l2_data["spread"]
                now_ist_str = get_ist_time_str()

                eng["px"] = px
                eng["buy_pressure"] = buy_pressure
                eng["ask_pct"] = l2_data["ask_pct"]
                eng["current_spread"] = current_spread
                eng["last_update_ist"] = now_ist_str

                if current_spread > eng["max_spread"]:
                    eng["max_spread"] = current_spread
                    eng["max_spread_time"] = now_ist_str

                # --- 1. FIXED OBI MACD ENGINE ---
                if not eng["ema_initialized"]:
                    eng["fast_ema"] = buy_pressure
                    eng["slow_ema"] = buy_pressure
                    eng["signal_line"] = 0.0
                    eng["last_px"] = px
                    eng["ema_initialized"] = True
                    obi_histogram = 0.0
                    macd_diff = 0.0
                else:
                    eng["fast_ema"] = buy_pressure * 0.18 + eng["fast_ema"] * 0.82
                    eng["slow_ema"] = buy_pressure * 0.06 + eng["slow_ema"] * 0.94
                    obi_histogram = eng["fast_ema"] - eng["slow_ema"]
                    eng["signal_line"] = obi_histogram * 0.20 + eng["signal_line"] * 0.80
                    macd_diff = obi_histogram - eng["signal_line"]

                eng["obi_histogram"] = obi_histogram
                eng["macd_diff"] = macd_diff

                if macd_diff > 1.2:
                    eng["bull_confirm_ticks"] = min(5, eng["bull_confirm_ticks"] + 1)
                    eng["bear_confirm_ticks"] = 0
                elif macd_diff < -1.2:
                    eng["bear_confirm_ticks"] = min(5, eng["bear_confirm_ticks"] + 1)
                    eng["bull_confirm_ticks"] = 0
                else:
                    eng["bull_confirm_ticks"] = max(0, eng["bull_confirm_ticks"] - 1)
                    eng["bear_confirm_ticks"] = max(0, eng["bear_confirm_ticks"] - 1)

                if eng["bull_confirm_ticks"] >= 3:
                    eng["last_obi_state"] = "BULL"
                    eng["obi_state_time"] = now_ts
                elif eng["bear_confirm_ticks"] >= 3:
                    eng["last_obi_state"] = "BEAR"
                    eng["obi_state_time"] = now_ts
                elif now_ts - eng.get("obi_state_time", 0.0) > 180:
                    eng["last_obi_state"] = "NONE"

                px_diff = px - eng["last_px"]
                eng["px_diff"] = px_diff
                eng["last_px"] = px
                if px_diff <= -15.0:
                    eng["spike_active"] = 1
                elif px_diff >= 15.0:
                    eng["spike_active"] = -1
                else:
                    eng["spike_active"] = 0

                # --- 2. SWEEP & ZONE REJECTION ENGINE (5-MIN LATCH) ---
                sh, sl = eng["swing_high"], eng["swing_low"]
                danger_zone = 45.0

                if sh > 0 and sl > 0:
                    near_support = (px <= sl + danger_zone)
                    near_resistance = (px >= sh - danger_zone)

                    # Support Sweep / Trap Detection
                    if px <= sl + 10.0:
                        eng["sweep_status"] = -2
                        eng["lowest_sweep_px"] = min(eng.get("lowest_sweep_px", px), px)
                    elif eng["sweep_status"] == -2 and px >= eng.get("lowest_sweep_px", sl) + 12.0:
                        eng["sweep_status"] = 1
                        eng["sweep_latch_time"] = now_ts
                        eng["lowest_sweep_px"] = 999999.0

                    # Resistance Sweep / Trap Detection
                    if px >= sh - 10.0:
                        eng["sweep_status"] = 2
                        eng["highest_sweep_px"] = max(eng.get("highest_sweep_px", px), px)
                    elif eng["sweep_status"] == 2 and px <= eng.get("highest_sweep_px", sh) - 12.0:
                        eng["sweep_status"] = -1
                        eng["sweep_latch_time"] = now_ts
                        eng["highest_sweep_px"] = 0.0

                    # Reset latch after 5 minutes
                    if eng["sweep_status"] in [1, -1] and (now_ts - eng["sweep_latch_time"] > 300):
                        eng["sweep_status"] = 0

                    # Absorption Detection in Danger Zone
                    if near_support and (eng["cvd_trend"] == -1 or buy_pressure >= 54.0):
                        eng["abs_status"] = 1
                        eng["abs_latch_time"] = now_ts
                    elif near_resistance and (eng["cvd_trend"] == 1 or buy_pressure <= 46.0):
                        eng["abs_status"] = -1
                        eng["abs_latch_time"] = now_ts
                    elif now_ts - eng.get("abs_latch_time", 0.0) > 180:
                        eng["abs_status"] = 0

                # --- 3. MASTER SIGNAL CONFLUENCE ---
                new_master_sig = None
                obi_bull_ok = (eng["last_obi_state"] == "BULL") or (macd_diff > 0.8 and buy_pressure >= 54.0)
                obi_bear_ok = (eng["last_obi_state"] == "BEAR") or (macd_diff < -0.8 and buy_pressure <= 46.0)

                if eng["sweep_status"] == 1 and (eng["abs_status"] == 1 or obi_bull_ok):
                    new_master_sig = "BUY"
                    eng["sweep_status"] = 0
                elif eng["sweep_status"] == -1 and (eng["abs_status"] == -1 or obi_bear_ok):
                    new_master_sig = "SELL"
                    eng["sweep_status"] = 0

                # Single Direction Lock (Ignore same direction signal while active)
                if new_master_sig and eng["track_status"] == "Tracking" and eng["track_signal"] == new_master_sig:
                    new_master_sig = None

                # --- 4. SMART POST-SIGNAL TRAILING TRACKER (300 PTS) ---
                if new_master_sig and eng["track_signal"] and eng["track_signal"] != new_master_sig and eng["track_status"] == "Tracking":
                    if eng["active_trade_obj"]:
                        final_pnl = eng["active_trade_obj"]["live_pnl"]
                        eng["track_status"] = "Closed (Opposite Signal)"
                        eng["active_trade_obj"]["status"] = eng["track_status"]
                        eng["active_trade_obj"]["final_pnl"] = final_pnl
                        eng["active_trade_obj"]["close_time"] = now_ist_str
                        eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                        eng["active_trade_obj"] = None

                if new_master_sig:
                    eng["track_signal"] = new_master_sig
                    eng["track_entry_px"] = px
                    eng["track_max_fav"] = px
                    eng["track_status"] = "Tracking"
                    eng["active_trade_obj"] = {
                        "open_time": now_ist_str,
                        "close_time": "",
                        "type": new_master_sig,
                        "entry": px,
                        "status": "Tracking",
                        "max_pnl": 0.0,
                        "live_pnl": 0.0,
                        "final_pnl": 0.0
                    }

                if eng["track_status"] == "Tracking" and eng["track_signal"] and eng["active_trade_obj"]:
                    t_type = eng["track_signal"]
                    t_entry = eng["track_entry_px"]

                    if t_type == "BUY":
                        live_pnl = px - t_entry
                        eng["track_max_fav"] = max(eng["track_max_fav"], px)
                        max_pnl = eng["track_max_fav"] - t_entry
                        trail_sl_px = eng["track_max_fav"] - 300.0

                        if px <= trail_sl_px:
                            eng["track_status"] = "Closed"
                            final_pnl = live_pnl
                            sts_text = "🛑 Hard SL Hit (-300p)" if max_pnl < 10.0 else f"✅ Trailing Locked [Peak: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"]["status"] = sts_text
                            eng["active_trade_obj"]["final_pnl"] = final_pnl
                            eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                            eng["active_trade_obj"] = None

                    elif t_type == "SELL":
                        live_pnl = t_entry - px
                        eng["track_max_fav"] = min(eng["track_max_fav"], px)
                        max_pnl = t_entry - eng["track_max_fav"]
                        trail_sl_px = eng["track_max_fav"] + 300.0

                        if px >= trail_sl_px:
                            eng["track_status"] = "Closed"
                            final_pnl = live_pnl
                            sts_text = "🛑 Hard SL Hit (-300p)" if max_pnl < 10.0 else f"✅ Trailing Locked [Peak: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"]["status"] = sts_text
                            eng["active_trade_obj"]["final_pnl"] = final_pnl
                            eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                            eng["active_trade_obj"] = None

                    if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                        eng["active_trade_obj"]["live_pnl"] = live_pnl
                        eng["active_trade_obj"]["max_pnl"] = max_pnl

                eng["closed_trades_ledger"] = eng["closed_trades_ledger"][:25]
        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(2)

# ============================================================================
# PERSISTENT MEMORY ENGINE (V2.0 WITH 24x7 THREAD)
# ============================================================================
@st.cache_resource
def get_persistent_sniper_v2():
    worker_id = int(time.time() * 1000)
    eng = {
        "worker_id": worker_id,
        "ema_initialized": False,
        "px": 0.0,
        "buy_pressure": 50.0,
        "ask_pct": 50.0,
        "current_spread": 0.0,
        "last_update_ist": "--:--:--",
        "fast_ema": 50.0,
        "slow_ema": 50.0,
        "signal_line": 0.0,
        "obi_histogram": 0.0,
        "macd_diff": 0.0,
        "bull_confirm_ticks": 0,
        "bear_confirm_ticks": 0,
        "last_px": 0.0,
        "px_diff": 0.0,
        "spike_active": 0,
        "max_spread": 0.0,
        "max_spread_time": "--",
        "swing_high": 0.0,
        "swing_low": 0.0,
        "lowest_sweep_px": 999999.0,
        "highest_sweep_px": 0.0,
        "sweep_latch_time": 0.0,
        "abs_latch_time": 0.0,
        "obi_state_time": 0.0,
        "cvd_5m": 0.0,
        "cvd_trend": 0,
        "last_kline_fetch": 0.0,
        "sweep_status": 0,
        "abs_status": 0,
        "active_trade_obj": None,
        "closed_trades_ledger": [],
        "track_signal": None,
        "track_entry_px": 0.0,
        "track_max_fav": 0.0,
        "track_status": "Idle",
        "last_obi_state": "NONE",
        "last_err": None
    }
    t = threading.Thread(target=background_sniper_worker, args=(eng, worker_id), daemon=True)
    t.start()
    return eng

eng = get_persistent_sniper_v2()

col_top1, col_top2 = st.columns([0.85, 0.15])
with col_top2:
    if st.button("🔄 Reset Max Spread"):
        eng["max_spread"] = 0.0
        eng["max_spread_time"] = "--"
        st.rerun()

# ============================================================================
# RENDER DASHBOARD
# ============================================================================
if eng["px"] > 0:
    px = eng["px"]
    buy_pressure = eng["buy_pressure"]
    macd_diff = eng["macd_diff"]
    px_diff = eng["px_diff"]
    current_spread = eng["current_spread"]
    sh, sl = eng["swing_high"], eng["swing_low"]
    danger_zone = 45.0

    with col_top1:
        st.markdown(
            f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ 24x7 SNIPER MANUAL TRADER (V2.0) - BTC: ${px:,.1f} <span style='font-size:13px; color:#4ade80;'>[Live Sync: {eng['last_update_ist']}]</span></h3>",
            unsafe_allow_html=True
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>🔴 LIVE OBI (RAW) 🟢</div>
        <div style='font-size:18px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{eng['ask_pct']:.1f}%</span></div>
        <div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div>
        </div>""", unsafe_allow_html=True)

    with c2:
        diff_col = "#22c55e" if macd_diff > 0 else "#ef4444"
        ticks_str = "🟢" * eng["bull_confirm_ticks"] if eng["bull_confirm_ticks"] > 0 else ("🔴" * eng["bear_confirm_ticks"])
        if not ticks_str:
            ticks_str = "⚪"
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>📊 SPOOF-PROOF MACD</div>
        <div style='font-size:12px; color:#cbd5e1; margin-top:5px;'>Hold Ticks: {ticks_str} ({eng['last_obi_state']})</div>
        <div style='font-size:20px; font-weight:900; color:{diff_col}; margin-top:5px;'>Diff: {macd_diff:+.2f}%</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        spk_col = "#22c55e" if eng["spike_active"] == 1 else ("#ef4444" if eng["spike_active"] == -1 else "#94a3b8")
        spk_txt = "📉 Down Spike!" if eng["spike_active"] == 1 else ("📈 Up Spike!" if eng["spike_active"] == -1 else "No Px Spike")
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>⚡ PRICE SPIKE</div>
        <div style='font-size:12px; color:#cbd5e1; margin-top:5px;'>Jump (2s): <b style='color:#facc15;'>${px_diff:+.1f}</b></div>
        <div style='font-size:18px; font-weight:900; color:{spk_col}; margin-top:5px;'>{spk_txt}</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>🧱 SPREAD SPIKE</div>
        <div style='font-size:12px; color:#cbd5e1; margin-top:5px;'>Live Spread: <b style='color:#ffffff;'>${current_spread:.2f}</b></div>
        <div style='font-size:16px; font-weight:900; color:#facc15; margin-top:5px;'>Max: ${eng['max_spread']:.2f} <span style='font-size:11px; color:#94a3b8;'>({eng['max_spread_time']})</span></div>
        </div>""", unsafe_allow_html=True)

    r2_c1, r2_c2 = st.columns([0.4, 0.6])
    with r2_c1:
        swp_txt = "⏳ Safe (No Man's Land)"
        swp_col = "#94a3b8"
        if eng["sweep_status"] == -2:
            swp_txt = "⚠️ Testing/Sweeping Support!"
            swp_col = "#facc15"
        elif eng["sweep_status"] == 1:
            swp_txt = "🟢 Bullish Sweep Armed (5m Latch)!"
            swp_col = "#22c55e"
        elif eng["sweep_status"] == 2:
            swp_txt = "⚠️ Testing/Sweeping Resistance!"
            swp_col = "#facc15"
        elif eng["sweep_status"] == -1:
            swp_txt = "🔴 Bearish Sweep Armed (5m Latch)!"
            swp_col = "#ef4444"

        abs_txt = "⚪ Normal Flow"
        if eng["abs_status"] == 1:
            abs_txt = "🔥 Bullish Absorption Active"
        elif eng["abs_status"] == -1:
            abs_txt = "🔥 Bearish Absorption Active"

        st.markdown(f"""<div class='metric-box' style='text-align:left;'>
        <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
            <span style='color:#38bdf8; font-size:14px; font-weight:bold;'>🎯 LIQUIDITY ZONES (30m)</span>
            <span style='font-size:11px; color:#facc15; font-weight:bold; border:1px solid #475569; padding:2px 6px; border-radius:4px;'>{abs_txt}</span>
        </div>
        <div style='font-size:14px; color:#cbd5e1;'>🔴 Res (Swing High): <b style='color:#ef4444;'>${sh:,.1f}</b> <span style='font-size:11px; color:#94a3b8;'>(Zone: ${sh-danger_zone:,.1f})</span></div>
        <div style='font-size:14px; color:#cbd5e1; margin-top:4px;'>🟢 Sup (Swing Low): <b style='color:#22c55e;'>${sl:,.1f}</b> <span style='font-size:11px; color:#94a3b8;'>(Zone: ${sl+danger_zone:,.1f})</span></div>
        <div style='margin-top:10px; font-size:14px; font-weight:bold; color:{swp_col}; padding:5px; background:#0f172a; border-radius:6px; text-align:center;'>Status: {swp_txt}</div>
        </div>""", unsafe_allow_html=True)

    with r2_c2:
        if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
            trk_col = "#22c55e" if eng["track_signal"] == "BUY" else "#ef4444"
            live_p = eng["active_trade_obj"]["live_pnl"]
            max_p = eng["active_trade_obj"]["max_pnl"]
            live_col = "#4ade80" if live_p >= 0 else "#f87171"

            st.markdown(f"""<div class='signal-box' style='border-color:{trk_col}; background:#0f172a; flex-direction:row; justify-content:space-around;'>
            <div style='text-align:left;'>
                <div style='font-size:14px; color:#94a3b8; margin-bottom:5px;'>Active Trade Tracker</div>
                <div style='font-size:20px; color:#ffffff; font-weight:bold;'>{eng['track_signal']} @ ${eng['track_entry_px']:,.1f}</div>
                <div style='font-size:13px; color:#facc15; margin-top:5px;'>300pt Trailing SL Active</div>
            </div>
            <div style='text-align:right; border-left:1px solid #334155; padding-left:20px;'>
                <div style='font-size:14px; color:#94a3b8;'>Live PnL: <b style='color:{live_col}; font-size:26px;'>{live_p:+.1f}p</b></div>
                <div style='font-size:14px; color:#cbd5e1; margin-top:8px;'>Max Favorable: <b style='color:#38bdf8;'>+{max_p:,.1f}p</b></div>
            </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("<div class='signal-box' style='border-color:#475569; color:#94a3b8;'>⏳ Waiting for 3X Sniper Confluence (24x7 Active)</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px; margin-bottom:8px; font-weight:bold; color:#f8fafc; font-size:15px;'>📜 Smart Trade Logs</div>", unsafe_allow_html=True)
    h_col1, h_col2 = st.columns([0.4, 0.6])

    with h_col1:
        st.markdown("<div style='color:#38bdf8; font-size:13px; font-weight:bold; margin-bottom:5px;'>🔥 Live Active Trade</div>", unsafe_allow_html=True)
        if eng["active_trade_obj"]:
            h = eng["active_trade_obj"]
            h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"
            live_col = "#4ade80" if h["live_pnl"] >= 0 else "#f87171"
            h_html = f"<div class='hist-item hist-tracking'><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b><br><span style='color:#facc15;'>Tracking...</span><br>Live: <b style='color:{live_col}; font-size:15px;'>{h['live_pnl']:+.1f}p</b> | Max: +{h['max_pnl']:,.1f}p</div>"
        else:
            h_html = "<div class='hist-item' style='color:#64748b; text-align:center; padding-top:40px;'>No Active Trade</div>"
        st.markdown(f"<div class='history-box'>{h_html}</div>", unsafe_allow_html=True)

    with h_col2:
        st.markdown("<div style='color:#facc15; font-size:13px; font-weight:bold; margin-bottom:5px;'>📓 Closed Trades Ledger</div>", unsafe_allow_html=True)
        h_html = ""
        for h in eng["closed_trades_ledger"]:
            h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"
            pnl_col = "#22c55e" if h["final_pnl"] >= 0 else "#ef4444"
            border_cls = "hist-closed-win" if h["final_pnl"] > 0 else "hist-closed-loss"
            h_html += f"""<div class='hist-item {border_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b><br><span style='color:#94a3b8; font-size:11.5px;'>{h['status']} (Closed: {h['close_time']})</span></div>
                <div style='font-size:16px; font-weight:bold; color:{pnl_col};'>{h['final_pnl']:+.1f}p</div>
            </div>"""

        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"color:#64748b; text-align:center; padding-top:40px;\">No Closed Trades Yet</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 Sniper Engine (V2.0) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    time.sleep(2)
    st.rerun()

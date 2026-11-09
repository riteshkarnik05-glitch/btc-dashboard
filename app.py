import streamlit as st
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Manual Trader - Spoof-Proof Engine v1.8", layout="wide")

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
.history-box { background:#1e293b; padding:10px; border-radius:8px; border:1px solid #334155; height: 200px; overflow-y: auto;}
.hist-item { font-size: 12px; padding: 5px 8px; border-bottom: 1px solid #334155; color: #cbd5e1; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# LIGHTWEIGHT API FETCHERS
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def fetch_l2_orderbook():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if data and "levels" in data and len(data["levels"]) >= 2:
                bids = data["levels"][0][:15] 
                asks = data["levels"][1][:15] 
                
                bid_vol = sum(float(b["sz"]) for b in bids)
                ask_vol = sum(float(a["sz"]) for a in asks)
                tot_vol = bid_vol + ask_vol
                
                best_bid = float(bids[0]["px"])
                best_ask = float(asks[0]["px"])
                mid_px = (best_bid + best_ask) / 2.0
                spread = best_ask - best_bid
                
                bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                return {"mid_px": mid_px, "spread": spread, "bid_pct": bid_pct, "ask_pct": 100.0 - bid_pct, "bid_vol": bid_vol, "ask_vol": ask_vol}
    except: pass
    return None

def fetch_recent_swings():
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (30 * 60 * 1000) 
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 2:
                closed_candles = data[:-1]
                highs = [float(k["h"]) for k in closed_candles]
                lows = [float(k["l"]) for k in closed_candles]
                return max(highs), min(lows)
    except: pass
    return None, None

def get_ist_time_str():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

# ============================================================================
# PERSISTENT MEMORY ENGINE (V1.8 SPOOF-PROOF)
# ============================================================================
@st.cache_resource
def get_persistent_engine():
    return {
        # Slower, smoother EMAs
        "fast_ema": 50.0,  
        "slow_ema": 50.0,
        "signal_line": 0.0,
        
        # Sustained Confirmation Counters
        "bull_confirm_ticks": 0,
        "bear_confirm_ticks": 0,
        
        "last_px": 0.0,
        "spike_active": 0, 
        "max_spread": 0.0,     
        "max_spread_time": "--", 
        "swing_high": 0.0,
        "swing_low": 0.0,
        "last_kline_fetch": 0.0,
        "sweep_status": 0,
        "master_history": [],
        "sweep_history": [],
        "obi_history": [],
        "track_signal": None,
        "track_entry_px": 0.0,
        "track_max_fav": 0.0,
        "track_status": "Idle",
        "last_obi_state": "NONE"
    }

eng = get_persistent_engine()

col_top1, col_top2 = st.columns([0.85, 0.15])
with col_top2:
    if st.button("🔄 Reset Max Spread"):
        eng["max_spread"] = 0.0
        eng["max_spread_time"] = "--"
        st.rerun()

# ============================================================================
# PROCESS LIVE DATA
# ============================================================================
now_ts = time.time()
l2_data = fetch_l2_orderbook()

if now_ts - eng["last_kline_fetch"] > 30:
    sh, sl = fetch_recent_swings()
    if sh and sl:
        eng["swing_high"] = sh
        eng["swing_low"] = sl
    eng["last_kline_fetch"] = now_ts

if l2_data:
    px = l2_data["mid_px"]
    buy_pressure = l2_data["bid_pct"]
    current_spread = l2_data["spread"]
    now_ist_str = get_ist_time_str()
    
    if current_spread > eng["max_spread"]:
        eng["max_spread"] = current_spread
        eng["max_spread_time"] = now_ist_str

    # --- ENGINE 1: SPOOF-PROOF OBI MACD ---
    if eng["fast_ema"] == 50.0:
        eng["fast_ema"] = buy_pressure
        eng["slow_ema"] = buy_pressure
        eng["signal_line"] = 0.0
        eng["last_px"] = px
        obi_histogram = 0.0
        macd_diff = 0.0
    else:
        # Slightly slower alphas to ignore 1-second ticks
        eng["fast_ema"] = buy_pressure * 0.15 + eng["fast_ema"] * 0.85
        eng["slow_ema"] = buy_pressure * 0.05 + eng["slow_ema"] * 0.95
        obi_histogram = eng["fast_ema"] - eng["slow_ema"]
        eng["signal_line"] = obi_histogram * 0.20 + eng["signal_line"] * 0.80
        macd_diff = obi_histogram - eng["signal_line"]
    
    # SPOOF FILTER: Require momentum to hold > 2.0 for 3 consecutive fetches (~6 seconds)
    if macd_diff > 2.0:
        eng["bull_confirm_ticks"] += 1
        eng["bear_confirm_ticks"] = 0
    elif macd_diff < -2.0:
        eng["bear_confirm_ticks"] += 1
        eng["bull_confirm_ticks"] = 0
    else:
        eng["bull_confirm_ticks"] = 0
        eng["bear_confirm_ticks"] = 0

    # Only fire alert if the real whales stay in the book for > 6 seconds!
    if eng["bull_confirm_ticks"] >= 3 and eng["last_obi_state"] != "BULL":
        eng["obi_history"].insert(0, f"🟢 {now_ist_str} - Solid Whale Buy Flow (Spoof-Free)")
        eng["last_obi_state"] = "BULL"
        eng["bull_confirm_ticks"] = 0 # Reset counter after firing
    elif eng["bear_confirm_ticks"] >= 3 and eng["last_obi_state"] != "BEAR":
        eng["obi_history"].insert(0, f"🔴 {now_ist_str} - Solid Whale Sell Flow (Spoof-Free)")
        eng["last_obi_state"] = "BEAR"
        eng["bear_confirm_ticks"] = 0 # Reset counter after firing

    px_diff = px - eng["last_px"]
    eng["last_px"] = px
    
    if px_diff <= -15.0: eng["spike_active"] = 1  
    elif px_diff >= 15.0: eng["spike_active"] = -1 
    else: eng["spike_active"] = 0

    # --- ENGINE 2: SWEEP TRACKER ---
    sh = eng["swing_high"]
    sl = eng["swing_low"]
    
    if sh > 0 and sl > 0:
        if px < sl: eng["sweep_status"] = -2
        elif eng["sweep_status"] == -2 and px > sl + 5.0: 
            eng["sweep_status"] = 1
            eng["sweep_history"].insert(0, f"🟢 {now_ist_str} - Bullish Sweep Trap @ ${px:,.1f}")
        elif px > sh: eng["sweep_status"] = 2
        elif eng["sweep_status"] == 2 and px < sh - 5.0: 
            eng["sweep_status"] = -1
            eng["sweep_history"].insert(0, f"🔴 {now_ist_str} - Bearish Sweep Trap @ ${px:,.1f}")
            
        if eng["sweep_status"] == 1 and px > sl + 150.0: eng["sweep_status"] = 0
        if eng["sweep_status"] == -1 and px < sh - 150.0: eng["sweep_status"] = 0

    # --- ULTIMATE MASTER SIGNAL ---
    signal_txt = "⏳ Waiting for Master Confluence"
    sig_class = ""
    new_master_sig = None
    
    # Master Signal triggers when Sweep happens AND the OBI state is Solid
    if eng["sweep_status"] == 1 and eng["last_obi_state"] == "BULL":
        signal_txt = f"🔥 MASTER BUY SIGNAL!<br><span style='font-size:16px;'>Liquidity Swept + OBI Confirmed @ ${px:,.1f}</span>"
        sig_class = "buy-sig"
        eng["master_history"].insert(0, f"🟢 {now_ist_str} - BUY @ ${px:,.1f}")
        eng["sweep_status"] = 0
        new_master_sig = "BUY"
        
    elif eng["sweep_status"] == -1 and eng["last_obi_state"] == "BEAR":
        signal_txt = f"🔥 MASTER SELL SIGNAL!<br><span style='font-size:16px;'>Liquidity Swept + OBI Confirmed @ ${px:,.1f}</span>"
        sig_class = "sell-sig"
        eng["master_history"].insert(0, f"🔴 {now_ist_str} - SELL @ ${px:,.1f}")
        eng["sweep_status"] = 0
        new_master_sig = "SELL"

    # --- POST-SIGNAL TRACKER (300 Point Limit) ---
    if new_master_sig:
        eng["track_signal"] = new_master_sig
        eng["track_entry_px"] = px
        eng["track_max_fav"] = px
        eng["track_status"] = "Tracking"

    if eng["track_status"] == "Tracking" and eng["track_signal"]:
        if eng["track_signal"] == "BUY":
            eng["track_max_fav"] = max(eng["track_max_fav"], px)
            if (eng["track_max_fav"] - eng["track_entry_px"]) >= 300.0:
                eng["track_status"] = "🎯 Target 300p Hit!"
        elif eng["track_signal"] == "SELL":
            eng["track_max_fav"] = min(eng["track_max_fav"], px)
            if (eng["track_entry_px"] - eng["track_max_fav"]) >= 300.0:
                eng["track_status"] = "🎯 Target 300p Hit!"

    eng["master_history"] = eng["master_history"][:10]
    eng["sweep_history"] = eng["sweep_history"][:10]
    eng["obi_history"] = eng["obi_history"][:10]

    # ============================================================================
    # RENDER DASHBOARD
    # ============================================================================
    with col_top1:
        st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ PERSISTENT MANUAL TRADER (V1.8 SPOOF-PROOF) - BTC: ${px:,.1f}</h3>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>🔴 LIVE OBI (RAW) 🟢</div>
        <div style='font-size:18px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{l2_data['ask_pct']:.1f}%</span></div>
        <div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div>
        </div>""", unsafe_allow_html=True)
        
    with c2:
        diff_col = "#22c55e" if macd_diff > 0 else "#ef4444"
        
        # Little dots to show the "spoof confirmation" progress
        ticks_str = "🟢" * eng["bull_confirm_ticks"] if eng["bull_confirm_ticks"] > 0 else ("🔴" * eng["bear_confirm_ticks"])
        if not ticks_str: ticks_str = "⚪"
        
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>📊 SPOOF-PROOF MACD</div>
        <div style='font-size:12px; color:#cbd5e1; margin-top:5px;'>Hold Ticks: {ticks_str}</div>
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
        swp_txt = "⏳ Safe (In Range)"
        swp_col = "#94a3b8"
        if eng["sweep_status"] == -2: swp_txt = "⚠️ Breaking Support!"; swp_col = "#facc15"
        elif eng["sweep_status"] == 1: swp_txt = "🟢 Bullish Sweep Trap!"; swp_col = "#22c55e"
        elif eng["sweep_status"] == 2: swp_txt = "⚠️ Breaking Resistance!"; swp_col = "#facc15"
        elif eng["sweep_status"] == -1: swp_txt = "🔴 Bearish Sweep Trap!"; swp_col = "#ef4444"
        
        st.markdown(f"""<div class='metric-box' style='text-align:left;'>
        <div style='color:#38bdf8; font-size:15px; font-weight:bold; margin-bottom:8px;'>🎯 LIQUIDITY ZONES (30m)</div>
        <div style='font-size:14px; color:#cbd5e1;'>🔴 Res (Swing High): <b style='color:#ef4444;'>${sh:,.1f}</b></div>
        <div style='font-size:14px; color:#cbd5e1; margin-top:4px;'>🟢 Sup (Swing Low): <b style='color:#22c55e;'>${sl:,.1f}</b></div>
        <div style='margin-top:10px; font-size:14px; font-weight:bold; color:{swp_col}; padding:5px; background:#0f172a; border-radius:6px; text-align:center;'>Status: {swp_txt}</div>
        </div>""", unsafe_allow_html=True)
        
    with r2_c2:
        if eng["track_signal"]:
            trk_col = "#22c55e" if eng["track_signal"] == "BUY" else "#ef4444"
            pts_moved = (eng["track_max_fav"] - eng["track_entry_px"]) if eng["track_signal"] == "BUY" else (eng["track_entry_px"] - eng["track_max_fav"])
            pts_moved = max(0.0, pts_moved)
            sts_col = "#4ade80" if eng["track_status"] != "Tracking" else "#facc15"
            
            st.markdown(f"""<div class='signal-box' style='border-color:{trk_col}; background:#0f172a;'>
            <div style='font-size:15px; color:#cbd5e1; margin-bottom:5px;'>Active Post-Signal Tracker ({eng['track_signal']} @ ${eng['track_entry_px']:,.1f})</div>
            <div style='font-size:26px; color:{trk_col}; font-weight:900;'>Max Favorable Move: +{pts_moved:,.1f} pts</div>
            <div style='font-size:14px; color:{sts_col}; margin-top:5px; padding:4px 10px; background:#1e293b; border-radius:6px;'>{eng['track_status']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='signal-box {sig_class}'>{signal_txt}</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px; margin-bottom:8px; font-weight:bold; color:#f8fafc; font-size:15px;'>📜 Individual Trackers History</div>", unsafe_allow_html=True)
    h_col1, h_col2, h_col3 = st.columns(3)
    
    with h_col1:
        st.markdown("<div style='color:#38bdf8; font-size:13px; font-weight:bold; margin-bottom:5px;'>🔥 Master Signals</div>", unsafe_allow_html=True)
        h_html = "".join([f"<div class='hist-item'>{h}</div>" for h in eng["master_history"]])
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item>No Signals Yet</div>'}</div>", unsafe_allow_html=True)

    with h_col2:
        st.markdown("<div style='color:#facc15; font-size:13px; font-weight:bold; margin-bottom:5px;'>🎯 Liquidity Sweeps</div>", unsafe_allow_html=True)
        h_html = "".join([f"<div class='hist-item'>{h}</div>" for h in eng["sweep_history"]])
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item>No Sweeps Yet</div>'}</div>", unsafe_allow_html=True)

    with h_col3:
        st.markdown("<div style='color:#c084fc; font-size:13px; font-weight:bold; margin-bottom:5px;'>📊 Spoof-Free OBI Shifts</div>", unsafe_allow_html=True)
        h_html = "".join([f"<div class='hist-item'>{h}</div>" for h in eng["obi_history"]])
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item>No Shifts Yet</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ L2 Data Load हो रहा है...")
    time.sleep(2)
    st.rerun()

import streamlit as st
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Manual Trader - L2 + Sweep Engine v1.4", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 12px; text-align: center; height: 100%; }
.signal-box { background: #0f172a; border: 2px dashed #475569; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: 900; height: 100%; display: flex; align-items: center; justify-content: center; }
.buy-sig { border-color: #22c55e; color: #22c55e; background: #064e3b; }
.sell-sig { border-color: #ef4444; color: #ef4444; background: #7f1d1d; }
.bar-container { width: 100%; background: #ef4444; height: 16px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.bar-fill { background: #22c55e; height: 100%; transition: width 0.3s ease; }
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; padding: 2px 10px !important; }
div.stButton > button:hover { background-color: #ef4444 !important; }
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
    # Light Klines Fetcher (Only grabs last 30 1-min candles to find Support/Resistance)
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (30 * 60 * 1000) 
        r = requests.post(HYPERLIQUID_URL, json={
            "type": "candleSnapshot",
            "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}
        }, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 2:
                closed_candles = data[:-1] # Ignore the currently moving candle
                highs = [float(k["h"]) for k in closed_candles]
                lows = [float(k["l"]) for k in closed_candles]
                return max(highs), min(lows)
    except: pass
    return None, None

def get_ist_time_str():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

# ============================================================================
# ROBUST STATE & MEMORY (TWO-ENGINE SYSTEM)
# ============================================================================
if "engine_state" not in st.session_state or "swing_high" not in st.session_state.engine_state:
    st.session_state.engine_state = {
        "fast_ema": 50.0,  
        "slow_ema": 50.0,  
        "last_px": 0.0,
        "spike_active": 0, 
        "max_spread": 0.0,     
        "max_spread_time": "", 
        "swing_high": 0.0,
        "swing_low": 0.0,
        "last_kline_fetch": 0.0,
        "sweep_status": 0,  # 0=None, -2=Breaking Low, 1=Bull Sweep, 2=Breaking High, -1=Bear Sweep
        "history": []
    }

eng = st.session_state.engine_state

col_top1, col_top2 = st.columns([0.85, 0.15])
with col_top2:
    if st.button("🔄 Reset Max Spread"):
        eng["max_spread"] = 0.0
        eng["max_spread_time"] = ""
        st.rerun()

# ============================================================================
# PROCESS LIVE DATA
# ============================================================================
now_ts = time.time()
l2_data = fetch_l2_orderbook()

# --- Engine 2: Update Swing High/Low every 30 seconds (Lightweight) ---
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

    # --- Engine 1: Update OBI MACD ---
    if eng["fast_ema"] == 50.0:
        eng["fast_ema"] = buy_pressure
        eng["slow_ema"] = buy_pressure
        eng["last_px"] = px
    else:
        eng["fast_ema"] = buy_pressure * 0.30 + eng["fast_ema"] * 0.70
        eng["slow_ema"] = buy_pressure * 0.05 + eng["slow_ema"] * 0.95
        
    obi_histogram = eng["fast_ema"] - eng["slow_ema"]
    
    px_diff = px - eng["last_px"]
    eng["last_px"] = px
    
    if px_diff <= -15.0: eng["spike_active"] = 1  
    elif px_diff >= 15.0: eng["spike_active"] = -1 
    else: eng["spike_active"] = 0

    # --- Engine 2: Sweep & Stop-Hunt Detection ---
    sh = eng["swing_high"]
    sl = eng["swing_low"]
    
    if sh > 0 and sl > 0:
        # Bullish Sweep Logic
        if px < sl:
            eng["sweep_status"] = -2 # Warning: Breaking Support
        elif eng["sweep_status"] == -2 and px > sl + 5.0:
            eng["sweep_status"] = 1  # Bullish Sweep Confirmed (Trap!)
            
        # Bearish Sweep Logic
        elif px > sh:
            eng["sweep_status"] = 2  # Warning: Breaking Resistance
        elif eng["sweep_status"] == 2 and px < sh - 5.0:
            eng["sweep_status"] = -1 # Bearish Sweep Confirmed (Trap!)
            
        # Auto-reset if price moves far away
        if eng["sweep_status"] == 1 and px > sl + 150.0: eng["sweep_status"] = 0
        if eng["sweep_status"] == -1 and px < sh - 150.0: eng["sweep_status"] = 0

    # --- ULTIMATE MASTER SIGNAL (Combining Both Engines) ---
    signal_txt = "⏳ कोई मास्टर सिग्नल नहीं (Waiting for Confluence)"
    sig_class = ""
    
    # MASTER BUY: Bullish Sweep Confirmed AND OBI MACD is heavily positive
    if eng["sweep_status"] == 1 and obi_histogram > 1.5:
        signal_txt = f"🔥 HIGH PROB BUY!<br><span style='font-size:16px;'>Liquidity Swept + Whale OBI Trap @ ${px:,.1f}</span>"
        sig_class = "buy-sig"
        eng["history"].insert(0, f"{now_ist_str} - 🔥 MASTER BUY (Sweep + OBI) @ ${px:,.1f}")
        eng["sweep_status"] = 0 # Reset after firing
        
    # MASTER SELL: Bearish Sweep Confirmed AND OBI MACD is heavily negative
    elif eng["sweep_status"] == -1 and obi_histogram < -1.5:
        signal_txt = f"🔥 HIGH PROB SELL!<br><span style='font-size:16px;'>Liquidity Swept + Whale OBI Trap @ ${px:,.1f}</span>"
        sig_class = "sell-sig"
        eng["history"].insert(0, f"{now_ist_str} - 🔥 MASTER SELL (Sweep + OBI) @ ${px:,.1f}")
        eng["sweep_status"] = 0

    eng["history"] = eng["history"][:5]

    # ============================================================================
    # RENDER DASHBOARD
    # ============================================================================
    with col_top1:
        st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ PRO MANUAL TRADER (L2 + SWEEP ENGINE) - BTC: ${px:,.1f}</h3>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>🔴 LIVE OBI (RAW) 🟢</div>
        <div style='font-size:18px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{l2_data['ask_pct']:.1f}%</span></div>
        <div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div>
        </div>""", unsafe_allow_html=True)
        
    with c2:
        hist_col = "#22c55e" if obi_histogram > 0 else "#ef4444"
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:13px; font-weight:bold;'>📊 OBI MACD (MOMENTUM)</div>
        <div style='font-size:12px; color:#cbd5e1; margin-top:5px;'>Fast {eng['fast_ema']:.1f} | Slow {eng['slow_ema']:.1f}</div>
        <div style='font-size:20px; font-weight:900; color:{hist_col}; margin-top:5px;'>Hist: {obi_histogram:+.2f}%</div>
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

    # 🎯 ROW 2: LIQUIDITY ZONES & ULTIMATE SIGNAL
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
        st.markdown(f"<div class='signal-box {sig_class}'>{signal_txt}</div>", unsafe_allow_html=True)
    
    # Recent Signals History
    if eng["history"]:
        st.markdown("<h4 style='color:#cbd5e1; margin-top:20px;'>📜 Master Signals History</h4>", unsafe_allow_html=True)
        for h in eng["history"]:
            st.markdown(f"<div style='background:#1e293b; padding:8px 15px; border-radius:6px; margin-bottom:5px; color:#facc15; font-weight:bold; font-size:13px;'>{h}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ L2 Data Load हो रहा है...")
    time.sleep(2)
    st.rerun()

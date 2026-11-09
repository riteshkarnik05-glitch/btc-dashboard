import streamlit as st
import requests
import time
import math
from datetime import datetime

st.set_page_config(page_title="Pro Manual Trader - L2 OBI Engine", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 12px; text-align: center; }
.signal-box { background: #0f172a; border: 2px dashed #475569; padding: 20px; border-radius: 12px; text-align: center; font-size: 24px; font-weight: 900; margin-top: 15px; }
.buy-sig { border-color: #22c55e; color: #22c55e; background: #064e3b; }
.sell-sig { border-color: #ef4444; color: #ef4444; background: #7f1d1d; }
.bar-container { width: 100%; background: #ef4444; height: 16px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.bar-fill { background: #22c55e; height: 100%; transition: width 0.3s ease; }
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
                bids = data["levels"][0][:15] # Top 15 Bids
                asks = data["levels"][1][:15] # Top 15 Asks
                
                bid_vol = sum(float(b["sz"]) for b in bids)
                ask_vol = sum(float(a["sz"]) for a in asks)
                tot_vol = bid_vol + ask_vol
                
                mid_px = (float(bids[0]["px"]) + float(asks[0]["px"])) / 2.0
                bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                return {"mid_px": mid_px, "bid_pct": bid_pct, "ask_pct": 100.0 - bid_pct, "bid_vol": bid_vol, "ask_vol": ask_vol}
    except: pass
    return None

# ============================================================================
# STATE & MEMORY (THE EMA ENGINE)
# ============================================================================
if "engine_state" not in st.session_state:
    st.session_state.engine_state = {
        "fast_ema": 50.0,  # ~10 sec memory
        "slow_ema": 50.0,  # ~60 sec memory
        "last_px": 0.0,
        "spike_active": 0, # 1 for Bull Spike, -1 for Bear Spike
        "history": []
    }

eng = st.session_state.engine_state

# ============================================================================
# PROCESS LIVE DATA
# ============================================================================
l2_data = fetch_l2_orderbook()

if l2_data:
    px = l2_data["mid_px"]
    buy_pressure = l2_data["bid_pct"]
    
    # 1. Update OBI MACD (Fast vs Slow Memory)
    if eng["fast_ema"] == 50.0:
        eng["fast_ema"] = buy_pressure
        eng["slow_ema"] = buy_pressure
        eng["last_px"] = px
    else:
        # Fast EMA (alpha ~ 0.3 for fast reaction)
        eng["fast_ema"] = buy_pressure * 0.30 + eng["fast_ema"] * 0.70
        # Slow EMA (alpha ~ 0.05 for slow base trend)
        eng["slow_ema"] = buy_pressure * 0.05 + eng["slow_ema"] * 0.95
        
    obi_histogram = eng["fast_ema"] - eng["slow_ema"]
    
    # 2. Spike Detector (Sudden Price Jump/Drop in 2 seconds)
    px_diff = px - eng["last_px"]
    eng["last_px"] = px
    
    # If price jumps more than 15 points in 2 seconds -> It's a spike!
    if px_diff <= -15.0:
        eng["spike_active"] = 1  # Bullish Mean-Reversion setup (Stop-hunt down)
    elif px_diff >= 15.0:
        eng["spike_active"] = -1 # Bearish Mean-Reversion setup (Stop-hunt up)
    else:
        # Decay spike memory slowly
        eng["spike_active"] = 0

    # 3. Generate Manual Signal
    signal_txt = "⏳ कोई सिग्नल नहीं (No Trade Zone)"
    sig_class = ""
    
    # 🟢 BUY SIGNAL: Spike Down (Trap) AND Fast OBI crosses above Slow OBI (Whale Buying)
    if eng["spike_active"] == 1 and obi_histogram > 1.5:
        signal_txt = f"🟢 BUY SIGNAL! (Whale Bid Wall Trap @ ${px:,.1f})"
        sig_class = "buy-sig"
        eng["history"].insert(0, f"{datetime.now().strftime('%H:%M:%S')} - BUY (Spike + OBI Div) @ ${px:,.1f}")
        
    # 🔴 SELL SIGNAL: Spike Up (Trap) AND Fast OBI crosses below Slow OBI (Whale Selling)
    elif eng["spike_active"] == -1 and obi_histogram < -1.5:
        signal_txt = f"🔴 SELL SIGNAL! (Whale Ask Wall Trap @ ${px:,.1f})"
        sig_class = "sell-sig"
        eng["history"].insert(0, f"{datetime.now().strftime('%H:%M:%S')} - SELL (Spike + OBI Div) @ ${px:,.1f}")

    eng["history"] = eng["history"][:5] # Keep only last 5 signals

    # ============================================================================
    # RENDER DASHBOARD
    # ============================================================================
    st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; text-align:center;'>⚡ PRO MANUAL TRADER (L2 OBI ENGINE) - BTC/USD: ${px:,.1f}</h3>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:14px; font-weight:bold;'>🔴 LIVE OBI (RAW) 🟢</div>
        <div style='font-size:20px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{l2_data['ask_pct']:.1f}%</span></div>
        <div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div>
        </div>""", unsafe_allow_html=True)
        
    with c2:
        hist_col = "#22c55e" if obi_histogram > 0 else "#ef4444"
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:14px; font-weight:bold;'>📊 OBI MACD (MOMENTUM)</div>
        <div style='font-size:13px; color:#cbd5e1; margin-top:5px;'>Fast EMA: {eng['fast_ema']:.1f}% | Slow EMA: {eng['slow_ema']:.1f}%</div>
        <div style='font-size:22px; font-weight:900; color:{hist_col}; margin-top:5px;'>Histogram: {obi_histogram:+.2f}%</div>
        </div>""", unsafe_allow_html=True)
        
    with c3:
        spk_col = "#22c55e" if eng["spike_active"] == 1 else ("#ef4444" if eng["spike_active"] == -1 else "#94a3b8")
        spk_txt = "📉 Down Spike Detected!" if eng["spike_active"] == 1 else ("📈 Up Spike Detected!" if eng["spike_active"] == -1 else "No Recent Spike")
        st.markdown(f"""<div class='metric-box'>
        <div style='color:#94a3b8; font-size:14px; font-weight:bold;'>⚡ SPIKE DETECTOR</div>
        <div style='font-size:13px; color:#cbd5e1; margin-top:5px;'>Price Diff (2s): <b style='color:#facc15;'>${px_diff:+.1f}</b></div>
        <div style='font-size:18px; font-weight:900; color:{spk_col}; margin-top:5px;'>{spk_txt}</div>
        </div>""", unsafe_allow_html=True)

    # Big Signal Alert Box
    st.markdown(f"<div class='signal-box {sig_class}'>{signal_txt}</div>", unsafe_allow_html=True)
    
    # Recent Signals History
    if eng["history"]:
        st.markdown("<h4 style='color:#cbd5e1; margin-top:20px;'>📜 Recent Manual Signals</h4>", unsafe_allow_html=True)
        for h in eng["history"]:
            st.markdown(f"<div style='background:#1e293b; padding:8px 15px; border-radius:6px; margin-bottom:5px; color:#facc15; font-weight:bold; font-size:13px;'>{h}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ L2 Data Load हो रहा है...")
    time.sleep(2)
    st.rerun()

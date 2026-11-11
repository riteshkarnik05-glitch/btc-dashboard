import streamlit as st
import requests
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant - V4.0 BBNT Engine", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 12px; text-align: center; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5); }
.card-title { font-size: 13px; font-weight: bold; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase; }
.card-value { font-size: 20px; font-weight: 900; }
.badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
.badge-green { background-color: #064e3b; color: #4ade80; border: 1px solid #22c55e; }
.badge-red { background-color: #7f1d1d; color: #f87171; border: 1px solid #ef4444; }
.badge-yellow { background-color: #422006; color: #facc15; border: 1px solid #eab308; }
.badge-cyan { background-color: #083344; color: #22d3ee; border: 1px solid #06b6d4; }
.badge-gray { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; }
.bar-container { width: 100%; background: #ef4444; height: 10px; border-radius: 5px; overflow: hidden; margin-top: 10px; display: flex;}
.bar-buy { background: #22c55e; height: 100%; transition: width 0.3s ease; }
.bar-sell { background: #ef4444; height: 100%; transition: width 0.3s ease; }
.table-container { background: #0f172a; border-radius: 12px; padding: 15px; border: 1px solid #334155; height: 400px; overflow-y: auto; margin-top: 20px;}
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; }
th { color: #94a3b8; border-bottom: 1px solid #334155; padding: 10px; background: #1e293b; position: sticky; top: 0; }
td { padding: 10px; border-bottom: 1px solid #1e293b; color: #f8fafc; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# API FETCHERS (TICKER, ORDERBOOK, KLINE/BOX)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
def get_ist_time_str(): return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

def fetch_l2_orderbook():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and "levels" in data and len(data["levels"]) >= 2:
                bids = data["levels"][0][:20]; asks = data["levels"][1][:20]
                if len(bids) > 0 and len(asks) > 0:
                    buy_size = sum(float(b["sz"]) for b in bids); sell_size = sum(float(a["sz"]) for a in asks)
                    tot_sz = buy_size + sell_size; best_bid = float(bids[0]["px"]); best_ask = float(asks[0]["px"])
                    return {"mark_price": (best_bid + best_ask)/2.0, "buy_sz": buy_size, "sell_sz": sell_size, "ob_ratio": (buy_size/tot_sz)*100 if tot_sz > 0 else 50}
    except: pass
    return None

def fetch_15m_box():
    try:
        end_time = int(time.time() * 1000); start_time = end_time - (30 * 60 * 1000) # Fetch 30 mins
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 15:
                df = pd.DataFrame(data[:-1]) # Exclude current forming minute
                df.rename(columns={'h':'High', 'l':'Low', 'c':'Close'}, inplace=True)
                for col in ['High', 'Low', 'Close']: df[col] = df[col].astype(float)
                
                # Rule 1: Rolling Box (t-15 to t-1)
                last_15 = df.tail(15)
                box_high = last_15['High'].max()
                box_low = last_15['Low'].min()
                box_width = box_high - box_low
                
                # Choppiness Filter
                if box_width < 40.0:
                    box_high += 15.0; box_low -= 15.0
                    box_width = box_high - box_low
                    
                return {"high": box_high, "low": box_low, "width": box_width}
    except: pass
    return None

# Placeholder for Options Data (Simulated based on Orderbook momentum for demo, replace with actual DB query)
def simulate_options_dual_track(buy_pressure, px_diff):
    # Simulate PE OI buildup if price is dropping or buying pressure is high
    base_pe = 500 + (buy_pressure - 50) * 10 - px_diff * 20
    base_ce = 500 - (buy_pressure - 50) * 10 + px_diff * 20
    return max(0, base_pe), max(0, base_ce)

# ============================================================================
# 24x7 BBNT MASTER ENGINE THREAD
# ============================================================================
def background_sniper_worker(eng, worker_id):
    while True:
        if eng.get("worker_id") != worker_id: break
        try:
            now_ts = time.time(); ist_str = get_ist_time_str()
            ob_data = fetch_l2_orderbook()
            
            if ob_data:
                px = ob_data["mark_price"]
                eng["px"] = px; eng["buy_sz"] = ob_data["buy_sz"]; eng["sell_sz"] = ob_data["sell_sz"]
                eng["ob_ratio"] = ob_data["ob_ratio"]
                eng["last_px"] = eng.get("last_px", px)
                px_diff = px - eng["last_px"]; eng["last_px"] = px
                
                # Update 15m Box every minute
                if now_ts - eng["last_box_fetch"] > 60:
                    box_data = fetch_15m_box()
                    if box_data:
                        eng["box_high"] = box_data["high"]; eng["box_low"] = box_data["low"]; eng["box_width"] = box_data["width"]
                    eng["last_box_fetch"] = now_ts
                    
                    # Minute Close Logic: Dual-Track Scoring & Core Engine
                    pe_chg, ce_chg = simulate_options_dual_track(ob_data["ob_ratio"], px_diff)
                    eng["pe_track"].append(pe_chg); eng["ce_track"].append(ce_chg)
                    if len(eng["pe_track"]) > 5: eng["pe_track"].pop(0); eng["ce_track"].pop(0)
                    
                    buy_track = sum(eng["pe_track"]) / len(eng["pe_track"]) if eng["pe_track"] else 0
                    sell_track = sum(eng["ce_track"]) / len(eng["ce_track"]) if eng["ce_track"] else 0
                    eng["buy_track_val"] = buy_track; eng["sell_track_val"] = sell_track
                    
                    # Rule 4 & 5: BBNT Core Signal & State Locking
                    bh = eng["box_high"]; bl = eng["box_low"]
                    sig_text = "Neutral (Inside Box)"; sig_col = "badge-gray"; locked_move = 0.0
                    
                    # Exit / Reset Conditions for Locked State
                    if eng["lock_state"] == "LONG":
                        locked_move = px - eng["lock_trigger_px"]
                        if px < eng["lock_box_high"] or sell_track > buy_track:
                            eng["lock_state"] = "NONE" # Trend Broken
                        else:
                            sig_text = f"Riding LONG (+{locked_move:,.1f} Pts)"; sig_col = "badge-green"
                            
                    elif eng["lock_state"] == "SHORT":
                        locked_move = eng["lock_trigger_px"] - px
                        if px > eng["lock_box_low"] or buy_track > sell_track:
                            eng["lock_state"] = "NONE" # Trend Broken
                        else:
                            sig_text = f"Riding SHORT (+{locked_move:,.1f} Pts)"; sig_col = "badge-red"
                    
                    # New Entry Conditions (If not locked)
                    if eng["lock_state"] == "NONE" and bh > 0:
                        is_buy_dominant = buy_track > sell_track * 1.15
                        is_sell_dominant = sell_track > buy_track * 1.15
                        conviction = "★ High Conviction " if (ob_data["ob_ratio"] > 60 and is_buy_dominant) or (ob_data["ob_ratio"] < 40 and is_sell_dominant) else ""
                        
                        if px > bh:
                            if is_buy_dominant:
                                sig_text = f"{conviction}True Breakout (LONG)"; sig_col = "badge-green"
                                eng["lock_state"] = "LONG"; eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh; eng["lock_box_low"] = bl
                            elif sell_track >= buy_track:
                                sig_text = "Fake Breakout / Bull Trap"; sig_col = "badge-yellow"
                                
                        elif px < bl:
                            if is_sell_dominant:
                                sig_text = f"{conviction}True Breakdown (SHORT)"; sig_col = "badge-red"
                                eng["lock_state"] = "SHORT"; eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh; eng["lock_box_low"] = bl
                            elif buy_track >= sell_track:
                                sig_text = "Fake Breakdown / Spring (LONG)"; sig_col = "badge-cyan"
                    
                    # Update Live Signal Table
                    new_row = {
                        "time": ist_str, "px": px, "bh": bh, "bl": bl, 
                        "bt": buy_track, "st": sell_track, "pts": locked_move,
                        "sig": sig_text, "cls": sig_col
                    }
                    if not eng["live_table"] or eng["live_table"][0]["time"][:5] != ist_str[:5]:
                        eng["live_table"].insert(0, new_row)
                        eng["live_table"] = eng["live_table"][:50]
                    else:
                        eng["live_table"][0] = new_row # Update current minute
                        
        except Exception as e: eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_persistent_bbnt():
    worker_id = int(time.time() * 1000)
    eng = {
        "worker_id": worker_id, "px": 0.0, "buy_sz": 0, "sell_sz": 0, "ob_ratio": 50.0,
        "box_high": 0.0, "box_low": 0.0, "box_width": 0.0, "last_box_fetch": 0.0,
        "pe_track": [], "ce_track": [], "buy_track_val": 0.0, "sell_track_val": 0.0,
        "lock_state": "NONE", "lock_trigger_px": 0.0, "lock_box_high": 0.0, "lock_box_low": 0.0,
        "live_table": [], "last_err": None
    }
    threading.Thread(target=background_sniper_worker, args=(eng, worker_id), daemon=True).start()
    return eng

eng = get_persistent_bbnt()

# ============================================================================
# RENDER DASHBOARD UI (V4.0)
# ============================================================================
if eng["px"] > 0:
    st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ BBNT DUAL-TRACK SIGNAL ENGINE (V4.0) - BTC: ${eng['px']:,.1f}</h3>", unsafe_allow_html=True)
    
    # --- 1. TOP SUMMARY CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        state_txt = "Neutral (Waiting)"
        state_col = "#cbd5e1"; bg = "#1e293b"
        if eng["lock_state"] == "LONG": state_txt = f"RIDING LONG (+{eng['px'] - eng['lock_trigger_px']:,.1f} Pts)"; state_col = "#4ade80"; bg = "#064e3b30"
        elif eng["lock_state"] == "SHORT": state_txt = f"RIDING SHORT (+{eng['lock_trigger_px'] - eng['px']:,.1f} Pts)"; state_col = "#f87171"; bg = "#7f1d1d30"
        
        st.markdown(f"<div class='metric-box' style='background:{bg}; border-color:{state_col};'><div class='card-title'>🎯 Current Market State</div><div style='font-size:18px; font-weight:900; color:{state_col}; margin-top:10px;'>{state_txt}</div></div>", unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"<div class='metric-box'><div class='card-title'>📦 15-Min Volatility Box</div><div style='font-size:14px; color:#cbd5e1; margin-top:5px;'>High: <span style='color:#ef4444; font-weight:bold;'>${eng['box_high']:,.1f}</span></div><div style='font-size:14px; color:#cbd5e1; margin-top:3px;'>Low: <span style='color:#22c55e; font-weight:bold;'>${eng['box_low']:,.1f}</span></div><div style='font-size:12px; color:#facc15; margin-top:5px;'>Width: {eng['box_width']:,.1f} Pts</div></div>", unsafe_allow_html=True)
        
    with c3:
        b_val = eng["buy_track_val"]; s_val = eng["sell_track_val"]
        tot = b_val + s_val if (b_val + s_val) > 0 else 1
        b_pct = (b_val / tot) * 100; s_pct = 100 - b_pct
        st.markdown(f"<div class='metric-box'><div class='card-title'>⚖️ Dual-Track OI Score (5m)</div><div style='display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-top:5px;'><span style='color:#22c55e;'>Buy (PE): {b_val:,.0f}</span><span style='color:#ef4444;'>Sell (CE): {s_val:,.0f}</span></div><div class='bar-container'><div class='bar-buy' style='width:{b_pct}%;'></div><div class='bar-sell' style='width:{s_pct}%;'></div></div></div>", unsafe_allow_html=True)
        
    with c4:
        ob_ratio = eng["ob_ratio"]
        st.markdown(f"<div class='metric-box'><div class='card-title'>📚 Orderbook Pressure (L2)</div><div style='display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-top:5px;'><span style='color:#22c55e;'>Bids: {ob_ratio:.1f} %</span><span style='color:#ef4444;'>Asks: {100-ob_ratio:.1f} %</span></div><div class='bar-container'><div class='bar-buy' style='width:{ob_ratio}%;'></div><div class='bar-sell' style='width:{100-ob_ratio}%;'></div></div></div>", unsafe_allow_html=True)

    # --- 2. LIVE SIGNAL TABLE ---
    st.markdown("<div class='table-container'><table><thead><tr><th>Time</th><th>Future Px</th><th>Box High</th><th>Box Low</th><th>Buy Track (PE)</th><th>Sell Track (CE)</th><th>Move (Pts)</th><th>Final Signal</th></tr></thead><tbody>", unsafe_allow_html=True)
    
    rows_html = ""
    for row in eng["live_table"]:
        pts_str = f"{row['pts']:+.1f}" if row['pts'] != 0 else "-"
        rows_html += f"<tr><td>{row['time']}</td><td>${row['px']:,.1f}</td><td>{row['bh']:,.1f}</td><td>{row['bl']:,.1f}</td><td style='color:#22c55e;'>{row['bt']:,.0f}</td><td style='color:#ef4444;'>{row['st']:,.0f}</td><td>{pts_str}</td><td><span class='badge {row['cls']}'>{row['sig']}</span></td></tr>"
        
    if not rows_html: rows_html = "<tr><td colspan='8' style='text-align:center;'>Waiting for 1-Minute Candle Close...</td></tr>"
    st.markdown(rows_html + "</tbody></table></div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V4.0 (BBNT Master Engine) स्टार्ट हो रहा है... 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"): st.error(f"🔴 System Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

import streamlit as st
import requests
import time
import threading
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant - V3.6 Auto-Repair", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 14px; border-radius: 12px; text-align: center; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5); }
.zone-box { background: #0f172a; border: 1px solid #334155; padding: 15px; border-radius: 12px; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5); }
.signal-box { background: #0f172a; border: 2px dashed #475569; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: 900; height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column;}
.vshape-box { background: #020617; border: 1px solid #38bdf8; border-left: 5px solid #38bdf8; padding: 15px; border-radius: 8px; margin-top: 15px;}
.bar-container { width: 100%; background: #ef4444; height: 14px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.bar-fill { background: #22c55e; height: 100%; transition: width 0.3s ease; }
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; padding: 2px 10px !important; }
div.stButton > button:hover { background-color: #ef4444 !important; }
.history-box { background:#1e293b; padding:12px; border-radius:12px; border:1px solid #334155; height: 320px; overflow-y: auto;}
.hist-item { font-size: 13.5px; padding: 10px 12px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom:6px; border-radius:6px; background: #0f172a; line-height: 1.5;}
.hist-tracking { border-left: 4px solid #38bdf8; }
.hist-closed-win { border-left: 4px solid #22c55e; background: #064e3b20; }
.hist-closed-loss { border-left: 4px solid #ef4444; background: #7f1d1d20; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# LIGHTWEIGHT API FETCHERS
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
def get_ist_time_str(): return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

def fetch_l2_orderbook():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and "levels" in data and len(data["levels"]) >= 2:
                bids = data["levels"][0][:15]; asks = data["levels"][1][:15]
                if len(bids) > 0 and len(asks) > 0:
                    bid_vol = sum(float(b["sz"]) for b in bids); ask_vol = sum(float(a["sz"]) for a in asks)
                    tot_vol = bid_vol + ask_vol; best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
                    mid_px = (best_bid + best_ask) / 2.0; spread = best_ask - best_bid
                    bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                    
                    l1_bid_sz = float(bids[0]["sz"]); l1_ask_sz = float(asks[0]["sz"])
                    l1_bid_pct = (l1_bid_sz / (l1_bid_sz + l1_ask_sz) * 100.0) if (l1_bid_sz + l1_ask_sz) > 0 else 50.0
                    
                    return {
                        "mid_px": mid_px, "spread": spread, "bid_pct": bid_pct, 
                        "ask_pct": 100.0 - bid_pct, "net_vol": bid_vol - ask_vol,
                        "l1_bid_pct": l1_bid_pct
                    }
    except Exception as e: return str(e)
    return None

def fetch_advanced_klines():
    try:
        end_time = int(time.time() * 1000); start_time = end_time - (100 * 60 * 1000)
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 20:
                closed_candles = data[:-1]
                df = pd.DataFrame(closed_candles)
                df.rename(columns={'o':'Open', 'h':'High', 'l':'Low', 'c':'Close', 'v':'Volume', 't':'Time'}, inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']: df[col] = df[col].astype(float)
                
                sma_100 = df['Close'].mean()
                latest_close = df['Close'].iloc[-1]
                htf_trend = "BULLISH" if latest_close > sma_100 else "BEARISH"

                last_10 = df.tail(10)
                highest_10m = last_10['High'].max()
                lowest_10m = last_10['Low'].min()

                return True, 0.0, htf_trend, sma_100, highest_10m, lowest_10m
    except Exception as e: return str(e), 0.0, "NONE", 0.0, 0.0, 0.0
    return False, 0.0, "NONE", 0.0, 0.0, 0.0

# ============================================================================
# 24x7 BACKGROUND WORKER (V3.6 AUTO-REPAIR)
# ============================================================================
def background_sniper_worker(eng, worker_id):
    while True:
        if eng.get("worker_id") != worker_id: break
        try:
            now_ts = time.time(); l2_data = fetch_l2_orderbook()
            now_ist_str = get_ist_time_str()

            if isinstance(l2_data, str): eng["last_err"] = f"L2 API Error: {l2_data}"
            elif l2_data is None: pass 
            else:
                if now_ts - eng["last_kline_fetch"] > 15:
                    is_ok, cvd_5m, htf_trend, sma_100, h10, l10 = fetch_advanced_klines()
                    if isinstance(is_ok, str): eng["last_err"] = f"Kline API Error: {is_ok}"
                    elif is_ok:
                        eng["htf_trend"] = htf_trend; eng["htf_sma"] = sma_100
                        eng["swing_high"] = h10; eng["swing_low"] = l10
                    eng["last_kline_fetch"] = now_ts

                px = l2_data["mid_px"]; buy_pressure = l2_data["bid_pct"]; current_spread = l2_data["spread"]
                net_vol = l2_data["net_vol"]; l1_bid_pct = l2_data["l1_bid_pct"]
                eng["px"] = px; eng["buy_pressure"] = buy_pressure; eng["ask_pct"] = l2_data["ask_pct"]
                eng["current_spread"] = current_spread; eng["last_update_ist"] = now_ist_str
                if current_spread > eng["max_spread"]: eng["max_spread"] = current_spread; eng["max_spread_time"] = now_ist_str

                if not eng["ema_initialized"]:
                    eng["fast_ema"] = eng["slow_ema"] = buy_pressure; eng["signal_line"] = 0.0; eng["last_px"] = px
                    eng["ema_initialized"] = True; obi_histogram = macd_diff = 0.0
                else:
                    eng["fast_ema"] = buy_pressure * 0.18 + eng["fast_ema"] * 0.82; eng["slow_ema"] = buy_pressure * 0.06 + eng["slow_ema"] * 0.94
                    obi_histogram = eng["fast_ema"] - eng["slow_ema"]; eng["signal_line"] = obi_histogram * 0.20 + eng["signal_line"] * 0.80
                    macd_diff = obi_histogram - eng["signal_line"]
                
                px_diff = px - eng["last_px"]; eng["px_diff"] = px_diff; eng["last_px"] = px
                eng["buy_pct_history"].append(buy_pressure)
                if len(eng["buy_pct_history"]) > 60: eng["buy_pct_history"].pop(0)

                # ====================================================================
                # V-SHAPE REVERSAL ENGINE
                # ====================================================================
                if eng["swing_high"] > 0:
                    drop_10m = eng["swing_high"] - px
                    rally_10m = px - eng["swing_low"]
                    
                    v_dir = "कोई साफ सेटअप नहीं"; v_prob = "बहुत कम"; v_score = 0; v_reasons = []
                    v_danger = "अभी मार्केट एकतरफा मूव में है, कोई रिजेक्शन नहीं आया है।"
                    action_idea = "प्राइस रिजेक्शन और एग्जॉशन की पुष्टि का इंतजार करें — अभी कोई ट्रेड नहीं"

                    if drop_10m >= 150.0:
                        v_dir = "बुलिश V-शेप"
                        if buy_pressure <= 27.0: v_score += 2; v_reasons.append(f"चरम सेलिंग प्रेशर (L2 Buy: {buy_pressure:.0f}%)")
                        elif buy_pressure <= 30.0: v_score += 1
                        if eng.get("iceberg_score", 0) >= 50: v_score += 2; v_reasons.append("शॉर्ट्स ट्रैप (व्हेल बाइंग अब्जॉर्प्शन)")
                        
                        l2_min = min(eng["buy_pct_history"]) if eng["buy_pct_history"] else buy_pressure
                        if buy_pressure > l2_min and l1_bid_pct >= 50.0: v_score += 2; v_reasons.append(f"सेलिंग एग्जॉशन (L1 Bid: {l1_bid_pct:.0f}% पर रिकवरी)")
                        
                        recovery = px - eng.get("lowest_sweep_px", eng["swing_low"])
                        if recovery >= 35.0: v_score += 2; v_reasons.append(f"लो से प्राइस रिजेक्शन (+${recovery:.1f} बाउंस)")
                        else: v_danger = f"प्राइस अभी भी लो के पास है (बाउंस सिर्फ +${recovery:.1f} है)। गिरती छुरी पकड़ना खतरनाक है!"
                        
                        if eng["htf_trend"] == "BULLISH": v_score += 2; v_reasons.append("बड़ा ट्रेंड Bullish है (सपोर्ट)")

                    elif rally_10m >= 150.0:
                        v_dir = "बियरिश Inverted V-शेप"
                        if buy_pressure >= 70.0: v_score += 2; v_reasons.append(f"चरम बाइंग प्रेशर (L2 Buy: {buy_pressure:.0f}%)")
                        elif buy_pressure >= 67.0: v_score += 1
                        if eng.get("iceberg_score", 0) <= -50: v_score += 2; v_reasons.append("लॉन्ग्स ट्रैप (व्हेल सेलिंग अब्जॉर्प्शन)")
                        
                        l2_max = max(eng["buy_pct_history"]) if eng["buy_pct_history"] else buy_pressure
                        if buy_pressure < l2_max and l1_bid_pct <= 50.0: v_score += 2; v_reasons.append(f"बाइंग एग्जॉशन (L1 Ask हावी: {100-l1_bid_pct:.0f}%)")
                        
                        fall = eng.get("highest_sweep_px", eng["swing_high"]) - px
                        if fall >= 35.0: v_score += 2; v_reasons.append(f"हाई से प्राइस रिजेक्शन (-${fall:.1f} गिरावट)")
                        else: v_danger = f"प्राइस अभी भी हाई के पास है (गिरावट सिर्फ -${fall:.1f} है)। ट्रेंड ऊपर जा सकता है!"
                        
                        if eng["htf_trend"] == "BEARISH": v_score += 2; v_reasons.append("बड़ा ट्रेंड Bearish है (रेजिस्टेंस)")

                    if v_dir != "कोई साफ सेटअप नहीं":
                        has_ex = any("एग्जॉशन" in r for r in v_reasons); has_rej = any("रिजेक्शन" in r for r in v_reasons)
                        if not (has_ex and has_rej): v_score = min(v_score, 4)
                        
                        if v_score <= 2: v_prob = "बहुत कम"
                        elif v_score <= 4: v_prob = "कम (प्रेशर है, पर एग्जॉशन/रिजेक्शन नहीं)"
                        elif v_score <= 6: v_prob = "मध्यम (पूरी पुष्टि का इंतजार करें)"
                        elif v_score <= 8: v_prob = "अच्छी"
                        else: v_prob = "बहुत अच्छी (हाई कन्विक्शन)"

                        if v_score >= 7:
                            v_danger = "कोई बड़ा खतरा नहीं। रिस्क मैनेज करके एंट्री की जा सकती है।"
                            if v_dir == "बुलिश V-शेप": action_idea = f"एंट्री दिशा: LONG (Buy) @ ${px:,.1f}\nस्टॉप लॉस: स्विंग लो के नीचे @ ${eng['swing_low'] - 40:,.1f}\nटारगेट: +250 पॉइंट्स, दूसरा +400 पॉइंट्स"
                            else: action_idea = f"एंट्री दिशा: SHORT (Sell) @ ${px:,.1f}\nस्टॉप लॉस: स्विंग हाई के ऊपर @ ${eng['swing_high'] + 40:,.1f}\nटारगेट: +250 पॉइंट्स, दूसरा +400 पॉइंट्स"

                    eng["v_engine"] = {"dir": v_dir, "prob": v_prob, "score": v_score, "reasons": v_reasons, "danger": v_danger, "action": action_idea}

                eng["iceberg_score"] = eng.get("iceberg_score", 0.0) * 0.985
                imbalance_delta = buy_pressure - 50.0
                if abs(imbalance_delta) >= 12.0 and abs(px_diff) <= 5.0: eng["iceberg_score"] += (imbalance_delta * 0.18)
                eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))

                sh, sl = eng["swing_high"], eng["swing_low"]
                if sh > 0 and sl > 0:
                    if px <= sl + 10.0: eng["sweep_status"] = -2; eng["lowest_sweep_px"] = min(eng.get("lowest_sweep_px", px), px)
                    elif eng["sweep_status"] == -2 and px >= eng.get("lowest_sweep_px", sl) + 12.0: eng["sweep_status"] = 1; eng["sweep_latch_time"] = now_ts
                    if px >= sh - 10.0: eng["sweep_status"] = 2; eng["highest_sweep_px"] = max(eng.get("highest_sweep_px", px), px)
                    elif eng["sweep_status"] == 2 and px <= eng.get("highest_sweep_px", sh) - 12.0: eng["sweep_status"] = -1; eng["sweep_latch_time"] = now_ts
                    if eng["sweep_status"] in [1, -1] and (now_ts - eng["sweep_latch_time"] > 300): eng["sweep_status"] = 0

                # MASTER SIGNAL CONFLUENCE (Connected to V-Engine)
                new_master_sig = None; master_sig_reason = ""
                if not eng["track_signal"]:
                    if eng["v_engine"]["score"] >= 8 and eng["v_engine"]["dir"] == "बुलिश V-शेप":
                        new_master_sig = "BUY"; master_sig_reason = "🚀 बुलिश V-शेप (हाई कन्विक्शन)"
                    elif eng["v_engine"]["score"] >= 8 and eng["v_engine"]["dir"] == "बियरिश Inverted V-शेप":
                        new_master_sig = "SELL"; master_sig_reason = "🚀 बियरिश Inverted V (हाई कन्विक्शन)"

                if new_master_sig:
                    eng["track_signal"] = new_master_sig; eng["track_entry_px"] = px; eng["track_max_fav"] = px; eng["track_status"] = "Tracking"
                    eng["active_trade_obj"] = {"open_time": now_ist_str, "close_time": "", "type": new_master_sig, "entry": px, "status": "Tracking", "max_pnl": 0.0, "live_pnl": 0.0, "final_pnl": 0.0, "reason": master_sig_reason}

                # POST-SIGNAL TRAILING TRACKER
                if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                    t_type = eng["track_signal"]; t_entry = eng["track_entry_px"]
                    if t_type == "BUY":
                        live_pnl = px - t_entry; eng["track_max_fav"] = max(eng["track_max_fav"], px); max_pnl = eng["track_max_fav"] - t_entry
                        if max_pnl >= 600.0: trail_sl_px = eng["track_max_fav"] - 150.0 
                        elif max_pnl >= 400.0: trail_sl_px = t_entry + 250.0 
                        elif max_pnl >= 200.0: trail_sl_px = t_entry + 100.0  
                        else: trail_sl_px = t_entry - 300.0 

                        if px <= trail_sl_px:
                            eng["track_status"] = "Closed"; final_pnl = live_pnl
                            sts_text = f"🛑 SL हिट ({final_pnl:+.0f}p)" if final_pnl < 0 else (f"🛡️ सेफ एक्जिट (+{final_pnl:,.0f}p)" if final_pnl < 150 else f"✅ बड़ा प्रॉफिट (+{final_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]")
                            eng["active_trade_obj"]["status"] = sts_text; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None; eng["track_signal"] = None
                    elif t_type == "SELL":
                        live_pnl = t_entry - px; eng["track_max_fav"] = min(eng["track_max_fav"], px); max_pnl = t_entry - eng["track_max_fav"]
                        if max_pnl >= 600.0: trail_sl_px = eng["track_max_fav"] + 150.0 
                        elif max_pnl >= 400.0: trail_sl_px = t_entry - 250.0 
                        elif max_pnl >= 200.0: trail_sl_px = t_entry - 100.0 
                        else: trail_sl_px = t_entry + 300.0 

                        if px >= trail_sl_px:
                            eng["track_status"] = "Closed"; final_pnl = live_pnl
                            sts_text = f"🛑 SL हिट ({final_pnl:+.0f}p)" if final_pnl < 0 else (f"🛡️ सेफ एक्जिट (+{final_pnl:,.0f}p)" if final_pnl < 150 else f"✅ बड़ा प्रॉफिट (+{final_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]")
                            eng["active_trade_obj"]["status"] = sts_text; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None; eng["track_signal"] = None
                    
                    if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                        eng["active_trade_obj"]["live_pnl"] = live_pnl; eng["active_trade_obj"]["max_pnl"] = max_pnl

        except Exception as e: eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_persistent_sniper_v3_6():
    worker_id = int(time.time() * 1000)
    eng = {
        "worker_id": worker_id, "ema_initialized": False, "px": 0.0, "buy_pressure": 50.0, "ask_pct": 50.0,
        "current_spread": 0.0, "last_update_ist": "--:--:--", "fast_ema": 50.0, "slow_ema": 50.0, "signal_line": 0.0,
        "max_spread": 0.0, "max_spread_time": "--", "swing_high": 0.0, "swing_low": 0.0,
        "lowest_sweep_px": 999999.0, "highest_sweep_px": 0.0, "sweep_latch_time": 0.0, "sweep_status": 0,
        "htf_trend": "NONE", "htf_sma": 0.0, "buy_pct_history": [],
        "iceberg_score": 0.0, "v_engine": {"dir": "तलाश जारी...", "prob": "-", "score": 0, "reasons": [], "danger": "-", "action": "-"},
        "active_trade_obj": None, "closed_trades_ledger": [], "track_signal": None, "track_entry_px": 0.0, 
        "track_max_fav": 0.0, "track_status": "Idle", "last_err": None, "last_kline_fetch": 0.0
    }
    threading.Thread(target=background_sniper_worker, args=(eng, worker_id), daemon=True).start()
    return eng

eng = get_persistent_sniper_v3_6()

# ============================================================================
# RENDER DASHBOARD
# ============================================================================
if eng["px"] > 0:
    px = eng["px"]
    st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ PRO QUANT TRADER (V3.6) - BTC: ${px:,.1f}</h3>", unsafe_allow_html=True)
    
    # 1. NEW V-SHAPE REVERSAL ENGINE BOX (EXACT USER FORMAT)
    v = eng["v_engine"]
    score_col = "#22c55e" if v["score"] >= 7 else ("#facc15" if v["score"] >= 5 else "#ef4444")
    reasons_html = "".join([f"<li>{r}</li>" for r in v["reasons"]]) if v["reasons"] else "<li>कोई ठोस कारण नहीं (ट्रेंड जारी है)</li>"
    
    st.markdown(f"""
    <div class='vshape-box'>
        <div style='font-size:18px; font-weight:bold; color:#f8fafc; margin-bottom:10px; border-bottom:1px solid #334155; padding-bottom:5px;'>
            🔬 1-Minute V-Shape Microstructure Analyzer
        </div>
        <p style='margin:5px 0;'><b>दिशा:</b> <span style='color:#38bdf8;'>{v['dir']}</span></p>
        <p style='margin:5px 0;'><b>संभावना:</b> <span style='color:{score_col};'>{v['prob']}</span></p>
        <p style='margin:5px 0;'><b>कन्फिडेंस:</b> <span style='font-size:20px; font-weight:900; color:{score_col};'>{v['score']}/10</span></p>
        <div style='margin-top:10px;'><b>मुख्य कारण:</b><ul style='color:#cbd5e1; font-size:14px; margin-top:5px;'>{reasons_html}</ul></div>
        <div style='margin-top:10px; padding:10px; background:#7f1d1d30; border-left:3px solid #ef4444; border-radius:4px;'>
            <b>मुख्य खतरा:</b> <span style='color:#fca5a5;'>{v['danger']}</span>
        </div>
        <div style='margin-top:10px; padding:10px; background:#064e3b30; border-left:3px solid #22c55e; border-radius:4px;'>
            <b>एक्शन आइडिया:</b> <br><span style='color:#86efac; white-space:pre-line;'>{v['action']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. ACTIVE TRADE TRACKER
    st.markdown("<br>", unsafe_allow_html=True)
    if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
        trk_col = "#22c55e" if eng["track_signal"] == "BUY" else "#ef4444"; live_p = eng["active_trade_obj"]["live_pnl"]; max_p = eng["active_trade_obj"]["max_pnl"]; live_col = "#4ade80" if live_p >= 0 else "#f87171"
        st.markdown(f"""<div class='signal-box' style='border-color:{trk_col}; flex-direction:row; justify-content:space-around;'>
        <div style='text-align:left;'><div style='font-size:15px; color:#94a3b8;'>🎯 लाइव मास्टर ट्रेड</div><div style='font-size:24px; color:#ffffff; font-weight:900;'>{eng['track_signal']} @ ${eng['track_entry_px']:,.1f}</div><div style='font-size:14px; color:#facc15; margin-top:6px;'>कारण: {eng['active_trade_obj']['reason']}</div></div>
        <div style='text-align:right; border-left:1px solid #334155; padding-left:25px;'><div style='font-size:15px; color:#94a3b8;'>लाइव PnL: <b style='color:{live_col}; font-size:32px;'>{live_p:+.1f}p</b></div><div style='font-size:15px; color:#cbd5e1;'>मैक्स (High): <b style='color:#38bdf8;'>+{max_p:,.1f}p</b></div></div></div>""", unsafe_allow_html=True)

    # 3. CLOSED TRADES LEDGER
    st.markdown("<div style='color:#facc15; font-size:15px; font-weight:bold; margin-top:20px; margin-bottom:10px;'>📓 पूरे हो चुके ट्रेड्स</div>", unsafe_allow_html=True)
    h_html = ""
    for h in eng["closed_trades_ledger"]:
        h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"; pnl_col = "#22c55e" if h["final_pnl"] > 0 else "#ef4444"; border_cls = "hist-closed-win" if h["final_pnl"] > 0 else "hist-closed-loss"
        h_html += f"<div class='hist-item {border_cls}' style='display:flex; justify-content:space-between; align-items:center;'><div><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b> <span style='color:#c084fc; font-size:11px;'>[{h['reason']}]</span><br><span style='color:#94a3b8; font-size:12px;'>{h['status']}</span></div><div style='font-size:18px; font-weight:900; color:{pnl_col};'>{h['final_pnl']:+.1f}p</div></div>"
    st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"text-align:center;\">कोई ट्रेड नहीं</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()
else:
    st.warning("⏳ 24x7 V3.6 (V-Shape Engine) स्टार्ट हो रहा है... 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 सिस्टम में दिक्कत मिली: {eng['last_err']}")
        st.info("API सर्वर बिजी हो सकता है, कोड अपने आप इसे ठीक करने की कोशिश कर रहा है...")
    time.sleep(2)
    st.rerun()

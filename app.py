import streamlit as st
import requests
import time
import threading
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Manual Trader - V3.3 Simple Hindi", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 14px; border-radius: 12px; text-align: center; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5); }
.zone-box { background: #0f172a; border: 1px solid #334155; padding: 15px; border-radius: 12px; height: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5); }
.signal-box { background: #0f172a; border: 2px dashed #475569; padding: 20px; border-radius: 12px; text-align: center; font-size: 22px; font-weight: 900; height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);}
.buy-sig { border-color: #22c55e; color: #22c55e; background: #064e3b; }
.sell-sig { border-color: #ef4444; color: #ef4444; background: #7f1d1d; }
.bar-container { width: 100%; background: #ef4444; height: 14px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
.bar-fill { background: #22c55e; height: 100%; transition: width 0.3s ease; }
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; padding: 2px 10px !important; }
div.stButton > button:hover { background-color: #ef4444 !important; }
.history-box { background:#1e293b; padding:12px; border-radius:12px; border:1px solid #334155; height: 340px; overflow-y: auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);}
.hist-item { font-size: 13.5px; padding: 10px 12px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom:6px; border-radius:6px; background: #0f172a; line-height: 1.5;}
.hist-tracking { border-left: 4px solid #38bdf8; }
.hist-closed-win { border-left: 4px solid #22c55e; background: #064e3b20; }
.hist-closed-loss { border-left: 4px solid #ef4444; background: #7f1d1d20; }
.hist-void-bull { border-left: 4px solid #22c55e; background: #064e3b15;}
.hist-void-bear { border-left: 4px solid #ef4444; background: #7f1d1d15;}
.hist-void-ice { border-left: 4px solid #facc15; background: #42200630;}
</style>""", unsafe_allow_html=True)

# ============================================================================
# USER LOGIC: FIBO 14.6% PIVOTS
# ============================================================================
def calculate_fibo_146_pivots(df, left_bars=5, right_bars=5):
    window = left_bars + right_bars + 1
    rolling_max = df['High'].rolling(window=window).max()
    rolling_min = df['Low'].rolling(window=window).min()
    is_pivot_high = df['High'].shift(right_bars) == rolling_max
    is_pivot_low = df['Low'].shift(right_bars) == rolling_min
    
    df['Pivot_High_Val'] = np.where(is_pivot_high, df['High'].shift(right_bars), np.nan)
    df['Pivot_Low_Val'] = np.where(is_pivot_low, df['Low'].shift(right_bars), np.nan)
    df['Recent_Swing_High'] = df['Pivot_High_Val'].ffill()
    df['Recent_Swing_Low'] = df['Pivot_Low_Val'].ffill()
    df['Swing_Range'] = df['Recent_Swing_High'] - df['Recent_Swing_Low']
    
    df['Fibo_146_Long_Lvl'] = df['Recent_Swing_High'] - (df['Swing_Range'] * 0.146)
    df['Fibo_146_Short_Lvl'] = df['Recent_Swing_Low'] + (df['Swing_Range'] * 0.146)
    df['Fibo_Long_Signal'] = (df['Low'] <= df['Fibo_146_Long_Lvl']) & (df['Close'] > df['Fibo_146_Long_Lvl'])
    df['Fibo_Short_Signal'] = (df['High'] >= df['Fibo_146_Short_Lvl']) & (df['Close'] < df['Fibo_146_Short_Lvl'])
    return df

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
                bid_vol = sum(float(b["sz"]) for b in bids); ask_vol = sum(float(a["sz"]) for a in asks)
                tot_vol = bid_vol + ask_vol; best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
                mid_px = (best_bid + best_ask) / 2.0; spread = best_ask - best_bid
                bid_pct = (bid_vol / tot_vol * 100.0) if tot_vol > 0 else 50.0
                return {
                    "mid_px": mid_px, "spread": spread, "bid_pct": bid_pct, 
                    "ask_pct": 100.0 - bid_pct, "bid_vol": bid_vol, "ask_vol": ask_vol,
                    "net_vol": bid_vol - ask_vol
                }
    except: pass
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

                df = calculate_fibo_146_pivots(df)
                last_row = df.iloc[-1]
                
                fibo_data = {
                    "piv_high": last_row['Recent_Swing_High'], "piv_low": last_row['Recent_Swing_Low'],
                    "long_lvl": last_row['Fibo_146_Long_Lvl'], "short_lvl": last_row['Fibo_146_Short_Lvl'],
                    "long_sig": bool(last_row['Fibo_Long_Signal']), "short_sig": bool(last_row['Fibo_Short_Signal']),
                    "candle_time": last_row['Time']
                }
                recent_5 = closed_candles[-5:]; cvd_5m = 0.0
                for k in recent_5:
                    o, h, l, c, v = float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k.get("v", 0.0))
                    bull_score = max(0.0, (c - l) + (c - o if c > o else 0.0)); bear_score = max(0.0, (h - c) + (o - c if c < o else 0.0))
                    tot_score = bull_score + bear_score
                    if tot_score > 0: cvd_5m += (v * (bull_score / tot_score)) - (v * (bear_score / tot_score))
                return fibo_data, cvd_5m, htf_trend, sma_100
    except: pass
    return None, 0.0, "NONE", 0.0

# ============================================================================
# 24x7 BACKGROUND WORKER (V3.3 SIMPLE HINDI EDITION)
# ============================================================================
def background_sniper_worker(eng, worker_id):
    SPREAD_VOID_THRESHOLD = 4.0
    
    while True:
        if eng.get("worker_id") != worker_id: break
        try:
            now_ts = time.time(); l2_data = fetch_l2_orderbook()
            new_master_sig = None; master_sig_reason = ""; now_ist_str = get_ist_time_str()

            if now_ts - eng["last_kline_fetch"] > 20:
                fibo_data, cvd_5m, htf_trend, sma_100 = fetch_advanced_klines()
                if fibo_data and pd.notna(fibo_data["piv_high"]) and pd.notna(fibo_data["piv_low"]):
                    eng["htf_trend"] = htf_trend; eng["htf_sma"] = sma_100
                    eng["swing_high"] = fibo_data["piv_high"]; eng["swing_low"] = fibo_data["piv_low"]
                    eng["fibo_long_lvl"] = fibo_data["long_lvl"]; eng["fibo_short_lvl"] = fibo_data["short_lvl"]
                    c_time = fibo_data["candle_time"]
                    
                    if c_time != eng.get("last_fibo_candle_time", 0):
                        if fibo_data["long_sig"] and htf_trend == "BULLISH":
                            new_master_sig = "BUY"; master_sig_reason = "🚀 Fibo 14.6% तेज़ मोमेंटम"; eng["last_fibo_candle_time"] = c_time
                        elif fibo_data["short_sig"] and htf_trend == "BEARISH":
                            new_master_sig = "SELL"; master_sig_reason = "🚀 Fibo 14.6% तेज़ मोमेंटम"; eng["last_fibo_candle_time"] = c_time
                            
                    eng["cvd_5m"] = cvd_5m; eng["cvd_trend"] = 1 if cvd_5m > 0 else -1
                eng["last_kline_fetch"] = now_ts

            if l2_data:
                px = l2_data["mid_px"]; buy_pressure = l2_data["bid_pct"]; current_spread = l2_data["spread"]
                net_vol = l2_data["net_vol"]
                eng["px"] = px; eng["buy_pressure"] = buy_pressure; eng["ask_pct"] = l2_data["ask_pct"]
                eng["current_spread"] = current_spread; eng["last_update_ist"] = now_ist_str
                if current_spread > eng["max_spread"]: eng["max_spread"] = current_spread; eng["max_spread_time"] = now_ist_str

                # 1. OBI MACD ENGINE
                if not eng["ema_initialized"]:
                    eng["fast_ema"] = eng["slow_ema"] = buy_pressure; eng["signal_line"] = 0.0; eng["last_px"] = px
                    eng["ema_initialized"] = True; obi_histogram = macd_diff = 0.0
                else:
                    eng["fast_ema"] = buy_pressure * 0.18 + eng["fast_ema"] * 0.82; eng["slow_ema"] = buy_pressure * 0.06 + eng["slow_ema"] * 0.94
                    obi_histogram = eng["fast_ema"] - eng["slow_ema"]; eng["signal_line"] = obi_histogram * 0.20 + eng["signal_line"] * 0.80
                    macd_diff = obi_histogram - eng["signal_line"]
                eng["obi_histogram"] = obi_histogram; eng["macd_diff"] = macd_diff
                
                if macd_diff > 1.2: eng["bull_confirm_ticks"] = min(5, eng["bull_confirm_ticks"] + 1); eng["bear_confirm_ticks"] = 0
                elif macd_diff < -1.2: eng["bear_confirm_ticks"] = min(5, eng["bear_confirm_ticks"] + 1); eng["bull_confirm_ticks"] = 0
                else: eng["bull_confirm_ticks"] = max(0, eng["bull_confirm_ticks"] - 1); eng["bear_confirm_ticks"] = max(0, eng["bear_confirm_ticks"] - 1)
                if eng["bull_confirm_ticks"] >= 3: eng["last_obi_state"] = "बायर्स हावी"; eng["obi_state_time"] = now_ts
                elif eng["bear_confirm_ticks"] >= 3: eng["last_obi_state"] = "सेलर्स हावी"; eng["obi_state_time"] = now_ts
                elif now_ts - eng.get("obi_state_time", 0.0) > 180: eng["last_obi_state"] = "शांत"

                px_diff = px - eng["last_px"]; eng["px_diff"] = px_diff; eng["last_px"] = px
                if px_diff <= -15.0: eng["spike_active"] = 1
                elif px_diff >= 15.0: eng["spike_active"] = -1
                else: eng["spike_active"] = 0

                # ====================================================================
                # 2. SIMPLE HINDI ICEBERG & WHALE TRACKER
                # ====================================================================
                eng["iceberg_score"] = eng.get("iceberg_score", 0.0) * 0.985
                imbalance_delta = buy_pressure - 50.0

                if abs(imbalance_delta) >= 12.0 and abs(px_diff) <= 5.0:
                    eng["iceberg_score"] += (imbalance_delta * 0.18)

                def get_simple_mood(score_val):
                    if score_val >= 150.0: return "🔥 बायर्स का पूरा कब्ज़ा (BUY ढूँढें)"
                    elif score_val >= 50.0: return "🟢 बायर्स माल भर रहे हैं"
                    elif score_val <= -150.0: return "🔥 सेलर्स का पूरा कब्ज़ा (SELL ढूँढें)"
                    elif score_val <= -50.0: return "🔴 सेलर्स माल दबा रहे हैं"
                    else: return "⚖️ बराबरी की टक्कर (वेट करें)"

                if current_spread >= SPREAD_VOID_THRESHOLD:
                    spread_weight = min(current_spread / 4.0, 3.5)
                    void_delta = imbalance_delta * spread_weight * 0.65
                    
                    if px_diff < -3.0 and buy_pressure >= 56.0:
                        action_tag = "🚨 नकली गिरावट! व्हेल नीचे खरीद रही है"
                        vol_desc = f"व्हेल ने खरीदा: +{abs(net_vol):.0f} BTC"
                        cls_tag = "hist-void-ice"
                        eng["iceberg_score"] += abs(void_delta) * 1.4
                    elif px_diff > 3.0 and buy_pressure <= 44.0:
                        action_tag = "🚨 नकली उछाल! व्हेल ऊपर बेच रही है"
                        vol_desc = f"व्हेल ने बेचा: -{abs(net_vol):.0f} BTC"
                        cls_tag = "hist-void-ice"
                        eng["iceberg_score"] -= abs(void_delta) * 1.4
                    elif buy_pressure >= 55.0:
                        action_tag = "🟢 बायर्स का सीधा हमला (तेज़ खरीदारी)"
                        vol_desc = f"बायर्स ने उठाए: +{abs(net_vol):.0f} BTC ({buy_pressure:.0f}%)"
                        cls_tag = "hist-void-bull"
                        eng["iceberg_score"] += void_delta
                    elif buy_pressure <= 45.0:
                        action_tag = "🔴 सेलर्स का सीधा हमला (तेज़ बिकवाली)"
                        vol_desc = f"सेलर्स ने पटके: -{abs(net_vol):.0f} BTC ({100-buy_pressure:.0f}%)"
                        cls_tag = "hist-void-bear"
                        eng["iceberg_score"] += void_delta
                    else:
                        action_tag = "⚪ दोनों तरफ की खींचतान (कोई साफ दिशा नहीं)"
                        vol_desc = f"अंतर: {net_vol:+.0f} BTC"
                        cls_tag = "hist-item"

                    eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))
                    eng["iceberg_state"] = get_simple_mood(eng["iceberg_score"])

                    jump_txt = f"प्राइस +${px_diff:.1f} उछला" if px_diff > 0 else f"प्राइस -${abs(px_diff):.1f} गिरा"
                    mood_short = "🟢 बायर्स आगे" if eng["iceberg_score"] > 30 else ("🔴 सेलर्स आगे" if eng["iceberg_score"] < -30 else "⚖️ बराबरी पर")

                    void_obj = {
                        "time": now_ist_str,
                        "action": action_tag,
                        "cls": cls_tag,
                        "jump_txt": jump_txt,
                        "vol_desc": vol_desc,
                        "mood_short": f"{mood_short} (स्कोर: {eng['iceberg_score']:+.0f})"
                    }
                    if not eng["void_ledger"] or eng["void_ledger"][0]["time"] != now_ist_str:
                        eng["void_ledger"].insert(0, void_obj)
                        eng["void_ledger"] = eng["void_ledger"][:25]
                else:
                    eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))
                    eng["iceberg_state"] = get_simple_mood(eng["iceberg_score"])

                # 3. SWEEP & ZONE ABSORPTION
                sh, sl = eng["swing_high"], eng["swing_low"]; danger_zone = 45.0
                if sh > 0 and sl > 0:
                    if px <= sl + 10.0: eng["sweep_status"] = -2; eng["lowest_sweep_px"] = min(eng.get("lowest_sweep_px", px), px)
                    elif eng["sweep_status"] == -2 and px >= eng.get("lowest_sweep_px", sl) + 12.0: eng["sweep_status"] = 1; eng["sweep_latch_time"] = now_ts; eng["lowest_sweep_px"] = 999999.0
                    if px >= sh - 10.0: eng["sweep_status"] = 2; eng["highest_sweep_px"] = max(eng.get("highest_sweep_px", px), px)
                    elif eng["sweep_status"] == 2 and px <= eng.get("highest_sweep_px", sh) - 12.0: eng["sweep_status"] = -1; eng["sweep_latch_time"] = now_ts; eng["highest_sweep_px"] = 0.0
                    if eng["sweep_status"] in [1, -1] and (now_ts - eng["sweep_latch_time"] > 300): eng["sweep_status"] = 0

                    near_support = (px <= sl + danger_zone); near_resistance = (px >= sh - danger_zone)
                    if near_support and (eng["cvd_trend"] == -1 or buy_pressure >= 54.0): eng["abs_status"] = 1; eng["abs_latch_time"] = now_ts
                    elif near_resistance and (eng["cvd_trend"] == 1 or buy_pressure <= 46.0): eng["abs_status"] = -1; eng["abs_latch_time"] = now_ts
                    elif now_ts - eng.get("abs_latch_time", 0.0) > 180: eng["abs_status"] = 0

                # 4. MASTER SIGNAL CONFLUENCE
                obi_bull_ok = (eng["last_obi_state"] == "बायर्स हावी") or (macd_diff > 0.8 and buy_pressure >= 54.0)
                obi_bear_ok = (eng["last_obi_state"] == "सेलर्स हावी") or (macd_diff < -0.8 and buy_pressure <= 46.0)

                if not new_master_sig:
                    if eng["sweep_status"] == 1 and (eng["abs_status"] == 1 or obi_bull_ok) and eng["htf_trend"] == "BULLISH": 
                        new_master_sig = "BUY"; master_sig_reason = "🔥 सपोर्ट ट्रैप (3X कन्फर्म)"; eng["sweep_status"] = 0
                    elif eng["sweep_status"] == -1 and (eng["abs_status"] == -1 or obi_bear_ok) and eng["htf_trend"] == "BEARISH": 
                        new_master_sig = "SELL"; master_sig_reason = "🔥 रेजिस्टेंस ट्रैप (3X कन्फर्म)"; eng["sweep_status"] = 0
                    elif eng["iceberg_score"] >= 150.0 and obi_bull_ok and px_diff >= 5.0:
                        new_master_sig = "BUY"; master_sig_reason = "🐳 व्हेल खरीदारी ब्रेकआउट"
                        eng["iceberg_score"] = 60.0
                    elif eng["iceberg_score"] <= -150.0 and obi_bear_ok and px_diff <= -5.0:
                        new_master_sig = "SELL"; master_sig_reason = "🐳 व्हेल बिकवाली ब्रेकडाउन"
                        eng["iceberg_score"] = -60.0

                if new_master_sig and eng["track_status"] == "Tracking" and eng["track_signal"] == new_master_sig:
                    new_master_sig = None

                # 5. SMART POST-SIGNAL TRAILING TRACKER
                if new_master_sig and eng["track_signal"] and eng["track_signal"] != new_master_sig and eng["track_status"] == "Tracking":
                    if eng["active_trade_obj"]:
                        final_pnl = eng["active_trade_obj"]["live_pnl"]; eng["track_status"] = "उल्टा सिग्नल आने पर बंद"
                        eng["active_trade_obj"]["status"] = eng["track_status"]; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                        eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None

                if new_master_sig:
                    eng["track_signal"] = new_master_sig; eng["track_entry_px"] = px; eng["track_max_fav"] = px; eng["track_status"] = "Tracking"
                    eng["active_trade_obj"] = {"open_time": now_ist_str, "close_time": "", "type": new_master_sig, "entry": px, "status": "Tracking", "max_pnl": 0.0, "live_pnl": 0.0, "final_pnl": 0.0, "reason": master_sig_reason}

                if eng["track_status"] == "Tracking" and eng["track_signal"] and eng["active_trade_obj"]:
                    t_type = eng["track_signal"]; t_entry = eng["track_entry_px"]
                    
                    if t_type == "BUY":
                        live_pnl = px - t_entry; eng["track_max_fav"] = max(eng["track_max_fav"], px); max_pnl = eng["track_max_fav"] - t_entry
                        if max_pnl >= 500.0: trail_sl_px = eng["track_max_fav"] - 150.0 
                        elif max_pnl >= 300.0: trail_sl_px = t_entry + 150.0 
                        elif max_pnl >= 150.0: trail_sl_px = t_entry + 10.0 
                        else: trail_sl_px = t_entry - 300.0 

                        if px <= trail_sl_px:
                            eng["track_status"] = "Closed"; final_pnl = live_pnl
                            if final_pnl < 0: sts_text = f"🛑 स्टॉप-लॉस हिट ({final_pnl:+.0f}p)"
                            elif final_pnl < 140: sts_text = f"🛡️ नो-लॉस पर निकला (+{final_pnl:,.0f}p)"
                            else: sts_text = f"✅ प्रॉफिट लॉक (+{final_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"]["status"] = sts_text; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None

                    elif t_type == "SELL":
                        live_pnl = t_entry - px; eng["track_max_fav"] = min(eng["track_max_fav"], px); max_pnl = t_entry - eng["track_max_fav"]
                        if max_pnl >= 500.0: trail_sl_px = eng["track_max_fav"] + 150.0 
                        elif max_pnl >= 300.0: trail_sl_px = t_entry - 150.0 
                        elif max_pnl >= 150.0: trail_sl_px = t_entry - 10.0 
                        else: trail_sl_px = t_entry + 300.0 

                        if px >= trail_sl_px:
                            eng["track_status"] = "Closed"; final_pnl = live_pnl
                            if final_pnl < 0: sts_text = f"🛑 स्टॉप-लॉस हिट ({final_pnl:+.0f}p)"
                            elif final_pnl < 140: sts_text = f"🛡️ नो-लॉस पर निकला (+{final_pnl:,.0f}p)"
                            else: sts_text = f"✅ प्रॉफिट लॉक (+{final_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"]["status"] = sts_text; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None

                    if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                        eng["active_trade_obj"]["live_pnl"] = live_pnl; eng["active_trade_obj"]["max_pnl"] = max_pnl

                eng["closed_trades_ledger"] = eng["closed_trades_ledger"][:30]
        except Exception as e: eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_persistent_sniper_v3_3():
    worker_id = int(time.time() * 1000)
    eng = {
        "worker_id": worker_id, "ema_initialized": False, "px": 0.0, "buy_pressure": 50.0, "ask_pct": 50.0,
        "current_spread": 0.0, "last_update_ist": "--:--:--", "fast_ema": 50.0, "slow_ema": 50.0, "signal_line": 0.0,
        "obi_histogram": 0.0, "macd_diff": 0.0, "bull_confirm_ticks": 0, "bear_confirm_ticks": 0, "last_px": 0.0,
        "px_diff": 0.0, "spike_active": 0, "max_spread": 0.0, "max_spread_time": "--", "swing_high": 0.0, "swing_low": 0.0,
        "fibo_long_lvl": 0.0, "fibo_short_lvl": 0.0, "last_fibo_candle_time": 0, "lowest_sweep_px": 999999.0, "highest_sweep_px": 0.0,
        "sweep_latch_time": 0.0, "abs_latch_time": 0.0, "obi_state_time": 0.0, "cvd_5m": 0.0, "cvd_trend": 0, "last_kline_fetch": 0.0, 
        "sweep_status": 0, "abs_status": 0, "htf_trend": "NONE", "htf_sma": 0.0,
        "iceberg_score": 0.0, "iceberg_state": "⚖️ बराबरी की टक्कर (वेट करें)",
        "active_trade_obj": None, "closed_trades_ledger": [], "void_ledger": [], "track_signal": None, "track_entry_px": 0.0, 
        "track_max_fav": 0.0, "track_status": "Idle", "last_obi_state": "शांत", "last_err": None
    }
    threading.Thread(target=background_sniper_worker, args=(eng, worker_id), daemon=True).start()
    return eng

eng = get_persistent_sniper_v3_3()

col_top1, col_top2, col_top3 = st.columns([0.70, 0.15, 0.15])
with col_top2:
    if st.button("🔄 मीटर रीसेट"): eng["iceberg_score"] = 0.0; st.rerun()
with col_top3:
    if st.button("🔄 स्प्रेड रीसेट"): eng["max_spread"] = 0.0; eng["max_spread_time"] = "--"; st.rerun()

# ============================================================================
# WIN RATE CALCULATOR
# ============================================================================
total_trades = len(eng["closed_trades_ledger"])
wins = sum(1 for t in eng["closed_trades_ledger"] if t["final_pnl"] > 0)
losses = total_trades - wins
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
win_col = "#22c55e" if win_rate >= 50 else "#ef4444"

# ============================================================================
# RENDER DASHBOARD
# ============================================================================
if eng["px"] > 0:
    px, buy_pressure, macd_diff, px_diff, current_spread = eng["px"], eng["buy_pressure"], eng["macd_diff"], eng["px_diff"], eng["current_spread"]
    sh, sl, flo, fsh = eng["swing_high"], eng["swing_low"], eng["fibo_long_lvl"], eng["fibo_short_lvl"]
    htf_trend = eng["htf_trend"]; ice_score = eng["iceberg_score"]

    with col_top1:
        st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ प्रो स्नाइपर डैशबोर्ड (V3.3 सरल हिंदी) - BTC: ${px:,.1f} <span style='font-size:13px; color:#4ade80;'>[लाइव: {eng['last_update_ist']}]</span></h3>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🔴 बायर्स vs सेलर्स 🟢</div><div style='font-size:17px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{eng['ask_pct']:.1f}%</span></div><div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div></div>", unsafe_allow_html=True)
    with c2: 
        diff_col = "#22c55e" if macd_diff > 0 else "#ef4444"
        ticks_str = "🟢" * eng["bull_confirm_ticks"] if eng["bull_confirm_ticks"] > 0 else ("🔴" * eng["bear_confirm_ticks"])
        st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>📊 ऑर्डर फ्लो ({eng['last_obi_state']})</div><div style='font-size:11px; color:#cbd5e1; margin-top:4px;'>मजबूती: {ticks_str if ticks_str else '⚪'}</div><div style='font-size:18px; font-weight:900; color:{diff_col}; margin-top:4px;'>रफ्तार: {macd_diff:+.2f}%</div></div>", unsafe_allow_html=True)
    with c3:
        ice_col = "#22c55e" if ice_score >= 50 else ("#ef4444" if ice_score <= -50 else "#38bdf8")
        st.markdown(f"<div class='metric-box'><div style='color:#facc15; font-size:12px; font-weight:bold;'>🐳 स्मार्ट मनी मीटर (कौन हावी?)</div><div style='font-size:18px; font-weight:900; color:{ice_col}; margin-top:4px;'>स्कोर: {ice_score:+.0f} <span style='font-size:11px; color:#cbd5e1;'>(±150 पर ट्रेड)</span></div><div style='font-size:11.5px; color:#ffffff; font-weight:bold; margin-top:4px;'>{eng['iceberg_state']}</div></div>", unsafe_allow_html=True)
    with c4:
        htf_col = "#22c55e" if htf_trend == "BULLISH" else "#ef4444"
        htf_hindi = "🟢 तेज़ी (BUY ट्रेंड)" if htf_trend == "BULLISH" else "🔴 मंदी (SELL ट्रेंड)"
        st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🏢 बड़ा ट्रेंड (100-SMA)</div><div style='font-size:16px; font-weight:900; color:{htf_col}; margin-top:5px;'>{htf_hindi} <br><span style='font-size:12px; color:#cbd5e1;'>औसत: ${eng['htf_sma']:,.1f}</span></div></div>", unsafe_allow_html=True)
    with c5: st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🧱 ऑर्डरबुक गैप (Spread)</div><div style='font-size:13px; color:#cbd5e1; margin-top:4px;'>अभी: <b style='color:#ffffff;'>${current_spread:.2f}</b></div><div style='font-size:15px; font-weight:900; color:#facc15; margin-top:4px;'>सबसे बड़ा: ${eng['max_spread']:.2f}</div></div>", unsafe_allow_html=True)

    # ROW 2: ZONES AND TRACKER
    st.markdown("<br>", unsafe_allow_html=True)
    r2_c1, r2_c2 = st.columns([0.35, 0.65])
    with r2_c1:
        swp_txt = "⏳ सामान्य चाल (लेवल का इंतज़ार)"; swp_col = "#94a3b8"
        if eng["sweep_status"] == -2: swp_txt = "⚠️ सपोर्ट टेस्ट हो रहा है"; swp_col = "#facc15"
        elif eng["sweep_status"] == 1: swp_txt = "🟢 सपोर्ट ट्रैप तैयार! (BUY की तलाश)"; swp_col = "#22c55e"
        elif eng["sweep_status"] == 2: swp_txt = "⚠️ रेजिस्टेंस टेस्ट हो रहा है"; swp_col = "#facc15"
        elif eng["sweep_status"] == -1: swp_txt = "🔴 रेजिस्टेंस ट्रैप तैयार! (SELL की तलाश)"; swp_col = "#ef4444"
        abs_txt = ""
        if eng["abs_status"] == 1: abs_txt = "<div style='color:#22c55e; font-size:13px; font-weight:bold; margin-top:5px;'>🔥 सपोर्ट पर व्हेल खरीदारी दिख रही है</div>"
        elif eng["abs_status"] == -1: abs_txt = "<div style='color:#ef4444; font-size:13px; font-weight:bold; margin-top:5px;'>🔥 रेजिस्टेंस पर व्हेल बिकवाली दिख रही है</div>"

        st.markdown(f"""<div class='zone-box' style='text-align:center;'><div style='color:#38bdf8; font-size:16px; font-weight:900; margin-bottom:15px; border-bottom:1px solid #334155; padding-bottom:10px;'>🎯 प्रमुख लेवल्स (Support & Resistance)</div><div style='font-size:15px; color:#cbd5e1;'>🔴 ऊपर की रुकावट (High): <b style='color:#ef4444;'>${sh:,.1f}</b></div><div style='font-size:13px; color:#94a3b8; margin-bottom:10px;'>⬇️ Fibo शॉर्ट लेवल (14.6%): <b style='color:#facc15;'>${fsh:,.1f}</b></div><div style='width:50%; margin:10px auto; border-top:1px dashed #475569;'></div><div style='font-size:13px; color:#94a3b8; margin-top:10px;'>⬆️ Fibo लॉन्ग लेवल (14.6%): <b style='color:#38bdf8;'>${flo:,.1f}</b></div><div style='font-size:15px; color:#cbd5e1;'>🟢 नीचे का सहारा (Low): <b style='color:#22c55e;'>${sl:,.1f}</b></div><div style='margin-top:15px; font-size:14px; font-weight:bold; color:{swp_col}; padding:8px; background:#1e293b; border-radius:8px;'>{swp_txt}{abs_txt}</div></div>""", unsafe_allow_html=True)
        
    with r2_c2:
        if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
            trk_col = "#22c55e" if eng["track_signal"] == "BUY" else "#ef4444"; live_p = eng["active_trade_obj"]["live_pnl"]; max_p = eng["active_trade_obj"]["max_pnl"]; live_col = "#4ade80" if live_p >= 0 else "#f87171"
            
            # Show current SL status in simple Hindi
            if max_p >= 500: sl_hindi = "🔒 सुपर ट्रेलिंग चालू (हाई से 150p पीछे)"
            elif max_p >= 300: sl_hindi = "🔒 +150 पॉइंट्स प्रॉफिट पक्का लॉक हो चुका है!"
            elif max_p >= 150: sl_hindi = "🛡️ रिस्क ज़ीरो! स्टॉप-लॉस कॉस्ट (+10p) पर आ गया है"
            else: sl_hindi = "⚠️ शुरुआती स्टॉप-लॉस: -300 पॉइंट्स (+150p जाते ही रिस्क ज़ीरो होगा)"

            st.markdown(f"""<div class='signal-box' style='border-color:{trk_col}; background:#0f172a; flex-direction:row; justify-content:space-around;'>
            <div style='text-align:left;'><div style='font-size:15px; color:#94a3b8; margin-bottom:5px;'>🎯 लाइव ट्रेड चालू है</div><div style='font-size:24px; color:#ffffff; font-weight:900;'>{eng['track_signal']} @ ${eng['track_entry_px']:,.1f}</div><div style='font-size:14px; color:#c084fc; margin-top:4px;'>कारण: {eng['active_trade_obj']['reason']}</div><div style='font-size:13px; color:#facc15; margin-top:6px;'>{sl_hindi}</div></div>
            <div style='text-align:right; border-left:1px solid #334155; padding-left:25px;'><div style='font-size:15px; color:#94a3b8;'>अभी चल रहा प्रॉफिट/लॉस: <b style='color:{live_col}; font-size:32px;'>{live_p:+.1f}p</b></div><div style='font-size:15px; color:#cbd5e1; margin-top:8px;'>अधिकतम गया (High): <b style='color:#38bdf8;'>+{max_p:,.1f}p</b></div></div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='signal-box' style='border-color:#475569; color:#94a3b8;'>⏳ पक्के सिग्नल की तलाश जारी है... ({eng['iceberg_state']})</div>", unsafe_allow_html=True)

    # ROW 3: CLEAN LEDGERS & WIN RATE & SIMPLE HINDI X-RAY
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:10px; font-weight:900; color:{win_col}; font-size:18px; padding:10px; background:#0f172a; border-radius:8px; border:1px solid #334155; display:inline-block;'>🏆 सिस्टम की सफलता दर (Win Rate): {win_rate:.1f}% <span style='font-size:13px; color:#94a3b8;'>(जीते: {wins} | हारे: {losses} | कुल ट्रेड: {total_trades})</span></div>", unsafe_allow_html=True)
    
    h_col1, h_col2, h_col3 = st.columns([0.30, 0.34, 0.36])
    
    with h_col1:
        st.markdown("<div style='color:#38bdf8; font-size:15px; font-weight:bold; margin-bottom:10px;'>🔥 अभी चल रहा ट्रेड</div>", unsafe_allow_html=True)
        if eng["active_trade_obj"]:
            h = eng["active_trade_obj"]; h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"; live_col = "#4ade80" if h["live_pnl"] >= 0 else "#f87171"
            h_html = f"<div class='hist-item hist-tracking'><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b><br><span style='color:#c084fc; font-weight:bold;'>{h['reason']}</span><br><br>अभी: <b style='color:{live_col}; font-size:16px;'>{h['live_pnl']:+.1f}p</b> | हाई: +{h['max_pnl']:,.1f}p</div>"
        else: h_html = "<div class='hist-item' style='color:#64748b; text-align:center; padding-top:140px;'>कोई ट्रेड चालू नहीं है</div>"
        st.markdown(f"<div class='history-box'>{h_html}</div>", unsafe_allow_html=True)

    with h_col2:
        st.markdown("<div style='color:#facc15; font-size:15px; font-weight:bold; margin-bottom:10px;'>📓 पूरे हो चुके ट्रेड्स (प्रॉफिट/लॉस खाता)</div>", unsafe_allow_html=True)
        h_html = ""
        for h in eng["closed_trades_ledger"]:
            h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"; pnl_col = "#22c55e" if h["final_pnl"] > 0 else "#ef4444"; border_cls = "hist-closed-win" if h["final_pnl"] > 0 else "hist-closed-loss"
            h_html += f"<div class='hist-item {border_cls}' style='display:flex; justify-content:space-between; align-items:center;'><div><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b> <span style='color:#c084fc; font-size:11px;'>[{h['reason']}]</span><br><span style='color:#94a3b8; font-size:12px;'>{h['status']} (बंद: {h['close_time']})</span></div><div style='font-size:18px; font-weight:900; color:{pnl_col};'>{h['final_pnl']:+.1f}p</div></div>"
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"color:#64748b; text-align:center; padding-top:140px;\">अभी कोई ट्रेड बंद नहीं हुआ</div>'}</div>", unsafe_allow_html=True)

    with h_col3:
        st.markdown("<div style='color:#38bdf8; font-size:15px; font-weight:bold; margin-bottom:10px;'>🕵️ व्हेल की चाल (सरल भाषा में एक्स-रे)</div>", unsafe_allow_html=True)
        h_html = ""
        for v in eng["void_ledger"]:
            h_html += f"<div class='hist-item {v['cls']}'><b>{v['time']} — {v['action']}</b><br><span style='color:#cbd5e1;'>{v['jump_txt']} | {v['vol_desc']}</span><br><span style='color:#facc15; font-weight:bold;'>कुल माहौल: {v['mood_short']}</span></div>"
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"color:#64748b; text-align:center; padding-top:140px;\">अभी कोई बड़ी हलचल नहीं हुई</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V3.3 (सरल हिंदी एडिशन) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    time.sleep(2)
    st.rerun()

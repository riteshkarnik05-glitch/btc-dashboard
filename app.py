import streamlit as st
import requests
import time
import threading
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Manual Trader - V3.2 Iceberg Quant", layout="wide")

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
.hist-item { font-size: 13px; padding: 9px 11px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom:6px; border-radius:6px; background: #0f172a;}
.hist-tracking { border-left: 4px solid #38bdf8; }
.hist-closed-win { border-left: 4px solid #22c55e; background: #064e3b20; }
.hist-closed-loss { border-left: 4px solid #ef4444; background: #7f1d1d20; }
.hist-void-bull { border-left: 4px solid #22c55e; background: #064e3b15;}
.hist-void-bear { border-left: 4px solid #ef4444; background: #7f1d1d15;}
.hist-void-ice { border-left: 4px solid #38bdf8; background: #0c4a6e25;}
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
# 24x7 BACKGROUND WORKER (V3.2 ICEBERG QUANT ENGINE)
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
                            new_master_sig = "BUY"; master_sig_reason = "🚀 FIBO 14.6% MOMENTUM"; eng["last_fibo_candle_time"] = c_time
                        elif fibo_data["short_sig"] and htf_trend == "BEARISH":
                            new_master_sig = "SELL"; master_sig_reason = "🚀 FIBO 14.6% MOMENTUM"; eng["last_fibo_candle_time"] = c_time
                            
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
                if eng["bull_confirm_ticks"] >= 3: eng["last_obi_state"] = "BULL"; eng["obi_state_time"] = now_ts
                elif eng["bear_confirm_ticks"] >= 3: eng["last_obi_state"] = "BEAR"; eng["obi_state_time"] = now_ts
                elif now_ts - eng.get("obi_state_time", 0.0) > 180: eng["last_obi_state"] = "NONE"

                px_diff = px - eng["last_px"]; eng["px_diff"] = px_diff; eng["last_px"] = px
                if px_diff <= -15.0: eng["spike_active"] = 1
                elif px_diff >= 15.0: eng["spike_active"] = -1
                else: eng["spike_active"] = 0

                # ====================================================================
                # 2. NEW QUANT LOGIC: ICEBERG ACCUMULATION & VOID DIVERGENCE ENGINE
                # ====================================================================
                # Natural 1.5% decay every 2s so old noise fades out without any cooldown timer
                eng["iceberg_score"] = eng.get("iceberg_score", 0.0) * 0.985
                imbalance_delta = buy_pressure - 50.0 # Range: -50 to +50

                # Continuous stealth absorption in sideways market (High imbalance, tiny price move)
                if abs(imbalance_delta) >= 12.0 and abs(px_diff) <= 5.0:
                    eng["iceberg_score"] += (imbalance_delta * 0.18)

                # When Liquidity Void (Spread >= $4.0) hits: Analyze True Intent!
                if current_spread >= SPREAD_VOID_THRESHOLD:
                    spread_weight = min(current_spread / 4.0, 3.5)
                    void_delta = imbalance_delta * spread_weight * 0.65
                    
                    # Detect Hidden Iceberg Divergence vs Aggressive Sweep
                    if px_diff < -3.0 and buy_pressure >= 56.0:
                        # Price dropped, but Buyers have a huge wall -> Passive Whale Absorbing the dip!
                        action_tag = "🧊 Bull Iceberg (Dip Absorbed)"
                        cls_tag = "hist-void-ice"
                        eng["iceberg_score"] += abs(void_delta) * 1.4
                    elif px_diff > 3.0 and buy_pressure <= 44.0:
                        # Price jumped, but Sellers have a huge wall -> Passive Whale Absorbing the pump!
                        action_tag = "🧊 Bear Iceberg (Pump Absorbed)"
                        cls_tag = "hist-void-ice"
                        eng["iceberg_score"] -= abs(void_delta) * 1.4
                    elif buy_pressure >= 55.0:
                        action_tag = "🟢 Buyer Sweep (Aggressive)"
                        cls_tag = "hist-void-bull"
                        eng["iceberg_score"] += void_delta
                    elif buy_pressure <= 45.0:
                        action_tag = "🔴 Seller Sweep (Aggressive)"
                        cls_tag = "hist-void-bear"
                        eng["iceberg_score"] += void_delta
                    else:
                        action_tag = "⚪ Mixed Void Chop"
                        cls_tag = "hist-item"

                    eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))
                    
                    if eng["iceberg_score"] >= 120.0: eng["iceberg_state"] = "🐳 HEAVY BUY ACCUMULATION"
                    elif eng["iceberg_score"] >= 50.0: eng["iceberg_state"] = "🟢 Mild Buy Absorption"
                    elif eng["iceberg_score"] <= -120.0: eng["iceberg_state"] = "🐳 HEAVY SELL DISTRIBUTION"
                    elif eng["iceberg_score"] <= -50.0: eng["iceberg_state"] = "🔴 Mild Sell Distribution"
                    else: eng["iceberg_state"] = "⚖️ Neutral / Balanced"

                    jump_txt = f"+${px_diff:.1f}" if px_diff > 0 else f"${px_diff:.1f}"
                    void_obj = {
                        "time": now_ist_str, "spread": current_spread, "jump": jump_txt,
                        "action": action_tag, "cls": cls_tag, "b_pct": buy_pressure,
                        "net_vol": net_vol, "score_snap": eng["iceberg_score"]
                    }
                    if not eng["void_ledger"] or eng["void_ledger"][0]["time"] != now_ist_str:
                        eng["void_ledger"].insert(0, void_obj)
                        eng["void_ledger"] = eng["void_ledger"][:25]
                else:
                    eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))
                    if eng["iceberg_score"] >= 120.0: eng["iceberg_state"] = "🐳 HEAVY BUY ACCUMULATION"
                    elif eng["iceberg_score"] >= 50.0: eng["iceberg_state"] = "🟢 Mild Buy Absorption"
                    elif eng["iceberg_score"] <= -120.0: eng["iceberg_state"] = "🐳 HEAVY SELL DISTRIBUTION"
                    elif eng["iceberg_score"] <= -50.0: eng["iceberg_state"] = "🔴 Mild Sell Distribution"
                    else: eng["iceberg_state"] = "⚖️ Neutral / Balanced"

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

                # ====================================================================
                # 4. MASTER SIGNAL CONFLUENCE (3X SWEEP OR ICEBERG BREAKOUT)
                # ====================================================================
                obi_bull_ok = (eng["last_obi_state"] == "BULL") or (macd_diff > 0.8 and buy_pressure >= 54.0)
                obi_bear_ok = (eng["last_obi_state"] == "BEAR") or (macd_diff < -0.8 and buy_pressure <= 46.0)

                if not new_master_sig:
                    # Trigger A: Classic 3X Sweep + HTF Trend
                    if eng["sweep_status"] == 1 and (eng["abs_status"] == 1 or obi_bull_ok) and eng["htf_trend"] == "BULLISH": 
                        new_master_sig = "BUY"; master_sig_reason = "🔥 3X SWEEP"; eng["sweep_status"] = 0
                    elif eng["sweep_status"] == -1 and (eng["abs_status"] == -1 or obi_bear_ok) and eng["htf_trend"] == "BEARISH": 
                        new_master_sig = "SELL"; master_sig_reason = "🔥 3X SWEEP"; eng["sweep_status"] = 0
                    
                    # Trigger B: Sideways Iceberg Accumulation Breakout!
                    elif eng["iceberg_score"] >= 150.0 and obi_bull_ok and px_diff >= 5.0:
                        new_master_sig = "BUY"; master_sig_reason = "🐳 ICEBERG ACCUMULATION BREAKOUT"
                        eng["iceberg_score"] = 60.0 # Reset partially after firing
                    elif eng["iceberg_score"] <= -150.0 and obi_bear_ok and px_diff <= -5.0:
                        new_master_sig = "SELL"; master_sig_reason = "🐳 ICEBERG DISTRIBUTION BREAKOUT"
                        eng["iceberg_score"] = -60.0

                if new_master_sig and eng["track_status"] == "Tracking" and eng["track_signal"] == new_master_sig:
                    new_master_sig = None

                # 5. SMART POST-SIGNAL TRAILING TRACKER
                if new_master_sig and eng["track_signal"] and eng["track_signal"] != new_master_sig and eng["track_status"] == "Tracking":
                    if eng["active_trade_obj"]:
                        final_pnl = eng["active_trade_obj"]["live_pnl"]; eng["track_status"] = "Closed (Opposite Signal)"
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
                            if final_pnl < 0: sts_text = f"🛑 Hard SL Hit ({final_pnl:+.0f}p)"
                            elif final_pnl < 140: sts_text = f"🛡️ Break-Even Hit (+{final_pnl:,.0f}p)"
                            else: sts_text = f"✅ Smart Lock (+{final_pnl:,.0f}p) [Peak: +{max_pnl:,.0f}p]"
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
                            if final_pnl < 0: sts_text = f"🛑 Hard SL Hit ({final_pnl:+.0f}p)"
                            elif final_pnl < 140: sts_text = f"🛡️ Break-Even Hit (+{final_pnl:,.0f}p)"
                            else: sts_text = f"✅ Smart Lock (+{final_pnl:,.0f}p) [Peak: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"]["status"] = sts_text; eng["active_trade_obj"]["final_pnl"] = final_pnl; eng["active_trade_obj"]["close_time"] = now_ist_str
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"]); eng["active_trade_obj"] = None

                    if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                        eng["active_trade_obj"]["live_pnl"] = live_pnl; eng["active_trade_obj"]["max_pnl"] = max_pnl

                eng["closed_trades_ledger"] = eng["closed_trades_ledger"][:30]
        except Exception as e: eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_persistent_sniper_v3_2():
    worker_id = int(time.time() * 1000)
    eng = {
        "worker_id": worker_id, "ema_initialized": False, "px": 0.0, "buy_pressure": 50.0, "ask_pct": 50.0,
        "current_spread": 0.0, "last_update_ist": "--:--:--", "fast_ema": 50.0, "slow_ema": 50.0, "signal_line": 0.0,
        "obi_histogram": 0.0, "macd_diff": 0.0, "bull_confirm_ticks": 0, "bear_confirm_ticks": 0, "last_px": 0.0,
        "px_diff": 0.0, "spike_active": 0, "max_spread": 0.0, "max_spread_time": "--", "swing_high": 0.0, "swing_low": 0.0,
        "fibo_long_lvl": 0.0, "fibo_short_lvl": 0.0, "last_fibo_candle_time": 0, "lowest_sweep_px": 999999.0, "highest_sweep_px": 0.0,
        "sweep_latch_time": 0.0, "abs_latch_time": 0.0, "obi_state_time": 0.0, "cvd_5m": 0.0, "cvd_trend": 0, "last_kline_fetch": 0.0, 
        "sweep_status": 0, "abs_status": 0, "htf_trend": "NONE", "htf_sma": 0.0,
        "iceberg_score": 0.0, "iceberg_state": "⚖️ Neutral / Balanced",
        "active_trade_obj": None, "closed_trades_ledger": [], "void_ledger": [], "track_signal": None, "track_entry_px": 0.0, 
        "track_max_fav": 0.0, "track_status": "Idle", "last_obi_state": "NONE", "last_err": None
    }
    threading.Thread(target=background_sniper_worker, args=(eng, worker_id), daemon=True).start()
    return eng

eng = get_persistent_sniper_v3_2()

col_top1, col_top2, col_top3 = st.columns([0.70, 0.15, 0.15])
with col_top2:
    if st.button("🔄 Reset Iceberg"): eng["iceberg_score"] = 0.0; st.rerun()
with col_top3:
    if st.button("🔄 Reset Spread"): eng["max_spread"] = 0.0; eng["max_spread_time"] = "--"; st.rerun()

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
        st.markdown(f"<h3 style='color:#38bdf8; font-weight:800; margin-top:0;'>⚡ PRO QUANT TRADER (V3.2 ICEBERG) - BTC: ${px:,.1f} <span style='font-size:13px; color:#4ade80;'>[Live: {eng['last_update_ist']}]</span></h3>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🔴 LIVE OBI 🟢</div><div style='font-size:17px; font-weight:900; margin-top:5px;'><span style='color:#22c55e;'>{buy_pressure:.1f}%</span> / <span style='color:#ef4444;'>{eng['ask_pct']:.1f}%</span></div><div class='bar-container'><div class='bar-fill' style='width:{buy_pressure}%;'></div></div></div>", unsafe_allow_html=True)
    with c2: 
        diff_col = "#22c55e" if macd_diff > 0 else "#ef4444"
        ticks_str = "🟢" * eng["bull_confirm_ticks"] if eng["bull_confirm_ticks"] > 0 else ("🔴" * eng["bear_confirm_ticks"])
        st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>📊 OBI MACD ({eng['last_obi_state']})</div><div style='font-size:11px; color:#cbd5e1; margin-top:4px;'>Ticks: {ticks_str if ticks_str else '⚪'}</div><div style='font-size:18px; font-weight:900; color:{diff_col}; margin-top:4px;'>Diff: {macd_diff:+.2f}%</div></div>", unsafe_allow_html=True)
    with c3:
        ice_col = "#22c55e" if ice_score >= 50 else ("#ef4444" if ice_score <= -50 else "#38bdf8")
        ice_pct = min(100.0, max(0.0, (ice_score + 300.0) / 600.0 * 100.0))
        st.markdown(f"<div class='metric-box'><div style='color:#facc15; font-size:12px; font-weight:bold;'>🐳 ICEBERG NET FLOW</div><div style='font-size:18px; font-weight:900; color:{ice_col}; margin-top:4px;'>{ice_score:+.1f} <span style='font-size:11px; color:#cbd5e1;'>(±150 Trig)</span></div><div style='font-size:11px; color:#94a3b8; margin-top:3px;'>{eng['iceberg_state']}</div></div>", unsafe_allow_html=True)
    with c4:
        htf_col = "#22c55e" if htf_trend == "BULLISH" else "#ef4444"
        st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🏢 HTF TREND (100-SMA)</div><div style='font-size:17px; font-weight:900; color:{htf_col}; margin-top:5px;'>{htf_trend} <br><span style='font-size:12px; color:#cbd5e1;'>Base: ${eng['htf_sma']:,.1f}</span></div></div>", unsafe_allow_html=True)
    with c5: st.markdown(f"<div class='metric-box'><div style='color:#94a3b8; font-size:12px; font-weight:bold;'>🧱 SPREAD SPIKE</div><div style='font-size:13px; color:#cbd5e1; margin-top:4px;'>Live: <b style='color:#ffffff;'>${current_spread:.2f}</b></div><div style='font-size:15px; font-weight:900; color:#facc15; margin-top:4px;'>Max: ${eng['max_spread']:.2f} <span style='font-size:10px; color:#94a3b8;'>({eng['max_spread_time']})</span></div></div>", unsafe_allow_html=True)

    # ROW 2: ZONES AND TRACKER
    st.markdown("<br>", unsafe_allow_html=True)
    r2_c1, r2_c2 = st.columns([0.35, 0.65])
    with r2_c1:
        swp_txt = "⏳ Normal Flow"; swp_col = "#94a3b8"
        if eng["sweep_status"] == -2: swp_txt = "⚠️ Testing Support"; swp_col = "#facc15"
        elif eng["sweep_status"] == 1: swp_txt = "🟢 Bull Sweep Armed"; swp_col = "#22c55e"
        elif eng["sweep_status"] == 2: swp_txt = "⚠️ Testing Resistance"; swp_col = "#facc15"
        elif eng["sweep_status"] == -1: swp_txt = "🔴 Bear Sweep Armed"; swp_col = "#ef4444"
        abs_txt = ""
        if eng["abs_status"] == 1: abs_txt = "<div style='color:#22c55e; font-size:13px; font-weight:bold; margin-top:5px;'>🔥 Bullish Whale Absorption</div>"
        elif eng["abs_status"] == -1: abs_txt = "<div style='color:#ef4444; font-size:13px; font-weight:bold; margin-top:5px;'>🔥 Bearish Whale Absorption</div>"

        st.markdown(f"""<div class='zone-box' style='text-align:center;'><div style='color:#38bdf8; font-size:16px; font-weight:900; margin-bottom:15px; border-bottom:1px solid #334155; padding-bottom:10px;'>🎯 MARKET ZONES & TRAPS</div><div style='font-size:15px; color:#cbd5e1;'>🔴 Swing High: <b style='color:#ef4444;'>${sh:,.1f}</b></div><div style='font-size:13px; color:#94a3b8; margin-bottom:10px;'>⬇️ Fibo Short Rej (14.6%): <b style='color:#facc15;'>${fsh:,.1f}</b></div><div style='width:50%; margin:10px auto; border-top:1px dashed #475569;'></div><div style='font-size:13px; color:#94a3b8; margin-top:10px;'>⬆️ Fibo Long Rej (14.6%): <b style='color:#38bdf8;'>${flo:,.1f}</b></div><div style='font-size:15px; color:#cbd5e1;'>🟢 Swing Low: <b style='color:#22c55e;'>${sl:,.1f}</b></div><div style='margin-top:15px; font-size:15px; font-weight:bold; color:{swp_col}; padding:8px; background:#1e293b; border-radius:8px;'>{swp_txt}{abs_txt}</div></div>""", unsafe_allow_html=True)
        
    with r2_c2:
        if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
            trk_col = "#22c55e" if eng["track_signal"] == "BUY" else "#ef4444"; live_p = eng["active_trade_obj"]["live_pnl"]; max_p = eng["active_trade_obj"]["max_pnl"]; live_col = "#4ade80" if live_p >= 0 else "#f87171"
            st.markdown(f"""<div class='signal-box' style='border-color:{trk_col}; background:#0f172a; flex-direction:row; justify-content:space-around;'>
            <div style='text-align:left;'><div style='font-size:15px; color:#94a3b8; margin-bottom:5px;'>🎯 Active Trade Tracker</div><div style='font-size:24px; color:#ffffff; font-weight:900;'>{eng['track_signal']} @ ${eng['track_entry_px']:,.1f}</div><div style='font-size:13px; color:#c084fc; margin-top:4px;'>{eng['active_trade_obj']['reason']}</div><div style='font-size:13px; color:#facc15; margin-top:4px;'>SMART TIER TRAILING SL ACTIVE</div></div>
            <div style='text-align:right; border-left:1px solid #334155; padding-left:25px;'><div style='font-size:15px; color:#94a3b8;'>Live PnL: <b style='color:{live_col}; font-size:32px;'>{live_p:+.1f}p</b></div><div style='font-size:15px; color:#cbd5e1; margin-top:8px;'>Max Favorable: <b style='color:#38bdf8;'>+{max_p:,.1f}p</b></div></div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='signal-box' style='border-color:#475569; color:#94a3b8;'>⏳ Scanning 3X Sweep, Fibo 14.6%, & Iceberg Accumulation ({htf_trend})...</div>", unsafe_allow_html=True)

    # ROW 3: CLEAN LEDGERS & WIN RATE & ICEBERG VOIDS
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:10px; font-weight:900; color:{win_col}; font-size:18px; padding:10px; background:#0f172a; border-radius:8px; border:1px solid #334155; display:inline-block;'>🏆 Smart Money Win Rate: {win_rate:.1f}% <span style='font-size:13px; color:#94a3b8;'>(Wins: {wins} | Losses: {losses} | Total: {total_trades})</span></div>", unsafe_allow_html=True)
    
    h_col1, h_col2, h_col3 = st.columns([0.32, 0.34, 0.34])
    
    with h_col1:
        st.markdown("<div style='color:#38bdf8; font-size:15px; font-weight:bold; margin-bottom:10px;'>🔥 Live Active Trade Logs</div>", unsafe_allow_html=True)
        if eng["active_trade_obj"]:
            h = eng["active_trade_obj"]; h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"; live_col = "#4ade80" if h["live_pnl"] >= 0 else "#f87171"
            h_html = f"<div class='hist-item hist-tracking'><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b><br><span style='color:#c084fc; font-weight:bold;'>{h['reason']}</span><br><br>Live: <b style='color:{live_col}; font-size:15px;'>{h['live_pnl']:+.1f}p</b> | Max: +{h['max_pnl']:,.1f}p</div>"
        else: h_html = "<div class='hist-item' style='color:#64748b; text-align:center; padding-top:140px;'>No Active Trade</div>"
        st.markdown(f"<div class='history-box'>{h_html}</div>", unsafe_allow_html=True)

    with h_col2:
        st.markdown("<div style='color:#facc15; font-size:15px; font-weight:bold; margin-bottom:10px;'>📓 Closed Trades Ledger</div>", unsafe_allow_html=True)
        h_html = ""
        for h in eng["closed_trades_ledger"]:
            h_type_col = "#22c55e" if h["type"] == "BUY" else "#ef4444"; pnl_col = "#22c55e" if h["final_pnl"] > 0 else "#ef4444"; border_cls = "hist-closed-win" if h["final_pnl"] > 0 else "hist-closed-loss"
            h_html += f"<div class='hist-item {border_cls}' style='display:flex; justify-content:space-between; align-items:center;'><div><b>{h['open_time']} - <span style='color:{h_type_col};'>{h['type']}</span> @ ${h['entry']:,.1f}</b> <span style='color:#c084fc; font-size:11px;'>[{h['reason']}]</span><br><span style='color:#94a3b8; font-size:11.5px;'>{h['status']}</span></div><div style='font-size:18px; font-weight:900; color:{pnl_col};'>{h['final_pnl']:+.1f}p</div></div>"
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"color:#64748b; text-align:center; padding-top:140px;\">No Closed Trades Yet</div>'}</div>", unsafe_allow_html=True)

    with h_col3:
        st.markdown("<div style='color:#38bdf8; font-size:15px; font-weight:bold; margin-bottom:10px;'>🧊 Iceberg & Void X-Ray (Spread > $4.0)</div>", unsafe_allow_html=True)
        h_html = ""
        for v in eng["void_ledger"]:
            h_html += f"<div class='hist-item {v['cls']}'><b>{v['time']} - <span style='color:#facc15;'>Void: ${v['spread']:.1f}</span> | {v['action']}</b><br><span style='color:#cbd5e1;'>Jump: {v['jump']} | Buy: {v['b_pct']:.0f}% | Net Vol: {v['net_vol']:+.1f} BTC | <b>Score: {v['score_snap']:+.0f}</b></span></div>"
        st.markdown(f"<div class='history-box'>{h_html if h_html else '<div class=hist-item style=\"color:#64748b; text-align:center; padding-top:140px;\">No Voids Yet</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V3.2 (Iceberg Quant Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    time.sleep(2)
    st.rerun()

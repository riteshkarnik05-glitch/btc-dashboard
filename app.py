import streamlit as st
import requests
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V5.0 - Smart Microstructure Engine", layout="wide")

# ============================================================================
# CLEAN INSTITUTIONAL UI STYLING
# ============================================================================
st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.top-header { background: #1e293b; border: 1px solid #334155; padding: 12px 18px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 12px 14px; border-radius: 10px; text-align: center; height: 132px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.card-title { font-size: 11.5px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.panel-box { background: #0f172a; border: 1px solid #334155; padding: 15px; border-radius: 10px; height: 410px; overflow-y: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.vshape-box { background: #0f172a; border: 1px solid #38bdf8; border-left: 5px solid #38bdf8; padding: 15px; border-radius: 10px; height: 410px; overflow-y: auto; }
.bar-container { width: 100%; background: #ef4444; height: 9px; border-radius: 5px; overflow: hidden; display: flex; }
.bar-buy { background: #22c55e; height: 100%; transition: width 0.3s ease; }
.bar-sell { background: #ef4444; height: 100%; transition: width 0.3s ease; }
.badge { padding: 4px 9px; border-radius: 5px; font-size: 11.5px; font-weight: bold; display: inline-block; }
.badge-green { background-color: #064e3b; color: #4ade80; border: 1px solid #22c55e; }
.badge-red { background-color: #7f1d1d; color: #f87171; border: 1px solid #ef4444; }
.badge-yellow { background-color: #422006; color: #facc15; border: 1px solid #eab308; }
.badge-cyan { background-color: #083344; color: #22d3ee; border: 1px solid #06b6d4; }
.badge-gray { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; }
.table-wrapper { background: #0f172a; border-radius: 10px; border: 1px solid #334155; max-height: 360px; overflow-y: auto; margin-top: 10px; }
table.custom-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12.8px; }
table.custom-table th { color: #94a3b8; border-bottom: 1px solid #334155; padding: 10px 12px; background: #1e293b; position: sticky; top: 0; z-index: 10; }
table.custom-table td { padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #f8fafc; }
.hist-item { font-size: 12.8px; padding: 9px 12px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom: 6px; border-radius: 6px; background: #1e293b; }
.hist-win { border-left: 4px solid #22c55e; }
.hist-loss { border-left: 4px solid #ef4444; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# SMART DATA PIPELINES (WEIGHTED L2 + TAKER TAPE + REAL OI & BASIS + KLINES)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def fetch_weighted_l2_and_tape():
    """Fetches Distance-Weighted L2 Orderbook & Real Executed Taker Trades"""
    try:
        r_ob = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2.5)
        if r_ob.status_code != 200:
            return None
        data = r_ob.json()
        if not data or "levels" not in data or len(data["levels"]) < 2:
            return None

        bids = data["levels"][0][:20]
        asks = data["levels"][1][:20]
        if not bids or not asks:
            return None

        best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
        mid_px = (best_bid + best_ask) / 2.0

        # Anti-Spoofing Distance-Weighted Orderbook Calculation
        # Levels 1-5: 1.0x weight | Levels 6-10: 0.5x weight | Levels 11-20: 0.2x weight
        weights = [1.0]*5 + [0.5]*5 + [0.2]*10
        w_bid_sz = sum(float(b["sz"]) * weights[i] for i, b in enumerate(bids))
        w_ask_sz = sum(float(a["sz"]) * weights[i] for i, a in enumerate(asks))
        w_tot = w_bid_sz + w_ask_sz
        weighted_ob_pct = (w_bid_sz / w_tot * 100.0) if w_tot > 0 else 50.0

        # Near-Book (L1-L3) vs Deep-Book (L10-L20) Spoof Detection
        near_bid = sum(float(b["sz"]) for b in bids[:3])
        near_ask = sum(float(a["sz"]) for a in asks[:3])
        l1_pct = (near_bid / (near_bid + near_ask) * 100.0) if (near_bid + near_ask) > 0 else 50.0

        # Fetch Real Executed Taker Trades (Market Buy vs Market Sell Tape)
        taker_buy_vol = 0.0
        taker_sell_vol = 0.0
        try:
            r_tr = requests.post(HYPERLIQUID_URL, json={"type": "recentTrades", "coin": "BTC"}, timeout=2.0)
            if r_tr.status_code == 200:
                trades = r_tr.json()
                if isinstance(trades, list):
                    for t in trades[:40]:
                        sz = float(t.get("sz", 0.0))
                        if t.get("side") == "B":
                            taker_buy_vol += sz
                        else:
                            taker_sell_vol += sz
        except:
            pass

        tot_taker = taker_buy_vol + taker_sell_vol
        taker_buy_pct = (taker_buy_vol / tot_taker * 100.0) if tot_taker > 0 else weighted_ob_pct
        net_tape_delta = taker_buy_vol - taker_sell_vol

        return {
            "mark_price": mid_px,
            "spread": best_ask - best_bid,
            "w_ob_pct": weighted_ob_pct,
            "l1_pct": l1_pct,
            "taker_buy_pct": taker_buy_pct,
            "net_tape_delta": net_tape_delta,
            "w_bid_sz": w_bid_sz,
            "w_ask_sz": w_ask_sz
        }
    except Exception as e:
        return str(e)

def fetch_real_oi_and_basis():
    """Fetches Real Open Interest, Oracle Spot Price, and Basis Spread"""
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "metaAndAssetCtxs"}, timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                universe = data[0].get("universe", [])
                ctxs = data[1]
                for idx, asset in enumerate(universe):
                    if asset.get("name") == "BTC" and idx < len(ctxs):
                        c = ctxs[idx]
                        oi = float(c.get("openInterest", 0.0))
                        mark_px = float(c.get("markPx", 0.0))
                        oracle_px = float(c.get("oraclePx", mark_px))
                        funding = float(c.get("funding", 0.0)) * 100.0
                        return {
                            "oi": oi,
                            "basis": mark_px - oracle_px,
                            "funding": funding
                        }
    except:
        pass
    return None

def fetch_smart_klines():
    """Calculates 15m Box, ATR Dynamic Buffer, RVOL, and Candle Efficiency"""
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (65 * 60 * 1000)
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 25:
                closed = data[:-1]
                df = pd.DataFrame(closed)
                df.rename(columns={'o':'Open', 'h':'High', 'l':'Low', 'c':'Close', 'v':'Volume'}, inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)

                # True Range & ATR (14-period) for Dynamic Noise Filtering
                df['Range'] = (df['High'] - df['Low']).clip(lower=1.0)
                df['Body'] = (df['Close'] - df['Open']).abs()
                df['Efficiency'] = df['Body'] / df['Range'] # 0.0 = pure wick, 1.0 = pure Marubozu
                atr_14 = float(df['Range'].tail(14).mean())

                # Relative Volume (Last 2 candles vs 20-period average)
                avg_vol_20 = max(0.1, float(df['Volume'].tail(20).mean()))
                recent_vol = float(df['Volume'].tail(2).mean())
                rvol = recent_vol / avg_vol_20

                # 15-Min Volatility Box (Shifted by 1)
                last_15 = df.tail(15)
                raw_bh = float(last_15['High'].max())
                raw_bl = float(last_15['Low'].min())
                raw_bw = raw_bh - raw_bl

                # Dynamic ATR Choppiness Buffer (Instead of blind fixed buffer)
                noise_buf = max(12.0, atr_14 * 0.45) if raw_bw < 45.0 else 0.0
                bh = raw_bh + noise_buf
                bl = raw_bl - noise_buf

                # 10-Min Stretch & Wick Rejection Metrics for V-Shape
                last_10 = df.tail(10)
                h10 = float(last_10['High'].max())
                l10 = float(last_10['Low'].min())
                last_close = float(df['Close'].iloc[-1])
                last_eff = float(df['Efficiency'].iloc[-1])

                # 5-Min Volume-Weighted Directional Pressure (Clean Smooth Track)
                last_5 = df.tail(5)
                bull_flow = 0.0
                bear_flow = 0.0
                for _, row in last_5.iterrows():
                    rng = row['Range']
                    vol_mult = row['Volume'] + (avg_vol_20 * 0.5)
                    # Upper close & lower wick adds to Bull (PE Put Writing proxy)
                    bull_ratio = ((row['Close'] - row['Low']) / rng)
                    bear_ratio = ((row['High'] - row['Close']) / rng)
                    bull_flow += bull_ratio * vol_mult * 100.0
                    bear_flow += bear_ratio * vol_mult * 100.0

                htf_sma = float(df['Close'].tail(50).mean())
                htf_trend = "BULLISH" if last_close > htf_sma else "BEARISH"

                return {
                    "bh": bh, "bl": bl, "bw": bh - bl,
                    "h10": h10, "l10": l10, "atr": atr_14,
                    "rvol": rvol, "last_eff": last_eff, "last_close": last_close,
                    "pe_base": bull_flow / 5.0, "ce_base": bear_flow / 5.0,
                    "htf_trend": htf_trend
                }
    except Exception as e:
        return str(e)
    return None

# ============================================================================
# 24x7 BACKGROUND WORKER (V5.0 INSTITUTIONAL ENGINE)
# ============================================================================
def background_worker(eng, worker_id):
    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            ist_dt = get_ist_now()
            ist_full = ist_dt.strftime('%I:%M:%S %p')
            ist_min = ist_dt.strftime('%H:%M')

            micro = fetch_weighted_l2_and_tape()
            if isinstance(micro, str):
                eng["last_err"] = micro
            elif micro:
                px = micro["mark_price"]
                w_ob_pct = micro["w_ob_pct"]
                l1_pct = micro["l1_pct"]
                taker_pct = micro["taker_buy_pct"]

                if eng["px"] == 0.0:
                    eng["last_px"] = px
                px_diff = px - eng["last_px"]
                eng["last_px"] = px
                eng["px"] = px
                eng["w_ob_pct"] = w_ob_pct
                eng["l1_pct"] = l1_pct
                eng["taker_pct"] = taker_pct
                eng["net_tape_delta"] = micro["net_tape_delta"]
                eng["buy_sz"] = micro["w_bid_sz"]
                eng["sell_sz"] = micro["w_ask_sz"]
                eng["last_update_ist"] = ist_full

                # Smooth EMA of Taker Tape & Weighted L2 (Eliminates 1-second spoofing glitches)
                eng["smooth_taker"] = (taker_pct * 0.35) + (eng["smooth_taker"] * 0.65)
                eng["smooth_ob"] = (w_ob_pct * 0.30) + (eng["smooth_ob"] * 0.70)

                eng["buy_pct_history"].append(eng["smooth_ob"])
                if len(eng["buy_pct_history"]) > 45:
                    eng["buy_pct_history"].pop(0)

                # Fetch Real OI, Basis & Klines every 12 seconds
                if now_ts - eng["last_kline_ts"] > 12 or eng["box_high"] == 0.0:
                    kdata = fetch_smart_klines()
                    if isinstance(kdata, str):
                        eng["last_err"] = kdata
                    elif kdata:
                        eng["box_high"] = kdata["bh"]
                        eng["box_low"] = kdata["bl"]
                        eng["box_width"] = kdata["bw"]
                        eng["h10"] = kdata["h10"]
                        eng["l10"] = kdata["l10"]
                        eng["atr"] = kdata["atr"]
                        eng["rvol"] = kdata["rvol"]
                        eng["last_eff"] = kdata["last_eff"]
                        eng["last_close"] = kdata["last_close"]
                        eng["pe_base"] = kdata["pe_base"]
                        eng["ce_base"] = kdata["ce_base"]
                        eng["htf_trend"] = kdata["htf_trend"]

                    oi_data = fetch_real_oi_and_basis()
                    if oi_data:
                        curr_oi = oi_data["oi"]
                        eng["oi_history"].append(curr_oi)
                        if len(eng["oi_history"]) > 25: # ~5 mins of 12s snapshots
                            eng["oi_history"].pop(0)
                        eng["oi_change_5m"] = curr_oi - eng["oi_history"][0]
                        eng["basis"] = oi_data["basis"]
                        eng["funding"] = oi_data["funding"]

                    eng["last_kline_ts"] = now_ts

                # ================================================================
                # 1. NORMALIZED DUAL-TRACK SCORE (EMA SMOOTHED, NO SPIKE NOISE)
                # ================================================================
                # Blend 5m structural flow with smoothed Taker Tape & OI Buildup
                oi_bull_bonus = 60.0 if (eng["oi_change_5m"] > 0 and px_diff >= 0) else 0.0
                oi_bear_bonus = 60.0 if (eng["oi_change_5m"] > 0 and px_diff < 0) else 0.0

                raw_buy_t = eng["pe_base"] + max(0.0, (eng["smooth_taker"] - 48.0) * 14.0) + oi_bull_bonus
                raw_sell_t = eng["ce_base"] + max(0.0, (52.0 - eng["smooth_taker"]) * 14.0) + oi_bear_bonus

                # Smooth the tracks so they never flip-flop randomly in 2 seconds
                eng["buy_track"] = (raw_buy_t * 0.25) + (eng["buy_track"] * 0.75)
                eng["sell_track"] = (raw_sell_t * 0.25) + (eng["sell_track"] * 0.75)
                buy_track = eng["buy_track"]
                sell_track = eng["sell_track"]

                # ================================================================
                # 2. 100-POINT MASTER QUANT CONVICTION ENGINE
                # ================================================================
                # Calculates true institutional conviction (0-100) for both Bull & Bear
                bull_pts = 0
                bear_pts = 0

                # Factor A: Real Executed Taker Tape (Max 25 pts)
                if eng["smooth_taker"] >= 58.0: bull_pts += 25
                elif eng["smooth_taker"] >= 53.0: bull_pts += 15
                if eng["smooth_taker"] <= 42.0: bear_pts += 25
                elif eng["smooth_taker"] <= 47.0: bear_pts += 15

                # Factor B: Distance-Weighted L2 + L1 Micro Alignment (Max 20 pts)
                if eng["smooth_ob"] >= 55.0 and l1_pct >= 52.0: bull_pts += 20
                elif eng["smooth_ob"] >= 52.0: bull_pts += 10
                if eng["smooth_ob"] <= 45.0 and l1_pct <= 48.0: bear_pts += 20
                elif eng["smooth_ob"] <= 48.0: bear_pts += 10

                # Factor C: Dual-Track Dominance 15% Rule (Max 25 pts)
                if buy_track > sell_track * 1.15: bull_pts += 25
                elif buy_track > sell_track * 1.05: bull_pts += 12
                if sell_track > buy_track * 1.15: bear_pts += 25
                elif sell_track > buy_track * 1.05: bear_pts += 12

                # Factor D: Real Futures OI & Spot-Mark Basis (Max 15 pts)
                if eng["oi_change_5m"] >= 0 and eng["basis"] >= -5.0: bull_pts += 15
                elif eng["basis"] >= 0: bull_pts += 8
                if eng["oi_change_5m"] >= 0 and eng["basis"] <= 5.0: bear_pts += 15
                elif eng["basis"] <= 0: bear_pts += 8

                # Factor E: RVOL & HTF Trend Support (Max 15 pts)
                if eng["rvol"] >= 1.15:
                    bull_pts += 10; bear_pts += 10
                if eng["htf_trend"] == "BULLISH": bull_pts += 5
                else: bear_pts += 5

                eng["bull_conviction"] = min(100, bull_pts)
                eng["bear_conviction"] = min(100, bear_pts)

                # ================================================================
                # 3. ANTI-WICK BBNT ENGINE (3-TICK HOLD + TRAP DETECTOR)
                # ================================================================
                bh, bl = eng["box_high"], eng["box_low"]
                sig_text = "Neutral (Inside Box)"
                sig_cls = "badge-gray"
                locked_pts = 0.0
                new_master_sig = None
                master_reason = ""

                if bh > 0 and bl > 0:
                    # Manage Existing Locked State
                    if eng["lock_state"] == "LONG":
                        locked_pts = px - eng["lock_trigger_px"]
                        # Exit only if price falls deeply back into box OR strong opposite dominance
                        if px < (eng["lock_box_high"] - 15.0) or (sell_track > buy_track * 1.20 and eng["smooth_taker"] < 44.0):
                            eng["lock_state"] = "NONE"
                            eng["up_hold_ticks"] = 0
                        else:
                            sig_text = f"Riding LONG ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-green"

                    elif eng["lock_state"] == "SHORT":
                        locked_pts = eng["lock_trigger_px"] - px
                        if px > (eng["lock_box_low"] + 15.0) or (buy_track > sell_track * 1.20 and eng["smooth_taker"] > 56.0):
                            eng["lock_state"] = "NONE"
                            eng["dn_hold_ticks"] = 0
                        else:
                            sig_text = f"Riding SHORT ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-red"

                    # Evaluate New Breakouts With 3-Tick Anti-Wick Filter
                    if eng["lock_state"] == "NONE":
                        if px > bh:
                            eng["up_hold_ticks"] += 1
                            eng["dn_hold_ticks"] = 0
                            # Check if Taker Tape is actually selling into this high (Bull Trap!)
                            if eng["smooth_taker"] <= 45.0 or sell_track >= buy_track:
                                sig_text = "🪤 Fake Breakout / Bull Trap (Whale Selling)"
                                sig_cls = "badge-yellow"
                            elif eng["up_hold_ticks"] < 3:
                                sig_text = f"⏳ Testing Upper Breakout (Hold: {eng['up_hold_ticks']}/3)"
                                sig_cls = "badge-cyan"
                            elif eng["bull_conviction"] >= 70:
                                hc = "★ High Conviction " if eng["bull_conviction"] >= 82 else ""
                                sig_text = f"{hc}True Breakout (LONG) [{eng['bull_conviction']}%]"
                                sig_cls = "badge-green"
                                eng["lock_state"] = "LONG"
                                eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh
                                eng["lock_box_low"] = bl
                                new_master_sig = "BUY"
                                master_reason = f"📦 पक्का BBNT ब्रेकआउट (Conviction: {eng['bull_conviction']}%)"
                            else:
                                sig_text = f"⚠️ Weak Breakout (Low Score: {eng['bull_conviction']}%)"
                                sig_cls = "badge-yellow"

                        elif px < bl:
                            eng["dn_hold_ticks"] += 1
                            eng["up_hold_ticks"] = 0
                            if eng["smooth_taker"] >= 55.0 or buy_track >= sell_track:
                                sig_text = "🪤 Fake Breakdown / Spring (Whale Buying)"
                                sig_cls = "badge-cyan"
                            elif eng["dn_hold_ticks"] < 3:
                                sig_text = f"⏳ Testing Lower Breakdown (Hold: {eng['dn_hold_ticks']}/3)"
                                sig_cls = "badge-yellow"
                            elif eng["bear_conviction"] >= 70:
                                hc = "★ High Conviction " if eng["bear_conviction"] >= 82 else ""
                                sig_text = f"{hc}True Breakdown (SHORT) [{eng['bear_conviction']}%]"
                                sig_cls = "badge-red"
                                eng["lock_state"] = "SHORT"
                                eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh
                                eng["lock_box_low"] = bl
                                new_master_sig = "SELL"
                                master_reason = f"📦 पक्का BBNT ब्रेकडाउन (Conviction: {eng['bear_conviction']}%)"
                            else:
                                sig_text = f"⚠️ Weak Breakdown (Low Score: {eng['bear_conviction']}%)"
                                sig_cls = "badge-yellow"
                        else:
                            # If price poked out and came right back inside -> Sweep Trap!
                            if eng["up_hold_ticks"] in [1, 2] and eng["bear_conviction"] >= 65:
                                sig_text = "🚨 Upper Sweep Trap! (Bearish Reversal)"
                                sig_cls = "badge-red"
                            elif eng["dn_hold_ticks"] in [1, 2] and eng["bull_conviction"] >= 65:
                                sig_text = "🚨 Lower Sweep Trap! (Bullish Reversal)"
                                sig_cls = "badge-green"
                            eng["up_hold_ticks"] = 0
                            eng["dn_hold_ticks"] = 0

                    eng["current_sig_text"] = sig_text
                    eng["current_sig_cls"] = sig_cls
                    eng["locked_pts"] = locked_pts

                    row_obj = {
                        "time": ist_min, "px": px, "bh": bh, "bl": bl,
                        "bt": buy_track, "st": sell_track,
                        "tape": f"{eng['smooth_taker']:.0f}% Buy",
                        "pts": locked_pts, "sig": sig_text, "cls": sig_cls
                    }
                    if not eng["live_table"] or eng["live_table"][0]["time"] != ist_min:
                        eng["live_table"].insert(0, row_obj)
                        eng["live_table"] = eng["live_table"][:35]
                    else:
                        eng["live_table"][0] = row_obj

                # ================================================================
                # 4. 1-MINUTE V-SHAPE REVERSAL ENGINE (WITH TAKER TAPE & OI TRAP)
                # ================================================================
                if eng["h10"] > 0:
                    drop_10m = eng["h10"] - px
                    rally_10m = px - eng["l10"]
                    v_dir = "कोई साफ सेटअप नहीं"
                    v_prob = "बहुत कम"
                    v_score = 0
                    v_reasons = []
                    v_danger = "मार्केट अभी सामान्य रेंज में है (150+ पॉइंट्स का तेज़ स्ट्रेच नहीं है)।"
                    v_action = "प्राइस रिजेक्शन और एग्जॉशन की पुष्टि का इंतजार करें — अभी कोई ट्रेड नहीं"

                    if drop_10m >= 150.0:
                        v_dir = "बुलिश V-शेप"
                        l2_min = min(eng["buy_pct_history"]) if eng["buy_pct_history"] else w_ob_pct
                        if l2_min <= 32.0:
                            v_score += 2; v_reasons.append(f"चरम सेलिंग प्रेशर पहुंचा (Min L2 Buy: {l2_min:.0f}%)")
                        elif l2_min <= 38.0:
                            v_score += 1; v_reasons.append(f"तेज़ सेलिंग प्रेशर (Min L2 Buy: {l2_min:.0f}%)")

                        if eng["oi_change_5m"] > 0 or buy_track > sell_track:
                            v_score += 2; v_reasons.append(f"लेट शॉर्ट्स ट्रैप (ΔOI: {eng['oi_change_5m']:+.1f} BTC | PE सपोर्ट)")

                        if eng["smooth_taker"] >= 53.0 and l1_pct >= 50.0:
                            v_score += 2; v_reasons.append(f"सेलिंग एग्जॉशन (Taker Tape: {eng['smooth_taker']:.0f}% बाइंग पर पलटा)")

                        bounce = px - eng["l10"]
                        if bounce >= 38.0:
                            v_score += 2; v_reasons.append(f"स्विंग लो से मजबूत बाउंस (+{bounce:.1f} Pts रिकवरी)")
                        else:
                            v_danger = f"लो से अभी सिर्फ +{bounce:.1f} Pts का बाउंस है। गिरती छुरी में हाथ न डालें!"

                        if eng["basis"] >= -8.0 and eng["rvol"] >= 1.1:
                            v_score += 2; v_reasons.append(f"वॉल्यूम और बेसिस सुधार (RVOL: {eng['rvol']:.1f}x)")

                    elif rally_10m >= 150.0:
                        v_dir = "बियरिश Inverted V-शेप"
                        l2_max = max(eng["buy_pct_history"]) if eng["buy_pct_history"] else w_ob_pct
                        if l2_max >= 68.0:
                            v_score += 2; v_reasons.append(f"चरम बाइंग प्रेशर पहुंचा (Max L2 Buy: {l2_max:.0f}%)")
                        elif l2_max >= 62.0:
                            v_score += 1; v_reasons.append(f"तेज़ बाइंग प्रेशर (Max L2 Buy: {l2_max:.0f}%)")

                        if eng["oi_change_5m"] > 0 or sell_track > buy_track:
                            v_score += 2; v_reasons.append(f"लेट लॉन्ग्स ट्रैप (ΔOI: {eng['oi_change_5m']:+.1f} BTC | CE रेजिस्टेंस)")

                        if eng["smooth_taker"] <= 47.0 and l1_pct <= 50.0:
                            v_score += 2; v_reasons.append(f"बाइंग एग्जॉशन (Taker Tape: {100-eng['smooth_taker']:.0f}% सेलिंग हावी)")

                        pullback = eng["h10"] - px
                        if pullback >= 38.0:
                            v_score += 2; v_reasons.append(f"स्विंग हाई से रिजेक्शन (-{pullback:.1f} Pts गिरावट)")
                        else:
                            v_danger = f"हाई से अभी सिर्फ -{pullback:.1f} Pts की गिरावट है। मोमेंटम अभी ऊपर जा सकता है!"

                        if eng["basis"] <= 8.0 and eng["rvol"] >= 1.1:
                            v_score += 2; v_reasons.append(f"वॉल्यूम और सप्लाई प्रेशर (RVOL: {eng['rvol']:.1f}x)")

                    # Hard Gating Rules
                    if v_dir != "कोई साफ सेटअप नहीं":
                        has_ex = any("एग्जॉशन" in r for r in v_reasons)
                        has_rej = any("बाउंस" in r or "रिजेक्शन" in r for r in v_reasons)
                        if not (has_ex and has_rej):
                            v_score = min(v_score, 4)

                        if v_score <= 2: v_prob = "बहुत कम"
                        elif v_score <= 4: v_prob = "कम (केवल प्रेशर है, रिजेक्शन नहीं)"
                        elif v_score <= 6: v_prob = "मध्यम (पुष्टि का इंतजार करें)"
                        elif v_score <= 8: v_prob = "अच्छी"
                        else: v_prob = "बहुत अच्छी (हाई कन्विक्शन V-रिवर्सल)"

                        if v_score >= 7:
                            v_danger = "रीसेंट स्विंग लो/हाई टूटने पर ट्रैप फेल हो जाएगा (SL सख्त रखें)।"
                            if v_dir == "बुलिश V-शेप":
                                v_action = f"LONG (Buy) @ ${px:,.1f} | SL: ${eng['l10']-40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig and eng["bull_conviction"] >= 68:
                                    new_master_sig = "BUY"; master_reason = f"🚀 V-शेप रिवर्सल ({v_score}/10)"
                            else:
                                v_action = f"SHORT (Sell) @ ${px:,.1f} | SL: ${eng['h10']+40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig and eng["bear_conviction"] >= 68:
                                    new_master_sig = "SELL"; master_reason = f"🚀 Inverted V रिवर्सल ({v_score}/10)"

                    eng["v_engine"] = {
                        "dir": v_dir, "prob": v_prob, "score": v_score,
                        "reasons": v_reasons, "danger": v_danger, "action": v_action
                    }

                # ================================================================
                # 5. SMART TRAILING & MOMENTUM-DEATH GUARD (+100p FEE-PROOF LOCK)
                # ================================================================
                if new_master_sig and not eng["track_signal"]:
                    eng["track_signal"] = new_master_sig
                    eng["track_entry_px"] = px
                    eng["track_max_fav"] = px
                    eng["track_open_ts"] = now_ts
                    eng["track_status"] = "Tracking"
                    eng["active_trade_obj"] = {
                        "open_time": ist_full, "close_time": "", "type": new_master_sig,
                        "entry": px, "status": "Tracking", "max_pnl": 0.0,
                        "live_pnl": 0.0, "final_pnl": 0.0, "reason": master_reason
                    }

                if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
                    t_type = eng["track_signal"]
                    t_entry = eng["track_entry_px"]

                    if t_type == "BUY":
                        live_pnl = px - t_entry
                        eng["track_max_fav"] = max(eng["track_max_fav"], px)
                        max_pnl = eng["track_max_fav"] - t_entry
                        if max_pnl >= 600.0: trail_sl = eng["track_max_fav"] - 140.0
                        elif max_pnl >= 400.0: trail_sl = t_entry + 250.0
                        elif max_pnl >= 200.0: trail_sl = t_entry + 100.0
                        elif max_pnl >= 130.0: trail_sl = t_entry + 75.0 # Early Fee-Cover Shield
                        else: trail_sl = t_entry - 260.0

                        # Emergency Tape Reversal Exit if trade is in loss and bears hit 85+ conviction
                        tape_crash = (max_pnl < 90.0 and live_pnl < -120.0 and eng["bear_conviction"] >= 85)

                        if px <= trail_sl or tape_crash:
                            eng["track_status"] = "Closed"
                            if tape_crash:
                                sts = f"🛡️ स्मार्ट टेप रिवर्सल से बचाव ({live_pnl:+.0f}p)"
                            elif live_pnl < 0:
                                sts = f"🛑 स्टॉप-लॉस हिट ({live_pnl:+.0f}p)"
                            else:
                                sts = f"✅ फीस+प्रॉफिट लॉक (+{live_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"].update({"status": sts, "final_pnl": live_pnl, "close_time": ist_full})
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                            eng["active_trade_obj"] = None; eng["track_signal"] = None

                    elif t_type == "SELL":
                        live_pnl = t_entry - px
                        eng["track_max_fav"] = min(eng["track_max_fav"], px)
                        max_pnl = t_entry - eng["track_max_fav"]
                        if max_pnl >= 600.0: trail_sl = eng["track_max_fav"] + 140.0
                        elif max_pnl >= 400.0: trail_sl = t_entry - 250.0
                        elif max_pnl >= 200.0: trail_sl = t_entry - 100.0
                        elif max_pnl >= 130.0: trail_sl = t_entry - 75.0 # Early Fee-Cover Shield
                        else: trail_sl = t_entry + 260.0

                        tape_crash = (max_pnl < 90.0 and live_pnl < -120.0 and eng["bull_conviction"] >= 85)

                        if px >= trail_sl or tape_crash:
                            eng["track_status"] = "Closed"
                            if tape_crash:
                                sts = f"🛡️ स्मार्ट टेप रिवर्सल से बचाव ({live_pnl:+.0f}p)"
                            elif live_pnl < 0:
                                sts = f"🛑 स्टॉप-लॉस हिट ({live_pnl:+.0f}p)"
                            else:
                                sts = f"✅ फीस+प्रॉफिट लॉक (+{live_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
                            eng["active_trade_obj"].update({"status": sts, "final_pnl": live_pnl, "close_time": ist_full})
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                            eng["active_trade_obj"] = None; eng["track_signal"] = None

                    if eng["active_trade_obj"]:
                        eng["active_trade_obj"]["live_pnl"] = live_pnl
                        eng["active_trade_obj"]["max_pnl"] = max_pnl

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_master_engine_v5_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_px": 0.0,
        "w_ob_pct": 50.0, "smooth_ob": 50.0, "l1_pct": 50.0,
        "taker_pct": 50.0, "smooth_taker": 50.0, "net_tape_delta": 0.0,
        "buy_sz": 0.0, "sell_sz": 0.0, "last_update_ist": "--:--:--",
        "box_high": 0.0, "box_low": 0.0, "box_width": 0.0, "h10": 0.0, "l10": 0.0,
        "atr": 15.0, "rvol": 1.0, "last_eff": 0.5, "last_close": 0.0,
        "oi_history": [], "oi_change_5m": 0.0, "basis": 0.0, "funding": 0.0,
        "pe_base": 500.0, "ce_base": 500.0, "buy_track": 500.0, "sell_track": 500.0,
        "bull_conviction": 50, "bear_conviction": 50,
        "up_hold_ticks": 0, "dn_hold_ticks": 0,
        "htf_trend": "BULLISH", "last_kline_ts": 0.0, "buy_pct_history": [],
        "lock_state": "NONE", "lock_trigger_px": 0.0, "lock_box_high": 0.0, "lock_box_low": 0.0,
        "current_sig_text": "Neutral (Inside Box)", "current_sig_cls": "badge-gray", "locked_pts": 0.0,
        "live_table": [], "v_engine": {"dir": "कोई साफ सेटअप नहीं", "prob": "बहुत कम", "score": 0, "reasons": [], "danger": "-", "action": "-"},
        "active_trade_obj": None, "closed_trades_ledger": [], "track_signal": None,
        "track_entry_px": 0.0, "track_max_fav": 0.0, "track_open_ts": 0.0, "track_status": "Idle", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v5_0()

# ============================================================================
# RENDER V5.0 DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    tot_trades = len(eng["closed_trades_ledger"])
    wins = sum(1 for t in eng["closed_trades_ledger"] if t["final_pnl"] > 0)
    win_rate = (wins / tot_trades * 100.0) if tot_trades > 0 else 0.0

    # --- TOP HEADER BAR ---
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:20px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V5.0 (ANTI-SPOOF & TAPE ENGINE)</span>
        <span style='font-size:20px; font-weight:900; color:#f8fafc; margin-left:15px;'>BTC: ${eng['px']:,.1f}</span></div>
        <div>
            <span style='color:#c084fc; font-weight:bold; font-size:13.5px; margin-right:18px;'>📊 RVOL: {eng['rvol']:.2f}x | ΔOI (5m): {eng['oi_change_5m']:+.1f} BTC | Basis: {eng['basis']:+.1f}</span>
            <span style='color:#facc15; font-weight:bold; margin-right:18px;'>🏆 Win Rate: {win_rate:.1f}% ({wins}/{tot_trades})</span>
            <span style='color:#4ade80; font-size:13px;'>● {eng['last_update_ist']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- ROW 1: 4 SMART SUMMARY CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        trig_info = f"Locked @ ${eng['lock_trigger_px']:,.1f} ({eng['locked_pts']:+.1f} Pts)" if eng["lock_state"] != "NONE" else f"Quant Gate: Bull {eng['bull_conviction']}% | Bear {eng['bear_conviction']}%"
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>1. Market State & Conviction Gate</div>
            <div><span class='badge {eng["current_sig_cls"]}' style='font-size:13px;'>{eng["current_sig_text"]}</span></div>
            <div style='font-size:12px; color:#cbd5e1; font-weight:bold;'>{trig_info}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>2. 15-Min Box & Anti-Wick Filter</div>
            <div style='font-size:14px; font-weight:bold;'><span style='color:#ef4444;'>H: ${eng['box_high']:,.1f}</span> &nbsp;|&nbsp; <span style='color:#22c55e;'>L: ${eng['box_low']:,.1f}</span></div>
            <div style='font-size:12px; color:#facc15;'>Width: {eng['box_width']:,.1f}p | 1m ATR: {eng['atr']:.1f}p</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        bt, st_val = eng["buy_track"], eng["sell_track"]
        tot_t = bt + st_val if (bt + st_val) > 0 else 1.0
        bt_pct = (bt / tot_t) * 100.0
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>3. Smoothed Dual-Track Score (5m)</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>Buy Track: {bt:,.0f}</span>
                <span style='color:#ef4444;'>Sell Track: {st_val:,.0f}</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{bt_pct:.1f}%;'></div><div class='bar-sell' style='width:{100-bt_pct:.1f}%;'></div></div>
        </div>""", unsafe_allow_html=True)

    with c4:
        tk_p = eng["smooth_taker"]
        ob_p = eng["smooth_ob"]
        spoof_warn = "⚠️ Spoof Divergence!" if abs(tk_p - ob_p) > 18.0 else f"Weighted L2: {ob_p:.0f}% Buy"
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>4. Real Taker Tape vs Weighted L2</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>Taker Buy: {tk_p:.1f}%</span>
                <span style='color:#ef4444;'>Taker Sell: {100-tk_p:.1f}%</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{tk_p:.1f}%;'></div><div class='bar-sell' style='width:{100-tk_p:.1f}%;'></div></div>
            <div style='font-size:11.5px; color:#38bdf8; font-weight:bold;'>{spoof_warn}</div>
        </div>""", unsafe_allow_html=True)

    # --- ROW 2: TRADE TRACKER (LEFT) & V-SHAPE ANALYZER (RIGHT) ---
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    m_left, m_right = st.columns([0.52, 0.48])

    with m_left:
        if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
            tr = eng["active_trade_obj"]
            t_col = "#22c55e" if tr["type"] == "BUY" else "#ef4444"
            p_col = "#4ade80" if tr["live_pnl"] >= 0 else "#f87171"
            mx = tr["max_pnl"]
            if mx >= 400: sl_txt = "🔒 +250p सुपर प्रॉफिट लॉक!"
            elif mx >= 200: sl_txt = "🛡️ +100p प्रॉफिट लॉक!"
            elif mx >= 130: sl_txt = "🛡️ +75p फीस-कवर शील्ड लॉक!"
            else: sl_txt = "⚠️ शुरुआती SL: -260p (+130p जाते ही ₹70 फीस सेफ होगी)"

            active_html = f"""<div style='background:#1e293b; border:2px solid {t_col}; padding:12px; border-radius:8px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;'>
                <div><div style='font-size:12px; color:#94a3b8;'>🎯 ACTIVE MASTER TRADE ({tr['reason']})</div>
                <div style='font-size:20px; font-weight:900; color:#fff;'>{tr['type']} @ ${tr['entry']:,.1f}</div>
                <div style='font-size:12px; color:#facc15; margin-top:3px;'>{sl_txt}</div></div>
                <div style='text-align:right;'><div style='font-size:26px; font-weight:900; color:{p_col};'>{tr['live_pnl']:+.1f}p</div>
                <div style='font-size:12px; color:#38bdf8;'>Peak: +{mx:,.1f}p</div></div>
            </div>"""
        else:
            active_html = f"""<div style='background:#1e293b; border:1px dashed #475569; padding:14px; border-radius:8px; margin-bottom:12px; text-align:center; color:#94a3b8; font-weight:bold;'>
                ⏳ हाई-कन्विक्शन सिग्नल की प्रतीक्षा (3-Tick Anti-Wick + Taker Tape Confirmation)...
            </div>"""

        ledger_html = ""
        for h in eng["closed_trades_ledger"]:
            cls = "hist-win" if h["final_pnl"] > 0 else "hist-loss"
            p_c = "#4ade80" if h["final_pnl"] > 0 else "#f87171"
            ledger_html += f"""<div class='hist-item {cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div><b>{h['open_time']} - {h['type']} @ ${h['entry']:,.1f}</b> <span style='color:#38bdf8; font-size:11px;'>[{h['reason']}]</span><br>
                <span style='font-size:11.5px; color:#94a3b8;'>{h['status']} (बंद: {h['close_time']})</span></div>
                <div style='font-size:16px; font-weight:900; color:{p_c};'>{h['final_pnl']:+.1f}p</div>
            </div>"""
        if not ledger_html:
            ledger_html = "<div style='color:#64748b; text-align:center; padding-top:65px;'>अभी कोई ट्रेड बंद नहीं हुआ है</div>"

        st.markdown(f"<div class='panel-box'><div style='font-size:14px; font-weight:bold; color:#facc15; margin-bottom:8px;'>🎯 स्मार्ट ट्रेड ट्रैकर (+75p/+100p फीस-प्रूफ लॉक)</div>{active_html}{ledger_html}</div>", unsafe_allow_html=True)

    with m_right:
        v = eng["v_engine"]
        sc_col = "#22c55e" if v["score"] >= 7 else ("#facc15" if v["score"] >= 5 else "#ef4444")
        r_li = "".join([f"<li>{r}</li>" for r in v["reasons"]]) if v["reasons"] else "<li>पिछले 10 मिनट में 150+ पॉइंट्स का एकतरफा मूव नहीं है</li>"
        st.markdown(f"""<div class='vshape-box'>
            <div style='font-size:15px; font-weight:bold; color:#38bdf8; border-bottom:1px solid #334155; padding-bottom:6px; margin-bottom:8px;'>
                🔬 1-Minute V-Shape Microstructure Analyzer
            </div>
            <div style='font-size:13.5px; line-height:1.6;'>
                <b>दिशा:</b> <span style='color:#f8fafc;'>{v['dir']}</span> &nbsp;|&nbsp;
                <b>संभावना:</b> <span style='color:{sc_col}; font-weight:bold;'>{v['prob']}</span> &nbsp;|&nbsp;
                <b>कन्फिडेंस:</b> <span style='color:{sc_col}; font-size:16px; font-weight:900;'>{v['score']}/10</span>
            </div>
            <div style='font-size:13px; margin-top:8px;'><b>मुख्य कारण:</b><ul style='margin:4px 0 8px 18px; color:#cbd5e1; padding:0;'>{r_li}</ul></div>
            <div style='font-size:12.5px; padding:8px; background:#7f1d1d30; border-left:3px solid #ef4444; border-radius:4px; margin-bottom:8px;'>
                <b>मुख्य खतरा:</b> <span style='color:#fca5a5;'>{v['danger']}</span>
            </div>
            <div style='font-size:12.5px; padding:8px; background:#064e3b30; border-left:3px solid #22c55e; border-radius:4px;'>
                <b>एक्शन आइडिया:</b> <span style='color:#86efac;'>{v['action']}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # --- ROW 3: UNIFIED BBNT LIVE SIGNAL TABLE ---
    st.markdown("<div style='font-size:15px; font-weight:bold; color:#38bdf8; margin-top:16px;'>📊 BBNT + Taker Tape Live 1-Minute Signal Table</div>", unsafe_allow_html=True)

    rows_str = ""
    for r in eng["live_table"]:
        pts_txt = f"{r['pts']:+.1f} Pts" if r["pts"] != 0 else "-"
        rows_str += f"<tr><td><b>{r['time']}</b></td><td>${r['px']:,.1f}</td><td>${r['bh']:,.1f}</td><td>${r['bl']:,.1f}</td><td style='color:#22c55e; font-weight:bold;'>{r['bt']:,.0f}</td><td style='color:#ef4444; font-weight:bold;'>{r['st']:,.0f}</td><td style='color:#38bdf8;'>{r['tape']}</td><td>{pts_txt}</td><td><span class='badge {r['cls']}'>{r['sig']}</span></td></tr>"

    if not rows_str:
        rows_str = "<tr><td colspan='9' style='text-align:center; color:#94a3b8;'>डेटा लोड हो रहा है...</td></tr>"

    full_table_html = f"""<div class='table-wrapper'>
        <table class='custom-table'>
            <thead><tr><th>Time (IST)</th><th>Future Price</th><th>Box High (15m)</th><th>Box Low (15m)</th><th>Buy Track</th><th>Sell Track</th><th>Taker Tape</th><th>Move / Points</th><th>Final Signal</th></tr></thead>
            <tbody>{rows_str}</tbody>
        </table>
    </div>"""
    st.markdown(full_table_html, unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V5.0 Smart Microstructure Engine स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

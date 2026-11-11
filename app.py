import streamlit as st
import requests
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V6.0 - S/R Zone & 1m-5m Buffer Engine", layout="wide")

# ============================================================================
# CLEAN INSTITUTIONAL UI STYLING
# ============================================================================
st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.top-header { background: #1e293b; border: 1px solid #334155; padding: 12px 18px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 12px 14px; border-radius: 10px; text-align: center; height: 138px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.card-title { font-size: 11.5px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.panel-box { background: #0f172a; border: 1px solid #334155; padding: 15px; border-radius: 10px; height: 420px; overflow-y: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.vshape-box { background: #0f172a; border: 1px solid #38bdf8; border-left: 5px solid #38bdf8; padding: 15px; border-radius: 10px; height: 420px; overflow-y: auto; }
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
# DATA FETCHERS (WEIGHTED L2 + TAKER TAPE + OI + MAJOR S/R ZONES)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def fetch_microstructure_snapshot():
    """Fetches Distance-Weighted L2 Orderbook & Executed Taker Trades"""
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

        # Distance-Weighted L2 Volumes (Anti-Spoofing)
        weights = [1.0]*5 + [0.5]*5 + [0.2]*10
        w_bid = sum(float(b["sz"]) * weights[i] for i, b in enumerate(bids))
        w_ask = sum(float(a["sz"]) * weights[i] for i, a in enumerate(asks))

        near_bid = sum(float(b["sz"]) for b in bids[:3])
        near_ask = sum(float(a["sz"]) for a in asks[:3])
        l1_pct = (near_bid / (near_bid + near_ask) * 100.0) if (near_bid + near_ask) > 0 else 50.0

        # Real Executed Taker Trades
        taker_buy = 0.0
        taker_sell = 0.0
        try:
            r_tr = requests.post(HYPERLIQUID_URL, json={"type": "recentTrades", "coin": "BTC"}, timeout=2.0)
            if r_tr.status_code == 200:
                trades = r_tr.json()
                if isinstance(trades, list):
                    for t in trades[:45]:
                        sz = float(t.get("sz", 0.0))
                        if t.get("side") == "B":
                            taker_buy += sz
                        else:
                            taker_sell += sz
        except:
            pass

        if (taker_buy + taker_sell) == 0:
            taker_buy, taker_sell = w_bid * 0.2, w_ask * 0.2

        return {
            "px": mid_px,
            "w_bid": w_bid,
            "w_ask": w_ask,
            "l1_pct": l1_pct,
            "taker_buy": taker_buy,
            "taker_sell": taker_sell
        }
    except Exception as e:
        return str(e)

def fetch_real_oi_and_basis():
    """Fetches Real Open Interest and Spot-Mark Basis"""
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
                        return {"oi": oi, "basis": mark_px - oracle_px}
    except:
        pass
    return None

def fetch_sr_zones_and_klines():
    """Calculates Major 60m S/R Zones, 15m Box, VWAP, and ATR"""
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (90 * 60 * 1000) # 90 minutes history
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 30:
                closed = data[:-1]
                df = pd.DataFrame(closed)
                df.rename(columns={'o':'Open', 'h':'High', 'l':'Low', 'c':'Close', 'v':'Volume'}, inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)

                df['Range'] = (df['High'] - df['Low']).clip(lower=1.0)
                atr_14 = float(df['Range'].tail(14).mean())

                # RVOL (5m average volume vs 30m average volume)
                avg_vol_30 = max(0.1, float(df['Volume'].tail(30).mean()))
                vol_5m = float(df['Volume'].tail(5).mean())
                rvol = vol_5m / avg_vol_30

                # 1. Major 60-Min Support & Resistance Zones
                last_60 = df.tail(60)
                major_res = float(last_60['High'].max())
                major_sup = float(last_60['Low'].min())

                # 2. Session VWAP (60-Min Rolling Institutional Anchor)
                typical_px = (last_60['High'] + last_60['Low'] + last_60['Close']) / 3.0
                vwap = float((typical_px * last_60['Volume']).sum() / max(0.1, last_60['Volume'].sum()))

                # 3. 15-Min Volatility Box (Shifted by 1)
                last_15 = df.tail(15)
                raw_bh = float(last_15['High'].max())
                raw_bl = float(last_15['Low'].min())
                raw_bw = raw_bh - raw_bl
                noise_buf = max(12.0, atr_14 * 0.45) if raw_bw < 45.0 else 0.0
                bh = raw_bh + noise_buf
                bl = raw_bl - noise_buf

                # 10-Min High/Low for V-Shape
                last_10 = df.tail(10)
                h10 = float(last_10['High'].max())
                l10 = float(last_10['Low'].min())

                # 5-Min Candle Structural Flow
                last_5 = df.tail(5)
                bull_flow = 0.0
                bear_flow = 0.0
                for _, row in last_5.iterrows():
                    rng = row['Range']
                    vol_m = row['Volume'] + (avg_vol_30 * 0.5)
                    bull_flow += ((row['Close'] - row['Low']) / rng) * vol_m * 100.0
                    bear_flow += ((row['High'] - row['Close']) / rng) * vol_m * 100.0

                return {
                    "major_res": major_res, "major_sup": major_sup, "vwap": vwap,
                    "bh": bh, "bl": bl, "bw": bh - bl,
                    "h10": h10, "l10": l10, "atr": atr_14, "rvol": rvol,
                    "pe_base": bull_flow / 5.0, "ce_base": bear_flow / 5.0
                }
    except Exception as e:
        return str(e)
    return None

# ============================================================================
# 24x7 BACKGROUND WORKER (V6.0 S/R ZONE + 1M/5M BUFFER ENGINE)
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

            snap = fetch_microstructure_snapshot()
            if isinstance(snap, str):
                eng["last_err"] = snap
            elif snap:
                px = snap["px"]
                eng["px"] = px
                eng["l1_pct"] = snap["l1_pct"]
                eng["last_update_ist"] = ist_full

                # ================================================================
                # 1. SAVE DATA INTO 1-MINUTE & 5-MINUTE ROLLING MEMORY VAULT
                # ================================================================
                eng["data_vault"].append({
                    "ts": now_ts,
                    "px": px,
                    "w_bid": snap["w_bid"],
                    "w_ask": snap["w_ask"],
                    "t_buy": snap["taker_buy"],
                    "t_sell": snap["taker_sell"],
                    "l1_pct": snap["l1_pct"]
                })
                # Keep last 5 minutes (300 seconds) of snapshots in memory
                eng["data_vault"] = [d for d in eng["data_vault"] if (now_ts - d["ts"]) <= 300.0]

                vault_1m = [d for d in eng["data_vault"] if (now_ts - d["ts"]) <= 60.0]
                vault_5m = eng["data_vault"]

                # Calculate 1-Minute Buffered Metrics (Saved over last 60s)
                bid_1m = sum(d["w_bid"] for d in vault_1m)
                ask_1m = sum(d["w_ask"] for d in vault_1m)
                tbuy_1m = sum(d["t_buy"] for d in vault_1m)
                tsell_1m = sum(d["t_sell"] for d in vault_1m)

                ob_1m_pct = (bid_1m / (bid_1m + ask_1m) * 100.0) if (bid_1m + ask_1m) > 0 else 50.0
                tape_1m_pct = (tbuy_1m / (tbuy_1m + tsell_1m) * 100.0) if (tbuy_1m + tsell_1m) > 0 else 50.0
                avg_px_1m = sum(d["px"] for d in vault_1m) / max(1, len(vault_1m))
                px_chg_1m = px - vault_1m[0]["px"] if len(vault_1m) > 1 else 0.0

                # Calculate 5-Minute Buffered Metrics (Saved over last 300s)
                bid_5m = sum(d["w_bid"] for d in vault_5m)
                ask_5m = sum(d["w_ask"] for d in vault_5m)
                tbuy_5m = sum(d["t_buy"] for d in vault_5m)
                tsell_5m = sum(d["t_sell"] for d in vault_5m)

                ob_5m_pct = (bid_5m / (bid_5m + ask_5m) * 100.0) if (bid_5m + ask_5m) > 0 else 50.0
                tape_5m_pct = (tbuy_5m / (tbuy_5m + tsell_5m) * 100.0) if (tbuy_5m + tsell_5m) > 0 else 50.0

                #Combined 1m & 5m Strength Scores (0 to 100%)
                eng["ob_1m_pct"] = ob_1m_pct
                eng["tape_1m_pct"] = tape_1m_pct
                eng["ob_5m_pct"] = ob_5m_pct
                eng["tape_5m_pct"] = tape_5m_pct

                eng["bull_1m_score"] = (tape_1m_pct * 0.60) + (ob_1m_pct * 0.40)
                eng["bull_5m_score"] = (tape_5m_pct * 0.60) + (ob_5m_pct * 0.40)
                eng["bear_1m_score"] = 100.0 - eng["bull_1m_score"]
                eng["bear_5m_score"] = 100.0 - eng["bull_5m_score"]

                # Buffer Readiness Status (Requires at least 45 seconds of saved data before firing trades)
                vault_age_sec = int(now_ts - vault_5m[0]["ts"]) if len(vault_5m) > 1 else 0
                eng["vault_age_sec"] = vault_age_sec
                buffer_ready = (vault_age_sec >= 45)

                # Fetch Major S/R Zones & OI every 12 seconds
                if now_ts - eng["last_kline_ts"] > 12 or eng["box_high"] == 0.0:
                    kdata = fetch_sr_zones_and_klines()
                    if isinstance(kdata, str):
                        eng["last_err"] = kdata
                    elif kdata:
                        eng["major_res"] = kdata["major_res"]
                        eng["major_sup"] = kdata["major_sup"]
                        eng["vwap"] = kdata["vwap"]
                        eng["box_high"] = kdata["bh"]
                        eng["box_low"] = kdata["bl"]
                        eng["box_width"] = kdata["bw"]
                        eng["h10"] = kdata["h10"]
                        eng["l10"] = kdata["l10"]
                        eng["atr"] = kdata["atr"]
                        eng["rvol"] = kdata["rvol"]
                        eng["pe_base"] = kdata["pe_base"]
                        eng["ce_base"] = kdata["ce_base"]

                    oi_data = fetch_real_oi_and_basis()
                    if oi_data:
                        curr_oi = oi_data["oi"]
                        eng["oi_history"].append(curr_oi)
                        if len(eng["oi_history"]) > 25:
                            eng["oi_history"].pop(0)
                        eng["oi_change_5m"] = curr_oi - eng["oi_history"][0]
                        eng["basis"] = oi_data["basis"]

                    eng["last_kline_ts"] = now_ts

                # Dual-Track 5m Score (Smoothed with 5m Buffer)
                eng["buy_track"] = eng["pe_base"] * (eng["bull_5m_score"] / 50.0)
                eng["sell_track"] = eng["ce_base"] * (eng["bear_5m_score"] / 50.0)
                buy_track, sell_track = eng["buy_track"], eng["sell_track"]

                # ================================================================
                # 2. SUPPORT & RESISTANCE LOCATION DETECTOR (NO-MAN'S LAND FILTER)
                # ================================================================
                bh, bl = eng["box_high"], eng["box_low"]
                m_res, m_sup = eng["major_res"], eng["major_sup"]
                zone_radius = max(45.0, eng["atr"] * 1.5) # Proximity radius around S/R

                dist_to_sup = min(abs(px - bl), abs(px - m_sup))
                dist_to_res = min(abs(px - bh), abs(px - m_res))

                at_support_zone = (dist_to_sup <= zone_radius) or (px < bl)
                at_resistance_zone = (dist_to_res <= zone_radius) or (px > bh)

                if px < bl:
                    eng["sr_status"] = "🟢 15m सपोर्ट के नीचे (Breakdown / Spring टेस्ट)"
                elif px > bh:
                    eng["sr_status"] = "🔴 15m रेजिस्टेंस के ऊपर (Breakout / Trap टेस्ट)"
                elif at_support_zone and dist_to_sup <= dist_to_res:
                    eng["sr_status"] = f"🟢 प्रमुख सपोर्ट ज़ोन के पास (दूरी: {dist_to_sup:.0f}p)"
                elif at_resistance_zone:
                    eng["sr_status"] = f"🔴 प्रमुख रेजिस्टेंस ज़ोन के पास (दूरी: {dist_to_res:.0f}p)"
                else:
                    eng["sr_status"] = "🚫 नो-ट्रेड ज़ोन (सपोर्ट और रेजिस्टेंस से दूर बीच बाज़ार में)"

                # ================================================================
                # 3. BUFFERED BBNT & S/R SIGNAL ENGINE (REQUIRES S/R + 1M & 5M DATA)
                # ================================================================
                sig_text = "Neutral (No-Trade Zone)"
                sig_cls = "badge-gray"
                locked_pts = 0.0
                new_master_sig = None
                master_reason = ""

                if bh > 0 and bl > 0:
                    # Manage Active Trend Lock
                    if eng["lock_state"] == "LONG":
                        locked_pts = px - eng["lock_trigger_px"]
                        if avg_px_1m < (eng["lock_box_level"] - 20.0) or (eng["bear_1m_score"] >= 62.0 and eng["bear_5m_score"] >= 56.0):
                            eng["lock_state"] = "NONE"
                        else:
                            sig_text = f"Riding LONG ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-green"

                    elif eng["lock_state"] == "SHORT":
                        locked_pts = eng["lock_trigger_px"] - px
                        if avg_px_1m > (eng["lock_box_level"] + 20.0) or (eng["bull_1m_score"] >= 62.0 and eng["bull_5m_score"] >= 56.0):
                            eng["lock_state"] = "NONE"
                        else:
                            sig_text = f"Riding SHORT ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-red"

                    # Generate New Signal ONLY if Buffer is Ready AND Price is at Support/Resistance
                    if eng["lock_state"] == "NONE":
                        if not buffer_ready:
                            sig_text = f"⏳ डेटा सहेजा जा रहा है ({vault_age_sec}/45s मेमोरी)..."
                            sig_cls = "badge-cyan"

                        elif not (at_support_zone or at_resistance_zone):
                            sig_text = "🚫 बीच बाज़ार (S/R लेवल पर आने का इंतज़ार करें)"
                            sig_cls = "badge-gray"

                        # CASE A: Price Breaking Above Resistance (Requires 1m Average Price > Box High)
                        elif px > bh:
                            if avg_px_1m > bh and eng["bull_1m_score"] >= 56.0 and eng["bull_5m_score"] >= 53.0 and buy_track > sell_track * 1.12:
                                sig_text = f"★ पक्का रेजिस्टेंस ब्रेकआउट (LONG) [1m:{eng['bull_1m_score']:.0f}%]"
                                sig_cls = "badge-green"
                                eng["lock_state"] = "LONG"; eng["lock_trigger_px"] = px; eng["lock_box_level"] = bh
                                new_master_sig = "BUY"; master_reason = "📦 S/R ब्रेकआउट + 1m/5m डेटा कन्फर्म"
                            elif eng["bear_1m_score"] >= 55.0:
                                sig_text = "🪤 रेजिस्टेंस ट्रैप / फेक ब्रेकआउट (सेलर्स हावी)"
                                sig_cls = "badge-yellow"
                            else:
                                sig_text = "⏳ रेजिस्टेंस ब्रेकआउट की 1m पुष्टि जारी..."
                                sig_cls = "badge-cyan"

                        # CASE B: Price Breaking Below Support (Requires 1m Average Price < Box Low)
                        elif px < bl:
                            if avg_px_1m < bl and eng["bear_1m_score"] >= 56.0 and eng["bear_5m_score"] >= 53.0 and sell_track > buy_track * 1.12:
                                sig_text = f"★ पक्का सपोर्ट ब्रेकडाउन (SHORT) [1m:{eng['bear_1m_score']:.0f}%]"
                                sig_cls = "badge-red"
                                eng["lock_state"] = "SHORT"; eng["lock_trigger_px"] = px; eng["lock_box_level"] = bl
                                new_master_sig = "SELL"; master_reason = "📦 S/R ब्रेकडाउन + 1m/5m डेटा कन्फर्म"
                            elif eng["bull_1m_score"] >= 55.0:
                                sig_text = "🪤 सपोर्ट स्प्रिंग ट्रैप (नीचे व्हेल बाइंग)"
                                sig_cls = "badge-cyan"
                            else:
                                sig_text = "⏳ सपोर्ट ब्रेकडाउन की 1m पुष्टि जारी..."
                                sig_cls = "badge-yellow"

                        # CASE C: Bounce From Support Zone (High-Reward Reversal at Support)
                        elif at_support_zone and dist_to_sup <= dist_to_res:
                            if eng["bull_1m_score"] >= 58.0 and eng["bull_5m_score"] >= 54.0 and px_chg_1m >= 12.0:
                                sig_text = f"★ मजबूत सपोर्ट बाउंस (LONG) [1m:{eng['bull_1m_score']:.0f}%]"
                                sig_cls = "badge-green"
                                eng["lock_state"] = "LONG"; eng["lock_trigger_px"] = px; eng["lock_box_level"] = bl
                                new_master_sig = "BUY"; master_reason = "🛡️ मेजर सपोर्ट बाउंस (1m+5m बाइंग)"
                            else:
                                sig_text = "👀 सपोर्ट ज़ोन पर 1m/5m बाइंग की जांच जारी..."
                                sig_cls = "badge-cyan"

                        # CASE D: Rejection From Resistance Zone (High-Reward Reversal at Resistance)
                        elif at_resistance_zone:
                            if eng["bear_1m_score"] >= 58.0 and eng["bear_5m_score"] >= 54.0 and px_chg_1m <= -12.0:
                                sig_text = f"★ मजबूत रेजिस्टेंस रिजेक्शन (SHORT) [1m:{eng['bear_1m_score']:.0f}%]"
                                sig_cls = "badge-red"
                                eng["lock_state"] = "SHORT"; eng["lock_trigger_px"] = px; eng["lock_box_level"] = bh
                                new_master_sig = "SELL"; master_reason = "🛡️ मेजर रेजिस्टेंस रिजेक्शन (1m+5m सेलिंग)"
                            else:
                                sig_text = "👀 रेजिस्टेंस ज़ोन पर 1m/5m सेलिंग की जांच जारी..."
                                sig_cls = "badge-yellow"

                    eng["current_sig_text"] = sig_text
                    eng["current_sig_cls"] = sig_cls
                    eng["locked_pts"] = locked_pts

                    row_obj = {
                        "time": ist_min, "px": px, "sr": eng["sr_status"][:22],
                        "b1m": f"{eng['bull_1m_score']:.0f}% B / {eng['bear_1m_score']:.0f}% S",
                        "b5m": f"{eng['bull_5m_score']:.0f}% B / {eng['bear_5m_score']:.0f}% S",
                        "bt": buy_track, "st": sell_track,
                        "pts": locked_pts, "sig": sig_text, "cls": sig_cls
                    }
                    if not eng["live_table"] or eng["live_table"][0]["time"] != ist_min:
                        eng["live_table"].insert(0, row_obj)
                        eng["live_table"] = eng["live_table"][:35]
                    else:
                        eng["live_table"][0] = row_obj

                # ================================================================
                # 4. S/R ANCHORED V-SHAPE ENGINE (USING 1M & 5M SAVED DATA)
                # ================================================================
                if eng["h10"] > 0:
                    drop_10m = eng["h10"] - px
                    rally_10m = px - eng["l10"]
                    v_dir = "कोई साफ सेटअप नहीं"
                    v_prob = "बहुत कम"
                    v_score = 0
                    v_reasons = []
                    v_danger = "प्राइस अभी किसी बड़े सपोर्ट/रेजिस्टेंस पर स्ट्रेच होकर नहीं पहुँचा है।"
                    v_action = "सपोर्ट/रेजिस्टेंस ज़ोन और 1m-5m डेटा कन्फर्मेशन का इंतजार करें"

                    if drop_10m >= 140.0 and at_support_zone:
                        v_dir = "बुलिश V-शेप (सपोर्ट ज़ोन पर)"
                        v_score += 2; v_reasons.append(f"प्रमुख सपोर्ट ज़ोन (${bl:,.0f} / ${m_sup:,.0f}) पर 140+ Pts की गिरावट के बाद टेस्ट")
                        if eng["bull_1m_score"] >= 56.0:
                            v_score += 2; v_reasons.append(f"1-मिनट सहेजे डेटा में बाइंग एग्जॉशन रिकवरी ({eng['bull_1m_score']:.0f}% Bull)")
                        if eng["bull_5m_score"] >= 52.0 or buy_track > sell_track:
                            v_score += 2; v_reasons.append(f"5-मिनट बफर में व्हेल अब्जॉर्प्शन ({eng['bull_5m_score']:.0f}% Bull)")
                        bounce = px - eng["l10"]
                        if bounce >= 35.0:
                            v_score += 2; v_reasons.append(f"सपोर्ट लो से +{bounce:.1f} Pts का मजबूत रिजेक्शन बाउंस")
                        else:
                            v_danger = f"सपोर्ट से बाउंस अभी सिर्फ +{bounce:.1f} Pts है, 1 मिनट क्लोज़ का इंतज़ार करें।"
                        if eng["oi_change_5m"] > 0 or eng["rvol"] >= 1.1:
                            v_score += 2; v_reasons.append(f"शॉर्ट ट्रैप और वॉल्यूम सपोर्ट (RVOL: {eng['rvol']:.1f}x)")

                    elif rally_10m >= 140.0 and at_resistance_zone:
                        v_dir = "बियरिश Inverted V (रेजिस्टेंस ज़ोन पर)"
                        v_score += 2; v_reasons.append(f"प्रमुख रेजिस्टेंस ज़ोन (${bh:,.0f} / ${m_res:,.0f}) पर 140+ Pts की चढ़ाई के बाद टेस्ट")
                        if eng["bear_1m_score"] >= 56.0:
                            v_score += 2; v_reasons.append(f"1-मिनट सहेजे डेटा में सेलिंग दबाव शुरू ({eng['bear_1m_score']:.0f}% Bear)")
                        if eng["bear_5m_score"] >= 52.0 or sell_track > buy_track:
                            v_score += 2; v_reasons.append(f"5-मिनट बफर में व्हेल बिकवाली ({eng['bear_5m_score']:.0f}% Bear)")
                        pullback = eng["h10"] - px
                        if pullback >= 35.0:
                            v_score += 2; v_reasons.append(f"रेजिस्टेंस हाई से -{pullback:.1f} Pts का रिजेक्शन")
                        else:
                            v_danger = f"रेजिस्टेंस से गिरावट अभी सिर्फ -{pullback:.1f} Pts है, जल्दबाजी न करें।"
                        if eng["oi_change_5m"] > 0 or eng["rvol"] >= 1.1:
                            v_score += 2; v_reasons.append(f"लॉन्ग ट्रैप और सप्लाई प्रेशर (RVOL: {eng['rvol']:.1f}x)")

                    if v_dir != "कोई साफ सेटअप नहीं":
                        has_1m = any("1-मिनट" in r for r in v_reasons)
                        has_rej = any("रिजेक्शन" in r for r in v_reasons)
                        if not (has_1m and has_rej):
                            v_score = min(v_score, 4)

                        if v_score <= 4: v_prob = "कम (1m डेटा या रिजेक्शन अधूरा है)"
                        elif v_score <= 6: v_prob = "मध्यम (डेटा बन रहा है)"
                        elif v_score <= 8: v_prob = "अच्छी (S/R + 1m/5m डेटा कन्फर्म)"
                        else: v_prob = "बहुत अच्छी (हाई कन्विक्शन V-रिवर्सल)"

                        if v_score >= 8 and buffer_ready:
                            v_danger = "सपोर्ट/रेजिस्टेंस के बाहर 40 पॉइंट्स का सख्त स्टॉप-लॉस रखें।"
                            if "बुलिश" in v_dir:
                                v_action = f"LONG (Buy) @ ${px:,.1f} | SL: ${eng['l10']-40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig:
                                    new_master_sig = "BUY"; master_reason = f"🚀 S/R बुलिश V-रिवर्सल ({v_score}/10)"
                            else:
                                v_action = f"SHORT (Sell) @ ${px:,.1f} | SL: ${eng['h10']+40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig:
                                    new_master_sig = "SELL"; master_reason = f"🚀 S/R Inverted V-रिवर्सल ({v_score}/10)"

                    eng["v_engine"] = {
                        "dir": v_dir, "prob": v_prob, "score": v_score,
                        "reasons": v_reasons, "danger": v_danger, "action": v_action
                    }

                # ================================================================
                # 5. SMART TRAILING TRACKER (+75p / +100p FEE-PROOF LOCK)
                # ================================================================
                if new_master_sig and not eng["track_signal"]:
                    eng["track_signal"] = new_master_sig
                    eng["track_entry_px"] = px
                    eng["track_max_fav"] = px
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
                        elif max_pnl >= 130.0: trail_sl = t_entry + 75.0
                        else: trail_sl = t_entry - 250.0

                        if px <= trail_sl:
                            eng["track_status"] = "Closed"
                            sts = f"🛑 स्टॉप-लॉस हिट ({live_pnl:+.0f}p)" if live_pnl < 0 else f"✅ फीस+प्रॉफिट लॉक (+{live_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
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
                        elif max_pnl >= 130.0: trail_sl = t_entry - 75.0
                        else: trail_sl = t_entry + 250.0

                        if px >= trail_sl:
                            eng["track_status"] = "Closed"
                            sts = f"🛑 स्टॉप-लॉस हिट ({live_pnl:+.0f}p)" if live_pnl < 0 else f"✅ फीस+प्रॉफिट लॉक (+{live_pnl:,.0f}p) [हाई: +{max_pnl:,.0f}p]"
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
def get_master_engine_v6_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "l1_pct": 50.0, "last_update_ist": "--:--:--",
        "data_vault": [], "vault_age_sec": 0,
        "ob_1m_pct": 50.0, "tape_1m_pct": 50.0, "ob_5m_pct": 50.0, "tape_5m_pct": 50.0,
        "bull_1m_score": 50.0, "bear_1m_score": 50.0, "bull_5m_score": 50.0, "bear_5m_score": 50.0,
        "major_res": 0.0, "major_sup": 0.0, "vwap": 0.0,
        "box_high": 0.0, "box_low": 0.0, "box_width": 0.0, "h10": 0.0, "l10": 0.0,
        "atr": 15.0, "rvol": 1.0, "oi_history": [], "oi_change_5m": 0.0, "basis": 0.0,
        "pe_base": 500.0, "ce_base": 500.0, "buy_track": 500.0, "sell_track": 500.0,
        "sr_status": "लेवल स्कैन हो रहा है...", "last_kline_ts": 0.0,
        "lock_state": "NONE", "lock_trigger_px": 0.0, "lock_box_level": 0.0,
        "current_sig_text": "Neutral", "current_sig_cls": "badge-gray", "locked_pts": 0.0,
        "live_table": [], "v_engine": {"dir": "कोई साफ सेटअप नहीं", "prob": "बहुत कम", "score": 0, "reasons": [], "danger": "-", "action": "-"},
        "active_trade_obj": None, "closed_trades_ledger": [], "track_signal": None,
        "track_entry_px": 0.0, "track_max_fav": 0.0, "track_status": "Idle", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v6_0()

# ============================================================================
# RENDER V6.0 DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    tot_trades = len(eng["closed_trades_ledger"])
    wins = sum(1 for t in eng["closed_trades_ledger"] if t["final_pnl"] > 0)
    win_rate = (wins / tot_trades * 100.0) if tot_trades > 0 else 0.0

    # --- TOP HEADER BAR ---
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:20px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V6.0 (S/R ZONE + 1M/5M BUFFER ENGINE)</span>
        <span style='font-size:20px; font-weight:900; color:#f8fafc; margin-left:15px;'>BTC: ${eng['px']:,.1f}</span></div>
        <div>
            <span style='color:#c084fc; font-weight:bold; font-size:13px; margin-right:15px;'>🗄️ मेमोरी बफर: {eng['vault_age_sec']}s / 300s | VWAP: ${eng['vwap']:,.1f}</span>
            <span style='color:#facc15; font-weight:bold; margin-right:15px;'>🏆 Win Rate: {win_rate:.1f}% ({wins}/{tot_trades})</span>
            <span style='color:#4ade80; font-size:13px;'>● {eng['last_update_ist']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- ROW 1: 4 SMART SUMMARY CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>1. S/R Location & Market State</div>
            <div><span class='badge {eng["current_sig_cls"]}' style='font-size:12.5px;'>{eng["current_sig_text"]}</span></div>
            <div style='font-size:11.5px; color:#facc15; font-weight:bold;'>{eng["sr_status"]}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>2. Major S/R Zones & 15m Box</div>
            <div style='font-size:12.5px; font-weight:bold; color:#ef4444;'>Major Res (60m): ${eng['major_res']:,.1f} | Box H: ${eng['box_high']:,.1f}</div>
            <div style='font-size:12.5px; font-weight:bold; color:#22c55e;'>Major Sup (60m): ${eng['major_sup']:,.1f} | Box L: ${eng['box_low']:,.1f}</div>
            <div style='font-size:11.5px; color:#94a3b8;'>Zone Radius: ±{max(45.0, eng['atr']*1.5):.0f} Pts</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        b1 = eng["bull_1m_score"]
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>3. 1-Min Saved Data Strength (60s)</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>1m Bull: {b1:.1f}%</span>
                <span style='color:#ef4444;'>1m Bear: {100-b1:.1f}%</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{b1:.1f}%;'></div><div class='bar-sell' style='width:{100-b1:.1f}%;'></div></div>
            <div style='font-size:11.5px; color:#cbd5e1;'>1m Tape: {eng['tape_1m_pct']:.0f}% | 1m L2: {eng['ob_1m_pct']:.0f}%</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        b5 = eng["bull_5m_score"]
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>4. 5-Min Saved Data Strength (300s)</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>5m Bull: {b5:.1f}%</span>
                <span style='color:#ef4444;'>5m Bear: {100-b5:.1f}%</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{b5:.1f}%;'></div><div class='bar-sell' style='width:{100-b5:.1f}%;'></div></div>
            <div style='font-size:11.5px; color:#38bdf8;'>5m Tape: {eng['tape_5m_pct']:.0f}% | 5m L2: {eng['ob_5m_pct']:.0f}%</div>
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
            else: sl_txt = "⚠️ शुरुआती SL: -250p (+130p जाते ही ₹70 फीस सेफ होगी)"

            active_html = f"""<div style='background:#1e293b; border:2px solid {t_col}; padding:12px; border-radius:8px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;'>
                <div><div style='font-size:12px; color:#94a3b8;'>🎯 ACTIVE S/R MASTER TRADE ({tr['reason']})</div>
                <div style='font-size:20px; font-weight:900; color:#fff;'>{tr['type']} @ ${tr['entry']:,.1f}</div>
                <div style='font-size:12px; color:#facc15; margin-top:3px;'>{sl_txt}</div></div>
                <div style='text-align:right;'><div style='font-size:26px; font-weight:900; color:{p_col};'>{tr['live_pnl']:+.1f}p</div>
                <div style='font-size:12px; color:#38bdf8;'>Peak: +{mx:,.1f}p</div></div>
            </div>"""
        else:
            active_html = f"""<div style='background:#1e293b; border:1px dashed #475569; padding:14px; border-radius:8px; margin-bottom:12px; text-align:center; color:#94a3b8; font-weight:bold;'>
                ⏳ कोई ट्रेड नहीं — प्राइस के सपोर्ट/रेजिस्टेंस पर आने और 1m+5m बफर कन्फर्मेशन का इंतज़ार...
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

        st.markdown(f"<div class='panel-box'><div style='font-size:14px; font-weight:bold; color:#facc15; margin-bottom:8px;'>🎯 S/R स्मार्ट ट्रेड ट्रैकर (+75p/+100p फीस-प्रूफ लॉक)</div>{active_html}{ledger_html}</div>", unsafe_allow_html=True)

    with m_right:
        v = eng["v_engine"]
        sc_col = "#22c55e" if v["score"] >= 7 else ("#facc15" if v["score"] >= 5 else "#ef4444")
        r_li = "".join([f"<li>{r}</li>" for r in v["reasons"]]) if v["reasons"] else "<li>प्राइस अभी किसी प्रमुख S/R ज़ोन पर 140+ पॉइंट्स के स्ट्रेच के साथ नहीं है</li>"
        st.markdown(f"""<div class='vshape-box'>
            <div style='font-size:15px; font-weight:bold; color:#38bdf8; border-bottom:1px solid #334155; padding-bottom:6px; margin-bottom:8px;'>
                🔬 S/R + 1m/5m Buffered V-Shape Analyzer
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

    # --- ROW 3: UNIFIED BBNT + 1M/5M BUFFER LIVE SIGNAL TABLE ---
    st.markdown("<div style='font-size:15px; font-weight:bold; color:#38bdf8; margin-top:16px;'>📊 S/R Zone + 1m/5m Saved Buffer Live Signal Table</div>", unsafe_allow_html=True)

    rows_str = ""
    for r in eng["live_table"]:
        pts_txt = f"{r['pts']:+.1f} Pts" if r["pts"] != 0 else "-"
        rows_str += f"<tr><td><b>{r['time']}</b></td><td>${r['px']:,.1f}</td><td>{r['sr']}</td><td style='color:#38bdf8; font-weight:bold;'>{r['b1m']}</td><td style='color:#c084fc; font-weight:bold;'>{r['b5m']}</td><td style='color:#22c55e;'>{r['bt']:,.0f}</td><td style='color:#ef4444;'>{r['st']:,.0f}</td><td>{pts_txt}</td><td><span class='badge {r['cls']}'>{r['sig']}</span></td></tr>"

    if not rows_str:
        rows_str = "<tr><td colspan='9' style='text-align:center; color:#94a3b8;'>डेटा बफर तैयार हो रहा है...</td></tr>"

    full_table_html = f"""<div class='table-wrapper'>
        <table class='custom-table'>
            <thead><tr><th>Time (IST)</th><th>Future Price</th><th>S/R Zone Status</th><th>1m Buffer Score</th><th>5m Buffer Score</th><th>Buy Track</th><th>Sell Track</th><th>Move / Points</th><th>Final Signal</th></tr></thead>
            <tbody>{rows_str}</tbody>
        </table>
    </div>"""
    st.markdown(full_table_html, unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V6.0 (S/R Zone & 1m-5m Data Buffer Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

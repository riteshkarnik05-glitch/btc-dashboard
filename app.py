import streamlit as st
import requests
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant - V4.1 Master Terminal", layout="wide")

# ============================================================================
# CLEAN & FIXED CSS LAYOUT (NO SCATTERING)
# ============================================================================
st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.top-header { background: #1e293b; border: 1px solid #334155; padding: 12px 18px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.metric-box { background: #1e293b; border: 1px solid #334155; padding: 14px; border-radius: 10px; text-align: center; height: 125px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.card-title { font-size: 12px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.panel-box { background: #0f172a; border: 1px solid #334155; padding: 16px; border-radius: 10px; height: 390px; overflow-y: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.vshape-box { background: #0f172a; border: 1px solid #38bdf8; border-left: 5px solid #38bdf8; padding: 16px; border-radius: 10px; height: 390px; overflow-y: auto; }
.bar-container { width: 100%; background: #ef4444; height: 10px; border-radius: 5px; overflow: hidden; display: flex; }
.bar-buy { background: #22c55e; height: 100%; transition: width 0.3s ease; }
.bar-sell { background: #ef4444; height: 100%; transition: width 0.3s ease; }
.badge { padding: 4px 9px; border-radius: 5px; font-size: 11.5px; font-weight: bold; display: inline-block; }
.badge-green { background-color: #064e3b; color: #4ade80; border: 1px solid #22c55e; }
.badge-red { background-color: #7f1d1d; color: #f87171; border: 1px solid #ef4444; }
.badge-yellow { background-color: #422006; color: #facc15; border: 1px solid #eab308; }
.badge-cyan { background-color: #083344; color: #22d3ee; border: 1px solid #06b6d4; }
.badge-gray { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; }
.table-wrapper { background: #0f172a; border-radius: 10px; border: 1px solid #334155; max-height: 360px; overflow-y: auto; margin-top: 10px; }
table.custom-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
table.custom-table th { color: #94a3b8; border-bottom: 1px solid #334155; padding: 10px 12px; background: #1e293b; position: sticky; top: 0; z-index: 10; }
table.custom-table td { padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #f8fafc; }
.hist-item { font-size: 13px; padding: 9px 12px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom: 6px; border-radius: 6px; background: #1e293b; }
.hist-win { border-left: 4px solid #22c55e; }
.hist-loss { border-left: 4px solid #ef4444; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# API FETCHERS (L2 ORDERBOOK, L1 TICKER & 1M KLINES)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def fetch_l2_and_l1():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data and "levels" in data and len(data["levels"]) >= 2:
                bids = data["levels"][0][:20]
                asks = data["levels"][1][:20]
                if len(bids) > 0 and len(asks) > 0:
                    buy_sz = sum(float(b["sz"]) for b in bids)
                    sell_sz = sum(float(a["sz"]) for a in asks)
                    tot_sz = buy_sz + sell_sz
                    best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
                    l1_bid_sz, l1_ask_sz = float(bids[0]["sz"]), float(asks[0]["sz"])
                    l1_pct = (l1_bid_sz / (l1_bid_sz + l1_ask_sz) * 100.0) if (l1_bid_sz + l1_ask_sz) > 0 else 50.0
                    return {
                        "mark_price": (best_bid + best_ask) / 2.0,
                        "spread": best_ask - best_bid,
                        "buy_sz": buy_sz,
                        "sell_sz": sell_sz,
                        "ob_pct": (buy_sz / tot_sz * 100.0) if tot_sz > 0 else 50.0,
                        "l1_pct": l1_pct
                    }
    except Exception as e:
        return str(e)
    return None

def fetch_klines_and_box():
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (60 * 60 * 1000)
        r = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 20:
                closed = data[:-1] # Shift(1): Exclude current forming minute
                df = pd.DataFrame(closed)
                df.rename(columns={'o':'Open', 'h':'High', 'l':'Low', 'c':'Close', 'v':'Volume'}, inplace=True)
                for c in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[c] = df[c].astype(float)

                # 15-Min Volatility Box (t-15 to t-1)
                last_15 = df.tail(15)
                raw_bh = float(last_15['High'].max())
                raw_bl = float(last_15['Low'].min())
                raw_bw = raw_bh - raw_bl

                # Choppiness Filter: Add +-15p buffer if Box Width < 40
                if raw_bw < 40.0:
                    bh = raw_bh + 15.0
                    bl = raw_bl - 15.0
                else:
                    bh = raw_bh
                    bl = raw_bl

                # 10-Min High/Low for V-Shape Engine
                last_10 = df.tail(10)
                h10 = float(last_10['High'].max())
                l10 = float(last_10['Low'].min())

                # 5-Min Smart Dual-Track Proxy (From Candle Volume + Imbalance)
                last_5 = df.tail(5)
                pe_sum = 0.0
                ce_sum = 0.0
                for _, row in last_5.iterrows():
                    rng = max(1.0, row['High'] - row['Low'])
                    bull_wt = ((row['Close'] - row['Low']) / rng) * (row['Volume'] + 10.0)
                    bear_wt = ((row['High'] - row['Close']) / rng) * (row['Volume'] + 10.0)
                    pe_sum += bull_wt * 120.0
                    ce_sum += bear_wt * 120.0

                htf_sma = float(df['Close'].mean())
                htf_trend = "BULLISH" if float(df['Close'].iloc[-1]) > htf_sma else "BEARISH"

                return {
                    "bh": bh, "bl": bl, "bw": bh - bl,
                    "h10": h10, "l10": l10,
                    "pe_base": pe_sum / 5.0, "ce_base": ce_sum / 5.0,
                    "htf_trend": htf_trend
                }
    except Exception as e:
        return str(e)
    return None

# ============================================================================
# 24x7 BACKGROUND WORKER (BBNT + V-SHAPE + SMART TRAILING)
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

            ob = fetch_l2_and_l1()
            if isinstance(ob, str):
                eng["last_err"] = ob
            elif ob:
                px = ob["mark_price"]
                ob_pct = ob["ob_pct"]
                l1_pct = ob["l1_pct"]

                if eng["px"] == 0.0:
                    eng["last_px"] = px
                px_diff = px - eng["last_px"]
                eng["last_px"] = px
                eng["px"] = px
                eng["ob_pct"] = ob_pct
                eng["l1_pct"] = l1_pct
                eng["buy_sz"] = ob["buy_sz"]
                eng["sell_sz"] = ob["sell_sz"]
                eng["last_update_ist"] = ist_full

                # Keep 2-minute L2 history for V-Shape exhaustion check
                eng["buy_pct_history"].append(ob_pct)
                if len(eng["buy_pct_history"]) > 45:
                    eng["buy_pct_history"].pop(0)

                # Iceberg Net Score
                eng["iceberg_score"] = eng["iceberg_score"] * 0.985 + ((ob_pct - 50.0) * 0.22)
                eng["iceberg_score"] = max(-300.0, min(300.0, eng["iceberg_score"]))

                # Fetch 1m Klines & Box every 15 seconds (and immediately on startup)
                if now_ts - eng["last_kline_ts"] > 15 or eng["box_high"] == 0.0:
                    kdata = fetch_klines_and_box()
                    if isinstance(kdata, str):
                        eng["last_err"] = kdata
                    elif kdata:
                        eng["box_high"] = kdata["bh"]
                        eng["box_low"] = kdata["bl"]
                        eng["box_width"] = kdata["bw"]
                        eng["h10"] = kdata["h10"]
                        eng["l10"] = kdata["l10"]
                        eng["pe_base"] = kdata["pe_base"]
                        eng["ce_base"] = kdata["ce_base"]
                        eng["htf_trend"] = kdata["htf_trend"]
                        eng["last_kline_ts"] = now_ts

                # Calculate Live Dual-Track Scores (Blended Kline + Live Orderbook Flow)
                live_buy_boost = max(0.0, (ob_pct - 45.0) * 18.0 + (px_diff * 12.0))
                live_sell_boost = max(0.0, (55.0 - ob_pct) * 18.0 - (px_diff * 12.0))
                buy_track = max(50.0, eng["pe_base"] + live_buy_boost)
                sell_track = max(50.0, eng["ce_base"] + live_sell_boost)
                eng["buy_track"] = buy_track
                eng["sell_track"] = sell_track

                # ================================================================
                # ENGINE 1: BBNT 15-MIN BOX & STATE LOCKING
                # ================================================================
                bh, bl = eng["box_high"], eng["box_low"]
                sig_text = "Neutral (Inside Box)"
                sig_cls = "badge-gray"
                locked_pts = 0.0
                new_master_sig = None
                master_reason = ""

                if bh > 0 and bl > 0:
                    # Check existing Locked Trend Ride
                    if eng["lock_state"] == "LONG":
                        locked_pts = px - eng["lock_trigger_px"]
                        if px < eng["lock_box_high"] or (sell_track > buy_track * 1.15):
                            eng["lock_state"] = "NONE"
                        else:
                            sig_text = f"Riding LONG ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-green"

                    elif eng["lock_state"] == "SHORT":
                        locked_pts = eng["lock_trigger_px"] - px
                        if px > eng["lock_box_low"] or (buy_track > sell_track * 1.15):
                            eng["lock_state"] = "NONE"
                        else:
                            sig_text = f"Riding SHORT ({locked_pts:+.1f} Pts)"
                            sig_cls = "badge-red"

                    # Check New Breakouts if Unlocked
                    if eng["lock_state"] == "NONE":
                        buy_dom = buy_track > (sell_track * 1.15)
                        sell_dom = sell_track > (buy_track * 1.15)
                        hc_buy = "★ High Conviction " if (ob_pct >= 58.0 and buy_dom) else ""
                        hc_sell = "★ High Conviction " if (ob_pct <= 42.0 and sell_dom) else ""

                        if px > bh:
                            if buy_dom:
                                sig_text = f"{hc_buy}True Breakout (LONG)"
                                sig_cls = "badge-green"
                                eng["lock_state"] = "LONG"
                                eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh
                                eng["lock_box_low"] = bl
                                new_master_sig = "BUY"
                                master_reason = "📦 BBNT 15m True Breakout"
                            else:
                                sig_text = "Fake Breakout / Bull Trap"
                                sig_cls = "badge-yellow"
                        elif px < bl:
                            if sell_dom:
                                sig_text = f"{hc_sell}True Breakdown (SHORT)"
                                sig_cls = "badge-red"
                                eng["lock_state"] = "SHORT"
                                eng["lock_trigger_px"] = px
                                eng["lock_box_high"] = bh
                                eng["lock_box_low"] = bl
                                new_master_sig = "SELL"
                                master_reason = "📦 BBNT 15m True Breakdown"
                            else:
                                sig_text = "Fake Breakdown / Spring (LONG)"
                                sig_cls = "badge-cyan"

                    eng["current_sig_text"] = sig_text
                    eng["current_sig_cls"] = sig_cls
                    eng["locked_pts"] = locked_pts

                    # Update Live Signal Table (1 row per minute, live-updated on top row)
                    row_obj = {
                        "time": ist_min, "px": px, "bh": bh, "bl": bl,
                        "bt": buy_track, "st": sell_track, "pts": locked_pts,
                        "sig": sig_text, "cls": sig_cls
                    }
                    if not eng["live_table"] or eng["live_table"][0]["time"] != ist_min:
                        eng["live_table"].insert(0, row_obj)
                        eng["live_table"] = eng["live_table"][:35]
                    else:
                        eng["live_table"][0] = row_obj

                # ================================================================
                # ENGINE 2: 1-MINUTE V-SHAPE REVERSAL ANALYZER (10-PT SCORE)
                # ================================================================
                if eng["h10"] > 0:
                    drop_10m = eng["h10"] - px
                    rally_10m = px - eng["l10"]
                    v_dir = "कोई साफ सेटअप नहीं"
                    v_prob = "बहुत कम"
                    v_score = 0
                    v_reasons = []
                    v_danger = "मार्केट अभी सामान्य रेंज में है (150+ पॉइंट्स का स्ट्रेच नहीं है)।"
                    v_action = "प्राइस रिजेक्शन और एग्जॉशन की पुष्टि का इंतजार करें — अभी कोई ट्रेड नहीं"

                    if drop_10m >= 150.0:
                        v_dir = "बुलिश V-शेप"
                        if ob_pct <= 27.0: v_score += 2; v_reasons.append(f"चरम सेलिंग प्रेशर (L2 Buy: {ob_pct:.0f}%)")
                        elif ob_pct <= 33.0: v_score += 1; v_reasons.append(f"तेज़ सेलिंग प्रेशर (L2 Buy: {ob_pct:.0f}%)")
                        if buy_track > sell_track: v_score += 2; v_reasons.append(f"पुट सपोर्ट मजबूत (PE Track: {buy_track:,.0f})")
                        l2_min = min(eng["buy_pct_history"]) if eng["buy_pct_history"] else ob_pct
                        if ob_pct > l2_min + 2.0 and l1_pct >= 50.0:
                            v_score += 2; v_reasons.append(f"सेलिंग एग्जॉशन (L1 Bid {l1_pct:.0f}% पर रिकवर)")
                        bounce = px - eng["l10"]
                        if bounce >= 35.0:
                            v_score += 2; v_reasons.append(f"स्विंग लो से रिजेक्शन बाउंस (+{bounce:.1f} Pts)")
                        else:
                            v_danger = f"लो से अभी सिर्फ +{bounce:.1f} Pts का बाउंस है। गिरती कैंडल में एंट्री खतरनाक है!"
                        if eng["iceberg_score"] > 30.0 or eng["htf_trend"] == "BULLISH":
                            v_score += 2; v_reasons.append("स्मार्ट मनी/HTF सपोर्ट पक्ष में है")

                    elif rally_10m >= 150.0:
                        v_dir = "बियरिश Inverted V-शेप"
                        if ob_pct >= 70.0: v_score += 2; v_reasons.append(f"चरम बाइंग प्रेशर (L2 Buy: {ob_pct:.0f}%)")
                        elif ob_pct >= 65.0: v_score += 1; v_reasons.append(f"तेज़ बाइंग प्रेशर (L2 Buy: {ob_pct:.0f}%)")
                        if sell_track > buy_track: v_score += 2; v_reasons.append(f"कॉल रेजिस्टेंस मजबूत (CE Track: {sell_track:,.0f})")
                        l2_max = max(eng["buy_pct_history"]) if eng["buy_pct_history"] else ob_pct
                        if ob_pct < l2_max - 2.0 and l1_pct <= 50.0:
                            v_score += 2; v_reasons.append(f"बाइंग एग्जॉशन (L1 Ask {100-l1_pct:.0f}% हावी)")
                        pullback = eng["h10"] - px
                        if pullback >= 35.0:
                            v_score += 2; v_reasons.append(f"स्विंग हाई से रिजेक्शन (-{pullback:.1f} Pts गिरावट)")
                        else:
                            v_danger = f"हाई से अभी सिर्फ -{pullback:.1f} Pts की गिरावट है। ब्रेकआउट जारी रह सकता है!"
                        if eng["iceberg_score"] < -30.0 or eng["htf_trend"] == "BEARISH":
                            v_score += 2; v_reasons.append("स्मार्ट मनी/HTF सप्लाई पक्ष में है")

                    if v_dir != "कोई साफ सेटअप नहीं":
                        has_ex = any("एग्जॉशन" in r for r in v_reasons)
                        has_rej = any("रिजेक्शन" in r for r in v_reasons)
                        if not (has_ex and has_rej):
                            v_score = min(v_score, 4)

                        if v_score <= 2: v_prob = "बहुत कम"
                        elif v_score <= 4: v_prob = "कम (प्रेशर है, रिजेक्शन नहीं)"
                        elif v_score <= 6: v_prob = "मध्यम (पुष्टि का इंतजार करें)"
                        elif v_score <= 8: v_prob = "अच्छी"
                        else: v_prob = "बहुत अच्छी (हाई कन्विक्शन)"

                        if v_score >= 7:
                            v_danger = "रीसेंट स्विंग लो/हाई टूटने पर ट्रैप फेल हो जाएगा (SL सख्त रखें)।"
                            if v_dir == "बुलिश V-शेप":
                                v_action = f"LONG (Buy) @ ${px:,.1f} | SL: ${eng['l10']-40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig:
                                    new_master_sig = "BUY"; master_reason = "🚀 बुलिश V-शेप रिवर्सल"
                            else:
                                v_action = f"SHORT (Sell) @ ${px:,.1f} | SL: ${eng['h10']+40:,.1f} | Target: +250p / +400p"
                                if not new_master_sig:
                                    new_master_sig = "SELL"; master_reason = "🚀 बियरिश Inverted V रिवर्सल"

                    eng["v_engine"] = {
                        "dir": v_dir, "prob": v_prob, "score": v_score,
                        "reasons": v_reasons, "danger": v_danger, "action": v_action
                    }

                # ================================================================
                # ENGINE 3: FEE-PROOF SMART TRAILING TRACKER (+100p LOCK)
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
                        if max_pnl >= 600.0: trail_sl = eng["track_max_fav"] - 150.0
                        elif max_pnl >= 400.0: trail_sl = t_entry + 250.0
                        elif max_pnl >= 200.0: trail_sl = t_entry + 100.0
                        else: trail_sl = t_entry - 300.0

                        if px <= trail_sl:
                            eng["track_status"] = "Closed"
                            sts = f"🛑 SL हिट ({live_pnl:+.0f}p)" if live_pnl < 0 else f"✅ प्रॉफिट लॉक (+{live_pnl:,.0f}p)"
                            eng["active_trade_obj"].update({"status": sts, "final_pnl": live_pnl, "close_time": ist_full})
                            eng["closed_trades_ledger"].insert(0, eng["active_trade_obj"])
                            eng["active_trade_obj"] = None; eng["track_signal"] = None

                    elif t_type == "SELL":
                        live_pnl = t_entry - px
                        eng["track_max_fav"] = min(eng["track_max_fav"], px)
                        max_pnl = t_entry - eng["track_max_fav"]
                        if max_pnl >= 600.0: trail_sl = eng["track_max_fav"] + 150.0
                        elif max_pnl >= 400.0: trail_sl = t_entry - 250.0
                        elif max_pnl >= 200.0: trail_sl = t_entry - 100.0
                        else: trail_sl = t_entry + 300.0

                        if px >= trail_sl:
                            eng["track_status"] = "Closed"
                            sts = f"🛑 SL हिट ({live_pnl:+.0f}p)" if live_pnl < 0 else f"✅ प्रॉफिट लॉक (+{live_pnl:,.0f}p)"
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
def get_master_engine_v4_1():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_px": 0.0, "ob_pct": 50.0, "l1_pct": 50.0,
        "buy_sz": 0.0, "sell_sz": 0.0, "last_update_ist": "--:--:--",
        "box_high": 0.0, "box_low": 0.0, "box_width": 0.0, "h10": 0.0, "l10": 0.0,
        "pe_base": 500.0, "ce_base": 500.0, "buy_track": 500.0, "sell_track": 500.0,
        "htf_trend": "BULLISH", "last_kline_ts": 0.0, "buy_pct_history": [], "iceberg_score": 0.0,
        "lock_state": "NONE", "lock_trigger_px": 0.0, "lock_box_high": 0.0, "lock_box_low": 0.0,
        "current_sig_text": "Neutral (Inside Box)", "current_sig_cls": "badge-gray", "locked_pts": 0.0,
        "live_table": [], "v_engine": {"dir": "कोई साफ सेटअप नहीं", "prob": "बहुत कम", "score": 0, "reasons": [], "danger": "-", "action": "-"},
        "active_trade_obj": None, "closed_trades_ledger": [], "track_signal": None,
        "track_entry_px": 0.0, "track_max_fav": 0.0, "track_status": "Idle", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v4_1()

# ============================================================================
# RENDER CLEAN DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    tot_trades = len(eng["closed_trades_ledger"])
    wins = sum(1 for t in eng["closed_trades_ledger"] if t["final_pnl"] > 0)
    win_rate = (wins / tot_trades * 100.0) if tot_trades > 0 else 0.0

    # --- TOP HEADER BAR ---
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:20px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V4.1 (BBNT + V-SHAPE)</span>
        <span style='font-size:20px; font-weight:900; color:#f8fafc; margin-left:15px;'>BTC: ${eng['px']:,.1f}</span></div>
        <div><span style='color:#facc15; font-weight:bold; margin-right:20px;'>🏆 Win Rate: {win_rate:.1f}% ({wins}/{tot_trades})</span>
        <span style='color:#4ade80; font-size:13px;'>● Live IST: {eng['last_update_ist']}</span></div>
    </div>
    """, unsafe_allow_html=True)

    # --- ROW 1: 4 EQUAL SUMMARY CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        trig_info = f"Trigger: ${eng['lock_trigger_px']:,.1f} ({eng['locked_pts']:+.1f} Pts)" if eng["lock_state"] != "NONE" else "Waiting for Box Breakout"
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>1. Current Market State</div>
            <div><span class='badge {eng["current_sig_cls"]}' style='font-size:13.5px;'>{eng["current_sig_text"]}</span></div>
            <div style='font-size:12px; color:#cbd5e1;'>{trig_info}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>2. 15-Min Volatility Box</div>
            <div style='font-size:14px; font-weight:bold;'><span style='color:#ef4444;'>H: ${eng['box_high']:,.1f}</span> &nbsp;|&nbsp; <span style='color:#22c55e;'>L: ${eng['box_low']:,.1f}</span></div>
            <div style='font-size:12.5px; color:#facc15; font-weight:bold;'>Box Width: {eng['box_width']:,.1f} Pts</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        bt, st_val = eng["buy_track"], eng["sell_track"]
        tot_t = bt + st_val if (bt + st_val) > 0 else 1.0
        bt_pct = (bt / tot_t) * 100.0
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>3. Dual-Track OI Score (5m)</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>Buy (PE): {bt:,.0f}</span>
                <span style='color:#ef4444;'>Sell (CE): {st_val:,.0f}</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{bt_pct:.1f}%;'></div><div class='bar-sell' style='width:{100-bt_pct:.1f}%;'></div></div>
        </div>""", unsafe_allow_html=True)

    with c4:
        ob_p = eng["ob_pct"]
        st.markdown(f"""<div class='metric-box'>
            <div class='card-title'>4. Orderbook Pressure (L2)</div>
            <div style='display:flex; justify-content:space-between; font-size:12.5px; font-weight:bold;'>
                <span style='color:#22c55e;'>Bids: {ob_p:.1f}% ({eng['buy_sz']:.1f} BTC)</span>
                <span style='color:#ef4444;'>Asks: {100-ob_p:.1f}%</span>
            </div>
            <div class='bar-container'><div class='bar-buy' style='width:{ob_p:.1f}%;'></div><div class='bar-sell' style='width:{100-ob_p:.1f}%;'></div></div>
        </div>""", unsafe_allow_html=True)

    # --- ROW 2: TRADE TRACKER (LEFT) & V-SHAPE ANALYZER (RIGHT) ---
    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
    m_left, m_right = st.columns([0.52, 0.48])

    with m_left:
        if eng["track_status"] == "Tracking" and eng["active_trade_obj"]:
            tr = eng["active_trade_obj"]
            t_col = "#22c55e" if tr["type"] == "BUY" else "#ef4444"
            p_col = "#4ade80" if tr["live_pnl"] >= 0 else "#f87171"
            mx = tr["max_pnl"]
            sl_txt = "🔒 +250p सुपर लॉक!" if mx >= 400 else ("🛡️ फीस+प्रॉफिट (+100p) लॉक!" if mx >= 200 else "⚠️ शुरुआती SL: -300p (+200p पर सेफ होगा)")
            active_html = f"""<div style='background:#1e293b; border:2px solid {t_col}; padding:12px; border-radius:8px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;'>
                <div><div style='font-size:12px; color:#94a3b8;'>🎯 ACTIVE MASTER TRADE ({tr['reason']})</div>
                <div style='font-size:20px; font-weight:900; color:#fff;'>{tr['type']} @ ${tr['entry']:,.1f}</div>
                <div style='font-size:12px; color:#facc15; margin-top:3px;'>{sl_txt}</div></div>
                <div style='text-align:right;'><div style='font-size:26px; font-weight:900; color:{p_col};'>{tr['live_pnl']:+.1f}p</div>
                <div style='font-size:12px; color:#38bdf8;'>High: +{mx:,.1f}p</div></div>
            </div>"""
        else:
            active_html = f"""<div style='background:#1e293b; border:1px dashed #475569; padding:14px; border-radius:8px; margin-bottom:12px; text-align:center; color:#94a3b8; font-weight:bold;'>
                ⏳ कोई एक्टिव ट्रेड नहीं — BBNT या V-Shape हाई-कन्विक्शन सिग्नल का इंतज़ार...
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
            ledger_html = "<div style='color:#64748b; text-align:center; padding-top:60px;'>अभी कोई ट्रेड बंद नहीं हुआ है</div>"

        st.markdown(f"<div class='panel-box'><div style='font-size:14px; font-weight:bold; color:#facc15; margin-bottom:8px;'>🎯 स्मार्ट ट्रेड ट्रैकर एवं प्रॉफिट/लॉस खाता</div>{active_html}{ledger_html}</div>", unsafe_allow_html=True)

    with m_right:
        v = eng["v_engine"]
        sc_col = "#22c55e" if v["score"] >= 7 else ("#facc15" if v["score"] >= 5 else "#ef4444")
        r_li = "".join([f"<li>{r}</li>" for r in v["reasons"]]) if v["reasons"] else "<li>पिछले 10 मिनट में 150+ पॉइंट्स का एकतरफा मूव नहीं है</li>"
        st.markdown(f"""<div class='vshape-box'>
            <div style='font-size:15px; font-weight:bold; color:#38bdf8; border-bottom:1px solid #334155; padding-bottom:6px; margin-bottom:8px;'>
                🔬 1-Minute V-Shape Reversal Engine
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

    # --- ROW 3: UNIFIED BBNT LIVE SIGNAL TABLE (SINGLE HTML BLOCK) ---
    st.markdown("<div style='font-size:15px; font-weight:bold; color:#38bdf8; margin-top:18px;'>📊 BBNT Live 1-Minute Signal Table</div>", unsafe_allow_html=True)
    
    rows_str = ""
    for r in eng["live_table"]:
        pts_txt = f"{r['pts']:+.1f} Pts" if r["pts"] != 0 else "-"
        rows_str += f"<tr><td><b>{r['time']}</b></td><td>${r['px']:,.1f}</td><td>${r['bh']:,.1f}</td><td>${r['bl']:,.1f}</td><td style='color:#22c55e; font-weight:bold;'>{r['bt']:,.0f}</td><td style='color:#ef4444; font-weight:bold;'>{r['st']:,.0f}</td><td>{pts_txt}</td><td><span class='badge {r['cls']}'>{r['sig']}</span></td></tr>"
    
    if not rows_str:
        rows_str = "<tr><td colspan='8' style='text-align:center; color:#94a3b8;'>डेटा लोड हो रहा है...</td></tr>"

    full_table_html = f"""<div class='table-wrapper'>
        <table class='custom-table'>
            <thead><tr><th>Time (IST)</th><th>Future Price</th><th>Box High (15m)</th><th>Box Low (15m)</th><th>Buy Track</th><th>Sell Track</th><th>Move / Points</th><th>Final Signal</th></tr></thead>
            <tbody>{rows_str}</tbody>
        </table>
    </div>"""
    st.markdown(full_table_html, unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V4.1 Master Terminal स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

import streamlit as st
import requests
import time
import threading
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V8.0 - Microstructure War Room", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.top-header { background: #1e293b; border: 1px solid #334155; padding: 15px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
.report-box { background: #0f172a; border: 1px solid #38bdf8; border-top: 5px solid #38bdf8; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
.void-box { background: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 10px; height: 350px; overflow-y: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }
.metric-row { display: flex; justify-content: space-between; margin-top: 15px; }
.metric-card { background: #1e293b; padding: 15px; border-radius: 8px; width: 23.5%; text-align: center; border: 1px solid #334155; }
.void-item { font-size: 13.5px; padding: 10px; border-bottom: 1px solid #334155; color: #cbd5e1; margin-bottom: 6px; border-radius: 6px; background: #0f172a; }
.void-bull { border-left: 4px solid #22c55e; }
.void-bear { border-left: 4px solid #ef4444; }
.void-chop { border-left: 4px solid #facc15; }
.report-title { font-size: 22px; font-weight: 900; color: #f8fafc; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 10px; }
.verdict-bull { background: #064e3b30; border-left: 4px solid #22c55e; padding: 12px; border-radius: 6px; margin-top: 15px; font-size: 16px; font-weight: bold; color: #4ade80; }
.verdict-bear { background: #7f1d1d30; border-left: 4px solid #ef4444; padding: 12px; border-radius: 6px; margin-top: 15px; font-size: 16px; font-weight: bold; color: #f87171; }
.verdict-neutral { background: #42200630; border-left: 4px solid #facc15; padding: 12px; border-radius: 6px; margin-top: 15px; font-size: 16px; font-weight: bold; color: #facc15; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# API FETCHERS
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now(): return datetime.utcnow() + timedelta(hours=5, minutes=30)
def get_ist_time_str(): return get_ist_now().strftime('%I:%M:%S %p')

def fetch_microstructure_snapshot():
    try:
        r_ob = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2.5)
        if r_ob.status_code != 200: return None
        data = r_ob.json()
        if not data or "levels" not in data or len(data["levels"]) < 2: return None

        bids = data["levels"][0][:20]; asks = data["levels"][1][:20]
        if not bids or not asks: return None

        best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
        mid_px = (best_bid + best_ask) / 2.0; spread = best_ask - best_bid

        # Distance-Weighted L2
        weights = [1.0]*5 + [0.5]*5 + [0.2]*10
        w_bid = sum(float(b["sz"]) * weights[i] for i, b in enumerate(bids))
        w_ask = sum(float(a["sz"]) * weights[i] for i, a in enumerate(asks))

        taker_buy = 0.0; taker_sell = 0.0
        try:
            r_tr = requests.post(HYPERLIQUID_URL, json={"type": "recentTrades", "coin": "BTC"}, timeout=2.0)
            if r_tr.status_code == 200:
                trades = r_tr.json()
                if isinstance(trades, list):
                    for t in trades[:50]:
                        sz = float(t.get("sz", 0.0))
                        if t.get("side") == "B": taker_buy += sz
                        else: taker_sell += sz
        except: pass

        if (taker_buy + taker_sell) == 0: taker_buy, taker_sell = w_bid * 0.1, w_ask * 0.1

        return {"px": mid_px, "spread": spread, "w_bid": w_bid, "w_ask": w_ask, "t_buy": taker_buy, "t_sell": taker_sell}
    except Exception as e: return str(e)

def fetch_oi_and_vwap():
    try:
        oi_val = 0.0
        r = requests.post(HYPERLIQUID_URL, json={"type": "metaAndAssetCtxs"}, timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                for idx, asset in enumerate(data[0].get("universe", [])):
                    if asset.get("name") == "BTC" and idx < len(data[1]):
                        oi_val = float(data[1][idx].get("openInterest", 0.0))
        
        end_time = int(time.time() * 1000); start_time = end_time - (30 * 60 * 1000)
        r2 = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3.0)
        vwap = 0.0
        if r2.status_code == 200 and len(r2.json()) > 5:
            df = pd.DataFrame(r2.json()[:-1])
            for c in ['h','l','c','v']: df[c] = df[c].astype(float)
            typ = (df['h'] + df['l'] + df['c']) / 3.0
            vwap = float((typ * df['v']).sum() / max(0.1, df['v'].sum()))

        return {"oi": oi_val, "vwap": vwap}
    except: pass
    return None

# ============================================================================
# 24x7 BACKGROUND WORKER (V8.0 WAR ROOM ENGINE)
# ============================================================================
def background_worker(eng, worker_id):
    SPREAD_VOID_THRESHOLD = 4.0
    REPORT_INTERVAL_SEC = 180 # 3 Minutes
    VAULT_MEMORY_SEC = 1800 # 30 Minutes

    while True:
        if eng.get("worker_id") != worker_id: break
        try:
            now_ts = time.time(); ist_str = get_ist_time_str()
            snap = fetch_microstructure_snapshot()

            if isinstance(snap, str): eng["last_err"] = snap
            elif snap:
                px = snap["px"]
                eng["px"] = px; eng["last_update"] = ist_str

                # 1. 30-MINUTE DATA VAULT
                eng["vault"].append({
                    "ts": now_ts, "px": px,
                    "w_bid": snap["w_bid"], "w_ask": snap["w_ask"],
                    "t_buy": snap["t_buy"], "t_sell": snap["t_sell"]
                })
                eng["vault"] = [d for d in eng["vault"] if (now_ts - d["ts"]) <= VAULT_MEMORY_SEC]

                # 2. LIQUIDITY VOID LOGGER (Spread > $4.0)
                spread = snap["spread"]
                if spread >= SPREAD_VOID_THRESHOLD:
                    t_pct = (snap["t_buy"] / (snap["t_buy"] + snap["t_sell"]) * 100) if (snap["t_buy"] + snap["t_sell"]) > 0 else 50
                    if t_pct >= 60: cls = "void-bull"; act = "🟢 बायर अटैक (मार्केट बायिंग)"
                    elif t_pct <= 40: cls = "void-bear"; act = "🔴 सेलर अटैक (मार्केट सेलिंग)"
                    else: cls = "void-chop"; act = "⚪ दोनों तरफ की खींचतान"

                    void_obj = {"time": ist_str, "spread": spread, "act": act, "cls": cls, "px": px}
                    if not eng["voids"] or eng["voids"][0]["time"] != ist_str:
                        eng["voids"].insert(0, void_obj)
                        eng["voids"] = eng["voids"][:40] # Keep recent voids

                # Fetch VWAP & OI every 15s
                if now_ts - eng["last_kline_ts"] > 15:
                    kdata = fetch_oi_and_vwap()
                    if kdata:
                        eng["vwap"] = kdata["vwap"]
                        if not eng["oi_start"]: eng["oi_start"] = kdata["oi"] # Anchor OI at startup
                        eng["oi_chg"] = kdata["oi"] - eng["oi_start"]
                    eng["last_kline_ts"] = now_ts

                # 3. THE 3-MINUTE PRO REPORT GENERATOR
                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and len(eng["vault"]) > 30:
                    vault = eng["vault"]
                    # Calculate 30-Minute Totals
                    tot_t_buy = sum(d["t_buy"] for d in vault)
                    tot_t_sell = sum(d["t_sell"] for d in vault)
                    tot_w_bid = sum(d["w_bid"] for d in vault)
                    tot_w_ask = sum(d["w_ask"] for d in vault)
                    
                    start_px = vault[0]["px"]; current_px = px
                    px_change = current_px - start_px
                    high_px = max(d["px"] for d in vault); low_px = min(d["px"] for d in vault)

                    tape_buy_pct = (tot_t_buy / (tot_t_buy + tot_t_sell) * 100) if (tot_t_buy + tot_t_sell) > 0 else 50
                    l2_buy_pct = (tot_w_bid / (tot_w_bid + tot_w_ask) * 100) if (tot_w_bid + tot_w_ask) > 0 else 50

                    # PRO LOGIC: Absorption & Spoofing Analysis
                    spoof_alert = ""
                    if tape_buy_pct > 55 and l2_buy_pct < 45: spoof_alert = "⚠️ स्पूफिंग अलर्ट: ऑर्डरबुक में नकली सेलिंग दीवारें हैं, लेकिन असली सौदों (Tape) में लोग खरीद रहे हैं।"
                    elif tape_buy_pct < 45 and l2_buy_pct > 55: spoof_alert = "⚠️ स्पूफिंग अलर्ट: ऑर्डरबुक में नकली बाइंग दीवारें हैं, लेकिन असली सौदों (Tape) में लोग बेच रहे हैं।"

                    absorption_alert = ""
                    if tape_buy_pct > 58 and px_change < 0: absorption_alert = "🧊 बियरिश अब्जॉर्प्शन (Bear Iceberg): भारी मार्केट बाइंग के बावजूद प्राइस गिर रहा है। व्हेल्स ऊपर से माल चिपका रहे हैं!"
                    elif tape_buy_pct < 42 and px_change > 0: absorption_alert = "🧊 बुलिश अब्जॉर्प्शन (Bull Iceberg): भारी मार्केट सेलिंग के बावजूद प्राइस बढ़ रहा है। व्हेल्स नीचे से माल सोख रहे हैं!"

                    # Void Analysis (Last 30 mins only)
                    voids_30m = [v for v in eng["voids"] if (datetime.strptime(ist_str, '%I:%M:%S %p') - datetime.strptime(v["time"], '%I:%M:%S %p')).seconds <= 1800]
                    bull_voids = sum(1 for v in voids_30m if v["cls"] == "void-bull")
                    bear_voids = sum(1 for v in voids_30m if v["cls"] == "void-bear")

                    # FINAL VERDICT LOGIC
                    score = 0
                    if tape_buy_pct >= 54: score += 2
                    elif tape_buy_pct <= 46: score -= 2
                    if "बुलिश अब्जॉर्प्शन" in absorption_alert: score += 3
                    elif "बियरिश अब्जॉर्प्शन" in absorption_alert: score -= 3
                    if bull_voids > bear_voids + 2: score += 1
                    elif bear_voids > bull_voids + 2: score -= 1
                    if current_px > eng["vwap"]: score += 1
                    else: score -= 1

                    if score >= 3: verdict = {"title": "🔥 बायर्स पूरी तरह से हावी हैं (Bullish Dominance)", "cls": "verdict-bull", "txt": "पिछले 30 मिनट में स्मार्ट मनी लगातार खरीदारी कर रही है। डिप (Dip) पर BUY करने के मौके ढूँढें।"}
                    elif score <= -3: verdict = {"title": "🩸 सेलर्स पूरी तरह से हावी हैं (Bearish Dominance)", "cls": "verdict-bear", "txt": "पिछले 30 मिनट में स्मार्ट मनी लगातार माल बेच रही है। उछाल (Pump) पर SELL करने के मौके ढूँढें।"}
                    else: verdict = {"title": "⚖️ दोनों तरफ की भयानक टक्कर (No-Man's Land / Choppy)", "cls": "verdict-neutral", "txt": "बायर्स और सेलर्स लगभग बराबर ताकत लगा रहे हैं। ब्रेकआउट या ब्रेकडाउन का इंतजार करें, अभी एंट्री न लें।"}

                    eng["report"] = {
                        "time": ist_str, "px_chg": px_change, "high": high_px, "low": low_px,
                        "tape_buy": tape_buy_pct, "l2_buy": l2_buy_pct, "oi_chg": eng["oi_chg"],
                        "bull_voids": bull_voids, "bear_voids": bear_voids,
                        "spoof": spoof_alert, "absorb": absorption_alert, "verdict": verdict
                    }
                    eng["last_report_ts"] = now_ts

        except Exception as e: eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_master_engine_v8_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "report": None, "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v8_0()

# ============================================================================
# RENDER V8.0 DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:24px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V8.0 (MICROSTRUCTURE WAR ROOM)</span></div>
        <div>
            <span style='font-size:24px; font-weight:900; color:#f8fafc; margin-right:20px;'>BTC: ${eng['px']:,.1f}</span>
            <span style='color:#4ade80; font-size:14px; font-weight:bold;'>● Live: {eng['last_update']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    r_left, r_right = st.columns([0.65, 0.35])

    with r_left:
        if eng["report"]:
            r = eng["report"]
            chg_col = "#4ade80" if r['px_chg'] >= 0 else "#f87171"
            oi_col = "#4ade80" if r['oi_chg'] >= 0 else "#f87171"
            
            alerts_html = ""
            if r['spoof']: alerts_html += f"<div style='background:#42200650; color:#facc15; padding:10px; border-left:4px solid #eab308; border-radius:6px; margin-top:10px; font-weight:bold;'>{r['spoof']}</div>"
            if r['absorb']: alerts_html += f"<div style='background:#0c4a6e50; color:#38bdf8; padding:10px; border-left:4px solid #0284c7; border-radius:6px; margin-top:10px; font-weight:bold;'>{r['absorb']}</div>"
            if not alerts_html: alerts_html = "<div style='color:#94a3b8; font-size:14px; margin-top:10px;'>मार्केट में कोई स्पूफिंग या छुपकर अब्जॉर्प्शन नहीं हो रहा है, वॉल्यूम असली है।</div>"

            st.markdown(f"""
            <div class='report-box'>
                <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:15px;'>
                    <div class='report-title' style='border:none; margin:0; padding:0;'>📋 पिछले 30-मिनट की स्मार्ट मनी रिपोर्ट</div>
                    <div style='color:#94a3b8; font-size:14px;'>अपडेट समय: <b style='color:#fff;'>{r['time']}</b> (अगली रिपोर्ट 3 मिनट में)</div>
                </div>
                
                <div class='metric-row'>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>प्राइस बदलाव (30m)</div>
                        <div style='font-size:18px; font-weight:900; color:{chg_col};'>{r['px_chg']:+.1f} Pts</div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>H: ${r['high']:,.0f} | L: ${r['low']:,.0f}</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>असली सौदे (Taker Tape)</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['tape_buy']:.0f}%</span> / <span style='color:#f87171;'>{100-r['tape_buy']:.0f}%</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>Buy Vol vs Sell Vol</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>ऑर्डरबुक दीवारें (L2 Limits)</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['l2_buy']:.0f}%</span> / <span style='color:#f87171;'>{100-r['l2_buy']:.0f}%</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>Bids vs Asks (Weighted)</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>लिक्विडिटी वॉइड्स (Spread > $4)</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['bull_voids']} Bull</span> / <span style='color:#f87171;'>{r['bear_voids']} Bear</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>अचानक फटे बड़े स्प्रेड</div>
                    </div>
                </div>

                <div style='margin-top:20px; font-size:16px; font-weight:bold; color:#38bdf8;'>🔎 प्रो-क्वांट विश्लेषण (Pro Logic Analysis):</div>
                {alerts_html}
                
                <div class='{r['verdict']['cls']}'>
                    <div style='font-size:18px; margin-bottom:5px;'>{r['verdict']['title']}</div>
                    <div style='font-size:14px; font-weight:normal; color:#f8fafc;'>{r['verdict']['txt']} (VWAP बेस: ${eng['vwap']:,.1f})</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            pct = min(100, int((len(eng["vault"]) / 15) * 100)) # Approx 30s to get initial 15 ticks for first report
            st.markdown(f"""
            <div class='report-box' style='text-align:center; padding:60px 20px;'>
                <div style='font-size:24px; font-weight:bold; color:#38bdf8; margin-bottom:15px;'>⏳ पहली स्मार्ट मनी रिपोर्ट तैयार हो रही है...</div>
                <div style='color:#94a3b8; font-size:16px;'>वॉर रूम डेटाबेस में पिछले 30 मिनट का डेटा मथ रहा है। ({pct}% डेटा जमा हुआ)</div>
                <div style='margin-top:10px; color:#facc15; font-size:14px;'>अगली रिपोर्ट 1 से 3 मिनट के अंदर स्क्रीन पर आ जाएगी।</div>
            </div>
            """, unsafe_allow_html=True)

    with r_right:
        st.markdown("<div style='font-size:16px; font-weight:bold; color:#facc15; margin-bottom:10px;'>🌪️ लिक्विडिटी वॉइड लेजर (Spread > $4.0)</div>", unsafe_allow_html=True)
        voids_html = ""
        for v in eng["voids"]:
            voids_html += f"<div class='void-item {v['cls']}'><b>{v['time']} — <span style='color:#f8fafc;'>Spread: ${v['spread']:.1f}</span></b><br><span style='font-size:12px; font-weight:bold; color:#94a3b8;'>{v['act']} @ ${v['px']:,.1f}</span></div>"
        
        st.markdown(f"<div class='void-box'>{voids_html if voids_html else '<div style=\"text-align:center; color:#64748b; padding-top:140px;\">पिछले 30 मिनट में कोई बड़ा स्प्रेड नहीं फटा</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V8.0 (Microstructure War Room) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"): st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

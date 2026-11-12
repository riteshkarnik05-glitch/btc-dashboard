import streamlit as st
import requests
import time
import threading
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V9.3 - Secure AI War Room", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; font-family: sans-serif; }
.top-header { background: #1e293b; border: 1px solid #334155; padding: 15px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
.report-box { background: #0f172a; border: 1px solid #38bdf8; border-top: 5px solid #38bdf8; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
.ai-box { background: #020617; border: 1px solid #c084fc; border-left: 5px solid #c084fc; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 4px 6px -1px rgba(192,132,252,0.2); }
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
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #c084fc !important; border-radius: 8px !important; font-weight: bold !important; }
div.stButton > button:hover { background-color: #c084fc !important; color: #020617 !important; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# API FETCHERS & MULTI-MODEL AI ENGINE
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_microstructure_snapshot():
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
        spread = best_ask - best_bid

        weights = [1.0]*5 + [0.5]*5 + [0.2]*10
        w_bid = sum(float(b["sz"]) * weights[i] for i, b in enumerate(bids))
        w_ask = sum(float(a["sz"]) * weights[i] for i, a in enumerate(asks))

        taker_buy = 0.0
        taker_sell = 0.0
        try:
            r_tr = requests.post(HYPERLIQUID_URL, json={"type": "recentTrades", "coin": "BTC"}, timeout=2.0)
            if r_tr.status_code == 200:
                trades = r_tr.json()
                if isinstance(trades, list):
                    for t in trades[:50]:
                        sz = float(t.get("sz", 0.0))
                        if t.get("side") == "B":
                            taker_buy += sz
                        else:
                            taker_sell += sz
        except:
            pass

        if (taker_buy + taker_sell) == 0:
            taker_buy, taker_sell = w_bid * 0.1, w_ask * 0.1

        return {
            "px": mid_px, "spread": spread,
            "w_bid": w_bid, "w_ask": w_ask,
            "t_buy": taker_buy, "t_sell": taker_sell
        }
    except Exception as e:
        return str(e)

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

        end_time = int(time.time() * 1000)
        start_time = end_time - (30 * 60 * 1000)
        r2 = requests.post(HYPERLIQUID_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_time, "endTime": end_time}}, timeout=3.0)
        vwap = 0.0
        if r2.status_code == 200 and len(r2.json()) > 5:
            df = pd.DataFrame(r2.json()[:-1])
            for c in ['h', 'l', 'c', 'v']:
                df[c] = df[c].astype(float)
            typ = (df['h'] + df['l'] + df['c']) / 3.0
            vwap = float((typ * df['v']).sum() / max(0.1, df['v'].sum()))

        return {"oi": oi_val, "vwap": vwap}
    except:
        pass
    return None

def update_ai_opinion_thread(api_key, report_data, eng):
    """Auto-fallback across latest Gemini models to eliminate 404 errors"""
    prompt = f"""
    तुम एक वॉल स्ट्रीट के HFT क्वांट एनालिस्ट हो। पिछले 30 मिनट का BTCUSDT माइक्रोस्ट्रक्चर डेटा यह है:
    - प्राइस बदलाव: {report_data['px_chg']:.1f} Pts
    - असली मार्केट ऑर्डर (Tape): {report_data['tape_buy']:.0f}% Buy / {100-report_data['tape_buy']:.0f}% Sell
    - लिमिट ऑर्डरबुक (L2): {report_data['l2_buy']:.0f}% Buy / {100-report_data['l2_buy']:.0f}% Sell
    - स्पूफिंग अलर्ट: {report_data['spoof'] if report_data['spoof'] else 'कोई स्पूफिंग नहीं, वॉल्यूम असली है।'}
    - अब्जॉर्प्शन अलर्ट: {report_data['absorb'] if report_data['absorb'] else 'कोई अब्जॉर्प्शन नहीं।'}
    - लिक्विडिटी वॉइड्स: {report_data['bull_voids']} Bullish vs {report_data['bear_voids']} Bearish Spreads

    इस डेटा के आधार पर 2 से 3 लाइन में एकदम सख्त और सीधी हिंदी में अपनी प्रो-ओपिनियन दो कि "बड़ी व्हेल्स असल में क्या कर रही हैं और एक इंट्राडे ट्रेडर को अभी क्या करना चाहिए?"
    कोई किताबी ज्ञान मत देना, सीधे पॉइंट पर बात करो।
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # Try latest active models in order
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    last_status = 0
    last_err_msg = ""

    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=8)
            last_status = res.status_code

            if res.status_code == 200:
                data = res.json()
                text_out = data['candidates'][0]['content']['parts'][0]['text'].strip()
                eng["ai_model_used"] = model_name
                eng["ai_opinion"] = text_out
                return
            else:
                try:
                    err_json = res.json()
                    last_err_msg = err_json.get("error", {}).get("message", "")
                except:
                    last_err_msg = res.text[:120]

                # If 400 or 403, the API key itself is invalid/wrong type, no need to try other models
                if res.status_code in [400, 403]:
                    break
        except Exception as e:
            last_err_msg = str(e)

    if last_status in [400, 403]:
        eng["ai_opinion"] = (
            f"⚠️ API Key अमान्य है (Status {last_status}): {last_err_msg}\n"
            f"💡 समाधान: आपकी Key 'AIzaSy...' से शुरू होनी चाहिए। कृपया Google AI Studio (aistudio.google.com/app/apikey) से नई Key बनाकर Streamlit Secrets में डालें।"
        )
    else:
        eng["ai_opinion"] = f"⚠️ AI सर्वर एरर (Status {last_status}): {last_err_msg}"

def build_report_now(eng, now_ts, ist_str):
    """Generates the 30-min report and triggers AI immediately"""
    vault = eng["vault"]
    if not vault:
        return
    px = eng["px"]
    tot_t_buy = sum(d["t_buy"] for d in vault)
    tot_t_sell = sum(d["t_sell"] for d in vault)
    tot_w_bid = sum(d["w_bid"] for d in vault)
    tot_w_ask = sum(d["w_ask"] for d in vault)

    start_px = vault[0]["px"]
    current_px = px
    px_change = current_px - start_px
    high_px = max(d["px"] for d in vault)
    low_px = min(d["px"] for d in vault)

    tape_buy_pct = (tot_t_buy / (tot_t_buy + tot_t_sell) * 100) if (tot_t_buy + tot_t_sell) > 0 else 50
    l2_buy_pct = (tot_w_bid / (tot_w_bid + tot_w_ask) * 100) if (tot_w_bid + tot_w_ask) > 0 else 50

    spoof_alert = ""
    if tape_buy_pct > 55 and l2_buy_pct < 45:
        spoof_alert = "⚠️ स्पूफिंग अलर्ट: ऑर्डरबुक में नकली सेलिंग दीवारें हैं, लेकिन असली सौदों में लोग खरीद रहे हैं।"
    elif tape_buy_pct < 45 and l2_buy_pct > 55:
        spoof_alert = "⚠️ स्पूफिंग अलर्ट: ऑर्डरबुक में नकली बाइंग दीवारें हैं, लेकिन असली सौदों में लोग बेच रहे हैं।"

    absorption_alert = ""
    if tape_buy_pct > 58 and px_change < 0:
        absorption_alert = "🧊 बियरिश अब्जॉर्प्शन: भारी मार्केट बाइंग के बावजूद प्राइस गिर रहा है। व्हेल्स ऊपर से माल चिपका रहे हैं!"
    elif tape_buy_pct < 42 and px_change > 0:
        absorption_alert = "🧊 बुलिश अब्जॉर्प्शन: भारी मार्केट सेलिंग के बावजूद प्राइस बढ़ रहा है। व्हेल्स नीचे से माल सोख रहे हैं!"

    voids_30m = [v for v in eng["voids"] if (now_ts - v.get("ts", now_ts)) <= 1800]
    bull_voids = sum(1 for v in voids_30m if v["cls"] == "void-bull")
    bear_voids = sum(1 for v in voids_30m if v["cls"] == "void-bear")

    score = 0
    if tape_buy_pct >= 54: score += 2
    elif tape_buy_pct <= 46: score -= 2
    if "बुलिश" in absorption_alert: score += 3
    elif "बियरिश" in absorption_alert: score -= 3
    if bull_voids > bear_voids + 2: score += 1
    elif bear_voids > bull_voids + 2: score -= 1
    if current_px > eng["vwap"]: score += 1
    else: score -= 1

    if score >= 3:
        verdict = {"title": "🔥 बायर्स पूरी तरह से हावी हैं (Bullish Dominance)", "cls": "verdict-bull", "txt": "पिछले 30 मिनट में स्मार्ट मनी लगातार खरीदारी कर रही है। डिप (Dip) पर BUY करने के मौके ढूँढें।"}
    elif score <= -3:
        verdict = {"title": "🩸 सेलर्स पूरी तरह से हावी हैं (Bearish Dominance)", "cls": "verdict-bear", "txt": "पिछले 30 मिनट में स्मार्ट मनी लगातार माल बेच रही है। उछाल (Pump) पर SELL करने के मौके ढूँढें।"}
    else:
        verdict = {"title": "⚖️ दोनों तरफ की भयानक टक्कर (No-Man's Land / Choppy)", "cls": "verdict-neutral", "txt": "बायर्स और सेलर्स लगभग बराबर ताकत लगा रहे हैं। ब्रेकआउट या ब्रेकडाउन का इंतजार करें, अभी एंट्री न लें।"}

    report_data = {
        "time": ist_str, "px_chg": px_change, "high": high_px, "low": low_px,
        "tape_buy": tape_buy_pct, "l2_buy": l2_buy_pct, "oi_chg": eng["oi_chg"],
        "bull_voids": bull_voids, "bear_voids": bear_voids,
        "spoof": spoof_alert, "absorb": absorption_alert, "verdict": verdict
    }
    eng["report"] = report_data
    eng["last_report_ts"] = now_ts

    api_key = eng.get("api_key", "").strip()
    if api_key:
        eng["ai_opinion"] = "🤖 AI पिछले 30 मिनट का डेटा पढ़ रहा है, जवाब कुछ सेकंड में..."
        threading.Thread(target=update_ai_opinion_thread, args=(api_key, report_data, eng), daemon=True).start()
    else:
        eng["ai_opinion"] = "⚠️ Streamlit Secrets में GEMINI_API_KEY नहीं मिली।"

# ============================================================================
# 24x7 BACKGROUND WORKER (V9.3 SECURE AI WAR ROOM)
# ============================================================================
def background_worker(eng, worker_id):
    SPREAD_VOID_THRESHOLD = 4.0
    REPORT_INTERVAL_SEC = 180
    VAULT_MEMORY_SEC = 1800

    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            ist_str = get_ist_time_str()
            snap = fetch_microstructure_snapshot()

            if isinstance(snap, str):
                eng["last_err"] = snap
            elif snap:
                px = snap["px"]
                eng["px"] = px
                eng["last_update"] = ist_str

                eng["vault"].append({
                    "ts": now_ts, "px": px,
                    "w_bid": snap["w_bid"], "w_ask": snap["w_ask"],
                    "t_buy": snap["t_buy"], "t_sell": snap["t_sell"]
                })
                eng["vault"] = [d for d in eng["vault"] if (now_ts - d["ts"]) <= VAULT_MEMORY_SEC]

                spread = snap["spread"]
                if spread >= SPREAD_VOID_THRESHOLD:
                    t_pct = (snap["t_buy"] / (snap["t_buy"] + snap["t_sell"]) * 100) if (snap["t_buy"] + snap["t_sell"]) > 0 else 50
                    if t_pct >= 60:
                        cls = "void-bull"; act = "🟢 बायर अटैक (मार्केट बायिंग)"
                    elif t_pct <= 40:
                        cls = "void-bear"; act = "🔴 सेलर अटैक (मार्केट सेलिंग)"
                    else:
                        cls = "void-chop"; act = "⚪ दोनों तरफ की खींचतान"

                    void_obj = {"ts": now_ts, "time": ist_str, "spread": spread, "act": act, "cls": cls, "px": px}
                    if not eng["voids"] or eng["voids"][0]["time"] != ist_str:
                        eng["voids"].insert(0, void_obj)
                        eng["voids"] = eng["voids"][:40]

                if now_ts - eng["last_kline_ts"] > 15:
                    kdata = fetch_oi_and_vwap()
                    if kdata:
                        eng["vwap"] = kdata["vwap"]
                        if not eng["oi_start"]:
                            eng["oi_start"] = kdata["oi"]
                        eng["oi_chg"] = kdata["oi"] - eng["oi_start"]
                    eng["last_kline_ts"] = now_ts

                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and len(eng["vault"]) >= 10:
                    build_report_now(eng, now_ts, ist_str)

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_master_engine_v9_3():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "report": None, "ai_opinion": "⏳ पहली रिपोर्ट बनते ही AI अपना सुझाव देगा...",
        "ai_model_used": "Auto", "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v9_3()

# Read API Key securely from Streamlit Secrets
try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

# ============================================================================
# RENDER V9.3 DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    sec_status = "🟢 Secrets Connected" if eng.get("api_key") else "🔴 Key Missing in Secrets"
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:24px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V9.3 (AUTO-MODEL AI WAR ROOM)</span></div>
        <div>
            <span style='font-size:13px; color:#c084fc; margin-right:15px; font-weight:bold;'>{sec_status}</span>
            <span style='font-size:24px; font-weight:900; color:#f8fafc; margin-right:20px;'>BTC: ${eng['px']:,.1f}</span>
            <span style='color:#4ade80; font-size:14px; font-weight:bold;'>● Live: {eng['last_update']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    btn_col1, btn_col2 = st.columns([0.25, 0.75])
    with btn_col1:
        if st.button("⚡ अभी रिपोर्ट और AI टेस्ट करें"):
            build_report_now(eng, time.time(), get_ist_time_str())
            st.rerun()

    r_left, r_right = st.columns([0.65, 0.35])

    with r_left:
        if eng["report"]:
            r = eng["report"]
            chg_col = "#4ade80" if r['px_chg'] >= 0 else "#f87171"

            alerts_html = ""
            if r['spoof']:
                alerts_html += f"<div style='background:#42200650; color:#facc15; padding:10px; border-left:4px solid #eab308; border-radius:6px; margin-top:10px; font-weight:bold;'>{r['spoof']}</div>"
            if r['absorb']:
                alerts_html += f"<div style='background:#0c4a6e50; color:#38bdf8; padding:10px; border-left:4px solid #0284c7; border-radius:6px; margin-top:10px; font-weight:bold;'>{r['absorb']}</div>"
            if not alerts_html:
                alerts_html = "<div style='color:#94a3b8; font-size:14px; margin-top:10px;'>मार्केट में कोई स्पूफिंग या छुपकर अब्जॉर्प्शन नहीं हो रहा है, वॉल्यूम असली है।</div>"

            st.markdown(f"""
            <div class='report-box'>
                <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:15px;'>
                    <div class='report-title' style='border:none; margin:0; padding:0;'>📋 पिछले 30-मिनट की स्मार्ट मनी रिपोर्ट</div>
                    <div style='color:#94a3b8; font-size:14px;'>अपडेट समय: <b style='color:#fff;'>{r['time']}</b></div>
                </div>
                <div class='metric-row'>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>प्राइस बदलाव (30m)</div>
                        <div style='font-size:18px; font-weight:900; color:{chg_col};'>{r['px_chg']:+.1f} Pts</div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>H: ${r['high']:,.0f} | L: ${r['low']:,.0f}</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>असली सौदे (Tape)</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['tape_buy']:.0f}%</span> / <span style='color:#f87171;'>{100-r['tape_buy']:.0f}%</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>Buy vs Sell Vol</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>लिमिट दीवारें (L2)</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['l2_buy']:.0f}%</span> / <span style='color:#f87171;'>{100-r['l2_buy']:.0f}%</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>Bids vs Asks</div>
                    </div>
                    <div class='metric-card'>
                        <div style='font-size:12px; color:#94a3b8; font-weight:bold; margin-bottom:5px;'>लिक्विडिटी वॉइड्स</div>
                        <div style='font-size:18px; font-weight:900; color:#fff;'><span style='color:#4ade80;'>{r['bull_voids']} Bull</span> / <span style='color:#f87171;'>{r['bear_voids']} Bear</span></div>
                        <div style='font-size:11.5px; color:#cbd5e1; margin-top:3px;'>अचानक फटे स्प्रेड</div>
                    </div>
                </div>
                <div style='margin-top:20px; font-size:16px; font-weight:bold; color:#38bdf8;'>🔎 प्रो-क्वांट विश्लेषण (Pro Logic Analysis):</div>
                {alerts_html}
                <div class='{r['verdict']['cls']}'>
                    <div style='font-size:18px; margin-bottom:5px;'>{r['verdict']['title']}</div>
                    <div style='font-size:14px; font-weight:normal; color:#f8fafc;'>{r['verdict']['txt']} (VWAP बेस: ${eng['vwap']:,.1f})</div>
                </div>
            </div>
            <div class='ai-box'>
                <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #c084fc50; padding-bottom:8px; margin-bottom:12px;'>
                    <div style='font-size:16px; font-weight:bold; color:#c084fc;'>🤖 AI Quant Opinion ({eng['ai_model_used']}):</div>
                    <div style='font-size:12px; color:#94a3b8;'>{sec_status}</div>
                </div>
                <div style='font-size:16px; line-height:1.6; color:#f8fafc; white-space:pre-line;'>{eng['ai_opinion']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            pct = min(100, int((len(eng["vault"]) / 10) * 100))
            st.markdown(f"""
            <div class='report-box' style='text-align:center; padding:60px 20px;'>
                <div style='font-size:24px; font-weight:bold; color:#38bdf8; margin-bottom:15px;'>⏳ पहली स्मार्ट मनी रिपोर्ट तैयार हो रही है...</div>
                <div style='color:#94a3b8; font-size:16px;'>वॉर रूम डेटाबेस में शुरुआती डेटा जमा हो रहा है ({pct}% पूरा)।</div>
                <div style='margin-top:10px; color:#facc15; font-size:14px;'>या ऊपर दिए गए '⚡ अभी रिपोर्ट और AI टेस्ट करें' बटन को दबाएं।</div>
            </div>
            """, unsafe_allow_html=True)

    with r_right:
        st.markdown("<div style='font-size:16px; font-weight:bold; color:#facc15; margin-bottom:10px;'>🌪️ लिक्विडिटी वॉइड लेजर (Spread $4.0 से ऊपर)</div>", unsafe_allow_html=True)
        voids_html = ""
        for v in eng["voids"]:
            voids_html += f"<div class='void-item {v['cls']}'><b>{v['time']} — <span style='color:#f8fafc;'>Spread: ${v['spread']:.1f}</span></b><br><span style='font-size:12px; font-weight:bold; color:#94a3b8;'>{v['act']} @ ${v['px']:,.1f}</span></div>"

        st.markdown(f"<div class='void-box'>{voids_html if voids_html else '<div style=\"text-align:center; color:#64748b; padding-top:140px;\">पिछले 30 मिनट में कोई बड़ा स्प्रेड नहीं फटा</div>'}</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V9.3 (Secure AI War Room) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

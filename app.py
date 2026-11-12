import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import threading
import io
import wave
import struct
import math
import base64
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V9.5 - Auto AI & Sound War Room", layout="wide")

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
div.stButton > button { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 8px !important; font-weight: bold !important; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #020617 !important; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# IN-BUILT SOUND ALERT SYNTHESIZER (NO EXTERNAL MP3 NEEDED)
# ============================================================================
def create_sound_b64(tone_type="BULL"):
    """Generates a clean WAV audio tone in memory and returns base64 string"""
    sample_rate = 22050
    buf = io.BytesIO()

    if tone_type == "BULL":
        # Upward double chime for Bullish Signal
        notes = [(880, 0.16), (0, 0.04), (1175, 0.25)]
    elif tone_type == "BEAR":
        # Downward double alert for Bearish Signal
        notes = [(587, 0.18), (0, 0.04), (440, 0.28)]
    elif tone_type == "VOID":
        # Quick high sonar ping for big Liquidity Void
        notes = [(1046, 0.14)]
    else:
        # Neutral single soft beep
        notes = [(660, 0.18)]

    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for freq, dur in notes:
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                if freq == 0:
                    val = 0
                else:
                    fade = 1.0 - (i / n_samples) * 0.6
                    val = int(16000.0 * fade * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                frames.extend(struct.pack('<h', val))
        wf.writeframes(bytes(frames))

    return base64.b64encode(buf.getvalue()).decode('ascii')

def trigger_browser_audio(tone_type="BULL"):
    """Plays sound directly in browser using HTML5 Audio"""
    b64_wav = create_sound_b64(tone_type)
    audio_html = f"""
        <audio autoplay="true" style="display:none;">
            <source src="data:audio/wav;base64,{b64_wav}" type="audio/wav">
        </audio>
    """
    components.html(audio_html, height=0, width=0)

# ============================================================================
# API FETCHERS & SILENT AUTO-FAILOVER AI ENGINE
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

def generate_local_quant_fallback(r, vwap):
    tb = r["tape_buy"]
    lb = r["l2_buy"]
    chg = r["px_chg"]
    if tb >= 56 and chg > 0:
        return f"असली सौदों (Tape: {tb:.0f}%) और ऑर्डरबुक ({lb:.0f}%) दोनों में खरीदार आक्रामक हैं। जब तक प्राइस VWAP (${vwap:,.0f}) के ऊपर है, हर छोटे डिप पर सिर्फ LONG (Buy) की तलाश करें।"
    elif tb <= 44 and chg < 0:
        return f"मार्केट में सेलर सीधे सौदे मार रहे हैं (Tape Sell: {100-tb:.0f}%) और L2 दीवारें भी कमज़ोर हैं। किसी भी छोटे उछाल (Rally) पर रेजिस्टेंस के पास SHORT (Sell) देखना सुरक्षित रहेगा।"
    elif tb >= 56 and chg < 0:
        return f"सावधान! मार्केट बाइंग ({tb:.0f}%) के बावजूद प्राइस ${abs(chg):.0f} पॉइंट्स गिरा है—यानी ऊपर बड़ी व्हेल लिमिट ऑर्डर लगाकर माल बेच (Absorb) रही है। बाउंस फेल होने पर शॉर्ट का मौका मिलेगा।"
    elif tb <= 44 and chg > 0:
        return f"भारी मार्केट सेलिंग ({100-tb:.0f}%) के बावजूद प्राइस ऊपर टिका है—नीचे व्हेल सारा बिकवाली का माल सोख (Bull Iceberg) रही है। सपोर्ट के पास LONG एंट्री फायदेमंद रहेगी।"
    else:
        return f"अभी बायर ({tb:.0f}%) और सेलर ({100-tb:.0f}%) के बीच बराबरी की खींचतान है। रेंज (${r['low']:,.0f} - ${r['high']:,.0f}) टूटने तक शांत बैठें और अपनी फीस बचाएं।"

def discover_available_flash_models(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            models = r.json().get("models", [])
            flash_list = []
            for m in models:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and ("flash" in name or "gemma" in name):
                    flash_list.append(name)
            return flash_list
    except:
        pass
    return []

def update_ai_opinion_thread(api_key, report_data, eng):
    """Fully silent background model rotation & fallback"""
    prompt = f"""
    तुम एक वॉल स्ट्रीट के HFT क्वांट एनालिस्ट हो। पिछले 30 मिनट का BTCUSDT माइक्रोस्ट्रक्चर डेटा यह है:
    - प्राइस बदलाव: {report_data['px_chg']:.1f} Pts (High: ${report_data['high']:,.0f}, Low: ${report_data['low']:,.0f})
    - असली मार्केट ऑर्डर (Tape): {report_data['tape_buy']:.0f}% Buy / {100-report_data['tape_buy']:.0f}% Sell
    - लिमिट ऑर्डरबुक (L2): {report_data['l2_buy']:.0f}% Buy / {100-report_data['l2_buy']:.0f}% Sell
    - स्पूफिंग अलर्ट: {report_data['spoof'] if report_data['spoof'] else 'कोई स्पूफिंग नहीं, वॉल्यूम असली है।'}
    - अब्जॉर्प्शन अलर्ट: {report_data['absorb'] if report_data['absorb'] else 'कोई अब्जॉर्प्शन नहीं।'}
    - लिक्विडिटी वॉइड्स: {report_data['bull_voids']} Bullish vs {report_data['bear_voids']} Bearish Spreads

    इस डेटा के आधार पर 2 से 3 लाइन में एकदम सख्त और सीधी हिंदी में अपनी प्रो-ओपिनियन दो कि "बड़ी व्हेल्स असल में क्या कर रही हैं और एक इंट्राडे ट्रेडर को अभी क्या करना चाहिए?"
    कोई किताबी ज्ञान मत देना, सीधे पॉइंट पर बात करो।
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-8b",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash"
    ]
    for d_mod in discover_available_flash_models(api_key):
        if d_mod not in models_to_try:
            models_to_try.append(d_mod)

    for model_name in models_to_try:
        for _ in range(2):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                res = requests.post(url, json=payload, timeout=7)
                if res.status_code == 200:
                    data = res.json()
                    eng["ai_opinion"] = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    return
                elif res.status_code == 503:
                    time.sleep(1.2)
                    continue
                else:
                    break
            except Exception:
                break

    eng["ai_opinion"] = generate_local_quant_fallback(report_data, eng.get("vwap", report_data["high"]))

def build_report_now(eng, now_ts, ist_str):
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
        eng["sound_event"] = {"id": now_ts, "type": "BULL"}
    elif score <= -3:
        verdict = {"title": "🩸 सेलर्स पूरी तरह से हावी हैं (Bearish Dominance)", "cls": "verdict-bear", "txt": "पिछले 30 मिनट में स्मार्ट मनी लगातार माल बेच रही है। उछाल (Pump) पर SELL करने के मौके ढूँढें।"}
        eng["sound_event"] = {"id": now_ts, "type": "BEAR"}
    else:
        verdict = {"title": "⚖️ दोनों तरफ की भयानक टक्कर (No-Man's Land / Choppy)", "cls": "verdict-neutral", "txt": "बायर्स और सेलर्स लगभग बराबर ताकत लगा रहे हैं। ब्रेकआउट या ब्रेकडाउन का इंतजार करें, अभी एंट्री न लें।"}
        eng["sound_event"] = {"id": now_ts, "type": "NEUTRAL"}

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
        eng["ai_opinion"] = "🤖 AI पिछले 30 मिनट का डेटा स्कैन कर रहा है..."
        threading.Thread(target=update_ai_opinion_thread, args=(api_key, report_data, eng), daemon=True).start()
    else:
        eng["ai_opinion"] = generate_local_quant_fallback(report_data, eng.get("vwap", high_px))

# ============================================================================
# 24x7 BACKGROUND WORKER (V9.5 SILENT AI + SOUND ENGINE)
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
                        # Trigger quick ping sound if a big spread void (>= $5.0) hits
                        if spread >= 5.0:
                            eng["sound_event"] = {"id": now_ts, "type": "VOID"}

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
def get_master_engine_v9_5():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "report": None, "ai_opinion": "⏳ पहली रिपोर्ट बनते ही AI अपना सुझाव देगा...",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v9_5()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# RENDER V9.5 DASHBOARD UI
# ============================================================================
if eng["px"] > 0:
    st.markdown(f"""
    <div class='top-header'>
        <div><span style='font-size:24px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V9.5 (AI WAR ROOM)</span></div>
        <div>
            <span style='font-size:24px; font-weight:900; color:#f8fafc; margin-right:20px;'>BTC: ${eng['px']:,.1f}</span>
            <span style='color:#4ade80; font-size:14px; font-weight:bold;'>● Live: {eng['last_update']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Clean Top Action & Sound Controls (No AI Model Dropdowns)
    c_btn1, c_btn2, c_btn3 = st.columns([0.28, 0.22, 0.50])
    with c_btn1:
        if st.button("⚡ अभी रिपोर्ट अपडेट करें"):
            build_report_now(eng, time.time(), get_ist_time_str())
            st.rerun()
    with c_btn2:
        if st.button("🔔 साउंड टेस्ट करें"):
            trigger_browser_audio("BULL")
    with c_btn3:
        sound_enabled = st.checkbox("🔊 सिग्नल और नई रिपोर्ट पर साउंड अलर्ट (ON/OFF)", value=True)

    # Play Audio Automatically when a new Report or Big Void event arrives
    curr_snd = eng.get("sound_event", {"id": 0.0, "type": "BULL"})
    if sound_enabled and curr_snd["id"] > 0 and curr_snd["id"] != st.session_state["last_played_sound_id"]:
        st.session_state["last_played_sound_id"] = curr_snd["id"]
        trigger_browser_audio(curr_snd["type"])

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
                    <div style='font-size:16px; font-weight:bold; color:#c084fc;'>🤖 AI Quant Opinion:</div>
                    <div style='font-size:12px; color:#4ade80; font-weight:bold;'>● Auto-Active</div>
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
                <div style='margin-top:10px; color:#facc15; font-size:14px;'>या ऊपर दिए गए '⚡ अभी रिपोर्ट अपडेट करें' बटन को दबाएं।</div>
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
    st.warning("⏳ 24x7 V9.5 (Auto AI & Sound War Room) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

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

st.set_page_config(page_title="Pro Quant V11.0 - Zero-Ghost Command Center", layout="wide")

def clean_html(raw_html: str) -> str:
    """Strips leading spaces so Streamlit renders pure HTML without breaking or duplicating"""
    return "\n".join(line.lstrip() for line in raw_html.splitlines() if line.strip())

st.markdown(clean_html("""
<style>
.stApp { background-color: #090d16; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
.top-bar { background: #111827; border: 1px solid #1f2937; border-bottom: 2px solid #38bdf8; padding: 12px 18px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.main-grid { display: grid; grid-template-columns: 1.65fr 1fr; gap: 14px; align-items: start; }
@media (max-width: 1000px) { .main-grid { grid-template-columns: 1fr; } }
.lock-banner { padding: 14px 18px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.lock-buy { background: #052e16; border: 2px solid #22c55e; color: #4ade80; }
.lock-sell { background: #450a0a; border: 2px solid #ef4444; color: #f87171; }
.lock-wait { background: #1e293b; border: 2px dashed #64748b; color: #cbd5e1; }
.sub-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.card-box { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 13px 15px; }
.card-title { font-size: 12.5px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 8px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; display: flex; justify-content: space-between; }
.stat-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed #1f2937; }
.ai-sharp-box { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid #a855f7; border-left: 5px solid #c084fc; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 245px; overflow-y: auto; }
.void-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 615px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
</style>
"""), unsafe_allow_html=True)

# ============================================================================
# IN-BUILT SOUND SYNTHESIZER
# ============================================================================
def create_sound_b64(tone_type="BULL"):
    sample_rate = 22050
    buf = io.BytesIO()
    if tone_type == "BULL":
        notes = [(784, 0.13), (0, 0.03), (1046, 0.15), (0, 0.03), (1318, 0.22)]
    elif tone_type == "BEAR":
        notes = [(659, 0.14), (0, 0.03), (523, 0.14), (0, 0.03), (392, 0.24)]
    else:
        notes = [(1175, 0.11)]

    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for freq, dur in notes:
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                val = 0 if freq == 0 else int(15000.0 * (1.0 - (i / n_samples) * 0.5) * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                frames.extend(struct.pack('<h', val))
        wf.writeframes(bytes(frames))
    return base64.b64encode(buf.getvalue()).decode('ascii')

# ============================================================================
# MARKET DATA FETCHERS
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
        start_time = end_time - (35 * 60 * 1000)
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

# ============================================================================
# SHORT, PUNCHY & DYNAMIC AI VERDICT ENGINE
# ============================================================================
def build_sharp_dynamic_verdict(rep):
    """Creates a crisp, non-boring 3-line actionable flash note from live microstructure"""
    m30 = rep["m30"]
    m5 = rep["m5"]
    px = rep["px"]
    vwap = rep["vwap"] if rep["vwap"] > 0 else px
    score = rep["score"]
    v_list = rep["recent_voids"]
    tape_shift = m5["tape_buy"] - m30["tape_buy"]

    # Line 1: Direct Action Call
    if rep["lock_state"] == "BUY":
        call_line = f"🎯 **स्पष्ट सिग्नल — BUY (LONG) @ ${px:,.0f}:** 30m और 5m दोनों में बायर लॉक हैं (स्कोर: {score:+d})। स्टॉप-लॉस ${min(vwap-40, m5['low']-25):,.0f} के नीचे रखें, टारगेट +200 से +350 पॉइंट्स।"
    elif rep["lock_state"] == "SELL":
        call_line = f"🎯 **स्पष्ट सिग्नल — SELL (SHORT) @ ${px:,.0f}:** मार्केट पर सेलर्स का सीधा कब्ज़ा है (स्कोर: {score:+d})। स्टॉप-लॉस ${max(vwap+40, m5['high']+25):,.0f} के ऊपर रखें, टारगेट +200 से +350 पॉइंट्स।"
    else:
        need_pts = 45 - abs(score)
        if abs(tape_shift) >= 8:
            call_line = f"✋ **स्पष्ट सिग्नल — WAIT (अभी ट्रेड न लें):** 30m और आखिरी 5m की दिशा आपस में टकरा रही है ({tape_shift:+.0f}% Shift)। कन्फर्म सिग्नल लॉक होने के लिए {need_pts} पॉइंट्स की मजबूती और चाहिए।"
        else:
            call_line = f"✋ **स्पष्ट सिग्नल — NO TRADE (शांत बैठें):** अभी मार्केट रेंज (${m5['low']:,.0f} – ${m5['high']:,.0f}) में फँसा है। फीस बचाएं, ब्रेकआउट पर ही सिग्नल लॉक होगा।"

    # Line 2: 5m vs 30m Dynamic Action
    if m5["tape_buy"] >= 58 and m5["px_chg"] < -10:
        flow_line = f"🧊 **व्हेल ट्रैप पकड़ा गया:** आखिरी 5m में {m5['tape_buy']:.0f}% मार्केट बाइंग के बावजूद प्राइस {m5['px_chg']:+.0f}$ गिरा—ऊपर व्हेल्स माल चिपका रही हैं!"
    elif m5["tape_buy"] <= 42 and m5["px_chg"] > 10:
        flow_line = f"🧊 **व्हेल अब्जॉर्प्शन पकड़ा गया:** आखिरी 5m में {100-m5['tape_buy']:.0f}% मार्केट सेलिंग के बावजूद प्राइस {m5['px_chg']:+.0f}$ चढ़ा—नीचे व्हेल्स सारा माल बटोर रही हैं!"
    elif tape_shift >= 6:
        flow_line = f"⚡ **ताज़ा हमला:** आखिरी 5 मिनट में अचानक बाइंग {m30['tape_buy']:.0f}% से उछलकर {m5['tape_buy']:.0f}% पर आ गई है (5m मूव: {m5['px_chg']:+.0f} Pts)।"
    elif tape_shift <= -6:
        flow_line = f"⚡ **ताज़ा बिकवाली:** आखिरी 5 मिनट में सेलिंग प्रेशर अचानक तेज़ हुआ है (Buy Tape गिरकर {m5['tape_buy']:.0f}% रह गया, 5m मूव: {m5['px_chg']:+.0f} Pts)।"
    else:
        flow_line = f"⚡ **फ्लो स्टेटस:** 30m Tape ({m30['tape_buy']:.0f}% Buy) और 5m Tape ({m5['tape_buy']:.0f}% Buy) स्थिर हैं | VWAP (${vwap:,.0f}) से दूरी: {px-vwap:+.0f} Pts।"

    # Line 3: Spread & Orderbook Reaction
    if v_list:
        lv = v_list[0]
        void_line = f"🌪️ **स्प्रेड एक्स-रे ({lv['time']}):** ${lv['spread']:.1f} का स्प्रेड फटा (प्राइस {lv['px_jump']:+.1f}$), L2 Bids {lv['l2_before']:.0f}% से {lv['l2_after']:.0f}% हुईं — {lv['ob_reaction']}।"
    else:
        void_line = f"🌪️ **स्प्रेड एक्स-रे:** हाल में $4+ का कोई स्प्रेड नहीं फटा; L2 ऑर्डरबुक में अभी {m5['l2_buy']:.0f}% Bids बनाम {100-m5['l2_buy']:.0f}% Asks खड़ी हैं।"

    return f"{call_line}\n{flow_line}\n{void_line}"

def run_ai_forensic_analysis(api_key, rep, eng):
    m30 = rep["m30"]
    m5 = rep["m5"]
    lv_txt = "कोई बड़ा स्प्रेड नहीं"
    if rep["recent_voids"]:
        lv = rep["recent_voids"][0]
        lv_txt = f"{lv['time']} पर Spread ${lv['spread']:.1f}, Price Jump {lv['px_jump']:+.1f}$, L2 Bids {lv['l2_before']:.0f}% से {lv['l2_after']:.0f}% ({lv['ob_reaction']})"

    prompt = f"""
तुम एक शार्प इंट्राडे BTC क्वांट कमांडर हो। बोरिंग या लंबी भाषा बिल्कुल मत लिखना।
लाइव डेटा:
- वर्तमान प्राइस: ${rep['px']:,.1f} | VWAP: ${rep['vwap']:,.1f} | सिस्टम लॉक स्टेटस: {rep['lock_state']} (स्कोर: {rep['score']:+d}/100)
- पूरे 30m डेटा: Price {m30['px_chg']:+.1f}p | Taker Buy {m30['tape_buy']:.0f}% | L2 Bids {m30['l2_buy']:.0f}%
- आखिरी 5m डेटा: Price {m5['px_chg']:+.1f}p (High: ${m5['high']:,.0f}, Low: ${m5['low']:,.0f}) | Taker Buy {m5['tape_buy']:.0f}% | L2 Bids {m5['l2_buy']:.0f}%
- आखिरी बड़ा स्प्रेड: {lv_txt}

सिर्फ 3 छोटी, पंचिंग लाइनों में जवाब दो (हर लाइन अधिकतम 20-25 शब्द):
🎯 **सीधा सिग्नल:** (साफ लिखो: 'कन्फर्म BUY करें', 'कन्फर्म SELL करें', या 'अभी कोई ट्रेड मत लो - WAIT' + सटीक लेवल)
⚡ **5m बनाम 30m हलचल:** (आखिरी 5 मिनट में व्हेल्स ने क्या बदला?)
🌪️ **स्प्रेड और ऑर्डरबुक असर:** (स्प्रेड और L2 दीवारों से क्या पता चला?)
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.45, "maxOutputTokens": 220}
    }

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    for mod in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=7)
            if res.status_code == 200:
                txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                eng["ai_opinion"] = txt
                eng["ai_status"] = f"🟢 Live AI ({mod})"
                return
        except Exception:
            continue

    eng["ai_opinion"] = build_sharp_dynamic_verdict(rep)
    eng["ai_status"] = "⚡ Instant Quant Flash"

# ============================================================================
# REPORT BUILDER & CONFIRMED SIGNAL HISTORY TRACKER
# ============================================================================
def compute_slice_metrics(slice_data):
    if not slice_data:
        return {"px_chg": 0.0, "high": 0.0, "low": 0.0, "tape_buy": 50.0, "l2_buy": 50.0}
    t_b = sum(d["t_buy"] for d in slice_data)
    t_s = sum(d["t_sell"] for d in slice_data)
    w_b = sum(d["w_bid"] for d in slice_data)
    w_a = sum(d["w_ask"] for d in slice_data)
    return {
        "px_chg": slice_data[-1]["px"] - slice_data[0]["px"],
        "high": max(d["px"] for d in slice_data),
        "low": min(d["px"] for d in slice_data),
        "tape_buy": (t_b / (t_b + t_s) * 100.0) if (t_b + t_s) > 0 else 50.0,
        "l2_buy": (w_b / (w_b + w_a) * 100.0) if (w_b + w_a) > 0 else 50.0
    }

def build_report_now(eng, now_ts, ist_str):
    vault = eng["vault"]
    if len(vault) < 5:
        return

    px = eng["px"]
    span_min = max(0.5, (now_ts - vault[0]["ts"]) / 60.0)
    vault_5m = [d for d in vault if (now_ts - d["ts"]) <= 300.0]

    m30 = compute_slice_metrics(vault)
    m5 = compute_slice_metrics(vault_5m)

    score = 0
    score += int(max(-25.0, min(25.0, (m30["tape_buy"] - 50.0) * 1.8)))
    score += int(max(-15.0, min(15.0, (m30["l2_buy"] - 50.0) * 1.1)))
    score += int(max(-20.0, min(20.0, (m5["tape_buy"] - 50.0) * 1.5)))
    score += int(max(-15.0, min(15.0, (m5["l2_buy"] - 50.0) * 1.0)))

    if eng["vwap"] > 0:
        if px > eng["vwap"] + 15 and m5["px_chg"] >= 0:
            score += 15
        elif px < eng["vwap"] - 15 and m5["px_chg"] <= 0:
            score -= 15

    voids_30m = [v for v in eng["voids"] if (now_ts - v.get("ts", now_ts)) <= 1800]
    bull_voids = sum(1 for v in voids_30m if v["cls"] == "ic-bull")
    bear_voids = sum(1 for v in voids_30m if v["cls"] == "ic-bear")
    if bull_voids >= bear_voids + 2:
        score += 10
    elif bear_voids >= bull_voids + 2:
        score -= 10

    score = max(-100, min(100, score))

    # HYSTERESIS SIGNAL LOCKING
    prev_lock = eng.get("lock_state", "WAIT")
    new_lock = prev_lock

    has_min_data = (span_min >= 1.5)
    both_bull = (m30["tape_buy"] >= 53.0 and m5["tape_buy"] >= 54.0 and px >= eng["vwap"])
    both_bear = (m30["tape_buy"] <= 47.0 and m5["tape_buy"] <= 46.0 and px <= eng["vwap"])

    if not has_min_data:
        new_lock = "WAIT"
    elif prev_lock == "BUY":
        if score < 15 or m5["tape_buy"] <= 43.0:
            new_lock = "SELL" if (score <= -45 and both_bear) else "WAIT"
    elif prev_lock == "SELL":
        if score > -15 or m5["tape_buy"] >= 57.0:
            new_lock = "BUY" if (score >= 45 and both_bull) else "WAIT"
    else:
        if score >= 45 and both_bull:
            new_lock = "BUY"
        elif score <= -45 and both_bear:
            new_lock = "SELL"
        else:
            new_lock = "WAIT"

    # RECORD CONFIRMED SIGNAL HISTORY WHEN A NEW SIGNAL LOCKS
    if new_lock != prev_lock:
        # Close previous active signal in history if any
        if eng["signal_history"] and eng["signal_history"][0]["status"] == "ACTIVE":
            eng["signal_history"][0]["status"] = f"CLOSED ({ist_str})"

        if new_lock in ["BUY", "SELL"]:
            eng["sound_event"] = {"id": now_ts, "type": "BULL" if new_lock == "BUY" else "BEAR"}
            sig_reason = f"30m Tape {m30['tape_buy']:.0f}% | 5m Tape {m5['tape_buy']:.0f}% | Score {score:+d}"
            eng["signal_history"].insert(0, {
                "time": ist_str,
                "type": new_lock,
                "entry": px,
                "score": score,
                "reason": sig_reason,
                "live_pts": 0.0,
                "peak_pts": 0.0,
                "status": "ACTIVE"
            })
            eng["signal_history"] = eng["signal_history"][:30]

    eng["lock_state"] = new_lock

    if new_lock == "BUY":
        lock_title = "🟢 कन्फर्म BUY सिग्नल लॉक (CONFIRMED LONG)"
        lock_cls = "lock-buy"
        lock_sub = f"30m और 5m दोनों में बायर हावी हैं। जब तक स्कोर +15 के ऊपर है, यह सिग्नल नहीं पलटेगा।"
    elif new_lock == "SELL":
        lock_title = "🔴 कन्फर्म SELL सिग्नल लॉक (CONFIRMED SHORT)"
        lock_cls = "lock-sell"
        lock_sub = f"30m और 5m दोनों में सेलर हावी हैं। जब तक स्कोर -15 के नीचे है, यह सिग्नल नहीं पलटेगा।"
    else:
        lock_title = "⚪ कोई कन्फर्म सिग्नल नहीं (WAIT — शांत बैठें)"
        lock_cls = "lock-wait"
        lock_sub = f"कन्फर्म सिग्नल तभी लॉक होगा जब स्कोर ±45 पार करेगा (अभी स्कोर: {score:+d}/100)।"

    rep_obj = {
        "time": ist_str, "px": px, "vwap": eng["vwap"], "span_min": span_min,
        "m30": m30, "m5": m5, "score": score,
        "lock_state": new_lock, "lock_title": lock_title, "lock_cls": lock_cls, "lock_sub": lock_sub,
        "bull_voids": bull_voids, "bear_voids": bear_voids, "recent_voids": voids_30m[:8]
    }
    eng["report"] = rep_obj
    eng["last_report_ts"] = now_ts

    # Update Sharp Verdict Immediately + Trigger Live AI if key exists
    eng["ai_opinion"] = build_sharp_dynamic_verdict(rep_obj)
    api_key = eng.get("api_key", "").strip()
    if api_key:
        threading.Thread(target=run_ai_forensic_analysis, args=(api_key, rep_obj, eng), daemon=True).start()

# ============================================================================
# 24x7 BACKGROUND WORKER
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
                spread = snap["spread"]
                w_bid, w_ask = snap["w_bid"], snap["w_ask"]
                curr_l2_pct = (w_bid / (w_bid + w_ask) * 100.0) if (w_bid + w_ask) > 0 else 50.0
                curr_tape_pct = (snap["t_buy"] / (snap["t_buy"] + snap["t_sell"]) * 100.0) if (snap["t_buy"] + snap["t_sell"]) > 0 else 50.0

                recent_5_ticks = eng["vault"][-5:] if len(eng["vault"]) >= 2 else []
                if recent_5_ticks:
                    pre_b = sum(d["w_bid"] for d in recent_5_ticks)
                    pre_a = sum(d["w_ask"] for d in recent_5_ticks)
                    pre_l2_pct = (pre_b / (pre_b + pre_a) * 100.0) if (pre_b + pre_a) > 0 else curr_l2_pct
                    prev_px = eng["vault"][-1]["px"]
                else:
                    pre_l2_pct = curr_l2_pct
                    prev_px = px

                eng["px"] = px
                eng["last_update"] = ist_str

                # Update Live Points on Active Confirmed Signal in History
                if eng["signal_history"] and eng["signal_history"][0]["status"] == "ACTIVE":
                    top_sig = eng["signal_history"][0]
                    move = (px - top_sig["entry"]) if top_sig["type"] == "BUY" else (top_sig["entry"] - px)
                    top_sig["live_pts"] = move
                    top_sig["peak_pts"] = max(top_sig["peak_pts"], move)

                eng["vault"].append({
                    "ts": now_ts, "px": px,
                    "w_bid": w_bid, "w_ask": w_ask,
                    "t_buy": snap["t_buy"], "t_sell": snap["t_sell"]
                })
                eng["vault"] = [d for d in eng["vault"] if (now_ts - d["ts"]) <= VAULT_MEMORY_SEC]

                if spread >= SPREAD_VOID_THRESHOLD:
                    px_jump = px - prev_px
                    l2_shift = curr_l2_pct - pre_l2_pct

                    if curr_tape_pct >= 58 and l2_shift >= 4:
                        cls = "ic-bull"; ob_reaction = "🟢 बायर्स ने आस्क तोड़ी और नीचे बिड्स बढ़ाईं"
                    elif curr_tape_pct <= 42 and l2_shift <= -4:
                        cls = "ic-bear"; ob_reaction = "🔴 सेलर्स ने बिड्स तोड़ीं और ऊपर आस्क बढ़ाईं"
                    elif l2_shift <= -8:
                        cls = "ic-warn"; ob_reaction = "⚠️ स्प्रेड फटते ही बायर्स ने डरकर बिड ऑर्डर हटाए"
                    elif l2_shift >= 8:
                        cls = "ic-warn"; ob_reaction = "⚠️ स्प्रेड फटते ही सेलर्स ने ऊपर से आस्क ऑर्डर हटाए"
                    else:
                        cls = "ic-bull" if curr_tape_pct >= 52 else "ic-bear"
                        ob_reaction = "⚡ तेज़ मार्केट ऑर्डर से ऑर्डरबुक में गैप बना"

                    void_obj = {
                        "ts": now_ts, "time": ist_str, "spread": spread, "px": px,
                        "px_jump": px_jump, "l2_before": pre_l2_pct, "l2_after": curr_l2_pct,
                        "l2_shift": l2_shift, "tape_pct": curr_tape_pct,
                        "ob_reaction": ob_reaction, "cls": cls
                    }
                    if not eng["voids"] or eng["voids"][0]["time"] != ist_str:
                        eng["voids"].insert(0, void_obj)
                        eng["voids"] = eng["voids"][:45]
                        if spread >= 5.5:
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
def get_master_engine_v11_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "signal_history": [],
        "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "lock_state": "WAIT", "report": None,
        "ai_opinion": "⏳ पहली रिपोर्ट बनते ही शॉर्ट और सटीक सिग्नल रिपोर्ट यहाँ दिखेगी...",
        "ai_status": "⚡ Auto-Active", "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v11_0()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# STATIC CONTROLS & SINGLE-CONTAINER ZERO-GHOST RENDERER
# ============================================================================
c_act1, c_act2, c_act3 = st.columns([0.26, 0.22, 0.52])
with c_act1:
    if st.button("🔄 अभी रिपोर्ट और AI रिफ्रेश करें"):
        build_report_now(eng, time.time(), get_ist_time_str())
with c_act2:
    test_snd = st.button("🔔 साउंड टेस्ट करें")
with c_act3:
    sound_enabled = st.checkbox("🔊 कन्फर्म सिग्नल लॉक होने पर साउंड अलर्ट बजाएं", value=True)

# Fixed placeholders so DOM tree NEVER shifts or creates ghost duplicate boxes on scroll
dashboard_slot = st.empty()
audio_slot = st.empty()

if test_snd:
    b64 = create_sound_b64("BULL")
    with audio_slot:
        components.html(f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>', height=0, width=0)

curr_snd = eng.get("sound_event", {"id": 0.0, "type": "BULL"})
if sound_enabled and curr_snd["id"] > 0 and curr_snd["id"] != st.session_state["last_played_sound_id"]:
    st.session_state["last_played_sound_id"] = curr_snd["id"]
    b64 = create_sound_b64(curr_snd["type"])
    with audio_slot:
        components.html(f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>', height=0, width=0)

if eng["px"] > 0:
    mem_min = (time.time() - eng["vault"][0]["ts"]) / 60.0 if len(eng["vault"]) > 1 else 0.0

    # 1. Build Confirmed Signal History HTML
    hist_cards = ""
    for h in eng["signal_history"]:
        h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
        h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
        p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
        sts_badge = "🟢 ACTIVE" if h["status"] == "ACTIVE" else f"🏁 {h['status']}"
        hist_cards += f"""
        <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <b style='color:{h_col}; font-size:13.5px;'>{h["time"]} — CONFIRMED {h["type"]} @ ${h["entry"]:,.1f}</b>
                <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span><br>
                <span style='color:#94a3b8; font-size:12px;'>{h["reason"]}</span>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:14.5px; font-weight:900; color:{p_col};'>{h["live_pts"]:+.1f}p</div>
                <div style='font-size:11px; color:#38bdf8;'>Peak: +{h["peak_pts"]:.1f}p</div>
            </div>
        </div>
        """
    if not hist_cards:
        hist_cards = "<div style='text-align:center; color:#64748b; padding-top:65px;'>अभी तक कोई कन्फर्म सिग्नल (Score ±45) लॉक नहीं हुआ है।<br>जैसे ही पक्का सिग्नल आएगा, उसका समय और प्राइस यहाँ दर्ज हो जाएगा।</div>"

    # 2. Build Void Postmortem HTML
    void_cards = ""
    for v in eng["voids"]:
        j_col = "#4ade80" if v["px_jump"] >= 0 else "#f87171"
        s_col = "#4ade80" if v["l2_shift"] >= 0 else "#f87171"
        void_cards += f"""
        <div class='item-card {v["cls"]}'>
            <div style='display:flex; justify-content:space-between; font-weight:800; color:#f8fafc;'>
                <span>🕒 {v["time"]} | Spread: <b style='color:#facc15;'>${v["spread"]:.1f}</b></span>
                <span style='color:{j_col};'>Jump: {v["px_jump"]:+.1f}$</span>
            </div>
            <div style='color:#cbd5e1; margin-top:3px;'>
                <b>L2 बदलाव:</b> {v["l2_before"]:.0f}% ➔ <b>{v["l2_after"]:.0f}% Bid</b> (<span style='color:{s_col}; font-weight:bold;'>{v["l2_shift"]:+.0f}%</span>) | <b>Tape:</b> {v["tape_pct"]:.0f}% B
            </div>
            <div style='color:#38bdf8; font-size:11.8px; margin-top:2px; font-weight:600;'>{v["ob_reaction"]}</div>
        </div>
        """
    if not void_cards:
        void_cards = "<div style='text-align:center; color:#64748b; padding-top:180px;'>अभी $4.0 से बड़ा कोई स्प्रेड नहीं फटा है।</div>"

    # 3. Build Left Main Section
    if eng["report"]:
        r = eng["report"]
        m30 = r["m30"]
        m5 = r["m5"]
        sc_col = "#4ade80" if r["score"] >= 45 else ("#f87171" if r["score"] <= -45 else "#facc15")
        c30_col = "#4ade80" if m30["px_chg"] >= 0 else "#f87171"
        c5_col = "#4ade80" if m5["px_chg"] >= 0 else "#f87171"

        left_body = f"""
        <div class='lock-banner {r["lock_cls"]}'>
            <div>
                <div style='font-size:18.5px; font-weight:900;'>{r["lock_title"]}</div>
                <div style='font-size:12.5px; margin-top:3px; opacity:0.92;'>{r["lock_sub"]}</div>
            </div>
            <div style='text-align:right; min-width:130px;'>
                <div style='font-size:11px; text-transform:uppercase; opacity:0.8;'>Conviction Score</div>
                <div style='font-size:24px; font-weight:900; color:{sc_col};'>{r["score"]:+d} / 100</div>
                <div style='font-size:11px; opacity:0.8;'>अपडेट: {r["time"]}</div>
            </div>
        </div>

        <div class='ai-sharp-box'>
            <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3b0764; padding-bottom:6px; margin-bottom:8px;'>
                <span style='font-size:15px; font-weight:900; color:#c084fc;'>🤖 शॉर्ट AI कमांड रिपोर्ट (30m + 5m + स्प्रेड निचोड़)</span>
                <span style='font-size:11.5px; color:#4ade80; font-weight:bold;'>{eng["ai_status"]}</span>
            </div>
            <div style='font-size:14.2px; line-height:1.65; color:#f8fafc; white-space:pre-line;'>{eng["ai_opinion"]}</div>
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🏛️ 1. पूरे {r["span_min"]:.0f}m का बेस डेटा</span>
                    <span style='color:{c30_col};'>{m30["px_chg"]:+.1f} Pts</span>
                </div>
                <div class='stat-row'><span>30m Taker Tape:</span><b><span style='color:#4ade80;'>{m30["tape_buy"]:.0f}% Buy</span> / <span style='color:#f87171;'>{100-m30["tape_buy"]:.0f}% Sell</span></b></div>
                <div class='stat-row'><span>30m L2 Orderbook:</span><b><span style='color:#4ade80;'>{m30["l2_buy"]:.0f}% Bid</span> / <span style='color:#f87171;'>{100-m30["l2_buy"]:.0f}% Ask</span></b></div>
                <div class='stat-row' style='border:none;'><span>30m रेंज एवं VWAP:</span><b>${m30["low"]:,.0f}–${m30["high"]:,.0f} (VWAP: ${r["vwap"]:,.0f})</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>⚡ 2. आखिरी 5m का ताज़ा ट्रिगर</span>
                    <span style='color:{c5_col};'>{m5["px_chg"]:+.1f} Pts</span>
                </div>
                <div class='stat-row'><span>आखिरी 5m Taker Tape:</span><b><span style='color:#4ade80;'>{m5["tape_buy"]:.0f}% Buy</span> ({m5["tape_buy"]-m30["tape_buy"]:+.0f}% Shift)</b></div>
                <div class='stat-row'><span>आखिरी 5m L2 Orderbook:</span><b><span style='color:#4ade80;'>{m5["l2_buy"]:.0f}% Bid</span> ({m5["l2_buy"]-m30["l2_buy"]:+.0f}% Shift)</b></div>
                <div class='stat-row' style='border:none;'><span>5m हाई / लो रेंज:</span><b>${m5["low"]:,.0f} — ${m5["high"]:,.0f}</b></div>
            </div>
        </div>
        """
    else:
        pct = min(100, int((len(eng["vault"]) / 10) * 100))
        left_body = f"""
        <div class='card-box' style='text-align:center; padding:45px 20px; margin-bottom:12px;'>
            <div style='font-size:20px; font-weight:800; color:#38bdf8; margin-bottom:8px;'>⏳ शुरुआती डेटा जमा हो रहा है... ({pct}%)</div>
            <div style='font-size:14px; color:#94a3b8;'>तुरंत रिपोर्ट देखने के लिए ऊपर <b>'🔄 अभी रिपोर्ट और AI रिफ्रेश करें'</b> बटन दबाएं।</div>
        </div>
        """

    # Render EVERYTHING inside ONE single container so scrolling never duplicates boxes
    dashboard_slot.markdown(clean_html(f"""
    <div>
        <div class='top-bar'>
            <div>
                <span style='font-size:21px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V11.0 (ZERO-GHOST WAR ROOM)</span>
                <span style='font-size:13px; color:#94a3b8; margin-left:14px;'>🗄️ मेमोरी: <b style='color:#facc15;'>{mem_min:.1f} / 30.0 Min</b></span>
            </div>
            <div>
                <span style='font-size:22px; font-weight:900; color:#f8fafc; margin-right:16px;'>BTC: ${eng['px']:,.1f}</span>
                <span style='color:#4ade80; font-size:13px; font-weight:bold;'>● {eng['last_update']}</span>
            </div>
        </div>

        <div class='main-grid'>
            <div>
                {left_body}
                <div class='history-panel'>
                    <div style='font-size:14px; font-weight:900; color:#4ade80; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        📜 कन्फर्म सिग्नल हिस्ट्री लॉग (कब आया, किस प्राइस पर, कितना चला)
                    </div>
                    {hist_cards}
                </div>
            </div>

            <div class='void-panel'>
                <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                    🌪️ स्प्रेड एवं ऑर्डरबुक पोस्टमार्टम (Spread > $4.0)
                </div>
                {void_cards}
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    dashboard_slot.warning("⏳ 24x7 V11.0 स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

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

st.set_page_config(page_title="Pro Quant V10.0 - Institutional War Room", layout="wide")

def clean_html(raw_html: str) -> str:
    """Removes leading spaces per line so Streamlit Markdown never breaks or scatters HTML boxes"""
    return "\n".join(line.lstrip() for line in raw_html.splitlines() if line.strip())

st.markdown(clean_html("""
<style>
.stApp { background-color: #090d16; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.2rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
.top-bar { background: #111827; border: 1px solid #1f2937; border-bottom: 2px solid #38bdf8; padding: 14px 20px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.lock-banner { padding: 16px 20px; border-radius: 10px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; }
.lock-buy { background: #052e16; border: 2px solid #22c55e; color: #4ade80; }
.lock-sell { background: #450a0a; border: 2px solid #ef4444; color: #f87171; }
.lock-wait { background: #1e293b; border: 2px dashed #64748b; color: #cbd5e1; }
.grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.horizon-card { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 14px 16px; }
.horizon-title { font-size: 13px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 10px; border-bottom: 1px solid #1f2937; padding-bottom: 6px; display: flex; justify-content: space-between; }
.stat-line { display: flex; justify-content: space-between; font-size: 13.5px; padding: 5px 0; border-bottom: 1px dashed #1f2937; }
.ai-panel { background: #0f172a; border: 1px solid #a855f7; border-left: 5px solid #a855f7; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
.void-panel { background: #111827; border: 1px solid #334155; border-top: 4px solid #facc15; border-radius: 10px; padding: 14px; height: 640px; overflow-y: auto; }
.void-card { background: #090d16; border: 1px solid #1f2937; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; font-size: 12.8px; line-height: 1.45; }
.vc-bull { border-left: 4px solid #22c55e; }
.vc-bear { border-left: 4px solid #ef4444; }
.vc-pull { border-left: 4px solid #facc15; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
</style>
"""), unsafe_allow_html=True)

# ============================================================================
# IN-BUILT SOUND ALERT SYNTHESIZER
# ============================================================================
def create_sound_b64(tone_type="BULL"):
    sample_rate = 22050
    buf = io.BytesIO()
    if tone_type == "BULL":
        notes = [(784, 0.14), (0, 0.04), (1046, 0.16), (0, 0.04), (1318, 0.24)]
    elif tone_type == "BEAR":
        notes = [(659, 0.16), (0, 0.04), (523, 0.16), (0, 0.04), (392, 0.26)]
    elif tone_type == "VOID":
        notes = [(1175, 0.12)]
    else:
        notes = [(587, 0.14)]

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
                    fade = 1.0 - (i / n_samples) * 0.5
                    val = int(15000.0 * fade * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                frames.extend(struct.pack('<h', val))
        wf.writeframes(bytes(frames))
    return base64.b64encode(buf.getvalue()).decode('ascii')

def trigger_browser_audio(tone_type="BULL"):
    b64_wav = create_sound_b64(tone_type)
    components.html(f'<audio autoplay="true" style="display:none;"><source src="data:audio/wav;base64,{b64_wav}" type="audio/wav"></audio>', height=0, width=0)

# ============================================================================
# MARKET DATA FETCHERS (HYPERLIQUID L2, TAPE, OI & VWAP)
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

        near_bid = sum(float(b["sz"]) for b in bids[:5])
        near_ask = sum(float(a["sz"]) for a in asks[:5])

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
            "near_bid": near_bid, "near_ask": near_ask,
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
# DEEP AI FORENSIC ENGINE (30M BASE + 5M SHIFT + VOID ORDERBOOK FORENSICS)
# ============================================================================
def discover_working_models(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            models = r.json().get("models", [])
            valid = []
            for m in models:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and ("2.5-flash" in name or "2.0-flash" in name or "flash" in name):
                    valid.append(name)
            return valid
    except:
        pass
    return []

def build_dynamic_forensic_fallback(rep):
    """Dynamic data-driven forensic synthesis if API is unreachable"""
    m30 = rep["m30"]
    m5 = rep["m5"]
    v_list = rep["recent_voids"]

    shift_txt = (
        f"पिछले 30 मिनट में कुल मार्केट बाइंग {m30['tape_buy']:.0f}% (प्राइस {m30['px_chg']:+.0f} Pts) रही, "
        f"जबकि आखिरी 5 मिनट में Taker बाइंग {m5['tape_buy']:.0f}% और L2 ऑर्डरबुक बाइंग {m5['l2_buy']:.0f}% पर है (5m प्राइस बदलाव: {m5['px_chg']:+.0f} Pts)।"
    )

    if v_list:
        lv = v_list[0]
        void_txt = (
            f"सबसे ताज़ा बड़ा स्प्रेड {lv['time']} पर ${lv['spread']:.1f} का फटा (प्राइस {lv['px_jump']:+.1f}$ चला), "
            f"जिसमें ऑर्डरबुक L2 Bids {lv['l2_before']:.0f}% से बदलकर {lv['l2_after']:.0f}% हो गईं ({lv['ob_reaction']})।"
        )
    else:
        void_txt = "पिछले कुछ मिनटों में $4.0 से ऊपर का कोई बड़ा लिक्विडिटी वॉइड नहीं फटा है, यानी ऑर्डरबुक में लिक्विडिटी स्थिर है।"

    if rep["lock_state"] == "BUY":
        act_txt = "✅ कन्फर्म निर्णय: 30m बेस और आखिरी 5m का मोमेंटम दोनों बायर्स के कब्जे में हैं। केवल VWAP या डिप सपोर्ट पर LONG देखें।"
    elif rep["lock_state"] == "SELL":
        act_txt = "✅ कन्फर्म निर्णय: 30m और आखिरी 5m दोनों में सेलर्स हावी हैं। किसी भी उछाल पर रेजिस्टेंस के पास SHORT की तलाश करें।"
    else:
        act_txt = "🚫 कन्फर्म निर्णय (NO TRADE): अभी 30m के बड़े डेटा और आखिरी 5m के डेटा में एकतरफा तालमेल नहीं है। कन्फ्यूजन से बचने के लिए अभी कोई ट्रेड न लें।"

    return f"• **30m बनाम 5m तुलना:** {shift_txt}\n• **स्प्रेड और ऑर्डरबुक जांच:** {void_txt}\n• **फाइनल एक्शन:** {act_txt}"

def run_ai_forensic_analysis(api_key, rep, eng):
    m30 = rep["m30"]
    m5 = rep["m5"]
    void_lines = []
    for v in rep["recent_voids"][:5]:
        void_lines.append(
            f"- समय {v['time']}: Spread ${v['spread']:.1f} | प्राइस झटका: {v['px_jump']:+.1f}$ | "
            f"L2 Orderbook बदलाव: पहले {v['l2_before']:.0f}% Buy था -> स्प्रेड पर {v['l2_after']:.0f}% हुआ ({v['l2_shift']:+.0f}%) | "
            f"उस पल Taker Buy: {v['tape_pct']:.0f}% | असर: {v['ob_reaction']}"
        )
    void_block = "\n".join(void_lines) if void_lines else "- इस दौरान $4.0 से बड़ा कोई स्प्रेड नहीं आया।"

    prompt = f"""
तुम एक इंस्टीट्यूशनल क्रिप्टो माइक्रोस्ट्रक्चर एनालिस्ट हो। नीचे दिए गए दो अलग-अलग टाइमफ्रेम (पूरे 30 मिनट बनाम आखिरी 5 मिनट) और बड़े स्प्रेड्स (Liquidity Voids) के डेटा का सटीक विश्लेषण करो:

1. पूरे 30 मिनट का मैक्रो डेटा (Macro Base - {rep['span_min']:.1f} mins collected):
   - कुल प्राइस बदलाव: {m30['px_chg']:+.1f} Pts (High: ${m30['high']:,.0f}, Low: ${m30['low']:,.0f})
   - 30m असली मार्केट सौदे (Taker Tape): {m30['tape_buy']:.1f}% Buy / {100-m30['tape_buy']:.1f}% Sell
   - 30m ऑर्डरबुक दीवारें (L2 Weighted): {m30['l2_buy']:.1f}% Bids / {100-m30['l2_buy']:.1f}% Asks
   - VWAP लेवल: ${rep['vwap']:,.1f} (वर्तमान प्राइस: ${rep['px']:,.1f})

2. आखिरी 5 मिनट का ताज़ा बदलाव (Recent 5-Min Momentum Shift):
   - आखिरी 5m में प्राइस बदलाव: {m5['px_chg']:+.1f} Pts
   - आखिरी 5m में Taker Tape: {m5['tape_buy']:.1f}% Buy (30m की तुलना में {m5['tape_buy']-m30['tape_buy']:+.1f}% बदलाव)
   - आखिरी 5m में L2 Orderbook: {m5['l2_buy']:.1f}% Bids (30m की तुलना में {m5['l2_buy']-m30['l2_buy']:+.1f}% बदलाव)

3. बड़े स्प्रेड्स (Spread > $4.0) और उस समय ऑर्डरबुक में हुआ बदलाव:
{void_block}

4. सिस्टम का वर्तमान लॉक स्टेटस: {rep['lock_title']} (Conviction Score: {rep['score']:+d}/100)

निर्देश:
हमेशा एक जैसी रटी-रटाई बात मत लिखो। ऊपर के सटीक नंबरों का हवाला देते हुए ठीक 3 बुलेट पॉइंट्स में हिंदी में जवाब दो:
• **30m बनाम आखिरी 5m की तुलना:** क्या आखिरी 5 मिनट में ताकत बदली है या 30 मिनट वाला ट्रेंड ही और मजबूत हुआ है?
• **बड़े स्प्रेड पर ऑर्डरबुक का पोस्टमार्टम:** जब बड़ा स्प्रेड आया तो ऑर्डरबुक में बिड्स/आस्क किसने हटाए और किसने मार्केट ऑर्डर मारे?
• **सटीक फैसला (Confirmed Signal या Wait):** अगर 30m और 5m दोनों एक साथ मजबूत हैं तभी साफ शब्दों में 'कन्फर्म BUY' या 'कन्फर्म SELL' बोलो, वरना साफ मना करो कि 'अभी कोई ट्रेड मत लो, इंतजार करो'।
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.35}
    }

    priority_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
    for dm in discover_working_models(api_key):
        if dm not in priority_models:
            priority_models.append(dm)

    for mod in priority_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=9)
            if res.status_code == 200:
                txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                eng["ai_opinion"] = txt
                eng["ai_status"] = f"🟢 Live AI ({mod})"
                return
            elif res.status_code == 503:
                time.sleep(1.0)
                continue
        except Exception:
            continue

    eng["ai_opinion"] = build_dynamic_forensic_fallback(rep)
    eng["ai_status"] = "🟡 Quant Forensic Engine"

# ============================================================================
# DUAL-HORIZON & HYSTERESIS REPORT BUILDER (ANTI-FLIP-FLOP)
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

    # Calculate Conviction Score (-100 to +100) combining 30m Base + 5m Confirmation + Voids
    score = 0
    # 1. 30-Minute Macro Base Weight (Max ±40)
    score += int(max(-25.0, min(25.0, (m30["tape_buy"] - 50.0) * 1.8)))
    score += int(max(-15.0, min(15.0, (m30["l2_buy"] - 50.0) * 1.1)))

    # 2. Last 5-Minute Micro Alignment Weight (Max ±35)
    score += int(max(-20.0, min(20.0, (m5["tape_buy"] - 50.0) * 1.5)))
    score += int(max(-15.0, min(15.0, (m5["l2_buy"] - 50.0) * 1.0)))

    # 3. Price vs VWAP & Momentum Structure (Max ±15)
    if eng["vwap"] > 0:
        if px > eng["vwap"] + 15 and m5["px_chg"] >= 0:
            score += 15
        elif px < eng["vwap"] - 15 and m5["px_chg"] <= 0:
            score -= 15

    # 4. Void Orderbook Reaction Bonus (Max ±10)
    voids_30m = [v for v in eng["voids"] if (now_ts - v.get("ts", now_ts)) <= 1800]
    bull_voids = sum(1 for v in voids_30m if v["cls"] == "vc-bull")
    bear_voids = sum(1 for v in voids_30m if v["cls"] == "vc-bear")
    if bull_voids >= bear_voids + 2:
        score += 10
    elif bear_voids >= bull_voids + 2:
        score -= 10

    score = max(-100, min(100, score))

    # ========================================================================
    # HYSTERESIS STATE MACHINE (STOPS SIGNAL FLIP-FLOPPING)
    # ========================================================================
    prev_lock = eng.get("lock_state", "WAIT")
    new_lock = prev_lock

    # Require at least 2 minutes of data before locking any confirmed signal
    has_min_data = (span_min >= 2.0)
    both_bull_aligned = (m30["tape_buy"] >= 53.0 and m5["tape_buy"] >= 54.0 and px >= eng["vwap"])
    both_bear_aligned = (m30["tape_buy"] <= 47.0 and m5["tape_buy"] <= 46.0 and px <= eng["vwap"])

    if not has_min_data:
        new_lock = "WAIT"
    elif prev_lock == "BUY":
        # Once BUY is locked, do NOT flip on minor noise! Hold until score drops below +15 or 5m turns strongly bearish
        if score < 15 or m5["tape_buy"] <= 43.0:
            new_lock = "SELL" if (score <= -45 and both_bear_aligned) else "WAIT"
    elif prev_lock == "SELL":
        # Once SELL is locked, Hold until score rises above -15 or 5m turns strongly bullish
        if score > -15 or m5["tape_buy"] >= 57.0:
            new_lock = "BUY" if (score >= 45 and both_bull_aligned) else "WAIT"
    else:
        # From WAIT state, require strict >= +45 or <= -45 AND 30m+5m alignment
        if score >= 45 and both_bull_aligned:
            new_lock = "BUY"
        elif score <= -45 and both_bear_aligned:
            new_lock = "SELL"
        else:
            new_lock = "WAIT"

    # Sound trigger ONLY when a Confirmed Signal newly locks (or on manual refresh of active signal)
    if new_lock != prev_lock and new_lock in ["BUY", "SELL"]:
        eng["sound_event"] = {"id": now_ts, "type": "BULL" if new_lock == "BUY" else "BEAR"}

    eng["lock_state"] = new_lock

    if new_lock == "BUY":
        lock_title = "🟢 कन्फर्म बुलिश सिग्नल लॉक (CONFIRMED BUY BIAS)"
        lock_cls = "lock-buy"
        lock_sub = "30-मिनट का बेस और आखिरी 5-मिनट का फ्लो दोनों मजबूती से बायर्स के साथ हैं। छोटे उतार-चढ़ाव पर यह सिग्नल नहीं बदलेगा।"
    elif new_lock == "SELL":
        lock_title = "🔴 कन्फर्म बियरिश सिग्नल लॉक (CONFIRMED SELL BIAS)"
        lock_cls = "lock-sell"
        lock_sub = "30-मिनट का बेस और आखिरी 5-मिनट का फ्लो दोनों सेलर्स के कब्जे में हैं। छोटे उछाल पर यह सिग्नल नहीं बदलेगा।"
    else:
        if not has_min_data:
            lock_title = f"⏳ शुरुआती डेटा जमा हो रहा है ({span_min:.1f} Min) — अभी प्रतीक्षा करें"
        elif (m30["tape_buy"] > 52 and m5["tape_buy"] < 48) or (m30["tape_buy"] < 48 and m5["tape_buy"] > 52):
            lock_title = "⚪ कोई सिग्नल नहीं (30m और आखिरी 5m के डेटा में टकराव है — WAIT)"
        else:
            lock_title = "⚪ कोई सटीक सिग्नल नहीं (NO CLEAR SETUP — शांत रहें)"
        lock_cls = "lock-wait"
        lock_sub = f"कन्फर्म सिग्नल के लिए स्कोर ±45 और 30m+5m का एक साथ मिलना ज़रूरी है (अभी स्कोर: {score:+d}/100)।"

    # Diagnostic Alerts comparing 30m vs 5m
    diagnostics = []
    if m30["tape_buy"] < 47 and m5["tape_buy"] >= 56:
        diagnostics.append("🔄 **ताज़ा मोमेंटम बदलाव (Bullish Shift):** पिछले 30 मिनट में सेलर्स आगे थे, लेकिन आखिरी 5 मिनट में अचानक बायर्स ({:.0f}% Tape) ने हमला शुरू किया है।".format(m5["tape_buy"]))
    elif m30["tape_buy"] > 53 and m5["tape_buy"] <= 44:
        diagnostics.append("🔄 **ताज़ा मोमेंटम बदलाव (Bearish Shift):** 30 मिनट का डेटा पॉजिटिव था, लेकिन आखिरी 5 मिनट में सेलर्स ({:.0f}% Sell Tape) हावी हो रहे हैं।".format(100 - m5["tape_buy"]))

    if m5["tape_buy"] >= 56 and m5["px_chg"] < -15:
        diagnostics.append("🧊 **आइसबर्ग अब्जॉर्प्शन (Bearish Wall):** आखिरी 5 मिनट में मार्केट बाइंग के बावजूद प्राइस गिरा है—ऊपर व्हेल्स लिमिट ऑर्डर से माल चिपका रही हैं।")
    elif m5["tape_buy"] <= 44 and m5["px_chg"] > 15:
        diagnostics.append("🧊 **आइसबर्ग अब्जॉर्प्शन (Bullish Wall):** आखिरी 5 मिनट में भारी मार्केट सेलिंग के बावजूद प्राइस ऊपर गया है—नीचे व्हेल्स सारा माल सोख रही हैं।")

    if not diagnostics:
        diagnostics.append("✔️ **डेटा स्थिरता:** ऑर्डरबुक और टेप में कोई विरोधाभास नहीं है। जब तक स्कोर ±45 पार कर लॉक न हो, जबरदस्ती ट्रेड न लें।")

    rep_obj = {
        "time": ist_str, "px": px, "vwap": eng["vwap"], "span_min": span_min,
        "m30": m30, "m5": m5, "score": score,
        "lock_state": new_lock, "lock_title": lock_title, "lock_cls": lock_cls, "lock_sub": lock_sub,
        "bull_voids": bull_voids, "bear_voids": bear_voids,
        "diagnostics": diagnostics, "recent_voids": voids_30m[:8]
    }
    eng["report"] = rep_obj
    eng["last_report_ts"] = now_ts

    api_key = eng.get("api_key", "").strip()
    if api_key:
        eng["ai_status"] = "🤖 AI विश्लेषण कर रहा है..."
        threading.Thread(target=run_ai_forensic_analysis, args=(api_key, rep_obj, eng), daemon=True).start()
    else:
        eng["ai_opinion"] = build_dynamic_forensic_fallback(rep_obj)
        eng["ai_status"] = "🟡 Quant Forensic Engine"

# ============================================================================
# 24x7 BACKGROUND WORKER (V10.0 FORENSIC ENGINE)
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

                # Compute Pre-Void Baseline (Average of previous 5 ticks before this tick)
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

                eng["vault"].append({
                    "ts": now_ts, "px": px,
                    "w_bid": w_bid, "w_ask": w_ask,
                    "t_buy": snap["t_buy"], "t_sell": snap["t_sell"]
                })
                eng["vault"] = [d for d in eng["vault"] if (now_ts - d["ts"]) <= VAULT_MEMORY_SEC]

                # LIQUIDITY VOID & ORDERBOOK SHIFT FORENSICS
                if spread >= SPREAD_VOID_THRESHOLD:
                    px_jump = px - prev_px
                    l2_shift = curr_l2_pct - pre_l2_pct

                    if curr_tape_pct >= 58 and l2_shift >= 4:
                        cls = "vc-bull"
                        ob_reaction = "🟢 बायर्स ने आस्क दीवार तोड़ी और नीचे नई बिड्स लगाईं"
                    elif curr_tape_pct <= 42 and l2_shift <= -4:
                        cls = "vc-bear"
                        ob_reaction = "🔴 सेलर्स ने बिड्स तोड़ीं और ऊपर भारी बिकवाली रखी"
                    elif l2_shift <= -8:
                        cls = "vc-pull"
                        ob_reaction = "⚠️ स्प्रेड फटते ही बायर्स ने डरकर बिड ऑर्डर खींच लिए (Liquidity Pulled)"
                    elif l2_shift >= 8:
                        cls = "vc-pull"
                        ob_reaction = "⚠️ स्प्रेड फटते ही सेलर्स ने ऊपर से आस्क ऑर्डर हटा लिए"
                    else:
                        cls = "vc-bull" if curr_tape_pct >= 52 else "vc-bear"
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

                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and len(eng["vault"]) >= 12:
                    build_report_now(eng, now_ts, ist_str)

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_master_engine_v10_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "lock_state": "WAIT", "report": None,
        "ai_opinion": "⏳ पहली 3-मिनट रिपोर्ट बनते ही AI पूरे 30m, आखिरी 5m और स्प्रेड ऑर्डरबुक का विश्लेषण देगा...",
        "ai_status": "Auto-Active", "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v10_0()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# RENDER V10.0 UNIFIED COMMAND CENTER UI
# ============================================================================
if eng["px"] > 0:
    mem_min = (time.time() - eng["vault"][0]["ts"]) / 60.0 if len(eng["vault"]) > 1 else 0.0

    st.markdown(clean_html(f"""
    <div class='top-bar'>
        <div>
            <span style='font-size:22px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V10.0 (ANTI-FLIP & VOID FORENSIC WAR ROOM)</span>
            <span style='font-size:13px; color:#94a3b8; margin-left:14px;'>🗄️ मेमोरी बफर: <b style='color:#facc15;'>{mem_min:.1f} / 30.0 Min</b></span>
        </div>
        <div>
            <span style='font-size:23px; font-weight:900; color:#f8fafc; margin-right:18px;'>BTC: ${eng['px']:,.1f}</span>
            <span style='color:#4ade80; font-size:13.5px; font-weight:bold;'>● {eng['last_update']}</span>
        </div>
    </div>
    """), unsafe_allow_html=True)

    c_act1, c_act2, c_act3 = st.columns([0.26, 0.22, 0.52])
    with c_act1:
        if st.button("🔄 अभी रिपोर्ट और AI रिफ्रेश करें"):
            build_report_now(eng, time.time(), get_ist_time_str())
            st.rerun()
    with c_act2:
        if st.button("🔔 साउंड अनलॉक / टेस्ट करें"):
            trigger_browser_audio("BULL")
    with c_act3:
        sound_enabled = st.checkbox("🔊 सिर्फ कन्फर्म सिग्नल लॉक होने और बड़े स्प्रेड ($5.5+) पर साउंड बजाएं", value=True)

    curr_snd = eng.get("sound_event", {"id": 0.0, "type": "BULL"})
    if sound_enabled and curr_snd["id"] > 0 and curr_snd["id"] != st.session_state["last_played_sound_id"]:
        st.session_state["last_played_sound_id"] = curr_snd["id"]
        trigger_browser_audio(curr_snd["type"])

    col_main, col_side = st.columns([0.63, 0.37])

    with col_main:
        if eng["report"]:
            r = eng["report"]
            m30 = r["m30"]
            m5 = r["m5"]
            sc_col = "#4ade80" if r["score"] >= 45 else ("#f87171" if r["score"] <= -45 else "#facc15")
            c30_col = "#4ade80" if m30["px_chg"] >= 0 else "#f87171"
            c5_col = "#4ade80" if m5["px_chg"] >= 0 else "#f87171"

            diag_html = "".join(f"<div style='margin-bottom:6px; font-size:13.8px; color:#e2e8f0;'>{d}</div>" for d in r["diagnostics"])

            st.markdown(clean_html(f"""
            <div class='lock-banner {r["lock_cls"]}'>
                <div>
                    <div style='font-size:19px; font-weight:900;'>{r["lock_title"]}</div>
                    <div style='font-size:13px; margin-top:4px; opacity:0.92;'>{r["lock_sub"]}</div>
                </div>
                <div style='text-align:right; min-width:140px;'>
                    <div style='font-size:11.5px; text-transform:uppercase; opacity:0.8;'>Conviction Score</div>
                    <div style='font-size:26px; font-weight:900; color:{sc_col};'>{r["score"]:+d} / 100</div>
                    <div style='font-size:11px; opacity:0.8;'>अपडेट: {r["time"]}</div>
                </div>
            </div>

            <div class='grid-2col'>
                <div class='horizon-card'>
                    <div class='horizon-title'>
                        <span>🏛️ 1. मैक्रो बेस (पूरे {r["span_min"]:.0f} मिनट का निचोड़)</span>
                        <span style='color:{c30_col};'>{m30["px_chg"]:+.1f} Pts</span>
                    </div>
                    <div class='stat-line'><span>असली सौदे (30m Taker Tape):</span><b><span style='color:#4ade80;'>{m30["tape_buy"]:.1f}% Buy</span> / <span style='color:#f87171;'>{100-m30["tape_buy"]:.1f}% Sell</span></b></div>
                    <div class='stat-line'><span>ऑर्डरबुक दीवारें (30m L2 Limits):</span><b><span style='color:#4ade80;'>{m30["l2_buy"]:.1f}% Bid</span> / <span style='color:#f87171;'>{100-m30["l2_buy"]:.1f}% Ask</span></b></div>
                    <div class='stat-line'><span>30m हाई / लो रेंज:</span><b>${m30["high"]:,.0f} — ${m30["low"]:,.0f}</b></div>
                    <div class='stat-line' style='border:none;'><span>VWAP बेस एवं स्प्रेड काउंट:</span><b>${r["vwap"]:,.1f} ({r["bull_voids"]}B / {r["bear_voids"]}S)</b></div>
                </div>

                <div class='horizon-card'>
                    <div class='horizon-title'>
                        <span>⚡ 2. माइक्रो ट्रिगर (आखिरी 5 मिनट का बदलाव)</span>
                        <span style='color:{c5_col};'>{m5["px_chg"]:+.1f} Pts</span>
                    </div>
                    <div class='stat-line'><span>आखिरी 5m Taker Tape:</span><b><span style='color:#4ade80;'>{m5["tape_buy"]:.1f}% Buy</span> / <span style='color:#f87171;'>{100-m5["tape_buy"]:.1f}% Sell</span></b></div>
                    <div class='stat-line'><span>आखिरी 5m L2 Orderbook:</span><b><span style='color:#4ade80;'>{m5["l2_buy"]:.1f}% Bid</span> / <span style='color:#f87171;'>{100-m5["l2_buy"]:.1f}% Ask</span></b></div>
                    <div class='stat-line'><span>30m की तुलना में Tape बदलाव:</span><b style='color:#38bdf8;'>{m5["tape_buy"]-m30["tape_buy"]:+.1f}% Shift</b></div>
                    <div class='stat-line' style='border:none;'><span>30m की तुलना में L2 बदलाव:</span><b style='color:#38bdf8;'>{m5["l2_buy"]-m30["l2_buy"]:+.1f}% Shift</b></div>
                </div>
            </div>

            <div class='horizon-card' style='margin-bottom:14px;'>
                <div class='horizon-title'><span>🔎 ऑटो-डायग्नोस्टिक (30m बनाम 5m क्रॉस-चेक)</span></div>
                {diag_html}
            </div>

            <div class='ai-panel'>
                <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3b0764; padding-bottom:8px; margin-bottom:10px;'>
                    <span style='font-size:15.5px; font-weight:900; color:#c084fc;'>🤖 AI फॉरेंसिक रिपोर्ट (30m + 5m + स्प्रेड ऑर्डरबुक जांच)</span>
                    <span style='font-size:12px; color:#94a3b8;'>{eng["ai_status"]}</span>
                </div>
                <div style='font-size:14.5px; line-height:1.65; color:#f8fafc; white-space:pre-line;'>{eng["ai_opinion"]}</div>
            </div>
            """), unsafe_allow_html=True)
        else:
            pct = min(100, int((len(eng["vault"]) / 12) * 100))
            st.markdown(clean_html(f"""
            <div class='horizon-card' style='text-align:center; padding:55px 20px;'>
                <div style='font-size:21px; font-weight:800; color:#38bdf8; margin-bottom:10px;'>⏳ 30m बनाम 5m वॉर रूम इंजन चालू हो रहा है... ({pct}%)</div>
                <div style='font-size:14.5px; color:#94a3b8;'>तुरंत रिपोर्ट देखने के लिए ऊपर <b>'🔄 अभी रिपोर्ट और AI रिफ्रेश करें'</b> बटन दबाएं।</div>
            </div>
            """), unsafe_allow_html=True)

    with col_side:
        void_cards_html = ""
        for v in eng["voids"]:
            j_col = "#4ade80" if v["px_jump"] >= 0 else "#f87171"
            s_col = "#4ade80" if v["l2_shift"] >= 0 else "#f87171"
            void_cards_html += f"""
            <div class='void-card {v["cls"]}'>
                <div style='display:flex; justify-content:space-between; font-weight:800; color:#f8fafc;'>
                    <span>🕒 {v["time"]} | Spread: <b style='color:#facc15;'>${v["spread"]:.1f}</b></span>
                    <span style='color:{j_col};'>Jump: {v["px_jump"]:+.1f}$</span>
                </div>
                <div style='color:#cbd5e1; margin-top:4px;'>
                    <b>L2 बदलाव:</b> {v["l2_before"]:.0f}% ➔ <b>{v["l2_after"]:.0f}% Bid</b> (<span style='color:{s_col}; font-weight:bold;'>{v["l2_shift"]:+.0f}%</span>) | <b>Tape:</b> {v["tape_pct"]:.0f}% B
                </div>
                <div style='color:#38bdf8; font-size:12px; margin-top:3px; font-weight:600;'>{v["ob_reaction"]}</div>
            </div>
            """

        if not void_cards_html:
            void_cards_html = "<div style='text-align:center; color:#64748b; padding-top:180px;'>अभी $4.0 से बड़ा कोई स्प्रेड नहीं आया है।<br>स्प्रेड फटते ही यहाँ ऑर्डरबुक के बदलाव का पूरा एक्स-रे दिखेगा।</div>"

        st.markdown(clean_html(f"""
        <div class='void-panel'>
            <div style='font-size:15px; font-weight:900; color:#facc15; margin-bottom:10px; border-bottom:1px solid #334155; padding-bottom:8px;'>
                🌪️ स्प्रेड एवं ऑर्डरबुक पोस्टमार्टम (Spread > $4.0)
            </div>
            {void_cards_html}
        </div>
        """), unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⏳ 24x7 V10.0 (Forensic War Room) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

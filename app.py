import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import threading
import json
import re
import io
import wave
import struct
import math
import base64
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V13.0 - Multi-Void & SL Trail AI Engine", layout="wide")

def clean_html(raw_html: str) -> str:
    """Strips leading spaces so Streamlit renders pure HTML inside a single slot without ghost boxes"""
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
.trail-banner { background: #091e3a; border: 1px solid #38bdf8; border-left: 4px solid #facc15; border-radius: 8px; padding: 10px 12px; margin-top: 10px; font-size: 13.2px; color: #f8fafc; }
.json-pill { background: #090d16; border: 1px solid #4c1d95; padding: 4px 10px; border-radius: 6px; font-size: 12px; color: #e9d5ff; font-weight: 700; display: inline-block; margin-right: 8px; margin-top: 6px; }
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 265px; overflow-y: auto; }
.void-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 660px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
</style>
"""), unsafe_allow_html=True)

# ============================================================================
# IN-BUILT SOUND SYNTHESIZER (ENTRY, EXIT, TRAIL & VOID TONES)
# ============================================================================
def create_sound_b64(tone_type="BULL"):
    sample_rate = 22050
    buf = io.BytesIO()
    if tone_type == "BULL":
        notes = [(784, 0.13), (0, 0.03), (1046, 0.15), (0, 0.03), (1318, 0.22)]
    elif tone_type == "BEAR":
        notes = [(659, 0.14), (0, 0.03), (523, 0.14), (0, 0.03), (392, 0.24)]
    elif tone_type == "TRAIL":
        notes = [(880, 0.10), (0, 0.03), (1175, 0.16)]
    elif tone_type == "EXIT":
        notes = [(880, 0.12), (0, 0.04), (660, 0.12), (0, 0.04), (880, 0.18)]
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
# HYPERLIQUID MARKET DATA FETCHERS
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

# ============================================================================
# MULTI-SPREAD (LAST 10 VOIDS) CLUSTER FORENSIC ANALYZER
# ============================================================================
def analyze_void_cluster(void_list, current_px):
    """Analyzes the last 5-10 liquidity voids together to detect institutional footprints"""
    recent = void_list[:10]
    if not recent:
        return {
            "count": 0, "bull_cnt": 0, "bear_cnt": 0, "pull_cnt": 0,
            "avg_l2_shift": 0.0, "avg_tape": 50.0, "net_px_progress": 0.0,
            "pattern_summary": "पिछले 30 मिनट में $4.0+ का कोई स्प्रेड क्लस्टर नहीं बना है (लिक्विडिटी सामान्य है)।",
            "prompt_table": "कोई बड़ा स्प्रेड रिकॉर्ड नहीं हुआ।"
        }

    cnt = len(recent)
    bull_cnt = sum(1 for v in recent if v["cls"] == "ic-bull")
    bear_cnt = sum(1 for v in recent if v["cls"] == "ic-bear")
    pull_cnt = sum(1 for v in recent if v["cls"] == "ic-warn")
    avg_l2_shift = sum(v["l2_shift"] for v in recent) / cnt
    avg_tape = sum(v["tape_pct"] for v in recent) / cnt
    oldest_void_px = recent[-1]["px"]
    net_px_progress = current_px - oldest_void_px

    # Detect multi-spread institutional footprint
    if bull_cnt >= bear_cnt + 2 and net_px_progress < -15.0:
        pattern = f"🧊 बियरिश आइसबर्ग ट्रैप: पिछले {cnt} में से {bull_cnt} स्प्रेड बुलिश थे (Avg Tape {avg_tape:.0f}%B), फिर भी प्राइस {net_px_progress:+.0f}$ गिरा—ऊपर व्हेल माल चिपका रही है!"
    elif bear_cnt >= bull_cnt + 2 and net_px_progress > 15.0:
        pattern = f"🧊 बुलिश आइसबर्ग अब्जॉर्प्शन: पिछले {cnt} में से {bear_cnt} स्प्रेड बियरिश थे, फिर भी प्राइस {net_px_progress:+.0f}$ चढ़ा—नीचे व्हेल सारा बिकवाली का माल सोख रही है!"
    elif avg_l2_shift <= -4.5:
        pattern = f"⚠️ बिड-पुलिंग पैनिक: पिछले {cnt} स्प्रेड्स में औसतन L2 Bids {avg_l2_shift:+.1f}% गिरी हैं—स्प्रेड फटने पर बायर्स डरकर सपोर्ट हटा रहे हैं।"
    elif avg_l2_shift >= 4.5:
        pattern = f"🚀 आक्रामक बाइंग स्वीप: पिछले {cnt} स्प्रेड्स में L2 Bids औसतन {avg_l2_shift:+.1f}% बढ़ी हैं और बायर्स ऊपर के आस्क तोड़ रहे हैं।"
    else:
        pattern = f"📊 पिछले {cnt} स्प्रेड्स का निचोड़: {bull_cnt} बुलिश बनाम {bear_cnt} बियरिश ({pull_cnt} ऑर्डर-पुल) | औसत L2 बदलाव: {avg_l2_shift:+.1f}% | नेट प्राइस असर: {net_px_progress:+.1f}$।"

    lines = []
    for idx, v in enumerate(recent, 1):
        lines.append(
            f"#{idx} [{v['time']}] Spread:${v['spread']:.1f} | Px:${v['px']:,.0f} (Jump:{v['px_jump']:+.1f}$) | "
            f"L2 Bid:{v['l2_before']:.0f}%->{v['l2_after']:.0f}% ({v['l2_shift']:+.0f}%) | Tape:{v['tape_pct']:.0f}%B | {v['ob_reaction']}"
        )

    return {
        "count": cnt, "bull_cnt": bull_cnt, "bear_cnt": bear_cnt, "pull_cnt": pull_cnt,
        "avg_l2_shift": avg_l2_shift, "avg_tape": avg_tape, "net_px_progress": net_px_progress,
        "pattern_summary": pattern,
        "prompt_table": "\n".join(lines)
    }

# ============================================================================
# AI JSON PARSER & FALLBACK QUANT BRAIN (USES 10-VOID CLUSTER + SL REASON)
# ============================================================================
def parse_ai_json_safely(raw_text: str):
    try:
        cleaned = re.sub(r"```json|```", "", raw_text).strip()
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1:
            return json.loads(cleaned[start_idx:end_idx+1])
    except Exception:
        pass
    return None

def fallback_quant_json_decision(ctx, active_trade):
    m30 = ctx["m30"]
    m5 = ctx["m5"]
    px = ctx["px"]
    vwap = ctx["vwap"] if ctx["vwap"] > 0 else px
    vc = ctx["void_cluster"]

    if active_trade is None:
        bull_align = (m30["tape_buy"] >= 53.5 and m5["tape_buy"] >= 55.0 and px >= vwap and vc["avg_l2_shift"] >= -3.0)
        bear_align = (m30["tape_buy"] <= 46.5 and m5["tape_buy"] <= 45.0 and px <= vwap and vc["avg_l2_shift"] <= 3.0)

        if bull_align and ctx["span_min"] >= 1.5:
            prob = min(92, int(55 + (m5["tape_buy"] - 50) * 1.8 + (m30["tape_buy"] - 50) * 1.2))
            return {
                "decision": "BUY",
                "probability": max(76, prob),
                "sl_price": round(px - 140.0, 1),
                "target_price": round(px + 320.0, 1),
                "headline": f"कन्फर्म BUY सिग्नल (${px:,.0f}) — 30m, 5m और स्प्रेड क्लस्टर तीनों में बायर्स मजबूत हैं।",
                "macro_vs_micro": f"30m Tape ({m30['tape_buy']:.0f}% Buy) के साथ आखिरी 5m में बाइंग बढ़कर {m5['tape_buy']:.0f}% पर पहुँची है।",
                "void_forensics": vc["pattern_summary"]
            }
        elif bear_align and ctx["span_min"] >= 1.5:
            prob = min(92, int(55 + (50 - m5["tape_buy"]) * 1.8 + (50 - m30["tape_buy"]) * 1.2))
            return {
                "decision": "SELL",
                "probability": max(76, prob),
                "sl_price": round(px + 140.0, 1),
                "target_price": round(px - 320.0, 1),
                "headline": f"कन्फर्म SELL सिग्नल (${px:,.0f}) — 30m, 5m और स्प्रेड क्लस्टर में सेलर्स हावी हैं।",
                "macro_vs_micro": f"30m Sell Tape ({100-m30['tape_buy']:.0f}%) के बाद आखिरी 5m में भी {100-m5['tape_buy']:.0f}% बिकवाली जारी है।",
                "void_forensics": vc["pattern_summary"]
            }
        else:
            prob = int(45 + abs(m5["tape_buy"] - 50) * 1.1)
            return {
                "decision": "WAIT",
                "probability": min(68, prob),
                "sl_price": round(px - 140.0, 1),
                "target_price": round(px + 250.0, 1),
                "headline": "WAIT (अभी कोई ट्रेड न लें) — 30m, 5m और स्प्रेड क्लस्टर में 75%+ वाली एकतरफा मजबूती नहीं है।",
                "macro_vs_micro": f"30m Tape में {m30['tape_buy']:.0f}% बाइंग है जबकि आखिरी 5m में {m5['tape_buy']:.0f}% बाइंग है।",
                "void_forensics": vc["pattern_summary"]
            }
    else:
        t_type = active_trade["type"]
        live_pts = active_trade["live_pts"]
        peak_pts = active_trade["peak_pts"]
        curr_sl = active_trade["sl_px"]
        entry_px = active_trade["entry"]

        if t_type == "BUY":
            if m5["tape_buy"] <= 42.0 or (peak_pts >= 140.0 and live_pts <= peak_pts * 0.45):
                return {
                    "action": "EXIT",
                    "confidence": 85,
                    "trailing_sl": curr_sl,
                    "sl_trail_reason": "ट्रेड एग्जिट किया गया क्योंकि 5m मोमेंटम टूट गया।",
                    "headline": f"🚨 EXIT LONG @ ${px:,.0f} ({live_pts:+.1f}p) — आखिरी 5m में बाइंग मोमेंटम खत्म हो गया है!",
                    "macro_vs_micro": f"आखिरी 5 मिनट में Taker बाइंग गिरकर {m5['tape_buy']:.0f}% रह गई है।",
                    "void_forensics": vc["pattern_summary"]
                }
            else:
                new_sl = curr_sl
                reason_txt = "अभी प्राइस कुशन कम है, इसलिए पुराने स्टॉप-लॉस को सुरक्षित रखा गया है।"
                if live_pts >= 160.0 and max(entry_px + 80.0, m5["low"] - 25.0) > curr_sl + 5.0:
                    new_sl = round(max(entry_px + 80.0, m5["low"] - 25.0), 1)
                    reason_txt = f"+{live_pts:.0f}p प्रॉफिट मिलने और 5m स्विंग लो (${m5['low']:,.0f}) पर नई L2 बिड्स बनने के कारण SL को प्रॉफिट में लॉक किया गया।"
                elif live_pts >= 90.0 and entry_px + 15.0 > curr_sl + 5.0:
                    new_sl = round(entry_px + 15.0, 1)
                    reason_txt = f"ट्रेड +{live_pts:.0f}p ऊपर चलने और स्प्रेड क्लस्टर बुलिश रहने से SL को कॉस्ट (Cost+15p) पर ट्रेल किया गया ताकि रिस्क ज़ीरो हो जाए।"
                elif live_pts >= 50.0 and m5["low"] - 45.0 > curr_sl + 10.0:
                    new_sl = round(m5["low"] - 45.0, 1)
                    reason_txt = f"आखिरी 5m में नीचे सपोर्ट (${m5['low']:,.0f}) बनने से शुरुआती रिस्क कम करने के लिए SL ऊपर खिसकाया गया।"

                return {
                    "action": "HOLD",
                    "confidence": 82,
                    "trailing_sl": new_sl,
                    "sl_trail_reason": reason_txt,
                    "headline": f"✅ HOLD LONG ({live_pts:+.1f}p) — बाइंग फ्लो मजबूत है, ट्रेड होल्ड करें (SL: ${new_sl:,.0f})।",
                    "macro_vs_micro": f"30m ({m30['tape_buy']:.0f}% B) और 5m ({m5['tape_buy']:.0f}% B) दोनों अभी आपके LONG ट्रेड के पक्ष में हैं।",
                    "void_forensics": vc["pattern_summary"]
                }
        else:
            if m5["tape_buy"] >= 58.0 or (peak_pts >= 140.0 and live_pts <= peak_pts * 0.45):
                return {
                    "action": "EXIT",
                    "confidence": 85,
                    "trailing_sl": curr_sl,
                    "sl_trail_reason": "ट्रेड एग्जिट किया गया क्योंकि 5m में शॉर्ट कवरिंग शुरू हो गई।",
                    "headline": f"🚨 EXIT SHORT @ ${px:,.0f} ({live_pts:+.1f}p) — आखिरी 5m में नीचे से तेज बाइंग आ रही है!",
                    "macro_vs_micro": f"आखिरी 5 मिनट में Taker बाइंग उछलकर {m5['tape_buy']:.0f}% हो गई है।",
                    "void_forensics": vc["pattern_summary"]
                }
            else:
                new_sl = curr_sl
                reason_txt = "अभी प्राइस कुशन कम है, इसलिए पुराने स्टॉप-लॉस को सुरक्षित रखा गया है।"
                if live_pts >= 160.0 and min(entry_px - 80.0, m5["high"] + 25.0) < curr_sl - 5.0:
                    new_sl = round(min(entry_px - 80.0, m5["high"] + 25.0), 1)
                    reason_txt = f"+{live_pts:.0f}p प्रॉफिट मिलने और 5m हाई (${m5['high']:,.0f}) पर सेल वॉल बनने से SL को प्रॉफिट में लॉक किया गया।"
                elif live_pts >= 90.0 and entry_px - 15.0 < curr_sl - 5.0:
                    new_sl = round(entry_px - 15.0, 1)
                    reason_txt = f"ट्रेड +{live_pts:.0f}p मुनाफे में आने से SL को कॉस्ट (Entry-15p) पर ट्रेल कर रिस्क फ्री किया गया।"
                elif live_pts >= 50.0 and m5["high"] + 45.0 < curr_sl - 10.0:
                    new_sl = round(m5["high"] + 45.0, 1)
                    reason_txt = f"5m रेजिस्टेंस (${m5['high']:,.0f}) नीचे शिफ्ट होने के कारण रिस्क घटाने के लिए SL ट्रेल किया गया।"

                return {
                    "action": "HOLD",
                    "confidence": 82,
                    "trailing_sl": new_sl,
                    "sl_trail_reason": reason_txt,
                    "headline": f"✅ HOLD SHORT ({live_pts:+.1f}p) — सेलिंग प्रेशर बरकरार है, ट्रेड होल्ड करें (SL: ${new_sl:,.0f})।",
                    "macro_vs_micro": f"30m ({100-m30['tape_buy']:.0f}% S) और 5m ({100-m5['tape_buy']:.0f}% S) दोनों आपके SHORT ट्रेड को सपोर्ट कर रहे हैं।",
                    "void_forensics": vc["pattern_summary"]
                }

# ============================================================================
# GEMINI JSON DECISION ENGINE (WITH 10-SPREAD CLUSTER & SL TRAIL REASON)
# ============================================================================
def call_gemini_json_engine(api_key, ctx, active_trade):
    m30 = ctx["m30"]
    m5 = ctx["m5"]
    px = ctx["px"]
    vwap = ctx["vwap"]
    vc = ctx["void_cluster"]

    if active_trade is None:
        prompt = f"""
तुम एक स्वायत्त (Autonomous) इंट्राडे BTCUSDT AI ट्रेडिंग इंजन हो। नीचे दिए गए 30-मिनट मैक्रो, 5-मिनट माइक्रो और पिछले 10 बड़े स्प्रेड्स (Liquidity Voids) के क्लस्टर पैटर्न को पढ़कर तय करो कि अभी नया ट्रेड लेना चाहिए या शांत रहना चाहिए (WAIT)।

1. लाइव मार्केट डेटा:
- वर्तमान BTC प्राइस: ${px:,.1f} | सेशन VWAP: ${vwap:,.1f} | डेटा मेमोरी: {ctx['span_min']:.1f} मिनट
- पूरे 30m का डेटा: प्राइस बदलाव {m30['px_chg']:+.1f} Pts (High: ${m30['high']:,.0f}, Low: ${m30['low']:,.0f}) | 30m Taker Tape: {m30['tape_buy']:.1f}% Buy | 30m L2 Orderbook: {m30['l2_buy']:.1f}% Bids
- आखिरी 5m का ताज़ा डेटा: प्राइस बदलाव {m5['px_chg']:+.1f} Pts (High: ${m5['high']:,.0f}, Low: ${m5['low']:,.0f}) | 5m Taker Tape: {m5['tape_buy']:.1f}% Buy ({m5['tape_buy']-m30['tape_buy']:+.1f}% Shift) | 5m L2 Orderbook: {m5['l2_buy']:.1f}% Bids

2. पिछले {vc['count']} बड़े स्प्रेड्स (Spread > $4.0) का क्लस्टर सारांश और पूरी लिस्ट:
- क्लस्टर पैटर्न: {vc['pattern_summary']}
- पिछले स्प्रेड्स का क्रमवार डेटा (नए से पुराना):
{vc['prompt_table']}

सख्त नियम:
1. सिर्फ आखिरी स्प्रेड मत देखो; पूरे {vc['count']} स्प्रेड्स के पैटर्न (जैसे बार-बार अब्जॉर्प्शन या L2 बिड पुलिंग) को 30m और 5m के साथ मिलाकर देखो।
2. "BUY" या "SELL" केवल तभी चुनो जब 30m, 5m और स्प्रेड क्लस्टर तीनों एक दिशा में मजबूत हों और संभावना (probability) 75 से 95 के बीच हो।
3. जवाब केवल नीचे दिए गए शुद्ध JSON फॉर्मेट में दो:
{{
  "decision": "BUY" या "SELL" या "WAIT",
  "probability": 0 से 100 के बीच पूर्णांक (int),
  "sl_price": संख्या (float - एंट्री से 110 से 160 पॉइंट्स दूर लॉजिकल स्टॉप-लॉस),
  "target_price": संख्या (float - एंट्री से 250 से 400 पॉइंट्स दूर टारगेट),
  "headline": "1 तीखी लाइन में स्पष्ट सिग्नल और कारण (हिंदी में)",
  "macro_vs_micro": "1 लाइन में 30m बनाम आखिरी 5m की तुलना (हिंदी में)",
  "void_forensics": "1 लाइन में पिछले सभी स्प्रेड्स के पैटर्न से निकला मुख्य निष्कर्ष (हिंदी में)"
}}
"""
    else:
        t_type = active_trade["type"]
        t_entry = active_trade["entry"]
        live_pts = active_trade["live_pts"]
        peak_pts = active_trade["peak_pts"]
        init_sl = active_trade["initial_sl"]
        curr_sl = active_trade["sl_px"]
        dur_min = (time.time() - active_trade["open_ts"]) / 60.0

        prompt = f"""
तुम एक स्वायत्त (Autonomous) इंट्राडे BTCUSDT AI ट्रेड मैनेजर हो। अभी हमारा एक ट्रेड चालू (ACTIVE) है। पिछले 3 मिनट का ताज़ा डेटा और पिछले {vc['count']} स्प्रेड्स का पैटर्न देखकर तय करो कि इस ट्रेड को होल्ड ("HOLD") करना है या तुरंत निकलना ("EXIT") है, और क्या स्टॉप-लॉस को ट्रेल (Trail) करना चाहिए।

चालू ट्रेड की स्थिति:
- ट्रेड दिशा: {t_type} | एंट्री प्राइस: ${t_entry:,.1f} | वर्तमान प्राइस: ${px:,.1f}
- वर्तमान प्रॉफिट/लॉस: {live_pts:+.1f} Points | अब तक का अधिकतम प्रॉफिट (Peak): +{peak_pts:.1f} Points
- शुरुआती स्टॉप-लॉस: ${init_sl:,.1f} | वर्तमान एक्टिव स्टॉप-लॉस: ${curr_sl:,.1f} | समय: {dur_min:.1f} मिनट

ताज़ा मार्केट और स्प्रेड क्लस्टर डेटा:
- पूरे 30m का डेटा: Taker Tape {m30['tape_buy']:.1f}% Buy | L2 Orderbook {m30['l2_buy']:.1f}% Bids | VWAP: ${vwap:,.1f}
- आखिरी 5m का ताज़ा बदलाव: प्राइस {m5['px_chg']:+.1f} Pts (5m High: ${m5['high']:,.0f}, 5m Low: ${m5['low']:,.0f}) | 5m Taker Tape: {m5['tape_buy']:.1f}% Buy | 5m L2 Orderbook: {m5['l2_buy']:.1f}% Bids
- पिछले {vc['count']} स्प्रेड्स का क्लस्टर पैटर्न: {vc['pattern_summary']}
- स्प्रेड्स की लिस्ट:
{vc['prompt_table']}

सख्त नियम:
1. अगर आखिरी 5 मिनट या स्प्रेड क्लस्टर में हमारे ट्रेड के खिलाफ भारी उलटफेर/अब्जॉर्प्शन दिख रहा है, तो "EXIT" चुनो।
2. अगर ट्रेड होल्ड ("HOLD") रखते हो और ट्रेड मुनाफे में है (+50p से ज़्यादा) या नया 5m स्विंग सपोर्ट/रेजिस्टेंस बन गया है, तो `trailing_sl` को हमारे पक्ष में आगे बढ़ाओ (BUY में ऊपर, SELL में नीचे) और `sl_trail_reason` में उसका स्पष्ट तकनीकी कारण बताओ (जैसे: '5m स्विंग लो $73,480 और L2 बिड सपोर्ट के नीचे SL शिफ्ट किया ताकि +80p लॉक हो जाएं')।
3. जवाब केवल नीचे दिए गए शुद्ध JSON फॉर्मेट में दो:
{{
  "action": "HOLD" या "EXIT",
  "confidence": 0 से 100 के बीच पूर्णांक (int),
  "trailing_sl": संख्या (float - नया ट्रेल किया हुआ SL या वर्तमान SL),
  "sl_trail_reason": "1 स्पष्ट लाइन में बताओ कि स्टॉप-लॉस क्यों ट्रेल किया गया या क्यों वहीं रखा गया (हिंदी में)",
  "headline": "1 तीखी लाइन में HOLD या EXIT का स्पष्ट आदेश (हिंदी में)",
  "macro_vs_micro": "1 लाइन में आखिरी 5m के डेटा का हमारे चालू ट्रेड पर असर (हिंदी में)",
  "void_forensics": "1 लाइन में पिछले स्प्रेड्स के क्लस्टर का हमारे ट्रेड पर असर (हिंदी में)"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 380,
            "responseMimeType": "application/json"
        }
    }

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    for mod in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=9)
            if res.status_code == 200:
                raw_txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                parsed = parse_ai_json_safely(raw_txt)
                if parsed:
                    return parsed, f"🟢 Autonomous AI ({mod})"
        except Exception:
            continue

    return fallback_quant_json_decision(ctx, active_trade), "⚡ Quant Backup JSON Engine"

# ============================================================================
# CORE EXECUTION CYCLE (RUNS EVERY 3 MINS OR ON MANUAL TRIGGER)
# ============================================================================
def execute_ai_cycle_thread(eng, now_ts, ist_str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        vault = eng["vault"]
        if len(vault) < 5:
            return

        px = eng["px"]
        span_min = max(0.5, (now_ts - vault[0]["ts"]) / 60.0)
        vault_5m = [d for d in vault if (now_ts - d["ts"]) <= 300.0]

        m30 = compute_slice_metrics(vault)
        m5 = compute_slice_metrics(vault_5m)
        voids_30m = [v for v in eng["voids"] if (now_ts - v.get("ts", now_ts)) <= 1800]
        void_cluster = analyze_void_cluster(voids_30m, px)

        ctx = {
            "time": ist_str, "px": px, "vwap": eng["vwap"] if eng["vwap"] > 0 else px,
            "span_min": span_min, "m30": m30, "m5": m5,
            "void_cluster": void_cluster, "recent_voids": voids_30m[:10]
        }

        api_key = eng.get("api_key", "").strip()
        active_tr = eng.get("active_trade")

        if api_key:
            ai_json, status_str = call_gemini_json_engine(api_key, ctx, active_tr)
        else:
            ai_json, status_str = fallback_quant_json_decision(ctx, active_tr), "🟡 Local JSON Engine (No API Key)"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = now_ts

        # --------------------------------------------------------------------
        # CASE 1: NO ACTIVE TRADE -> CHECK IF AI CONFIRMS AN ENTRY (>=75% PROB)
        # --------------------------------------------------------------------
        if active_tr is None:
            dec = str(ai_json.get("decision", "WAIT")).upper()
            prob = int(ai_json.get("probability", 50))
            sl_px = float(ai_json.get("sl_price", px - 140.0 if dec == "BUY" else px + 140.0))
            tp_px = float(ai_json.get("target_price", px + 300.0 if dec == "BUY" else px - 300.0))

            if dec == "BUY":
                sl_px = min(px - 60.0, max(px - 180.0, sl_px))
            elif dec == "SELL":
                sl_px = max(px + 60.0, min(px + 180.0, sl_px))

            if dec in ["BUY", "SELL"] and prob >= 75 and span_min >= 1.2:
                init_sl_rounded = round(sl_px, 1)
                new_trade = {
                    "open_ts": now_ts,
                    "open_time": ist_str,
                    "close_time": "",
                    "type": dec,
                    "entry": px,
                    "prob": prob,
                    "initial_sl": init_sl_rounded,
                    "sl_px": init_sl_rounded,
                    "tp_px": round(tp_px, 1),
                    "trail_count": 0,
                    "last_trail_msg": f"🛡️ प्रारंभिक AI स्टॉप-लॉस: ${init_sl_rounded:,.1f} (अगली हर 3-मिनट जांच में AI इसे ट्रेल करेगा)",
                    "trail_log": [],
                    "live_pts": 0.0,
                    "peak_pts": 0.0,
                    "status": "ACTIVE (AI MANAGING)",
                    "entry_reason": ai_json.get("headline", "AI Confirmed Entry"),
                    "exit_reason": "अभी ट्रेड चालू है — हर 3 मिनट में AI निगरानी कर रहा है"
                }
                eng["active_trade"] = new_trade
                eng["signal_history"].insert(0, new_trade)
                eng["signal_history"] = eng["signal_history"][:30]
                eng["sound_event"] = {"id": now_ts, "type": "BULL" if dec == "BUY" else "BEAR"}

                lock_title = f"🟢 AI ने नया {dec} ट्रेड लॉक किया! (संभावना: {prob}%)" if dec == "BUY" else f"🔴 AI ने नया {dec} ट्रेड लॉक किया! (संभावना: {prob}%)"
                lock_cls = "lock-buy" if dec == "BUY" else "lock-sell"
                lock_sub = f"एंट्री: ${px:,.1f} | शुरुआती SL: ${init_sl_rounded:,.1f} | टारगेट: ${tp_px:,.1f}"
            else:
                lock_title = f"⚪ AI का फैसला: WAIT — कोई ट्रेड नहीं (संभावना सिर्फ {prob}%)"
                lock_cls = "lock-wait"
                lock_sub = f"पिछले {void_cluster['count']} स्प्रेड्स और 30m/5m डेटा में 75%+ वाली एकतरफा शर्त पूरी नहीं हुई।"

            eng["ai_json_view"] = {
                "mode": "ENTRY_SCAN",
                "badge_1": f"AI Decision: {dec}",
                "badge_2": f"Probability: {prob}%",
                "badge_3": f"Suggested SL: ${sl_px:,.0f}",
                "badge_4": f"Spreads Analyzed: {void_cluster['count']}",
                "headline": ai_json.get("headline", ""),
                "macro_vs_micro": ai_json.get("macro_vs_micro", ""),
                "void_forensics": ai_json.get("void_forensics", ""),
                "trail_box_html": ""
            }

        # --------------------------------------------------------------------
        # CASE 2: ACTIVE TRADE RUNNING -> AI DECIDES HOLD/EXIT & TRAILS SL
        # --------------------------------------------------------------------
        else:
            act = str(ai_json.get("action", "HOLD")).upper()
            conf = int(ai_json.get("confidence", 75))
            ai_trail_sl = float(ai_json.get("trailing_sl", active_tr["sl_px"]))
            trail_reason = str(ai_json.get("sl_trail_reason", "मोमेंटम और ऑर्डरबुक सपोर्ट के अनुसार SL की समीक्षा की गई।")).strip()

            if act == "EXIT":
                active_tr["close_time"] = ist_str
                active_tr["status"] = f"AI EXIT @ ${px:,.1f} ({ist_str})"
                active_tr["exit_reason"] = f"🤖 AI Exit: {ai_json.get('headline', 'मोमेंटम समाप्त')}"
                eng["active_trade"] = None
                eng["sound_event"] = {"id": now_ts, "type": "EXIT"}

                lock_title = f"🚨 AI ने ट्रेड EXIT कर दिया! ({active_tr['live_pts']:+.1f} Pts बुक)"
                lock_cls = "lock-wait"
                lock_sub = f"{active_tr['type']} ट्रेड ${px:,.1f} पर बंद किया गया। कारण: {ai_json.get('headline', '')}"
                trail_box_html = f"<div class='trail-banner'>🚨 <b>ट्रेड क्लोज किया गया ({ist_str}):</b> {trail_reason}</div>"
            else:
                old_sl = active_tr["sl_px"]
                sl_trailed_now = False

                # Tighten trailing SL in favorable direction only (minimum 2 points shift to avoid micro noise)
                if active_tr["type"] == "BUY" and (ai_trail_sl >= old_sl + 2.0) and (ai_trail_sl < px - 15.0):
                    active_tr["sl_px"] = round(ai_trail_sl, 1)
                    sl_trailed_now = True
                elif active_tr["type"] == "SELL" and (ai_trail_sl <= old_sl - 2.0) and (ai_trail_sl > px + 15.0):
                    active_tr["sl_px"] = round(ai_trail_sl, 1)
                    sl_trailed_now = True

                if sl_trailed_now:
                    active_tr["trail_count"] += 1
                    pts_shifted = abs(active_tr["sl_px"] - old_sl)
                    locked_vs_entry = (active_tr["sl_px"] - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - active_tr["sl_px"])
                    lock_tag = f"+{locked_vs_entry:.0f}p प्रॉफिट लॉक" if locked_vs_entry >= 0 else f"रिस्क घटकर {abs(locked_vs_entry):.0f}p रह गया"

                    event_str = (
                        f"🔄 <b>SL ट्रेल किया गया #{active_tr['trail_count']} ({ist_str}):</b> "
                        f"<span style='color:#f87171; text-decoration:line-through;'>${old_sl:,.1f}</span> ➔ "
                        f"<b style='color:#4ade80; font-size:14.5px;'>${active_tr['sl_px']:,.1f}</b> "
                        f"(<span style='color:#facc15;'>+{pts_shifted:.0f}p शिफ्ट | {lock_tag}</span>)<br>"
                        f"📌 <b>AI ट्रेलिंग कारण:</b> {trail_reason}"
                    )
                    active_tr["last_trail_msg"] = event_str
                    active_tr["trail_log"].insert(0, f"[{ist_str}] ${old_sl:,.0f} ➔ ${active_tr['sl_px']:,.0f}: {trail_reason}")
                    eng["sound_event"] = {"id": now_ts, "type": "TRAIL"}
                else:
                    event_str = (
                        f"🛡️ <b>स्टॉप-लॉस स्थिति ({ist_str}):</b> शुरुआती SL: <b>${active_tr['initial_sl']:,.1f}</b> | "
                        f"वर्तमान एक्टिव SL: <b style='color:#facc15;'>${active_tr['sl_px']:,.1f}</b> (कुल ट्रेल: {active_tr['trail_count']} बार)<br>"
                        f"📌 <b>AI SL नोट:</b> {trail_reason}"
                    )

                trail_box_html = f"<div class='trail-banner'>{event_str}</div>"

                lock_title = f"{'🟢' if active_tr['type']=='BUY' else '🔴'} AI ने {active_tr['type']} ट्रेड को HOLD रखा है ({active_tr['live_pts']:+.1f} Pts)"
                lock_cls = "lock-buy" if active_tr["type"] == "BUY" else "lock-sell"
                lock_sub = f"एंट्री: ${active_tr['entry']:,.1f} | शुरुआती SL: ${active_tr['initial_sl']:,.1f} ➔ एक्टिव SL: ${active_tr['sl_px']:,.1f} (ट्रेल: {active_tr['trail_count']} बार)"

            eng["ai_json_view"] = {
                "mode": "TRADE_MANAGER",
                "badge_1": f"AI Command: {act}",
                "badge_2": f"Initial SL: ${active_tr['initial_sl']:,.0f}",
                "badge_3": f"Active SL: ${active_tr['sl_px']:,.0f} (Trailed {active_tr['trail_count']}x)",
                "badge_4": f"Spreads Checked: {void_cluster['count']}",
                "headline": ai_json.get("headline", ""),
                "macro_vs_micro": ai_json.get("macro_vs_micro", ""),
                "void_forensics": ai_json.get("void_forensics", ""),
                "trail_box_html": trail_box_html
            }

        ctx["lock_title"] = lock_title
        ctx["lock_cls"] = lock_cls
        ctx["lock_sub"] = lock_sub
        eng["report"] = ctx

    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 BACKGROUND WORKER (DATA COLLECTION + 2s EMERGENCY SL GUARD)
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

                # 2-SECOND LIVE PNL & TRAILED STOP-LOSS GUARD FOR ACTIVE TRADE
                active_tr = eng.get("active_trade")
                if active_tr is not None:
                    move = (px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - px)
                    active_tr["live_pts"] = move
                    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)

                    sl_hit = (active_tr["type"] == "BUY" and px <= active_tr["sl_px"]) or (active_tr["type"] == "SELL" and px >= active_tr["sl_px"])
                    if sl_hit:
                        active_tr["close_time"] = ist_str
                        sl_kind = "TRAILED SL HIT" if active_tr["trail_count"] > 0 else "INITIAL SL HIT"
                        active_tr["status"] = f"{sl_kind} @ ${px:,.1f} ({ist_str})"
                        active_tr["exit_reason"] = f"🛡️ {sl_kind} (${active_tr['sl_px']:,.1f}) हिट हुआ | फाइनल: {move:+.1f}p"
                        eng["active_trade"] = None
                        eng["sound_event"] = {"id": now_ts, "type": "EXIT"}
                        if eng["report"]:
                            eng["report"]["lock_title"] = f"🛡️ {sl_kind} एग्जिट ({move:+.1f} Pts)"
                            eng["report"]["lock_cls"] = "lock-wait"
                            eng["report"]["lock_sub"] = f"प्राइस ने आपके स्टॉप-लॉस (${active_tr['sl_px']:,.1f}) को छू लिया, इसलिए ट्रेड क्लोज कर दिया गया।"

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

                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and len(eng["vault"]) >= 12 and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(2)

@st.cache_resource
def get_master_engine_v13_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "vault": [], "voids": [], "signal_history": [],
        "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "report": None,
        "ai_json_view": {
            "mode": "INIT",
            "badge_1": "AI Status: Waiting",
            "badge_2": "Probability: --%",
            "badge_3": "SL: --",
            "badge_4": "Spreads: 0",
            "headline": "⏳ पहली 3-मिनट रिपोर्ट बनते ही AI पिछले 10 स्प्रेड्स और 30m/5m डेटा से फैसला लेगा...",
            "macro_vs_micro": "डेटा बफर तैयार हो रहा है...",
            "void_forensics": "स्प्रेड क्लस्टर पर नज़र रखी जा रही है...",
            "trail_box_html": ""
        },
        "ai_status": "🤖 Multi-Void & SL Trail AI",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v13_0()

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
c_act1, c_act2, c_act3 = st.columns([0.30, 0.20, 0.50])
with c_act1:
    if st.button("🤖 अभी AI से फैसला / SL ट्रेल चेक कराएं"):
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()
with c_act2:
    test_snd = st.button("🔔 साउंड टेस्ट करें")
with c_act3:
    sound_enabled = st.checkbox("🔊 AI एंट्री, SL ट्रेल, एग्जिट और बड़े स्प्रेड पर साउंड बजाएं", value=True)

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
    next_sec = max(0, int(180 - (time.time() - eng["last_report_ts"]))) if eng["last_report_ts"] > 0 else 0

    # 1. Build AI Signal, SL Trail & Trade History HTML
    hist_cards = ""
    for h in eng["signal_history"]:
        h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
        h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
        p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
        is_act = "ACTIVE" in h["status"]
        sts_badge = "🟢 AI ACTIVE" if is_act else f"🏁 {h['status']}"
        trail_info = (
            f"शुरुआती SL: ${h['initial_sl']:,.0f} ➔ एक्टिव SL: <b style='color:#facc15;'>${h['sl_px']:,.0f}</b> (ट्रेल: {h['trail_count']} बार)"
        )
        latest_trail_note = f"<br><span style='color:#fde047; font-size:11.8px;'>🔄 {h['trail_log'][0]}</span>" if h.get("trail_log") else ""

        hist_cards += f"""
        <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <b style='color:{h_col}; font-size:13.5px;'>{h["open_time"]} — AI {h["type"]} @ ${h["entry"]:,.1f} (Prob: {h["prob"]}%)</b>
                <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span><br>
                <span style='color:#cbd5e1; font-size:12px;'>एंट्री: {h["entry_reason"]}</span><br>
                <span style='color:#38bdf8; font-size:11.8px;'>🛡️ {trail_info} | {h["exit_reason"]}</span>
                {latest_trail_note}
            </div>
            <div style='text-align:right; min-width:95px;'>
                <div style='font-size:15px; font-weight:900; color:{p_col};'>{h["live_pts"]:+.1f}p</div>
                <div style='font-size:11px; color:#94a3b8;'>Peak: +{h["peak_pts"]:.1f}p</div>
            </div>
        </div>
        """
    if not hist_cards:
        hist_cards = "<div style='text-align:center; color:#64748b; padding-top:75px;'>अभी तक AI ने कोई ट्रेड लॉक नहीं किया है (संभावना 75%+ होने पर ही ट्रेड लॉक होगा)।</div>"

    # 2. Build Void Postmortem + 10-Void Cluster Summary HTML
    live_cluster = analyze_void_cluster([v for v in eng["voids"] if (time.time() - v.get("ts", time.time())) <= 1800], eng["px"])
    cluster_banner = f"""
    <div style='background:#1e293b; border:1px solid #475569; border-left:4px solid #38bdf8; padding:8px 10px; border-radius:6px; margin-bottom:9px; font-size:12.2px; color:#f8fafc;'>
        <b>📊 पिछले {live_cluster["count"]} स्प्रेड्स का क्लस्टर पैटर्न:</b><br>
        <span style='color:#fde047;'>{live_cluster["pattern_summary"]}</span>
    </div>
    """

    void_cards = ""
    for idx, v in enumerate(eng["voids"], 1):
        j_col = "#4ade80" if v["px_jump"] >= 0 else "#f87171"
        s_col = "#4ade80" if v["l2_shift"] >= 0 else "#f87171"
        in_ai_tag = "<span style='color:#c084fc; font-size:10.5px; margin-left:4px;'>[AI Cluster Top-10]</span>" if idx <= 10 else ""
        void_cards += f"""
        <div class='item-card {v["cls"]}'>
            <div style='display:flex; justify-content:space-between; font-weight:800; color:#f8fafc;'>
                <span>#{idx} 🕒 {v["time"]} | Spread: <b style='color:#facc15;'>${v["spread"]:.1f}</b> {in_ai_tag}</span>
                <span style='color:{j_col};'>Jump: {v["px_jump"]:+.1f}$</span>
            </div>
            <div style='color:#cbd5e1; margin-top:3px;'>
                <b>L2 बदलाव:</b> {v["l2_before"]:.0f}% ➔ <b>{v["l2_after"]:.0f}% Bid</b> (<span style='color:{s_col}; font-weight:bold;'>{v["l2_shift"]:+.0f}%</span>) | <b>Tape:</b> {v["tape_pct"]:.0f}% B
            </div>
            <div style='color:#38bdf8; font-size:11.8px; margin-top:2px; font-weight:600;'>{v["ob_reaction"]}</div>
        </div>
        """
    if not void_cards:
        void_cards = "<div style='text-align:center; color:#64748b; padding-top:160px;'>अभी $4.0 से बड़ा कोई स्प्रेड नहीं फटा है।</div>"

    # 3. Build Left Main Section
    if eng["report"]:
        r = eng["report"]
        m30 = r["m30"]
        m5 = r["m5"]
        aj = eng["ai_json_view"]
        c30_col = "#4ade80" if m30["px_chg"] >= 0 else "#f87171"
        c5_col = "#4ade80" if m5["px_chg"] >= 0 else "#f87171"

        act_tr = eng.get("active_trade")
        if act_tr:
            right_stat_label = "LIVE TRADE PNL"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            right_stat_label = "AI CYCLE TIMER"
            right_stat_val = f"{next_sec}s"
            right_stat_col = "#38bdf8"

        left_body = f"""
        <div class='lock-banner {r["lock_cls"]}'>
            <div>
                <div style='font-size:18.5px; font-weight:900;'>{r["lock_title"]}</div>
                <div style='font-size:12.5px; margin-top:3px; opacity:0.92;'>{r["lock_sub"]}</div>
            </div>
            <div style='text-align:right; min-width:135px;'>
                <div style='font-size:11px; text-transform:uppercase; opacity:0.8;'>{right_stat_label}</div>
                <div style='font-size:24px; font-weight:900; color:{right_stat_col};'>{right_stat_val}</div>
                <div style='font-size:11px; opacity:0.8;'>अपडेट: {r["time"]}</div>
            </div>
        </div>

        <div class='ai-sharp-box'>
            <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3b0764; padding-bottom:6px; margin-bottom:8px;'>
                <span style='font-size:15px; font-weight:900; color:#c084fc;'>🧠 AI JSON डिसीजन (30m + 5m + पिछले 10 स्प्रेड्स का क्लस्टर विश्लेषण)</span>
                <span style='font-size:11.5px; color:#4ade80; font-weight:bold;'>{eng["ai_status"]}</span>
            </div>
            <div>
                <span class='json-pill'>{aj["badge_1"]}</span>
                <span class='json-pill'>{aj["badge_2"]}</span>
                <span class='json-pill'>{aj["badge_3"]}</span>
                <span class='json-pill'>{aj["badge_4"]}</span>
            </div>
            <div style='font-size:14px; line-height:1.65; color:#f8fafc; margin-top:10px;'>
                <div>🎯 <b>AI फैसला:</b> {aj["headline"]}</div>
                <div style='margin-top:4px;'>⚡ <b>30m बनाम 5m विश्लेषण:</b> {aj["macro_vs_micro"]}</div>
                <div style='margin-top:4px;'>🌪️ <b>10-स्प्रेड क्लस्टर निष्कर्ष:</b> {aj["void_forensics"]}</div>
            </div>
            {aj.get("trail_box_html", "")}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🏛️ 1. पूरे {r["span_min"]:.0f}m का मैक्रो बेस</span>
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
        pct = min(100, int((len(eng["vault"]) / 12) * 100))
        left_body = f"""
        <div class='card-box' style='text-align:center; padding:45px 20px; margin-bottom:12px;'>
            <div style='font-size:20px; font-weight:800; color:#38bdf8; margin-bottom:8px;'>⏳ AI JSON इंजन के लिए शुरुआती डेटा जमा हो रहा है... ({pct}%)</div>
            <div style='font-size:14px; color:#94a3b8;'>तुरंत AI से फैसला लेने के लिए ऊपर <b>'🤖 अभी AI से फैसला / SL ट्रेल चेक कराएं'</b> बटन दबाएं।</div>
        </div>
        """

    dashboard_slot.markdown(clean_html(f"""
    <div>
        <div class='top-bar'>
            <div>
                <span style='font-size:21px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V13.0 (MULTI-VOID & SL TRAIL AI ENGINE)</span>
                <span style='font-size:13px; color:#94a3b8; margin-left:14px;'>🗄️ मेमोरी: <b style='color:#facc15;'>{mem_min:.1f} / 30.0 Min</b> | अगली AI जांच: <b>{next_sec}s</b></span>
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
                        📜 AI ट्रेड एवं स्टॉप-लॉस ट्रेलिंग हिस्ट्री (Initial SL ➔ Trailed SL और कारण सहित)
                    </div>
                    {hist_cards}
                </div>
            </div>

            <div class='void-panel'>
                <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                    🌪️ स्प्रेड क्लस्टर एवं ऑर्डरबुक पोस्टमार्टम (Top-10 AI Analyzed)
                </div>
                {cluster_banner}
                {void_cards}
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    dashboard_slot.warning("⏳ 24x7 V13.0 (Multi-Void & SL Trail AI Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")
    if eng.get("last_err"):
        st.error(f"🔴 API Error: {eng['last_err']}")
    time.sleep(2)
    st.rerun()

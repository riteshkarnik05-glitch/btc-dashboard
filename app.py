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

st.set_page_config(page_title="Pro Quant V14.2 - Zero-Blink Dynamic AI Engine", layout="wide")

def clean_html(raw_html: str) -> str:
    """Strips leading spaces so Streamlit renders pure HTML inside a single slot without ghost boxes"""
    return "\n".join(line.lstrip() for line in raw_html.splitlines() if line.strip())

st.markdown(clean_html("""
<style>
.stApp { background-color: #090d16; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 4.2rem !important; padding-bottom: 1.5rem !important; max-width: 98% !important; }
/* ZERO-BLINK & ANTI-FLICKER LOCK */
[data-stale="true"], .element-container, .stMarkdown, [data-testid="stAppViewBlockContainer"] * {
    opacity: 1 !important;
    transition: none !important;
    animation: none !important;
    filter: none !important;
}
.top-bar { background: #111827; border: 1px solid #1f2937; border-bottom: 2px solid #38bdf8; padding: 12px 16px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.main-grid { display: grid; grid-template-columns: 1.65fr 1fr; gap: 14px; align-items: start; }
@media (max-width: 1000px) { .main-grid { grid-template-columns: 1fr; } }
.lock-banner { padding: 14px 16px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.lock-buy { background: #052e16; border: 2px solid #22c55e; color: #4ade80; }
.lock-sell { background: #450a0a; border: 2px solid #ef4444; color: #f87171; }
.lock-wait { background: #1e293b; border: 2px dashed #64748b; color: #cbd5e1; }
.sub-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media (max-width: 768px) { .sub-grid { grid-template-columns: 1fr; } }
.card-box { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 13px 15px; }
.card-title { font-size: 12.5px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 8px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; display: flex; justify-content: space-between; }
.stat-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed #1f2937; }
.ai-sharp-box { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid #a855f7; border-left: 5px solid #c084fc; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
.trail-banner { background: #091e3a; border: 1px solid #38bdf8; border-left: 4px solid #facc15; border-radius: 8px; padding: 10px 12px; margin-top: 10px; font-size: 13.2px; color: #f8fafc; }
.json-pill { background: #090d16; border: 1px solid #4c1d95; padding: 4px 10px; border-radius: 6px; font-size: 12px; color: #e9d5ff; font-weight: 700; display: inline-block; margin-right: 8px; margin-top: 6px; }
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 270px; overflow-y: auto; }
.void-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 665px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; margin-top: 2px; }
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
        notes = [(987, 0.12), (0, 0.03), (659, 0.12), (0, 0.03), (440, 0.22)]
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
# HYPERLIQUID MARKET DATA & REAL L2 WALL DETECTOR
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_microstructure_snapshot():
    try:
        r_ob = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2.0)
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

        top_bid_node = max(bids, key=lambda x: float(x["sz"]))
        top_ask_node = max(asks, key=lambda x: float(x["sz"]))
        bid_wall_px, bid_wall_sz = float(top_bid_node["px"]), float(top_bid_node["sz"])
        ask_wall_px, ask_wall_sz = float(top_ask_node["px"]), float(top_ask_node["sz"])

        taker_buy = 0.0
        taker_sell = 0.0
        try:
            r_tr = requests.post(HYPERLIQUID_URL, json={"type": "recentTrades", "coin": "BTC"}, timeout=1.8)
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
            "px": mid_px, "best_bid": best_bid, "best_ask": best_ask, "spread": spread,
            "w_bid": w_bid, "w_ask": w_ask,
            "bid_wall_px": bid_wall_px, "bid_wall_sz": bid_wall_sz,
            "ask_wall_px": ask_wall_px, "ask_wall_sz": ask_wall_sz,
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
# INSTANT HARD-SL / TRAILED-SL CLOSER (SHARED BY 1s WORKER & AI THREAD)
# ============================================================================
def close_active_trade_immediately(eng, active_tr, exit_px, ist_str, reason_title, detailed_reason):
    move = (exit_px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - exit_px)
    active_tr["live_pts"] = move
    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)
    active_tr["close_time"] = ist_str
    active_tr["status"] = f"{reason_title} @ ${exit_px:,.1f} ({ist_str})"
    active_tr["exit_reason"] = detailed_reason

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"🚨 {reason_title} — ट्रेड तुरंत EXIT किया गया ({move:+.1f} Pts)"
        eng["report"]["lock_cls"] = "lock-wait"
        eng["report"]["lock_sub"] = detailed_reason

    if eng.get("ai_json_view"):
        eng["ai_json_view"]["badge_1"] = f"Status: {reason_title}"
        eng["ai_json_view"]["badge_3"] = f"Exit Price: ${exit_px:,.1f}"
        eng["ai_json_view"]["badge_4"] = f"Booked: {move:+.1f} Pts"
        eng["ai_json_view"]["headline"] = detailed_reason
        eng["ai_json_view"]["trail_box_html"] = (
            f"<div class='trail-banner' style='border-left-color:#ef4444; background:#3b0a0a;'>"
            f"🚨 <b>इंस्टेंट एग्जिट ({ist_str}):</b> {detailed_reason}</div>"
        )

# ============================================================================
# 100% DYNAMIC AI JSON ENGINE (NO FIXED POINT RULES)
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

def dynamic_microstructure_backup_brain(ctx, active_trade):
    m30 = ctx["m30"]
    m5 = ctx["m5"]
    m1 = ctx["m1"]
    px = ctx["px"]
    vwap = ctx["vwap"] if ctx["vwap"] > 0 else px
    vc = ctx["void_cluster"]

    bull_struct_support = min(m5["low"], vwap, ctx["bid_wall_px"]) - max(8.0, ctx["spread"] * 3.0)
    bear_struct_resist = max(m5["high"], vwap, ctx["ask_wall_px"]) + max(8.0, ctx["spread"] * 3.0)
    dynamic_range = max(40.0, m30["high"] - m30["low"])

    if active_trade is None:
        bull_align = (m30["tape_buy"] >= 53.5 and m5["tape_buy"] >= 55.0 and px >= vwap and vc["avg_l2_shift"] >= -3.0)
        bear_align = (m30["tape_buy"] <= 46.5 and m5["tape_buy"] <= 45.0 and px <= vwap and vc["avg_l2_shift"] <= 3.0)

        if bull_align and ctx["span_min"] >= 1.5:
            prob = min(92, int(55 + (m5["tape_buy"] - 50) * 1.8 + (m30["tape_buy"] - 50) * 1.2))
            return {
                "decision": "BUY",
                "probability": max(76, prob),
                "sl_price": round(bull_struct_support, 1),
                "target_price": round(px + dynamic_range * 1.6, 1),
                "headline": f"कन्फर्म BUY सिग्नल (${px:,.0f}) — 30m, 5m और स्प्रेड क्लस्टर तीनों में बायर्स मजबूत हैं।",
                "macro_vs_micro": f"30m Tape ({m30['tape_buy']:.0f}% Buy) के साथ आखिरी 5m में बाइंग {m5['tape_buy']:.0f}% पर है।",
                "void_forensics": vc["pattern_summary"]
            }
        elif bear_align and ctx["span_min"] >= 1.5:
            prob = min(92, int(55 + (50 - m5["tape_buy"]) * 1.8 + (50 - m30["tape_buy"]) * 1.2))
            return {
                "decision": "SELL",
                "probability": max(76, prob),
                "sl_price": round(bear_struct_resist, 1),
                "target_price": round(px - dynamic_range * 1.6, 1),
                "headline": f"कन्फर्म SELL सिग्नल (${px:,.0f}) — 30m, 5m और स्प्रेड क्लस्टर में सेलर्स हावी हैं।",
                "macro_vs_micro": f"30m Sell Tape ({100-m30['tape_buy']:.0f}%) के बाद आखिरी 5m में भी {100-m5['tape_buy']:.0f}% बिकवाली है।",
                "void_forensics": vc["pattern_summary"]
            }
        else:
            prob = int(45 + abs(m5["tape_buy"] - 50) * 1.1)
            return {
                "decision": "WAIT",
                "probability": min(68, prob),
                "sl_price": round(bull_struct_support, 1),
                "target_price": round(px + dynamic_range, 1),
                "headline": "WAIT (अभी कोई ट्रेड न लें) — डेटा में 75%+ वाली एकतरफा मजबूती नहीं है।",
                "macro_vs_micro": f"30m Tape ({m30['tape_buy']:.0f}% B) और 5m Tape ({m5['tape_buy']:.0f}% B) में स्पष्ट ब्रेकआउट का इंतज़ार करें।",
                "void_forensics": vc["pattern_summary"]
            }
    else:
        t_type = active_trade["type"]
        live_pts = active_trade["live_pts"]
        curr_sl = active_trade["sl_px"]

        if t_type == "BUY":
            if m5["tape_buy"] <= 43.0 or (m1["tape_buy"] <= 35.0 and m1["px_chg"] < -15.0):
                return {
                    "action": "EXIT",
                    "confidence": 88,
                    "trailing_sl": curr_sl,
                    "sl_trail_reason": "5m/1m ऑर्डरफ्लो में अचानक भारी बिकवाली आने से तुरंत एग्जिट।",
                    "headline": f"🚨 EXIT LONG @ ${px:,.0f} ({live_pts:+.1f}p) — ताज़ा ऑर्डरफ्लो बायर्स के खिलाफ पलट गया है!",
                    "macro_vs_micro": f"5m बाइंग गिरकर {m5['tape_buy']:.0f}% और 1m बाइंग {m1['tape_buy']:.0f}% रह गई है।",
                    "void_forensics": vc["pattern_summary"]
                }
            candidates = [lvl for lvl in [m5["low"] - 5.0, m1["low"] - 8.0, ctx["bid_wall_px"] - 4.0, vwap - 6.0] if curr_sl < lvl < px - 2.0]
            new_sl = round(max(candidates), 1) if candidates else curr_sl
            reason_txt = (
                f"डायनामिक स्ट्रक्चर (1m Low ${m1['low']:,.0f}, 5m Low ${m5['low']:,.0f}, L2 Bid Wall ${ctx['bid_wall_px']:,.0f}) के आधार पर SL ${new_sl:,.1f} तय किया गया।"
                if new_sl > curr_sl else
                f"अभी नया माइक्रो-सपोर्ट पुराने SL (${curr_sl:,.1f}) से ऊपर नहीं बना है।"
            )
            return {
                "action": "HOLD",
                "confidence": 82,
                "trailing_sl": new_sl,
                "sl_trail_reason": reason_txt,
                "headline": f"✅ HOLD LONG ({live_pts:+.1f}p) — बाइंग स्ट्रक्चर सुरक्षित है (Dynamic SL: ${new_sl:,.1f})।",
                "macro_vs_micro": f"5m Tape ({m5['tape_buy']:.0f}% B) और 1m Tape ({m1['tape_buy']:.0f}% B) ट्रेड को सपोर्ट कर रहे हैं।",
                "void_forensics": vc["pattern_summary"]
            }
        else:
            if m5["tape_buy"] >= 57.0 or (m1["tape_buy"] >= 65.0 and m1["px_chg"] > 15.0):
                return {
                    "action": "EXIT",
                    "confidence": 88,
                    "trailing_sl": curr_sl,
                    "sl_trail_reason": "5m/1m ऑर्डरफ्लो में अचानक भारी बाइंग आने से तुरंत एग्जिट।",
                    "headline": f"🚨 EXIT SHORT @ ${px:,.0f} ({live_pts:+.1f}p) — नीचे से आक्रामक बाइंग आ रही है!",
                    "macro_vs_micro": f"5m बाइंग उछलकर {m5['tape_buy']:.0f}% और 1m बाइंग {m1['tape_buy']:.0f}% हो गई है।",
                    "void_forensics": vc["pattern_summary"]
                }
            candidates = [lvl for lvl in [m5["high"] + 5.0, m1["high"] + 8.0, ctx["ask_wall_px"] + 4.0, vwap + 6.0] if px + 2.0 < lvl < curr_sl]
            new_sl = round(min(candidates), 1) if candidates else curr_sl
            reason_txt = (
                f"डायनामिक रेजिस्टेंस स्ट्रक्चर (1m High ${m1['high']:,.0f}, 5m High ${m5['high']:,.0f}, L2 Ask Wall ${ctx['ask_wall_px']:,.0f}) के आधार पर SL ${new_sl:,.1f} पर ट्रेल किया गया।"
                if new_sl < curr_sl else
                f"अभी नया माइक्रो-रेजिस्टेंस पुराने SL (${curr_sl:,.1f}) से नीचे नहीं बना है।"
            )
            return {
                "action": "HOLD",
                "confidence": 82,
                "trailing_sl": new_sl,
                "sl_trail_reason": reason_txt,
                "headline": f"✅ HOLD SHORT ({live_pts:+.1f}p) — सेलिंग प्रेशर बरकरार है (Dynamic SL: ${new_sl:,.1f})।",
                "macro_vs_micro": f"5m Sell Tape ({100-m5['tape_buy']:.0f}%) और 1m Sell Tape ({100-m1['tape_buy']:.0f}%) आपके पक्ष में हैं।",
                "void_forensics": vc["pattern_summary"]
            }

def call_gemini_json_engine(api_key, ctx, active_trade):
    m30 = ctx["m30"]
    m5 = ctx["m5"]
    m1 = ctx["m1"]
    px = ctx["px"]
    vwap = ctx["vwap"]
    vc = ctx["void_cluster"]

    if active_trade is None:
        prompt = f"""
तुम एक स्वायत्त (Autonomous) इंट्राडे BTCUSDT AI ट्रेडिंग इंजन हो। तुम्हारे लिए कोई भी फिक्स पॉइंट नियम नहीं है—तुम्हें नीचे दिए गए लाइव ऑर्डरबुक वॉल्स, 30m/5m/1m माइक्रोस्ट्रक्चर और पिछले 10 स्प्रेड्स के क्लस्टर को पढ़कर 100% डायनामिक फैसला लेना है।

1. लाइव मार्केट और ऑर्डरबुक स्ट्रक्चर:
- वर्तमान प्राइस: ${px:,.1f} (Best Bid: ${ctx['best_bid']:,.1f}, Best Ask: ${ctx['best_ask']:,.1f}, Spread: ${ctx['spread']:.1f}) | सेशन VWAP: ${vwap:,.1f}
- ऑर्डरबुक की सबसे बड़ी बाइंग दीवार (Major L2 Bid Support Wall): ${ctx['bid_wall_px']:,.1f} (Size: {ctx['bid_wall_sz']:.2f} BTC)
- ऑर्डरबुक की सबसे बड़ी सेलिंग दीवार (Major L2 Ask Resistance Wall): ${ctx['ask_wall_px']:,.1f} (Size: {ctx['ask_wall_sz']:.2f} BTC)
- पूरे 30m डेटा: बदलाव {m30['px_chg']:+.1f} Pts (High: ${m30['high']:,.0f}, Low: ${m30['low']:,.0f}) | 30m Tape: {m30['tape_buy']:.1f}% Buy | 30m L2: {m30['l2_buy']:.1f}% Bids
- आखिरी 5m डेटा: बदलाव {m5['px_chg']:+.1f} Pts (5m High: ${m5['high']:,.0f}, 5m Low: ${m5['low']:,.0f}) | 5m Tape: {m5['tape_buy']:.1f}% Buy | 5m L2: {m5['l2_buy']:.1f}% Bids
- आखिरी 1m (ताज़ा टिक मोमेंटम): बदलाव {m1['px_chg']:+.1f} Pts (1m High: ${m1['high']:,.0f}, 1m Low: ${m1['low']:,.0f}) | 1m Tape: {m1['tape_buy']:.1f}% Buy

2. पिछले {vc['count']} बड़े स्प्रेड्स (Spread > $4.0) का क्लस्टर पैटर्न:
- सारांश: {vc['pattern_summary']}
- स्प्रेड्स की लिस्ट:
{vc['prompt_table']}

डायनामिक निर्णय के नियम:
1. "BUY" या "SELL" केवल तभी चुनो जब संभावना (probability) 75 से 95 के बीच हो।
2. `sl_price` और `target_price` किसी फिक्स पॉइंट पर मत रखो—इन्हें 5m/1m High-Low, VWAP और L2 Bid/Ask Wall के असली स्ट्रक्चर के हिसाब से डायनामिक तय करो।
3. केवल शुद्ध JSON में जवाब दो:
{{
  "decision": "BUY" या "SELL" या "WAIT",
  "probability": 0 से 100 के बीच पूर्णांक (int),
  "sl_price": संख्या (float - मार्केट स्ट्रक्चर के अनुसार डायनामिक स्टॉप-लॉस प्राइस),
  "target_price": संख्या (float - मार्केट स्ट्रक्चर के अनुसार डायनामिक टारगेट प्राइस),
  "headline": "1 तीखी लाइन में स्पष्ट सिग्नल और कारण (हिंदी में)",
  "macro_vs_micro": "1 लाइन में 30m बनाम 5m/1m की तुलना (हिंदी में)",
  "void_forensics": "1 लाइन में पिछले सभी स्प्रेड्स के पैटर्न का निष्कर्ष (हिंदी में)"
}}
"""
    else:
        t_type = active_trade["type"]
        t_entry = active_trade["entry"]
        live_pts = active_trade["live_pts"]
        peak_pts = active_trade["peak_pts"]
        init_sl = active_trade["initial_sl"]
        curr_sl = active_trade["sl_px"]
        curr_sl_pts = (curr_sl - t_entry) if t_type == "BUY" else (t_entry - curr_sl)
        dur_min = (time.time() - active_trade["open_ts"]) / 60.0

        prompt = f"""
तुम एक स्वायत्त (Autonomous) इंट्राडे BTCUSDT AI ट्रेड मैनेजर हो। अभी हमारा एक ट्रेड चालू (ACTIVE) है। तुम्हारे ऊपर कोई फिक्स पॉइंट का नियम नहीं है। लाइव डेटा देखकर खुद तय करो कि:
(A) क्या खतरा दिख रहा है या मोमेंटम खत्म हो गया है इसलिए तुरंत "EXIT" करना है?
(B) या "HOLD" रखना है और मार्केट की ताज़ा स्थिति (1m/5m स्विंग, VWAP, L2 ऑर्डरबुक दीवारें, या बड़ा प्रॉफिट लॉक करने की ज़रूरत) देखकर डायनामिक स्टॉप-लॉस (`trailing_sl`) को कितना आगे बढ़ाना है?

चालू ट्रेड की स्थिति:
- ट्रेड दिशा: {t_type} | एंट्री प्राइस: ${t_entry:,.1f} | वर्तमान लाइव प्राइस: ${px:,.1f}
- लाइव प्रॉफिट/लॉस: {live_pts:+.1f} Points | अब तक का अधिकतम प्रॉफिट (Peak): +{peak_pts:.1f} Points
- शुरुआती SL: ${init_sl:,.1f} | वर्तमान एक्टिव SL: ${curr_sl:,.1f} (एंट्री से {curr_sl_pts:+.1f} Points पर) | समय: {dur_min:.1f} मिनट

ताज़ा लाइव माइक्रोस्ट्रक्चर डेटा:
- ऑर्डरबुक L2 सबसे बड़ी Bid सपोर्ट दीवार: ${ctx['bid_wall_px']:,.1f} ({ctx['bid_wall_sz']:.2f} BTC) | सबसे बड़ी Ask रेजिस्टेंस दीवार: ${ctx['ask_wall_px']:,.1f} ({ctx['ask_wall_sz']:.2f} BTC)
- सेशन VWAP: ${vwap:,.1f}
- पूरे 30m का डेटा: Tape {m30['tape_buy']:.1f}% Buy | L2 {m30['l2_buy']:.1f}% Bids
- आखिरी 5m का डेटा: प्राइस {m5['px_chg']:+.1f} Pts (5m High: ${m5['high']:,.0f}, 5m Low: ${m5['low']:,.0f}) | 5m Tape: {m5['tape_buy']:.1f}% Buy | 5m L2: {m5['l2_buy']:.1f}% Bids
- आखिरी 1m का एकदम ताज़ा डेटा: प्राइस {m1['px_chg']:+.1f} Pts (1m High: ${m1['high']:,.0f}, 1m Low: ${m1['low']:,.0f}) | 1m Tape: {m1['tape_buy']:.1f}% Buy | 1m L2: {m1['l2_buy']:.1f}% Bids
- पिछले {vc['count']} स्प्रेड्स का क्लस्टर पैटर्न: {vc['pattern_summary']}
{vc['prompt_table']}

डायनामिक निर्णय के सख्त निर्देश:
1. अगर ऑर्डरफ्लो (1m/5m Tape या Spread Cluster) हमारे ट्रेड के खिलाफ पलट चुका है या बड़ा प्रॉफिट बनने के बाद मोमेंटम टूट रहा है, तो बिना इंतज़ार किए `"action": "EXIT"` चुनो।
2. अगर `"action": "HOLD"` चुनते हो, तो तुम पूरी तरह स्वतंत्र हो कि डेटा के हिसाब से `trailing_sl` (प्राइस में, जैसे 73501.0) को कितना टाइट या स्ट्रक्चरल रखना है:
   - ध्यान रहे: BUY ट्रेड में `trailing_sl` हमेशा पुराने SL (${curr_sl:,.1f}) के बराबर या उससे ऊपर होना चाहिए (और वर्तमान प्राइस ${px:,.1f} से नीचे)। SELL ट्रेड में पुराने SL के बराबर या उससे नीचे होना चाहिए (और वर्तमान प्राइस ${px:,.1f} से ऊपर)।
3. केवल शुद्ध JSON में जवाब दो:
{{
  "action": "HOLD" या "EXIT",
  "confidence": 0 से 100 के बीच पूर्णांक (int),
  "trailing_sl": संख्या (float - सटीक नया स्टॉप-लॉस प्राइस, जैसे {curr_sl:.1f}),
  "sl_trail_reason": "1 स्पष्ट लाइन में बताओ कि डेटा के किस लेवल (L2 Wall / 1m-5m Swing / Profit Lock) को देखकर यह डायनामिक SL तय किया गया (हिंदी में)",
  "headline": "1 तीखी लाइन में HOLD या EXIT का स्पष्ट आदेश (हिंदी में)",
  "macro_vs_micro": "1 लाइन में 30m बनाम 5m/1m डेटा का चालू ट्रेड पर असर (हिंदी में)",
  "void_forensics": "1 लाइन में 10-स्प्रेड क्लस्टर का चालू ट्रेड पर असर (हिंदी में)"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 400
        }
    }

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    for mod in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                raw_txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                parsed = parse_ai_json_safely(raw_txt)
                if parsed:
                    return parsed, f"🟢 Dynamic AI Brain ({mod})"
        except Exception:
            continue

    return dynamic_microstructure_backup_brain(ctx, active_trade), "⚡ Dynamic Microstructure Brain"

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
        vault_1m = [d for d in vault if (now_ts - d["ts"]) <= 60.0]

        m30 = compute_slice_metrics(vault)
        m5 = compute_slice_metrics(vault_5m)
        m1 = compute_slice_metrics(vault_1m)
        voids_30m = [v for v in eng["voids"] if (now_ts - v.get("ts", now_ts)) <= 1800]
        void_cluster = analyze_void_cluster(voids_30m, px)

        ctx = {
            "time": ist_str, "px": px,
            "best_bid": eng.get("best_bid", px), "best_ask": eng.get("best_ask", px),
            "spread": eng.get("spread", 1.0),
            "bid_wall_px": eng.get("bid_wall_px", px - 25.0), "bid_wall_sz": eng.get("bid_wall_sz", 1.0),
            "ask_wall_px": eng.get("ask_wall_px", px + 25.0), "ask_wall_sz": eng.get("ask_wall_sz", 1.0),
            "vwap": eng["vwap"] if eng["vwap"] > 0 else px,
            "span_min": span_min, "m30": m30, "m5": m5, "m1": m1,
            "void_cluster": void_cluster, "recent_voids": voids_30m[:10]
        }

        api_key = eng.get("api_key", "").strip()
        active_tr_snapshot = eng.get("active_trade")
        snapshot_trade_id = active_tr_snapshot["open_ts"] if active_tr_snapshot else None

        if api_key:
            ai_json, status_str = call_gemini_json_engine(api_key, ctx, active_tr_snapshot)
        else:
            ai_json, status_str = dynamic_microstructure_backup_brain(ctx, active_tr_snapshot), "🟡 Local Dynamic Engine"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()

        current_live_tr = eng.get("active_trade")
        if snapshot_trade_id is not None and (current_live_tr is None or current_live_tr["open_ts"] != snapshot_trade_id):
            return

        live_px_now = eng["px"]
        ist_now_str = get_ist_time_str()

        if current_live_tr is None:
            dec = str(ai_json.get("decision", "WAIT")).upper()
            prob = int(ai_json.get("probability", 50))
            raw_sl = float(ai_json.get("sl_price", live_px_now - 90.0 if dec == "BUY" else live_px_now + 90.0))
            tp_px = float(ai_json.get("target_price", live_px_now + 280.0 if dec == "BUY" else live_px_now - 280.0))

            if dec == "BUY":
                sl_px = min(live_px_now - 15.0, max(live_px_now - 250.0, raw_sl))
            elif dec == "SELL":
                sl_px = max(live_px_now + 15.0, min(live_px_now + 250.0, raw_sl))
            else:
                sl_px = raw_sl

            if dec in ["BUY", "SELL"] and prob >= 75 and span_min >= 1.2:
                init_sl_rounded = round(sl_px, 1)
                init_sl_pts = round((init_sl_rounded - live_px_now) if dec == "BUY" else (live_px_now - init_sl_rounded), 1)
                new_trade = {
                    "open_ts": time.time(),
                    "open_time": ist_now_str,
                    "close_time": "",
                    "type": dec,
                    "entry": live_px_now,
                    "prob": prob,
                    "initial_sl": init_sl_rounded,
                    "sl_px": init_sl_rounded,
                    "sl_pts": init_sl_pts,
                    "tp_px": round(tp_px, 1),
                    "trail_count": 0,
                    "last_trail_msg": f"🛡️ डायनामिक AI शुरुआती SL: ${init_sl_rounded:,.1f} ({init_sl_pts:+.1f} Pts)",
                    "trail_log": [],
                    "live_pts": 0.0,
                    "peak_pts": 0.0,
                    "status": "ACTIVE (AI MANAGING)",
                    "entry_reason": ai_json.get("headline", "AI Confirmed Entry"),
                    "exit_reason": "अभी ट्रेड चालू है — 1s रियल-टाइम SL गार्ड + 3m AI निगरानी सक्रिय"
                }
                eng["active_trade"] = new_trade
                eng["signal_history"].insert(0, new_trade)
                eng["signal_history"] = eng["signal_history"][:30]
                eng["sound_event"] = {"id": time.time(), "type": "BULL" if dec == "BUY" else "BEAR"}

                lock_title = f"🟢 AI ने नया {dec} ट्रेड लॉक किया! (संभावना: {prob}%)" if dec == "BUY" else f"🔴 AI ने नया {dec} ट्रेड लॉक किया! (संभावना: {prob}%)"
                lock_cls = "lock-buy" if dec == "BUY" else "lock-sell"
                lock_sub = f"एंट्री: ${live_px_now:,.1f} | डायनामिक AI SL: ${init_sl_rounded:,.1f} ({init_sl_pts:+.1f} Pts) | टारगेट: ${tp_px:,.1f}"
            else:
                lock_title = f"⚪ AI का फैसला: WAIT — कोई ट्रेड नहीं (संभावना सिर्फ {prob}%)"
                lock_cls = "lock-wait"
                lock_sub = f"पिछले {void_cluster['count']} स्प्रेड्स और 30m/5m डेटा में 75%+ वाली एकतरफा शर्त पूरी नहीं हुई।"

            eng["ai_json_view"] = {
                "mode": "ENTRY_SCAN",
                "badge_1": f"AI Decision: {dec}",
                "badge_2": f"Probability: {prob}%",
                "badge_3": f"Dynamic SL: ${sl_px:,.1f}",
                "badge_4": f"Spreads Analyzed: {void_cluster['count']}",
                "headline": ai_json.get("headline", ""),
                "macro_vs_micro": ai_json.get("macro_vs_micro", ""),
                "void_forensics": ai_json.get("void_forensics", ""),
                "trail_box_html": ""
            }
            ctx["lock_title"] = lock_title
            ctx["lock_cls"] = lock_cls
            ctx["lock_sub"] = lock_sub
            eng["report"] = ctx

        else:
            act = str(ai_json.get("action", "HOLD")).upper()
            conf = int(ai_json.get("confidence", 80))
            raw_ai_sl = float(ai_json.get("trailing_sl", current_live_tr["sl_px"]))
            trail_reason = str(ai_json.get("sl_trail_reason", "ऑर्डरबुक और प्राइस स्ट्रक्चर के अनुसार डायनामिक SL अपडेट।")).strip()

            if 0 < abs(raw_ai_sl) < 5000:
                ai_trail_sl = (current_live_tr["entry"] + raw_ai_sl) if current_live_tr["type"] == "BUY" else (current_live_tr["entry"] - raw_ai_sl)
            else:
                ai_trail_sl = raw_ai_sl

            if act == "EXIT":
                close_active_trade_immediately(
                    eng, current_live_tr, live_px_now, ist_now_str,
                    "AI EXIT", f"🤖 AI ने तुरंत एग्जिट किया: {ai_json.get('headline', trail_reason)}"
                )
                return

            old_sl = current_live_tr["sl_px"]

            if current_live_tr["type"] == "BUY" and ai_trail_sl > old_sl + 0.5:
                if live_px_now <= ai_trail_sl:
                    current_live_tr["sl_px"] = round(ai_trail_sl, 1)
                    current_live_tr["sl_pts"] = round(ai_trail_sl - current_live_tr["entry"], 1)
                    close_active_trade_immediately(
                        eng, current_live_tr, live_px_now, ist_now_str,
                        "DYNAMIC SL BREACHED",
                        f"🛡️ AI ने SL को ${ai_trail_sl:,.1f} ({current_live_tr['sl_pts']:+.1f}p) पर लॉक किया और लाइव प्राइस (${live_px_now:,.1f}) उसके नीचे आने से तुरंत EXIT!"
                    )
                    return
                else:
                    current_live_tr["sl_px"] = round(ai_trail_sl, 1)
                    current_live_tr["sl_pts"] = round(current_live_tr["sl_px"] - current_live_tr["entry"], 1)
                    sl_trailed_now = True

            elif current_live_tr["type"] == "SELL" and ai_trail_sl < old_sl - 0.5:
                if live_px_now >= ai_trail_sl:
                    current_live_tr["sl_px"] = round(ai_trail_sl, 1)
                    current_live_tr["sl_pts"] = round(current_live_tr["entry"] - ai_trail_sl, 1)
                    close_active_trade_immediately(
                        eng, current_live_tr, live_px_now, ist_now_str,
                        "DYNAMIC SL BREACHED",
                        f"🛡️ AI ने SL को ${ai_trail_sl:,.1f} ({current_live_tr['sl_pts']:+.1f}p) पर लॉक किया और लाइव प्राइस (${live_px_now:,.1f}) उसके ऊपर आने से तुरंत EXIT!"
                    )
                    return
                else:
                    current_live_tr["sl_px"] = round(ai_trail_sl, 1)
                    current_live_tr["sl_pts"] = round(current_live_tr["entry"] - current_live_tr["sl_px"], 1)
                    sl_trailed_now = True
            else:
                sl_trailed_now = False

            curr_sl_pts = current_live_tr["sl_pts"]

            if sl_trailed_now:
                current_live_tr["trail_count"] += 1
                pts_shifted = abs(current_live_tr["sl_px"] - old_sl)
                lock_tag = f"+{curr_sl_pts:.1f} Pts प्रॉफिट लॉक" if curr_sl_pts >= 0 else f"रिस्क घटकर {abs(curr_sl_pts):.1f} Pts रह गया"

                event_str = (
                    f"🔄 <b>डायनामिक SL ट्रेल #{current_live_tr['trail_count']} ({ist_now_str}):</b> "
                    f"<span style='color:#f87171; text-decoration:line-through;'>${old_sl:,.1f}</span> ➔ "
                    f"<b style='color:#4ade80; font-size:14.5px;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> "
                    f"(<span style='color:#facc15;'>+{pts_shifted:.1f}p शिफ्ट | {lock_tag}</span>)<br>"
                    f"📌 <b>AI डायनामिक कारण:</b> {trail_reason}"
                )
                current_live_tr["last_trail_msg"] = event_str
                current_live_tr["trail_log"].insert(
                    0, f"[{ist_now_str}] ${old_sl:,.1f} ➔ ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p): {trail_reason}"
                )
                eng["sound_event"] = {"id": time.time(), "type": "TRAIL"}
            else:
                event_str = (
                    f"🛡️ <b>सक्रिय स्टॉप-लॉस गारंटी ({ist_now_str}):</b> एक्टिव SL: <b style='color:#facc15;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> | "
                    f"अगर लाइव पॉइंट्स <b>{curr_sl_pts:+.1f}p</b> को छूते हैं तो 1 सेकंड में ऑटो-एग्जिट हो जाएगा।<br>"
                    f"📌 <b>AI SL नोट:</b> {trail_reason}"
                )

            trail_box_html = f"<div class='trail-banner'>{event_str}</div>"

            lock_title = f"{'🟢' if current_live_tr['type']=='BUY' else '🔴'} AI ने {current_live_tr['type']} ट्रेड को HOLD रखा है (Live: {current_live_tr['live_pts']:+.1f} Pts)"
            lock_cls = "lock-buy" if current_live_tr["type"] == "BUY" else "lock-sell"
            lock_sub = (
                f"एंट्री: ${current_live_tr['entry']:,.1f} | "
                f"एक्टिव डायनामिक SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts) | "
                f"ट्रेल: {current_live_tr['trail_count']} बार (1s Instant Guard ON)"
            )

            eng["ai_json_view"] = {
                "mode": "TRADE_MANAGER",
                "badge_1": f"AI Command: {act} ({conf}%)",
                "badge_2": f"Entry: ${current_live_tr['entry']:,.1f}",
                "badge_3": f"Active SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p)",
                "badge_4": f"Trailed: {current_live_tr['trail_count']}x",
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
# 24x7 1-SECOND BACKGROUND WORKER (INSTANT TICK-LEVEL SL EXECUTION)
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
                eng["best_bid"] = snap["best_bid"]
                eng["best_ask"] = snap["best_ask"]
                eng["spread"] = spread
                eng["bid_wall_px"] = snap["bid_wall_px"]
                eng["bid_wall_sz"] = snap["bid_wall_sz"]
                eng["ask_wall_px"] = snap["ask_wall_px"]
                eng["ask_wall_sz"] = snap["ask_wall_sz"]
                eng["last_update"] = ist_str

                active_tr = eng.get("active_trade")
                if active_tr is not None:
                    move = (px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - px)
                    active_tr["live_pts"] = move
                    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)
                    sl_pts_locked = active_tr["sl_pts"]

                    if active_tr["type"] == "BUY":
                        sl_breached = (px <= active_tr["sl_px"]) or (move <= sl_pts_locked)
                    else:
                        sl_breached = (px >= active_tr["sl_px"]) or (move <= sl_pts_locked)

                    if sl_breached:
                        sl_kind = "TRAILED SL HIT" if active_tr["trail_count"] > 0 else "INITIAL SL HIT"
                        detail_msg = (
                            f"🛡️ {sl_kind}: लाइव प्राइस ${px:,.1f} ({move:+.1f} Pts) ने आपके एक्टिव स्टॉप-लॉस "
                            f"${active_tr['sl_px']:,.1f} ({sl_pts_locked:+.1f} Pts) को छू लिया — बिना अगली AI जांच का इंतज़ार किए तुरंत एग्जिट!"
                        )
                        close_active_trade_immediately(eng, active_tr, px, ist_str, sl_kind, detail_msg)

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
        time.sleep(1)

@st.cache_resource
def get_master_engine_v14_2():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "best_bid": 0.0, "best_ask": 0.0, "spread": 0.0,
        "bid_wall_px": 0.0, "bid_wall_sz": 0.0, "ask_wall_px": 0.0, "ask_wall_sz": 0.0,
        "last_update": "--:--:--",
        "vault": [], "voids": [], "signal_history": [],
        "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "vwap": 0.0, "oi_start": 0.0, "oi_chg": 0.0,
        "report": None,
        "ai_json_view": {
            "mode": "INIT",
            "badge_1": "AI Status: Waiting",
            "badge_2": "Probability: --%",
            "badge_3": "Dynamic SL: --",
            "badge_4": "Spreads: 0",
            "headline": "⏳ पहली रिपोर्ट बनते ही AI 100% डायनामिक स्ट्रक्चर से एंट्री/SL तय करेगा...",
            "macro_vs_micro": "डेटा बफर तैयार हो रहा है...",
            "void_forensics": "स्प्रेड क्लस्टर पर नज़र रखी जा रही है...",
            "trail_box_html": ""
        },
        "ai_status": "🤖 100% Dynamic AI + 1s SL Guard",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v14_2()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# STATIC CONTROLS & ZERO-BLINK IN-PLACE LIVE STREAMING LOOP
# ============================================================================
c_act1, c_act2, c_act3 = st.columns([0.34, 0.20, 0.46])
with c_act1:
    if st.button("🤖 अभी AI से डायनामिक फैसला / SL जांच कराएं"):
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()
with c_act2:
    test_snd = st.button("🔔 साउंड टेस्ट करें")
with c_act3:
    sound_enabled = st.checkbox("🔊 AI एंट्री, डायनामिक SL ट्रेल और इंस्टेंट एग्जिट पर साउंड बजाएं", value=True)

dashboard_slot = st.empty()
audio_slot = st.empty()

if test_snd:
    b64 = create_sound_b64("BULL")
    audio_slot.empty()
    with audio_slot:
        components.html(f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>', height=0, width=0)

# Continuous in-place DOM update loop (No st.rerun() -> ZERO screen blinking)
while True:
    curr_snd = eng.get("sound_event", {"id": 0.0, "type": "BULL"})
    if sound_enabled and curr_snd["id"] > 0 and curr_snd["id"] != st.session_state["last_played_sound_id"]:
        st.session_state["last_played_sound_id"] = curr_snd["id"]
        b64 = create_sound_b64(curr_snd["type"])
        audio_slot.empty()
        with audio_slot:
            components.html(f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>', height=0, width=0)

    if eng["px"] > 0:
        mem_min = (time.time() - eng["vault"][0]["ts"]) / 60.0 if len(eng["vault"]) > 1 else 0.0
        next_sec = max(0, int(180 - (time.time() - eng["last_report_ts"]))) if eng["last_report_ts"] > 0 else 0

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            is_act = "ACTIVE" in h["status"]
            sts_badge = "🟢 AI ACTIVE (1s SL Guard)" if is_act else f"🏁 {h['status']}"
            sl_pts_val = h.get("sl_pts", 0.0)
            trail_info = (
                f"शुरुआती SL: ${h['initial_sl']:,.1f} ➔ एक्टिव SL: <b style='color:#facc15;'>${h['sl_px']:,.1f} ({sl_pts_val:+.1f}p)</b> (ट्रेल: {h['trail_count']}x)"
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
                <div style='text-align:right; min-width:105px;'>
                    <div style='font-size:15px; font-weight:900; color:{p_col};'>{h["live_pts"]:+.1f}p</div>
                    <div style='font-size:11px; color:#94a3b8;'>Peak: +{h["peak_pts"]:.1f}p</div>
                </div>
            </div>
            """
        if not hist_cards:
            hist_cards = "<div style='text-align:center; color:#64748b; padding-top:75px;'>अभी तक AI ने कोई ट्रेड लॉक नहीं किया है (संभावना 75%+ होने पर ही ट्रेड लॉक होगा)।</div>"

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

        if eng["report"]:
            r = eng["report"]
            m30 = r["m30"]
            m5 = r["m5"]
            aj = eng["ai_json_view"]
            c30_col = "#4ade80" if m30["px_chg"] >= 0 else "#f87171"
            c5_col = "#4ade80" if m5["px_chg"] >= 0 else "#f87171"

            act_tr = eng.get("active_trade")
            if act_tr:
                right_stat_label = f"LIVE PNL (SL: {act_tr['sl_pts']:+.1f}p)"
                right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
                right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
            else:
                right_stat_label = "AI CYCLE TIMER"
                right_stat_val = f"{next_sec}s"
                right_stat_col = "#38bdf8"

            left_body = f"""
            <div class='lock-banner {r["lock_cls"]}'>
                <div>
                    <div style='font-size:18px; font-weight:900;'>{r["lock_title"]}</div>
                    <div style='font-size:12.5px; margin-top:3px; opacity:0.92;'>{r["lock_sub"]}</div>
                </div>
                <div style='text-align:right; min-width:145px;'>
                    <div style='font-size:11px; text-transform:uppercase; opacity:0.85;'>{right_stat_label}</div>
                    <div style='font-size:23px; font-weight:900; color:{right_stat_col};'>{right_stat_val}</div>
                    <div style='font-size:11px; opacity:0.8;'>अपडेट: {r["time"]}</div>
                </div>
            </div>

            <div class='ai-sharp-box'>
                <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3b0764; padding-bottom:6px; margin-bottom:8px;'>
                    <span style='font-size:15px; font-weight:900; color:#c084fc;'>🧠 100% डायनामिक AI डिसीजन एवं 1-सेकंड SL गार्ड</span>
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
                    <div style='margin-top:4px;'>⚡ <b>30m बनाम 5m/1m विश्लेषण:</b> {aj["macro_vs_micro"]}</div>
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
                        <span>⚡ 2. आखिरी 5m ट्रिगर और L2 वॉल्स</span>
                        <span style='color:{c5_col};'>{m5["px_chg"]:+.1f} Pts</span>
                    </div>
                    <div class='stat-row'><span>आखिरी 5m Taker Tape:</span><b><span style='color:#4ade80;'>{m5["tape_buy"]:.0f}% Buy</span> ({m5["tape_buy"]-m30["tape_buy"]:+.0f}% Shift)</b></div>
                    <div class='stat-row'><span>L2 सबसे बड़ी Bid/Ask दीवार:</span><b><span style='color:#4ade80;'>${eng["bid_wall_px"]:,.0f}</span> / <span style='color:#f87171;'>${eng["ask_wall_px"]:,.0f}</span></b></div>
                    <div class='stat-row' style='border:none;'><span>5m हाई / लो रेंज:</span><b>${m5["low"]:,.0f} — ${m5["high"]:,.0f}</b></div>
                </div>
            </div>
            """
        else:
            pct = min(100, int((len(eng["vault"]) / 12) * 100))
            left_body = f"""
            <div class='card-box' style='text-align:center; padding:45px 20px; margin-bottom:12px;'>
                <div style='font-size:20px; font-weight:800; color:#38bdf8; margin-bottom:8px;'>⏳ डायनामिक AI इंजन के लिए शुरुआती डेटा जमा हो रहा है... ({pct}%)</div>
                <div style='font-size:14px; color:#94a3b8;'>तुरंत AI से फैसला लेने के लिए ऊपर <b>'🤖 अभी AI से डायनामिक फैसला / SL जांच कराएं'</b> बटन दबाएं।</div>
            </div>
            """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V14.2 (ZERO-BLINK DYNAMIC AI)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🗄️ मेमोरी: <b style='color:#facc15;'>{mem_min:.1f} / 30.0 Min</b> | अगली AI जांच: <b>{next_sec}s</b></div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:21px; font-weight:900; color:#f8fafc;'>BTC: ${eng['px']:,.1f}</div>
                    <div style='color:#4ade80; font-size:12px; font-weight:bold;'>● {eng['last_update']}</div>
                </div>
            </div>

            <div class='main-grid'>
                <div>
                    {left_body}
                    <div class='history-panel'>
                        <div style='font-size:14px; font-weight:900; color:#4ade80; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                            📜 AI ट्रेड एवं डायनामिक स्टॉप-लॉस हिस्ट्री (Initial SL ➔ Trailed SL Price & Points सहित)
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

    else:
        dashboard_slot.warning("⏳ 24x7 V14.2 (Zero-Blink Dynamic AI Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")

    time.sleep(1.5)

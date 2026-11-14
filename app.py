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

st.set_page_config(page_title="Pro Quant V20.0 - Hard-Locked Renko & AI Trail Engine", layout="wide")

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
div[data-baseweb="select"] > div { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #c084fc !important; border-radius: 7px !important; font-weight: 700 !important; }
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
# LIVE GEMINI API MODEL DISCOVERY (PRO-MODEL PRIORITY)
# ============================================================================
AUTO_MODEL_LABEL = "🤖 Auto (Pro/Advanced Priority)"

def score_model_priority(model_name: str) -> tuple:
    tier = 0 if ("pro" in model_name and "vision" not in model_name) else (
        1 if "exp" in model_name else (
            2 if ("flash" in model_name and "lite" not in model_name and "8b" not in model_name) else 3
        )
    )
    gen = 0 if "2.5" in model_name else (
        1 if "2.0" in model_name else (
            2 if "1.5" in model_name else 3
        )
    )
    is_dated = 1 if re.search(r"-\d{3,4}", model_name) else 0
    return (tier, gen, is_dated, model_name)

def fetch_available_api_models(api_key):
    default_models = [
        "gemini-2.5-pro",
        "gemini-1.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite"
    ]
    if not api_key:
        return default_models
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=4.0)
        if r.status_code == 200:
            models_data = r.json().get("models", [])
            discovered = []
            skip_keywords = ["embedding", "aqa", "imagen", "veo", "tts", "audio", "vision", "robotics", "computer-use", "learnlm"]
            for m in models_data:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name:
                    if not any(kw in name for kw in skip_keywords):
                        discovered.append(name)
            if discovered:
                discovered.sort(key=score_model_priority)
                return discovered
    except Exception:
        pass
    return default_models

# ============================================================================
# HYPERLIQUID MARKET DATA + FIXED-GRID AI-RENKO CONFIRMED CLOSE ENGINE
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

def fetch_renko_supertrend_and_vwap():
    """
    Fixed-Grid Non-Repainting Python implementation of 'Dr Devendra AI-Renko':
    - Anchors initial brick to a fixed mathematical multiple of box_size so new 1m bars never shift historical bricks.
    """
    try:
        now_ms = int(time.time() * 1000)

        # 1. Fetch Daily Candles for 23H/Daily ATR-5 Auto Box Size
        box_size = 150.0
        macro_range = 1500.0
        try:
            start_1d = now_ms - (18 * 86400 * 1000)
            r_1d = requests.post(
                HYPERLIQUID_URL,
                json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1d", "startTime": start_1d, "endTime": now_ms}},
                timeout=3.0
            )
            if r_1d.status_code == 200 and len(r_1d.json()) >= 6:
                d_bars = r_1d.json()[:-1]
                trs = []
                for i in range(1, len(d_bars)):
                    h = float(d_bars[i]["h"])
                    l = float(d_bars[i]["l"])
                    pc = float(d_bars[i-1]["c"])
                    tr = max(h - l, abs(h - pc), abs(l - pc))
                    trs.append(tr)
                if len(trs) >= 5:
                    macro_range = sum(trs[-5:]) / 5.0
                    box_size = max(50.0, round(macro_range / 10.0, 1))
        except Exception:
            pass

        # 2. Fetch 1m Candles (Last 720 mins = 12 Hours) for rock-solid Renko convergence
        start_1m = now_ms - (720 * 60 * 1000)
        r_1m = requests.post(
            HYPERLIQUID_URL,
            json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_1m, "endTime": now_ms}},
            timeout=3.5
        )
        if r_1m.status_code != 200 or len(r_1m.json()) < 40:
            return None

        closed_bars = r_1m.json()[:-1] # Confirmed closed candles only
        closes = [float(b["c"]) for b in closed_bars]
        highs = [float(b["h"]) for b in closed_bars]
        lows = [float(b["l"]) for b in closed_bars]
        opens = [float(b["o"]) for b in closed_bars]
        vols = [float(b["v"]) for b in closed_bars]
        bar_times = [int(b["t"]) for b in closed_bars]

        recent_30 = closed_bars[-30:]
        vwap_num = sum(((float(b["h"]) + float(b["l"]) + float(b["c"])) / 3.0) * float(b["v"]) for b in recent_30)
        vwap_den = max(0.1, sum(float(b["v"]) for b in recent_30))
        vwap_val = vwap_num / vwap_den

        # 3. Gaussian Filter (gaussPeriod = 20)
        gauss_len = 20.0
        w = (2.0 * math.pi) / gauss_len
        b_coef = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
        a_coef = -b_coef + math.sqrt(b_coef * b_coef + 2.0 * b_coef)

        g_vals = []
        eval_prices = []
        for i, c_val in enumerate(closes):
            if i == 0:
                g = c_val
            elif i == 1:
                g = (a_coef ** 2) * c_val + 2.0 * (1.0 - a_coef) * g_vals[i-1] - ((1.0 - a_coef) ** 2) * c_val
            else:
                g = (a_coef ** 2) * c_val + 2.0 * (1.0 - a_coef) * g_vals[i-1] - ((1.0 - a_coef) ** 2) * g_vals[i-2]
            g_vals.append(g)
            eval_prices.append(c_val * 0.70 + g * 0.30)

        # 4. 3-Bar Orderflow Dominance
        bar_buy_v = []
        bar_sell_v = []
        for i in range(len(closes)):
            rng = max(highs[i] - lows[i], 0.1)
            u_wick = highs[i] - max(opens[i], closes[i])
            l_wick = min(opens[i], closes[i]) - lows[i]
            body = abs(closes[i] - opens[i])
            bull_score = (closes[i] - lows[i]) + (l_wick * 1.1) + (body * 0.85 if closes[i] > opens[i] else 0.0)
            bear_score = (highs[i] - closes[i]) + (u_wick * 1.1) + (body * 0.85 if closes[i] < opens[i] else 0.0)
            bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8)
            bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
            tot_pow = bull_pow + bear_pow
            bar_buy_v.append(vols[i] * (bull_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5)
            bar_sell_v.append(vols[i] * (bear_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5)

        roll_buy = (bar_buy_v[-1] * 1.4) + bar_buy_v[-2] + bar_buy_v[-3]
        roll_sell = (bar_sell_v[-1] * 1.4) + bar_sell_v[-2] + bar_sell_v[-3]
        buy_dom_pct = (roll_buy / (roll_buy + roll_sell) * 100.0) if (roll_buy + roll_sell) > 0 else 50.0

        # 5. FIXED-GRID RENKO BRICK & SPECIAL SUPERTREND ENGINE
        # Snap initial brick to a deterministic multiple of box_size so rolling window never shifts brick boundaries!
        st_factor = 3.0
        band_distance = box_size * st_factor

        grid_base = math.floor(closes[0] / box_size) * box_size
        brick_bot = grid_base
        brick_top = grid_base + box_size
        brick_dir = 1
        brick_streak = 1

        support_band = None
        resistance_band = None
        st_trend = 1
        st_line = brick_top - band_distance

        st_flip_buy = False
        st_flip_sell = False
        last_flip_bar_ts = bar_times[0]

        for i in range(1, len(closes)):
            ep = eval_prices[i]
            if ep >= brick_top + box_size:
                steps = int(math.floor((ep - brick_top) / box_size))
                brick_top = brick_top + (steps * box_size)
                brick_bot = brick_top - box_size
                if brick_dir == -1:
                    brick_streak = steps
                else:
                    brick_streak += steps
                brick_dir = 1
            elif ep <= brick_bot - box_size:
                steps = int(math.floor((brick_bot - ep) / box_size))
                brick_bot = brick_bot - (steps * box_size)
                brick_top = brick_bot + box_size
                if brick_dir == 1:
                    brick_streak = steps
                else:
                    brick_streak += steps
                brick_dir = -1

            r_close = brick_top if brick_dir == 1 else brick_bot
            raw_support = r_close - band_distance
            raw_resistance = r_close + band_distance
            prev_trend = st_trend

            if support_band is None:
                support_band = raw_support
            elif prev_trend == 1:
                support_band = raw_support if (brick_dir == 1 and raw_support > support_band) else support_band
            else:
                support_band = raw_support

            if resistance_band is None:
                resistance_band = raw_resistance
            elif prev_trend == -1:
                resistance_band = raw_resistance if (brick_dir == -1 and raw_resistance < resistance_band) else resistance_band
            else:
                resistance_band = raw_resistance

            bar_flipped_buy = False
            bar_flipped_sell = False

            if prev_trend == -1 and brick_dir == 1 and r_close > resistance_band:
                st_trend = 1
                support_band = r_close - band_distance
                brick_streak = 1
                bar_flipped_buy = True
                last_flip_bar_ts = bar_times[i]
            elif prev_trend == 1 and brick_dir == -1 and r_close < support_band:
                st_trend = -1
                resistance_band = r_close + band_distance
                brick_streak = 1
                bar_flipped_sell = True
                last_flip_bar_ts = bar_times[i]
            else:
                st_trend = prev_trend

            st_line = support_band if st_trend == 1 else resistance_band

            if i == len(closes) - 1:
                st_flip_buy = bar_flipped_buy
                st_flip_sell = bar_flipped_sell

        r_close_now = brick_top if brick_dir == 1 else brick_bot

        return {
            "vwap": vwap_val,
            "macro_range": macro_range,
            "box_size": box_size,
            "brick_top": round(brick_top, 1),
            "brick_bot": round(brick_bot, 1),
            "brick_dir": brick_dir,
            "brick_streak": brick_streak,
            "r_close": round(r_close_now, 1),
            "st_trend": st_trend,
            "st_line": round(st_line, 1),
            "st_flip_buy": st_flip_buy,
            "st_flip_sell": st_flip_sell,
            "last_flip_bar_ts": last_flip_bar_ts,
            "buy_dom_pct": buy_dom_pct,
            "last_confirmed_close": closes[-1]
        }
    except Exception:
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
            "pattern_en": "No major liquidity voids (> $4.0 spread) in the last 30 minutes; orderbook liquidity is stable.",
            "prompt_table": "No major liquidity voids recorded."
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
        pattern_en = f"BEARISH ICEBERG ABSORPTION TRAP: {bull_cnt}/{cnt} voids had aggressive buying (Avg Tape {avg_tape:.0f}% Buy), yet net price fell {net_px_progress:+.1f} pts."
    elif bear_cnt >= bull_cnt + 2 and net_px_progress > 15.0:
        pattern = f"🧊 बुलिश आइसबर्ग अब्जॉर्प्शन: पिछले {cnt} में से {bear_cnt} स्प्रेड बियरिश थे, फिर भी प्राइस {net_px_progress:+.0f}$ चढ़ा—नीचे व्हेल सारा बिकवाली का माल सोख रही है!"
        pattern_en = f"BULLISH ICEBERG ABSORPTION: {bear_cnt}/{cnt} voids had heavy selling, yet net price rose {net_px_progress:+.1f} pts."
    elif avg_l2_shift <= -4.5:
        pattern = f"⚠️ बिड-पुलिंग पैनिक: पिछले {cnt} स्प्रेड्स में औसतन L2 Bids {avg_l2_shift:+.1f}% गिरी हैं—स्प्रेड फटने पर बायर्स डरकर सपोर्ट हटा रहे हैं।"
        pattern_en = f"BID-PULLING PANIC: Across last {cnt} voids, L2 Bids dropped by an average of {avg_l2_shift:+.1f}%."
    elif avg_l2_shift >= 4.5:
        pattern = f"🚀 आक्रामक बाइंग स्वीप: पिछले {cnt} स्प्रेड्स में L2 Bids औसतन {avg_l2_shift:+.1f}% बढ़ी हैं और बायर्स ऊपर के आस्क तोड़ रहे हैं।"
        pattern_en = f"AGGRESSIVE BUYING SWEEP: Across last {cnt} voids, L2 Bids surged by an average of {avg_l2_shift:+.1f}%."
    else:
        pattern = f"📊 पिछले {cnt} स्प्रेड्स का निचोड़: {bull_cnt} बुलिश बनाम {bear_cnt} बियरिश ({pull_cnt} ऑर्डर-पुल) | औसत L2 बदलाव: {avg_l2_shift:+.1f}% | नेट प्राइस असर: {net_px_progress:+.1f}$।"
        pattern_en = f"VOID CLUSTER SUMMARY ({cnt} events): {bull_cnt} Bullish vs {bear_cnt} Bearish | Avg L2 Shift: {avg_l2_shift:+.1f}% | Net Price Progress: {net_px_progress:+.1f} pts."

    lines = []
    for idx, v in enumerate(recent, 1):
        lines.append(
            f"#{idx} [{v['time']}] Spread:${v['spread']:.1f} | Px:${v['px']:,.0f} (Jump:{v['px_jump']:+.1f}$) | "
            f"L2 Bid:{v['l2_before']:.0f}%->{v['l2_after']:.0f}% ({v['l2_shift']:+.0f}%) | Tape:{v['tape_pct']:.0f}% Buy"
        )

    return {
        "count": cnt, "bull_cnt": bull_cnt, "bear_cnt": bear_cnt, "pull_cnt": pull_cnt,
        "avg_l2_shift": avg_l2_shift, "avg_tape": avg_tape, "net_px_progress": net_px_progress,
        "pattern_summary": pattern,
        "pattern_en": pattern_en,
        "prompt_table": "\n".join(lines)
    }

# ============================================================================
# RENKO ENTRY OPENER & STRICT NON-OVERLAPPING RE-ENTRY ARMER
# ============================================================================
def get_initial_sl_near_250pts(entry_px: float, direction: str) -> float:
    return round(entry_px - 250.0, 1) if direction == "BUY" else round(entry_px + 250.0, 1)

def open_renko_trade_now(eng, direction: str, entry_px: float, ist_str: str, entry_source_label: str):
    init_sl = get_initial_sl_near_250pts(entry_px, direction)
    init_sl_pts = round((init_sl - entry_px) if direction == "BUY" else (entry_px - init_sl), 1)
    rk = eng.get("renko", {})
    st_line_val = rk.get("st_line", entry_px)
    box_sz = rk.get("box_size", 150.0)

    new_trade = {
        "open_ts": time.time(),
        "open_time": ist_str,
        "close_time": "",
        "type": direction,
        "entry": entry_px,
        "prob": 90,
        "initial_sl": init_sl,
        "sl_px": init_sl,
        "sl_pts": init_sl_pts,
        "tp_px": round(entry_px + 650.0 if direction == "BUY" else entry_px - 650.0, 1),
        "trail_count": 0,
        "last_trail_msg": f"🛡️ शुरुआती ~250pt SL लॉक: ${init_sl:,.1f} ({init_sl_pts:+.1f} Pts) | +220p प्रॉफिट से पहले SL नहीं छेड़ा जाएगा",
        "trail_log": [],
        "live_pts": 0.0,
        "peak_pts": 0.0,
        "status": "ACTIVE (RENKO + HARD-LOCK AI)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | ST Line: ${st_line_val:,.0f})",
        "exit_reason": "अभी ट्रेड चालू है — +220p प्रॉफिट गेट और 160p गैप ट्रेलिंग नियम सक्रिय"
    }
    eng["active_trade"] = new_trade
    eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"{'🟢' if direction=='BUY' else '🔴'} {entry_source_label}: {direction} @ ${entry_px:,.1f}"
        eng["report"]["lock_cls"] = "lock-buy" if direction == "BUY" else "lock-sell"
        eng["report"]["lock_sub"] = f"शुरुआती SL: ${init_sl:,.1f} ({init_sl_pts:+.1f} Pts) | +220p मुनाफे के बाद ही 160p गैप के साथ ट्रेलिंग शुरू होगी।"

def close_active_trade_immediately(eng, active_tr, exit_px, ist_str, reason_title, detailed_reason):
    """
    RULE 4 (NON-OVERLAPPING RE-ENTRY):
    Arms Pullback Re-Entry ONLY if:
    1. Trade exited with BIG profit (move >= +200.0 pts)
    2. At the time of exit, price was genuinely FAR from Renko ST Line (dist_to_st >= max(300.0, box_size * 2.0))
    3. Re-entry will only trigger later when price pulls back into the tight 15p to 85p retest zone near stLine!
    """
    move = (exit_px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - exit_px)
    active_tr["live_pts"] = move
    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)
    active_tr["close_time"] = ist_str
    active_tr["status"] = f"{reason_title} @ ${exit_px:,.1f} ({ist_str})"
    active_tr["exit_reason"] = detailed_reason

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

    rk = eng.get("renko", {})
    st_trend_now = rk.get("st_trend", 0)
    st_line_now = rk.get("st_line", 0.0)
    box_sz = rk.get("box_size", 150.0)
    tr_dir_int = 1 if active_tr["type"] == "BUY" else -1
    dist_to_st = abs(exit_px - st_line_now) if st_line_now > 0 else 0.0
    min_far_dist = max(300.0, box_sz * 2.0)

    reentry_note = ""
    if move >= 200.0 and st_trend_now == tr_dir_int and dist_to_st >= min_far_dist and "ST FLIP" not in reason_title:
        eng["reentry_watch"] = {
            "armed": True,
            "dir": tr_dir_int,
            "dir_str": active_tr["type"],
            "exit_px": exit_px,
            "exit_profit": move,
            "armed_ts": time.time(),
            "reason": (
                f"पिछला {active_tr['type']} ट्रेड +{move:.1f}p के बड़े प्रॉफिट में कटा जब ST Line (${st_line_now:,.0f}) {dist_to_st:.0f}p दूर थी। "
                f"अब जब प्राइस वापस घूमकर ST Line के करीब (15p–85p ज़ोन में) आएगा, तभी री-एंट्री होगी!"
            )
        }
        reentry_note = f" | 🎯 री-एंट्री आर्म हुई (प्राइस के ST Line ${st_line_now:,.0f} के 15-85p पास आने पर ही री-एंट्री होगी)"
    else:
        eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"🚨 {reason_title} — ट्रेड EXIT किया गया ({move:+.1f} Pts)"
        eng["report"]["lock_cls"] = "lock-wait"
        eng["report"]["lock_sub"] = detailed_reason + reentry_note

    if eng.get("ai_json_view"):
        eng["ai_json_view"]["badge_1"] = f"Closed: {reason_title}"
        eng["ai_json_view"]["badge_3"] = f"Exit Price: ${exit_px:,.1f}"
        eng["ai_json_view"]["badge_4"] = f"PnL: {move:+.1f} Pts"
        eng["ai_json_view"]["headline"] = detailed_reason + reentry_note
        eng["ai_json_view"]["trail_box_html"] = (
            f"<div class='trail-banner' style='border-left-color:#ef4444; background:#3b0a0a;'>"
            f"🚨 <b>ट्रेड एग्जिट ({ist_str}):</b> {detailed_reason}{reentry_note}</div>"
        )

# ============================================================================
# V20.0 HARD-LOCKED AI POST-ENTRY MANAGER
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
    px = ctx["px"]
    vc = ctx["void_cluster"]
    rk = ctx["renko"]
    st_line = rk["st_line"]
    box_sz = rk["box_size"]

    if active_trade is None:
        st_dir_str = "BUY 🟢" if rk["st_trend"] == 1 else "SELL 🔴"
        return {
            "headline": f"एंट्री केवल पक्के AI-Renko फ्लिप या ST Line (${st_line:,.0f}) रीटेस्ट पर होगी (वर्तमान रैंकों ट्रेंड: {st_dir_str})।",
            "macro_vs_micro": f"30m Tape: {m30['tape_buy']:.0f}% Buy | 5m Tape: {m5['tape_buy']:.0f}% Buy | Renko Brick: ${box_sz:.0f} (rClose: ${rk['r_close']:,.0f})।",
            "void_forensics": vc["pattern_summary"]
        }

    t_type = active_trade["type"]
    entry_px = active_trade["entry"]
    live_pts = active_trade["live_pts"]
    peak_pts = active_trade["peak_pts"]
    curr_sl = active_trade["sl_px"]
    safe_gap = max(160.0, box_sz * 1.15)

    if t_type == "BUY":
        if live_pts >= 320.0 and m5["tape_buy"] <= 40.0 and m30["tape_buy"] <= 46.5:
            return {
                "action": "EXIT",
                "confidence": 90,
                "trailing_sl": curr_sl,
                "sl_trail_reason": "+320p से बड़ा मुनाफा बनने के बाद ऊपर मोमेंटम थमने से प्रॉफिट बुक किया गया।",
                "headline": f"🚨 BIG PROFIT EXIT LONG @ ${px:,.0f} (+{live_pts:.1f}p) — बड़े टारगेट ज़ोन में रिवर्सल दिखने पर प्रॉफिट लॉक!",
                "macro_vs_micro": f"5m बाइंग गिरकर {m5['tape_buy']:.0f}% रह गई है जबकि ST Line ${st_line:,.0f} पर काफी नीचे है।",
                "void_forensics": vc["pattern_summary"]
            }

        new_sl = curr_sl
        reason_txt = f"हार्ड-लॉक नियम: +220p मुनाफे से पहले शुरुआती ~250p SL (${curr_sl:,.1f}) को बिल्कुल नहीं छेड़ा जाएगा।"
        if peak_pts >= 220.0:
            cand_sl = max(entry_px + 65.0, min(px - safe_gap, max(st_line - 15.0, rk["r_close"] - box_sz)))
            if cand_sl >= curr_sl + 25.0:
                new_sl = round(cand_sl, 1)
                reason_txt = f"Peak +{peak_pts:.0f}p पार होने पर {safe_gap:.0f}p का सुरक्षित गैप रखते हुए SL को ${new_sl:,.1f} पर ट्रेल किया गया।"

        return {
            "action": "HOLD",
            "confidence": 86,
            "trailing_sl": new_sl,
            "sl_trail_reason": reason_txt,
            "headline": f"✅ HOLD RENKO LONG ({live_pts:+.1f}p) — बड़े प्रॉफिट के लिए ट्रेड होल्ड रखें (SL: ${new_sl:,.1f})।",
            "macro_vs_micro": f"Renko ST Line (${st_line:,.0f}) बुलिश है और 5m Tape ({m5['tape_buy']:.0f}% B) सपोर्ट कर रहा है।",
            "void_forensics": vc["pattern_summary"]
        }
    else:
        if live_pts >= 320.0 and m5["tape_buy"] >= 60.0 and m30["tape_buy"] >= 53.5:
            return {
                "action": "EXIT",
                "confidence": 90,
                "trailing_sl": curr_sl,
                "sl_trail_reason": "+320p से बड़ा मुनाफा बनने के बाद नीचे बाइंग आने से प्रॉफिट बुक किया गया।",
                "headline": f"🚨 BIG PROFIT EXIT SHORT @ ${px:,.0f} (+{live_pts:.1f}p) — बड़े टारगेट पर प्रॉफिट बुक!",
                "macro_vs_micro": f"5m बाइंग उछलकर {m5['tape_buy']:.0f}% हो गई है जबकि ST Line ${st_line:,.0f} पर ऊपर है।",
                "void_forensics": vc["pattern_summary"]
            }

        new_sl = curr_sl
        reason_txt = f"हार्ड-लॉक नियम: +220p मुनाफे से पहले शुरुआती ~250p SL (${curr_sl:,.1f}) को बिल्कुल नहीं छेड़ा जाएगा।"
        if peak_pts >= 220.0:
            cand_sl = min(entry_px - 65.0, max(px + safe_gap, min(st_line + 15.0, rk["r_close"] + box_sz)))
            if cand_sl <= curr_sl - 25.0:
                new_sl = round(cand_sl, 1)
                reason_txt = f"Peak +{peak_pts:.0f}p पार होने पर {safe_gap:.0f}p का सुरक्षित गैप रखते हुए SL को ${new_sl:,.1f} पर ट्रेल किया गया।"

        return {
            "action": "HOLD",
            "confidence": 86,
            "trailing_sl": new_sl,
            "sl_trail_reason": reason_txt,
            "headline": f"✅ HOLD RENKO SHORT ({live_pts:+.1f}p) — बड़े प्रॉफिट के लिए शॉर्ट होल्ड रखें (SL: ${new_sl:,.1f})।",
            "macro_vs_micro": f"Renko ST Line (${st_line:,.0f}) बियरिश है और 5m Sell Tape ({100-m5['tape_buy']:.0f}%) पक्ष में है।",
            "void_forensics": vc["pattern_summary"]
        }

def call_gemini_json_engine(api_key, ctx, active_trade, selected_model, available_models):
    if active_trade is None:
        return dynamic_microstructure_backup_brain(ctx, None), "🟢 Fixed-Grid Renko Watcher"

    m30 = ctx["m30"]
    m5 = ctx["m5"]
    m1 = ctx["m1"]
    px = ctx["px"]
    vwap = ctx["vwap"]
    vc = ctx["void_cluster"]
    rk = ctx["renko"]

    t_type = active_trade["type"]
    t_entry = active_trade["entry"]
    live_pts = active_trade["live_pts"]
    peak_pts = active_trade["peak_pts"]
    init_sl = active_trade["initial_sl"]
    curr_sl = active_trade["sl_px"]
    curr_sl_pts = (curr_sl - t_entry) if t_type == "BUY" else (t_entry - curr_sl)
    dur_min = (time.time() - active_trade["open_ts"]) / 60.0

    prompt = f"""
You are a disciplined Wall Street Institutional Swing Trade Manager managing an ACTIVE BTCUSDT trade opened by our Fixed-Grid 'Dr Devendra AI-Renko' indicator.
Your job is to let winners run into BIG SWING PROFITS (+300 to +800 points) and NEVER choke the trade on small profits.

ACTIVE RENKO TRADE STATUS:
- Trade Direction: {t_type} | Entry Price: ${t_entry:,.1f} | Current Live Price: ${px:,.1f}
- Live PnL: {live_pts:+.1f} Points | Peak Profit Achieved: +{peak_pts:.1f} Points
- Initial Stop-Loss (~250 pts): ${init_sl:,.1f} | Current Active Stop-Loss: ${curr_sl:,.1f} ({curr_sl_pts:+.1f} Points from entry) | Duration: {dur_min:.1f} mins

DR DEVENDRA AI-RENKO & ORDERBOOK STRUCTURE:
- Dynamic Renko Box Size (Daily ATR-5 / 10): ${rk['box_size']:.1f} pts
- Current Renko Brick Close (`rClose`): ${rk['r_close']:,.1f} | Brick Direction: {'BULLISH (+1)' if rk['brick_dir']==1 else 'BEARISH (-1)'} | Brick Streak: #{rk['brick_streak']}
- Special Renko Supertrend Line (`stLine`): ${rk['st_line']:,.1f} (Distance from live price: {abs(px - rk['st_line']):.1f} pts) | 3-Bar Orderflow Dominance: {rk['buy_dom_pct']:.1f}% Buy
- Major L2 Bid Wall: ${ctx['bid_wall_px']:,.1f} ({ctx['bid_wall_sz']:.2f} BTC) | Major L2 Ask Wall: ${ctx['ask_wall_px']:,.1f} ({ctx['ask_wall_sz']:.2f} BTC) | VWAP: ${vwap:,.1f}
- 30-Minute Macro Flow: Price Change {m30['px_chg']:+.1f} pts | 30m Taker Tape: {m30['tape_buy']:.1f}% Buy | 30m L2 Bids: {m30['l2_buy']:.1f}%
- 5-Minute Micro Flow: Price Change {m5['px_chg']:+.1f} pts | 5m Taker Tape: {m5['tape_buy']:.1f}% Buy | 5m L2 Bids: {m5['l2_buy']:.1f}%
- Last {vc['count']} Liquidity Voids Cluster Pattern: {vc['pattern_en']}
{vc['prompt_table']}

MANDATORY HARD-LOCKED RULES (DO NOT VIOLATE):
1. NO EARLY TRAILING BELOW +220 POINTS PEAK PROFIT:
   - If `Peak Profit Achieved` (+{peak_pts:.1f} pts) is less than +220 points, you MUST NOT trail the Stop-Loss! Return `trailing_sl` as `{curr_sl:.1f}` so the initial ~250-point SL gives full breathing room.
2. SAFE GAP TRAILING ONCE PROFIT >= +220 POINTS:
   - Once Peak Profit is >= +220 points, trail `trailing_sl` progressively behind `stLine` (${rk['st_line']:,.1f}), Renko bricks (`rClose`), or L2 walls, ALWAYS keeping a wide gap of at least 160 to 220 points from current live price `${px:,.1f}`.
   - Any trailed SL in profit must lock at least +60 points above/below entry (never lock tiny +10 or +25 point profits).
3. NO PREMATURE "EXIT" COMMANDS:
   - You are FORBIDDEN from commanding `"action": "EXIT"` when `Live PnL` ({live_pts:+.1f} pts) is below +300 points! Below +300 points, always output `"action": "HOLD"` and let the Renko Supertrend and ~250p SL manage risk.
   - Only command `"action": "EXIT"` if `Live PnL` is >= +300 points AND price is far from `stLine` with heavy opposing iceberg absorption in the 10-void cluster.
4. OUTPUT FORMAT: Return ONLY valid JSON matching the exact keys below. Write all 4 text fields in sharp, clear Hindi:
{{
  "action": "HOLD" or "EXIT",
  "confidence": integer (0 to 100),
  "trailing_sl": float (return {curr_sl:.1f} if Peak Profit < 220 pts, or new wide-gap trailed SL price),
  "sl_trail_reason": "Sharp 1-line explanation in Hindi of why SL is held at ~250p breathing room or trailed with a 160p+ gap",
  "headline": "Sharp 1-line HOLD or EXIT command in Hindi",
  "macro_vs_micro": "Sharp 1-line analysis of Renko ST Line, 30m & 5m flow in Hindi",
  "void_forensics": "Sharp 1-line impact of the 10-void cluster on this trade in Hindi"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 420
        }
    }

    pro_first_priority = [
        "gemini-2.5-pro",
        "gemini-1.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite"
    ]
    sorted_avail = sorted(available_models or [], key=score_model_priority)
    combined_auto = []
    for m in sorted_avail + pro_first_priority:
        if m not in combined_auto:
            combined_auto.append(m)
    combined_auto.sort(key=score_model_priority)

    if selected_model and selected_model != AUTO_MODEL_LABEL:
        models_queue = [selected_model] + [m for m in combined_auto if m != selected_model]
    else:
        models_queue = combined_auto

    for idx, mod in enumerate(models_queue):
        try:
            req_timeout = 14.0 if "pro" in mod else 8.5
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=req_timeout)
            if res.status_code == 200:
                raw_txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                parsed = parse_ai_json_safely(raw_txt)
                if parsed:
                    if selected_model == AUTO_MODEL_LABEL:
                        return parsed, f"🟢 Auto Pro-Priority ({mod})"
                    elif idx == 0:
                        return parsed, f"🟢 Selected AI ({mod})"
                    else:
                        return parsed, f"🟡 Fallback ({mod}) [{selected_model} Busy]"
        except Exception:
            continue

    return dynamic_microstructure_backup_brain(ctx, active_trade), "⚡ Quant Backup Brain"

# ============================================================================
# AI TRADE MANAGEMENT CYCLE (WITH PYTHON HARD-CODE LOCKS)
# ============================================================================
def execute_ai_cycle_thread(eng, now_ts, ist_str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        vault = eng["vault"]
        if len(vault) < 3:
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
        rk = eng.get("renko", {})

        ctx = {
            "time": ist_str, "px": px,
            "best_bid": eng.get("best_bid", px), "best_ask": eng.get("best_ask", px),
            "spread": eng.get("spread", 1.0),
            "bid_wall_px": eng.get("bid_wall_px", px - 25.0), "bid_wall_sz": eng.get("bid_wall_sz", 1.0),
            "ask_wall_px": eng.get("ask_wall_px", px + 25.0), "ask_wall_sz": eng.get("ask_wall_sz", 1.0),
            "vwap": eng["vwap"] if eng["vwap"] > 0 else px,
            "span_min": span_min, "m30": m30, "m5": m5, "m1": m1,
            "void_cluster": void_cluster, "recent_voids": voids_30m[:10],
            "renko": rk
        }

        api_key = eng.get("api_key", "").strip()
        selected_mod = eng.get("selected_model", AUTO_MODEL_LABEL)
        avail_mods = eng.get("available_models", [])
        active_tr_snapshot = eng.get("active_trade")
        snapshot_trade_id = active_tr_snapshot["open_ts"] if active_tr_snapshot else None

        if api_key and active_tr_snapshot is not None:
            ai_json, status_str = call_gemini_json_engine(api_key, ctx, active_tr_snapshot, selected_mod, avail_mods)
        else:
            ai_json, status_str = dynamic_microstructure_backup_brain(ctx, active_tr_snapshot), "🟢 Fixed-Grid Renko + Hard-Lock AI"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()

        current_live_tr = eng.get("active_trade")
        if snapshot_trade_id is not None and (current_live_tr is None or current_live_tr["open_ts"] != snapshot_trade_id):
            return

        live_px_now = eng["px"]
        ist_now_str = get_ist_time_str()

        # --------------------------------------------------------------------
        # CASE 1: NO ACTIVE TRADE -> DISPLAY RENKO ENTRY / RE-ENTRY WATCH STATUS
        # --------------------------------------------------------------------
        if current_live_tr is None:
            st_dir_str = "BUY 🟢" if rk.get("st_trend", 1) == 1 else "SELL 🔴"
            st_line_px = rk.get("st_line", live_px_now)
            dist_st = abs(live_px_now - st_line_px)
            rw = eng.get("reentry_watch", {"armed": False})

            if rw.get("armed"):
                lock_title = f"🎯 रैंकों री-एंट्री वॉचर ON ({rw['dir_str']}) — ST Line (${st_line_px:,.0f}) के 15-85p पास आने का इंतज़ार"
                lock_cls = "lock-wait"
                lock_sub = f"{rw['reason']} | वर्तमान दूरी: {dist_st:.0f} Pts"
            else:
                lock_title = f"⚪ रैंकों डायरेक्ट सिग्नल की प्रतीक्षा (वर्तमान रैंकों सुपरट्रेंड: {st_dir_str} | ST Line: ${st_line_px:,.0f})"
                lock_cls = "lock-wait"
                lock_sub = "नया ट्रेड तभी खुलेगा जब रैंकों सुपरट्रेंड फ्लिप (BUY ▲ / SELL ▼) होगा या आप ऊपर मैनुअल सिंक बटन दबाएंगे।"

            eng["ai_json_view"] = {
                "mode": "RENKO_WATCH",
                "badge_1": f"Renko Trend: {st_dir_str}",
                "badge_2": f"ST Line: ${st_line_px:,.1f}",
                "badge_3": f"Brick Size: ${rk.get('box_size', 150.0):.1f}",
                "badge_4": f"Trail Gate: +220p",
                "headline": ai_json.get("headline", ""),
                "macro_vs_micro": ai_json.get("macro_vs_micro", ""),
                "void_forensics": ai_json.get("void_forensics", ""),
                "trail_box_html": ""
            }
            ctx["lock_title"] = lock_title
            ctx["lock_cls"] = lock_cls
            ctx["lock_sub"] = lock_sub
            eng["report"] = ctx

        # --------------------------------------------------------------------
        # CASE 2: ACTIVE RENKO TRADE -> ENFORCE HARD-CODED PYTHON GATES
        # --------------------------------------------------------------------
        else:
            raw_act = str(ai_json.get("action", "HOLD")).upper()
            conf = int(ai_json.get("confidence", 85))
            raw_ai_sl = float(ai_json.get("trailing_sl", current_live_tr["sl_px"]))
            trail_reason = str(ai_json.get("sl_trail_reason", "रैंकों सुपरट्रेंड और ऑर्डरबुक के अनुसार SL की समीक्षा की गई।")).strip()

            if 0 < abs(raw_ai_sl) < 5000:
                ai_trail_sl = (current_live_tr["entry"] + raw_ai_sl) if current_live_tr["type"] == "BUY" else (current_live_tr["entry"] - raw_ai_sl)
            else:
                ai_trail_sl = raw_ai_sl

            live_pts_now = current_live_tr["live_pts"]
            peak_pts_now = current_live_tr["peak_pts"]

            # ================================================================
            # HARD RULE 3: BLOCK PREMATURE AI "EXIT" BELOW +300 PTS PROFIT
            # ================================================================
            if raw_act == "EXIT":
                if live_pts_now >= 300.0:
                    close_active_trade_immediately(
                        eng, current_live_tr, live_px_now, ist_now_str,
                        "AI BIG PROFIT EXIT", f"🤖 +{live_pts_now:.1f}p के बड़े प्रॉफिट पर AI ने एग्जिट किया: {ai_json.get('headline', trail_reason)}"
                    )
                    return
                else:
                    # Override premature AI exit!
                    act = "HOLD"
                    trail_reason = f"🛡️ हार्ड-लॉक सुरक्षा: अभी प्रॉफिट (+{live_pts_now:.0f}p) +300p से कम है, इसलिए AI को समय से पहले ट्रेड काटने से रोका गया।"
            else:
                act = "HOLD"

            # ================================================================
            # HARD RULE 2: +220 PTS MINIMUM PROFIT GATE & 160 PTS MINIMUM GAP
            # ================================================================
            MIN_PEAK_TO_UNLOCK_TRAIL = 220.0
            MIN_GAP_FROM_LIVE = 160.0
            MIN_LOCKED_PROFIT_FLOOR = 60.0
            MIN_STEP_IMPROVEMENT = 25.0

            old_sl = current_live_tr["sl_px"]
            sl_trailed_now = False
            gate_note = ""

            if peak_pts_now < MIN_PEAK_TO_UNLOCK_TRAIL:
                # Strictly forbid any SL change before +220 pts peak profit!
                gate_note = f"🔒 हार्ड-लॉक: जब तक Peak Profit (+{peak_pts_now:.0f}p) +220p पार नहीं करता, शुरुआती ~250p SL (${old_sl:,.1f}) लॉक रहेगा।"
            else:
                if current_live_tr["type"] == "BUY" and ai_trail_sl > old_sl + MIN_STEP_IMPROVEMENT:
                    capped_sl = min(ai_trail_sl, live_px_now - MIN_GAP_FROM_LIVE)
                    min_profit_sl = current_live_tr["entry"] + MIN_LOCKED_PROFIT_FLOOR
                    # Only trail if it satisfies the 160p gap AND locks at least +60p (or improves already-positive SL by 25p+)
                    if capped_sl >= max(old_sl + MIN_STEP_IMPROVEMENT, min_profit_sl):
                        current_live_tr["sl_px"] = round(capped_sl, 1)
                        current_live_tr["sl_pts"] = round(current_live_tr["sl_px"] - current_live_tr["entry"], 1)
                        sl_trailed_now = True
                    else:
                        gate_note = f"🔒 160p गैप नियम: लाइव प्राइस से 160p का सुरक्षित गैप रखने के लिए अभी SL को ${old_sl:,.1f} पर ही रखा गया है।"

                elif current_live_tr["type"] == "SELL" and ai_trail_sl < old_sl - MIN_STEP_IMPROVEMENT:
                    capped_sl = max(ai_trail_sl, live_px_now + MIN_GAP_FROM_LIVE)
                    min_profit_sl = current_live_tr["entry"] - MIN_LOCKED_PROFIT_FLOOR
                    if capped_sl <= min(old_sl - MIN_STEP_IMPROVEMENT, min_profit_sl):
                        current_live_tr["sl_px"] = round(capped_sl, 1)
                        current_live_tr["sl_pts"] = round(current_live_tr["entry"] - current_live_tr["sl_px"], 1)
                        sl_trailed_now = True
                    else:
                        gate_note = f"🔒 160p गैप नियम: लाइव प्राइस से 160p का सुरक्षित गैप रखने के लिए अभी SL को ${old_sl:,.1f} पर ही रखा गया है।"

            curr_sl_pts = current_live_tr["sl_pts"]
            gap_now = abs(live_px_now - current_live_tr["sl_px"])
            shown_reason = gate_note if gate_note else trail_reason

            if sl_trailed_now:
                current_live_tr["trail_count"] += 1
                pts_shifted = abs(current_live_tr["sl_px"] - old_sl)
                lock_tag = f"+{curr_sl_pts:.1f} Pts पक्का प्रॉफिट लॉक"

                event_str = (
                    f"🔄 <b>हार्ड-लॉक गैप ट्रेल #{current_live_tr['trail_count']} ({ist_now_str}):</b> "
                    f"<span style='color:#f87171; text-decoration:line-through;'>${old_sl:,.1f}</span> ➔ "
                    f"<b style='color:#4ade80; font-size:14.5px;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> "
                    f"(<span style='color:#facc15;'>+{pts_shifted:.1f}p शिफ्ट | {lock_tag} | Gap: {gap_now:.0f}p</span>)<br>"
                    f"📌 <b>AI ट्रेलिंग कारण:</b> {trail_reason}"
                )
                current_live_tr["last_trail_msg"] = event_str
                current_live_tr["trail_log"].insert(
                    0, f"[{ist_now_str}] ${old_sl:,.1f} ➔ ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p | Gap {gap_now:.0f}p): {trail_reason}"
                )
                eng["sound_event"] = {"id": time.time(), "type": "TRAIL"}
            else:
                event_str = (
                    f"🛡️ <b>सक्रिय स्टॉप-लॉस स्थिति ({ist_now_str}):</b> एक्टिव SL: <b style='color:#facc15;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> | "
                    f"लाइव प्राइस से गैप: <b>{gap_now:.0f} Pts</b> | Peak: <b>+{peak_pts_now:.1f}p</b><br>"
                    f"📌 <b>नियम एवं AI नोट:</b> {shown_reason}"
                )

            trail_box_html = f"<div class='trail-banner'>{event_str}</div>"

            lock_title = f"{'🟢' if current_live_tr['type']=='BUY' else '🔴'} रैंकों {current_live_tr['type']} ट्रेड चालू है — हार्ड-लॉक AI मैनेजिंग (Live: {live_pts_now:+.1f} Pts)"
            lock_cls = "lock-buy" if current_live_tr["type"] == "BUY" else "lock-sell"
            lock_sub = (
                f"एंट्री: ${current_live_tr['entry']:,.1f} | "
                f"एक्टिव SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts | Gap: {gap_now:.0f}p) | "
                f"Renko ST Line: ${rk.get('st_line', 0.0):,.1f}"
            )

            eng["ai_json_view"] = {
                "mode": "TRADE_MANAGER",
                "badge_1": f"Command: {act} ({conf}%)",
                "badge_2": f"Entry: ${current_live_tr['entry']:,.1f}",
                "badge_3": f"Active SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p)",
                "badge_4": f"Gap: {gap_now:.0f}p | Peak: +{peak_pts_now:.0f}p",
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
# 24x7 1-SECOND BACKGROUND WORKER (FIXED-GRID RENKO, STRICT RE-ENTRY & 1s SL)
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

                # 1. 1-SECOND REAL-TIME HARD SL & TRAILED SL GUARD
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
                        sl_kind = "TRAILED SL HIT" if active_tr["trail_count"] > 0 else "INITIAL ~250p SL HIT"
                        detail_msg = (
                            f"🛡️ {sl_kind}: लाइव प्राइस ${px:,.1f} ({move:+.1f} Pts) ने आपके एक्टिव स्टॉप-लॉस "
                            f"${active_tr['sl_px']:,.1f} ({sl_pts_locked:+.1f} Pts) को छू लिया — 1 सेकंड में तुरंत एग्जिट!"
                        )
                        close_active_trade_immediately(eng, active_tr, px, ist_str, sl_kind, detail_msg)

                # 2. STRICT NON-OVERLAPPING RENKO ST LINE PULLBACK RE-ENTRY
                # Only triggers when price genuinely pulls back within 15p to 85p of stLine (at least 30s after exit)
                rk = eng.get("renko", {})
                rw = eng.get("reentry_watch", {"armed": False})
                if eng.get("active_trade") is None and rw.get("armed") and rk.get("st_line", 0.0) > 0:
                    st_trend_now = rk["st_trend"]
                    st_line_now = rk["st_line"]
                    elapsed_since_arm = now_ts - rw.get("armed_ts", 0.0)

                    if st_trend_now != rw["dir"]:
                        eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
                    elif elapsed_since_arm >= 30.0:
                        if rw["dir"] == 1 and (st_line_now + 15.0 <= px <= st_line_now + 85.0):
                            open_renko_trade_now(eng, "BUY", px, ist_str, "🔄 Renko ST Line Pullback Re-Entry ▲")
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()
                        elif rw["dir"] == -1 and (st_line_now - 85.0 <= px <= st_line_now - 15.0):
                            open_renko_trade_now(eng, "SELL", px, ist_str, "🔄 Renko ST Line Pullback Re-Entry ▼")
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

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

                # 3. UPDATE FIXED-GRID CONFIRMED-CLOSE AI-RENKO EVERY 12 SECONDS
                if now_ts - eng["last_kline_ts"] > 12:
                    rk_data = fetch_renko_supertrend_and_vwap()
                    if rk_data:
                        eng["vwap"] = rk_data["vwap"]
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data

                        if prev_rk_trend == 0:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                        else:
                            if rk_data["st_trend"] != prev_rk_trend and rk_data["last_flip_bar_ts"] != eng.get("last_handled_flip_ts"):
                                eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                                new_dir_str = "BUY" if rk_data["st_trend"] == 1 else "SELL"

                                curr_tr = eng.get("active_trade")
                                if curr_tr is not None and curr_tr["type"] != new_dir_str:
                                    close_active_trade_immediately(
                                        eng, curr_tr, px, ist_str,
                                        "RENKO ST FLIP EXIT",
                                        f"🔄 रैंकों सुपरट्रेंड पक्के क्लोज पर {new_dir_str} में फ्लिप होने से पिछला ट्रेड क्लोज किया गया।"
                                    )

                                if eng.get("active_trade") is None:
                                    open_renko_trade_now(
                                        eng, new_dir_str, px, ist_str,
                                        f"🔥 AI-Renko Direct Flip {new_dir_str} {'▲' if new_dir_str=='BUY' else '▼'}"
                                    )
                                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                    eng["last_kline_ts"] = now_ts

                # 4. RUN 3-MINUTE AI TRADE & TRAILING MANAGER CYCLE
                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and len(eng["vault"]) >= 8 and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v20_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "best_bid": 0.0, "best_ask": 0.0, "spread": 0.0,
        "bid_wall_px": 0.0, "bid_wall_sz": 0.0, "ask_wall_px": 0.0, "ask_wall_sz": 0.0,
        "last_update": "--:--:--",
        "vault": [], "voids": [], "signal_history": [],
        "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0,
        "last_handled_flip_ts": 0,
        "vwap": 0.0,
        "renko": {
            "box_size": 150.0, "macro_range": 1500.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "st_flip_buy": False, "st_flip_sell": False, "buy_dom_pct": 50.0
        },
        "reentry_watch": {"armed": False, "dir": 0, "dir_str": "", "reason": ""},
        "report": None,
        "available_models": [],
        "models_fetched": False,
        "selected_model": AUTO_MODEL_LABEL,
        "ai_json_view": {
            "mode": "INIT",
            "badge_1": "Renko: Fixed-Grid",
            "badge_2": "ST Line: --",
            "badge_3": "Initial SL: ~250p",
            "badge_4": "Trail Gate: +220p",
            "headline": "⏳ Fixed-Grid AI-Renko इंजन लाइव कैंडल्स स्कैन कर रहा है...",
            "macro_vs_micro": "डेटा बफर तैयार हो रहा है...",
            "void_forensics": "स्प्रेड क्लस्टर पर नज़र रखी जा रही है...",
            "trail_box_html": ""
        },
        "ai_status": "🤖 Fixed-Grid Renko + Hard-Lock AI",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v20_0()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if not eng.get("models_fetched"):
    eng["available_models"] = fetch_available_api_models(eng.get("api_key", ""))
    eng["models_fetched"] = True

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# TOP CONTROL BAR
# ============================================================================
c_mod, c_act1, c_act2, c_act3 = st.columns([0.26, 0.27, 0.25, 0.22])

with c_mod:
    dropdown_options = [AUTO_MODEL_LABEL] + eng.get("available_models", [])
    curr_sel = eng.get("selected_model", AUTO_MODEL_LABEL)
    sel_idx = dropdown_options.index(curr_sel) if curr_sel in dropdown_options else 0
    chosen_model = st.selectbox(
        "🧠 AI मॉडल चुनें:",
        options=dropdown_options,
        index=sel_idx,
        label_visibility="collapsed"
    )
    eng["selected_model"] = chosen_model

with c_act1:
    if st.button("🤖 अभी AI से SL ट्रेल / स्टेटस अपडेट कराएं"):
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()

with c_act2:
    if st.button("🔥 चालू रैंकों ट्रेंड में अभी एंट्री लें (~250p SL)"):
        if eng.get("active_trade") is None and eng["px"] > 0 and eng["renko"].get("st_trend", 0) != 0:
            cur_dir = "BUY" if eng["renko"]["st_trend"] == 1 else "SELL"
            open_renko_trade_now(eng, cur_dir, eng["px"], get_ist_time_str(), f"🔥 Manual Sync AI-Renko {cur_dir}")
            threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()

with c_act3:
    sound_enabled = st.checkbox("🔊 साउंड अलर्ट (ON/OFF)", value=True)

dashboard_slot = st.empty()
audio_slot = st.empty()

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
        mod_label_short = "Pro-Priority Auto" if eng["selected_model"] == AUTO_MODEL_LABEL else eng["selected_model"]
        rk = eng.get("renko", {})
        rw = eng.get("reentry_watch", {"armed": False})

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            is_act = "ACTIVE" in h["status"]
            sts_badge = "🟢 HARD-LOCK ACTIVE" if is_act else f"🏁 {h['status']}"
            sl_pts_val = h.get("sl_pts", 0.0)
            trail_info = (
                f"शुरुआती SL: ${h['initial_sl']:,.1f} ➔ एक्टिव SL: <b style='color:#facc15;'>${h['sl_px']:,.1f} ({sl_pts_val:+.1f}p)</b> (ट्रेल: {h['trail_count']}x)"
            )
            latest_trail_note = f"<br><span style='color:#fde047; font-size:11.8px;'>🔄 {h['trail_log'][0]}</span>" if h.get("trail_log") else ""

            hist_cards += f"""
            <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <b style='color:{h_col}; font-size:13.5px;'>{h["open_time"]} — {h["type"]} @ ${h["entry"]:,.1f}</b>
                    <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span><br>
                    <span style='color:#cbd5e1; font-size:12px;'>एंट्री स्रोत: {h["entry_reason"]}</span><br>
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
            hist_cards = "<div style='text-align:center; color:#64748b; padding-top:75px;'>अभी तक कोई रैंकों ट्रेड शुरू नहीं हुआ है। अगले पक्के रैंकों फ्लिप या मैनुअल सिंक बटन पर ट्रेड शुरू होगा।</div>"

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

        st_trend_col = "#4ade80" if rk.get("st_trend", 1) == 1 else "#f87171"
        st_trend_txt = "BUY 🟢 (Bullish)" if rk.get("st_trend", 1) == 1 else "SELL 🔴 (Bearish)"
        brick_dir_txt = f"🟢 Up (Streak #{rk.get('brick_streak', 1)})" if rk.get("brick_dir", 1) == 1 else f"🔴 Down (Streak #{rk.get('brick_streak', 1)})"
        st_dist_pts = abs(eng["px"] - rk.get("st_line", eng["px"]))
        reentry_status_txt = f"🎯 ARMED ({rw.get('dir_str')} @ 15-85p from ${rk.get('st_line', 0):,.0f})" if rw.get("armed") else "⚪ Standby (Requires +200p Exit & >300p Dist)"

        act_tr = eng.get("active_trade")
        if act_tr:
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} रैंकों {act_tr['type']} ट्रेड चालू है — +220p गेट एवं 160p गैप-ट्रेल सक्रिय"
            banner_sub = (
                f"एंट्री: ${act_tr['entry']:,.1f} | एक्टिव SL: ${act_tr['sl_px']:,.1f} ({act_tr['sl_pts']:+.1f} Pts) | "
                f"Peak: +{act_tr['peak_pts']:.1f}p | Renko ST Line: ${rk.get('st_line', 0.0):,.1f}"
            )
            right_stat_label = f"LIVE PNL (SL: {act_tr['sl_pts']:+.1f}p)"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            if rw.get("armed"):
                banner_title = f"🎯 रैंकों री-एंट्री वॉचर ON ({rw['dir_str']}) — ST Line (${rk.get('st_line', 0.0):,.0f}) के 15-85p पास आने की प्रतीक्षा"
                banner_sub = rw.get("reason", "")
            else:
                banner_title = f"⚪ रैंकों डायरेक्ट सिग्नल की प्रतीक्षा (चालू रैंकों सुपरट्रेंड: {st_trend_txt})"
                banner_sub = f"Renko ST Line: ${rk.get('st_line', 0.0):,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर) | नए फ्लिप या ऊपर मैनुअल सिंक बटन से एंट्री होगी।"
            right_stat_label = "AI CYCLE TIMER"
            right_stat_val = f"{next_sec}s"
            right_stat_col = "#38bdf8"

        aj = eng["ai_json_view"]
        m5_slice = compute_slice_metrics([d for d in eng["vault"] if (time.time() - d["ts"]) <= 300.0])
        c5_col = "#4ade80" if m5_slice["px_chg"] >= 0 else "#f87171"

        left_body = f"""
        <div class='lock-banner {banner_cls}'>
            <div>
                <div style='font-size:18px; font-weight:900;'>{banner_title}</div>
                <div style='font-size:12.5px; margin-top:3px; opacity:0.92;'>{banner_sub}</div>
            </div>
            <div style='text-align:right; min-width:145px;'>
                <div style='font-size:11px; text-transform:uppercase; opacity:0.85;'>{right_stat_label}</div>
                <div style='font-size:23px; font-weight:900; color:{right_stat_col};'>{right_stat_val}</div>
                <div style='font-size:11px; opacity:0.8;'>● {eng["last_update"]}</div>
            </div>
        </div>

        <div class='ai-sharp-box'>
            <div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3b0764; padding-bottom:6px; margin-bottom:8px;'>
                <span style='font-size:15px; font-weight:900; color:#c084fc;'>🧠 हार्ड-लॉक AI ट्रेलिंग मैनेजर (~250p SL | +220p Profit Gate | 160p Gap)</span>
                <span style='font-size:11.5px; color:#4ade80; font-weight:bold;'>{eng["ai_status"]}</span>
            </div>
            <div>
                <span class='json-pill'>{aj["badge_1"]}</span>
                <span class='json-pill'>{aj["badge_2"]}</span>
                <span class='json-pill'>{aj["badge_3"]}</span>
                <span class='json-pill'>{aj["badge_4"]}</span>
            </div>
            <div style='font-size:14px; line-height:1.65; color:#f8fafc; margin-top:10px;'>
                <div>🎯 <b>स्टेटस / AI आदेश:</b> {aj["headline"]}</div>
                <div style='margin-top:4px;'>⚡ <b>रैंकों एवं ऑर्डरफ्लो विश्लेषण:</b> {aj["macro_vs_micro"]}</div>
                <div style='margin-top:4px;'>🌪️ <b>10-स्प्रेड क्लस्टर निष्कर्ष:</b> {aj["void_forensics"]}</div>
            </div>
            {aj.get("trail_box_html", "")}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. Fixed-Grid AI-Renko इंजन (Non-Repainting)</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>स्पेशल रैंकों सुपरट्रेंड लाइन (stLine):</span><b><span style='color:{st_trend_col};'>${rk.get("st_line", 0.0):,.1f}</span> (दूरी: {st_dist_pts:.0f} Pts)</b></div>
                <div class='stat-row'><span>डायनामिक ब्रिक साइज (Daily ATR÷10):</span><b style='color:#facc15;'>${rk.get("box_size", 150.0):.1f} Pts (23H Range: ${rk.get("macro_range", 1500.0):,.0f})</b></div>
                <div class='stat-row'><span>रैंकों ब्रिक क्लोज (rClose) एवं दिशा:</span><b>${rk.get("r_close", 0.0):,.1f} ({brick_dir_txt})</b></div>
                <div class='stat-row' style='border:none;'><span>ST पुलबैक री-एंट्री वॉचर:</span><b style='color:#38bdf8;'>{reentry_status_txt}</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>⚡ 2. आखिरी 5m ऑर्डरफ्लो और L2 वॉल्स (AI Input)</span>
                    <span style='color:{c5_col};'>{m5_slice["px_chg"]:+.1f} Pts</span>
                </div>
                <div class='stat-row'><span>आखिरी 5m Taker Tape:</span><b><span style='color:#4ade80;'>{m5_slice["tape_buy"]:.0f}% Buy</span> / <span style='color:#f87171;'>{100-m5_slice["tape_buy"]:.0f}% Sell</span></b></div>
                <div class='stat-row'><span>रैंकों 3-Bar ऑर्डरफ्लो डोमिनेंस:</span><b><span style='color:#4ade80;'>{rk.get("buy_dom_pct", 50.0):.0f}% Buy</span> / <span style='color:#f87171;'>{100-rk.get("buy_dom_pct", 50.0):.0f}% Sell</span></b></div>
                <div class='stat-row'><span>L2 सबसे बड़ी Bid/Ask दीवार:</span><b><span style='color:#4ade80;'>${eng["bid_wall_px"]:,.0f}</span> / <span style='color:#f87171;'>${eng["ask_wall_px"]:,.0f}</span></b></div>
                <div class='stat-row' style='border:none;'><span>सेशन VWAP एवं 5m रेंज:</span><b>${eng["vwap"]:,.0f} (${m5_slice["low"]:,.0f}–${m5_slice["high"]:,.0f})</b></div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V20.0 (FIXED-GRID RENKO & HARD-LOCK AI ENGINE)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🗄️ मेमोरी: <b style='color:#facc15;'>{mem_min:.1f} / 30.0 Min</b> | अगली AI जांच: <b>{next_sec}s</b> | 🧠 AI: <b style='color:#c084fc;'>{mod_label_short}</b></div>
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
                            📜 रैंकों ट्रेड, नॉन-ओवरलैपिंग री-एंट्री एवं AI गैप-ट्रेलिंग हिस्ट्री
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
        dashboard_slot.warning("⏳ 24x7 V20.0 (Fixed-Grid Renko & Hard-Lock AI Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")

    time.sleep(1.5)

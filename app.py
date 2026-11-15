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
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V21.0 - 4-Stage Pro Dynamic Renko AI", layout="wide")

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
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 280px; overflow-y: auto; }
.stage-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 675px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
.ic-active-stage { background: #172554; border: 1px solid #38bdf8; border-left: 5px solid #facc15; }
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
# HYPERLIQUID LIVE PRICE & PURE DR DEVENDRA AI-RENKO ENGINE (NO 30m/5m NOISE)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_live_btc_price():
    """Lightweight 1-second BTC mid-price fetcher for instant SL & Peak Ratchet execution"""
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "allMids"}, timeout=1.8)
        if r.status_code == 200:
            mids = r.json()
            if isinstance(mids, dict) and "BTC" in mids:
                return float(mids["BTC"])
    except Exception as e:
        return str(e)
    return None

def fetch_renko_pro_structure(locked_box_size=None):
    """
    Pure 'Dr Devendra AI-Renko [Confirmed Close Algo PRO]' Engine:
    Calculates Stable Renko Bricks, Special Renko Supertrend (stLine),
    21-EMA Stretch (in Bricks), 14-RSI, 3-Bar Dominance, and Recent Brick History.
    """
    try:
        now_ms = int(time.time() * 1000)

        # 1. Stable Box Size (Initialized once from Daily ATR-5 / 10, then locked)
        box_size = locked_box_size if locked_box_size else 200.0
        macro_range = box_size * 10.0
        if not locked_box_size:
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
                        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
                    if len(trs) >= 5:
                        macro_range = sum(trs[-5:]) / 5.0
                        box_size = max(120.0, min(300.0, round(macro_range / 10.0, 1)))
            except Exception:
                pass

        # 2. Fetch 1m Confirmed Closed Candles (Last 720 mins)
        start_1m = now_ms - (720 * 60 * 1000)
        r_1m = requests.post(
            HYPERLIQUID_URL,
            json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_1m, "endTime": now_ms}},
            timeout=3.5
        )
        if r_1m.status_code != 200 or len(r_1m.json()) < 40:
            return None

        closed_bars = r_1m.json()[:-1]
        closes = [float(b["c"]) for b in closed_bars]
        highs = [float(b["h"]) for b in closed_bars]
        lows = [float(b["l"]) for b in closed_bars]
        opens = [float(b["o"]) for b in closed_bars]
        vols = [float(b["v"]) for b in closed_bars]
        bar_times = [int(b["t"]) for b in closed_bars]

        # 3. 21-EMA & 14-RSI (Exact Pine Script Indicators for Pro Over-Extension Check)
        ema21 = closes[0]
        k_ema = 2.0 / (21.0 + 1.0)
        for c_val in closes[1:]:
            ema21 = (c_val * k_ema) + (ema21 * (1.0 - k_ema))

        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))

        rsi14 = 50.0
        if len(gains) >= 14:
            avg_gain = sum(gains[:14]) / 14.0
            avg_loss = sum(losses[:14]) / 14.0
            for i in range(14, len(gains)):
                avg_gain = (avg_gain * 13.0 + gains[i]) / 14.0
                avg_loss = (avg_loss * 13.0 + losses[i]) / 14.0
            if avg_loss == 0:
                rsi14 = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi14 = 100.0 - (100.0 / (1.0 + rs))

        # 4. Gaussian Smoothing (gaussPeriod = 20)
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

        # 5. 3-Bar Candle Orderflow Dominance (from Pine Script)
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

        # 6. Stable-Grid Renko Brick & Special Supertrend Iteration
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
        brick_events = []

        for i in range(1, len(closes)):
            ep = eval_prices[i]
            stepped = False
            if ep >= brick_top + box_size:
                steps = int(math.floor((ep - brick_top) / box_size))
                brick_top = brick_top + (steps * box_size)
                brick_bot = brick_top - box_size
                brick_streak = steps if brick_dir == -1 else (brick_streak + steps)
                brick_dir = 1
                stepped = True
            elif ep <= brick_bot - box_size:
                steps = int(math.floor((brick_bot - ep) / box_size))
                brick_bot = brick_bot - (steps * box_size)
                brick_top = brick_bot + box_size
                brick_streak = steps if brick_dir == 1 else (brick_streak + steps)
                brick_dir = -1
                stepped = True

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

            if stepped or bar_flipped_buy or bar_flipped_sell:
                b_ist = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
                brick_events.append({
                    "time": b_ist,
                    "dir": "UP 🟢" if brick_dir == 1 else "DOWN 🔴",
                    "cls": "ic-bull" if brick_dir == 1 else "ic-bear",
                    "r_close": round(r_close, 1),
                    "streak": brick_streak,
                    "st_line": round(st_line, 1),
                    "flip": "🔥 ST FLIP BUY ▲" if bar_flipped_buy else ("🔥 ST FLIP SELL ▼" if bar_flipped_sell else "")
                })

            if i == len(closes) - 1:
                st_flip_buy = bar_flipped_buy
                st_flip_sell = bar_flipped_sell

        r_close_now = brick_top if brick_dir == 1 else brick_bot
        last_c = closes[-1]
        ema_dist_bricks = abs(last_c - ema21) / max(1.0, box_size)

        return {
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
            "buy_dom_pct": round(buy_dom_pct, 1),
            "ema21": round(ema21, 1),
            "ema_dist_bricks": round(ema_dist_bricks, 2),
            "rsi14": round(rsi14, 1),
            "last_confirmed_close": last_c,
            "brick_events": list(reversed(brick_events[-15:]))
        }
    except Exception:
        return None

# ============================================================================
# 4-STAGE PRO-TRADER DYNAMIC TRAILING CALCULATOR (NO FIXED ROBOTIC GAP!)
# ============================================================================
def compute_pro_stage_profile(peak_pts: float, live_pts: float, rk: dict, trade_type: str) -> dict:
    """
    Determines the active Pro-Trader Stage (1 to 4) based on Peak Profit and Renko Over-Extension
    (Brick Streak >= 4, EMA Stretch >= 2.0 Bricks, or RSI Exhaustion).
    """
    streak = rk.get("brick_streak", 1)
    ema_bricks = rk.get("ema_dist_bricks", 0.5)
    rsi = rk.get("rsi14", 50.0)

    is_exhausted = (
        streak >= 4
        or ema_bricks >= 2.2
        or (trade_type == "BUY" and rsi >= 74.0)
        or (trade_type == "SELL" and rsi <= 26.0)
    )

    if peak_pts < 220.0:
        return {
            "stage_num": 1,
            "stage_name": "STAGE 1: BREATHING ZONE (0–220p)",
            "min_gap": 250.0,
            "max_gap": 250.0,
            "min_lock_pts": -250.0,
            "is_exhausted": is_exhausted,
            "rule_hi": "ट्रेड अभी शुरुआती ब्रीदिंग ज़ोन (< +220p) में है — शुरुआती ~250p SL को बिल्कुल नहीं छेड़ा जाएगा।"
        }
    elif peak_pts < 450.0:
        # Stage 2: Safe Trend Zone (+220p to +450p) -> Wide gap (140p-190p), tighter if exhausted
        min_gap = 115.0 if is_exhausted else 140.0
        max_gap = 165.0 if is_exhausted else 190.0
        min_lock_pts = max(75.0, round(peak_pts - max_gap, 1))
        return {
            "stage_num": 2,
            "stage_name": "STAGE 2: SAFE TREND ZONE (220–450p)",
            "min_gap": min_gap,
            "max_gap": max_gap,
            "min_lock_pts": min_lock_pts,
            "is_exhausted": is_exhausted,
            "rule_hi": f"स्टेज 2 सक्रिय: रिस्क ज़ीरो कर दिया गया है और ट्रेंड को बड़ा चलने देने के लिए {min_gap:.0f}p–{max_gap:.0f}p का डायनामिक गैप रखा गया है।"
        }
    elif peak_pts < 700.0:
        # Stage 3: Aggressive Lock Zone (+450p to +700p) -> Medium gap (85p-130p), locks ~75-82% of peak!
        min_gap = 70.0 if is_exhausted else 85.0
        max_gap = 110.0 if is_exhausted else 130.0
        min_lock_pts = max(320.0, round(peak_pts - max_gap, 1))
        return {
            "stage_num": 3,
            "stage_name": "STAGE 3: AGGRESSIVE LOCK (450–700p)",
            "min_gap": min_gap,
            "max_gap": max_gap,
            "min_lock_pts": min_lock_pts,
            "is_exhausted": is_exhausted,
            "rule_hi": f"स्टेज 3 सक्रिय: बड़ा प्रॉफिट बन चुका है, इसलिए गैप को घटाकर {min_gap:.0f}p–{max_gap:.0f}p किया गया है (कम से कम +{min_lock_pts:.0f}p लॉक)।"
        }
    else:
        # Stage 4: Parabolic Choke Zone (+700p+) -> Tight choke gap (45p-75p), locks ~88-92% of 900pt spikes!
        min_gap = 40.0 if is_exhausted else 50.0
        max_gap = 65.0 if is_exhausted else 80.0
        min_lock_pts = max(610.0, round(peak_pts - max_gap, 1))
        return {
            "stage_num": 4,
            "stage_name": "STAGE 4: PARABOLIC CHOKE (700p+)",
            "min_gap": min_gap,
            "max_gap": max_gap,
            "min_lock_pts": min_lock_pts,
            "is_exhausted": is_exhausted,
            "rule_hi": f"स्टेज 4 (चोक ज़ोन) सक्रिय: मार्केट एक्सट्रीम पर है! मैक्सिमम प्रॉफिट बुक करने के लिए गैप को टाइट ({min_gap:.0f}p–{max_gap:.0f}p) कर दिया गया है।"
        }

# ============================================================================
# RENKO ENTRY OPENER & STRICT RE-ENTRY ARMER
# ============================================================================
def get_initial_sl_near_250pts(entry_px: float, direction: str) -> float:
    return round(entry_px - 250.0, 1) if direction == "BUY" else round(entry_px + 250.0, 1)

def open_renko_trade_now(eng, direction: str, entry_px: float, ist_str: str, entry_source_label: str):
    init_sl = get_initial_sl_near_250pts(entry_px, direction)
    init_sl_pts = round((init_sl - entry_px) if direction == "BUY" else (entry_px - init_sl), 1)
    rk = eng.get("renko", {})
    st_line_val = rk.get("st_line", entry_px)
    box_sz = rk.get("box_size", 200.0)

    new_trade = {
        "open_ts": time.time(),
        "open_time": ist_str,
        "close_time": "",
        "type": direction,
        "entry": entry_px,
        "initial_sl": init_sl,
        "sl_px": init_sl,
        "sl_pts": init_sl_pts,
        "stage_num": 1,
        "stage_name": "STAGE 1: BREATHING ZONE",
        "last_ai_peak": 0.0,
        "trail_count": 0,
        "last_trail_msg": f"🛡️ स्टेज 1 (ब्रीदिंग ज़ोन): शुरुआती SL ${init_sl:,.1f} ({init_sl_pts:+.1f} Pts) लॉक किया गया।",
        "trail_log": [],
        "live_pts": 0.0,
        "peak_pts": 0.0,
        "status": "ACTIVE (4-STAGE PRO AI)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | ST Line: ${st_line_val:,.1f})",
        "exit_reason": "अभी ट्रेड चालू है — 4-स्टेज प्रो डायनामिक ट्रेलिंग सक्रिय"
    }
    eng["active_trade"] = new_trade
    eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"{'🟢' if direction=='BUY' else '🔴'} {entry_source_label}: {direction} @ ${entry_px:,.1f}"
        eng["report"]["lock_cls"] = "lock-buy" if direction == "BUY" else "lock-sell"
        eng["report"]["lock_sub"] = f"शुरुआती SL: ${init_sl:,.1f} ({init_sl_pts:+.1f} Pts) | अब प्रो 4-स्टेज डायनामिक ट्रेलिंग सिस्टम ट्रेड को संभालेगा।"

def close_active_trade_immediately(eng, active_tr, exit_px, ist_str, reason_title, detailed_reason):
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
    box_sz = rk.get("box_size", 200.0)
    tr_dir_int = 1 if active_tr["type"] == "BUY" else -1
    dist_to_st = abs(exit_px - st_line_now) if st_line_now > 0 else 0.0
    min_far_dist = max(300.0, box_sz * 1.8)

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
                f"पिछला {active_tr['type']} ट्रेड +{move:.1f}p के प्रॉफिट में बुक हुआ जब ST Line (${st_line_now:,.0f}) {dist_to_st:.0f}p दूर थी। "
                f"प्राइस के वापस ST Line के करीब (20p–90p ज़ोन) आने पर ऑटो री-एंट्री होगी!"
            )
        }
        reentry_note = f" | 🎯 री-एंट्री वॉचर ON (ST Line ${st_line_now:,.0f} के 20-90p पास आने पर दोबारा {active_tr['type']} लिया जाएगा)"
    else:
        eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"🚨 {reason_title} — ट्रेड EXIT किया गया ({move:+.1f} Pts)"
        eng["report"]["lock_cls"] = "lock-wait"
        eng["report"]["lock_sub"] = detailed_reason + reentry_note

    if eng.get("ai_json_view"):
        eng["ai_json_view"]["badge_1"] = f"Closed: {reason_title}"
        eng["ai_json_view"]["badge_3"] = f"Exit Price: ${exit_px:,.1f}"
        eng["ai_json_view"]["badge_4"] = f"Booked: {move:+.1f} Pts"
        eng["ai_json_view"]["headline"] = detailed_reason + reentry_note
        eng["ai_json_view"]["trail_box_html"] = (
            f"<div class='trail-banner' style='border-left-color:#ef4444; background:#3b0a0a;'>"
            f"🚨 <b>ट्रेड एग्जिट ({ist_str}):</b> {detailed_reason}{reentry_note}</div>"
        )

# ============================================================================
# V21.0 PURE PRO-TRADER AI BRAIN (NO 30m/5m TAPE CLUTTER, 4-STAGE DYNAMIC GAP)
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

def pro_renko_backup_brain(ctx, active_trade):
    px = ctx["px"]
    rk = ctx["renko"]
    st_line = rk["st_line"]
    box_sz = rk["box_size"]

    if active_trade is None:
        st_dir_str = "BUY 🟢" if rk["st_trend"] == 1 else "SELL 🔴"
        return {
            "headline": f"एंट्री केवल पक्के AI-Renko फ्लिप या ST Line (${st_line:,.0f}) रीटेस्ट पर होगी (वर्तमान रैंकों ट्रेंड: {st_dir_str})।",
            "renko_structure": f"Renko Brick: ${box_sz:.0f} | rClose: ${rk['r_close']:,.0f} (Streak #{rk['brick_streak']}) | ST Line दूरी: {abs(px - st_line):.0f} Pts।",
            "extension_check": f"21-EMA से दूरी: {rk['ema_dist_bricks']:.2f} Bricks (${rk['ema21']:,.0f}) | 14-RSI: {rk['rsi14']:.1f} | 3-Bar Dominance: {rk['buy_dom_pct']:.0f}% Buy।"
        }

    t_type = active_trade["type"]
    entry_px = active_trade["entry"]
    live_pts = active_trade["live_pts"]
    peak_pts = active_trade["peak_pts"]
    curr_sl = active_trade["sl_px"]
    prof = compute_pro_stage_profile(peak_pts, live_pts, rk, t_type)
    target_gap = (prof["min_gap"] + prof["max_gap"]) / 2.0

    if prof["stage_num"] == 1:
        new_sl = curr_sl
        reason_txt = prof["rule_hi"]
    else:
        if t_type == "BUY":
            cand_sl = max(entry_px + prof["min_lock_pts"], px - target_gap)
            new_sl = round(max(curr_sl, cand_sl), 1)
        else:
            cand_sl = min(entry_px - prof["min_lock_pts"], px + target_gap)
            new_sl = round(min(curr_sl, cand_sl), 1)
        reason_txt = f"{prof['stage_name']}: Peak +{peak_pts:.0f}p के अनुसार गैप को {target_gap:.0f}p पर सेट करके SL को ${new_sl:,.1f} किया गया।"

    return {
        "action": "HOLD",
        "confidence": 88,
        "trailing_sl": new_sl,
        "sl_trail_reason": reason_txt,
        "headline": f"✅ HOLD {t_type} ({live_pts:+.1f}p | {prof['stage_name']}) — Active SL: ${new_sl:,.1f}",
        "renko_structure": f"rClose: ${rk['r_close']:,.0f} (Streak #{rk['brick_streak']}) | Renko ST Line: ${st_line:,.0f} (दूरी: {abs(px - st_line):.0f}p)।",
        "extension_check": f"21-EMA Stretch: {rk['ema_dist_bricks']:.2f} Bricks | RSI: {rk['rsi14']:.1f} | Stage Allowed Gap: {prof['min_gap']:.0f}p–{prof['max_gap']:.0f}p।"
    }

def call_gemini_pro_renko_engine(api_key, ctx, active_trade, selected_model, available_models):
    if active_trade is None:
        return pro_renko_backup_brain(ctx, None), "🟢 Pure Renko Structure Watcher"

    px = ctx["px"]
    rk = ctx["renko"]
    t_type = active_trade["type"]
    t_entry = active_trade["entry"]
    live_pts = active_trade["live_pts"]
    peak_pts = active_trade["peak_pts"]
    init_sl = active_trade["initial_sl"]
    curr_sl = active_trade["sl_px"]
    curr_sl_pts = (curr_sl - t_entry) if t_type == "BUY" else (t_entry - curr_sl)
    dur_min = (time.time() - active_trade["open_ts"]) / 60.0

    prof = compute_pro_stage_profile(peak_pts, live_pts, rk, t_type)

    prompt = f"""
You are a master Wall Street Price-Action & Renko Swing Trader managing an ACTIVE intraday BTCUSDT position opened by our 'Dr Devendra AI-Renko [Confirmed Close Algo PRO]' system.
We have completely removed noisy 30m/5m orderbook tape metrics. You must make decisions purely like a professional Renko & Price-Action trader using the 4-Stage Dynamic Profit Ratchet, Renko Brick Streak, 21-EMA Extension, and 14-RSI Exhaustion.

ACTIVE RENKO TRADE STATUS:
- Direction: {t_type} | Entry Price: ${t_entry:,.1f} | Current Live Price: ${px:,.1f}
- Live Profit/Loss: {live_pts:+.1f} Points | Peak Profit Achieved: +{peak_pts:.1f} Points | Duration: {dur_min:.1f} mins
- Initial SL (~250p): ${init_sl:,.1f} | Current Active SL: ${curr_sl:,.1f} ({curr_sl_pts:+.1f} Points locked from entry)
- Current Active Profit Stage: {prof['stage_name']}

PURE RENKO & PRICE-ACTION STRUCTURE (FROM PINE SCRIPT ENGINE):
- Stable Renko Box Size (1 Brick): ${rk['box_size']:.1f} pts
- Current Renko Brick Close (`rClose`): ${rk['r_close']:,.1f} | Brick Direction: {'BULLISH (+1)' if rk['brick_dir']==1 else 'BEARISH (-1)'} | Consecutive Brick Streak: #{rk['brick_streak']} (Max safe streak in Pine Script = 4)
- Special Renko Supertrend Line (`stLine`): ${rk['st_line']:,.1f} (Distance from live price: {abs(px - rk['st_line']):.1f} pts)
- 21-Period EMA (`ema21`): ${rk['ema21']:,.1f} | Over-Extension from 21-EMA: {rk['ema_dist_bricks']:.2f} Bricks (Over-extended if >= 2.0 Bricks)
- 14-Period RSI (`rsiVal`): {rk['rsi14']:.1f} (Overbought >= 74, Oversold <= 26)
- 3-Bar Candle Orderflow Dominance: {rk['buy_dom_pct']:.1f}% Buy / {100.0 - rk['buy_dom_pct']:.1f}% Sell
- Over-Extension / Exhaustion Detected: {'YES (Tighten gap aggressively!)' if prof['is_exhausted'] else 'NO (Normal trend expansion)'}

4-STAGE DYNAMIC PRO-TRADER TRAILING RULES (NO FIXED ROBOTIC GAP!):
1. STAGE 1 — BREATHING ZONE (Peak Profit < +220 pts):
   - Do NOT trail the Stop-Loss! Keep `trailing_sl` at `{curr_sl:.1f}` so the trade has full breathing room to survive normal BTC pullbacks.
2. STAGE 2 — SAFE TREND ZONE (Peak Profit +220 to +449 pts):
   - Eliminate risk and let the trend grow. Choose a dynamic gap between `{prof['min_gap']:.0f} and {prof['max_gap']:.0f} points` from live price `${px:,.1f}` (locking at least +{prof['min_lock_pts']:.0f} pts profit).
3. STAGE 3 — AGGRESSIVE LOCK ZONE (Peak Profit +450 to +699 pts):
   - We are deep in profit; never give back half the move! Narrow the trailing gap dynamically to `{prof['min_gap']:.0f}–{prof['max_gap']:.0f} points` behind live price (locking at least +{prof['min_lock_pts']:.0f} pts).
4. STAGE 4 — PARABOLIC CHOKE ZONE (Peak Profit >= +700 pts):
   - Parabolic move! Choke the Stop-Loss tight right behind price with a `{prof['min_gap']:.0f}–{prof['max_gap']:.0f} point gap` (locking at least +{prof['min_lock_pts']:.0f} pts) so we capture 85%–92% of massive 800–1000 point rallies!
5. WHEN TO COMMAND "EXIT":
   - Below +450 pts profit, NEVER command `"action": "EXIT"` (always output `"HOLD"`).
   - Above +450 pts profit, only command `"action": "EXIT"` if `Over-Extension` is extreme (Brick Streak >= 5 or RSI > 78 / < 22) and candle dominance flips sharply against the trade; otherwise output `"HOLD"` with a tight Stage 3/4 `trailing_sl`.

Return ONLY valid JSON matching the exact keys below. Write the 4 text explanation fields in sharp, clear Hindi:
{{
  "action": "HOLD" or "EXIT",
  "confidence": integer (0 to 100),
  "trailing_sl": float (exact new SL price based on current Stage {prof['stage_num']} gap rules, or {curr_sl:.1f} if Stage 1),
  "sl_trail_reason": "Sharp 1-line explanation in Hindi citing Stage {prof['stage_num']}, Peak Profit (+{peak_pts:.0f}p), and chosen dynamic gap",
  "headline": "Sharp 1-line Pro-Trader command and stage status in Hindi",
  "renko_structure": "Sharp 1-line analysis of Renko Brick Streak (#{rk['brick_streak']}) and ST Line (${rk['st_line']:,.0f}) in Hindi",
  "extension_check": "Sharp 1-line analysis of 21-EMA Stretch ({rk['ema_dist_bricks']:.2f} bricks) and RSI ({rk['rsi14']:.1f}) in Hindi"
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

    return pro_renko_backup_brain(ctx, active_trade), "⚡ Pro Stage Backup Brain"

# ============================================================================
# AI 4-STAGE EXECUTION CYCLE (RUNS EVERY 3 MINS OR INSTANTLY ON STAGE SPIKE!)
# ============================================================================
def execute_ai_cycle_thread(eng, now_ts, ist_str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        px = eng["px"]
        if px <= 0:
            return
        rk = eng.get("renko", {})

        ctx = {
            "time": ist_str,
            "px": px,
            "renko": rk
        }

        api_key = eng.get("api_key", "").strip()
        selected_mod = eng.get("selected_model", AUTO_MODEL_LABEL)
        avail_mods = eng.get("available_models", [])
        active_tr_snapshot = eng.get("active_trade")
        snapshot_trade_id = active_tr_snapshot["open_ts"] if active_tr_snapshot else None

        if api_key and active_tr_snapshot is not None:
            ai_json, status_str = call_gemini_pro_renko_engine(api_key, ctx, active_tr_snapshot, selected_mod, avail_mods)
        else:
            ai_json, status_str = pro_renko_backup_brain(ctx, active_tr_snapshot), "🟢 4-Stage Pro Renko Engine"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()

        current_live_tr = eng.get("active_trade")
        if snapshot_trade_id is not None and (current_live_tr is None or current_live_tr["open_ts"] != snapshot_trade_id):
            return

        live_px_now = eng["px"]
        ist_now_str = get_ist_time_str()

        if current_live_tr is None:
            st_dir_str = "BUY 🟢" if rk.get("st_trend", 1) == 1 else "SELL 🔴"
            st_line_px = rk.get("st_line", live_px_now)
            dist_st = abs(live_px_now - st_line_px)
            rw = eng.get("reentry_watch", {"armed": False})

            if rw.get("armed"):
                lock_title = f"🎯 रैंकों री-एंट्री वॉचर ON ({rw['dir_str']}) — ST Line (${st_line_px:,.0f}) के 20-90p पास आने का इंतज़ार"
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
                "badge_3": f"Brick: ${rk.get('box_size', 200.0):.0f} (#{rk.get('brick_streak', 1)})",
                "badge_4": f"Trail Mode: 4-Stage Dynamic",
                "headline": ai_json.get("headline", ""),
                "renko_structure": ai_json.get("renko_structure", ""),
                "extension_check": ai_json.get("extension_check", ""),
                "trail_box_html": ""
            }
            ctx["lock_title"] = lock_title
            ctx["lock_cls"] = lock_cls
            ctx["lock_sub"] = lock_sub
            eng["report"] = ctx

        else:
            raw_act = str(ai_json.get("action", "HOLD")).upper()
            conf = int(ai_json.get("confidence", 88))
            raw_ai_sl = float(ai_json.get("trailing_sl", current_live_tr["sl_px"]))
            trail_reason = str(ai_json.get("sl_trail_reason", "4-स्टेज प्रो डायनामिक नियम के अनुसार SL की समीक्षा की गई।")).strip()

            if 0 < abs(raw_ai_sl) < 5000:
                ai_trail_sl = (current_live_tr["entry"] + raw_ai_sl) if current_live_tr["type"] == "BUY" else (current_live_tr["entry"] - raw_ai_sl)
            else:
                ai_trail_sl = raw_ai_sl

            live_pts_now = current_live_tr["live_pts"]
            peak_pts_now = current_live_tr["peak_pts"]
            prof = compute_pro_stage_profile(peak_pts_now, live_pts_now, rk, current_live_tr["type"])

            current_live_tr["stage_num"] = prof["stage_num"]
            current_live_tr["stage_name"] = prof["stage_name"]
            current_live_tr["last_ai_peak"] = peak_pts_now

            # Only allow direct AI EXIT in Stage 3/4 (+450p+ profit)
            if raw_act == "EXIT":
                if live_pts_now >= 450.0:
                    close_active_trade_immediately(
                        eng, current_live_tr, live_px_now, ist_now_str,
                        "STAGE 3/4 PRO AI EXIT",
                        f"🤖 +{live_pts_now:.1f}p के बड़े प्रॉफिट और ओवर-एक्सटेंशन पर AI ने एग्जिट किया: {ai_json.get('headline', trail_reason)}"
                    )
                    return
                else:
                    act = "HOLD"
            else:
                act = "HOLD"

            old_sl = current_live_tr["sl_px"]
            sl_trailed_now = False
            stage_note = ""

            if prof["stage_num"] == 1:
                stage_note = prof["rule_hi"]
            else:
                # Stage 2, 3, or 4 Dynamic Gap Bounds:
                # AI can choose any SL inside [live_px - max_gap, live_px - min_gap], AND must lock at least min_lock_pts!
                min_gap = prof["min_gap"]
                max_gap = prof["max_gap"]
                min_lock_pts = prof["min_lock_pts"]

                if current_live_tr["type"] == "BUY":
                    stage_floor_sl = max(current_live_tr["entry"] + min_lock_pts, live_px_now - max_gap)
                    stage_ceil_sl = live_px_now - min_gap
                    proposed_sl = max(ai_trail_sl, stage_floor_sl)
                    capped_sl = min(proposed_sl, stage_ceil_sl)

                    if capped_sl >= old_sl + 12.0:
                        current_live_tr["sl_px"] = round(capped_sl, 1)
                        current_live_tr["sl_pts"] = round(current_live_tr["sl_px"] - current_live_tr["entry"], 1)
                        sl_trailed_now = True
                    else:
                        stage_note = f"{prof['stage_name']}: वर्तमान SL (${old_sl:,.1f}) पहले से ही {min_gap:.0f}p–{max_gap:.0f}p के डायनामिक गैप पर सुरक्षित है।"

                else:
                    stage_ceil_sl = min(current_live_tr["entry"] - min_lock_pts, live_px_now + max_gap)
                    stage_floor_sl = live_px_now + min_gap
                    proposed_sl = min(ai_trail_sl, stage_ceil_sl)
                    capped_sl = max(proposed_sl, stage_floor_sl)

                    if capped_sl <= old_sl - 12.0:
                        current_live_tr["sl_px"] = round(capped_sl, 1)
                        current_live_tr["sl_pts"] = round(current_live_tr["entry"] - current_live_tr["sl_px"], 1)
                        sl_trailed_now = True
                    else:
                        stage_note = f"{prof['stage_name']}: वर्तमान SL (${old_sl:,.1f}) पहले से ही {min_gap:.0f}p–{max_gap:.0f}p के डायनामिक गैप पर सुरक्षित है।"

            curr_sl_pts = current_live_tr["sl_pts"]
            gap_now = abs(live_px_now - current_live_tr["sl_px"])
            shown_reason = stage_note if stage_note else trail_reason

            if sl_trailed_now:
                current_live_tr["trail_count"] += 1
                pts_shifted = abs(current_live_tr["sl_px"] - old_sl)
                pct_locked = int((curr_sl_pts / max(1.0, peak_pts_now)) * 100) if curr_sl_pts > 0 else 0

                event_str = (
                    f"🔄 <b>{prof['stage_name']} ट्रेल #{current_live_tr['trail_count']} ({ist_now_str}):</b> "
                    f"<span style='color:#f87171; text-decoration:line-through;'>${old_sl:,.1f}</span> ➔ "
                    f"<b style='color:#4ade80; font-size:14.5px;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> "
                    f"(<span style='color:#facc15;'>+{pts_shifted:.1f}p शिफ्ट | Peak का {pct_locked}% लॉक | Dynamic Gap: {gap_now:.0f}p</span>)<br>"
                    f"📌 <b>AI प्रो-ट्रेडर कारण:</b> {trail_reason}"
                )
                current_live_tr["last_trail_msg"] = event_str
                current_live_tr["trail_log"].insert(
                    0, f"[{ist_now_str}] Stage {prof['stage_num']}: ${old_sl:,.1f} ➔ ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p | Gap {gap_now:.0f}p)"
                )
                eng["sound_event"] = {"id": time.time(), "type": "TRAIL"}
            else:
                event_str = (
                    f"🛡️ <b>{prof['stage_name']} ({ist_now_str}):</b> एक्टिव SL: <b style='color:#facc15;'>${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts)</b> | "
                    f"डायनामिक गैप: <b>{gap_now:.0f} Pts</b> | Peak: <b>+{peak_pts_now:.1f}p</b><br>"
                    f"📌 <b>प्रो-ट्रेडर नोट:</b> {shown_reason}"
                )

            trail_box_html = f"<div class='trail-banner'>{event_str}</div>"

            lock_title = f"{'🟢' if current_live_tr['type']=='BUY' else '🔴'} रैंकों {current_live_tr['type']} चालू ({prof['stage_name']}) — Live: {live_pts_now:+.1f} Pts"
            lock_cls = "lock-buy" if current_live_tr["type"] == "BUY" else "lock-sell"
            lock_sub = (
                f"एंट्री: ${current_live_tr['entry']:,.1f} | "
                f"एक्टिव SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f} Pts | Gap: {gap_now:.0f}p) | "
                f"Peak: +{peak_pts_now:.1f}p | ट्रेल: {current_live_tr['trail_count']}x"
            )

            eng["ai_json_view"] = {
                "mode": "TRADE_MANAGER",
                "badge_1": f"{prof['stage_name']}",
                "badge_2": f"Entry: ${current_live_tr['entry']:,.1f}",
                "badge_3": f"Active SL: ${current_live_tr['sl_px']:,.1f} ({curr_sl_pts:+.1f}p)",
                "badge_4": f"Dynamic Gap: {gap_now:.0f}p | Peak: +{peak_pts_now:.0f}p",
                "headline": ai_json.get("headline", ""),
                "renko_structure": ai_json.get("renko_structure", ""),
                "extension_check": ai_json.get("extension_check", ""),
                "trail_box_html": trail_box_html
            }

            ctx["lock_title"] = lock_title
            ctx["lock_cls"] = lock_cls
            ctx["lock_sub"] = lock_sub
            eng["report"] = ctx

    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 1-SECOND BACKGROUND WORKER (1s SL + INSTANT STAGE SPIKE RATCHET)
# ============================================================================
def background_worker(eng, worker_id):
    REPORT_INTERVAL_SEC = 180
    cached_box_size = None

    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            ist_str = get_ist_time_str()
            px_res = fetch_live_btc_price()

            if isinstance(px_res, str):
                eng["last_err"] = px_res
            elif isinstance(px_res, float) and px_res > 0:
                px = px_res
                eng["px"] = px
                eng["last_update"] = ist_str
                rk = eng.get("renko", {})

                # 1. 1-SECOND REAL-TIME SL GUARD + INSTANT 4-STAGE SPIKE RATCHET
                active_tr = eng.get("active_trade")
                if active_tr is not None:
                    move = (px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - px)
                    prev_stage = active_tr.get("stage_num", 1)
                    active_tr["live_pts"] = move
                    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)

                    prof = compute_pro_stage_profile(active_tr["peak_pts"], move, rk, active_tr["type"])
                    active_tr["stage_num"] = prof["stage_num"]
                    active_tr["stage_name"] = prof["stage_name"]

                    # INSTANT SPIKE RATCHET: If price spikes into Stage 2/3/4 between 3-min AI checks,
                    # enforce the stage's max_gap floor immediately so a fast 900pt spike never gives back 400pts!
                    if prof["stage_num"] >= 2:
                        old_sl = active_tr["sl_px"]
                        max_allowed_gap = prof["max_gap"]
                        min_lock = prof["min_lock_pts"]

                        if active_tr["type"] == "BUY":
                            instant_floor_sl = round(max(active_tr["entry"] + min_lock, px - max_allowed_gap), 1)
                            if instant_floor_sl >= old_sl + 25.0 and instant_floor_sl < px - prof["min_gap"]:
                                active_tr["sl_px"] = instant_floor_sl
                                active_tr["sl_pts"] = round(instant_floor_sl - active_tr["entry"], 1)
                                active_tr["trail_count"] += 1
                                gap_now = abs(px - instant_floor_sl)
                                active_tr["trail_log"].insert(
                                    0, f"[{ist_str}] ⚡ Auto-{prof['stage_name'][:7]} Ratchet: ${old_sl:,.1f} ➔ ${instant_floor_sl:,.1f} ({active_tr['sl_pts']:+.1f}p | Gap {gap_now:.0f}p)"
                                )
                        else:
                            instant_ceil_sl = round(min(active_tr["entry"] - min_lock, px + max_allowed_gap), 1)
                            if instant_ceil_sl <= old_sl - 25.0 and instant_ceil_sl > px + prof["min_gap"]:
                                active_tr["sl_px"] = instant_ceil_sl
                                active_tr["sl_pts"] = round(active_tr["entry"] - instant_ceil_sl, 1)
                                active_tr["trail_count"] += 1
                                gap_now = abs(px - instant_ceil_sl)
                                active_tr["trail_log"].insert(
                                    0, f"[{ist_str}] ⚡ Auto-{prof['stage_name'][:7]} Ratchet: ${old_sl:,.1f} ➔ ${instant_ceil_sl:,.1f} ({active_tr['sl_pts']:+.1f}p | Gap {gap_now:.0f}p)"
                                )

                        # Also trigger AI brain immediately whenever trade upgrades to a new Stage or jumps +90p in Peak!
                        if (prof["stage_num"] > prev_stage or (active_tr["peak_pts"] - active_tr.get("last_ai_peak", 0.0) >= 90.0)) and not eng.get("ai_busy"):
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                    # Check 1-second SL breach
                    sl_pts_locked = active_tr["sl_pts"]
                    if active_tr["type"] == "BUY":
                        sl_breached = (px <= active_tr["sl_px"]) or (move <= sl_pts_locked)
                    else:
                        sl_breached = (px >= active_tr["sl_px"]) or (move <= sl_pts_locked)

                    if sl_breached:
                        sl_kind = f"STAGE {prof['stage_num']} TRAILED SL HIT" if active_tr["trail_count"] > 0 else "INITIAL ~250p SL HIT"
                        detail_msg = (
                            f"🛡️ {sl_kind}: लाइव प्राइस ${px:,.1f} ({move:+.1f} Pts) ने आपके एक्टिव स्टॉप-लॉस "
                            f"${active_tr['sl_px']:,.1f} ({sl_pts_locked:+.1f} Pts | Peak: +{active_tr['peak_pts']:.1f}p) को छू लिया — तुरंत एग्जिट!"
                        )
                        close_active_trade_immediately(eng, active_tr, px, ist_str, sl_kind, detail_msg)

                # 2. STRICT STABLE-GRID RENKO PULLBACK RE-ENTRY (20p to 90p zone)
                rw = eng.get("reentry_watch", {"armed": False})
                if eng.get("active_trade") is None and rw.get("armed") and rk.get("st_line", 0.0) > 0:
                    st_trend_now = rk["st_trend"]
                    st_line_now = rk["st_line"]
                    elapsed_since_arm = now_ts - rw.get("armed_ts", 0.0)

                    if st_trend_now != rw["dir"]:
                        eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
                    elif elapsed_since_arm >= 45.0:
                        if rw["dir"] == 1 and (st_line_now + 20.0 <= px <= st_line_now + 90.0):
                            open_renko_trade_now(eng, "BUY", px, ist_str, "🔄 Renko ST Line Pullback Re-Entry ▲")
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()
                        elif rw["dir"] == -1 and (st_line_now - 90.0 <= px <= st_line_now - 20.0):
                            open_renko_trade_now(eng, "SELL", px, ist_str, "🔄 Renko ST Line Pullback Re-Entry ▼")
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                # 3. UPDATE PURE AI-RENKO STRUCTURE EVERY 12 SECONDS
                if now_ts - eng["last_kline_ts"] > 12:
                    rk_data = fetch_renko_pro_structure(locked_box_size=cached_box_size)
                    if rk_data:
                        cached_box_size = rk_data["box_size"]
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data

                        if prev_rk_trend == 0:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()
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

                # 4. PERIODIC 3-MINUTE AI CHECK
                if now_ts - eng["last_report_ts"] >= REPORT_INTERVAL_SEC and rk.get("st_line", 0.0) > 0 and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v21_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "signal_history": [], "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0, "last_handled_flip_ts": 0,
        "renko": {
            "box_size": 200.0, "macro_range": 2000.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "st_flip_buy": False, "st_flip_sell": False,
            "buy_dom_pct": 50.0, "ema21": 0.0, "ema_dist_bricks": 0.0, "rsi14": 50.0,
            "brick_events": []
        },
        "reentry_watch": {"armed": False, "dir": 0, "dir_str": "", "reason": ""},
        "report": None,
        "available_models": [],
        "models_fetched": False,
        "selected_model": AUTO_MODEL_LABEL,
        "ai_json_view": {
            "mode": "INIT",
            "badge_1": "Stage: Scanning...",
            "badge_2": "ST Line: --",
            "badge_3": "Initial SL: ~250p",
            "badge_4": "4-Stage Dynamic Gap",
            "headline": "⏳ Pure AI-Renko एवं 4-Stage Pro Trailing इंजन स्टार्ट हो रहा है...",
            "renko_structure": "रैंकों ब्रिक्स और सुपरट्रेंड स्कैन हो रहे हैं...",
            "extension_check": "21-EMA और RSI एक्सटेंशन की गणना हो रही है...",
            "trail_box_html": ""
        },
        "ai_status": "🤖 4-Stage Pro Renko AI",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v21_0()

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
    if st.button("🤖 अभी AI से 4-स्टेज SL ट्रेल अपडेट कराएं"):
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
        next_sec = max(0, int(180 - (time.time() - eng["last_report_ts"]))) if eng["last_report_ts"] > 0 else 0
        mod_label_short = "Pro-Priority Auto" if eng["selected_model"] == AUTO_MODEL_LABEL else eng["selected_model"]
        rk = eng.get("renko", {})
        rw = eng.get("reentry_watch", {"armed": False})
        act_tr = eng.get("active_trade")

        active_prof = compute_pro_stage_profile(
            act_tr["peak_pts"] if act_tr else 0.0,
            act_tr["live_pts"] if act_tr else 0.0,
            rk,
            act_tr["type"] if act_tr else ("BUY" if rk.get("st_trend", 1) == 1 else "SELL")
        )

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            is_act = "ACTIVE" in h["status"]
            sts_badge = f"🟢 {h.get('stage_name', 'STAGE 1')}" if is_act else f"🏁 {h['status']}"
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

        # Right Panel: 4-Stage Pro Trailing Roadmap + Recent Confirmed Renko Brick Steps
        cur_stg = active_prof["stage_num"] if act_tr else 0
        stage_roadmap_html = f"""
        <div class='item-card {"ic-active-stage" if cur_stg == 1 else "ic-warn"}'>
            <b>🛡️ STAGE 1: द ब्रीदिंग ज़ोन (Peak: 0 से +220 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: शुरुआती <b>~250 Pts SL</b> को बिल्कुल नहीं छेड़ा जाएगा ताकि ट्रेड छोटे झटकों से बाहर न हो।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_stg == 2 else "ic-bull"}'>
            <b>🟢 STAGE 2: द सेफ ट्रेंड ज़ोन (Peak: +220 से +450 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: रिस्क ज़ीरो! प्राइस से <b>140p–190p का चौड़ा गैप</b> रखकर SL को कॉस्ट+प्रॉफिट में लॉक किया जाता है।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_stg == 3 else "ic-bull"}'>
            <b>🚀 STAGE 3: द एग्रेसिव लॉक ज़ोन (Peak: +450 से +700 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: बड़ा मुनाफा वापस जाने से रोकने के लिए गैप घटकर <b>85p–130p</b> हो जाता है (Peak का ~78% लॉक)।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_stg == 4 else "ic-bull"}'>
            <b>🔥 STAGE 4: पैराबोलिक चोक ज़ोन (Peak: +700 Pts से ऊपर)</b><br>
            <span style='color:#cbd5e1;'>नियम: 800-1000p की एक्सट्रीम रैली में <b>45p–75p का एकदम टाइट गैप</b> रखकर टॉप/बॉटम के पास ~90% प्रॉफिट लॉक!</span>
        </div>
        """

        brick_cards = ""
        for idx, b in enumerate(rk.get("brick_events", []), 1):
            flip_tag = f"<span style='color:#facc15; font-weight:900; margin-left:6px;'>{b['flip']}</span>" if b["flip"] else ""
            brick_cards += f"""
            <div class='item-card {b["cls"]}'>
                <div style='display:flex; justify-content:space-between; font-weight:800;'>
                    <span>#{idx} 🕒 {b["time"]} | Brick: {b["dir"]} (Streak #{b["streak"]})</span>
                    <span style='color:#38bdf8;'>rClose: ${b["r_close"]:,.1f}</span>
                </div>
                <div style='color:#cbd5e1; font-size:11.8px; margin-top:2px;'>
                    Renko ST Line: <b>${b["st_line"]:,.1f}</b> {flip_tag}
                </div>
            </div>
            """
        if not brick_cards:
            brick_cards = "<div style='text-align:center; color:#64748b; padding-top:40px;'>कन्फर्म्ड रैंकों ब्रिक्स लोड हो रही हैं...</div>"

        st_trend_col = "#4ade80" if rk.get("st_trend", 1) == 1 else "#f87171"
        st_trend_txt = "BUY 🟢 (Bullish)" if rk.get("st_trend", 1) == 1 else "SELL 🔴 (Bearish)"
        brick_dir_txt = f"🟢 Up (Streak #{rk.get('brick_streak', 1)})" if rk.get("brick_dir", 1) == 1 else f"🔴 Down (Streak #{rk.get('brick_streak', 1)})"
        st_dist_pts = abs(eng["px"] - rk.get("st_line", eng["px"]))
        reentry_status_txt = f"🎯 ARMED ({rw.get('dir_str')} @ 20-90p from ${rk.get('st_line', 0):,.0f})" if rw.get("armed") else "⚪ Standby (+200p Exit & >300p ST Dist)"

        if act_tr:
            gap_now = abs(eng["px"] - act_tr["sl_px"])
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} रैंकों {act_tr['type']} चालू — {active_prof['stage_name']}"
            banner_sub = (
                f"एंट्री: ${act_tr['entry']:,.1f} | एक्टिव SL: ${act_tr['sl_px']:,.1f} ({act_tr['sl_pts']:+.1f} Pts | Dynamic Gap: {gap_now:.0f}p) | "
                f"Peak: +{act_tr['peak_pts']:.1f}p"
            )
            right_stat_label = f"LIVE PNL (SL: {act_tr['sl_pts']:+.1f}p)"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            if rw.get("armed"):
                banner_title = f"🎯 रैंकों री-एंट्री वॉचर ON ({rw['dir_str']}) — ST Line (${rk.get('st_line', 0.0):,.0f}) के पास आने की प्रतीक्षा"
                banner_sub = rw.get("reason", "")
            else:
                banner_title = f"⚪ रैंकों डायरेक्ट सिग्नल की प्रतीक्षा (चालू रैंकों सुपरट्रेंड: {st_trend_txt})"
                banner_sub = f"Renko ST Line: ${rk.get('st_line', 0.0):,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर) | नए फ्लिप या ऊपर मैनुअल सिंक बटन से एंट्री होगी।"
            right_stat_label = "AI CYCLE TIMER"
            right_stat_val = f"{next_sec}s"
            right_stat_col = "#38bdf8"

        aj = eng["ai_json_view"]
        exh_col = "#facc15" if active_prof["is_exhausted"] else "#4ade80"
        exh_txt = "⚠️ Over-Extended (Tight Gap)" if active_prof["is_exhausted"] else "✅ Healthy Normal Trend"

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
                <span style='font-size:15px; font-weight:900; color:#c084fc;'>🧠 4-स्टेज प्रो डायनामिक AI ट्रेलिंग मैनेजर (Pure Renko & Price Action)</span>
                <span style='font-size:11.5px; color:#4ade80; font-weight:bold;'>{eng["ai_status"]}</span>
            </div>
            <div>
                <span class='json-pill'>{aj["badge_1"]}</span>
                <span class='json-pill'>{aj["badge_2"]}</span>
                <span class='json-pill'>{aj["badge_3"]}</span>
                <span class='json-pill'>{aj["badge_4"]}</span>
            </div>
            <div style='font-size:14px; line-height:1.65; color:#f8fafc; margin-top:10px;'>
                <div>🎯 <b>प्रो-ट्रेडर कमांड:</b> {aj["headline"]}</div>
                <div style='margin-top:4px;'>🧱 <b>रैंकों ब्रिक एवं ST संरचना:</b> {aj.get("renko_structure", "")}</div>
                <div style='margin-top:4px;'>📐 <b>21-EMA एवं RSI एक्सटेंशन जांच:</b> {aj.get("extension_check", "")}</div>
            </div>
            {aj.get("trail_box_html", "")}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. Dr Devendra AI-Renko इंजन (Direct Mode)</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>स्पेशल रैंकों सुपरट्रेंड लाइन (stLine):</span><b><span style='color:{st_trend_col};'>${rk.get("st_line", 0.0):,.1f}</span> (दूरी: {st_dist_pts:.0f} Pts)</b></div>
                <div class='stat-row'><span>स्थिर ब्रिक साइज (Stable Locked):</span><b style='color:#facc15;'>${rk.get("box_size", 200.0):.1f} Pts</b></div>
                <div class='stat-row'><span>रैंकों ब्रिक क्लोज (rClose) एवं स्ट्रीक:</span><b>${rk.get("r_close", 0.0):,.1f} ({brick_dir_txt})</b></div>
                <div class='stat-row' style='border:none;'><span>ST पुलबैक री-एंट्री वॉचर:</span><b style='color:#38bdf8;'>{reentry_status_txt}</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>🎯 2. प्रो-ट्रेडर एक्सटेंशन एवं डायनामिक गैप</span>
                    <span style='color:{exh_col};'>{exh_txt}</span>
                </div>
                <div class='stat-row'><span>चालू प्रॉफिट स्टेज एवं अनुमत गैप:</span><b style='color:#facc15;'>Stage {active_prof["stage_num"]} ({active_prof["min_gap"]:.0f}p–{active_prof["max_gap"]:.0f}p Gap)</b></div>
                <div class='stat-row'><span>21-EMA से दूरी (Over-Extension):</span><b>{rk.get("ema_dist_bricks", 0.0):.2f} Bricks (EMA: ${rk.get("ema21", 0.0):,.0f})</b></div>
                <div class='stat-row'><span>14-RSI मोमेंटम एवं 3-Bar पावर:</span><b>RSI: {rk.get("rsi14", 50.0):.1f} | <span style='color:#4ade80;'>{rk.get("buy_dom_pct", 50.0):.0f}% Buy</span></b></div>
                <div class='stat-row' style='border:none;'><span>स्टेज गारंटीड लॉक फ्लोर:</span><b style='color:#4ade80;'>{f"+{active_prof['min_lock_pts']:.0f} Pts Min Lock" if active_prof["stage_num"] >= 2 else "Breathing Room (-250p SL)"}</b></div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V21.0 (PURE AI-RENKO & 4-STAGE DYNAMIC PRO TRAILING)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🎯 30m/5m नॉइज़ मुक्त | 1s स्पाइक रैचेट: <b style='color:#4ade80;'>ON</b> | अगली AI जांच: <b>{next_sec}s</b> | 🧠 AI: <b style='color:#c084fc;'>{mod_label_short}</b></div>
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
                            📜 रैंकों ट्रेड एवं 4-स्टेज डायनामिक स्टॉप-लॉस हिस्ट्री
                        </div>
                        {hist_cards}
                    </div>
                </div>

                <div class='stage-panel'>
                    <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        📐 4-स्टेज प्रो ट्रेलिंग रोडमैप (Active Stage Highlighted)
                    </div>
                    {stage_roadmap_html}
                    <div style='font-size:13.5px; font-weight:900; color:#38bdf8; margin:12px 0 8px 0; border-bottom:1px solid #334155; padding-bottom:5px;'>
                        🧱 ताज़ा कन्फर्म्ड रैंकों ब्रिक स्टेप्स एवं फ्लिप लॉग
                    </div>
                    {brick_cards}
                </div>
            </div>
        </div>
        """), unsafe_allow_html=True)

    else:
        dashboard_slot.warning("⏳ 24x7 V21.0 (Pure AI-Renko & 4-Stage Pro Trailing Engine) स्टार्ट हो रहा है... कृपया 2 सेकंड प्रतीक्षा करें।")

    time.sleep(1.5)

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

st.set_page_config(page_title="Pro Quant V23.0 - Pure Signal-to-Signal Renko ST", layout="wide")

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
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 320px; overflow-y: auto; }
.brick-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 690px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; margin-top: 2px; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
div[data-baseweb="select"] > div { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #c084fc !important; border-radius: 7px !important; font-weight: 700 !important; }
div[data-baseweb="input"] > div { background-color: #1e293b !important; color: #facc15 !important; border: 1px solid #facc15 !important; border-radius: 7px !important; font-weight: 800 !important; }
input[type="number"] { color: #facc15 !important; font-weight: 800 !important; }
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
# CORE ARCHITECTURE: SYNTHETIC RENKO SUPERTREND (SIGNAL TO SIGNAL)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_live_btc_price():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "allMids"}, timeout=1.8)
        if r.status_code == 200:
            mids = r.json()
            if isinstance(mids, dict) and "BTC" in mids:
                return float(mids["BTC"])
    except Exception as e:
        return str(e)
    return None

def fetch_core_renko_supertrend(fixed_brick_size: float = 270.0, rev_bricks: float = 2.0):
    try:
        brick_size = max(10.0, float(fixed_brick_size))
        now_ms = int(time.time() * 1000)

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

        ema21 = closes[0]
        k_ema = 2.0 / (21.0 + 1.0)
        for c_val in closes[1:]:
            ema21 = (c_val * k_ema) + (ema21 * (1.0 - k_ema))

        gains, losses = [], []
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
            rsi14 = 100.0 if avg_loss == 0 else (100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))))

        bar_buy_v, bar_sell_v = [], []
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

        st_factor = 3.0
        band_distance = box_size * st_factor

        snapped = math.floor(closes[0] / brick_size) * brick_size
        brick_bot = snapped
        brick_top = snapped + brick_size
        trend = 1
        st_level = brick_top - (rev_bricks * brick_size)
        brick_streak = 1

        buy_signal = False
        sell_signal = False
        last_flip_bar_ts = bar_times[0]
        brick_events = []

        for i in range(1, len(closes)):
            c = closes[i]
            prev_trend = trend
            prev_st_level = st_level
            stepped_bricks = 0
            flipped_now = False

            if trend == 1:
                if c >= brick_top + brick_size:
                    steps = int(math.floor((c - brick_top) / brick_size))
                    brick_top = brick_top + (steps * brick_size)
                    brick_bot = brick_top - brick_size
                    brick_streak += steps
                    stepped_bricks = steps

                raw_support = brick_top - (rev_bricks * brick_size)
                st_level = max(raw_support, prev_st_level)

                if c < st_level:
                    trend = -1
                    down_steps = max(1, int(math.floor((brick_top - c) / brick_size)))
                    brick_bot = brick_top - (down_steps * brick_size)
                    brick_top = brick_bot + brick_size
                    st_level = brick_bot + (rev_bricks * brick_size)
                    brick_streak = down_steps
                    flipped_now = True
                    last_flip_bar_ts = bar_times[i]

            elif trend == -1:
                if c <= brick_bot - brick_size:
                    steps = int(math.floor((brick_bot - c) / brick_size))
                    brick_bot = brick_bot - (steps * brick_size)
                    brick_top = brick_bot + brick_size
                    brick_streak += steps
                    stepped_bricks = steps

                raw_res = brick_bot + (rev_bricks * brick_size)
                st_level = min(raw_res, prev_st_level)

                if c > st_level:
                    trend = 1
                    up_steps = max(1, int(math.floor((c - brick_bot) / brick_size)))
                    brick_top = brick_bot + (up_steps * brick_size)
                    brick_bot = brick_top - brick_size
                    st_level = brick_top - (rev_bricks * brick_size)
                    brick_streak = up_steps
                    flipped_now = True
                    last_flip_bar_ts = bar_times[i]

            bar_buy_sig = (trend == 1 and prev_trend == -1)
            bar_sell_sig = (trend == -1 and prev_trend == 1)

            if stepped_bricks > 0 or flipped_now:
                b_ist = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
                brick_events.append({
                    "time": b_ist,
                    "dir": "BULLISH 🟢" if trend == 1 else "BEARISH 🔴",
                    "cls": "ic-bull" if trend == 1 else "ic-bear",
                    "brick_top": round(brick_top, 1),
                    "brick_bot": round(brick_bot, 1),
                    "streak": brick_streak,
                    "st_line": round(st_level, 1),
                    "flip": "🔥 BUY SIGNAL ▲" if bar_buy_sig else ("🔥 SELL SIGNAL ▼" if bar_sell_sig else "")
                })

            if i == len(closes) - 1:
                buy_signal = bar_buy_sig
                sell_signal = bar_sell_sig

        r_close_now = brick_top if trend == 1 else brick_bot
        last_c = closes[-1]
        ema_dist_bricks = abs(last_c - ema21) / max(1.0, brick_size)

        return {
            "box_size": round(brick_size, 1),
            "rev_bricks": rev_bricks,
            "brick_top": round(brick_top, 1),
            "brick_bot": round(brick_bot, 1),
            "brick_dir": trend,
            "brick_streak": brick_streak,
            "r_close": round(r_close_now, 1),
            "st_trend": trend,
            "st_line": round(st_level, 1),
            "st_flip_buy": buy_signal,
            "st_flip_sell": sell_signal,
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
# SIGNAL-TO-SIGNAL TRADE EXECUTION (NO SL / NO TRAILING)
# ============================================================================
def open_signal_trade_now(eng, direction: str, entry_px: float, ist_str: str, entry_source_label: str):
    rk = eng.get("renko", {})
    st_line_val = rk.get("st_line", entry_px)
    box_sz = rk.get("box_size", 270.0)

    new_trade = {
        "open_ts": time.time(),
        "open_time": ist_str,
        "close_time": "",
        "type": direction,
        "entry": entry_px,
        "live_pts": 0.0,
        "peak_pts": 0.0,
        "status": "ACTIVE (SIGNAL-TO-SIGNAL)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | ST Line: ${st_line_val:,.1f})",
        "exit_reason": "ट्रेड चालू है — विपरीत सिग्नल (Opposite Signal) आते ही बंद होगा"
    }
    eng["active_trade"] = new_trade
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"{'🟢' if direction=='BUY' else '🔴'} {entry_source_label}: {direction} @ ${entry_px:,.1f}"
        eng["report"]["lock_cls"] = "lock-buy" if direction == "BUY" else "lock-sell"
        eng["report"]["lock_sub"] = f"सिग्नल-टू-सिग्नल मोड: कोई फिक्स SL नहीं है। विपरीत सिग्नल पर ट्रेड फ्लिप होगा।"

def close_signal_trade_at_price(eng, active_tr, exit_px: float, ist_str: str, reason_title: str):
    move = (exit_px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - exit_px)
    active_tr["live_pts"] = move
    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)
    active_tr["close_time"] = ist_str
    active_tr["status"] = f"{reason_title} @ ${exit_px:,.1f} ({ist_str})"
    active_tr["exit_reason"] = f"विपरीत सिग्नल मिलने पर ट्रेड बंद हुआ (PnL: {move:+.1f} Pts)"

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

    if eng.get("report"):
        eng["report"]["lock_title"] = f"🚨 {reason_title} — ट्रेड बंद हुआ ({move:+.1f} Pts)"
        eng["report"]["lock_cls"] = "lock-wait"
        eng["report"]["lock_sub"] = f"एग्जिट प्राइस: ${exit_px:,.1f} | कुल PnL: {move:+.1f} Pts"

# ============================================================================
# AI MARKET COMMENTARY BRAIN (SIGNAL-TO-SIGNAL MODE)
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

def signal_commentary_backup_brain(ctx, active_trade):
    px = ctx["px"]
    rk = ctx["renko"]
    st_line = rk["st_line"]
    box_sz = rk["box_size"]
    st_dir = "BUY 🟢" if rk["st_trend"] == 1 else "SELL 🔴"

    if active_trade is None:
        return {
            "headline": f"सिग्नल-टू-सिग्नल मोड सक्रिय: अगला Core Renko ST फ्लिप (BUY/SELL) होते ही ट्रेड ले लिया जाएगा।",
            "renko_structure": f"Fixed Brick: ${box_sz:.0f} | Core Trend: {st_dir} | Reversal Level: ${st_line:,.0f} (दूरी: {abs(px - st_line):.0f}p)।",
            "extension_check": f"21-EMA: ${rk['ema21']:,.0f} | RSI: {rk['rsi14']:.1f} | Dominance: {rk['buy_dom_pct']:.0f}% Buy।"
        }
    else:
        t_type = active_trade["type"]
        live_pts = active_trade["live_pts"]
        return {
            "headline": f"✅ {t_type} ट्रेड चालू है ({live_pts:+.1f}p) — यह तब तक चलेगा जब तक विपरीत सिग्नल नहीं आता।",
            "renko_structure": f"Fixed Brick: ${box_sz:.0f} | Core Trend: {st_dir} | Reversal Level: ${st_line:,.0f}।",
            "extension_check": f"RSI: {rk['rsi14']:.1f} | Live PnL: {live_pts:+.1f} Pts।"
        }

def call_gemini_commentary_engine(api_key, ctx, active_trade, selected_model, available_models):
    if active_trade is None:
        return signal_commentary_backup_brain(ctx, None), "🟢 Signal-to-Signal Watcher"

    px = ctx["px"]
    rk = ctx["renko"]
    t_type = active_trade["type"]
    live_pts = active_trade["live_pts"]

    prompt = f"""
You are an institutional trading assistant monitoring an ACTIVE BTCUSDT position in Signal-to-Signal (Direct Flip) mode using the 'AI Renko Supertrend [Core Architecture]'.
There is no Stop-Loss and no Trailing. The trade stays open until the opposite Renko Supertrend signal fires. Provide a professional market commentary in Hindi.

ACTIVE TRADE STATUS:
- Direction: {t_type} | Live PnL: {live_pts:+.1f} Points | Current Price: ${px:,.1f}
- Core Renko Trend: {'BULLISH (1)' if rk['st_trend']==1 else 'BEARISH (-1)'} | Reversal Level (stLevel): ${rk['st_line']:,.1f}
- RSI: {rk['rsi14']:.1f} | EMA Stretch: {rk['ema_dist_bricks']:.2f} bricks

Return ONLY valid JSON:
{{
  "action": "HOLD",
  "confidence": 90,
  "trailing_sl": 0.0,
  "sl_trail_reason": "Signal-to-Signal mode: no trailing or SL used.",
  "headline": "Sharp 1-line trade status in Hindi",
  "renko_structure": "Sharp 1-line analysis of Renko trend and stLevel in Hindi",
  "extension_check": "Sharp 1-line RSI and EMA analysis in Hindi"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
    }

    pro_first_priority = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    sorted_avail = sorted(available_models or [], key=score_model_priority)
    combined_auto = [m for m in sorted_avail + pro_first_priority if m not in combined_auto] if False else pro_first_priority

    for mod in combined_auto:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=8.0)
            if res.status_code == 200:
                raw_txt = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                parsed = parse_ai_json_safely(raw_txt)
                if parsed:
                    return parsed, f"🟢 AI Commentary ({mod})"
        except Exception:
            continue

    return signal_commentary_backup_brain(ctx, active_trade), "⚡ Commentary Backup Brain"

def execute_ai_cycle_thread(eng, now_ts, ist_str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        px = eng["px"]
        if px <= 0:
            return
        rk = eng.get("renko", {})
        ctx = {"time": ist_str, "px": px, "renko": rk}

        api_key = eng.get("api_key", "").strip()
        selected_mod = eng.get("selected_model", AUTO_MODEL_LABEL)
        avail_mods = eng.get("available_models", [])
        active_tr_snapshot = eng.get("active_trade")

        if api_key:
            ai_json, status_str = call_gemini_commentary_engine(api_key, ctx, active_tr_snapshot, selected_mod, avail_mods)
        else:
            ai_json, status_str = signal_commentary_backup_brain(ctx, active_tr_snapshot), "🟢 Signal-to-Signal Engine"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()

        if active_tr_snapshot:
            active_tr_snapshot["live_pts"] = (px - active_tr_snapshot["entry"]) if active_tr_snapshot["type"] == "BUY" else (active_tr_snapshot["entry"] - px)
            active_tr_snapshot["peak_pts"] = max(active_tr_snapshot["peak_pts"], active_tr_snapshot["live_pts"])

        st_dir_str = "BUY 🟢" if rk.get("st_trend", 1) == 1 else "SELL 🔴"
        st_line_px = rk.get("st_line", px)
        dist_st = abs(px - st_line_px)

        if active_tr_snapshot:
            lock_title = f"{'🟢' if active_tr_snapshot['type']=='BUY' else '🔴'} सिग्नल-टू-सिग्नल ट्रेड चालू ({active_tr_snapshot['type']})"
            lock_cls = "lock-buy" if active_tr_snapshot["type"] == "BUY" else "lock-sell"
            lock_sub = f"एंट्री: ${active_tr_snapshot['entry']:,.1f} | लाइव PnL: {active_tr_snapshot['live_pts']:+.1f} Pts | विपरीत सिग्नल पर बंद होगा।"
        else:
            lock_title = f"⚪ सिग्नल-टू-सिग्नल मोड (Core Trend: {st_dir_str})"
            lock_cls = "lock-wait"
            lock_sub = f"Reversal Level: ${st_line_px:,.1f} (दूरी: {dist_st:.0f}p) | अगले फ्लिप पर नया ट्रेड खुलेगा।"

        eng["ai_json_view"] = {
            "mode": "SIGNAL_TO_SIGNAL",
            "badge_1": f"Mode: Signal-to-Signal",
            "badge_2": f"Trend: {st_dir_str}",
            "badge_3": f"Reversal Level: ${st_line_px:,.1f}",
            "badge_4": f"SL / Trailing: DISABLED",
            "headline": ai_json.get("headline", ""),
            "renko_structure": ai_json.get("renko_structure", ""),
            "extension_check": ai_json.get("extension_check", ""),
            "trail_box_html": f"<div class='trail-banner'>ℹ️ <b>सिग्नल-टू-सिग्नल नियम:</b> फिक्स SL और ट्रेलिंग पूरी तरह हटा दी गई है। ट्रेड केवल विपरीत सिग्नल आने पर ही बंद होगा।</div>"
        }
        ctx["lock_title"] = lock_title
        ctx["lock_cls"] = lock_cls
        ctx["lock_sub"] = lock_sub
        eng["report"] = ctx

    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 BACKGROUND WORKER (CORE RENKO FLIP EXECUTION)
# ============================================================================
def background_worker(eng, worker_id):
    last_used_brick_size = eng.get("fixed_brick_size", 270.0)

    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            ist_str = get_ist_time_str()
            px_res = fetch_live_btc_price()

            if isinstance(px_res, float) and px_res > 0:
                px = px_res
                eng["px"] = px
                eng["last_update"] = ist_str

                # Update live PnL if trade is active
                active_tr = eng.get("active_trade")
                if active_tr is not None:
                    move = (px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - px)
                    active_tr["live_pts"] = move
                    active_tr["peak_pts"] = max(active_tr["peak_pts"], move)

                # Check core Renko supertrend updates every 8 seconds or when brick size changes
                user_brick_sz = float(eng.get("fixed_brick_size", 270.0))
                brick_size_changed = abs(user_brick_sz - last_used_brick_size) >= 0.5

                if brick_size_changed or (now_ts - eng["last_kline_ts"] > 8):
                    rk_data = fetch_core_renko_supertrend(fixed_brick_size=user_brick_sz, rev_bricks=2.0)
                    if rk_data:
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data
                        last_used_brick_size = user_brick_sz

                        if prev_rk_trend == 0 or brick_size_changed:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                            if eng.get("active_trade") is None:
                                init_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                open_signal_trade_now(eng, init_dir, px, ist_str, f"🔥 Initial Sync Renko {init_dir}")
                        else:
                            # SIGNAL-TO-SIGNAL FLIP EXECUTION
                            if rk_data["st_trend"] != prev_rk_trend and rk_data["last_flip_bar_ts"] != eng.get("last_handled_flip_ts"):
                                eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                                new_dir_str = "BUY" if rk_data["st_trend"] == 1 else "SELL"

                                curr_tr = eng.get("active_trade")
                                if curr_tr is not None:
                                    close_signal_trade_at_price(
                                        eng, curr_tr, px, ist_str,
                                        f"RENKO OPPOSITE FLIP EXIT ({new_dir_str})"
                                    )

                                if eng.get("active_trade") is None:
                                    open_signal_trade_now(
                                        eng, new_dir_str, px, ist_str,
                                        f"🔥 Signal-to-Signal Flip {new_dir_str} {'▲' if new_dir_str=='BUY' else '▼'}"
                                    )
                                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                    eng["last_kline_ts"] = now_ts

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v23_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "fixed_brick_size": 270.0,
        "signal_history": [], "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0, "last_handled_flip_ts": 0,
        "renko": {
            "box_size": 270.0, "rev_bricks": 2.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "buy_dom_pct": 50.0, "ema21": 0.0, "ema_dist_bricks": 0.0, "rsi14": 50.0,
            "brick_events": []
        },
        "report": None,
        "available_models": [],
        "models_fetched": False,
        "selected_model": AUTO_MODEL_LABEL,
        "ai_json_view": {
            "mode": "INIT",
            "badge_1": "Mode: Signal-to-Signal",
            "badge_2": "Reversal Level: --",
            "badge_3": "Fixed Brick: $270",
            "badge_4": "SL / Trailing: OFF",
            "headline": "⏳ AI Renko Supertrend [Signal-to-Signal Mode] (Fixed Brick: 270) स्टार्ट हो रहा है...",
            "renko_structure": "रैंकों ब्रिक्स और सुपरट्रेंड स्कैन हो रहे हैं...",
            "extension_check": "21-EMA और RSI की गणना हो रही है...",
            "trail_box_html": ""
        },
        "ai_status": "🤖 Signal-to-Signal Renko",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v23_0()

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
c_mod, c_brk, c_act1, c_act2, c_act3 = st.columns([0.22, 0.16, 0.23, 0.23, 0.16])

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

with c_brk:
    new_brick_val = st.number_input(
        "🧱 फिक्स ब्रिक साइज:",
        min_value=10.0,
        max_value=2000.0,
        value=270.0,
        step=10.0,
        help="फिक्स ब्रिक साइज (डिफ़ॉल्ट: 270)",
        label_visibility="collapsed"
    )
    eng["fixed_brick_size"] = float(new_brick_val)

with c_act1:
    if st.button("🤖 AI स्टेटस अपडेट कराएं"):
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()

with c_act2:
    if st.button("🔥 चालू ट्रेंड में अभी एंट्री लें (Signal Mode)"):
        if eng.get("active_trade") is None and eng["px"] > 0 and eng["renko"].get("st_trend", 0) != 0:
            cur_dir = "BUY" if eng["renko"]["st_trend"] == 1 else "SELL"
            open_signal_trade_now(eng, cur_dir, eng["px"], get_ist_time_str(), f"🔥 Manual Sync Signal {cur_dir}")

with c_act3:
    sound_enabled = st.checkbox("🔊 साउंड (ON/OFF)", value=True)

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
        mod_label_short = "Pro-Priority Auto" if eng["selected_model"] == AUTO_MODEL_LABEL else eng["selected_model"]
        rk = eng.get("renko", {})
        act_tr = eng.get("active_trade")

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            is_act = "ACTIVE" in h["status"]
            sts_badge = "🟢 SIGNAL ACTIVE" if is_act else f"🏁 {h['status']}"

            hist_cards += f"""
            <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <b style='color:{h_col}; font-size:13.5px;'>{h["open_time"]} — {h["type"]} @ ${h["entry"]:,.1f}</b>
                    <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span><br>
                    <span style='color:#cbd5e1; font-size:12px;'>एंट्री स्रोत: {h["entry_reason"]}</span><br>
                    <span style='color:#38bdf8; font-size:11.8px;'>{h["exit_reason"]}</span>
                </div>
                <div style='text-align:right; min-width:105px;'>
                    <div style='font-size:15px; font-weight:900; color:{p_col};'>{h["live_pts"]:+.1f}p</div>
                    <div style='font-size:11px; color:#94a3b8;'>Peak: +{h["peak_pts"]:.1f}p</div>
                </div>
            </div>
            """
        if not hist_cards:
            hist_cards = "<div style='text-align:center; color:#64748b; padding-top:75px;'>अभी तक कोई ट्रेड शुरू नहीं हुआ है। अगले सिग्नल पर ट्रेड शुरू होगा।</div>"

        brick_cards = ""
        for idx, b in enumerate(rk.get("brick_events", []), 1):
            flip_tag = f"<span style='color:#facc15; font-weight:900; margin-left:6px;'>{b['flip']}</span>" if b["flip"] else ""
            brick_cards += f"""
            <div class='item-card {b["cls"]}'>
                <div style='display:flex; justify-content:space-between; font-weight:800;'>
                    <span>#{idx} 🕒 {b["time"]} | {b["dir"]} (Streak #{b["streak"]})</span>
                    <span style='color:#38bdf8;'>Box: ${b["brick_bot"]:,.0f}–${b["brick_top"]:,.0f}</span>
                </div>
                <div style='color:#cbd5e1; font-size:11.8px; margin-top:2px;'>
                    Reversal Level (stLevel): <b>${b["st_line"]:,.1f}</b> {flip_tag}
                </div>
            </div>
            """
        if not brick_cards:
            brick_cards = "<div style='text-align:center; color:#64748b; padding-top:40px;'>कन्फर्म्ड रैंकों ब्रिक्स लोड हो रही हैं...</div>"

        st_trend_col = "#4ade80" if rk.get("st_trend", 1) == 1 else "#f87171"
        st_trend_txt = "BULLISH (Buy) 🟢" if rk.get("st_trend", 1) == 1 else "BEARISH (Sell) 🔴"
        st_dist_pts = abs(eng["px"] - rk.get("st_line", eng["px"]))

        if act_tr:
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} सिग्नल-टू-सिग्नल ट्रेड चालू ({act_tr['type']})"
            banner_sub = f"एंट्री: ${act_tr['entry']:,.1f} | लाइव PnL: {act_tr['live_pts']:+.1f} Pts | विपरीत सिग्नल आने पर ही बंद होगा।"
            right_stat_label = "LIVE PNL"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            banner_title = f"⚪ सिग्नल-टू-सिग्नल मोड (Core Trend: {st_trend_txt})"
            banner_sub = f"Reversal Level: ${rk.get('st_line', 0.0):,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर) | Fixed Brick: ${rk.get('box_size', 270.0):.0f}"
            right_stat_label = "STATUS"
            right_stat_val = "STANDBY"
            right_stat_col = "#38bdf8"

        aj = eng["ai_json_view"]

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
                <span style='font-size:15px; font-weight:900; color:#c084fc;'>🧠 AI Renko Supertrend [Signal-to-Signal Mode]</span>
                <span style='font-size:11.5px; color:#4ade80; font-weight:bold;'>{eng["ai_status"]}</span>
            </div>
            <div>
                <span class='json-pill'>{aj["badge_1"]}</span>
                <span class='json-pill'>{aj["badge_2"]}</span>
                <span class='json-pill'>{aj["badge_3"]}</span>
                <span class='json-pill'>{aj["badge_4"]}</span>
            </div>
            <div style='font-size:14px; line-height:1.65; color:#f8fafc; margin-top:10px;'>
                <div>🎯 <b>मार्केट कमेंट्री:</b> {aj["headline"]}</div>
                <div style='margin-top:4px;'>🧱 <b>Core Renko संरचना:</b> {aj.get("renko_structure", "")}</div>
                <div style='margin-top:4px;'>📐 <b>मोमेंटम जांच:</b> {aj.get("extension_check", "")}</div>
            </div>
            {aj.get("trail_box_html", "")}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. Core Architecture Renko ST</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>Fixed Brick Size:</span><b style='color:#facc15;'>${rk.get("box_size", 270.0):.1f} Pts (Reversal: 2.0 Bricks)</b></div>
                <div class='stat-row'><span>Current Brick Box (Bot – Top):</span><b>${rk.get("brick_bot", 0.0):,.1f} — ${rk.get("brick_top", 0.0):,.1f} (Streak #{rk.get("brick_streak", 1)})</b></div>
                <div class='stat-row' style='border:none;'><span>Reversal Level (stLevel):</span><b><span style='color:{st_trend_col};'>${rk.get("st_line", 0.0):,.1f}</span> (दूरी: {st_dist_pts:.0f} Pts)</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>⚡ 2. मोमेंटम एवं इंडिकेटर्स</span>
                    <span style='color:#4ade80;'>Active</span>
                </div>
                <div class='stat-row'><span>21-EMA से दूरी:</span><b>{rk.get("ema_dist_bricks", 0.0):.2f} Bricks (EMA: ${rk.get("ema21", 0.0):,.0f})</b></div>
                <div class='stat-row'><span>14-RSI मोमेंटम:</span><b>RSI: {rk.get("rsi14", 50.0):.1f}</b></div>
                <div class='stat-row' style='border:none;'><span>3-Bar आर्डरफ्लो पावर:</span><b style='color:#4ade80;'>{rk.get("buy_dom_pct", 50.0):.0f}% Buy / {100.0 - rk.get("buy_dom_pct", 50.0):.0f}% Sell</b></div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V23.0 (PURE SIGNAL-TO-SIGNAL RENKO ST ENGINE)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🧱 Fixed Brick: <b style='color:#facc15;'>${rk.get('box_size', 270.0):.0f}</b> | Mode: <b>Signal-to-Signal (No SL / No Trailing)</b> | 🧠 AI: <b style='color:#c084fc;'>{mod_label_short}</b></div>
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
                            📜 Signal-to-Signal ट्रेड हिस्ट्री (Flip-to-Flip)
                        </div>
                        {hist_cards}
                    </div>
                </div>

                <div class='brick-panel'>
                    <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        🧱 ताज़ा कन्फर्म्ड रैंकों ब्रिक बॉक्स एवं फ्लिप लॉग
                    </div>
                    {brick_cards}
                </div>
            </div>
        </div>
        """), unsafe_allow_html=True)

    else:
        dashboard_slot.warning("⏳ 24x7 V23.0 (Pure Signal-to-Signal Renko ST Engine) स्टार्ट हो रहा है... कृपया 2 प्रतीक्षा करें।")

    time.sleep(1.5)

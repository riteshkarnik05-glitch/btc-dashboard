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

st.set_page_config(page_title="Pro Quant V24.0 - Signal-to-Signal Renko ST + Live Chart", layout="wide")

def clean_html(raw_html: str) -> str:
    """Strips leading spaces so Streamlit renders pure HTML/SVG inside a single slot without ghost boxes"""
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
.chart-box { background: #0c1220; border: 1px solid #334155; border-top: 3px solid #38bdf8; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
.ai-sharp-box { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid #a855f7; border-left: 5px solid #c084fc; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
.trail-banner { background: #091e3a; border: 1px solid #38bdf8; border-left: 4px solid #facc15; border-radius: 8px; padding: 10px 12px; margin-top: 10px; font-size: 13.2px; color: #f8fafc; }
.json-pill { background: #090d16; border: 1px solid #4c1d95; padding: 4px 10px; border-radius: 6px; font-size: 12px; color: #e9d5ff; font-weight: 700; display: inline-block; margin-right: 8px; margin-top: 6px; }
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 340px; overflow-y: auto; }
.brick-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 980px; overflow-y: auto; }
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
    else:
        notes = [(987, 0.12), (0, 0.03), (659, 0.12), (0, 0.03), (440, 0.22)]

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
# PURE SVG LIVE CHART GENERATOR (ZERO EXTERNAL DEPENDENCIES, ZERO BLINK)
# ============================================================================
def build_renko_svg_chart(rk: dict, live_px: float) -> str:
    """
    Renders a high-precision dark-mode SVG chart showing:
    - Close Price Line (Cyan)
    - Renko Supertrend Step-Line (Green when Bullish, Red when Bearish)
    - Current Brick Top & Brick Bottom dashed bands
    - BUY ▲ and SELL ▼ Flip Signal Markers with exact prices
    """
    pts = rk.get("chart_points", [])
    if len(pts) < 5:
        return "<div style='text-align:center; color:#64748b; padding:60px;'>📊 लाइव चार्ट डेटा तैयार हो रहा है...</div>"

    w, h = 920, 320
    pad_l, pad_r, pad_t, pad_b = 18, 82, 22, 28
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    all_y = []
    for p in pts:
        all_y.extend([p["close"], p["st"]])
    all_y.extend([live_px, rk.get("brick_top", live_px), rk.get("brick_bot", live_px), rk.get("st_line", live_px)])

    min_y = min(all_y)
    max_y = max(all_y)
    span_y = max(50.0, max_y - min_y)
    min_y -= span_y * 0.08
    max_y += span_y * 0.08
    span_y = max_y - min_y

    def to_x(idx, total):
        return pad_l + (idx / max(1, total - 1)) * plot_w

    def to_y(val):
        return pad_t + plot_h - ((val - min_y) / span_y) * plot_h

    n = len(pts)
    grid_svg = ""
    for i in range(5):
        gy = pad_t + (i / 4.0) * plot_h
        gval = max_y - (i / 4.0) * span_y
        grid_svg += f"<line x1='{pad_l}' y1='{gy:.1f}' x2='{w - pad_r}' y2='{gy:.1f}' stroke='#1e293b' stroke-dasharray='3,3' stroke-width='1'/>"
        grid_svg += f"<text x='{w - pad_r + 6}' y='{gy + 4:.1f}' fill='#94a3b8' font-size='11' font-family='monospace'>${gval:,.0f}</text>"

    # Time axis labels
    for idx_pos in [0, n // 3, (2 * n) // 3, n - 1]:
        if 0 <= idx_pos < n:
            tx = to_x(idx_pos, n)
            grid_svg += f"<text x='{tx:.1f}' y='{h - 6}' fill='#64748b' font-size='10.5' text-anchor='middle' font-family='sans-serif'>{pts[idx_pos]['time']}</text>"

    # Current Brick Top & Bottom horizontal guide lines
    b_top = rk.get("brick_top", live_px)
    b_bot = rk.get("brick_bot", live_px)
    y_btop = to_y(b_top)
    y_bbot = to_y(b_bot)
    brick_guides = (
        f"<line x1='{pad_l}' y1='{y_btop:.1f}' x2='{w - pad_r}' y2='{y_btop:.1f}' stroke='#14b8a6' stroke-dasharray='4,4' stroke-width='1' opacity='0.65'/>"
        f"<line x1='{pad_l}' y1='{y_bbot:.1f}' x2='{w - pad_r}' y2='{y_bbot:.1f}' stroke='#f97316' stroke-dasharray='4,4' stroke-width='1' opacity='0.65'/>"
    )

    # Build Supertrend step-line segments (colored by trend) & Price polyline
    price_coords = []
    st_segments = ""
    markers_svg = ""

    for i, p in enumerate(pts):
        x1 = to_x(i, n)
        yc = to_y(p["close"])
        yst = to_y(p["st"])
        price_coords.append(f"{x1:.1f},{yc:.1f}")

        if i > 0:
            x0 = to_x(i - 1, n)
            yst0 = to_y(pts[i - 1]["st"])
            seg_col = "#22c55e" if p["trend"] == 1 else "#ef4444"
            # Step-line (horizontal then vertical)
            st_segments += f"<path d='M {x0:.1f} {yst0:.1f} L {x1:.1f} {yst0:.1f} L {x1:.1f} {yst:.1f}' stroke='{seg_col}' stroke-width='2.6' fill='none'/>"

        if p.get("sig") == "BUY":
            markers_svg += (
                f"<polygon points='{x1:.1f},{yst - 2:.1f} {x1 - 7:.1f},{yst + 12:.1f} {x1 + 7:.1f},{yst + 12:.1f}' fill='#22c55e' stroke='#052e16' stroke-width='1.2'/>"
                f"<text x='{x1:.1f}' y='{yst + 24:.1f}' fill='#4ade80' font-size='10.5' font-weight='bold' text-anchor='middle'>BUY ${p['close']:,.0f}</text>"
            )
        elif p.get("sig") == "SELL":
            markers_svg += (
                f"<polygon points='{x1:.1f},{yst + 2:.1f} {x1 - 7:.1f},{yst - 12:.1f} {x1 + 7:.1f},{yst - 12:.1f}' fill='#ef4444' stroke='#450a0a' stroke-width='1.2'/>"
                f"<text x='{x1:.1f}' y='{yst - 16:.1f}' fill='#f87171' font-size='10.5' font-weight='bold' text-anchor='middle'>SELL ${p['close']:,.0f}</text>"
            )

    price_poly = f"<polyline points='{' '.join(price_coords)}' fill='none' stroke='#38bdf8' stroke-width='1.9'/>"

    # Right-edge live badges for Price & ST Level
    y_live = to_y(live_px)
    y_st_now = to_y(rk.get("st_line", live_px))
    st_now_col = "#22c55e" if rk.get("st_trend", 1) == 1 else "#ef4444"

    live_tags = (
        f"<circle cx='{to_x(n - 1, n):.1f}' cy='{y_live:.1f}' r='4' fill='#38bdf8'/>"
        f"<rect x='{w - pad_r + 2}' y='{y_st_now - 9:.1f}' width='76' height='18' rx='4' fill='{st_now_col}'/>"
        f"<text x='{w - pad_r + 40}' y='{y_st_now + 4:.1f}' fill='#090d16' font-size='10.5' font-weight='bold' text-anchor='middle'>ST ${rk.get('st_line', 0):,.0f}</text>"
        f"<rect x='{w - pad_r + 2}' y='{y_live - 9:.1f}' width='76' height='18' rx='4' fill='#38bdf8'/>"
        f"<text x='{w - pad_r + 40}' y='{y_live + 4:.1f}' fill='#090d16' font-size='10.5' font-weight='bold' text-anchor='middle'>Px ${live_px:,.0f}</text>"
    )

    return f"""
    <svg viewBox='0 0 {w} {h}' style='width:100%; height:auto; background:#090d16; border-radius:8px; display:block;'>
        {grid_svg}
        {brick_guides}
        {st_segments}
        {price_poly}
        {markers_svg}
        {live_tags}
    </svg>
    """

# ============================================================================
# CORE ARCHITECTURE: SYNTHETIC RENKO SUPERTREND (100% BUG-FREE)
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_live_btc_price():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "allMids"}, timeout=2.0)
        if r.status_code == 200:
            mids = r.json()
            if isinstance(mids, dict) and "BTC" in mids:
                return float(mids["BTC"])
    except Exception:
        pass
    try:
        r2 = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2.0)
        if r2.status_code == 200:
            levels = r2.json().get("levels", [])
            if len(levels) >= 2 and levels[0] and levels[1]:
                return (float(levels[0][0]["px"]) + float(levels[1][0]["px"])) / 2.0
    except Exception as e:
        return str(e)
    return None

def fetch_core_renko_supertrend(fixed_brick_size: float = 270.0, rev_bricks: float = 2.0):
    """
    Exact, verified Python implementation of 'AI Renko Supertrend [Core Architecture]':
    - Fixed Brick Size (default 270.0) & Reversal Bricks (default 2.0).
    - 100% Non-Repainting on confirmed closed 1m candles.
    - Also extracts historical flip-to-flip trades and chart points for live visual tracing.
    """
    try:
        brick_size = max(10.0, float(fixed_brick_size))
        rev_mult = max(0.5, float(rev_bricks))
        now_ms = int(time.time() * 1000)

        # Fetch last 1440 mins (24 Hours) of 1m candles so bricks & flips are well-established
        start_1m = now_ms - (1440 * 60 * 1000)
        r_1m = requests.post(
            HYPERLIQUID_URL,
            json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_1m, "endTime": now_ms}},
            timeout=4.0
        )
        if r_1m.status_code != 200 or len(r_1m.json()) < 30:
            return None

        # Strictly use confirmed closed candles (waitClose = true)
        closed_bars = r_1m.json()[:-1]
        closes = [float(b["c"]) for b in closed_bars]
        highs = [float(b["h"]) for b in closed_bars]
        lows = [float(b["l"]) for b in closed_bars]
        opens = [float(b["o"]) for b in closed_bars]
        vols = [float(b["v"]) for b in closed_bars]
        bar_times = [int(b["t"]) for b in closed_bars]

        # 21-EMA & 14-RSI for momentum display
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

        # ====================================================================
        # EXACT PINE SCRIPT STEP 3: SYNTHETIC RENKO SUPERTREND ENGINE
        # ====================================================================
        rev_dist = rev_mult * brick_size
        snapped = math.floor(closes[0] / brick_size) * brick_size
        brick_bot = snapped
        brick_top = snapped + brick_size
        trend = 1
        st_level = brick_top - rev_dist
        brick_streak = 1

        buy_signal = False
        sell_signal = False
        last_flip_bar_ts = bar_times[0]
        last_flip_price = closes[0]
        last_flip_time_str = (datetime.utcfromtimestamp(bar_times[0] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

        brick_events = []
        flip_trades = []
        chart_points = []

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

                raw_support = brick_top - rev_dist
                st_level = max(raw_support, prev_st_level)

                if c < st_level:
                    trend = -1
                    down_steps = max(1, int(math.floor((brick_top - c) / brick_size)))
                    brick_bot = brick_top - (down_steps * brick_size)
                    brick_top = brick_bot + brick_size
                    st_level = brick_bot + rev_dist
                    brick_streak = down_steps
                    flipped_now = True

            elif trend == -1:
                if c <= brick_bot - brick_size:
                    steps = int(math.floor((brick_bot - c) / brick_size))
                    brick_bot = brick_bot - (steps * brick_size)
                    brick_top = brick_bot + brick_size
                    brick_streak += steps
                    stepped_bricks = steps

                raw_res = brick_bot + rev_dist
                st_level = min(raw_res, prev_st_level)

                if c > st_level:
                    trend = 1
                    up_steps = max(1, int(math.floor((c - brick_bot) / brick_size)))
                    brick_top = brick_bot + (up_steps * brick_size)
                    brick_bot = brick_top - brick_size
                    st_level = brick_top - rev_dist
                    brick_streak = up_steps
                    flipped_now = True

            bar_buy_sig = (trend == 1 and prev_trend == -1)
            bar_sell_sig = (trend == -1 and prev_trend == 1)
            b_ist_short = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
            b_ist_full = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

            if bar_buy_sig or bar_sell_sig:
                last_flip_bar_ts = bar_times[i]
                last_flip_price = c
                last_flip_time_str = b_ist_full
                sig_dir = "BUY" if bar_buy_sig else "SELL"

                # Close previous flip trade in historical tracker
                if flip_trades:
                    prev_tr = flip_trades[-1]
                    move_pts = (c - prev_tr["entry"]) if prev_tr["type"] == "BUY" else (prev_tr["entry"] - c)
                    prev_tr["live_pts"] = round(move_pts, 1)
                    prev_tr["peak_pts"] = round(max(prev_tr["peak_pts"], move_pts), 1)
                    prev_tr["close_time"] = b_ist_full
                    prev_tr["status"] = f"FLIPPED TO {sig_dir} @ ${c:,.1f} ({b_ist_short})"
                    prev_tr["exit_reason"] = f"विपरीत {sig_dir} सिग्नल आने पर ${c:,.1f} पर बंद हुआ (PnL: {move_pts:+.1f} Pts)"

                flip_trades.append({
                    "open_ts": bar_times[i] / 1000.0,
                    "open_time": b_ist_full,
                    "close_time": "",
                    "type": sig_dir,
                    "entry": round(c, 1),
                    "live_pts": 0.0,
                    "peak_pts": 0.0,
                    "status": "ACTIVE (SIGNAL-TO-SIGNAL)",
                    "entry_reason": f"🔥 Core Renko ST {sig_dir} Signal (Brick: ${brick_size:.0f} | ST: ${st_level:,.1f})",
                    "exit_reason": f"ट्रेड चालू है — विपरीत सिग्नल (Reversal Level: ${st_level:,.1f}) टूटने पर ही बंद होगा"
                })
            elif flip_trades:
                # Update peak excursion of current running trade
                cur_t = flip_trades[-1]
                fav_px = highs[i] if cur_t["type"] == "BUY" else lows[i]
                cur_fav = (fav_px - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - fav_px)
                cur_t["peak_pts"] = round(max(cur_t["peak_pts"], cur_fav), 1)

            if stepped_bricks > 0 or flipped_now:
                brick_events.append({
                    "time": b_ist_short,
                    "dir": "BULLISH 🟢" if trend == 1 else "BEARISH 🔴",
                    "cls": "ic-bull" if trend == 1 else "ic-bear",
                    "brick_top": round(brick_top, 1),
                    "brick_bot": round(brick_bot, 1),
                    "streak": brick_streak,
                    "st_line": round(st_level, 1),
                    "flip": f"🔥 BUY @ ${c:,.0f} ▲" if bar_buy_sig else (f"🔥 SELL @ ${c:,.0f} ▼" if bar_sell_sig else "")
                })

            # Collect last 240 minutes (4 hours) every 1-2 mins + all flip bars for crisp SVG chart
            if i >= len(closes) - 240 or bar_buy_sig or bar_sell_sig:
                chart_points.append({
                    "time": b_ist_short,
                    "close": round(c, 1),
                    "st": round(st_level, 1),
                    "trend": trend,
                    "sig": "BUY" if bar_buy_sig else ("SELL" if bar_sell_sig else None)
                })

            if i == len(closes) - 1:
                buy_signal = bar_buy_sig
                sell_signal = bar_sell_sig

        last_c = closes[-1]
        r_close_now = brick_top if trend == 1 else brick_bot
        ema_dist_bricks = abs(last_c - ema21) / max(1.0, brick_size)

        return {
            "box_size": round(brick_size, 1),
            "rev_bricks": round(rev_mult, 1),
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
            "last_flip_price": round(last_flip_price, 1),
            "last_flip_time_str": last_flip_time_str,
            "buy_dom_pct": round(buy_dom_pct, 1),
            "ema21": round(ema21, 1),
            "ema_dist_bricks": round(ema_dist_bricks, 2),
            "rsi14": round(rsi14, 1),
            "last_confirmed_close": round(last_c, 1),
            "brick_events": list(reversed(brick_events[-20:])),
            "flip_trades": list(reversed(flip_trades[-20:])),
            "chart_points": chart_points[-180:]
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# SIGNAL-TO-SIGNAL TRADE EXECUTION (NO FIXED SL / NO TRAILING)
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
        "entry": round(entry_px, 1),
        "live_pts": 0.0,
        "peak_pts": 0.0,
        "status": "ACTIVE (SIGNAL-TO-SIGNAL)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | Reversal ST: ${st_line_val:,.1f})",
        "exit_reason": f"ट्रेड चालू है — विपरीत सिग्नल (Reversal Level: ${st_line_val:,.1f}) टूटने पर ही बंद होगा"
    }
    eng["active_trade"] = new_trade
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

def close_signal_trade_at_price(eng, active_tr, exit_px: float, ist_str: str, reason_title: str):
    move = (exit_px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - exit_px)
    active_tr["live_pts"] = round(move, 1)
    active_tr["peak_pts"] = round(max(active_tr["peak_pts"], move), 1)
    active_tr["close_time"] = ist_str
    active_tr["status"] = f"{reason_title} @ ${exit_px:,.1f} ({ist_str})"
    active_tr["exit_reason"] = f"विपरीत सिग्नल मिलने पर ${exit_px:,.1f} पर बंद हुआ (PnL: {move:+.1f} Pts)"

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

# ============================================================================
# AI MARKET COMMENTARY BRAIN (SIGNAL-TO-SIGNAL MODE)
# ============================================================================
def parse_ai_json_safely(raw_text: str):
    try:
        cleaned = re.sub(r"```json|```", "", raw_text).strip()
        s = cleaned.find("{")
        e = cleaned.rfind("}")
        if s != -1 and e != -1:
            return json.loads(cleaned[s:e+1])
    except Exception:
        pass
    return None

def signal_commentary_backup_brain(ctx, active_trade):
    px = ctx["px"]
    rk = ctx["renko"]
    st_line = rk.get("st_line", px)
    box_sz = rk.get("box_size", 270.0)
    rev_b = rk.get("rev_bricks", 2.0)
    st_dir = "BUY (Bullish) 🟢" if rk.get("st_trend", 1) == 1 else "SELL (Bearish) 🔴"
    dist_to_flip = abs(px - st_line)
    next_brick_px = (rk.get("brick_top", px) + box_sz) if rk.get("st_trend", 1) == 1 else (rk.get("brick_bot", px) - box_sz)

    if active_trade is None:
        return {
            "headline": f"सिग्नल-टू-सिग्नल मोड: अगला फ्लिप तब होगा जब कन्फर्म्ड क्लोज Reversal Level (${st_line:,.0f}) को पार करेगा (अभी {dist_to_flip:.0f} Pts दूर)।",
            "renko_structure": f"Fixed Brick: ${box_sz:.0f} (Rev: {rev_b:.1f}x = ${box_sz*rev_b:.0f}p) | अगली ब्रिक स्टेप: ${next_brick_px:,.0f} पर।",
            "extension_check": f"21-EMA: ${rk.get('ema21', 0):,.0f} | 14-RSI: {rk.get('rsi14', 50):.1f} | 3-Bar Power: {rk.get('buy_dom_pct', 50):.0f}% Buy।"
        }
    else:
        t_type = active_trade["type"]
        live_pts = active_trade["live_pts"]
        opp_dir = "SELL ▼" if t_type == "BUY" else "BUY ▲"
        return {
            "headline": f"✅ {t_type} ट्रेड चालू ({live_pts:+.1f}p) — विपरीत {opp_dir} सिग्नल केवल तभी आएगा जब क्लोज प्राइस ${st_line:,.1f} को तोड़ेगा (अभी {dist_to_flip:.0f} Pts दूर)।",
            "renko_structure": f"Brick Box: ${rk.get('brick_bot', 0):,.0f}–${rk.get('brick_top', 0):,.0f} (Streak #{rk.get('brick_streak', 1)}) | अगली ब्रिक ${next_brick_px:,.0f} पर बनेगी जिससे ST Line आगे खिसकेगी।",
            "extension_check": f"21-EMA से दूरी: {rk.get('ema_dist_bricks', 0):.2f} Bricks | RSI: {rk.get('rsi14', 50):.1f} | 3-Bar Power: {rk.get('buy_dom_pct', 50):.0f}% Buy।"
        }

def call_gemini_commentary_engine(api_key, ctx, active_trade, selected_model, available_models):
    if active_trade is None:
        return signal_commentary_backup_brain(ctx, None), "🟢 Signal-to-Signal Watcher"

    px = ctx["px"]
    rk = ctx["renko"]
    t_type = active_trade["type"]
    live_pts = active_trade["live_pts"]
    st_line = rk.get("st_line", px)
    dist_st = abs(px - st_line)

    prompt = f"""
You are a Quantitative Renko Trading Assistant monitoring an ACTIVE BTCUSDT trade in Pure Signal-to-Signal mode ('AI Renko Supertrend [Core Architecture]').
There is no fixed SL; the Renko Supertrend Reversal Level (`stLevel` = ${st_line:,.1f}) acts as the exact flip/exit level on candle close.

ACTIVE TRADE DATA:
- Active Direction: {t_type} | Entry Price: ${active_trade['entry']:,.1f} | Current Price: ${px:,.1f} | Live PnL: {live_pts:+.1f} pts
- Fixed Brick Size: ${rk.get('box_size', 270):.0f} | Reversal Factor: {rk.get('rev_bricks', 2.0):.1f} Bricks
- Current Brick Box: ${rk.get('brick_bot', 0):,.1f} to ${rk.get('brick_top', 0):,.1f} (Streak #{rk.get('brick_streak', 1)})
- Reversal Level (`stLevel`): ${st_line:,.1f} (Current distance from price: {dist_st:.1f} pts)
- 21-EMA: ${rk.get('ema21', 0):,.1f} | 14-RSI: {rk.get('rsi14', 50):.1f} | 3-Bar Dominance: {rk.get('buy_dom_pct', 50):.1f}% Buy

Return ONLY valid JSON with sharp, clear Hindi explanations:
{{
  "headline": "Sharp 1-line Hindi summary of current trade status and how far price is from flipping at stLevel (${st_line:,.0f})",
  "renko_structure": "Sharp 1-line Hindi explanation of current Brick Box and at what price the next brick will form to move stLevel",
  "extension_check": "Sharp 1-line Hindi momentum check (RSI, EMA stretch, and buyer/seller power)"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
    }

    pro_first_priority = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    sorted_avail = sorted(available_models or [], key=score_model_priority)
    combined_auto = []
    for m in sorted_avail + pro_first_priority:
        if m not in combined_auto:
            combined_auto.append(m)

    models_queue = [selected_model] + [m for m in combined_auto if m != selected_model] if (selected_model and selected_model != AUTO_MODEL_LABEL) else combined_auto

    for mod in models_queue:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=9.0)
            if res.status_code == 200:
                parsed = parse_ai_json_safely(res.json()['candidates'][0]['content']['parts'][0]['text'].strip())
                if parsed:
                    return parsed, f"🟢 AI Commentary ({mod})"
        except Exception:
            continue

    return signal_commentary_backup_brain(ctx, active_trade), "⚡ Signal-to-Signal Brain"

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

        if api_key and eng.get("active_trade") is not None:
            ai_json, status_str = call_gemini_commentary_engine(api_key, ctx, eng.get("active_trade"), selected_mod, eng.get("available_models"))
        else:
            ai_json, status_str = signal_commentary_backup_brain(ctx, eng.get("active_trade")), "🟢 Signal-to-Signal Engine"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()
        eng["ai_json_view"].update({
            "headline": ai_json.get("headline", ""),
            "renko_structure": ai_json.get("renko_structure", ""),
            "extension_check": ai_json.get("extension_check", "")
        })
    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 BACKGROUND WORKER (SIGNAL-TO-SIGNAL + CHART TRACE SYNC)
# ============================================================================
def background_worker(eng, worker_id):
    last_used_brick_size = eng.get("fixed_brick_size", 270.0)
    last_used_rev = eng.get("rev_bricks", 2.0)

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

                user_brick_sz = float(eng.get("fixed_brick_size", 270.0))
                user_rev = float(eng.get("rev_bricks", 2.0))
                settings_changed = (abs(user_brick_sz - last_used_brick_size) >= 0.5) or (abs(user_rev - last_used_rev) >= 0.1)

                # Update Renko structure every 6 seconds or immediately when user changes Brick Size / Reversal Factor
                if settings_changed or (now_ts - eng["last_kline_ts"] > 6):
                    rk_data = fetch_core_renko_supertrend(fixed_brick_size=user_brick_sz, rev_bricks=user_rev)
                    if rk_data and "error" not in rk_data:
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data
                        last_used_brick_size = user_brick_sz
                        last_used_rev = user_rev

                        # First boot OR user changed Brick/Reversal settings -> Sync trade history directly with chart signals!
                        if prev_rk_trend == 0 or settings_changed:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                            if rk_data.get("flip_trades"):
                                eng["signal_history"] = rk_data["flip_trades"]
                                eng["active_trade"] = eng["signal_history"][0]
                            else:
                                cur_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                open_signal_trade_now(eng, cur_dir, rk_data["last_flip_price"], rk_data["last_flip_time_str"], f"🔥 Chart Sync {cur_dir}")
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()
                        else:
                            # Live Signal-to-Signal Flip Detection on confirmed close
                            if rk_data["st_trend"] != prev_rk_trend and rk_data["last_flip_bar_ts"] != eng.get("last_handled_flip_ts"):
                                eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                                new_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                flip_px = rk_data["last_confirmed_close"]

                                if eng.get("active_trade") is not None:
                                    close_signal_trade_at_price(eng, eng["active_trade"], flip_px, ist_str, f"FLIPPED TO {new_dir}")

                                open_signal_trade_now(eng, new_dir, flip_px, ist_str, f"🔥 Live Renko ST Flip {new_dir} {'▲' if new_dir=='BUY' else '▼'}")
                                threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                    elif rk_data and "error" in rk_data:
                        eng["last_err"] = rk_data["error"]

                    eng["last_kline_ts"] = now_ts

                # Update live PnL of active trade on every 1-second tick
                act_tr = eng.get("active_trade")
                if act_tr is not None:
                    rk_now = eng.get("renko", {})
                    st_line_now = rk_now.get("st_line", 0.0)
                    dist_now = abs(px - st_line_now) if st_line_now > 0 else 0.0
                    move = (px - act_tr["entry"]) if act_tr["type"] == "BUY" else (act_tr["entry"] - px)
                    act_tr["live_pts"] = round(move, 1)
                    act_tr["peak_pts"] = round(max(act_tr["peak_pts"], move), 1)
                    act_tr["exit_reason"] = f"चालू है — Reversal Level (${st_line_now:,.1f}) से अभी {dist_now:.0f} Pts दूर है (क्लोज नीचे/ऊपर होने पर फ्लिप होगा)"

                if now_ts - eng["last_report_ts"] >= 180 and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v24_0():
    wid = int(time.time() * 1000)
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "fixed_brick_size": 270.0, "rev_bricks": 2.0,
        "signal_history": [], "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0, "last_handled_flip_ts": 0,
        "renko": {
            "box_size": 270.0, "rev_bricks": 2.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "buy_dom_pct": 50.0, "ema21": 0.0, "ema_dist_bricks": 0.0, "rsi14": 50.0,
            "brick_events": [], "chart_points": []
        },
        "available_models": [], "models_fetched": False, "selected_model": AUTO_MODEL_LABEL,
        "ai_json_view": {
            "headline": "⏳ Core Renko Supertrend चार्ट और सिग्नल ट्रेस किए जा रहे हैं...",
            "renko_structure": "फिक्स ब्रिक बॉक्स और Reversal Level लोड हो रहा है...",
            "extension_check": "21-EMA और RSI की गणना हो रही है..."
        },
        "ai_status": "🟢 Signal-to-Signal Engine",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v24_0()

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
# TOP CONTROL BAR (BRICK SIZE, REVERSAL FACTOR, AI MODEL & MANUAL FLIP)
# ============================================================================
c_mod, c_brk, c_rev, c_act1, c_act2 = st.columns([0.24, 0.18, 0.18, 0.24, 0.16])

with c_mod:
    dropdown_options = [AUTO_MODEL_LABEL] + eng.get("available_models", [])
    curr_sel = eng.get("selected_model", AUTO_MODEL_LABEL)
    sel_idx = dropdown_options.index(curr_sel) if curr_sel in dropdown_options else 0
    eng["selected_model"] = st.selectbox("🧠 AI मॉडल:", options=dropdown_options, index=sel_idx, label_visibility="collapsed")

with c_brk:
    eng["fixed_brick_size"] = float(st.number_input(
        "🧱 ब्रिक साइज (Default 270):",
        min_value=10.0, max_value=2000.0,
        value=float(eng.get("fixed_brick_size", 270.0)),
        step=10.0,
        help="फिक्स ब्रिक साइज (जैसे 270, 150, 100)",
        label_visibility="collapsed"
    ))

with c_rev:
    eng["rev_bricks"] = float(st.number_input(
        "🔄 रिवर्सल ब्रिक्स (Default 2.0):",
        min_value=0.5, max_value=5.0,
        value=float(eng.get("rev_bricks", 2.0)),
        step=0.5,
        help="रिवर्सल ब्रिक फैक्टर (Standard = 2.0 Bricks, Fast = 1.0 Brick)",
        label_visibility="collapsed"
    ))

with c_act1:
    if st.button("🤖 AI कमेंट्री / चार्ट रिफ्रेश करें"):
        eng["last_kline_ts"] = 0.0
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()

with c_act2:
    sound_enabled = st.checkbox("🔊 साउंड अलर्ट", value=True)

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

    if eng["px"] > 0 and eng["renko"].get("st_line", 0.0) > 0:
        rk = eng.get("renko", {})
        act_tr = eng.get("active_trade")
        st_line_px = rk.get("st_line", eng["px"])
        box_sz = rk.get("box_size", 270.0)
        rev_b = rk.get("rev_bricks", 2.0)
        st_dist_pts = abs(eng["px"] - st_line_px)
        next_step_px = (rk.get("brick_top", eng["px"]) + box_sz) if rk.get("st_trend", 1) == 1 else (rk.get("brick_bot", eng["px"]) - box_sz)
        pts_to_next_brick = abs(next_step_px - eng["px"])

        st_trend_col = "#4ade80" if rk.get("st_trend", 1) == 1 else "#f87171"
        st_trend_txt = "BULLISH (BUY ▲) 🟢" if rk.get("st_trend", 1) == 1 else "BEARISH (SELL ▼) 🔴"

        if act_tr:
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            opp_sig = "SELL ▼" if act_tr["type"] == "BUY" else "BUY ▲"
            banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} सिग्नल-टू-सिग्नल {act_tr['type']} ट्रेड चालू (Entry: ${act_tr['entry']:,.1f} @ {act_tr['open_time']})"
            banner_sub = (
                f"विपरीत सिग्नल ({opp_sig}) लेवल: <b>${st_line_px:,.1f}</b> (अभी लाइव प्राइस से <b>{st_dist_pts:.0f} Pts दूर</b>) | "
                f"अगली ब्रिक (${next_step_px:,.0f}) बनने में {pts_to_next_brick:.0f} Pts बाकी"
            )
            right_stat_label = "LIVE SIGNAL PNL"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            banner_title = f"⚪ सिग्नल-टू-सिग्नल मोड ({st_trend_txt})"
            banner_sub = f"Reversal Level (stLevel): ${st_line_px:,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर)"
            right_stat_label = "DISTANCE TO FLIP"
            right_stat_val = f"{st_dist_pts:.0f} Pts"
            right_stat_col = "#38bdf8"

        # Generate Pure SVG Chart (Zero External Dependencies)
        svg_chart_html = build_renko_svg_chart(rk, eng["px"])

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            sts_badge = "🟢 RUNNING (SIGNAL-TO-SIGNAL)" if "ACTIVE" in h["status"] else f"🏁 {h['status']}"
            hist_cards += f"""
            <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <b style='color:{h_col}; font-size:13.5px;'>{h['open_time']} — {h['type']} @ ${h['entry']:,.1f}</b>
                    <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span><br>
                    <span style='color:#cbd5e1; font-size:12px;'>{h['entry_reason']}</span><br>
                    <span style='color:#38bdf8; font-size:11.8px;'>🛡️ {h['exit_reason']}</span>
                </div>
                <div style='text-align:right; min-width:105px;'>
                    <div style='font-size:15px; font-weight:900; color:{p_col};'>{h['live_pts']:+.1f}p</div>
                    <div style='font-size:11px; color:#94a3b8;'>Peak: +{h['peak_pts']:.1f}p</div>
                </div>
            </div>
            """

        brick_cards = ""
        for idx, b in enumerate(rk.get("brick_events", []), 1):
            flip_tag = f"<span style='color:#facc15; font-weight:900; margin-left:6px;'>{b['flip']}</span>" if b["flip"] else ""
            brick_cards += f"""
            <div class='item-card {b['cls']}'>
                <div style='display:flex; justify-content:space-between; font-weight:800;'>
                    <span>#{idx} 🕒 {b['time']} | {b['dir']} (#{b['streak']})</span>
                    <span style='color:#38bdf8;'>Box: ${b['brick_bot']:,.0f}–${b['brick_top']:,.0f}</span>
                </div>
                <div style='color:#cbd5e1; font-size:11.8px; margin-top:2px;'>
                    Reversal Level (stLevel): <b>${b['st_line']:,.1f}</b> {flip_tag}
                </div>
            </div>
            """

        aj = eng["ai_json_view"]

        left_body = f"""
        <div class='lock-banner {banner_cls}'>
            <div>
                <div style='font-size:18px; font-weight:900;'>{banner_title}</div>
                <div style='font-size:12.5px; margin-top:3px; opacity:0.95;'>{banner_sub}</div>
            </div>
            <div style='text-align:right; min-width:145px;'>
                <div style='font-size:11px; text-transform:uppercase; opacity:0.85;'>{right_stat_label}</div>
                <div style='font-size:23px; font-weight:900; color:{right_stat_col};'>{right_stat_val}</div>
                <div style='font-size:11px; opacity:0.8;'>● {eng["last_update"]}</div>
            </div>
        </div>

        <div class='chart-box'>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;'>
                <span style='font-size:14px; font-weight:900; color:#38bdf8;'>
                    📈 LIVE AI-RENKO SUPERTREND SIGNAL TRACE CHART (Brick: ${box_sz:.0f} | Rev: {rev_b:.1f}x = ${box_sz*rev_b:.0f}p)
                </span>
                <span style='font-size:12px; color:#cbd5e1;'>
                    <b style='color:#38bdf8;'>━ Price (${eng['px']:,.0f})</b> &nbsp;|&nbsp;
                    <b style='color:{st_trend_col};'>━ Reversal ST (${st_line_px:,.0f})</b> &nbsp;|&nbsp;
                    <span style='color:#14b8a6;'>-- Brick Top (${rk.get('brick_top',0):,.0f})</span> &nbsp;|&nbsp;
                    <span style='color:#f97316;'>-- Brick Bot (${rk.get('brick_bot',0):,.0f})</span>
                </span>
            </div>
            {svg_chart_html}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. सिग्नल क्यों / कब आएगा? (Live Distance Trace)</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>विपरीत सिग्नल लेवल (Reversal stLevel):</span><b><span style='color:{st_trend_col};'>${st_line_px:,.1f}</span> (प्राइस से {st_dist_pts:.0f} Pts दूर)</b></div>
                <div class='stat-row'><span>चालू ब्रिक बॉक्स (Bot – Top):</span><b>${rk.get("brick_bot", 0.0):,.1f} — ${rk.get("brick_top", 0.0):,.1f} (Streak #{rk.get("brick_streak", 1)})</b></div>
                <div class='stat-row'><span>अगली ब्रिक बनने का लेवल (ST खिसकेगा):</span><b style='color:#facc15;'>${next_step_px:,.1f} ({pts_to_next_brick:.0f} Pts दूर)</b></div>
                <div class='stat-row' style='border:none;'><span>ब्रिक एवं रिवर्सल सेटिंग:</span><b>Brick: ${box_sz:.0f} × Rev {rev_b:.1f} = ${box_sz*rev_b:.0f}p Gap</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>🧠 2. AI लाइव स्ट्रक्चर एवं मोमेंटम नोट</span>
                    <span style='color:#4ade80;'>{eng["ai_status"]}</span>
                </div>
                <div style='font-size:12.8px; line-height:1.55; color:#f8fafc;'>
                    <div>🎯 <b>स्टेटस:</b> {aj["headline"]}</div>
                    <div style='margin-top:4px; color:#cbd5e1;'>🧱 <b>रैंकों गणित:</b> {aj.get("renko_structure", "")}</div>
                    <div style='margin-top:4px; color:#38bdf8;'>📐 <b>मोमेंटम:</b> {aj.get("extension_check", "")}</div>
                </div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V24.0 (SIGNAL-TO-SIGNAL RENKO ST + LIVE SVG CHART)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🧱 Fixed Brick: <b style='color:#facc15;'>${box_sz:.0f}</b> | Reversal: <b>{rev_b:.1f} Bricks (${box_sz*rev_b:.0f}p)</b> | Reversal ST Level: <b style='color:{st_trend_col};'>${st_line_px:,.1f} ({st_dist_pts:.0f}p away)</b></div>
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
                            📜 Signal-to-Signal ट्रेड हिस्ट्री (Chart Synced Flip-to-Flip)
                        </div>
                        {hist_cards}
                    </div>
                </div>

                <div class='brick-panel'>
                    <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        🧱 कन्फर्म्ड रैंकों ब्रिक स्टेप्स एवं सिग्नल लॉग
                    </div>
                    {brick_cards}
                </div>
            </div>
        </div>
        """), unsafe_allow_html=True)

    else:
        err_msg = f" ({eng['last_err']})" if eng.get("last_err") else ""
        dashboard_slot.warning(f"⏳ 24x7 V24.0 (Signal-to-Signal + Live SVG Chart) डेटा सिंक कर रहा है... कृपया 2 सेकंड प्रतीक्षा करें।{err_msg}")

    time.sleep(1.5)

import streamlit as st
import requests
import time
import threading
import json
from datetime import datetime, timedelta
import math
import io
import wave
import struct
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="AI-Renko Pro & Pre-Spike Terminal", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; }
.block-container { padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
.t-grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
@media (min-width: 960px) { .t-grid { grid-template-columns: 1.15fr 0.85fr; } }

/* रीसेट बटन की कस्टम स्टाइलिंग */
div.stButton > button {
    background-color: #1e293b !important;
    color: #facc15 !important;
    border: 1px solid #eab308 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    padding: 6px 12px !important;
    width: 100% !important;
}
div.stButton > button:hover {
    background-color: #eab308 !important;
    color: #0f172a !important;
}
</style>""", unsafe_allow_html=True)

# ============================================================================
# IN-MEMORY WAV BEEP GENERATOR (FOR ZERO-DEPENDENCY AUTOPLAY AUDIO)
# ============================================================================
def build_beep_wav_b64(freqs, tone_ms=140, pause_ms=45):
    sample_rate = 22050
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for f in freqs:
            n_tone = int(sample_rate * (tone_ms / 1000.0))
            for i in range(n_tone):
                env = min(1.0, i / 150.0, (n_tone - i) / 150.0)
                val = int(26000.0 * env * math.sin(2.0 * math.pi * f * (i / float(sample_rate))))
                frames.extend(struct.pack("<h", val))
            n_pause = int(sample_rate * (pause_ms / 1000.0))
            frames.extend(b"\x00\x00" * n_pause)
        wf.writeframes(bytes(frames))
    return base64.b64encode(buf.getvalue()).decode("ascii")

BUY_BEEP_B64  = build_beep_wav_b64([880, 1175, 1568, 1568])   # Ascending Bullish Siren
SELL_BEEP_B64 = build_beep_wav_b64([987, 740, 523, 523])      # Descending Bearish Alarm

# ============================================================================
# 1-MINUTE FIXED-POINT PARAMETERS (10 LOT: 7Q TP1 @ 350pts + 3Q TRAIL, SL 290pts)
# ============================================================================
TOTAL_QTY            = 10
TP1_BOOK_QTY         = 7      # TP1 (350 pts / ~₹300) पर 7 लॉट तुरंत बुक होंगे
RUNNER_QTY           = 3      # बचे हुए 3 लॉट प्रॉफिट-लॉक और ट्रेलिंग रनर के लिए

# ---- नया: फिक्स्ड पॉइंट्स मोड (1m चार्ट के हिसाब से) ----
USE_FIXED_POINTS     = True   # True = नीचे दिए पॉइंट्स इस्तेमाल होंगे | False = पुराना ब्रिक-आधारित सिस्टम
TP1_POINTS           = 350.0  # ~₹300 टारगेट (7 लॉट बुक)
SL_POINTS            = 290.0  # ~₹250 स्टॉप-लॉस (10 लॉट)
RUNNER_LOCK_POINTS   = 60.0   # TP1 हिट होते ही 3 लॉट का SL एंट्री से +60 pts पर लॉक
MID_LOCK_POINTS      = 520.0  # 520 pts छूते ही 3 लॉट का SL सीधा TP1 (350) पर आ जाएगा
TP2_POINTS           = 600.0  # इसके बाद 3 लॉट की ट्रेलिंग शुरू

USE_TRAIL_BEYOND_TP2 = True
TRAIL_METHOD         = "Smart Brick + Peak Ratchet (Best)"
TRAIL_LOCK_BRICKS    = 0.8
USE_STREAK_FILTER    = True
MAX_BRICK_STREAK     = 2      # केवल शुरुआती Brick #1 और #2 पर ही एंट्री
USE_STRETCH_FILTER   = True
MAX_EMA_DIST_BRICKS  = 1.1    # ओवर-स्ट्रेच फिल्टर

USE_AUTO_BOX         = True
ATR_PERIOD           = 5
RANGE_DIVISOR        = 15.0   # Medium Brick Size
MANUAL_BOX           = 120.0

ST_FACTOR            = 3.0
USE_GAUSSIAN         = True
GAUSS_PERIOD         = 20
SIG_MODE             = "Supertrend + Brick-Step Re-Entry (Best)"
MIN_VOL_DOM          = 55.0

# पुराने ब्रिक-आधारित पैरामीटर (USE_FIXED_POINTS = False होने पर काम आएंगे)
TP1_BRICKS           = 0.85
RUNNER_LOCK_BRICKS   = 0.35
MID_LOCK_BRICKS      = 1.25
TP2_BRICKS           = 2.20
SL_BRICKS            = 1.15
MAX_SL_LOSS_BRICKS   = 0.90
ANTI_WICK_SL         = True   # True = केवल कैंडल क्लोज या ब्रिक पलटने पर ही SL कटेगा
BROK_PER_QTY         = 1.5
MINTICK              = 0.1

# PRO 3-ENGINE PRE-SPIKE DIRECTION PARAMETERS ($8.0 SPREAD + STEP-IN + TAKER CVD + TOP-3)
MIN_SPREAD_TRIGGER   = 8.0
SPREAD_MULT_TRIGGER  = 7.0
VACUUM_WATCH_SEC     = 3.5
MIN_TAKER_DOM_PCT    = 58.0
MIN_TOP3_DOM_PCT     = 58.0
SIGNAL_COOLDOWN_SEC  = 180
EVAL_LOCK_SECONDS    = 180

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def fmt_pts(pts):
    return f"{pts:,.1f}"

# ============================================================================
# 100% HYPERLIQUID CANDLE SNAPSHOT FETCHERS (FIXED 3.5-DAY ANCHOR + LIVE)
# ============================================================================
def fetch_hl_klines(interval="1m", num_bars=20):
    tf_ms_map = {
        "1m": 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000
    }
    step_ms = tf_ms_map.get(interval, 60000)
    end_time = int(time.time() * 1000)
    start_time = end_time - (num_bars * step_ms)

    for attempt in range(3):
        try:
            r = requests.post(
                HYPERLIQUID_INFO_URL,
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": interval,
                        "startTime": start_time,
                        "endTime": end_time
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    data.sort(key=lambda x: int(x["t"]))
                    klines = []
                    for k in data:
                        t_ms = int(k["t"])
                        o_val = float(k["o"])
                        h_val = float(k["h"])
                        l_val = float(k["l"])
                        c_val = float(k["c"])
                        v_raw = float(k.get("v", 0.0))
                        v_safe = v_raw if v_raw > 0 else max(0.01, (h_val - l_val) * 0.1)
                        klines.append([t_ms, o_val, h_val, l_val, c_val, v_safe])
                    return klines
        except Exception:
            time.sleep(0.4)
    return None

def fetch_hl_5000_fixed_anchor():
    now_sec = int(time.time())
    today_00_utc_sec = (now_sec // 86400) * 86400
    anchor_start_ms = (today_00_utc_sec - (3 * 86400)) * 1000
    now_ms = now_sec * 1000
    mid_ms = anchor_start_ms + (2600 * 60 * 1000)

    chunks = [(anchor_start_ms, min(mid_ms, now_ms))]
    if now_ms > mid_ms:
        chunks.append((mid_ms, now_ms))

    merged = {}
    for st_ms, en_ms in chunks:
        for attempt in range(3):
            try:
                r = requests.post(
                    HYPERLIQUID_INFO_URL,
                    json={
                        "type": "candleSnapshot",
                        "req": {
                            "coin": "BTC",
                            "interval": "1m",
                            "startTime": st_ms,
                            "endTime": en_ms
                        }
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        for k in data:
                            t_ms = int(k["t"])
                            if t_ms >= anchor_start_ms:
                                o_val = float(k["o"])
                                h_val = float(k["h"])
                                l_val = float(k["l"])
                                c_val = float(k["c"])
                                v_raw = float(k.get("v", 0.0))
                                v_safe = v_raw if v_raw > 0 else max(0.01, (h_val - l_val) * 0.1)
                                merged[t_ms] = [t_ms, o_val, h_val, l_val, c_val, v_safe]
                        break
            except Exception:
                time.sleep(0.5)

    if not merged:
        return None
    sorted_times = sorted(merged.keys())
    return [merged[t] for t in sorted_times]

def calc_daily_atr5(klines_1d):
    if not klines_1d or len(klines_1d) < ATR_PERIOD + 2:
        return None
    highs = [float(k[2]) for k in klines_1d]
    lows = [float(k[3]) for k in klines_1d]
    closes = [float(k[4]) for k in klines_1d]
    tr = [0.0] * len(closes)
    for i in range(len(closes)):
        if i == 0:
            tr[i] = highs[i] - lows[i]
        else:
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    rma = [0.0] * len(tr)
    for i, v in enumerate(tr):
        if i < ATR_PERIOD - 1:
            rma[i] = sum(tr[:i + 1]) / float(i + 1)
        elif i == ATR_PERIOD - 1:
            rma[i] = sum(tr[:ATR_PERIOD]) / float(ATR_PERIOD)
        else:
            rma[i] = (rma[i - 1] * (ATR_PERIOD - 1) + v) / float(ATR_PERIOD)
    return rma[-2]

# ============================================================================
# STATEFUL INCREMENTAL BAR PROCESSOR (TRUE ADVERSE SL CHECK + BRICK SYNC)
# ============================================================================
def process_single_closed_bar(eng, kline):
    bar_time = int(kline[0])
    if bar_time <= eng["last_bar_time"]:
        return

    o = float(kline[1])
    h = float(kline[2])
    l = float(kline[3])
    c = float(kline[4])
    v = float(kline[5])
    bar_ist = (datetime.utcfromtimestamp(bar_time / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M %p")

    idx = eng["bar_count"]

    if idx == 0:
        tr = h - l
        eng["atr14"] = tr
    else:
        prev_c = eng["prev_close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        if idx < 14:
            eng["tr_sum"] += tr
            eng["atr14"] = eng["tr_sum"] / float(idx + 1)
        else:
            eng["atr14"] = (eng["atr14"] * 13.0 + tr) / 14.0

    if idx == 0:
        eng["ema21"] = c
    else:
        k_ema = 2.0 / 22.0
        eng["ema21"] = c * k_ema + eng["ema21"] * (1.0 - k_ema)

    if idx == 0:
        eng["rsi14"] = 50.0
    else:
        diff = c - eng["prev_close"]
        up = max(diff, 0.0)
        dn = max(-diff, 0.0)
        if idx < 14:
            eng["up_sum"] += up
            eng["dn_sum"] += dn
            eng["rma_up"] = eng["up_sum"] / float(idx)
            eng["rma_dn"] = eng["dn_sum"] / float(idx)
        else:
            eng["rma_up"] = (eng["rma_up"] * 13.0 + up) / 14.0
            eng["rma_dn"] = (eng["rma_dn"] * 13.0 + dn) / 14.0

        if eng["rma_dn"] == 0:
            eng["rsi14"] = 100.0
        elif eng["rma_up"] == 0:
            eng["rsi14"] = 0.0
        else:
            rs = eng["rma_up"] / eng["rma_dn"]
            eng["rsi14"] = 100.0 - (100.0 / (1.0 + rs))

    w = (2.0 * math.pi) / float(GAUSS_PERIOD)
    b = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a = -b + math.sqrt(b * b + 2.0 * b)
    if idx == 0:
        g_val = c
    elif idx == 1:
        g_val = (a ** 2) * c + 2.0 * (1.0 - a) * eng["g1"] - ((1.0 - a) ** 2) * c
    else:
        g_val = (a ** 2) * c + 2.0 * (1.0 - a) * eng["g1"] - ((1.0 - a) ** 2) * eng["g2"]
    eng["g2"] = eng["g1"]
    eng["g1"] = g_val

    rng = max(h - l, MINTICK)
    u_wick = h - max(o, c)
    l_wick = min(o, c) - l
    body = abs(c - o)
    bull_score = (c - l) + (l_wick * 1.1) + (body * 0.85 if c > o else 0.0)
    bear_score = (h - c) + (u_wick * 1.1) + (body * 0.85 if c < o else 0.0)
    bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8)
    bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
    tot_pow = bull_pow + bear_pow
    bar_buy_v = v * (bull_pow / tot_pow) if tot_pow > 0 else v * 0.5
    bar_sell_v = v * (bear_pow / tot_pow) if tot_pow > 0 else v * 0.5

    roll_buy = (bar_buy_v * 1.4) + eng["buy_v1"] + eng["buy_v2"]
    roll_sell = (bar_sell_v * 1.4) + eng["sell_v1"] + eng["sell_v2"]
    roll_tot = roll_buy + roll_sell
    buy_dom_pct = (roll_buy / roll_tot) * 100.0 if roll_tot > 0 else 50.0
    sell_dom_pct = 100.0 - buy_dom_pct

    eng["buy_v2"] = eng["buy_v1"]
    eng["buy_v1"] = bar_buy_v
    eng["sell_v2"] = eng["sell_v1"]
    eng["sell_v1"] = bar_sell_v
    eng["buy_dom_pct"] = buy_dom_pct
    eng["sell_dom_pct"] = sell_dom_pct

    safe_range = eng["macro_range"] if (eng["macro_range"] and eng["macro_range"] > 0) else (eng["atr14"] * 10.0)
    calc_auto_box = safe_range / RANGE_DIVISOR
    box_size = max(calc_auto_box if USE_AUTO_BOX else MANUAL_BOX, MINTICK * 2.0)
    eng["safe_range"] = safe_range
    eng["box_size"] = box_size

    eval_price = (c * 0.70 + g_val * 0.30) if USE_GAUSSIAN else c

    brick_step_up = False
    brick_step_dn = False

    if idx == 0:
        grid_top = round(c / box_size) * box_size
        eng["brick_top"] = grid_top
        eng["brick_bot"] = grid_top - box_size
        eng["brick_dir"] = 1
        eng["brick_streak"] = 1
        eng["anchor_time_str"] = bar_ist
    else:
        if eval_price >= eng["brick_top"] + box_size:
            steps = int(math.floor((eval_price - eng["brick_top"]) / box_size))
            eng["brick_top"] += (steps * box_size)
            eng["brick_bot"] = eng["brick_top"] - box_size
            brick_step_up = True
            eng["brick_streak"] = steps if eng["brick_dir"] == -1 else (eng["brick_streak"] + steps)
            eng["brick_dir"] = 1
        elif eval_price <= eng["brick_bot"] - box_size:
            steps = int(math.floor((eng["brick_bot"] - eval_price) / box_size))
            eng["brick_bot"] -= (steps * box_size)
            eng["brick_top"] = eng["brick_bot"] + box_size
            brick_step_dn = True
            eng["brick_streak"] = steps if eng["brick_dir"] == 1 else (eng["brick_streak"] + steps)
            eng["brick_dir"] = -1

    r_close = eng["brick_top"] if eng["brick_dir"] == 1 else eng["brick_bot"]

    band_dist = box_size * ST_FACTOR
    raw_supp = r_close - band_dist
    raw_res = r_close + band_dist

    prev_trend = eng["st_trend"]
    prev_supp = eng["support_band"]
    prev_res = eng["resistance_band"]

    if prev_supp is None:
        eng["support_band"] = raw_supp
    elif prev_trend == 1:
        eng["support_band"] = raw_supp if (eng["brick_dir"] == 1 and raw_supp > prev_supp) else prev_supp
    else:
        eng["support_band"] = raw_supp

    if prev_res is None:
        eng["resistance_band"] = raw_res
    elif prev_trend == -1:
        eng["resistance_band"] = raw_res if (eng["brick_dir"] == -1 and raw_res < prev_res) else prev_res
    else:
        eng["resistance_band"] = raw_res

    if prev_trend == -1 and eng["brick_dir"] == 1 and prev_res is not None and r_close > prev_res:
        eng["st_trend"] = 1
        eng["support_band"] = r_close - band_dist
    elif prev_trend == 1 and eng["brick_dir"] == -1 and prev_supp is not None and r_close < prev_supp:
        eng["st_trend"] = -1
        eng["resistance_band"] = r_close + band_dist
    else:
        eng["st_trend"] = prev_trend

    st_line = eng["support_band"] if eng["st_trend"] == 1 else eng["resistance_band"]
    eng["st_line"] = st_line

    st_flip_buy = (eng["st_trend"] == 1 and prev_trend == -1)
    st_flip_sell = (eng["st_trend"] == -1 and prev_trend == 1)

    if st_flip_buy or st_flip_sell:
        eng["brick_streak"] = 1
        eng["trend_tp1_done"] = False

    if st_flip_buy:
        eng["pending_flip_buy"] = True
        eng["pending_flip_sell"] = False
    if st_flip_sell:
        eng["pending_flip_sell"] = True
        eng["pending_flip_buy"] = False
    if eng["st_trend"] == -1:
        eng["pending_flip_buy"] = False
    if eng["st_trend"] == 1:
        eng["pending_flip_sell"] = False

    # ========================================================================
    # MANAGE ACTIVE 10-QTY TRADE (TRUE ADVERSE SL CHECK + 7Q TP1 BOOKING)
    # ========================================================================
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        eng["max_fav_price"] = max(eng["max_fav_price"], h) if t_dir == 1 else min(eng["max_fav_price"], l)

        # 1. Hit TP1 -> Book 7 Qty Immediately & Lock 3 Qty at small profit
        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["trend_tp1_done"] = True
            eng["wins"] += 1
            eng["booked_pnl_10q"] = eng["locked_tp1_pts"] * TP1_BOOK_QTY
            eng["gross_profit"] += eng["booked_pnl_10q"]
            eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
            eng["open_qty"] = RUNNER_QTY
            runner_lock_pts = RUNNER_LOCK_POINTS if USE_FIXED_POINTS else (box_size * RUNNER_LOCK_BRICKS)
            eng["stop_price"] = (eng["entry_price"] + runner_lock_pts) if t_dir == 1 else (eng["entry_price"] - runner_lock_pts)

        # 2. Hit Mid-Lock -> Lock 3 Qty Runner at TP1 price
        hit_mid_now = eng["tp1_reached"] and (not eng["mid_reached"]) and ((h >= eng["mid_lock_price"]) if t_dir == 1 else (l <= eng["mid_lock_price"]))
        if hit_mid_now:
            eng["mid_reached"] = True
            eng["stop_price"] = max(eng["stop_price"], eng["tp1_price"]) if t_dir == 1 else min(eng["stop_price"], eng["tp1_price"])

        # 3. Hit TP2 -> Start Unlimited Trail on 3 Qty Runner
        hit_tp2_now = eng["tp1_reached"] and (not eng["tp2_reached"]) and ((h >= eng["tp2_price"]) if t_dir == 1 else (l <= eng["tp2_price"]))
        if hit_tp2_now:
            eng["tp2_reached"] = True
            eng["tp2_hits"] += 1
            lock_floor = (eng["tp2_price"] - box_size * 0.35) if t_dir == 1 else (eng["tp2_price"] + box_size * 0.35)
            eng["stop_price"] = max(eng["stop_price"], lock_floor) if t_dir == 1 else min(eng["stop_price"], lock_floor)

        if eng["trade_dir"] != 0 and eng["tp2_reached"] and USE_TRAIL_BEYOND_TP2:
            gap_dist = box_size * TRAIL_LOCK_BRICKS
            brick_trail = (r_close - gap_dist) if t_dir == 1 else (r_close + gap_dist)
            peak_trail = (eng["max_fav_price"] - gap_dist * 1.15) if t_dir == 1 else (eng["max_fav_price"] + gap_dist * 1.15)

            if TRAIL_METHOD == "Pure Renko Brick Step Trail":
                cand_trail = brick_trail
            elif TRAIL_METHOD == "Renko Supertrend Line Trail":
                cand_trail = st_line
            else:
                cand_trail = max(brick_trail, peak_trail) if t_dir == 1 else min(brick_trail, peak_trail)

            eng["stop_price"] = max(eng["stop_price"], cand_trail) if t_dir == 1 else min(eng["stop_price"], cand_trail)

            hit_trail_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
            st_reversed = (eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)

            if (hit_trail_sl or st_reversed) and not hit_tp2_now:
                exit_p = eng["stop_price"] if hit_trail_sl else (max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"]))
                runner_pts = (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p)
                safe_runner_pts = max(runner_pts, eng["locked_tp2_pts"] * 0.85)
                runner_pnl_3q = safe_runner_pts * RUNNER_QTY

                eng["gross_profit"] += runner_pnl_3q
                total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_3q

                eng["last_result"] = f"🚀 Trail Exit (10Q): +{fmt_pts(total_trade_pnl)} pts [7Q TP1 + 3Q Trail]"
                eng["last_result_color"] = "#0369a1"
                eng["history"].insert(0, {
                    "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                    "exit": exit_p, "status": "🚀 7Q TP1 + 3Q TRAIL", "pnl": f"+{fmt_pts(total_trade_pnl)}", "color": "#38bdf8"
                })
                eng["history"] = eng["history"][:40]
                eng["trade_dir"] = 0
                eng["open_qty"] = 0

        if eng["trade_dir"] != 0 and not eng["tp2_reached"]:
            if not eng["tp1_reached"]:
                # True signed adverse move (positive only when trade is actually in loss)
                adverse_close_pts = (eng["entry_price"] - c) if t_dir == 1 else (c - eng["entry_price"])
                wick_hit_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
                close_hit_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])

                # brick_turned_bad ONLY triggers if brick flipped against trade AND price is genuinely in loss by >= 0.50 Brick
                brick_turned_bad = (
                    (eng["brick_dir"] == -1 and c < eng["brick_bot"] and adverse_close_pts >= box_size * 0.50)
                    if t_dir == 1
                    else (eng["brick_dir"] == 1 and c > eng["brick_top"] and adverse_close_pts >= box_size * 0.50)
                )
                st_turned_bad = ((eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)) and (adverse_close_pts > 0)
                hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

                sl_triggered = (close_hit_sl or brick_turned_bad or st_turned_bad or hard_crash) if ANTI_WICK_SL else (wick_hit_sl or st_turned_bad)

                if sl_triggered:
                    eng["losses"] += 1
                    # अधिकतम नुकसान कैप: फिक्स्ड मोड में SL_POINTS (290 pts), वरना ब्रिक-आधारित
                    max_cap_pts = SL_POINTS if USE_FIXED_POINTS else (box_size * MAX_SL_LOSS_BRICKS)
                    if ANTI_WICK_SL and not hard_crash and adverse_close_pts > 0:
                        loss_per_qty = min(adverse_close_pts, max_cap_pts)
                    else:
                        loss_per_qty = max_cap_pts
                    total_loss_10q = loss_per_qty * TOTAL_QTY
                    eng["gross_loss"] += total_loss_10q
                    eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)

                    eng["last_result"] = f"🛑 Full SL (10Q): -{fmt_pts(total_loss_10q)} pts (-{fmt_pts(loss_per_qty)}/Q)"
                    eng["last_result_color"] = "#991b1b"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": c, "status": "🛑 SL HIT (10Q)", "pnl": f"-{fmt_pts(total_loss_10q)}", "color": "#ef4444"
                    })
                    eng["history"] = eng["history"][:40]
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0
                    eng["trend_tp1_done"] = True
            else:
                hit_be_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
                st_turned_bad = (eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)

                if (hit_be_sl or st_turned_bad) and not hit_tp1_now:
                    exit_p = eng["stop_price"] if hit_be_sl else (max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"]))
                    runner_pts = max(0.0, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                    runner_pnl_3q = runner_pts * RUNNER_QTY
                    eng["gross_profit"] += runner_pnl_3q
                    total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_3q

                    status_tag = "✅ 7Q TP1 + 3Q MID-LOCK" if eng["mid_reached"] else "✅ 7Q TP1 + 3Q PROFIT-LOCK"
                    eng["last_result"] = f"{status_tag}: +{fmt_pts(total_trade_pnl)} pts"
                    eng["last_result_color"] = "#166534"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": exit_p, "status": status_tag, "pnl": f"+{fmt_pts(total_trade_pnl)}", "color": "#22c55e"
                    })
                    eng["history"] = eng["history"][:40]
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0

    # ========================================================================
    # CHECK NEW ENTRY SIGNALS (WITH BRICK DIRECTION SYNC & ONE-SHOT LOCK)
    # ========================================================================
    ema21 = eng["ema21"]
    rsi_val = eng["rsi14"]

    candle_not_giant = (h - l) <= box_size * 1.75
    flip_stretch_ok  = abs(c - ema21) <= box_size * 1.65
    bull_filter_ok   = candle_not_giant and flip_stretch_ok and buy_dom_pct >= 52.0 and rsi_val < 72.0
    bear_filter_ok   = candle_not_giant and flip_stretch_ok and sell_dom_pct >= 52.0 and rsi_val > 28.0

    # Require brick_dir to match st_trend so SHORT never enters on an opposing green brick!
    trigger_flip_buy  = eng["pending_flip_buy"] and eng["st_trend"] == 1 and eng["brick_dir"] == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and eng["st_trend"] == -1 and eng["brick_dir"] == -1 and bear_filter_ok and c < o

    allow_re_entry = (SIG_MODE == "Supertrend + Brick-Step Re-Entry (Best)")
    raw_cont_buy   = allow_re_entry and (not trigger_flip_buy) and eng["st_trend"] == 1 and eng["brick_dir"] == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and rsi_val > 51.0 and rsi_val < 68.0 and candle_not_giant
    raw_cont_sell  = allow_re_entry and (not trigger_flip_sell) and eng["st_trend"] == -1 and eng["brick_dir"] == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and rsi_val < 49.0 and rsi_val > 32.0 and candle_not_giant

    streak_ok   = (not USE_STREAK_FILTER) or (eng["brick_streak"] <= MAX_BRICK_STREAK)
    stretch_ok  = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
    one_shot_ok = not eng["trend_tp1_done"]
    late_safe   = streak_ok and stretch_ok and one_shot_ok

    trigger_cont_buy  = raw_cont_buy and late_safe
    trigger_cont_sell = raw_cont_sell and late_safe

    can_open_trade = (eng["trade_dir"] == 0) or (eng["tp1_reached"] and (st_flip_buy or st_flip_sell))

    if can_open_trade and ((raw_cont_buy and not trigger_cont_buy) or (raw_cont_sell and not trigger_cont_sell)):
        eng["blocked_late"] += 1

    if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            runner_pts = max(0.0, (c - eng["entry_price"]) if eng["trade_dir"] == 1 else (eng["entry_price"] - c))
            runner_pnl_3q = runner_pts * RUNNER_QTY
            eng["gross_profit"] += runner_pnl_3q
            tot_flip_pnl = eng["booked_pnl_10q"] + runner_pnl_3q
            eng["history"].insert(0, {
                "time": bar_ist, "type": f"{old_label} (10Q)", "entry": eng["entry_price"],
                "exit": c, "status": "✅ 7Q TP1 + 3Q FLIP", "pnl": f"+{fmt_pts(tot_flip_pnl)}", "color": "#22c55e"
            })
            eng["history"] = eng["history"][:40]

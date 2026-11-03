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
# UPGRADED MEDIUM-BRICK (DIVISOR 15) + ONE-SHOT TREND LOCK + 7Q TP1 PARAMETERS
# ============================================================================
TOTAL_QTY            = 10
TP1_BOOK_QTY         = 7      # 0.85 Brick (TP1) पर 7 क्वांटिटी तुरंत बुक होंगी
RUNNER_QTY           = 3      # बची हुई 3 क्वांटिटी प्रॉफिट-लॉक और बड़े रनर (TP2 + Trail) के लिए

USE_TRAIL_BEYOND_TP2 = True
TRAIL_METHOD         = "Smart Brick + Peak Ratchet (Best)"
TRAIL_LOCK_BRICKS    = 0.8
USE_STREAK_FILTER    = True
MAX_BRICK_STREAK     = 2      # केवल शुरुआती Brick #1 और #2 पर ही एंट्री (थके हुए ट्रेंड में लेट एंट्री बंद)
USE_STRETCH_FILTER   = True
MAX_EMA_DIST_BRICKS  = 1.1    # सख्त ओवर-स्ट्रेच फिल्टर: 21-EMA से 1.1 ब्रिक से ज्यादा दूर होने पर टॉप/बॉटम एंट्री ब्लॉक

USE_AUTO_BOX         = True
ATR_PERIOD           = 5
RANGE_DIVISOR        = 15.0   # 10.0 से बढ़ाकर 15.0 (Medium Brick Size ~120 pts: जल्दी एंट्री और छोटा SL)
MANUAL_BOX           = 120.0

ST_FACTOR            = 3.0
USE_GAUSSIAN         = True
GAUSS_PERIOD         = 20
SIG_MODE             = "Supertrend + Brick-Step Re-Entry (Best)"
MIN_VOL_DOM          = 55.0

# HIGH WIN-RATE TRIGGERS + IMPROVED PAYOFF RATIO
TP1_BRICKS           = 0.85   # 0.85 Brick पर 7 Qty बुक
RUNNER_LOCK_BRICKS   = 0.35   # TP1 हिट होते ही बची हुई 3 Qty का SL +0.35 Brick प्रॉफिट पर लॉक होगा
MID_LOCK_BRICKS      = 1.25   # 1.25 Bricks छूते ही बची हुई 3 Qty का SL सीधा TP1 (+0.85 Brick) पर आ जाएगा
TP2_BRICKS           = 2.20   # TP2 रनर टारगेट
SL_BRICKS            = 1.15   # Anti-Wick कैंडल-क्लोज ट्रिगर (ताकि मामूली सुई/Wick से ट्रेड न कटे)
MAX_SL_LOSS_BRICKS   = 0.90   # अधिकतम SL नुकसान कैप: 0.90 Brick प्रति Qty से ज्यादा नुकसान कभी नहीं लगेगा
ANTI_WICK_SL         = True   # True = केवल कैंडल क्लोज या रैंकों पलटने पर ही SL कटेगा
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
# STATEFUL INCREMENTAL BAR PROCESSOR (DIVISOR 15 + ONE-SHOT TREND LOCK)
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
        # Reset One-Shot Trend Lock only when a fresh Supertrend Flip occurs
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
    # MANAGE ACTIVE 10-QTY TRADE (0.85 TP1 + 7Q BOOK + ONE-SHOT LOCK + 0.9B SL CAP)
    # ========================================================================
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        eng["max_fav_price"] = max(eng["max_fav_price"], h) if t_dir == 1 else min(eng["max_fav_price"], l)

        # 1. Hit TP1 (0.85 Brick) -> Book 7 Qty Immediately & Lock 3 Qty at +0.35 Brick Profit!
        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["trend_tp1_done"] = True   # Lock out late re-entries in the same trend wave!
            eng["wins"] += 1
            eng["booked_pnl_10q"] = eng["locked_tp1_pts"] * TP1_BOOK_QTY
            eng["gross_profit"] += eng["booked_pnl_10q"]
            eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
            eng["open_qty"] = RUNNER_QTY
            runner_lock_pts = box_size * RUNNER_LOCK_BRICKS
            eng["stop_price"] = (eng["entry_price"] + runner_lock_pts) if t_dir == 1 else (eng["entry_price"] - runner_lock_pts)

        # 2. Hit Mid-Lock (1.25 Bricks) -> Lock 3 Qty Runner at TP1 (+0.85 Brick)
        hit_mid_now = eng["tp1_reached"] and (not eng["mid_reached"]) and ((h >= eng["mid_lock_price"]) if t_dir == 1 else (l <= eng["mid_lock_price"]))
        if hit_mid_now:
            eng["mid_reached"] = True
            eng["stop_price"] = max(eng["stop_price"], eng["tp1_price"]) if t_dir == 1 else min(eng["stop_price"], eng["tp1_price"])

        # 3. Hit TP2 (2.20 Bricks) -> Start Unlimited Trail on 3 Qty Runner
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
                wick_hit_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
                close_hit_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
                brick_turned_bad = (eng["brick_dir"] == -1 and c < eng["brick_bot"]) if t_dir == 1 else (eng["brick_dir"] == 1 and c > eng["brick_top"])
                st_turned_bad = (eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)
                hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

                sl_triggered = (close_hit_sl or brick_turned_bad or st_turned_bad or hard_crash) if ANTI_WICK_SL else (wick_hit_sl or st_turned_bad)

                if sl_triggered:
                    eng["losses"] += 1
                    # Strict SL Loss Cap: Never charge more than MAX_SL_LOSS_BRICKS (0.90 Brick) per Qty
                    max_cap_pts = box_size * MAX_SL_LOSS_BRICKS
                    loss_per_qty = min(abs(eng["entry_price"] - c), max_cap_pts) if (ANTI_WICK_SL and not hard_crash) else max_cap_pts
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
                    # Also lock out same-trend re-entry after a full SL hit so it waits for a fresh ST Flip
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
    # CHECK NEW ENTRY SIGNALS (WITH ONE-SHOT TREND LOCK & STRICT EMA STRETCH)
    # ========================================================================
    ema21 = eng["ema21"]
    rsi_val = eng["rsi14"]

    candle_not_giant = (h - l) <= box_size * 1.75
    flip_stretch_ok  = abs(c - ema21) <= box_size * 1.65
    bull_filter_ok   = candle_not_giant and flip_stretch_ok and buy_dom_pct >= 52.0 and rsi_val < 72.0
    bear_filter_ok   = candle_not_giant and flip_stretch_ok and sell_dom_pct >= 52.0 and rsi_val > 28.0

    trigger_flip_buy  = eng["pending_flip_buy"] and eng["st_trend"] == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and eng["st_trend"] == -1 and bear_filter_ok and c < o

    allow_re_entry = (SIG_MODE == "Supertrend + Brick-Step Re-Entry (Best)")
    raw_cont_buy   = allow_re_entry and (not trigger_flip_buy) and eng["st_trend"] == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and rsi_val > 51.0 and rsi_val < 68.0 and candle_not_giant
    raw_cont_sell  = allow_re_entry and (not trigger_flip_sell) and eng["st_trend"] == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and rsi_val < 49.0 and rsi_val > 32.0 and candle_not_giant

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

        is_long = trigger_flip_buy or trigger_cont_buy
        if is_long:
            eng["pending_flip_buy"] = False
        else:
            eng["pending_flip_sell"] = False

        eng["trade_dir"] = 1 if is_long else -1
        eng["entry_bar"] = idx
        eng["entry_price"] = c
        eng["max_fav_price"] = c
        eng["tp1_reached"] = False
        eng["mid_reached"] = False
        eng["tp2_reached"] = False
        eng["open_qty"] = TOTAL_QTY
        eng["booked_pnl_10q"] = 0.0
        eng["entry_tag"] = f"🧱 Brick #{eng['brick_streak']}" if (trigger_cont_buy or trigger_cont_sell) else "🔥 ST Flip"
        eng["entry_time_str"] = bar_ist

        eng["locked_tp1_pts"] = box_size * TP1_BRICKS
        mid_pts = box_size * MID_LOCK_BRICKS
        eng["locked_tp2_pts"] = box_size * TP2_BRICKS
        eng["locked_sl_pts"] = box_size * SL_BRICKS

        eng["tp1_price"] = (c + eng["locked_tp1_pts"]) if is_long else (c - eng["locked_tp1_pts"])
        eng["mid_lock_price"] = (c + mid_pts) if is_long else (c - mid_pts)
        eng["tp2_price"] = (c + eng["locked_tp2_pts"]) if is_long else (c - eng["locked_tp2_pts"])
        eng["stop_price"] = (c - eng["locked_sl_pts"]) if is_long else (c + eng["locked_sl_pts"])
        eng["hard_stop_price"] = (eng["stop_price"] - box_size * 0.35) if is_long else (eng["stop_price"] + box_size * 0.35)

    eng["prev_close"] = c
    eng["last_bar_time"] = bar_time
    eng["bar_count"] += 1

# ============================================================================
# PRO 3-ENGINE PRE-SPIKE DIRECTION RADAR:
# [1] $8+ VACUUM STEP-IN + [2] REAL TAKER TRADES (CVD) + [3] TOP-3 DEPLETION
# ============================================================================
def fetch_hl_taker_flow():
    taker_buy_v = 0.0
    taker_sell_v = 0.0
    try:
        r_tr = requests.post(
            HYPERLIQUID_INFO_URL,
            json={"type": "recentTrades", "coin": "BTC"},
            headers={"Content-Type": "application/json"},
            timeout=2.5
        )
        if r_tr.status_code == 200:
            trades = r_tr.json()
            if isinstance(trades, list) and len(trades) > 0:
                now_ms = int(time.time() * 1000)
                for idx, t in enumerate(trades[:40]):
                    t_ms = int(t.get("time", 0))
                    if (now_ms - t_ms <= 12000) or idx < 15:
                        sz = float(t.get("sz", 0.0))
                        side = str(t.get("side", ""))
                        if side == "B":
                            taker_buy_v += sz
                        elif side == "A":
                            taker_sell_v += sz
    except Exception:
        pass

    tot_v = taker_buy_v + taker_sell_v
    if tot_v > 0:
        t_buy_pct = round((taker_buy_v / tot_v) * 100.0, 1)
    else:
        t_buy_pct = 50.0
    t_sell_pct = round(100.0 - t_buy_pct, 1)
    return taker_buy_v, taker_sell_v, t_buy_pct, t_sell_pct

def fetch_l2_orderbook_and_spike_radar(eng):
    bids = []
    asks = []

    try:
        r_hl = requests.post(
            HYPERLIQUID_INFO_URL,
            json={"type": "l2Book", "coin": "BTC"},
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        if r_hl.status_code == 200:
            data = r_hl.json()
            levels = data.get("levels", [])
            if len(levels) >= 2 and levels[0] and levels[1]:
                bids = [(float(b["px"]), float(b["sz"])) for b in levels[0][:20]]
                asks = [(float(a["px"]), float(a["sz"])) for a in levels[1][:20]]
    except Exception:
        return

    if not bids or not asks:
        return

    now_ts = time.time()
    ist_t = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
    best_bid, best_bid_sz = bids[0][0], bids[0][1]
    best_ask, best_ask_sz = asks[0][0], asks[0][1]
    mid_price = (best_bid + best_ask) / 2.0
    spread = max(0.1, best_ask - best_bid)

    taker_buy_v, taker_sell_v, taker_buy_pct, taker_sell_pct = fetch_hl_taker_flow()
    taker_net_delta = taker_buy_v - taker_sell_v

    bid_vol_3 = sum(b[1] for b in bids[:3])
    ask_vol_3 = sum(a[1] for a in asks[:3])
    tot_top3 = bid_vol_3 + ask_vol_3
    top3_bid_pct = round((bid_vol_3 / tot_top3) * 100.0, 1) if tot_top3 > 0 else 50.0
    top3_ask_pct = round(100.0 - top3_bid_pct, 1)

    bid_vol_15 = sum(b[1] for b in bids[:15])
    ask_vol_15 = sum(a[1] for a in asks[:15])
    tot_depth_15 = bid_vol_15 + ask_vol_15
    bid_pct = round((bid_vol_15 / tot_depth_15) * 100.0, 1) if tot_depth_15 > 0 else 50.0
    ask_pct = round(100.0 - bid_pct, 1)

    top_sz = best_bid_sz + best_ask_sz
    micro_price = ((best_bid * best_ask_sz) + (best_ask * best_bid_sz)) / top_sz if top_sz > 0 else mid_price
    micro_skew = micro_price - mid_price

    max_bid_wall = max(bids, key=lambda x: x[1])
    max_ask_wall = max(asks, key=lambda x: x[1])

    for item in eng["spike_history"]:
        if not item.get("locked", False):
            elapsed = now_ts - item["sig_ts"]
            sig_p = item["price"]
            fav_move = (mid_price - sig_p) if item["dir_code"] == 1 else (sig_p - mid_price)
            item["max_fav"] = max(item["max_fav"], fav_move)
            item["curr_move"] = fav_move
            if elapsed >= EVAL_LOCK_SECONDS:
                item["locked"] = True
                item["rem_sec"] = 0
            else:
                item["rem_sec"] = int(EVAL_LOCK_SECONDS - elapsed)

    hist = eng["l2_tick_window"]
    if len(hist) >= 5:
        sorted_sp = sorted(x["spread"] for x in hist)
        calm_slice = sorted_sp[:max(3, int(len(sorted_sp) * 0.70))]
        normal_spread = sum(calm_slice) / float(len(calm_slice))
    else:
        normal_spread = 1.0

    if len(hist) >= 3:
        ref_ask = min(x["ask"] for x in hist[-3:])
        ref_bid = max(x["bid"] for x in hist[-3:])
        ask_jump = max(0.0, best_ask - ref_ask)
        bid_drop = max(0.0, ref_bid - best_bid)

        prev_ask_v3 = sum(x["ask_v3"] for x in hist[-3:]) / 3.0
        prev_bid_v3 = sum(x["bid_v3"] for x in hist[-3:]) / 3.0
        ask_top3_eaten = (bid_vol_3 > prev_bid_v3 * 0.9) and (ask_vol_3 < prev_ask_v3 * 0.75)
        bid_top3_eaten = (ask_vol_3 > prev_ask_v3 * 0.9) and (bid_vol_3 < prev_bid_v3 * 0.75)
    else:
        ask_jump = 0.0
        bid_drop = 0.0
        ask_top3_eaten = False
        bid_top3_eaten = False

    hist.append({
        "ts": now_ts,
        "mid": mid_price,
        "bid": best_bid,
        "ask": best_ask,
        "spread": spread,
        "bid_v3": bid_vol_3,
        "ask_v3": ask_vol_3,
        "t_buy_pct": taker_buy_pct
    })
    if len(hist) > 30:
        hist.pop(0)

    req_spread = max(MIN_SPREAD_TRIGGER, normal_spread * SPREAD_MULT_TRIGGER)
    spread_gate_open = (spread >= req_spread)

    vac = eng.setdefault("active_vacuum", {
        "armed": False,
        "ts": 0.0,
        "peak_spread": 0.0,
        "vac_bid": 0.0,
        "vac_ask": 0.0,
        "vac_mid": 0.0
    })

    if spread_gate_open:
        if not vac["armed"]:
            vac["armed"] = True
            vac["ts"] = now_ts
            vac["peak_spread"] = spread
            vac["vac_bid"] = best_bid
            vac["vac_ask"] = best_ask
            vac["vac_mid"] = mid_price
        else:
            if spread > vac["peak_spread"]:
                vac["peak_spread"] = spread
            vac["vac_bid"] = min(vac["vac_bid"], best_bid)
            vac["vac_ask"] = max(vac["vac_ask"], best_ask)
    elif vac["armed"] and (now_ts - vac["ts"] > VACUUM_WATCH_SEC):
        vac["armed"] = False

    if vac["armed"]:
        bid_step_in = max(0.0, best_bid - vac["vac_bid"])
        ask_step_dn = max(0.0, vac["vac_ask"] - best_ask)
    else:
        bid_step_in = 0.0
        ask_step_dn = 0.0

    gate_status_txt = (
        f"🔓 VACUUM ARMED! (Peak Spread: ${vac['peak_spread']:.1f} | Step-In Tracking...)"
        if vac["armed"]
        else f"🔒 GATE LOCKED (Live Spread ${spread:.1f} < Trigger ${req_spread:.1f})"
    )

    eng["order_book"] = {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "micro_price": micro_price,
        "spread": spread,
        "normal_spread": normal_spread,
        "req_spread": req_spread,
        "spread_gate_open": vac["armed"],
        "gate_status_txt": gate_status_txt,
        "ask_jump": ask_jump,
        "bid_drop": bid_drop,
        "bid_step_in": bid_step_in,
        "ask_step_dn": ask_step_dn,
        "bid_vol_3": bid_vol_3,
        "ask_vol_3": ask_vol_3,
        "top3_bid_pct": top3_bid_pct,
        "top3_ask_pct": top3_ask_pct,
        "taker_buy_v": taker_buy_v,
        "taker_sell_v": taker_sell_v,
        "taker_buy_pct": taker_buy_pct,
        "taker_sell_pct": taker_sell_pct,
        "taker_net_delta": taker_net_delta,
        "bid_vol": bid_vol_15,
        "ask_vol": ask_vol_15,
        "bid_pct": bid_pct,
        "ask_pct": ask_pct,
        "bid_wall_px": max_bid_wall[0],
        "bid_wall_sz": max_bid_wall[1],
        "ask_wall_px": max_ask_wall[0],
        "ask_wall_sz": max_ask_wall[1]
    }

    taker_bull_ok = (taker_buy_pct >= MIN_TAKER_DOM_PCT) or (taker_buy_pct >= 52.0 and micro_skew > 0)
    step_bull_ok  = (bid_step_in >= 1.5 and bid_step_in > ask_step_dn) or (ask_jump >= 4.0 and ask_jump > bid_drop * 1.4 and mid_price >= vac["vac_mid"])
    top3_bull_ok  = (top3_bid_pct >= MIN_TOP3_DOM_PCT) or ask_top3_eaten

    taker_bear_ok = (taker_sell_pct >= MIN_TAKER_DOM_PCT) or (taker_sell_pct >= 52.0 and micro_skew < 0)
    step_bear_ok  = (ask_step_dn >= 1.5 and ask_step_dn > bid_step_in) or (bid_drop >= 4.0 and bid_drop > ask_jump * 1.4 and mid_price <= vac["vac_mid"])
    top3_bear_ok  = (top3_ask_pct >= MIN_TOP3_DOM_PCT) or bid_top3_eaten

    time_since_last = now_ts - eng["last_spike_alert_ts"]
    spike_dir_text = None
    dir_code = 0
    col = "#38bdf8"
    trig_sp = vac["peak_spread"] if vac["armed"] else spread

    if vac["armed"] and len(hist) >= 5 and time_since_last >= SIGNAL_COOLDOWN_SEC:
        if taker_bull_ok and step_bull_ok and top3_bull_ok:
            spike_dir_text = (
                f"🚀 PRO PRE-SPIKE BUY (Spread: ${trig_sp:.1f} | "
                f"Taker Buy: {taker_buy_pct:.0f}% | Top3 Bid: {top3_bid_pct:.0f}%)"
            )
            dir_code = 1
            col = "#22c55e"
            vac["armed"] = False
        elif taker_bear_ok and step_bear_ok and top3_bear_ok:
            spike_dir_text = (
                f"🔻 PRO PRE-SPIKE SELL (Spread: ${trig_sp:.1f} | "
                f"Taker Sell: {taker_sell_pct:.0f}% | Top3 Ask: {top3_ask_pct:.0f}%)"
            )
            dir_code = -1
            col = "#ef4444"
            vac["armed"] = False

    eng.setdefault("max_spread_record", {
        "spread": 0.0,
        "time": "--:--:--",
        "price": 0.0,
        "signal": "अभी कोई रिकॉर्ड नहीं",
        "color": "#94a3b8"
    })

    if spread > eng["max_spread_record"]["spread"]:
        if spike_dir_text:
            peak_sig = spike_dir_text
            peak_col = col
        elif taker_buy_pct >= 56.0 and top3_bid_pct >= 55.0:
            peak_sig = f"🟢 PRO BUY FLOW (Taker Buy: {taker_buy_pct:.0f}% | Top-3 Bid: {top3_bid_pct:.0f}%)"
            peak_col = "#4ade80"
        elif taker_sell_pct >= 56.0 and top3_ask_pct >= 55.0:
            peak_sig = f"🔴 PRO SELL FLOW (Taker Sell: {taker_sell_pct:.0f}% | Top-3 Ask: {top3_ask_pct:.0f}%)"
            peak_col = "#f87171"
        else:
            peak_sig = f"⚖️ Mixed Flow (Taker Buy {taker_buy_pct:.0f}% | Top-3 Bid {top3_bid_pct:.0f}%)"
            peak_col = "#facc15"

        eng["max_spread_record"] = {
            "spread": spread,
            "time": ist_t,
            "price": mid_price,
            "signal": peak_sig,
            "color": peak_col
        }

    if spike_dir_text:
        alert_id = int(now_ts * 1000)
        eng["spike_history"].insert(0, {
            "time": ist_t,
            "sig_ts": now_ts,
            "price": mid_price,
            "spread_info": f"${trig_sp:.1f} (Taker {taker_buy_pct:.0f}/{taker_sell_pct:.0f}%)",
            "direction": spike_dir_text,
            "dir_code": dir_code,
            "max_fav": 0.0,
            "curr_move": 0.0,
            "rem_sec": EVAL_LOCK_SECONDS,
            "locked": False,
            "color": col
        })
        eng["spike_history"] = eng["spike_history"][:20]
        eng["last_spike_alert_ts"] = now_ts
        eng["last_spike_alert_id"] = alert_id
        eng["last_spike_dir"] = dir_code
        eng["last_spike_status"] = f"🔊⚡ {ist_t}: {spike_dir_text} @ ${mid_price:,.1f}"
        eng["last_spike_color"] = col
    elif now_ts - eng["last_spike_alert_ts"] > 15:
        if vac["armed"]:
            eng["last_spike_status"] = (
                f"⚠️ वैक्यूम खुला (${vac['peak_spread']:.1f})! Step-In व Taker Flow चेक हो रहा है: "
                f"Taker Buy {taker_buy_pct:.0f}% | Top-3 Bid {top3_bid_pct:.0f}%"
            )
            eng["last_spike_color"] = "#b45309"
        else:
            eng["last_spike_status"] = (
                f"🛡️ 3-Engine Direction Lock (Live Spread: ${spread:.1f} | "
                f"Taker Buy: {taker_buy_pct:.0f}% | Top-3 Bid: {top3_bid_pct:.0f}%)"
            )
            eng["last_spike_color"] = "#0f172a"

# ============================================================================
# 24x7 BACKGROUND WORKER (5000 CANDLES FIXED-GRID LOCK + 3-ENGINE RADAR)
# ============================================================================
def background_worker(eng):
    last_1d_fetch = 0
    last_kline_fetch = 0

    while True:
        try:
            now_ts = time.time()

            if now_ts - last_1d_fetch > 300 or eng["macro_range"] is None:
                klines_1d = fetch_hl_klines("1d", 20)
                if klines_1d:
                    d_val = calc_daily_atr5(klines_1d)
                    if d_val:
                        eng["macro_range"] = d_val
                        last_1d_fetch = now_ts

            if not eng["initialized"] and eng["macro_range"] is not None:
                klines_init = fetch_hl_5000_fixed_anchor()
                if klines_init and len(klines_init) > 100:
                    for b in klines_init[:-1]:
                        process_single_closed_bar(eng, b)
                    eng["price"] = float(klines_init[-1][4])
                    eng["initialized"] = True
                    last_kline_fetch = now_ts

            fetch_l2_orderbook_and_spike_radar(eng)
            if eng["order_book"]["mid_price"] > 0 and eng["initialized"]:
                eng["price"] = eng["order_book"]["mid_price"]

            if eng["initialized"] and (now_ts - last_kline_fetch >= 2.0):
                klines_live = fetch_hl_klines("1m", 8)
                if klines_live and len(klines_live) >= 2:
                    for b in klines_live[:-1]:
                        process_single_closed_bar(eng, b)
                    if eng["order_book"]["mid_price"] == 0:
                        eng["price"] = float(klines_live[-1][4])
                    last_kline_fetch = now_ts

            eng["ist_time"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
            eng["error"] = None

        except Exception as e:
            eng["error"] = str(e)

        time.sleep(1)

@st.cache_resource
def get_hl_5000_oneshot_div15_engine():
    eng = {
        "initialized": False,
        "bar_count": 0,
        "last_bar_time": 0,
        "anchor_time_str": "--",
        "prev_close": 0.0,
        "tr_sum": 0.0,
        "atr14": 15.0,
        "ema21": 0.0,
        "up_sum": 0.0,
        "dn_sum": 0.0,
        "rma_up": 0.0,
        "rma_dn": 0.0,
        "rsi14": 50.0,
        "g1": 0.0,
        "g2": 0.0,
        "buy_v1": 0.0,
        "buy_v2": 0.0,
        "sell_v1": 0.0,
        "sell_v2": 0.0,
        "buy_dom_pct": 50.0,
        "sell_dom_pct": 50.0,
        "macro_range": None,
        "safe_range": 1500.0,
        "box_size": 120.0,
        "brick_top": 0.0,
        "brick_bot": 0.0,
        "brick_dir": 1,
        "brick_streak": 1,
        "support_band": None,
        "resistance_band": None,
        "st_trend": 1,
        "st_line": 0.0,
        "trend_tp1_done": False,
        "pending_flip_buy": False,
        "pending_flip_sell": False,
        "trade_dir": 0,
        "entry_bar": -1,
        "entry_price": 0.0,
        "tp1_price": 0.0,
        "mid_lock_price": 0.0,
        "tp2_price": 0.0,
        "stop_price": 0.0,
        "hard_stop_price": 0.0,
        "max_fav_price": 0.0,
        "locked_tp1_pts": 0.0,
        "locked_tp2_pts": 0.0,
        "locked_sl_pts": 0.0,
        "tp1_reached": False,
        "mid_reached": False,
        "tp2_reached": False,
        "open_qty": 0,
        "booked_pnl_10q": 0.0,
        "entry_tag": "",
        "entry_time_str": "",
        "wins": 0,
        "losses": 0,
        "tp2_hits": 0,
        "blocked_late": 0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "total_brok": 0.0,
        "price": 0.0,
        "ist_time": "--:--:--",
        "last_result": "अभी कोई ट्रेड क्लोज नहीं हुआ है",
        "last_result_color": "#334155",
        "history": [],
        "order_book": {
            "best_bid": 0.0,
            "best_ask": 0.0,
            "mid_price": 0.0,
            "micro_price": 0.0,
            "spread": 0.0,
            "normal_spread": 1.0,
            "req_spread": 8.0,
            "spread_gate_open": False,
            "gate_status_txt": "🔒 GATE LOCKED (Trigger ≥ $8.0)",
            "ask_jump": 0.0,
            "bid_drop": 0.0,
            "bid_step_in": 0.0,
            "ask_step_dn": 0.0,
            "bid_vol_3": 0.0,
            "ask_vol_3": 0.0,
            "top3_bid_pct": 50.0,
            "top3_ask_pct": 50.0,
            "taker_buy_v": 0.0,
            "taker_sell_v": 0.0,
            "taker_buy_pct": 50.0,
            "taker_sell_pct": 50.0,
            "taker_net_delta": 0.0,
            "bid_vol": 0.0,
            "ask_vol": 0.0,
            "bid_pct": 50.0,
            "ask_pct": 50.0,
            "bid_wall_px": 0.0,
            "bid_wall_sz": 0.0,
            "ask_wall_px": 0.0,
            "ask_wall_sz": 0.0
        },
        "active_vacuum": {
            "armed": False,
            "ts": 0.0,
            "peak_spread": 0.0,
            "vac_bid": 0.0,
            "vac_ask": 0.0,
            "vac_mid": 0.0
        },
        "max_spread_record": {
            "spread": 0.0,
            "time": "--:--:--",
            "price": 0.0,
            "signal": "अभी कोई रिकॉर्ड नहीं",
            "color": "#94a3b8"
        },
        "l2_tick_window": [],
        "last_spike_alert_ts": 0,
        "last_spike_alert_id": 0,
        "last_spike_dir": 0,
        "last_spike_status": "📡 Pro 3-Engine Direction Radar सिंक हो रहा है...",
        "last_spike_color": "#0f172a",
        "spike_history": [],
        "error": None
    }
    thread = threading.Thread(target=background_worker, args=(eng,), daemon=True)
    thread.start()
    return eng

eng = get_hl_5000_oneshot_div15_engine()

# ============================================================================
# SINGLE CLEAN TERMINAL HEADER (AUDIO UNLOCK BAR + RESET MAX SPREAD BUTTON)
# ============================================================================
top_col1, top_col2 = st.columns([0.74, 0.26])
with top_col1:
    sound_bar_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: transparent; font-family: sans-serif; overflow: hidden; }
  .aud-bar {
    display: flex; align-items: center; justify-content: space-between;
    background: #111827; border: 1px solid #334155; border-radius: 10px;
    padding: 6px 14px; color: #f8fafc; font-size: 12px;
  }
  .aud-left { display: flex; align-items: center; gap: 8px; font-weight: 700; color: #38bdf8; }
  .aud-btns { display: flex; align-items: center; gap: 8px; }
  button {
    background: #0284c7; color: #ffffff; border: 1px solid #38bdf8;
    border-radius: 6px; padding: 5px 11px; font-size: 11.5px; font-weight: 700;
    cursor: pointer; transition: 0.15s;
  }
  button:hover { background: #0369a1; }
  button.unlocked { background: #15803d; border-color: #4ade80; }
  button.muted { background: #7f1d1d; border-color: #f87171; }
</style>
</head>
<body>
<div class="aud-bar">
  <div class="aud-left">
    <span id="aud-status">🔔 $8.0+ Pre-Spike Sound Alert: स्टैंडबाय (एक बार 'टेस्ट/अनलॉक' बटन दबाएं)</span>
  </div>
  <div class="aud-btns">
    <button id="unlock-btn" onclick="unlockAndTestAudio()">🔊 साउंड अनलॉक / टेस्ट करें</button>
    <button id="mute-btn" onclick="toggleMute()">🔈 Mute: OFF</button>
  </div>
</div>
<script>
let audioCtx = null;
let isMuted = false;
let lastPlayedAlertId = "0";

function ensureAudioCtx() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
}

function playSpikeChime(dirCode) {
  if (isMuted) return;
  try {
    ensureAudioCtx();
    const notes = dirCode === 1 ? [880, 1175, 1568, 1568] : [987, 740, 523, 523];
    let startTime = audioCtx.currentTime;
    notes.forEach((freq, idx) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = dirCode === 1 ? "triangle" : "sawtooth";
      osc.frequency.setValueAtTime(freq, startTime + idx * 0.17);
      gain.gain.setValueAtTime(0.001, startTime + idx * 0.17);
      gain.gain.exponentialRampToValueAtTime(0.35, startTime + idx * 0.17 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + idx * 0.17 + 0.14);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(startTime + idx * 0.17);
      osc.stop(startTime + idx * 0.17 + 0.15);
    });
  } catch (e) {}
}

function unlockAndTestAudio() {
  ensureAudioCtx();
  playSpikeChime(1);
  const btn = document.getElementById("unlock-btn");
  btn.className = "unlocked";
  btn.textContent = "✅ साउंड एक्टिव है";
  document.getElementById("aud-status").textContent = "🔊 $8.0+ Pre-Spike Audio Alert: 100% ACTIVE";
  document.getElementById("aud-status").style.color = "#4ade80";
}

function toggleMute() {
  isMuted = !isMuted;
  const mBtn = document.getElementById("mute-btn");
  if (isMuted) {
    mBtn.className = "muted";
    mBtn.textContent = "🔇 Muted: ON";
  } else {
    mBtn.className = "";
    mBtn.textContent = "🔈 Mute: OFF";
    playSpikeChime(1);
  }
}

setInterval(() => {
  try {
    const hook = window.parent.document.getElementById("hl-spike-audio-hook");
    if (hook) {
      const alertId = hook.getAttribute("data-alert-id") || "0";
      const alertDir = parseInt(hook.getAttribute("data-alert-dir") || "1", 10);
      if (alertId !== "0" && alertId !== lastPlayedAlertId) {
        if (lastPlayedAlertId !== "0") {
          playSpikeChime(alertDir);
        }
        lastPlayedAlertId = alertId;
      }
    }
  } catch (e) {}
}, 500);
</script>
</body>
</html>"""
    components.html(sound_bar_html, height=44, scrolling=False)

with top_col2:
    if st.button("🔄 सर्वोच्च स्प्रेड रीसेट करें (Reset Max Spread)"):
        eng["max_spread_record"] = {
            "spread": 0.0,
            "time": "--:--:--",
            "price": 0.0,
            "signal": "रीसेट किया गया (नए हाई की प्रतीक्षा...)",
            "color": "#94a3b8"
        }

terminal = st.empty()

# ============================================================================
# ZERO-BLINK LIVE RENDERING LOOP (DIVISOR 15 + ONE-SHOT LOCK + 7Q TP1)
# ============================================================================
while True:
    if not eng["initialized"] or eng["price"] == 0.0:
        terminal.info("⏳ Dr Devendra AI-Renko PRO: मीडियम ब्रिक (Divisor 15) और One-Shot Trend Lock इंजन लोड हो रहा है...")
        time.sleep(1)
        continue

    price = eng["price"]
    box_size = eng["box_size"]
    safe_range = eng["safe_range"]
    st_trend = eng["st_trend"]
    st_line = eng["st_line"]
    brick_streak = eng["brick_streak"]
    ema21 = eng["ema21"]
    rsi14 = eng["rsi14"]
    buy_pct = int(round(eng["buy_dom_pct"]))
    sell_pct = int(round(eng["sell_dom_pct"]))
    imbalance = (eng["buy_dom_pct"] - eng["sell_dom_pct"]) / 100.0
    ist_time = eng["ist_time"]
    bar_count = eng["bar_count"]
    anchor_str = eng["anchor_time_str"]

    ob = eng["order_book"]
    best_bid = ob["best_bid"]
    best_ask = ob["best_ask"]
    spread = ob["spread"]
    normal_spread = ob["normal_spread"]
    req_spread = ob["req_spread"]
    spread_gate_open = ob["spread_gate_open"]
    gate_status_txt = ob["gate_status_txt"]
    ask_jump = ob["ask_jump"]
    bid_drop = ob["bid_drop"]
    bid_step_in = ob.get("bid_step_in", 0.0)
    ask_step_dn = ob.get("ask_step_dn", 0.0)
    bid_vol_3 = ob.get("bid_vol_3", 0.0)
    ask_vol_3 = ob.get("ask_vol_3", 0.0)
    top3_bid_pct = ob.get("top3_bid_pct", 50.0)
    top3_ask_pct = ob.get("top3_ask_pct", 50.0)
    taker_buy_v = ob.get("taker_buy_v", 0.0)
    taker_sell_v = ob.get("taker_sell_v", 0.0)
    taker_buy_pct = ob.get("taker_buy_pct", 50.0)
    taker_sell_pct = ob.get("taker_sell_pct", 50.0)
    taker_net_delta = ob.get("taker_net_delta", 0.0)
    bid_pct = ob["bid_pct"]
    ask_pct = ob["ask_pct"]
    bid_vol = ob["bid_vol"]
    ask_vol = ob["ask_vol"]
    bid_wall_px = ob["bid_wall_px"]
    bid_wall_sz = ob["bid_wall_sz"]
    ask_wall_px = ob["ask_wall_px"]
    ask_wall_sz = ob["ask_wall_sz"]
    spike_status = eng["last_spike_status"]
    spike_box_bg = eng["last_spike_color"]
    alert_id = eng["last_spike_alert_id"]
    alert_dir = eng["last_spike_dir"]

    max_rec = eng.get("max_spread_record", {
        "spread": 0.0,
        "time": "--:--:--",
        "price": 0.0,
        "signal": "अभी कोई रिकॉर्ड नहीं",
        "color": "#94a3b8"
    })
    peak_sp_val = max_rec["spread"]
    peak_sp_time = max_rec["time"]
    peak_sp_price = max_rec["price"]
    peak_sp_sig = max_rec["signal"]
    peak_sp_col = max_rec["color"]

    audio_autoplay_html = ""
    if time.time() - eng["last_spike_alert_ts"] <= 4.0 and alert_id > 0:
        wav_b64 = BUY_BEEP_B64 if alert_dir == 1 else SELL_BEEP_B64
        audio_autoplay_html = f'<audio autoplay="true" src="data:audio/wav;base64,{wav_b64}"></audio>'

    gate_col = "#22c55e" if spread_gate_open else "#facc15"
    delta_col = "#4ade80" if taker_net_delta >= 0 else "#f87171"

    tot_trades = eng["wins"] + eng["losses"]
    win_rate = (float(eng["wins"]) / float(tot_trades) * 100.0) if tot_trades > 0 else 0.0
    net_pnl = eng["gross_profit"] - eng["gross_loss"] - eng["total_brok"]

    st_badge_text = "STATUS: BUY 🟢" if st_trend == 1 else "STATUS: SELL 🔴"
    st_badge_col = "#00c891" if st_trend == 1 else "#f03769"

    if eng["trade_dir"] != 0:
        t_type = "LONG" if eng["trade_dir"] == 1 else "SHORT"
        entry = eng["entry_price"]
        tp1 = eng["tp1_price"]
        tp2 = eng["tp2_price"]
        sl = eng["stop_price"]
        open_qty = eng["open_qty"]
        booked_pnl = eng["booked_pnl_10q"]

        unit_pnl = (price - entry) if t_type == "LONG" else (entry - price)
        open_pnl = unit_pnl * open_qty
        total_live_pnl = booked_pnl + open_pnl

        pnl_color = "#22c55e" if total_live_pnl >= 0 else "#ef4444"
        badge_bg = "#00af6e" if t_type == "LONG" else "#dc284b"

        if eng["tp2_reached"]:
            status_label = f"🚀 3Q TRAILING ABOVE TP2 ({t_type}) | 7Q Booked"
            sl_tag = "Trail SL (3Q)"
        elif eng["mid_reached"]:
            status_label = f"🔒 7Q TP1 BOOKED • 3Q SL AT TP1 ({t_type})"
            sl_tag = "SL @ TP1 (3Q)"
        elif eng["tp1_reached"]:
            status_label = f"✅ 7Q TP1 BOOKED • 3Q PROFIT-LOCKED ({t_type})"
            sl_tag = "Profit SL (3Q)"
        else:
            status_label = f"🔥 ACTIVE {t_type} (10 Qty Open | {eng['entry_tag']} @ {eng['entry_time_str']})"
            sl_tag = "Anti-Wick SL (10Q)"

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:15px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
<span style="background:{badge_bg}; color:white; padding:5px 11px; border-radius:6px; font-weight:bold; font-size:13px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:800;">{total_live_pnl:+,.1f} pts</span>
</div>
<div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:10px; background:#0b1324; padding:6px 10px; border-radius:6px; flex-wrap:wrap; gap:6px;">
<span>📦 Open Qty: <b style="color:#f8fafc;">{open_qty}/10</b></span>
<span>💰 Booked (7Q @ TP1): <b style="color:#4ade80;">+{booked_pnl:,.1f}p</b></span>
<span>⚡ Runner ({open_qty}Q): <b style="color:{pnl_color};">{open_pnl:+,.1f}p</b></span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; color:#cbd5e1; font-size:12px; background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
<div>Entry (10Q)<br><b style="color:#ffffff; font-size:14px;">{entry:,.1f}</b></div>
<div>TP1 (Book 7Q)<br><b style="color:#22c55e; font-size:14px;">{tp1:,.1f}</b></div>
<div>TP2 (Trail 3Q)<br><b style="color:#38bdf8; font-size:14px;">{tp2:,.1f}</b></div>
<div>{sl_tag}<br><b style="color:#ef4444; font-size:14px;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        lock_note = "🔒 Same-Trend Re-Entry Locked (Waiting Next ST Flip)" if eng["trend_tp1_done"] else "🟢 Ready for Signal"
        trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR CONFIRMED SIGNAL (DIVISOR 15 • ONE-SHOT TREND LOCK)</div>
<div style="color:#facc15; font-size:12px; margin-top:4px; font-weight:bold;">{lock_note}</div>
<div style="color:#94a3b8; font-size:12px; margin-top:3px;">Supertrend: <b>{st_line:,.1f}</b> | Streak: <b>#{brick_streak}</b> | EMA21: <b>{ema21:,.1f}</b> | RSI: <b>{rsi14:.1f}</b></div>
</div>"""

    spike_rows_html = ""
    if not eng["spike_history"]:
        spike_rows_html = f"""<tr><td colspan="5" style="text-align:center; padding:12px; color:#64748b;">अभी तक कोई $8.0+ Pro 3-Engine स्पाइक (Spread ≥ ${req_spread:.1f}) ट्रिगर नहीं हुआ है</td></tr>"""
    else:
        for sh in eng["spike_history"]:
            mv_col = "#4ade80" if sh["max_fav"] >= 25.0 else ("#f87171" if sh["curr_move"] < 0 else "#cbd5e1")
            if sh.get("locked", False):
                eval_txt = f"🔒 Max: +{sh['max_fav']:.1f}p (3m Close: {sh['curr_move']:+.1f}p)"
            else:
                eval_txt = f"⏱️ {sh.get('rem_sec', 0)}s | Max: +{sh['max_fav']:.1f}p (Now: {sh['curr_move']:+.1f}p)"
            spike_rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:11.5px;">
<td style="padding:6px 5px; color:#94a3b8;">{sh['time']}</td>
<td style="padding:6px 5px; color:#f8fafc; font-weight:600;">${sh['price']:,.1f}</td>
<td style="padding:6px 5px; color:#facc15;">{sh['spread_info']}</td>
<td style="padding:6px 5px; color:{sh['color']}; font-weight:bold;">{sh['direction']}</td>
<td style="padding:6px 5px; color:{mv_col}; font-weight:bold; text-align:right;">{eval_txt}</td>
</tr>"""

    rows_html = ""
    if not eng["history"]:
        rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी कोई ट्रेड क्लोज नहीं हुआ है</td></tr>"""
    else:
        for h in eng["history"]:
            h_col = h.get("color", "#22c55e")
            rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12px;">
<td style="padding:8px 6px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 6px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 6px; color:#cbd5e1;">{h['entry']:,.1f} → {h['exit']:,.1f}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold; text-align:right;">{h['pnl']} pts</td>
</tr>"""

    net_color = "#00e676" if net_pnl >= 0 else "#ff5252"
    wr_color = "#00e676" if win_rate >= 60.0 else "#facc15"
    setup_str = f"TP1(7Q): +{box_size * TP1_BRICKS:.0f}p | TP2(3Q): +{box_size * TP2_BRICKS:.0f}p | Max SL Cap: -{box_size * MAX_SL_LOSS_BRICKS:.0f}p"

    raw_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; border:1px solid #1e293b; box-shadow:0 8px 30px rgba(0,0,0,0.6); font-family:sans-serif;">
<div id="hl-spike-audio-hook" data-alert-id="{alert_id}" data-alert-dir="{alert_dir}" style="display:none;"></div>
{audio_autoplay_html}
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
<div>
<div style="font-size:12px; color:#38bdf8; font-weight:700;">⚡ DR DEVENDRA AI-RENKO PRO [DIVISOR 15 MEDIUM BRICK • ONE-SHOT LOCK]</div>
<div style="font-size:34px; font-weight:800; color:#ffffff; line-height:1.15;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="background:#1e293b; border:1px solid {st_badge_col}; color:{st_badge_col}; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:inline-block; margin-bottom:4px;">{st_badge_text}</div>
<div style="font-size:11.5px; color:#cbd5e1;">🔒 Grid Anchor: {anchor_str} ({bar_count} Bars) | {ist_time}</div>
</div>
</div>
<div class="t-grid">
<div>
<div style="margin-bottom:14px; background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
<div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:6px;">
<span style="color:#22c55e;">🟢 3-Bar Candle Flow: {buy_pct}%</span>
<span style="color:#e2e8f0;">Imbalance: {imbalance:+.2f}</span>
<span style="color:#ef4444;">Sell Flow: {sell_pct}% 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:12px; border-radius:6px; overflow:hidden;">
<div style="width:{buy_pct}%; background:#22c55e; height:100%;"></div>
</div>
</div>

{trade_box_html}

<!-- PRO 3-ENGINE PRE-SPIKE DIRECTION RADAR BOX (STEP-IN + TAKER CVD + TOP-3) -->
<div style="background:#1e293b; border:2px solid #38bdf8; border-radius:12px; padding:14px; margin-bottom:14px; box-shadow:0 4px 15px rgba(56,189,248,0.15);">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
<span style="font-size:13px; font-weight:bold; color:#38bdf8;">📡 PRO 3-ENGINE PRE-SPIKE RADAR (STEP-IN + TAKER CVD + TOP-3)</span>
<span style="font-size:12px; color:{gate_col}; font-weight:800;">{gate_status_txt}</span>
</div>

<!-- 🏆 PEAK SPREAD HIGH-WATER MARK BANNER -->
<div style="background:linear-gradient(90deg, #0f172a, #1e1b4b); border:1.5px solid #eab308; border-radius:8px; padding:8px 11px; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:3px;">
<span style="font-size:12px; font-weight:800; color:#facc15;">🏆 अब तक का सर्वोच्च स्प्रेड (Max Spread): <span style="font-size:15px; color:#ffffff;">${peak_sp_val:.1f}</span></span>
<span style="font-size:11.5px; color:#cbd5e1;">🕒 समय: <b style="color:#f8fafc;">{peak_sp_time}</b> | प्राइस: <b style="color:#38bdf8;">${peak_sp_price:,.1f}</b></span>
</div>
<div style="font-size:11.5px; color:#94a3b8;">
उस समय का सिग्नल / झुकाव: <b style="color:{peak_sp_col};">{peak_sp_sig}</b>
</div>
</div>

<!-- ENGINE 1: SPREAD & VACUUM STEP-IN -->
<div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:6px; background:#0b1324; padding:7px 10px; border-radius:6px; flex-wrap:wrap; gap:6px;">
<span>📏 Spread: <b style="color:#facc15;">${spread:.1f}</b> (Norm: ${normal_spread:.1f})</span>
<span>👣 Bid Step-In: <b style="color:#4ade80;">+${bid_step_in:.1f}</b> (Ask Pull: +${ask_jump:.1f})</span>
<span>👣 Ask Step-Dn: <b style="color:#f87171;">-${ask_step_dn:.1f}</b> (Bid Drop: -${bid_drop:.1f})</span>
</div>

<!-- ENGINE 2: AGGRESSIVE TAKER TRADES (MARKET BUY VS MARKET SELL CVD) -->
<div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:5px; background:#0b1324; padding:6px 10px; border-radius:6px; flex-wrap:wrap; gap:6px;">
<span>⚡ Taker Market Buy: <b style="color:#22c55e;">{taker_buy_pct:.1f}% ({taker_buy_v:.2f} BTC)</b></span>
<span>⚡ Net CVD: <b style="color:{delta_col};">{taker_net_delta:+.2f} BTC</b></span>
<span>⚡ Taker Market Sell: <b style="color:#ef4444;">{taker_sell_pct:.1f}% ({taker_sell_v:.2f} BTC)</b></span>
</div>
<div style="width:100%; background:#ef4444; height:8px; border-radius:4px; overflow:hidden; margin-bottom:7px;">
<div style="width:{taker_buy_pct}%; background:#22c55e; height:100%;"></div>
</div>

<!-- ENGINE 3: TOP-3 NEAR-TOUCH BOOK VS TOP-15 DEPTH -->
<div style="display:flex; justify-content:space-between; font-size:11.5px; color:#cbd5e1; margin-bottom:8px; background:#0f172a; padding:6px 10px; border-radius:6px; flex-wrap:wrap; gap:6px;">
<span>🎯 Top-3 Touch Book: <b style="color:#4ade80;">Bid {top3_bid_pct:.0f}% ({bid_vol_3:.1f}B)</b> / <b style="color:#f87171;">Ask {top3_ask_pct:.0f}% ({ask_vol_3:.1f}B)</b></span>
<span>🛡️ Whale Walls: <b style="color:#4ade80;">B ${bid_wall_px:,.0f} ({bid_wall_sz:.1f}B)</b> | <b style="color:#f87171;">S ${ask_wall_px:,.0f} ({ask_wall_sz:.1f}B)</b></span>
</div>

<div style="background:{spike_box_bg}; color:#ffffff; padding:9px; border-radius:8px; font-size:12px; font-weight:bold; text-align:center; border:1px solid #334155; margin-bottom:10px;">
{spike_status}
</div>
<div style="font-size:12px; font-weight:bold; color:#cbd5e1; margin-bottom:6px;">📜 Pro 3-Engine Pre-Spike History (Spread ≥ $8 + Step-In + Taker CVD + Top-3)</div>
<div style="max-height:150px; overflow-y:auto;">
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:5px;">समय</th>
<th style="padding:5px;">सिग्नल प्राइस</th>
<th style="padding:5px;">स्प्रेड (Taker%)</th>
<th style="padding:5px;">प्रो प्री-स्पाइक दिशा</th>
<th style="padding:5px; text-align:right;">3-Min मूव (Auto-Lock)</th>
</tr>
</thead>
<tbody>
{spike_rows_html}
</tbody>
</table>
</div>
</div>

<div style="background:{eng['last_result_color']}; color:#ffffff; padding:10px 14px; border-radius:8px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:14px;">
पिछला परिणाम: {eng['last_result']}
</div>
<div style="background:#1e293b; border-radius:12px; padding:12px; border:1px solid #334155;">
<div style="font-size:13px; font-weight:bold; color:#38bdf8; margin-bottom:8px;">📊 10-QTY MASTER BACKTEST TABLE (Divisor 15 • One-Shot Trend Lock • 7Q TP1)</div>
<table style="width:100%; border-collapse:collapse; font-size:13px;">
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Daily ATR-5 | 1 Brick (Div 15)</td><td style="padding:6px; color:#facc15; font-weight:bold; text-align:right;">{safe_range:,.1f} pts | Brick: {box_size:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Position Sizing Rule</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">10 Qty (7Q @ 0.85B TP1 + One-Shot Lock)</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Per-Qty Levels</td><td style="padding:6px; color:#38bdf8; font-weight:bold; text-align:right;">{setup_str}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Total Trades (W / L)</td><td style="padding:6px; color:#ffffff; font-weight:bold; text-align:right;">{tot_trades} ({eng['wins']}W / {eng['losses']}L)</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Win Rate % | TP2 Runners</td><td style="padding:6px; color:{wr_color}; font-weight:bold; text-align:right;">{win_rate:.1f}% | 🚀 Runners: {eng['tp2_hits']}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Profit (10 Qty)</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">+{eng['gross_profit']:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Loss (10 Qty)</td><td style="padding:6px; color:#f87171; font-weight:bold; text-align:right;">-{eng['gross_loss']:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Brokerage/Tax (10 Qty)</td><td style="padding:6px; color:#fca5a5; font-weight:bold; text-align:right;">-{eng['total_brok']:,.1f} pts</td></tr>
<tr style="background:#0f172a;"><td style="padding:8px 6px; color:#ffffff; font-weight:bold;">NET PROFIT (10 Qty Total)</td><td style="padding:8px 6px; color:{net_color}; font-weight:800; font-size:15px; text-align:right;">{net_pnl:+,.1f} pts</td></tr>
</table>
</div>
</div>
<div>
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155; height:100%; box-sizing:border-box;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<span style="font-size:14px; font-weight:bold; color:#f8fafc;">📜 10-Qty ट्रेड इतिहास लॉग (3.5-Day Fixed Grid)</span>
<span style="font-size:11px; color:#94a3b8;">Blocked Late: {eng['blocked_late']}</span>
</div>
<div style="max-height:460px; overflow-y:auto;">
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:6px;">तारीख व समय</th>
<th style="padding:6px;">ट्रेड</th>
<th style="padding:6px;">Entry → Exit</th>
<th style="padding:6px;">स्टेटस</th>
<th style="padding:6px; text-align:right;">10Q PnL</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
</div>
</div>
</div>
</div>"""

    clean_html = "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())
    terminal.markdown(clean_html, unsafe_allow_html=True)
    time.sleep(2)

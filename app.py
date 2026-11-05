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
import hmac
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="AI-Renko Pro & Pre-Spike Terminal", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; }
.block-container { padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
.t-grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
@media (min-width: 960px) { .t-grid { grid-template-columns: 1.15fr 0.85fr; } }

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
# DELTA EXCHANGE DEMO API & SERVER IP HELPER (RENKO ONLY ACTIVE, SPIKE OFF)
# ============================================================================
DELTA_API_KEY    = "m9deE36P5CmkezL8JJkJ4s9WhbFTs"
DELTA_API_SECRET = "sqRjTWnvB8WpqYlEJTCRZVP46OdbiaEUyeKLWLRXtxdvdlcWL6sBgFH2E7eC"
DELTA_URLS       = [
    "https://cdn-ind.testnet.deltaex.org",
    "https://testnet-api.delta.exchange"
]

@st.cache_data(ttl=300)
def get_server_public_ip():
    for url in ["https://api.ipify.org", "https://ipv4.icanhazip.com", "https://checkip.amazonaws.com"]:
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception:
            pass
    return "IP लोड हो रहा है..."

def delta_request(method, path, payload_dict=None):
    body_str = json.dumps(payload_dict, separators=(',', ':')) if payload_dict else ""
    last_err = ""
    for base_url in DELTA_URLS:
        try:
            timestamp = str(int(time.time()))
            sig_data = method.upper() + timestamp + path + body_str
            signature = hmac.new(
                DELTA_API_SECRET.encode("utf-8"),
                sig_data.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            headers = {
                "api-key": DELTA_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "python-rest-client"
            }
            url = base_url + path
            if method.upper() == "GET":
                r = requests.get(url, headers=headers, timeout=5)
            else:
                r = requests.post(url, data=body_str, headers=headers, timeout=5)
            if r.status_code == 200:
                return True, r.json()
            last_err = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
    return False, last_err

def place_delta_demo_order(eng, side, qty, tag="Renko", reduce_only=False):
    if not eng.get("initialized", False) or qty <= 0:
        return False
    try:
        prod_id = eng.get("delta_btc_product_id", 27)
        payload = {
            "product_id": int(prod_id),
            "size": int(qty),
            "side": side.lower(),
            "order_type": "market_order"
        }
        if reduce_only:
            payload["reduce_only"] = True
        ok, resp = delta_request("POST", "/v2/orders", payload)
        ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
        if ok:
            eng["delta_status"] = f"✅ [{ist_now}] Delta Demo {tag}: {side.upper()} {qty} Qty सफल!"
        else:
            eng["delta_status"] = f"⚠️ [{ist_now}] Delta {tag} ({side.upper()} {qty}Q) अटका: {resp}"
        return ok
    except Exception as e:
        eng["delta_status"] = f"⚠️ Delta Error: {str(e)}"
        return False

def init_delta_product_id(eng):
    for base_url in DELTA_URLS:
        try:
            r = requests.get(base_url + "/v2/products", timeout=5)
            if r.status_code == 200:
                items = r.json().get("result", [])
                for p in items:
                    sym = str(p.get("symbol", "")).upper()
                    if sym in ["BTCUSD", "BTCUSDT"]:
                        eng["delta_btc_product_id"] = int(p["id"])
                        return
        except Exception:
            pass

# ============================================================================
# IN-MEMORY WAV BEEP GENERATOR
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

BUY_BEEP_B64  = build_beep_wav_b64([880, 1175, 1568, 1568])
SELL_BEEP_B64 = build_beep_wav_b64([987, 740, 523, 523])

# ============================================================================
# 10-QTY SETUP (7Q @ 300p TP1 + 3Q RUNNER WITH ₹100 STEP TRAIL & 250p SL)
# ============================================================================
TOTAL_QTY            = 10     
TP1_BOOK_QTY         = 7      # 7 लॉट TP1 पर बुक होंगे
RUNNER_QTY           = 3      # 3 लॉट बची हुई क्वांटिटी (रनर) ट्रेल होंगी

USD_INR_RATE         = 85.0   

# 🎯 आपके नए सटीक नियम (1m टाइमफ्रेम के अनुकूल):
TP1_TARGET_PTS       = 300.0  # TP1: 300 पॉइंट्स पर 7 लॉट (70%) तुरंत बुक
INITIAL_SL_PTS       = 250.0  # शुरुआती स्टॉप-लॉस: 250 पॉइंट्स (~₹210 नुकसान जोखिम)
TRAIL_STEP_PTS       = 118.0  # TP1 के बाद हर ₹100 (118 BTC pts) ऊपर जाने पर SL ₹100 ऊपर खिसकेगा
ANTI_WICK_SL         = True

USE_STREAK_FILTER    = True
MAX_BRICK_STREAK     = 2
USE_STRETCH_FILTER   = True
MAX_EMA_DIST_BRICKS  = 1.1

USE_AUTO_BOX         = True
ATR_PERIOD           = 5
RANGE_DIVISOR        = 15.0
MANUAL_BOX           = 120.0

ST_FACTOR            = 3.0
USE_GAUSSIAN         = True
GAUSS_PERIOD         = 20
SIG_MODE             = "Supertrend + Brick-Step Re-Entry (Best)"
MIN_VOL_DOM          = 55.0

# REAL DELTA EXCHANGE FEE (82.1 Points Per Lot -> 821.0 pts / ~₹70 for 10 Lots)
BROK_PER_QTY         = 82.1
MINTICK              = 0.1

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

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

def fmt_inr(lot_pts):
    val = pts_to_inr(lot_pts)
    return f"{val:+,.0f}" if val != 0 else "0"

def fetch_hl_klines(interval="1m", num_bars=20):
    tf_ms_map = {"1m": 60 * 1000, "5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000, "1d": 24 * 60 * 60 * 1000}
    step_ms = tf_ms_map.get(interval, 60000)
    end_time = int(time.time() * 1000)
    start_time = end_time - (num_bars * step_ms)

    for attempt in range(3):
        try:
            r = requests.post(HYPERLIQUID_INFO_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": interval, "startTime": start_time, "endTime": end_time}}, headers={"Content-Type": "application/json"}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    data.sort(key=lambda x: int(x["t"]))
                    klines = []
                    for k in data:
                        t_ms = int(k["t"])
                        o_val, h_val, l_val, c_val = float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])
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
    if now_ms > mid_ms: chunks.append((mid_ms, now_ms))

    merged = {}
    for st_ms, en_ms in chunks:
        for attempt in range(3):
            try:
                r = requests.post(HYPERLIQUID_INFO_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": st_ms, "endTime": en_ms}}, headers={"Content-Type": "application/json"}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        for k in data:
                            t_ms = int(k["t"])
                            if t_ms >= anchor_start_ms:
                                o_val, h_val, l_val, c_val = float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])
                                v_raw = float(k.get("v", 0.0))
                                v_safe = v_raw if v_raw > 0 else max(0.01, (h_val - l_val) * 0.1)
                                merged[t_ms] = [t_ms, o_val, h_val, l_val, c_val, v_safe]
                        break
            except Exception:
                time.sleep(0.5)

    if not merged: return None
    return [merged[t] for t in sorted(merged.keys())]

def calc_daily_atr5(klines_1d):
    if not klines_1d or len(klines_1d) < ATR_PERIOD + 2: return None
    highs, lows, closes = [float(k[2]) for k in klines_1d], [float(k[3]) for k in klines_1d], [float(k[4]) for k in klines_1d]
    tr = [0.0] * len(closes)
    for i in range(len(closes)):
        if i == 0: tr[i] = highs[i] - lows[i]
        else: tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    rma = [0.0] * len(tr)
    for i, v in enumerate(tr):
        if i < ATR_PERIOD - 1: rma[i] = sum(tr[:i + 1]) / float(i + 1)
        elif i == ATR_PERIOD - 1: rma[i] = sum(tr[:ATR_PERIOD]) / float(ATR_PERIOD)
        else: rma[i] = (rma[i - 1] * (ATR_PERIOD - 1) + v) / float(ATR_PERIOD)
    return rma[-2]

def process_single_closed_bar(eng, kline):
    bar_time = int(kline[0])
    if bar_time <= eng["last_bar_time"]: return

    o, h, l, c, v = float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4]), float(kline[5])
    bar_ist = (datetime.utcfromtimestamp(bar_time / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M %p")
    idx = eng["bar_count"]

    if idx == 0: eng["atr14"] = h - l
    else:
        prev_c = eng["prev_close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        if idx < 14:
            eng["tr_sum"] += tr
            eng["atr14"] = eng["tr_sum"] / float(idx + 1)
        else:
            eng["atr14"] = (eng["atr14"] * 13.0 + tr) / 14.0

    if idx == 0: eng["ema21"] = c
    else:
        k_ema = 2.0 / 22.0
        eng["ema21"] = c * k_ema + eng["ema21"] * (1.0 - k_ema)

    if idx == 0: eng["rsi14"] = 50.0
    else:
        diff = c - eng["prev_close"]
        up, dn = max(diff, 0.0), max(-diff, 0.0)
        if idx < 14:
            eng["up_sum"] += up
            eng["dn_sum"] += dn
            eng["rma_up"] = eng["up_sum"] / float(idx)
            eng["rma_dn"] = eng["dn_sum"] / float(idx)
        else:
            eng["rma_up"] = (eng["rma_up"] * 13.0 + up) / 14.0
            eng["rma_dn"] = (eng["rma_dn"] * 13.0 + dn) / 14.0

        if eng["rma_dn"] == 0: eng["rsi14"] = 100.0
        elif eng["rma_up"] == 0: eng["rsi14"] = 0.0
        else:
            rs = eng["rma_up"] / eng["rma_dn"]
            eng["rsi14"] = 100.0 - (100.0 / (1.0 + rs))

    w = (2.0 * math.pi) / float(GAUSS_PERIOD)
    b = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a = -b + math.sqrt(b * b + 2.0 * b)
    if idx == 0: g_val = c
    elif idx == 1: g_val = (a ** 2) * c + 2.0 * (1.0 - a) * eng["g1"] - ((1.0 - a) ** 2) * c
    else: g_val = (a ** 2) * c + 2.0 * (1.0 - a) * eng["g1"] - ((1.0 - a) ** 2) * eng["g2"]
    eng["g2"] = eng["g1"]
    eng["g1"] = g_val

    rng = max(h - l, MINTICK)
    u_wick, l_wick, body = h - max(o, c), min(o, c) - l, abs(c - o)
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
    box_size = max(safe_range / RANGE_DIVISOR if USE_AUTO_BOX else MANUAL_BOX, MINTICK * 2.0)
    eng["safe_range"] = safe_range
    eng["box_size"] = box_size

    eval_price = (c * 0.70 + g_val * 0.30) if USE_GAUSSIAN else c
    brick_step_up, brick_step_dn = False, False

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
    raw_supp, raw_res = r_close - band_dist, r_close + band_dist
    prev_trend, prev_supp, prev_res = eng["st_trend"], eng["support_band"], eng["resistance_band"]

    if prev_supp is None: eng["support_band"] = raw_supp
    elif prev_trend == 1: eng["support_band"] = raw_supp if (eng["brick_dir"] == 1 and raw_supp > prev_supp) else prev_supp
    else: eng["support_band"] = raw_supp

    if prev_res is None: eng["resistance_band"] = raw_res
    elif prev_trend == -1: eng["resistance_band"] = raw_res if (eng["brick_dir"] == -1 and raw_res < prev_res) else prev_res
    else: eng["resistance_band"] = raw_res

    if prev_trend == -1 and eng["brick_dir"] == 1 and prev_res is not None and r_close > prev_res:
        eng["st_trend"] = 1
        eng["support_band"] = r_close - band_dist
    elif prev_trend == 1 and eng["brick_dir"] == -1 and prev_supp is not None and r_close < prev_supp:
        eng["st_trend"] = -1
        eng["resistance_band"] = r_close + band_dist
    else:
        eng["st_trend"] = prev_trend

    eng["st_line"] = eng["support_band"] if eng["st_trend"] == 1 else eng["resistance_band"]
    st_flip_buy, st_flip_sell = (eng["st_trend"] == 1 and prev_trend == -1), (eng["st_trend"] == -1 and prev_trend == 1)

    if st_flip_buy or st_flip_sell:
        eng["brick_streak"] = 1
        eng["trend_tp1_done"] = False
    if st_flip_buy: eng["pending_flip_buy"], eng["pending_flip_sell"] = True, False
    if st_flip_sell: eng["pending_flip_sell"], eng["pending_flip_buy"] = True, False
    if eng["st_trend"] == -1: eng["pending_flip_buy"] = False
    if eng["st_trend"] == 1: eng["pending_flip_sell"] = False

    # ========================================================================
    # MANAGE ACTIVE TRADE (7Q @ 300p TP1 + 3Q STEP TRAIL & 250p SL)
    # ========================================================================
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        close_side = "sell" if t_dir == 1 else "buy"
        eng["max_fav_price"] = max(eng["max_fav_price"], h) if t_dir == 1 else min(eng["max_fav_price"], l)

        # 1. Hit TP1 (300 Points) -> Book 7 क़ॉन्टीटी (70%) तुरंत!
        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["trend_tp1_done"] = True
            eng["wins"] += 1
            eng["booked_pnl_10q"] = TP1_TARGET_PTS * TP1_BOOK_QTY
            eng["gross_profit"] += eng["booked_pnl_10q"]
            eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
            eng["open_qty"] = RUNNER_QTY
            # TP1 हिट होते ही बची हुई 3 Qty का SL एंट्री प्राइस (Cost) पर लॉक हो जाएगा
            eng["stop_price"] = eng["entry_price"]
            place_delta_demo_order(eng, close_side, TP1_BOOK_QTY, tag=f"Renko TP1 ({TP1_BOOK_QTY}Q)", reduce_only=True)

        # 2. Step-Trailing for 3 Qty Runner: Every +₹100 (118 pts) above TP1 shifts SL up by +₹100 (118 pts)
        if eng["tp1_reached"]:
            max_fav_move = (eng["max_fav_price"] - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - eng["max_fav_price"])
            
            if max_fav_move >= TP1_TARGET_PTS + TRAIL_STEP_PTS:
                steps_above_tp1 = int(math.floor((max_fav_move - TP1_TARGET_PTS) / TRAIL_STEP_PTS))
                if not eng["tp2_reached"]:
                    eng["tp2_reached"] = True
                    eng["mid_reached"] = True
                    eng["tp2_hits"] += 1
                eng["trail_steps"] = steps_above_tp1

                # SL moves up by 118 pts for every 118 pts move above TP1
                step_locked_pts = TP1_TARGET_PTS + ((steps_above_tp1 - 1) * TRAIL_STEP_PTS)
                step_sl = (eng["entry_price"] + step_locked_pts) if t_dir == 1 else (eng["entry_price"] - step_locked_pts)
                eng["stop_price"] = max(eng["stop_price"], step_sl) if t_dir == 1 else min(eng["stop_price"], step_sl)
                eng["tp2_price"] = (eng["entry_price"] + TP1_TARGET_PTS + (steps_above_tp1 * TRAIL_STEP_PTS)) if t_dir == 1 else (eng["entry_price"] - TP1_TARGET_PTS - (steps_above_tp1 * TRAIL_STEP_PTS))

            close_hit_runner_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
            st_reversed = (eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)

            if (close_hit_runner_sl or st_reversed) and not hit_tp1_now:
                exit_p = max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"])
                runner_pts = max(0.0, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                runner_pnl = runner_pts * RUNNER_QTY
                eng["gross_profit"] += runner_pnl
                total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl
                net_trade_pts = total_trade_pnl - (BROK_PER_QTY * TOTAL_QTY)

                if eng["tp2_reached"]:
                    status_tag = f"🚀 {TP1_BOOK_QTY}Q TP1 + {RUNNER_QTY}Q TRAIL (Step #{eng.get('trail_steps', 1)})"
                    row_col = "#38bdf8"
                    box_col = "#0369a1"
                else:
                    status_tag = f"✅ {TP1_BOOK_QTY}Q TP1 + {RUNNER_QTY}Q COST-LOCK"
                    row_col = "#22c55e"
                    box_col = "#166534"

                eng["last_result"] = f"{status_tag}: +{fmt_pts(total_trade_pnl)} pts (Net: ₹{fmt_inr(net_trade_pts)})"
                eng["last_result_color"] = box_col
                eng["history"].insert(0, {"time": bar_ist, "type": f"{t_label} ({TOTAL_QTY}Q)", "entry": eng["entry_price"], "exit": exit_p, "status": status_tag, "pnl": f"+{fmt_pts(total_trade_pnl)} (₹{fmt_inr(net_trade_pts)})", "color": row_col})
                eng["history"] = eng["history"][:40]
                place_delta_demo_order(eng, close_side, RUNNER_QTY, tag=f"Renko Runner Exit ({RUNNER_QTY}Q)", reduce_only=True)
                eng["trade_dir"] = 0
                eng["open_qty"] = 0

        # 3. Initial Stop-Loss (250 Points) before TP1
        if eng["trade_dir"] != 0 and not eng["tp1_reached"]:
            adverse_close_pts = (eng["entry_price"] - c) if t_dir == 1 else (c - eng["entry_price"])
            close_hit_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
            st_turned_bad = ((eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)) and (adverse_close_pts > 0)
            hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

            sl_triggered = (close_hit_sl or st_turned_bad or hard_crash) if ANTI_WICK_SL else ((l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"]))

            if sl_triggered:
                eng["losses"] += 1
                loss_per_qty = INITIAL_SL_PTS
                total_loss_all_q = loss_per_qty * TOTAL_QTY
                eng["gross_loss"] += total_loss_all_q
                eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
                net_loss_pts = -(total_loss_all_q + (BROK_PER_QTY * TOTAL_QTY))

                eng["last_result"] = f"🛑 SL Hit ({TOTAL_QTY}Q): -{fmt_pts(total_loss_all_q)} pts (Net: ₹{fmt_inr(net_loss_pts)})"
                eng["last_result_color"] = "#991b1b"
                eng["history"].insert(0, {"time": bar_ist, "type": f"{t_label} ({TOTAL_QTY}Q)", "entry": eng["entry_price"], "exit": c, "status": f"🛑 SL HIT ({TOTAL_QTY}Q)", "pnl": f"-{fmt_pts(total_loss_all_q)} (₹{fmt_inr(net_loss_pts)})", "color": "#ef4444"})
                eng["history"] = eng["history"][:40]
                place_delta_demo_order(eng, close_side, TOTAL_QTY, tag=f"Renko SL Exit ({TOTAL_QTY}Q)", reduce_only=True)
                eng["trade_dir"] = 0
                eng["open_qty"] = 0
                eng["trend_tp1_done"] = True

    ema21, rsi_val = eng["ema21"], eng["rsi14"]
    candle_not_giant = (h - l) <= box_size * 1.75
    flip_stretch_ok  = abs(c - ema21) <= box_size * 1.65
    bull_filter_ok   = candle_not_giant and flip_stretch_ok and buy_dom_pct >= 52.0 and rsi_val < 72.0
    bear_filter_ok   = candle_not_giant and flip_stretch_ok and sell_dom_pct >= 52.0 and rsi_val > 28.0

    trigger_flip_buy  = eng["pending_flip_buy"] and eng["st_trend"] == 1 and eng["brick_dir"] == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and eng["st_trend"] == -1 and eng["brick_dir"] == -1 and bear_filter_ok and c < o

    allow_re_entry = (SIG_MODE == "Supertrend + Brick-Step Re-Entry (Best)")
    raw_cont_buy   = allow_re_entry and (not trigger_flip_buy) and eng["st_trend"] == 1 and eng["brick_dir"] == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and 51.0 < rsi_val < 68.0 and candle_not_giant
    raw_cont_sell  = allow_re_entry and (not trigger_flip_sell) and eng["st_trend"] == -1 and eng["brick_dir"] == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and 32.0 < rsi_val < 49.0 and candle_not_giant

    streak_ok   = (not USE_STREAK_FILTER) or (eng["brick_streak"] <= MAX_BRICK_STREAK)
    stretch_ok  = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
    one_shot_ok = not eng["trend_tp1_done"]
    late_safe   = streak_ok and stretch_ok and one_shot_ok

    trigger_cont_buy  = raw_cont_buy and late_safe
    trigger_cont_sell = raw_cont_sell and late_safe
    can_open_trade = (eng["trade_dir"] == 0) or (eng["tp1_reached"] and (st_flip_buy or st_flip_sell))

    if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            old_close_side = "sell" if eng["trade_dir"] == 1 else "buy"
            runner_pts = max(0.0, (c - eng["entry_price"]) if eng["trade_dir"] == 1 else (eng["entry_price"] - c))
            runner_pnl = runner_pts * RUNNER_QTY
            eng["gross_profit"] += runner_pnl
            tot_flip_pnl = eng["booked_pnl_10q"] + runner_pnl
            net_flip_pts = tot_flip_pnl - (BROK_PER_QTY * TOTAL_QTY)
            eng["history"].insert(0, {"time": bar_ist, "type": f"{old_label} ({TOTAL_QTY}Q)", "entry": eng["entry_price"], "exit": c, "status": f"✅ {TP1_BOOK_QTY}Q TP1 + {RUNNER_QTY}Q FLIP", "pnl": f"+{fmt_pts(tot_flip_pnl)} (₹{fmt_inr(net_flip_pts)})", "color": "#22c55e"})
            eng["history"] = eng["history"][:40]
            place_delta_demo_order(eng, old_close_side, RUNNER_QTY, tag=f"Renko Flip Close ({RUNNER_QTY}Q)", reduce_only=True)

        is_long = trigger_flip_buy or trigger_cont_buy
        if is_long: eng["pending_flip_buy"] = False
        else: eng["pending_flip_sell"] = False

        eng["trade_dir"] = 1 if is_long else -1
        eng["entry_bar"] = idx
        eng["entry_price"] = c
        eng["max_fav_price"] = c
        eng["tp1_reached"] = False
        eng["mid_reached"] = False
        eng["tp2_reached"] = False
        eng["trail_steps"] = 0
        eng["open_qty"] = TOTAL_QTY
        eng["booked_pnl_10q"] = 0.0
        eng["entry_tag"] = f"🧱 Brick #{eng['brick_streak']}" if (trigger_cont_buy or trigger_cont_sell) else "🔥 ST Flip"
        eng["entry_time_str"] = bar_ist

        eng["tp1_price"] = (c + TP1_TARGET_PTS) if is_long else (c - TP1_TARGET_PTS)
        eng["tp2_price"] = (eng["tp1_price"] + TRAIL_STEP_PTS) if is_long else (eng["tp1_price"] - TRAIL_STEP_PTS)
        eng["stop_price"] = (c - INITIAL_SL_PTS) if is_long else (c + INITIAL_SL_PTS)
        eng["hard_stop_price"] = (eng["stop_price"] - box_size * 0.35) if is_long else (eng["stop_price"] + box_size * 0.35)

        entry_side = "buy" if is_long else "sell"
        place_delta_demo_order(eng, entry_side, TOTAL_QTY, tag=f"Renko Entry ({TOTAL_QTY}Q)")

    eng["prev_close"] = c
    eng["last_bar_time"] = bar_time
    eng["bar_count"] += 1

def background_worker(eng):
    last_1d_fetch, last_kline_fetch = 0, 0
    init_delta_product_id(eng)
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
                    for b in klines_init[:-1]: process_single_closed_bar(eng, b)
                    eng["price"] = float(klines_init[-1][4])
                    eng["initialized"] = True
                    last_kline_fetch = now_ts

            if eng["initialized"] and (now_ts - last_kline_fetch >= 2.0):
                klines_live = fetch_hl_klines("1m", 8)
                if klines_live and len(klines_live) >= 2:
                    for b in klines_live[:-1]: process_single_closed_bar(eng, b)
                    eng["price"] = float(klines_live[-1][4])
                    last_kline_fetch = now_ts

            eng["ist_time"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
        except Exception:
            pass
        time.sleep(1)

@st.cache_resource
def get_engine():
    eng = {
        "initialized": False, "bar_count": 0, "last_bar_time": 0, "anchor_time_str": "--",
        "prev_close": 0.0, "tr_sum": 0.0, "atr14": 15.0, "ema21": 0.0, "rsi14": 50.0,
        "g1": 0.0, "g2": 0.0, "buy_v1": 0.0, "buy_v2": 0.0, "sell_v1": 0.0, "sell_v2": 0.0,
        "buy_dom_pct": 50.0, "sell_dom_pct": 50.0, "macro_range": None, "box_size": 169.3,
        "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
        "support_band": None, "resistance_band": None, "st_trend": 1, "st_line": 0.0,
        "trend_tp1_done": False, "pending_flip_buy": False, "pending_flip_sell": False,
        "trade_dir": 0, "entry_bar": -1, "entry_price": 0.0, "tp1_price": 0.0, "tp2_price": 0.0,
        "stop_price": 0.0, "hard_stop_price": 0.0, "max_fav_price": 0.0,
        "tp1_reached": False, "mid_reached": False, "tp2_reached": False, "trail_steps": 0,
        "open_qty": 0, "booked_pnl_10q": 0.0, "entry_tag": "", "entry_time_str": "",
        "wins": 0, "losses": 0, "tp2_hits": 0, "blocked_late": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "total_brok": 0.0,
        "price": 0.0, "ist_time": "--:--:--", "last_result": "अभी कोई ट्रेड क्लोज नहीं हुआ है", "last_result_color": "#334155",
        "history": [], "delta_btc_product_id": 27, "delta_status": "🤖 Delta Demo Algo: Ready", "spike_history": [],
        "last_spike_alert_ts": 0, "last_spike_alert_id": 0, "last_spike_dir": 0,
        "last_spike_status": "📡 Radar Ready", "last_spike_color": "#0f172a", "l2_tick_window": []
    }
    threading.Thread(target=background_worker, args=(eng,), daemon=True).start()
    return eng

eng = get_engine()
server_ip = get_server_public_ip()

col1, col2, col3 = st.columns([0.52, 0.24, 0.24])
with col1:
    st.markdown(f"**🌐 Server IP:** `{server_ip}` | **Status:** {eng.get('delta_status', 'Ready')}")
with col2:
    if st.button("🔌 Delta API Test"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        eng["delta_status"] = "✅ Connected!" if ok else f"⚠️ Error: {resp}"
with col3:
    if st.button("🔄 Reset History"):
        eng["history"] = []

terminal = st.empty()

while True:
    if not eng["initialized"] or eng["price"] == 0.0:
        terminal.info("⏳ AI-Renko Pro: TP1 (300p), SL (250p), 7Q + 3Q ट्रेलिंग इंजन लोड हो रहा है...")
        time.sleep(1)
        continue

    price = eng["price"]
    box_size = eng["box_size"]
    st_trend = eng["st_trend"]
    st_line = eng["st_line"]
    brick_streak = eng["brick_streak"]
    ema21 = eng["ema21"]
    rsi14 = eng["rsi14"]
    ist_time = eng["ist_time"]
    anchor_str = eng["anchor_time_str"]

    tot_trades = eng["wins"] + eng["losses"]
    win_rate = (float(eng["wins"]) / float(tot_trades) * 100.0) if tot_trades > 0 else 0.0
    net_pnl = eng["gross_profit"] - eng["gross_loss"] - eng["total_brok"]

    st_badge_text = "STATUS: BUY 🟢" if st_trend == 1 else "STATUS: SELL 🔴"
    st_badge_col = "#00c891" if st_trend == 1 else "#f03769"

    if eng["trade_dir"] != 0:
        t_type = "LONG" if eng["trade_dir"] == 1 else "SHORT"
        entry, tp1, tp2, sl, open_qty, booked_pnl = eng["entry_price"], eng["tp1_price"], eng["tp2_price"], eng["stop_price"], eng["open_qty"], eng["booked_pnl_10q"]
        unit_pnl = (price - entry) if t_type == "LONG" else (entry - price)
        open_pnl = unit_pnl * open_qty
        total_live_pnl = booked_pnl + open_pnl
        live_net_inr = pts_to_inr(total_live_pnl - (BROK_PER_QTY * TOTAL_QTY))
        pnl_color = "#22c55e" if total_live_pnl >= 0 else "#ef4444"
        badge_bg = "#00af6e" if t_type == "LONG" else "#dc284b"

        if eng["tp2_reached"]:
            status_label = f"🚀 {RUNNER_QTY}Q TRAILING (हर ₹100 आगे बढ़ने पर ट्रेलिंग)"
            sl_tag = f"Trail SL ({RUNNER_QTY}Q)"
        elif eng["tp1_reached"]:
            status_label = f"✅ {TP1_BOOK_QTY}Q TP1 BOOKED • SL AT COST"
            sl_tag = f"Cost SL ({RUNNER_QTY}Q)"
        else:
            status_label = f"🔥 ACTIVE {t_type} ({TOTAL_QTY}Q Open)"
            sl_tag = f"Initial SL (-250p)"

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:15px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
<span style="background:{badge_bg}; color:white; padding:5px 11px; border-radius:6px; font-weight:bold; font-size:13px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:800;">{total_live_pnl:+,.1f} pts (Net: ₹{live_net_inr:+,.0f})</span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; color:#cbd5e1; font-size:12px; background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
<div>Entry ({TOTAL_QTY}Q)<br><b style="color:#ffffff; font-size:14px;">{entry:,.1f}</b></div>
<div>TP1 (300p / 7Q)<br><b style="color:#22c55e; font-size:14px;">{tp1:,.1f}</b></div>
<div>Next +₹100 Step<br><b style="color:#38bdf8; font-size:14px;">{tp2:,.1f}</b></div>
<div>{sl_tag}<br><b style="color:#ef4444; font-size:14px;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR SIGNAL (TP1: 300p | SL: 250p | Trail Step: ₹100)</div>
<div style="color:#94a3b8; font-size:12px; margin-top:3px;">Supertrend: <b>{st_line:,.1f}</b> | EMA21: <b>{ema21:,.1f}</b> | RSI: <b>{rsi14:.1f}</b></div>
</div>"""

    rows_html = ""
    if not eng["history"]:
        rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी कोई ट्रेड क्लोज नहीं हुआ है</td></tr>"""
    else:
        for h in eng["history"]:
            rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12px;">
<td style="padding:8px 6px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 6px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 6px; color:#cbd5e1;">{h['entry']:,.1f} → {h['exit']:,.1f}</td>
<td style="padding:8px 6px; color:{h['color']}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 6px; color:{h['color']}; font-weight:bold; text-align:right;">{h['pnl']}</td>
</tr>"""

    net_color = "#00e676" if net_pnl >= 0 else "#ff5252"
    wr_color = "#00e676" if win_rate >= 60.0 else "#facc15"

    raw_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; border:1px solid #1e293b; font-family:sans-serif;">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px;">
<div>
<div style="font-size:12px; color:#38bdf8; font-weight:700;">⚡ AI-RENKO PRO [TP1: 300p (7Q) | SL: 250p | TRAIL: ₹100 STEP (3Q)]</div>
<div style="font-size:34px; font-weight:800; color:#ffffff;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="background:#1e293b; border:1px solid {st_badge_col}; color:{st_badge_col}; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:inline-block; margin-bottom:4px;">{st_badge_text}</div>
<div style="font-size:11.5px; color:#cbd5e1;">Grid Anchor: {anchor_str} | {ist_time}</div>
</div>
</div>
<div class="t-grid">
<div>
{trade_box_html}
<div style="background:#1e293b; border-radius:12px; padding:12px; border:1px solid #334155;">
<div style="font-size:13px; font-weight:bold; color:#38bdf8; margin-bottom:8px;">📊 {TOTAL_QTY}-QTY MASTER BACKTEST TABLE (TP1: 300p | SL: 250p | Trail: ₹100)</div>
<table style="width:100%; border-collapse:collapse; font-size:13px;">
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Total Trades (W / L)</td><td style="padding:6px; color:#ffffff; font-weight:bold; text-align:right;">{tot_trades} ({eng['wins']}W / {eng['losses']}L)</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Win Rate % | Step Runners</td><td style="padding:6px; color:{wr_color}; font-weight:bold; text-align:right;">{win_rate:.1f}% | 🚀 Runners: {eng['tp2_hits']}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Profit</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">+{eng['gross_profit']:,.1f} pts (₹{pts_to_inr(eng['gross_profit']):+,.0f})</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Loss</td><td style="padding:6px; color:#f87171; font-weight:bold; text-align:right;">-{eng['gross_loss']:,.1f} pts (-₹{pts_to_inr(eng['gross_loss']):,.0f})</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Delta Fee ({BROK_PER_QTY}p × {TOTAL_QTY}Q)</td><td style="padding:6px; color:#fca5a5; font-weight:bold; text-align:right;">-{eng['total_brok']:,.1f} pts (-₹{pts_to_inr(eng['total_brok']):,.0f})</td></tr>
<tr style="background:#0f172a;"><td style="padding:8px 6px; color:#ffffff; font-weight:bold;">NET PROFIT (After Real Fee)</td><td style="padding:8px 6px; color:{net_color}; font-weight:800; font-size:15px; text-align:right;">{net_pnl:+,.1f} pts (₹{pts_to_inr(net_pnl):+,.0f})</td></tr>
</table>
</div>
</div>
<div>
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
<div style="font-size:14px; font-weight:bold; color:#f8fafc; margin-bottom:10px;">📜 ट्रेड इतिहास लॉग</div>
<div style="max-height:420px; overflow-y:auto;">
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:6px;">समय</th>
<th style="padding:6px;">ट्रेड</th>
<th style="padding:6px;">Entry → Exit</th>
<th style="padding:6px;">स्टेटस स्कोर</th>
<th style="padding:6px; text-align:right;">PnL</th>
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

    terminal.markdown("\n".join(line.strip() for line in raw_html.splitlines() if line.strip()), unsafe_allow_html=True)
    time.sleep(2)

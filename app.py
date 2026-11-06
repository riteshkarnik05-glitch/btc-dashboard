import streamlit as st
import requests
import time
import threading
import json
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="Dr Devendra AI-Renko 15m Terminal", layout="wide")

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
            signature = __import__('hmac').new(
                DELTA_API_SECRET.encode("utf-8"),
                sig_data.encode("utf-8"),
                __import__('hashlib').sha256
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

def place_delta_demo_order(eng, side, qty, tag="Renko 15m", reduce_only=False):
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
# 15m SETUP PARAMETERS (10 Qty: 7Q TP1 @ ₹400 + 3Q Runner & SL ₹200)
# ============================================================================
SIGNAL_TF            = "15m"  
TOTAL_QTY            = 10     
TP1_BOOK_QTY         = 7      
RUNNER_QTY           = 3      
USD_INR_RATE         = 85.0   

SL_RUPEES_10Q        = 200.0  
TARGET_RUPEES_10Q    = 400.0  

FIXED_SL_BTC_PTS     = round((SL_RUPEES_10Q / USD_INR_RATE) * (1000.0 / TOTAL_QTY), 1)      # 235.3 pts
FIXED_TP1_BTC_PTS    = round((TARGET_RUPEES_10Q / USD_INR_RATE) * (1000.0 / TOTAL_QTY), 1)  # 470.6 pts
RUNNER_LOCK_PTS      = FIXED_SL_BTC_PTS                                                     # +235.3 pts
FIXED_TP2_BTC_PTS    = round(FIXED_TP1_BTC_PTS * 1.50, 1)                                   # +705.9 pts

USE_TRAIL_BEYOND_TP2 = True
TRAIL_LOCK_BRICKS    = 0.8
USE_STREAK_FILTER    = True
MAX_BRICK_STREAK     = 4
USE_STRETCH_FILTER   = True
MAX_EMA_DIST_BRICKS  = 2.0

USE_AUTO_BOX         = True
ATR_PERIOD           = 5
RANGE_DIVISOR        = 10.0
MANUAL_BOX           = 150.0

ST_FACTOR            = 3.0
USE_GAUSSIAN         = True
GAUSS_PERIOD         = 20
MIN_VOL_DOM          = 55.0
ANTI_WICK_SL         = True
BROK_PER_QTY         = 1.5
MINTICK              = 0.1

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def fmt_pts(pts):
    return f"{pts:,.1f}"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

def fetch_hl_klines(interval="15m", num_bars=20):
    step_ms = 900000
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

def fetch_hl_15m_fixed_anchor():
    now_sec = int(time.time())
    today_00_utc_sec = (now_sec // 86400) * 86400
    anchor_start_ms = (today_00_utc_sec - (25 * 86400)) * 1000
    now_ms = now_sec * 1000

    merged = {}
    for attempt in range(3):
        try:
            r = requests.post(
                HYPERLIQUID_INFO_URL,
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": SIGNAL_TF,
                        "startTime": anchor_start_ms,
                        "endTime": now_ms
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
# PROCESSOR ENGINE (15m + LIGHTWEIGHT)
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

    if idx == 0:
        eng["brick_top"] = c
        eng["brick_bot"] = c - box_size
        eng["brick_dir"] = 1
        eng["brick_streak"] = 1
        eng["anchor_time_str"] = bar_ist
    else:
        if eval_price >= eng["brick_top"] + box_size:
            steps = int(math.floor((eval_price - eng["brick_top"]) / box_size))
            eng["brick_top"] = eng["brick_top"] + (steps * box_size)
            eng["brick_bot"] = eng["brick_top"] - box_size
            if eng["brick_dir"] == -1:
                eng["brick_streak"] = steps
            else:
                eng["brick_streak"] += steps
            eng["brick_dir"] = 1
        elif eval_price <= eng["brick_bot"] - box_size:
            steps = int(math.floor((eng["brick_bot"] - eval_price) / box_size))
            eng["brick_bot"] = eng["brick_bot"] - (steps * box_size)
            eng["brick_top"] = eng["brick_bot"] + box_size
            if eng["brick_dir"] == 1:
                eng["brick_streak"] = steps
            else:
                eng["brick_streak"] += steps
            eng["brick_dir"] = -1

    r_close = eng["brick_top"] if eng["brick_dir"] == 1 else eng["brick_bot"]
    eng["r_close"] = r_close

    band_distance = box_size * ST_FACTOR
    raw_support = r_close - band_distance
    raw_resistance = r_close + band_distance

    prev_trend = eng["st_trend"]
    prev_supp = eng["support_band"]
    prev_res = eng["resistance_band"]

    if prev_supp is None:
        support_band = raw_support
    elif prev_trend == 1:
        support_band = raw_support if (eng["brick_dir"] == 1 and raw_support > prev_supp) else prev_supp
    else:
        support_band = raw_support

    if prev_res is None:
        resistance_band = raw_resistance
    elif prev_trend == -1:
        resistance_band = raw_resistance if (eng["brick_dir"] == -1 and raw_resistance < prev_res) else prev_res
    else:
        resistance_band = raw_resistance

    if prev_trend == -1 and eng["brick_dir"] == 1 and prev_res is not None and r_close > prev_res:
        st_trend = 1
        support_band = r_close - band_distance
    elif prev_trend == 1 and eng["brick_dir"] == -1 and prev_supp is not None and r_close < prev_supp:
        st_trend = -1
        resistance_band = r_close + band_distance
    else:
        st_trend = prev_trend

    eng["support_band"] = support_band
    eng["resistance_band"] = resistance_band
    eng["st_trend"] = st_trend

    st_line = support_band if st_trend == 1 else resistance_band
    eng["st_line"] = st_line

    st_flip_buy = (idx > 0) and (st_trend == 1 and prev_trend == -1)
    st_flip_sell = (idx > 0) and (st_trend == -1 and prev_trend == 1)

    if st_flip_buy or st_flip_sell:
        eng["brick_streak"] = 1

    if st_flip_buy:
        eng["pending_flip_buy"] = True
        eng["pending_flip_sell"] = False
    if st_flip_sell:
        eng["pending_flip_sell"] = True
        eng["pending_flip_buy"] = False
    if st_trend == -1:
        eng["pending_flip_buy"] = False
    if st_trend == 1:
        eng["pending_flip_sell"] = False

    # Trade Management
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        close_side = "sell" if t_dir == 1 else "buy"
        eng["max_fav_price"] = max(eng["max_fav_price"], h) if t_dir == 1 else min(eng["max_fav_price"], l)

        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["wins"] += 1
            eng["booked_pnl_10q"] = eng["locked_tp1_pts"] * TP1_BOOK_QTY
            eng["gross_profit"] += eng["booked_pnl_10q"]
            eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
            eng["open_qty"] = RUNNER_QTY
            eng["stop_price"] = (eng["entry_price"] - box_size * 0.25) if t_dir == 1 else (eng["entry_price"] + box_size * 0.25)
            place_delta_demo_order(eng, close_side, TP1_BOOK_QTY, tag="Renko 15m TP1 (7Q)", reduce_only=True)

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
            cand_trail = max(brick_trail, peak_trail) if t_dir == 1 else min(brick_trail, peak_trail)
            eng["stop_price"] = max(eng["stop_price"], cand_trail) if t_dir == 1 else min(eng["stop_price"], cand_trail)

            hit_trail_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
            st_reversed = (st_trend == -1) if t_dir == 1 else (st_trend == 1)

            if (hit_trail_sl or st_reversed) and not hit_tp2_now:
                exit_p = eng["stop_price"] if hit_trail_sl else (max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"]))
                total_run_pts = (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p)
                safe_run_pts = max(total_run_pts, eng["locked_tp2_pts"] * 0.85)
                runner_pnl_3q = safe_run_pts * RUNNER_QTY
                eng["gross_profit"] += runner_pnl_3q
                total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_3q

                eng["last_result"] = f"🚀 Trail Exit (10Q): +{fmt_pts(total_trade_pnl)} pts (₹{pts_to_inr(total_trade_pnl):+,.0f})"
                eng["last_result_color"] = "#0369a1"
                eng["history"].insert(0, {
                    "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                    "exit": exit_p, "status": "🚀 7Q TP1 + 3Q TRAIL", "pnl": f"+{fmt_pts(total_trade_pnl)} (₹{pts_to_inr(total_trade_pnl):+,.0f})", "color": "#38bdf8"
                })
                eng["history"] = eng["history"][:40]
                place_delta_demo_order(eng, close_side, RUNNER_QTY, tag="Renko 15m Trail Exit (3Q)", reduce_only=True)
                eng["trade_dir"] = 0
                eng["open_qty"] = 0

        if eng["trade_dir"] != 0 and not eng["tp2_reached"]:
            if not eng["tp1_reached"]:
                adverse_close_pts = (eng["entry_price"] - c) if t_dir == 1 else (c - eng["entry_price"])
                close_hit_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
                brick_turned_bad = (eng["brick_dir"] == -1 and c < eng["brick_bot"]) if t_dir == 1 else (eng["brick_dir"] == 1 and c > eng["brick_top"])
                st_turned_bad = (st_trend == -1) if t_dir == 1 else (st_trend == 1)
                hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

                sl_triggered = (close_hit_sl or brick_turned_bad or st_turned_bad or hard_crash) if ANTI_WICK_SL else ((l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"]))

                if sl_triggered:
                    eng["losses"] += 1
                    max_cap_pts = eng["locked_sl_pts"]
                    loss_per_qty = min(adverse_close_pts, max_cap_pts) if (ANTI_WICK_SL and not hard_crash and adverse_close_pts > 0) else max_cap_pts
                    total_loss_10q = loss_per_qty * TOTAL_QTY
                    eng["gross_loss"] += total_loss_10q
                    eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)

                    eng["last_result"] = f"❌ SL (10Q): -{fmt_pts(total_loss_10q)} pts (-₹{pts_to_inr(total_loss_10q):,.0f})"
                    eng["last_result_color"] = "#991b1b"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": c, "status": "🛑 SL HIT (10Q)", "pnl": f"-{fmt_pts(total_loss_10q)} (-₹{pts_to_inr(total_loss_10q):,.0f})", "color": "#ef4444"
                    })
                    eng["history"] = eng["history"][:40]
                    place_delta_demo_order(eng, close_side, TOTAL_QTY, tag="Renko 15m SL Exit (10Q)", reduce_only=True)
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0
            else:
                close_hit_sl = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
                st_turned_bad = (st_trend == -1) if t_dir == 1 else (st_trend == 1)

                if (close_hit_sl or st_turned_bad) and not hit_tp1_now:
                    runner_pts = max(0.0, (c - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - c))
                    runner_pnl_3q = runner_pts * RUNNER_QTY
                    eng["gross_profit"] += runner_pnl_3q
                    total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_3q

                    eng["last_result"] = f"✅ TP1 Won (10Q): +{fmt_pts(total_trade_pnl)} pts (₹{pts_to_inr(total_trade_pnl):+,.0f})"
                    eng["last_result_color"] = "#166534"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": c, "status": "✅ 7Q TP1 + 3Q EXIT", "pnl": f"+{fmt_pts(total_trade_pnl)} (₹{pts_to_inr(total_trade_pnl):+,.0f})", "color": "#22c55e"
                    })
                    eng["history"] = eng["history"][:40]
                    place_delta_demo_order(eng, close_side, RUNNER_QTY, tag="Renko 15m Runner Close (3Q)", reduce_only=True)
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0

    # New Signals
    ema21 = eng["ema21"]
    rsi_val = eng["rsi14"]
    candle_not_giant = (h - l) <= box_size * 1.85
    bull_filter_ok   = candle_not_giant and buy_dom_pct >= 50.0 and rsi_val < 76.0
    bear_filter_ok   = candle_not_giant and sell_dom_pct >= 50.0 and rsi_val > 24.0

    trigger_flip_buy  = eng["pending_flip_buy"] and st_trend == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and st_trend == -1 and bear_filter_ok and c < o

    allow_re_entry = True
    raw_cont_buy   = allow_re_entry and (not trigger_flip_buy) and st_trend == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and rsi_val > 50.0 and rsi_val < 72.0 and candle_not_giant
    raw_cont_sell  = allow_re_entry and (not trigger_flip_sell) and st_trend == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and rsi_val < 50.0 and rsi_val > 28.0 and candle_not_giant

    streak_ok  = (not USE_STREAK_FILTER) or (eng["brick_streak"] <= MAX_BRICK_STREAK)
    stretch_ok = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
    late_safe  = streak_ok and stretch_ok

    trigger_cont_buy  = raw_cont_buy and late_safe
    trigger_cont_sell = raw_cont_sell and late_safe

    can_open_trade = (eng["trade_dir"] == 0) or (eng["tp1_reached"] and (st_flip_buy or st_flip_sell))

    if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            old_close_side = "sell" if eng["trade_dir"] == 1 else "buy"
            runner_pts = max(0.0, (c - eng["entry_price"]) if eng["trade_dir"] == 1 else (eng["entry_price"] - c))
            runner_pnl_3q = runner_pts * RUNNER_QTY
            eng["gross_profit"] += runner_pnl_3q
            tot_flip_pnl = eng["booked_pnl_10q"] + runner_pnl_3q
            eng["history"].insert(0, {
                "time": bar_ist, "type": f"{old_label} (10Q)", "entry": eng["entry_price"],
                "exit": c, "status": "✅ 7Q TP1 + 3Q FLIP", "pnl": f"+{fmt_pts(tot_flip_pnl)} (₹{pts_to_inr(tot_flip_pnl):+,.0f})", "color": "#22c55e"
            })
            eng["history"] = eng["history"][:40]
            place_delta_demo_order(eng, old_close_side, RUNNER_QTY, tag="Renko 15m Flip Close (3Q)", reduce_only=True)

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
        eng["tp2_reached"] = False
        eng["open_qty"] = TOTAL_QTY
        eng["booked_pnl_10q"] = 0.0
        eng["entry_tag"] = f"🧱 15m Brick #{eng['brick_streak']}" if (trigger_cont_buy or trigger_cont_sell) else "🔥 15m ST Entry"
        eng["entry_time_str"] = bar_ist

        eng["locked_tp1_pts"] = FIXED_TP1_BTC_PTS
        eng["locked_tp2_pts"] = max(box_size * TP2_BRICKS, FIXED_TP1_BTC_PTS * 1.6)
        eng["locked_sl_pts"]  = FIXED_SL_BTC_PTS

        eng["tp1_price"]       = (c + eng["locked_tp1_pts"]) if is_long else (c - eng["locked_tp1_pts"])
        eng["tp2_price"]       = (c + eng["locked_tp2_pts"]) if is_long else (c - eng["locked_tp2_pts"])
        eng["stop_price"]      = (c - eng["locked_sl_pts"]) if is_long else (c + eng["locked_sl_pts"])
        eng["hard_stop_price"] = (c - box_size * 1.8) if is_long else (c + box_size * 1.8)

        entry_side = "buy" if is_long else "sell"
        place_delta_demo_order(eng, entry_side, TOTAL_QTY, tag="Renko 15m Entry (10Q)")

    eng["prev_close"] = c
    eng["last_bar_time"] = bar_time
    eng["bar_count"] += 1

def background_worker(eng):
    last_1d_fetch = 0
    last_kline_fetch = 0
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
                if eng["macro_range"] is None:
                    eng["macro_range"] = 2500.0

            if not eng["initialized"] and eng["macro_range"] is not None:
                klines_init = fetch_hl_15m_fixed_anchor()
                if klines_init and len(klines_init) > 30:
                    for b in klines_init[:-1]:
                        process_single_closed_bar(eng, b)
                    eng["price"] = float(klines_init[-1][4])
                    eng["initialized"] = True
                    last_kline_fetch = now_ts

            if eng["initialized"] and (now_ts - last_kline_fetch >= 8.0):
                klines_live = fetch_hl_klines(SIGNAL_TF, 8)
                if klines_live and len(klines_live) >= 2:
                    for b in klines_live[:-1]:
                        process_single_closed_bar(eng, b)
                    eng["price"] = float(klines_live[-1][4])
                    last_kline_fetch = now_ts

            eng["ist_time"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
            eng["error"] = None
        except Exception as e:
            eng["error"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_hl_15m_clean_v8_engine():
    eng = {
        "initialized": False, "bar_count": 0, "last_bar_time": 0, "anchor_time_str": "--",
        "prev_close": 0.0, "tr_sum": 0.0, "atr14": 15.0, "ema21": 0.0, "rsi14": 50.0,
        "g1": 0.0, "g2": 0.0, "buy_v1": 0.0, "buy_v2": 0.0, "sell_v1": 0.0, "sell_v2": 0.0,
        "buy_dom_pct": 50.0, "sell_dom_pct": 50.0, "macro_range": None, "safe_range": 2500.0,
        "box_size": 250.0, "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
        "r_close": 0.0, "support_band": None, "resistance_band": None, "st_trend": 1, "st_line": 0.0,
        "pending_flip_buy": False, "pending_flip_sell": False, "trade_dir": 0, "entry_bar": -1,
        "entry_price": 0.0, "tp1_price": 0.0, "tp2_price": 0.0, "stop_price": 0.0, "hard_stop_price": 0.0,
        "max_fav_price": 0.0, "locked_tp1_pts": 0.0, "locked_tp2_pts": 0.0, "locked_sl_pts": 0.0,
        "tp1_reached": False, "tp2_reached": False, "open_qty": 0, "booked_pnl_10q": 0.0,
        "entry_tag": "", "entry_time_str": "", "wins": 0, "losses": 0, "tp2_hits": 0, "blocked_late": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "total_brok": 0.0, "price": 0.0, "ist_time": "--:--:--",
        "last_result": "अभी कोई ट्रेड क्लोज नहीं हुआ है", "last_result_color": "#334155", "history": [],
        "order_book": {"best_bid": 0.0, "best_ask": 0.0, "mid_price": 0.0, "spread": 0.0},
        "spike_history": [], "delta_btc_product_id": 27, "delta_status": "🤖 Delta Demo Algo: Ready (15m Light Renko 10Q Active)", "error": None
    }
    threading.Thread(target=background_worker, args=(eng,), daemon=True).start()
    return eng

eng = get_hl_15m_clean_v8_engine()
server_ip = get_server_public_ip()

top_col1, top_col2, top_col3 = st.columns([0.52, 0.24, 0.24])
with top_col1:
    st.markdown(f"**🌐 Server IP:** `{server_ip}` | **Status:** {eng.get('delta_status', 'Ready')}")
with top_col2:
    if st.button("🔌 Delta API Test"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        eng["delta_status"] = "✅ Connected!" if ok else f"⚠️ Error: {resp}"
with top_col3:
    if st.button("🔄 Reset History"):
        eng["history"] = []

terminal = st.empty()

while True:
    try:
        if not eng["initialized"] or eng["price"] == 0.0:
            terminal.info("⏳ Dr Devendra AI-Renko PRO (15m Lightweight): 25-Day 15m Grid और स्पेशल रैंकों सुपरट्रेंड लोड हो रहा है...")
            time.sleep(1)
            continue

        price = eng["price"]
        box_size = eng["box_size"]
        safe_range = eng["safe_range"]
        st_trend = eng["st_trend"]
        st_line = eng["st_line"]
        r_close = eng.get("r_close", price)
        brick_dir = eng["brick_dir"]
        brick_streak = eng["brick_streak"]
        ema21 = eng["ema21"]
        rsi14 = eng["rsi14"]
        buy_pct = int(round(eng["buy_dom_pct"]))
        sell_pct = int(round(eng["sell_dom_pct"]))
        imbalance = (eng["buy_dom_pct"] - eng["sell_dom_pct"]) / 100.0
        ist_time = eng["ist_time"]
        bar_count = eng["bar_count"]
        anchor_str = eng["anchor_time_str"]
        delta_status_str = eng.get("delta_status", "🤖 Delta Demo Algo: Ready")

        tot_trades = eng["wins"] + eng["losses"]
        win_rate = (float(eng["wins"]) / float(tot_trades) * 100.0) if tot_trades > 0 else 0.0
        net_pnl = eng["gross_profit"] - eng["gross_loss"] - eng["total_brok"]

        st_badge_text = "15m RENKO ST: BUY ▲ 🟢" if st_trend == 1 else "15m RENKO ST: SELL ▼ 🔴"
        st_badge_col = "#00c891" if st_trend == 1 else "#f03769"
        brick_dir_txt = "🟢 Up Brick" if brick_dir == 1 else "🔴 Down Brick"

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
            elif eng["tp1_reached"]:
                status_label = f"✅ 7Q TP1 BOOKED • 3Q RUNNER PROTECTED ({t_type})"
                sl_tag = "Runner SL (3Q)"
            else:
                status_label = f"🔥 ACTIVE 15m {t_type} (10 Qty Open | {eng['entry_tag']} @ {eng['entry_time_str']})"
                sl_tag = "₹200 SL Cap (-235p)"

            trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:15px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
<span style="background:{badge_bg}; color:white; padding:5px 11px; border-radius:6px; font-weight:bold; font-size:13px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:800;">{total_live_pnl:+,.1f} pts (₹{pts_to_inr(total_live_pnl):+,.0f})</span>
</div>
<div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:10px; background:#0b1324; padding:6px 10px; border-radius:6px; flex-wrap:wrap; gap:6px;">
<span>📦 Open Qty: <b style="color:#f8fafc;">{open_qty}/10</b></span>
<span>💰 Booked (7Q @ TP1): <b style="color:#4ade80;">+{booked_pnl:,.1f}p (₹{pts_to_inr(booked_pnl):+,.0f})</b></span>
<span>⚡ Runner ({open_qty}Q): <b style="color:{pnl_color};">{open_pnl:+,.1f}p (₹{pts_to_inr(open_pnl):+,.0f})</b></span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; color:#cbd5e1; font-size:12px; background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
<div>Entry (10Q)<br><b style="color:#ffffff; font-size:14px;">{entry:,.1f}</b></div>
<div>TP1 (₹350 / +412p)<br><b style="color:#22c55e; font-size:14px;">{tp1:,.1f}</b></div>
<div>TP2 (Trail 3Q)<br><b style="color:#38bdf8; font-size:14px;">{tp2:,.1f}</b></div>
<div>{sl_tag}<br><b style="color:#ef4444; font-size:14px;">{sl:,.1f}</b></div>
</div>
</div>"""
        else:
            trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR 15m RENKO SUPERTREND SIGNAL (DIVISOR 10 • TARGET ₹350 • SL CAP ₹200)</div>
<div style="color:#facc15; font-size:12px; margin-top:4px; font-weight:bold;">🧱 Renko Step Line (rClose): {r_close:,.1f} ({brick_dir_txt} #{brick_streak}) | 🛡️ Renko ST Line: {st_line:,.1f}</div>
<div style="color:#94a3b8; font-size:12px; margin-top:3px;">EMA21: <b>{ema21:,.1f}</b> | RSI: <b>{rsi14:.1f}</b> | Max Streak Allowed: <b>4</b></div>
</div>"""

        rows_html = ""
        if not eng["history"]:
            rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी कोई 15m ट्रेड क्लोज नहीं हुआ है</td></tr>"""
        else:
            for h in eng["history"]:
                h_col = h.get("color", "#22c55e")
                rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12px;">
<td style="padding:8px 6px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 6px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 6px; color:#cbd5e1;">{h['entry']:,.1f} → {h['exit']:,.1f}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold; text-align:right;">{h['pnl']}</td>
</tr>"""

        net_color = "#00e676" if net_pnl >= 0 else "#ff5252"
        wr_color = "#00e676" if win_rate >= 60.0 else "#facc15"
        setup_str = f"Target: ₹350 (+{FIXED_TP1_BTC_PTS:.0f}p/Q) | SL Cap: ₹200 (-{FIXED_SL_BTC_PTS:.0f}p/Q)"

        raw_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; border:1px solid #1e293b; box-shadow:0 8px 30px rgba(0,0,0,0.6); font-family:sans-serif;">
<div style="display:flex; justify-content:space-between; align-items:center; background:#111827; border:1px solid #eab308; border-radius:10px; padding:8px 14px; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
<span style="font-size:12.5px; font-weight:800; color:#facc15;">🌐 Server IP (Delta में Whitelist करें): <span style="color:#ffffff; background:#1e293b; padding:2px 8px; border-radius:5px; border:1px solid #475569;">{server_ip}</span></span>
<span style="font-size:12px; font-weight:700; color:#38bdf8;">{delta_status_str}</span>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
<div>
<div style="font-size:12px; color:#38bdf8; font-weight:700;">⚡ DR DEVENDRA AI-RENKO PRO [15-MINUTE TIMEFRAME • LIGHTWEIGHT RENKO CLONE]</div>
<div style="font-size:34px; font-weight:800; color:#ffffff; line-height:1.15;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="background:#1e293b; border:1px solid {st_badge_col}; color:{st_badge_col}; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:inline-block; margin-bottom:4px;">{st_badge_text}</div>
<div style="font-size:11.5px; color:#cbd5e1;">🔒 15m Pine Grid Anchor: {anchor_str} ({bar_count} Bars) | {ist_time}</div>
</div>
</div>
<div class="t-grid">
<div>
<div style="margin-bottom:14px; background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
<div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:6px;">
<span style="color:#22c55e;">🟢 15m 3-Bar Candle Flow: {buy_pct}%</span>
<span style="color:#e2e8f0;">Imbalance: {imbalance:+.2f}</span>
<span style="color:#ef4444;">Sell Flow: {sell_pct}% 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:12px; border-radius:6px; overflow:hidden;">
<div style="width:{buy_pct}%; background:#22c55e; height:100%;"></div>
</div>
</div>

{trade_box_html}

<div style="background:{eng['last_result_color']}; color:#ffffff; padding:10px 14px; border-radius:8px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:14px;">
पिछला परिणाम: {eng['last_result']}
</div>
<div style="background:#1e293b; border-radius:12px; padding:12px; border:1px solid #334155;">
<div style="font-size:13px; font-weight:bold; color:#38bdf8; margin-bottom:8px;">📊 10-QTY MASTER BACKTEST TABLE (15m Timeframe • Pine-Script Clone • ₹350 TP / ₹200 SL)</div>
<table style="width:100%; border-collapse:collapse; font-size:13px;">
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">23H/Daily Range | 1 Brick (Div 10)</td><td style="padding:6px; color:#facc15; font-weight:bold; text-align:right;">{safe_range:,.1f} pts | Brick: {box_size:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Renko Step (rClose) | ST Line</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">{r_close:,.1f} | ST: {st_line:,.1f}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">10-Qty Levels (7Q TP1 + 3Q Trail)</td><td style="padding:6px; color:#38bdf8; font-weight:bold; text-align:right;">{setup_str}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Total Trades (W / L)</td><td style="padding:6px; color:#ffffff; font-weight:bold; text-align:right;">{tot_trades} ({eng['wins']}W / {eng['losses']}L)</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Win Rate % | TP2 Runners</td><td style="padding:6px; color:{wr_color}; font-weight:bold; text-align:right;">{win_rate:.1f}% | 🎯 TP2: {eng['tp2_hits']}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Profit (10 Qty)</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">+{eng['gross_profit']:,.1f} pts (₹{pts_to_inr(eng['gross_profit']):+,.0f})</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Loss (10 Qty)</td><td style="padding:6px; color:#f87171; font-weight:bold; text-align:right;">-{eng['gross_loss']:,.1f} pts (-₹{pts_to_inr(eng['gross_loss']):,.0f})</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Brokerage/Tax (10 Qty)</td><td style="padding:6px; color:#fca5a5; font-weight:bold; text-align:right;">-{eng['total_brok']:,.1f} pts (-₹{pts_to_inr(eng['total_brok']):,.0f})</td></tr>
<tr style="background:#0f172a;"><td style="padding:8px 6px; color:#ffffff; font-weight:bold;">NET PROFIT (10 Qty Total)</td><td style="padding:8px 6px; color:{net_color}; font-weight:800; font-size:15px; text-align:right;">{net_pnl:+,.1f} pts (₹{pts_to_inr(net_pnl):+,.0f})</td></tr>
</table>
</div>
</div>
<div>
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155; height:100%; box-sizing:border-box;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<span style="font-size:14px; font-weight:bold; color:#f8fafc;">📜 10-Qty ट्रेड इतिहास लॉग (15m Lightweight Clone)</span>
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
<th style="padding:6px; text-align:right;">10Q PnL (₹)</th>
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

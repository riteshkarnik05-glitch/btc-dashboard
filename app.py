import streamlit as st
import requests
import time
import threading
import json
from datetime import datetime, timedelta
import math
import hmac
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Dr Devendra AI-Quantum Pro Terminal", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; }
.block-container { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
div.stButton > button {
    background-color: #1e293b !important;
    color: #facc15 !important;
    border: 1px solid #eab308 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    padding: 6px 10px !important;
    width: 100% !important;
}
div.stButton > button:hover {
    background-color: #eab308 !important;
    color: #0f172a !important;
}
</style>""", unsafe_allow_html=True)

# ============================================================================
# DELTA EXCHANGE LIVE AUTO-EXECUTION API & CONNECTION HELPERS
# ============================================================================
ALGO_EXECUTION_ENABLED = True  # ✅ डेल्टा ऑटोमैटिक ट्रेड एंट्री और एग्जिट अब 100% चालू है!

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

def place_delta_demo_order(eng, side, qty, tag="AI-Quantum", is_exit=False):
    if (not ALGO_EXECUTION_ENABLED) or (not eng.get("initialized", False)) or qty <= 0:
        return False
    try:
        prod_id = int(eng.get("delta_btc_product_id", 27))
        ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")

        payload = {
            "product_id": prod_id,
            "size": int(qty),
            "side": side.lower(),
            "order_type": "market_order"
        }
        if is_exit:
            payload["reduce_only"] = True

        ok, resp = delta_request("POST", "/v2/orders", payload)

        # यदि लाइव ट्रेड इस सेशन में खुला था और reduce_only अटका, तो काउंटर मार्केट ऑर्डर से तुरंत एग्जिट करें
        if (not ok) and is_exit and eng.get("live_order_active", False):
            payload_fallback = {
                "product_id": prod_id,
                "size": int(qty),
                "side": side.lower(),
                "order_type": "market_order"
            }
            ok, resp = delta_request("POST", "/v2/orders", payload_fallback)

        if ok:
            eng["delta_status"] = f"✅ [{ist_now}] Delta {tag}: {side.upper()} {qty} Lots सफल!"
        else:
            eng["delta_status"] = f"⚠️ [{ist_now}] Delta {tag} ({side.upper()} {qty}L): {resp}"
        return ok
    except Exception as e:
        eng["delta_status"] = f"⚠️ Delta Error: {str(e)}"
        return False

# ============================================================================
# CORE QUANTUM PARAMETERS (EXACT V16 TURBO LOGIC — STEALTH DESIGN)
# ============================================================================
USD_INR_RATE         = 85.0
BROK_PER_QTY         = 82.38   # Real Delta CSV Fee: 82.38 pts/Qty ($0.08238 = ₹7.002 per Qty Round-Trip)

STAGE1_TRIG_UNITS    = 1.00
STAGE1_LOCK_UNITS    = 0.85
STAGE1_MIN_PTS_Q     = 215.0   # कम से कम +215 pts/Q लॉक
STAGE2_TRIG_UNITS    = 1.75
STAGE2_FLOOR_UNITS   = 1.35
CLOSE_TRAIL_UNITS    = 1.15

MAX_WAVE_STREAK      = 5
MAX_DLINE_DIST       = 2.6
MIN_FLOW_DOM         = 50.0

ATR_PERIOD           = 5
USE_SMOOTHING        = True
SMOOTH_PERIOD        = 14

SL_UNITS             = 1.40
MAX_SL_PTS_PER_QTY   = 235.3
ANTI_WICK_SL         = True
MINTICK              = 0.1

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

# ============================================================================
# MARKET DATA FETCHERS
# ============================================================================
def fetch_hl_live_mid_price():
    try:
        r = requests.post(
            HYPERLIQUID_INFO_URL,
            json={"type": "allMids"},
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "BTC" in data:
                return float(data["BTC"])
    except Exception:
        pass
    return None

def fetch_hl_klines_range(interval, start_ms, end_ms):
    for attempt in range(3):
        try:
            r = requests.post(
                HYPERLIQUID_INFO_URL,
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": "BTC",
                        "interval": interval,
                        "startTime": start_ms,
                        "endTime": end_ms
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=10
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
    return []

def calc_daily_atr5():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (22 * 86400 * 1000)
    klines_1d = fetch_hl_klines_range("1d", start_ms, now_ms)
    if not klines_1d or len(klines_1d) < ATR_PERIOD + 2:
        return 2800.0
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
# REAL-TIME INTRABAR LIVE TICK MONITOR (STAGE LOCKS & CRASH SL AUTO-EXIT)
# ============================================================================
def check_live_intrabar_ticks(eng, live_px):
    if not eng.get("initialized", False) or eng["trade_dir"] == 0 or live_px <= 0:
        return

    t_dir = eng["trade_dir"]
    t_label = "LONG" if t_dir == 1 else "SHORT"
    close_side = "sell" if t_dir == 1 else "buy"
    total_qty = eng["total_qty"]
    unit_size = eng["unit_size"]
    brok_tot = BROK_PER_QTY * total_qty
    s1_lock_pts_q = max(unit_size * STAGE1_LOCK_UNITS, STAGE1_MIN_PTS_Q)
    now_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M:%S %p")

    # 1. Live Stage-1 Lock Trigger
    hit_tp1_live = (not eng["tp1_reached"]) and ((live_px >= eng["tp1_price"]) if t_dir == 1 else (live_px <= eng["tp1_price"]))
    if hit_tp1_live:
        eng["tp1_reached"] = True
        eng["wins"] += 1
        s1_sl = (eng["entry_price"] + s1_lock_pts_q) if t_dir == 1 else (eng["entry_price"] - s1_lock_pts_q)
        eng["stop_price"] = max(eng["stop_price"], s1_sl) if t_dir == 1 else min(eng["stop_price"], s1_sl)

    # 2. Live Stage-2 Big Wave Trigger
    hit_tp2_live = eng["tp1_reached"] and (not eng["tp2_reached"]) and ((live_px >= eng["tp2_price"]) if t_dir == 1 else (live_px <= eng["tp2_price"]))
    if hit_tp2_live:
        eng["tp2_reached"] = True
        eng["tp2_hits"] += 1
        s2_floor_pts = max(unit_size * STAGE2_FLOOR_UNITS, s1_lock_pts_q + 85.0)
        s2_sl = (eng["entry_price"] + s2_floor_pts) if t_dir == 1 else (eng["entry_price"] - s2_floor_pts)
        eng["stop_price"] = max(eng["stop_price"], s2_sl) if t_dir == 1 else min(eng["stop_price"], s2_sl)

    # 3. Live Hard Crash Protection before Stage-1
    if not eng["tp1_reached"]:
        hit_hard_crash = (live_px <= eng["hard_stop_price"]) if t_dir == 1 else (live_px >= eng["hard_stop_price"])
        if hit_hard_crash:
            eng["losses"] += 1
            loss_per_qty = eng["locked_sl_pts"]
            total_loss_tot = loss_per_qty * total_qty
            eng["gross_loss"] += total_loss_tot
            eng["total_brok"] += brok_tot
            net_loss_inr = pts_to_inr(-(total_loss_tot + brok_tot))

            eng["trade_logs"].insert(0, {
                "time": now_ist, "type": f"{t_label} ({total_qty}L {eng['entry_tag']})", "entry": eng["entry_price"],
                "exit": live_px, "status": f"🛑 LIVE SHIELD SL ({total_qty}L)",
                "pnl": f"-{loss_per_qty:,.0f}p/L (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"
            })
            eng["trade_logs"] = eng["trade_logs"][:50]
            place_delta_demo_order(eng, close_side, total_qty, tag="Live Shield SL Exit", is_exit=True)
            eng["trade_dir"] = 0
            eng["live_order_active"] = False

# ============================================================================
# STATEFUL BAR PROCESSOR (HANDLES BOTH HISTORICAL WARMUP & LIVE AUTO-TRADING)
# ============================================================================
def process_closed_bar(eng, kline):
    bar_time_ms = int(kline[0])
    if bar_time_ms <= eng["last_bar_time"]:
        return

    ist_offset_sec = 19800
    t_sec_ist = int(bar_time_ms // 1000) + ist_offset_sec
    o = float(kline[1])
    h = float(kline[2])
    l = float(kline[3])
    c = float(kline[4])
    v = float(kline[5])
    bar_ist = (datetime.utcfromtimestamp(bar_time_ms / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M %p")

    idx = eng["bar_count"]
    unit_size = eng["unit_size"]
    st_factor = eng["st_factor"]
    total_qty = eng["total_qty"]
    brok_tot = BROK_PER_QTY * total_qty

    s1_lock_pts_q = max(unit_size * STAGE1_LOCK_UNITS, STAGE1_MIN_PTS_Q)
    s1_trig_pts_q = max(unit_size * STAGE1_TRIG_UNITS, s1_lock_pts_q + 30.0)

    if idx == 0:
        eng["atr14"] = h - l
        eng["ema21"] = c
        eng["rsi14"] = 50.0
    else:
        prev_c = eng["prev_close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        if idx < 14:
            eng["tr_sum"] += tr
            eng["atr14"] = eng["tr_sum"] / float(idx + 1)
        else:
            eng["atr14"] = (eng["atr14"] * 13.0 + tr) / 14.0

        k_ema = 2.0 / 22.0
        eng["ema21"] = c * k_ema + eng["ema21"] * (1.0 - k_ema)

        diff = c - prev_c
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

    w = (2.0 * math.pi) / float(SMOOTH_PERIOD)
    b_g = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a_g = -b_g + math.sqrt(b_g * b_g + 2.0 * b_g)
    if idx == 0:
        g_val = c
    elif idx == 1:
        g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * eng["g1"] - ((1.0 - a_g) ** 2) * c
    else:
        g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * eng["g1"] - ((1.0 - a_g) ** 2) * eng["g2"]
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

    eval_price = (c * 0.70 + g_val * 0.30) if USE_SMOOTHING else c

    step_up = False
    step_dn = False

    if idx == 0:
        eng["q_top"] = c
        eng["q_bot"] = c - unit_size
        eng["q_dir"] = 1
        eng["q_streak"] = 1
    else:
        if eval_price >= eng["q_top"] + unit_size:
            steps = int(math.floor((eval_price - eng["q_top"]) / unit_size))
            eng["q_top"] = eng["q_top"] + (steps * unit_size)
            eng["q_bot"] = eng["q_top"] - unit_size
            step_up = True
            eng["q_streak"] = steps if eng["q_dir"] == -1 else (eng["q_streak"] + steps)
            eng["q_dir"] = 1
        elif eval_price <= eng["q_bot"] - unit_size:
            steps = int(math.floor((eng["q_bot"] - eval_price) / unit_size))
            eng["q_bot"] = eng["q_bot"] - (steps * unit_size)
            eng["q_top"] = eng["q_bot"] + unit_size
            step_dn = True
            eng["q_streak"] = steps if eng["q_dir"] == 1 else (eng["q_streak"] + steps)
            eng["q_dir"] = -1

    q_core = eng["q_top"] if eng["q_dir"] == 1 else eng["q_bot"]
    eng["q_core"] = q_core

    band_distance = unit_size * float(st_factor)
    raw_support = q_core - band_distance
    raw_resistance = q_core + band_distance

    prev_trend = eng["n_trend"]
    prev_supp = eng["support_band"]
    prev_res = eng["resistance_band"]

    if prev_supp is None:
        support_band = raw_support
    elif prev_trend == 1:
        support_band = raw_support if (eng["q_dir"] == 1 and raw_support > prev_supp) else prev_supp
    else:
        support_band = raw_support

    if prev_res is None:
        resistance_band = raw_resistance
    elif prev_trend == -1:
        resistance_band = raw_resistance if (eng["q_dir"] == -1 and raw_resistance < prev_res) else prev_res
    else:
        resistance_band = raw_resistance

    if prev_trend == -1 and eng["q_dir"] == 1 and prev_res is not None and q_core > prev_res:
        n_trend = 1
        support_band = q_core - band_distance
    elif prev_trend == 1 and eng["q_dir"] == -1 and prev_supp is not None and q_core < prev_supp:
        n_trend = -1
        resistance_band = q_core + band_distance
    else:
        n_trend = prev_trend

    eng["support_band"] = support_band
    eng["resistance_band"] = resistance_band
    eng["n_trend"] = n_trend

    n_line = support_band if n_trend == 1 else resistance_band
    eng["n_line"] = n_line

    flip_buy = (idx > 0) and (n_trend == 1 and prev_trend == -1)
    flip_sell = (idx > 0) and (n_trend == -1 and prev_trend == 1)

    if flip_buy or flip_sell:
        eng["q_streak"] = 1

    if flip_buy:
        eng["pending_flip_buy"] = True
        eng["pending_flip_sell"] = False
    if flip_sell:
        eng["pending_flip_sell"] = True
        eng["pending_flip_buy"] = False
    if n_trend == -1:
        eng["pending_flip_buy"] = False
    if n_trend == 1:
        eng["pending_flip_sell"] = False

    # Save to chart series
    eng["candles_js"].append({"time": t_sec_ist, "open": round(o, 1), "high": round(h, 1), "low": round(l, 1), "close": round(c, 1)})
    eng["qcore_js"].append({"time": t_sec_ist, "value": round(q_core, 1)})
    eng["nline_js"].append({"time": t_sec_ist, "value": round(n_line, 1), "color": "#00e676" if n_trend == 1 else "#ff5252"})
    eng["dline_js"].append({"time": t_sec_ist, "value": round(eng["ema21"], 1)})

    # ========================================================================
    # MANAGE ACTIVE TRADE & AUTO-EXIT ON DELTA
    # ========================================================================
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        close_side = "sell" if t_dir == 1 else "buy"
        eng["max_fav_close"] = max(eng["max_fav_close"], c) if t_dir == 1 else min(eng["max_fav_close"], c)

        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["wins"] += 1
            s1_sl = (eng["entry_price"] + s1_lock_pts_q) if t_dir == 1 else (eng["entry_price"] - s1_lock_pts_q)
            eng["stop_price"] = max(eng["stop_price"], s1_sl) if t_dir == 1 else min(eng["stop_price"], s1_sl)

        hit_tp2_now = eng["tp1_reached"] and (not eng["tp2_reached"]) and ((h >= eng["tp2_price"]) if t_dir == 1 else (l <= eng["tp2_price"]))
        if hit_tp2_now:
            eng["tp2_reached"] = True
            eng["tp2_hits"] += 1
            s2_floor_pts = max(unit_size * STAGE2_FLOOR_UNITS, s1_lock_pts_q + 85.0)
            s2_sl = (eng["entry_price"] + s2_floor_pts) if t_dir == 1 else (eng["entry_price"] - s2_floor_pts)
            eng["stop_price"] = max(eng["stop_price"], s2_sl) if t_dir == 1 else min(eng["stop_price"], s2_sl)

        if eng["tp1_reached"]:
            if t_dir == 1 and n_trend == 1 and n_line > eng["stop_price"]:
                eng["stop_price"] = n_line
            elif t_dir == -1 and n_trend == -1 and n_line < eng["stop_price"]:
                eng["stop_price"] = n_line

        if eng["trade_dir"] != 0 and eng["tp2_reached"]:
            gap_dist = unit_size * CLOSE_TRAIL_UNITS
            q_trail = (q_core - gap_dist) if t_dir == 1 else (q_core + gap_dist)
            close_trail = (eng["max_fav_close"] - gap_dist) if t_dir == 1 else (eng["max_fav_close"] + gap_dist)
            cand_trail = max(q_trail, close_trail, n_line if n_trend == 1 else 0.0) if t_dir == 1 else min(q_trail, close_trail, n_line if n_trend == -1 else 999999.0)
            eng["stop_price"] = max(eng["stop_price"], cand_trail) if t_dir == 1 else min(eng["stop_price"], cand_trail)

            close_hit_trail = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
            n_reversed      = (n_trend == -1) if t_dir == 1 else (n_trend == 1)

            if (close_hit_trail or n_reversed) and not hit_tp2_now:
                exit_p = max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"])
                s2_min_q = max(unit_size * STAGE2_FLOOR_UNITS, s1_lock_pts_q + 85.0)
                run_pts_per_q = max(s2_min_q, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                total_trade_pnl = run_pts_per_q * total_qty
                eng["gross_profit"] += total_trade_pnl
                eng["total_brok"] += brok_tot
                net_inr = pts_to_inr(total_trade_pnl - brok_tot)

                eng["markers_js"].append({
                    "time": t_sec_ist,
                    "position": "aboveBar" if t_dir == 1 else "belowBar",
                    "color": "#38bdf8",
                    "shape": "circle",
                    "text": f"🚀 WAVE EXIT (₹{net_inr:+,.0f})"
                })
                eng["trade_logs"].insert(0, {
                    "time": bar_ist, "type": f"{t_label} ({total_qty}L {eng['entry_tag']})", "entry": eng["entry_price"],
                    "exit": exit_p, "status": "🚀 QUANTUM WAVE EXIT",
                    "pnl": f"+{run_pts_per_q:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#38bdf8"
                })
                eng["trade_logs"] = eng["trade_logs"][:50]
                place_delta_demo_order(eng, close_side, total_qty, tag="Quantum Wave Exit", is_exit=True)
                eng["trade_dir"] = 0
                eng["live_order_active"] = False

        if eng["trade_dir"] != 0 and not eng["tp2_reached"]:
            if not eng["tp1_reached"]:
                adverse_close_pts = (eng["entry_price"] - c) if t_dir == 1 else (c - eng["entry_price"])
                unit_sl_price = (eng["entry_price"] - unit_size * SL_UNITS) if t_dir == 1 else (eng["entry_price"] + unit_size * SL_UNITS)
                close_hit_sl = (c <= unit_sl_price) if t_dir == 1 else (c >= unit_sl_price)
                q_turned_bad = (
                    (eng["q_dir"] == -1 and c < eng["q_bot"] and adverse_close_pts >= MAX_SL_PTS_PER_QTY * 0.65)
                    if t_dir == 1
                    else (eng["q_dir"] == 1 and c > eng["q_top"] and adverse_close_pts >= MAX_SL_PTS_PER_QTY * 0.65)
                )
                n_turned_bad = ((n_trend == -1) if t_dir == 1 else (n_trend == 1)) and (adverse_close_pts > 0)
                hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

                if close_hit_sl or q_turned_bad or n_turned_bad or hard_crash:
                    eng["losses"] += 1
                    loss_per_qty = min(adverse_close_pts, eng["locked_sl_pts"]) if (ANTI_WICK_SL and not hard_crash and adverse_close_pts > 0) else eng["locked_sl_pts"]
                    total_loss_tot = loss_per_qty * total_qty
                    eng["gross_loss"] += total_loss_tot
                    eng["total_brok"] += brok_tot
                    net_loss_inr = pts_to_inr(-(total_loss_tot + brok_tot))

                    eng["markers_js"].append({
                        "time": t_sec_ist,
                        "position": "belowBar" if t_dir == 1 else "aboveBar",
                        "color": "#f87171",
                        "shape": "circle",
                        "text": f"🛑 SL (₹{net_loss_inr:+,.0f})"
                    })
                    eng["trade_logs"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} ({total_qty}L {eng['entry_tag']})", "entry": eng["entry_price"],
                        "exit": c, "status": f"🛑 SHIELD SL ({total_qty}L)",
                        "pnl": f"-{loss_per_qty:,.0f}p/L (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"
                    })
                    eng["trade_logs"] = eng["trade_logs"][:50]
                    place_delta_demo_order(eng, close_side, total_qty, tag="Shield SL Exit", is_exit=True)
                    eng["trade_dir"] = 0
                    eng["live_order_active"] = False
            else:
                hit_s1_close = (c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])
                n_turned_bad = (n_trend == -1) if t_dir == 1 else (n_trend == 1)

                if (hit_s1_close or n_turned_bad) and not hit_tp1_now:
                    exit_p = max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"])
                    locked_pts_q = max(s1_lock_pts_q, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                    total_trade_pnl = locked_pts_q * total_qty
                    eng["gross_profit"] += total_trade_pnl
                    eng["total_brok"] += brok_tot
                    net_inr = pts_to_inr(total_trade_pnl - brok_tot)

                    eng["markers_js"].append({
                        "time": t_sec_ist,
                        "position": "aboveBar" if t_dir == 1 else "belowBar",
                        "color": "#4ade80",
                        "shape": "circle",
                        "text": f"✅ S1 LOCK (₹{net_inr:+,.0f})"
                    })
                    eng["trade_logs"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} ({total_qty}L {eng['entry_tag']})", "entry": eng["entry_price"],
                        "exit": exit_p, "status": "✅ STAGE-1 PROFIT LOCK",
                        "pnl": f"+{locked_pts_q:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#22c55e"
                    })
                    eng["trade_logs"] = eng["trade_logs"][:50]
                    place_delta_demo_order(eng, close_side, total_qty, tag="Stage-1 Lock Exit", is_exit=True)
                    eng["trade_dir"] = 0
                    eng["live_order_active"] = False

    # ========================================================================
    # NEW ENTRY SIGNALS & AUTO-ENTRY ON DELTA (STEALTH TAGS)
    # ========================================================================
    ema21 = eng["ema21"]
    rsi14 = eng["rsi14"]
    q_dir = eng["q_dir"]
    q_streak = eng["q_streak"]

    candle_not_giant = (h - l) <= unit_size * 1.90
    bull_filter_ok   = candle_not_giant and buy_dom_pct >= MIN_FLOW_DOM and 48.0 <= rsi14 < 76.0
    bear_filter_ok   = candle_not_giant and sell_dom_pct >= MIN_FLOW_DOM and 24.0 < rsi14 <= 52.0

    trigger_flip_buy  = eng["pending_flip_buy"] and n_trend == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and n_trend == -1 and bear_filter_ok and c < o

    streak_ok  = q_streak <= MAX_WAVE_STREAK
    stretch_ok = abs(c - ema21) <= unit_size * MAX_DLINE_DIST
    trigger_cont_buy  = (not trigger_flip_buy) and n_trend == 1 and q_dir == 1 and step_up and bull_filter_ok and c > ema21 and streak_ok and stretch_ok
    trigger_cont_sell = (not trigger_flip_sell) and n_trend == -1 and q_dir == -1 and step_dn and bear_filter_ok and c < ema21 and streak_ok and stretch_ok

    pullback_bounce_buy  = (not trigger_flip_buy) and (not trigger_cont_buy) and n_trend == 1 and q_dir == 1 and l <= (ema21 + unit_size * 0.15) and c > ema21 and c > o and (c - o) >= (unit_size * 0.30) and buy_dom_pct >= 54.0 and 50.0 < rsi14 < 70.0
    pullback_bounce_sell = (not trigger_flip_sell) and (not trigger_cont_sell) and n_trend == -1 and q_dir == -1 and h >= (ema21 - unit_size * 0.15) and c < ema21 and c < o and (o - c) >= (unit_size * 0.30) and sell_dom_pct >= 54.0 and 30.0 < rsi14 < 50.0

    can_open_trade = (eng["trade_dir"] == 0) or (eng["tp1_reached"] and (flip_buy or flip_sell))

    if can_open_trade and (trigger_flip_buy or trigger_cont_buy or pullback_bounce_buy or trigger_flip_sell or trigger_cont_sell or pullback_bounce_sell):
        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            old_close_side = "sell" if eng["trade_dir"] == 1 else "buy"
            runner_pts_q = max(s1_lock_pts_q, (c - eng["entry_price"]) if eng["trade_dir"] == 1 else (eng["entry_price"] - c))
            tot_flip_pnl = runner_pts_q * total_qty
            eng["gross_profit"] += tot_flip_pnl
            eng["total_brok"] += brok_tot
            net_flip_inr = pts_to_inr(tot_flip_pnl - brok_tot)
            eng["trade_logs"].insert(0, {
                "time": bar_ist, "type": f"{old_label} ({total_qty}L {eng['entry_tag']})", "entry": eng["entry_price"],
                "exit": c, "status": "✅ MATRIX FLIP WIN",
                "pnl": f"+{runner_pts_q:,.0f}p/L (Net ₹{net_flip_inr:+,.0f})", "color": "#22c55e"
            })
            eng["trade_logs"] = eng["trade_logs"][:50]
            place_delta_demo_order(eng, old_close_side, total_qty, tag="Matrix Flip Close", is_exit=True)

        is_long = trigger_flip_buy or trigger_cont_buy or pullback_bounce_buy
        if is_long:
            eng["pending_flip_buy"] = False
        else:
            eng["pending_flip_sell"] = False

        eng["trade_dir"] = 1 if is_long else -1
        eng["entry_bar"] = idx
        eng["entry_price"] = c
        eng["max_fav_close"] = c
        eng["tp1_reached"] = False
        eng["tp2_reached"] = False
        if trigger_flip_buy or trigger_flip_sell:
            eng["entry_tag"] = "🔥 Q-Alpha"
        elif pullback_bounce_buy or pullback_bounce_sell:
            eng["entry_tag"] = "🎯 P-Pulse"
        else:
            eng["entry_tag"] = f"⚡ W#{q_streak}"
        eng["entry_time_str"] = bar_ist

        eng["locked_tp1_pts"] = s1_trig_pts_q
        eng["locked_tp2_pts"] = unit_size * STAGE2_TRIG_UNITS
        eng["locked_sl_pts"]  = MAX_SL_PTS_PER_QTY

        eng["tp1_price"]       = (c + eng["locked_tp1_pts"]) if is_long else (c - eng["locked_tp1_pts"])
        eng["tp2_price"]       = (c + eng["locked_tp2_pts"]) if is_long else (c - eng["locked_tp2_pts"])
        eng["stop_price"]      = (c - eng["locked_sl_pts"]) if is_long else (c + eng["locked_sl_pts"])
        eng["hard_stop_price"] = (c - unit_size * 1.65) if is_long else (c + unit_size * 1.65)

        eng["markers_js"].append({
            "time": t_sec_ist,
            "position": "belowBar" if is_long else "aboveBar",
            "color": "#00e676" if is_long else "#ff1744",
            "shape": "arrowUp" if is_long else "arrowDown",
            "text": f"{'BUY' if is_long else 'SELL'} {eng['entry_tag']} @ {c:,.0f}"
        })

        entry_side = "buy" if is_long else "sell"
        if eng.get("initialized", False):
            eng["live_order_active"] = True
            place_delta_demo_order(eng, entry_side, total_qty, tag=f"AI Entry ({eng['entry_tag']})", is_exit=False)
        else:
            eng["live_order_active"] = False

    eng["prev_close"] = c
    eng["last_bar_time"] = bar_time_ms
    eng["bar_count"] += 1

# ============================================================================
# ENGINE INITIALIZER & 24x7 BACKGROUND AUTO-TRADING WORKER
# ============================================================================
def reset_and_warmup_engine(eng, signal_tf, st_factor, range_divisor, total_qty):
    eng["initialized"] = False
    eng["signal_tf"] = signal_tf
    eng["st_factor"] = float(st_factor)
    eng["range_divisor"] = float(range_divisor)
    eng["total_qty"] = int(total_qty)
    eng["config_key"] = f"{signal_tf}_{st_factor}_{range_divisor}_{total_qty}"

    macro_range = calc_daily_atr5()
    eng["macro_range"] = macro_range
    eng["unit_size"] = max(macro_range / float(range_divisor), MINTICK * 2.0)

    now_sec = int(time.time())
    today_00_utc_sec = (now_sec // 86400) * 86400
    days_back = 45 if signal_tf == "1h" else (25 if signal_tf == "15m" else 10)
    eng["days_back"] = days_back
    anchor_start_ms = (today_00_utc_sec - (days_back * 86400)) * 1000
    now_ms = now_sec * 1000

    eng["bar_count"] = 0
    eng["last_bar_time"] = 0
    eng["prev_close"] = 0.0
    eng["tr_sum"] = 0.0
    eng["atr14"] = 15.0
    eng["ema21"] = 0.0
    eng["up_sum"] = 0.0
    eng["dn_sum"] = 0.0
    eng["rma_up"] = 0.0
    eng["rma_dn"] = 0.0
    eng["rsi14"] = 50.0
    eng["g1"] = 0.0
    eng["g2"] = 0.0
    eng["buy_v1"] = 0.0
    eng["buy_v2"] = 0.0
    eng["sell_v1"] = 0.0
    eng["sell_v2"] = 0.0
    eng["buy_dom_pct"] = 50.0
    eng["sell_dom_pct"] = 50.0
    eng["q_top"] = 0.0
    eng["q_bot"] = 0.0
    eng["q_dir"] = 1
    eng["q_streak"] = 1
    eng["q_core"] = 0.0
    eng["support_band"] = None
    eng["resistance_band"] = None
    eng["n_trend"] = 1
    eng["n_line"] = 0.0
    eng["pending_flip_buy"] = False
    eng["pending_flip_sell"] = False

    eng["trade_dir"] = 0
    eng["entry_bar"] = -1
    eng["entry_price"] = 0.0
    eng["tp1_price"] = 0.0
    eng["tp2_price"] = 0.0
    eng["stop_price"] = 0.0
    eng["hard_stop_price"] = 0.0
    eng["max_fav_close"] = 0.0
    eng["locked_tp1_pts"] = 0.0
    eng["locked_tp2_pts"] = 0.0
    eng["locked_sl_pts"] = 0.0
    eng["tp1_reached"] = False
    eng["tp2_reached"] = False
    eng["entry_tag"] = ""
    eng["entry_time_str"] = ""
    eng["wins"] = 0
    eng["losses"] = 0
    eng["tp2_hits"] = 0
    eng["gross_profit"] = 0.0
    eng["gross_loss"] = 0.0
    eng["total_brok"] = 0.0

    eng["candles_js"] = []
    eng["qcore_js"] = []
    eng["nline_js"] = []
    eng["dline_js"] = []
    eng["markers_js"] = []
    eng["trade_logs"] = []

    klines = fetch_hl_klines_range(signal_tf, anchor_start_ms, now_ms)
    if klines and len(klines) > 30:
        for b in klines[:-1]:
            process_closed_bar(eng, b)
        last_k = klines[-1]
        eng["live_bar"] = {
            "time": int(last_k[0] // 1000) + 19800,
            "open": round(float(last_k[1]), 1),
            "high": round(float(last_k[2]), 1),
            "low": round(float(last_k[3]), 1),
            "close": round(float(last_k[4]), 1)
        }
        eng["last_price"] = float(last_k[4])
        eng["initialized"] = True

def background_worker(eng, my_worker_id):
    init_delta_product_id(eng)
    last_kline_poll = 0.0

    while True:
        if eng.get("active_worker_id") != my_worker_id:
            break
        try:
            if eng.get("initialized", False):
                now_ts = time.time()

                # 1. हर 2 सेकंड में लाइव टिक प्राइस चेक और इंट्रा-बार स्टेज/SL लॉक
                live_px = fetch_hl_live_mid_price()
                if live_px and live_px > 0:
                    eng["last_price"] = live_px
                    lb = eng.get("live_bar")
                    if lb:
                        lb["high"] = round(max(lb["high"], live_px), 1)
                        lb["low"] = round(min(lb["low"], live_px), 1)
                        lb["close"] = round(live_px, 1)
                    check_live_intrabar_ticks(eng, live_px)

                # 2. हर 4 सेकंड में नई क्लोज हुई कैंडल चेक करें -> नया सिग्नल या एग्जिट आते ही तुरंत डेल्टा आर्डर फायर करें!
                if now_ts - last_kline_poll >= 4.0:
                    tf = eng["signal_tf"]
                    tf_ms = 3600000 if tf == "1h" else (900000 if tf == "15m" else 300000)
                    end_ms = int(now_ts * 1000)
                    start_ms = end_ms - (8 * tf_ms)
                    recent_klines = fetch_hl_klines_range(tf, start_ms, end_ms)
                    if recent_klines and len(recent_klines) >= 2:
                        for b in recent_klines[:-1]:
                            process_closed_bar(eng, b)
                        lk = recent_klines[-1]
                        eng["live_bar"] = {
                            "time": int(lk[0] // 1000) + 19800,
                            "open": round(float(lk[1]), 1),
                            "high": round(float(lk[2]), 1),
                            "low": round(float(lk[3]), 1),
                            "close": round(float(lk[4]), 1)
                        }
                        eng["last_price"] = float(lk[4])
                    last_kline_poll = now_ts
        except Exception as e:
            eng["last_error"] = str(e)
        time.sleep(2.0)

@st.cache_resource
def get_quantum_live_v17_engine():
    worker_id = int(time.time() * 1000)
    eng = {
        "active_worker_id": worker_id,
        "initialized": False,
        "live_order_active": False,
        "config_key": "",
        "signal_tf": "15m",
        "st_factor": 2.0,
        "range_divisor": 12.0,
        "total_qty": 25,
        "delta_btc_product_id": 27,
        "delta_status": "🤖 Delta Live Algo: ACTIVE (Auto-Entry & Auto-Exit Ready)",
        "last_price": 0.0,
        "live_bar": None,
        "last_error": None
    }
    reset_and_warmup_engine(eng, "15m", 2.0, 12.0, 25)
    t = threading.Thread(target=background_worker, args=(eng, worker_id), daemon=True)
    t.start()
    return eng

eng = get_quantum_live_v17_engine()
server_ip = get_server_public_ip()

# ============================================================================
# TOP CONTROL BAR (STEALTH LABELS + DELTA CONNECTION TEST BUTTON + FORCE EXIT)
# ============================================================================
r1_c1, r1_c2, r1_c3, r1_c4 = st.columns([0.46, 0.18, 0.18, 0.18])
with r1_c1:
    st.markdown(
        f"**🌐 Server IP:** `{server_ip}` | <span style='color:#4ade80;font-weight:700;'>{eng.get('delta_status', 'Ready')}</span>",
        unsafe_allow_html=True
    )
with r1_c2:
    if st.button("🔌 Delta API कनेक्शन टेस्ट करें"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        if ok:
            eng["delta_status"] = f"✅ Delta Demo API Connected! (Auto-Trading ON | IP: {server_ip})"
        else:
            eng["delta_status"] = f"⚠️ Delta API Error: {resp}"
        st.rerun()
with r1_c3:
    if st.button("🛑 Force Close Delta Trade"):
        if eng.get("trade_dir", 0) != 0:
            close_side = "sell" if eng["trade_dir"] == 1 else "buy"
            eng["live_order_active"] = True
            place_delta_demo_order(eng, close_side, eng["total_qty"], tag="Manual Force Exit", is_exit=True)
            eng["trade_dir"] = 0
            eng["live_order_active"] = False
        else:
            eng["delta_status"] = "ℹ️ अभी कोई ओपन ट्रेड नहीं है"
        st.rerun()
with r1_c4:
    if st.button("🔄 चार्ट व डेटा सिंक करें"):
        st.rerun()

r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([0.22, 0.26, 0.26, 0.26])
with r2_c1:
    selected_tf = st.selectbox("⏱️ Timeframe", ["15m", "5m", "1h"], index=0, label_visibility="collapsed")
with r2_c2:
    qty_label = st.selectbox(
        "📦 Position Size",
        [
            "25 Lots (1p = ₹2.12)",
            "50 Lots (1p = ₹4.25)",
            "30 Lots (1p = ₹2.55)",
            "20 Lots (1p = ₹1.70)",
            "10 Lots (1p = ₹0.85)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    selected_qty = int(qty_label.split()[0])
with r2_c3:
    div_label = st.selectbox(
        "🧬 Matrix Grid Mode",
        [
            "Mode 12 (Balanced Pro)",
            "Mode 14 (High Frequency)",
            "Mode 10 (Macro Wave)",
            "Mode 16 (Turbo Scalper)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    selected_divisor = float(div_label.split()[1])
with r2_c4:
    st_mult_label = st.selectbox(
        "🛡️ Neural Shield Sensitivity",
        [
            "Core 2.0 (Fast Shield - Best)",
            "Core 2.2 (Balanced Shield)",
            "Core 1.8 (Ultra Shield)",
            "Core 2.5 (Wide Shield)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    selected_st_mult = float(st_mult_label.split()[1])

desired_cfg = f"{selected_tf}_{selected_st_mult}_{selected_divisor}_{selected_qty}"
if eng.get("config_key") != desired_cfg:
    reset_and_warmup_engine(eng, selected_tf, selected_st_mult, selected_divisor, selected_qty)

if not eng.get("initialized", False) or not eng.get("candles_js"):
    st.warning("⏳ AI-Quantum Pro: लाइव चार्ट और न्यूरल सिग्नल्स सिंक हो रहे हैं...")
    st.stop()

# Build combined chart series including the currently forming live bar
candles_full = list(eng["candles_js"])
qcore_full   = list(eng["qcore_js"])
nline_full   = list(eng["nline_js"])
dline_full   = list(eng["dline_js"])

if eng.get("live_bar"):
    lb = eng["live_bar"]
    candles_full.append(lb)
    qcore_full.append({"time": lb["time"], "value": round(eng["q_core"], 1)})
    nline_full.append({"time": lb["time"], "value": round(eng["n_line"], 1), "color": "#00e676" if eng["n_trend"] == 1 else "#ff5252"})
    dline_full.append({"time": lb["time"], "value": round(eng["ema21"], 1)})

tot_tr = eng["wins"] + eng["losses"]
wr_pct = (eng["wins"] / tot_tr * 100.0) if tot_tr > 0 else 0.0
net_pnl_pts = eng["gross_profit"] - eng["gross_loss"] - eng["total_brok"]
net_inr_val = pts_to_inr(net_pnl_pts)
pt_inr = selected_qty * 0.001 * USD_INR_RATE
fee_per_tr_inr = pts_to_inr(BROK_PER_QTY * selected_qty)

matrix_txt = f"{selected_tf.upper()} AI MATRIX: BULLISH ▲" if eng["n_trend"] == 1 else f"{selected_tf.upper()} AI MATRIX: BEARISH ▼"
matrix_col = "#00e676" if eng["n_trend"] == 1 else "#ff5252"

active_trade_info = {
    "active": eng["trade_dir"] != 0,
    "dir": "LONG ▲" if eng["trade_dir"] == 1 else ("SHORT ▼" if eng["trade_dir"] == -1 else "NONE"),
    "dir_code": eng["trade_dir"],
    "tag": eng["entry_tag"],
    "time": eng["entry_time_str"],
    "entry": round(eng["entry_price"], 1),
    "tp1": round(eng["tp1_price"], 1),
    "tp2": round(eng["tp2_price"], 1),
    "sl": round(eng["stop_price"], 1),
    "tp1_reached": eng["tp1_reached"],
    "tp2_reached": eng["tp2_reached"]
}

# ============================================================================
# INTERACTIVE STEALTH AI-QUANTUM CHART (ZERO MENTION OF UNDERLYING INDICATORS)
# ============================================================================
candles_json = json.dumps(candles_full)
qcore_json   = json.dumps(qcore_full)
nline_json   = json.dumps(nline_full)
dline_json   = json.dumps(dline_full)
markers_json = json.dumps(eng["markers_js"])
active_json  = json.dumps(active_trade_info)

chart_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0b0e14; color: #f8fafc; font-family: sans-serif; overflow: hidden; }}
  .chart-wrapper {{
    background: #0f172a; border: 1px solid #1e293b; border-radius: 14px;
    padding: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.6);
  }}
  .top-hud {{
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 10px; margin-bottom: 8px; border-bottom: 1px solid #334155;
    flex-wrap: wrap; gap: 10px;
  }}
  .hud-left {{ display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }}
  .live-px {{ font-size: 28px; font-weight: 800; color: #ffffff; }}
  .badge {{
    padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;
    border: 1px solid {matrix_col}; color: {matrix_col}; background: #1e293b;
  }}
  .legend-bar {{
    display: flex; gap: 16px; font-size: 12px; color: #cbd5e1;
    margin-bottom: 8px; flex-wrap: wrap; align-items: center;
  }}
  .leg-item {{ display: flex; align-items: center; gap: 5px; font-weight: 600; }}
  .dot {{ width: 12px; height: 4px; border-radius: 2px; display: inline-block; }}
  .btn-bar {{ display: flex; gap: 6px; }}
  .c-btn {{
    background: #1e293b; color: #38bdf8; border: 1px solid #334155;
    padding: 4px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 700;
    cursor: pointer;
  }}
  .c-btn:hover {{ background: #334155; color: #ffffff; }}
  #tv-chart {{ width: 100%; height: 540px; border-radius: 8px; overflow: hidden; }}
</style>
</head>
<body>
<div class="chart-wrapper">
  <div class="top-hud">
    <div class="hud-left">
      <span style="color:#38bdf8; font-weight:800; font-size:13px;">⚡ DR DEVENDRA AI-QUANTUM PRO ({selected_tf.upper()} • {selected_qty} LOTS • AUTO-ALGO ON)</span>
      <span id="live-price-txt" class="live-px">${eng['last_price']:,.2f}</span>
      <span class="badge">{matrix_txt}</span>
      <span style="font-size:12px; color:#facc15; font-weight:700;">
        🧬 Q-Grid: {eng['unit_size']:,.1f}p | Q-Core: {eng['q_core']:,.1f} | Neural Shield: {eng['n_line']:,.1f}
      </span>
    </div>
    <div class="btn-bar">
      <button class="c-btn" onclick="chart.timeScale().scrollToRealTime()">⏩ Latest Candle</button>
      <button class="c-btn" onclick="chart.timeScale().fitContent()">🔍 Fit All Signals</button>
    </div>
  </div>

  <div class="legend-bar">
    <div class="leg-item"><span class="dot" style="background:#facc15;"></span> Quantum Step (Q-Core)</div>
    <div class="leg-item"><span class="dot" style="background:#00e676;"></span><span class="dot" style="background:#ff5252;"></span> Neural Shield (N-Line)</div>
    <div class="leg-item"><span class="dot" style="background:#38bdf8;"></span> Dynamic Pulse (D-Line)</div>
    <div id="hover-info" style="margin-left:auto; color:#e2e8f0; font-size:12.5px; font-weight:700;">
      🗓️ {eng['days_back']} Days: <span style="color:#facc15;">{tot_tr} Trades</span> ({eng['wins']}W / {eng['losses']}L) | 🏆 Accuracy: <span style="color:#00e676;">{wr_pct:.1f}%</span> | 🚀 Quantum Waves: {eng['tp2_hits']} | 💰 Net Profit ({selected_qty}L After Fee): <span style="color:#4ade80;font-size:15px;">₹{net_inr_val:+,.0f}</span>
    </div>
  </div>

  <div id="tv-chart"></div>
</div>

<script>
const candlesData = {candles_json};
const qcoreData   = {qcore_json};
const nlineData   = {nline_json};
const dlineData   = {dline_json};
const markersData = {markers_json};
const activeTrade = {active_json};

const container = document.getElementById('tv-chart');
const chart = LightweightCharts.createChart(container, {{
  layout: {{
    background: {{ type: 'solid', color: '#090d16' }},
    textColor: '#cbd5e1',
    fontSize: 12
  }},
  grid: {{
    vertLines: {{ color: '#1e293b' }},
    horzLines: {{ color: '#1e293b' }}
  }},
  crosshair: {{
    mode: LightweightCharts.CrosshairMode.Normal
  }},
  rightPriceScale: {{
    borderColor: '#334155',
    autoScale: true
  }},
  timeScale: {{
    borderColor: '#334155',
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 8,
    barSpacing: 10
  }}
}});

const candleSeries = chart.addCandlestickSeries({{
  upColor: '#22c55e',
  downColor: '#ef4444',
  borderUpColor: '#22c55e',
  borderDownColor: '#ef4444',
  wickUpColor: '#22c55e',
  wickDownColor: '#ef4444'
}});
candleSeries.setData(candlesData);
candleSeries.setMarkers(markersData);

const qcoreSeries = chart.addLineSeries({{
  color: '#facc15',
  lineWidth: 2,
  lineType: LightweightCharts.LineType.WithSteps,
  title: 'Q-Core'
}});
qcoreSeries.setData(qcoreData);

const nlineSeries = chart.addLineSeries({{
  lineWidth: 3,
  lineType: LightweightCharts.LineType.WithSteps,
  title: 'Neural Shield'
}});
nlineSeries.setData(nlineData);

const dlineSeries = chart.addLineSeries({{
  color: '#38bdf8',
  lineWidth: 1,
  lineStyle: LightweightCharts.LineStyle.Dashed,
  title: 'D-Line'
}});
dlineSeries.setData(dlineData);

if (activeTrade && activeTrade.active) {{
  candleSeries.createPriceLine({{
    price: activeTrade.entry,
    color: '#ffffff',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: 'ACTIVE ENTRY (' + activeTrade.dir + ')'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.tp1,
    color: '#4ade80',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'Stage-1 Lock'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.tp2,
    color: '#38bdf8',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'Quantum Wave'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.sl,
    color: activeTrade.tp1_reached ? '#00e676' : '#ef4444',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: activeTrade.tp1_reached ? 'LOCKED SHIELD SL' : 'INITIAL SHIELD SL'
  }});
}}

window.addEventListener('resize', () => {{
  chart.applyOptions({{ width: container.clientWidth }});
}});

let lastBar = candlesData[candlesData.length - 1];
setInterval(async () => {{
  try {{
    const res = await fetch('https://api.hyperliquid.xyz/info', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ type: 'allMids' }})
    }});
    if (res.ok) {{
      const d = await res.json();
      if (d && d.BTC) {{
        const px = parseFloat(d.BTC);
        const pxEl = document.getElementById('live-price-txt');
        if (pxEl) {{
          pxEl.textContent = '$' + px.toLocaleString('en-US', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
          pxEl.style.color = px >= lastBar.close ? '#4ade80' : '#f87171';
        }}
        lastBar = {{
          time: lastBar.time,
          open: lastBar.open,
          high: Math.max(lastBar.high, px),
          low: Math.min(lastBar.low, px),
          close: px
        }};
        candleSeries.update(lastBar);
      }}
    }}
  }} catch (e) {{}}
}}, 2000);
</script>
</body>
</html>"""

components.html(chart_html, height=640, scrolling=False)

# ============================================================================
# ACTIVE TRADE STATUS BANNER & STEALTH EXECUTION LOG
# ============================================================================
act = active_trade_info
if act["active"]:
    live_pts_q = (eng["last_price"] - act["entry"]) if act["dir_code"] == 1 else (act["entry"] - eng["last_price"])
    live_net_inr = pts_to_inr((live_pts_q * selected_qty) - (BROK_PER_QTY * selected_qty))
    st.markdown(
        f"""<div style="background:#1e293b; border:1.5px solid #00e676; border-radius:10px; padding:10px 14px; margin-bottom:10px; font-size:13px;">
        🔥 <b>लाइव ओपन पोज़ीशन ({selected_qty} Lots • Auto-Exit Active):</b>
        <span style="color:#facc15;font-weight:bold;">{act['dir']} ({act['tag']} @ {act['time']})</span> |
        <b>Entry:</b> {act['entry']:,.1f} | <b>Live Net PnL:</b> <span style="color:#4ade80;font-weight:800;">₹{live_net_inr:+,.0f} ({live_pts_q:+,.1f}p/L)</span> |
        <b>Stage-1 Lock:</b> {act['tp1']:,.1f} | <b>Quantum Wave:</b> {act['tp2']:,.1f} | <b>Shield SL:</b> <span style="color:#38bdf8;font-weight:bold;">{act['sl']:,.1f}</span>
        </div>""",
        unsafe_allow_html=True
    )

with st.expander(f"📜 Dr Devendra AI-Quantum Pro ({selected_tf.upper()} • {selected_qty} Lots) सिग्नल व एग्जिट लॉग (Click to Expand)", expanded=True):
    rows_html = ""
    for lg in eng["trade_logs"]:
        c_hex = lg["color"]
        rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12.5px;">
        <td style="padding:7px; color:#94a3b8;">{lg['time']}</td>
        <td style="padding:7px; color:#f8fafc; font-weight:bold;">{lg['type']}</td>
        <td style="padding:7px; color:#cbd5e1;">{lg['entry']:,.1f} → {lg['exit']:,.1f}</td>
        <td style="padding:7px; color:{c_hex}; font-weight:bold;">{lg['status']}</td>
        <td style="padding:7px; color:{c_hex}; font-weight:bold; text-align:right;">{lg['pnl']}</td>
        </tr>"""
    st.markdown(
        f"""<div style="max-height:320px; overflow-y:auto; background:#0f172a; border-radius:10px; padding:10px; border:1px solid #1e293b;">
        <table style="width:100%; border-collapse:collapse;">
        <thead><tr style="border-bottom:1px solid #475569; font-size:11.5px; color:#94a3b8; text-align:left;">
        <th style="padding:6px;">समय (IST)</th><th style="padding:6px;">AI सिग्नल</th><th style="padding:6px;">Entry → Exit</th>
        <th style="padding:6px;">एग्जिट स्टेटस</th><th style="padding:6px; text-align:right;">{selected_qty}L Net PnL (₹{fee_per_tr_inr:.0f} फीस काटकर)</th>
        </tr></thead><tbody>{rows_html}</tbody></table></div>""",
        unsafe_allow_html=True
    )

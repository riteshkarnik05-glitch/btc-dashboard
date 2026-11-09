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

st.set_page_config(page_title="Dr Devendra AI-Quantum Pro Terminal (V21)", layout="wide")

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
.locked-bar {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px;
}
@media (max-width: 768px) { .locked-bar { grid-template-columns: repeat(2, 1fr); } }
.locked-pill {
    background: #131c2e; border: 1px solid #334155; border-left: 3px solid #38bdf8;
    border-radius: 8px; padding: 7px 12px; font-size: 12.5px; color: #94a3b8;
    display: flex; justify-content: space-between; align-items: center;
}
.locked-pill b { color: #facc15; font-size: 13px; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# DELTA EXCHANGE LIVE AUTO-EXECUTION API & CONNECTION HELPERS
# ============================================================================
ALGO_EXECUTION_ENABLED = True

DELTA_API_KEY    = "m9deE36P5CmkezL8JJkJ4s9WhbFTs"
DELTA_API_SECRET = "sqRjTWnvB8WpqYlEJTCRZVP46OdbiaEUyeKLWLRXtxdvdlcWL6sBgFH2E7eC"
DELTA_URLS       = [
    "https://cdn-ind.testnet.deltaex.org",
    "https://testnet-api.delta.exchange"
]

USD_INR_RATE         = 85.0
BROK_PER_QTY         = 82.38

# ============================================================================
# 🔒 V21 ENGINE SETTINGS: 15m DAILY VWAP FILTERED + PYRAMIDING
# ============================================================================
FIXED_TF             = "15m"   
FIXED_BASE_QTY       = 25      # 25 Lots Initial Entry
FIXED_PYRAMID_QTY    = 25      # 25 Lots Added AFTER Stage-1 Safe Lock (Total 50 Lots for big run!)
FIXED_DIVISOR        = 12.0    
FIXED_ST_MULT        = 2.2     

STAGE1_TRIG_UNITS    = 1.05    
STAGE1_LOCK_UNITS    = 0.85    
STAGE1_MIN_PTS_Q     = 210.0   
STAGE2_TRIG_UNITS    = 1.85    
STAGE2_FLOOR_UNITS   = 1.35    
CLOSE_TRAIL_UNITS    = 1.15    

MAX_WAVE_STREAK      = 4
MAX_DLINE_DIST       = 2.2
MIN_FLOW_DOM         = 50.0

ATR_PERIOD           = 5
SMOOTH_PERIOD        = 14
SL_UNITS             = 1.45
MAX_SL_PTS_PER_QTY   = 235.3
ANTI_WICK_SL         = True
MINTICK              = 0.1

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

@st.cache_data(ttl=300)
def get_server_public_ip():
    for url in ["https://api.ipify.org", "https://ipv4.icanhazip.com", "https://checkip.amazonaws.com"]:
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200 and r.text.strip(): return r.text.strip()
        except Exception: pass
    return "IP लोड हो रहा है..."

def delta_request(method, path, payload_dict=None):
    body_str = json.dumps(payload_dict, separators=(',', ':')) if payload_dict else ""
    for base_url in DELTA_URLS:
        try:
            timestamp = str(int(time.time()))
            sig_data = method.upper() + timestamp + path + body_str
            signature = hmac.new(DELTA_API_SECRET.encode("utf-8"), sig_data.encode("utf-8"), hashlib.sha256).hexdigest()
            headers = {"api-key": DELTA_API_KEY, "timestamp": timestamp, "signature": signature, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "python-rest-client"}
            url = base_url + path
            if method.upper() == "GET": r = requests.get(url, headers=headers, timeout=5)
            else: r = requests.post(url, data=body_str, headers=headers, timeout=5)
            if r.status_code == 200: return True, r.json()
        except Exception: pass
    return False, "Error"

def init_delta_product_id(eng):
    for base_url in DELTA_URLS:
        try:
            r = requests.get(base_url + "/v2/products", timeout=5)
            if r.status_code == 200:
                for p in r.json().get("result", []):
                    if str(p.get("symbol", "")).upper() in ["BTCUSD", "BTCUSDT"]:
                        eng["delta_btc_product_id"] = int(p["id"])
                        return
        except Exception: pass

def place_delta_demo_order(eng, side, qty, tag="AI-Quantum", is_exit=False):
    if (not ALGO_EXECUTION_ENABLED) or (not eng.get("initialized", False)) or qty <= 0: return False
    try:
        prod_id = int(eng.get("delta_btc_product_id", 27))
        payload = {"product_id": prod_id, "size": int(qty), "side": side.lower(), "order_type": "market_order"}
        if is_exit: payload["reduce_only"] = True
        ok, resp = delta_request("POST", "/v2/orders", payload)
        if (not ok) and is_exit and eng.get("live_order_active", False):
            payload.pop("reduce_only", None)
            ok, resp = delta_request("POST", "/v2/orders", payload)
        if ok: eng["delta_status"] = f"✅ Delta {tag}: {side.upper()} {qty}L सफल!"
        else: eng["delta_status"] = f"⚠️ Delta {tag} Error!"
        return ok
    except Exception: return False

# ============================================================================
# MARKET DATA & KLINE FETCHERS
# ============================================================================
def fetch_hl_live_mid_price():
    try:
        r = requests.post(HYPERLIQUID_INFO_URL, json={"type": "allMids"}, headers={"Content-Type": "application/json"}, timeout=3)
        if r.status_code == 200: return float(r.json().get("BTC", 0))
    except: pass
    return None

def fetch_hl_klines_range(interval, start_ms, end_ms):
    for attempt in range(3):
        try:
            r = requests.post(HYPERLIQUID_INFO_URL, json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": interval, "startTime": start_ms, "endTime": end_ms}}, headers={"Content-Type": "application/json"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    data.sort(key=lambda x: int(x["t"]))
                    return [[int(k["t"]), float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k.get("v", 0.0))] for k in data]
        except: time.sleep(0.4)
    return []

def calc_daily_atr5():
    now_ms = int(time.time() * 1000)
    klines_1d = fetch_hl_klines_range("1d", now_ms - (22 * 86400 * 1000), now_ms)
    if not klines_1d or len(klines_1d) < 7: return 2800.0
    highs = [k[2] for k in klines_1d]; lows = [k[3] for k in klines_1d]; closes = [k[4] for k in klines_1d]
    tr = [highs[i]-lows[i] if i==0 else max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(len(closes))]
    rma = [0.0] * len(tr)
    for i, v in enumerate(tr):
        if i < 4: rma[i] = sum(tr[:i+1]) / float(i+1)
        elif i == 4: rma[i] = sum(tr[:5]) / 5.0
        else: rma[i] = (rma[i-1] * 4.0 + v) / 5.0
    return rma[-2]

# ============================================================================
# STATEFUL BAR PROCESSOR (V21 MACRO VWAP PYRAMIDING ENGINE)
# ============================================================================
def process_closed_bar(eng, kline):
    bar_time_ms = int(kline[0])
    if bar_time_ms <= eng["last_bar_time"]: return

    ist_offset_sec = 19800
    t_sec_ist = int(bar_time_ms // 1000) + ist_offset_sec
    o, h, l, c, v = kline[1], kline[2], kline[3], kline[4], kline[5]
    bar_dt = datetime.utcfromtimestamp(bar_time_ms / 1000.0) + timedelta(hours=5, minutes=30)
    bar_ist = bar_dt.strftime("%d %b %I:%M %p")

    idx = eng["bar_count"]
    unit_size = eng["unit_size"]
    base_qty = FIXED_BASE_QTY
    add_qty = FIXED_PYRAMID_QTY
    
    cur_qty = eng.get("active_qty", base_qty)
    brok_tot = BROK_PER_QTY * cur_qty

    s1_lock_pts_q = max(unit_size * STAGE1_LOCK_UNITS, STAGE1_MIN_PTS_Q)
    s1_trig_pts_q = max(unit_size * STAGE1_TRIG_UNITS, s1_lock_pts_q + 25.0)

    # 📌 Calculate Daily VWAP
    if bar_dt.day != eng["cur_day"]:
        eng["cur_day"] = bar_dt.day
        eng["cum_pv"] = ((h + l + c) / 3.0) * v
        eng["cum_v"] = v
    else:
        eng["cum_pv"] += ((h + l + c) / 3.0) * v
        eng["cum_v"] += v
    
    vwap_val = (eng["cum_pv"] / eng["cum_v"]) if eng["cum_v"] > 0 else c
    eng["vwap"] = vwap_val

    if idx == 0:
        eng["atr14"] = h - l; eng["ema21"] = c; eng["rsi14"] = 50.0
    else:
        prev_c = eng["prev_close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        if idx < 14: eng["tr_sum"] += tr; eng["atr14"] = eng["tr_sum"] / float(idx + 1)
        else: eng["atr14"] = (eng["atr14"] * 13.0 + tr) / 14.0
        
        eng["ema21"] = c * (2.0 / 22.0) + eng["ema21"] * (1.0 - (2.0 / 22.0))

        diff = c - prev_c
        up = max(diff, 0.0); dn = max(-diff, 0.0)
        if idx < 14:
            eng["up_sum"] += up; eng["dn_sum"] += dn
            eng["rma_up"] = eng["up_sum"] / float(idx); eng["rma_dn"] = eng["dn_sum"] / float(idx)
        else:
            eng["rma_up"] = (eng["rma_up"] * 13.0 + up) / 14.0; eng["rma_dn"] = (eng["rma_dn"] * 13.0 + dn) / 14.0
        
        if eng["rma_dn"] == 0: eng["rsi14"] = 100.0
        elif eng["rma_up"] == 0: eng["rsi14"] = 0.0
        else: eng["rsi14"] = 100.0 - (100.0 / (1.0 + eng["rma_up"] / eng["rma_dn"]))

    w = (2.0 * math.pi) / float(SMOOTH_PERIOD)
    b_g = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a_g = -b_g + math.sqrt(b_g * b_g + 2.0 * b_g)
    if idx == 0: g_val = c
    elif idx == 1: g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * eng["g1"] - ((1.0 - a_g) ** 2) * c
    else: g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * eng["g1"] - ((1.0 - a_g) ** 2) * eng["g2"]
    eng["g2"] = eng["g1"]; eng["g1"] = g_val

    rng = max(h - l, MINTICK)
    lower_wick = min(o, c) - l; upper_wick = h - max(o, c); body = abs(c - o)
    bull_score = (c - l) + (lower_wick * 1.1) + (body * 0.85 if c > o else 0.0)
    bear_score = (h - c) + (upper_wick * 1.1) + (body * 0.85 if c < o else 0.0)
    bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8); bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
    tot_pow = bull_pow + bear_pow
    bar_buy_v = v * (bull_pow / tot_pow) if tot_pow > 0 else v * 0.5
    bar_sell_v = v * (bear_pow / tot_pow) if tot_pow > 0 else v * 0.5

    roll_buy = (bar_buy_v * 1.4) + eng["buy_v1"] + eng["buy_v2"]
    roll_sell = (bar_sell_v * 1.4) + eng["sell_v1"] + eng["sell_v2"]
    roll_tot = roll_buy + roll_sell
    buy_dom_pct = (roll_buy / roll_tot) * 100.0 if roll_tot > 0 else 50.0
    sell_dom_pct = 100.0 - buy_dom_pct

    eng["buy_v2"] = eng["buy_v1"]; eng["buy_v1"] = bar_buy_v
    eng["sell_v2"] = eng["sell_v1"]; eng["sell_v1"] = bar_sell_v
    eng["buy_dom_pct"] = buy_dom_pct; eng["sell_dom_pct"] = sell_dom_pct

    eval_price = (c * 0.70 + g_val * 0.30)
    step_up = step_dn = False

    if idx == 0:
        eng["q_top"] = c; eng["q_bot"] = c - unit_size; eng["q_dir"] = 1; eng["q_streak"] = 1
    else:
        if eval_price >= eng["q_top"] + unit_size:
            steps = int((eval_price - eng["q_top"]) // unit_size)
            eng["q_top"] += steps * unit_size; eng["q_bot"] = eng["q_top"] - unit_size
            step_up = True; eng["q_streak"] = steps if eng["q_dir"] == -1 else (eng["q_streak"] + steps)
            eng["q_dir"] = 1
        elif eval_price <= eng["q_bot"] - unit_size:
            steps = int((eng["q_bot"] - eval_price) // unit_size)
            eng["q_bot"] -= steps * unit_size; eng["q_top"] = eng["q_bot"] + unit_size
            step_dn = True; eng["q_streak"] = steps if eng["q_dir"] == 1 else (eng["q_streak"] + steps)
            eng["q_dir"] = -1

    q_core = eng["q_top"] if eng["q_dir"] == 1 else eng["q_bot"]
    eng["q_core"] = q_core

    band_dist = unit_size * FIXED_ST_MULT
    raw_support = q_core - band_dist; raw_resistance = q_core + band_dist
    prev_trend = eng["n_trend"]; prev_supp = eng["support_band"]; prev_res = eng["resistance_band"]

    if prev_supp is None: support_band = raw_support
    elif prev_trend == 1: support_band = raw_support if (eng["q_dir"] == 1 and raw_support > prev_supp) else prev_supp
    else: support_band = raw_support

    if prev_res is None: resistance_band = raw_resistance
    elif prev_trend == -1: resistance_band = raw_resistance if (eng["q_dir"] == -1 and raw_resistance < prev_res) else prev_res
    else: resistance_band = raw_resistance

    if prev_trend == -1 and eng["q_dir"] == 1 and prev_res is not None and q_core > prev_res:
        n_trend = 1; support_band = q_core - band_dist
    elif prev_trend == 1 and eng["q_dir"] == -1 and prev_supp is not None and q_core < prev_supp:
        n_trend = -1; resistance_band = q_core + band_dist
    else: n_trend = prev_trend

    eng["support_band"] = support_band; eng["resistance_band"] = resistance_band; eng["n_trend"] = n_trend
    n_line = support_band if n_trend == 1 else resistance_band; eng["n_line"] = n_line

    flip_buy = (idx > 0) and (n_trend == 1 and prev_trend == -1)
    flip_sell = (idx > 0) and (n_trend == -1 and prev_trend == 1)

    if flip_buy or flip_sell: eng["q_streak"] = 1
    if flip_buy: eng["pending_flip_buy"] = True; eng["pending_flip_sell"] = False
    if flip_sell: eng["pending_flip_sell"] = True; eng["pending_flip_buy"] = False
    if n_trend == -1: eng["pending_flip_buy"] = False
    if n_trend == 1: eng["pending_flip_sell"] = False

    eng["candles_js"].append({"time": t_sec_ist, "open": round(o, 1), "high": round(h, 1), "low": round(l, 1), "close": round(c, 1)})
    eng["qcore_js"].append({"time": t_sec_ist, "value": round(q_core, 1)})
    eng["nline_js"].append({"time": t_sec_ist, "value": round(n_line, 1), "color": "#00e676" if n_trend == 1 else "#ff5252"})
    eng["dline_js"].append({"time": t_sec_ist, "value": round(eng["ema21"], 1)})
    eng["vwap_js"].append({"time": t_sec_ist, "value": round(eng["vwap"], 1)})

    # ========================================================================
    # V21 AUTO-EXIT WITH PYRAMIDING (SCALE-IN ONCE S1 IS SAFE)
    # ========================================================================
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]; t_label = "LONG" if t_dir == 1 else "SHORT"; close_side = "sell" if t_dir == 1 else "buy"
        eng["max_fav_close"] = max(eng["max_fav_close"], c) if t_dir == 1 else min(eng["max_fav_close"], c)

        # Stage-1 Hit -> Scale In (Pyramid) to 50 Lots total!
        if not eng["tp1_reached"] and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"])):
            eng["tp1_reached"] = True; eng["wins"] += 1
            s1_sl = (eng["entry_price"] + s1_lock_pts_q) if t_dir == 1 else (eng["entry_price"] - s1_lock_pts_q)
            eng["stop_price"] = max(eng["stop_price"], s1_sl) if t_dir == 1 else min(eng["stop_price"], s1_sl)
            
            # 🚀 Scale-In +25 Lots since trend is locked safe!
            eng["active_qty"] = base_qty + add_qty
            cur_qty = eng["active_qty"]
            brok_tot = BROK_PER_QTY * cur_qty
            
            eng["markers_js"].append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#facc15", "shape": "arrowUp", "text": f"📈 SCALE-IN (+{add_qty}L)"})
            place_delta_demo_order(eng, "buy" if t_dir == 1 else "sell", add_qty, tag="Pyramid Scale-In", is_exit=False)

        if eng["tp1_reached"] and not eng["tp2_reached"] and ((h >= eng["tp2_price"]) if t_dir == 1 else (l <= eng["tp2_price"])):
            eng["tp2_reached"] = True; eng["tp2_hits"] += 1
            s2_floor_pts = max(unit_size * STAGE2_FLOOR_UNITS, s1_lock_pts_q + 85.0)
            s2_sl = (eng["entry_price"] + s2_floor_pts) if t_dir == 1 else (eng["entry_price"] - s2_floor_pts)
            eng["stop_price"] = max(eng["stop_price"], s2_sl) if t_dir == 1 else min(eng["stop_price"], s2_sl)

        if eng["tp1_reached"]:
            if t_dir == 1 and n_trend == 1 and n_line > eng["stop_price"]: eng["stop_price"] = n_line
            elif t_dir == -1 and n_trend == -1 and n_line < eng["stop_price"]: eng["stop_price"] = n_line

        if eng["trade_dir"] != 0 and eng["tp2_reached"]:
            gap_dist = unit_size * CLOSE_TRAIL_UNITS
            q_trail = (q_core - gap_dist) if t_dir == 1 else (q_core + gap_dist)
            close_trail = (eng["max_fav_close"] - gap_dist) if t_dir == 1 else (eng["max_fav_close"] + gap_dist)
            cand_trail = max(q_trail, close_trail, n_line if n_trend == 1 else 0.0) if t_dir == 1 else min(q_trail, close_trail, n_line if n_trend == -1 else 999999.0)
            eng["stop_price"] = max(eng["stop_price"], cand_trail) if t_dir == 1 else min(eng["stop_price"], cand_trail)

            if ((c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])) or ((n_trend == -1) if t_dir == 1 else (n_trend == 1)):
                exit_p = max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"])
                run_pts = max(s1_lock_pts_q + 85.0, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                
                tot_pnl_base = run_pts * base_qty
                run_pts_add = (exit_p - eng["tp1_price"]) if t_dir == 1 else (eng["tp1_price"] - exit_p)
                tot_pnl_add = run_pts_add * add_qty
                tot_pnl = tot_pnl_base + tot_pnl_add
                
                eng["gross_profit"] += tot_pnl; eng["total_brok"] += brok_tot
                net_inr = pts_to_inr(tot_pnl - brok_tot)
                eng["markers_js"].append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#38bdf8", "shape": "circle", "text": f"🚀 WAVE EXIT (₹{net_inr:+,.0f})"})
                eng["trade_logs"].insert(0, {"time": bar_ist, "type": f"{t_label} ({cur_qty}L Pyramid)", "entry": eng["entry_price"], "exit": exit_p, "status": "🚀 QUANTUM WAVE EXIT", "pnl": f"Avg +{run_pts:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#38bdf8"})
                eng["trade_logs"] = eng["trade_logs"][:50]; place_delta_demo_order(eng, close_side, cur_qty, tag="Wave Exit", is_exit=True); eng["trade_dir"] = 0

        if eng["trade_dir"] != 0 and not eng["tp2_reached"]:
            if not eng["tp1_reached"]:
                adverse_pts = (eng["entry_price"] - c) if t_dir == 1 else (c - eng["entry_price"])
                close_hit_sl = (c <= eng["entry_price"] - unit_size * SL_UNITS) if t_dir == 1 else (c >= eng["entry_price"] + unit_size * SL_UNITS)
                q_bad = ((eng["q_dir"] == -1 and c < eng["q_bot"]) if t_dir == 1 else (eng["q_dir"] == 1 and c > eng["q_top"])) and adverse_pts >= MAX_SL_PTS_PER_QTY * 0.65
                n_bad = ((n_trend == -1) if t_dir == 1 else (n_trend == 1)) and adverse_pts > 0
                hard_crash = (l <= eng["hard_stop_price"]) if t_dir == 1 else (h >= eng["hard_stop_price"])

                if close_hit_sl or q_bad or n_bad or hard_crash:
                    eng["losses"] += 1
                    loss_q = min(adverse_pts, eng["locked_sl_pts"]) if (ANTI_WICK_SL and not hard_crash and adverse_pts > 0) else eng["locked_sl_pts"]
                    tot_loss = loss_q * cur_qty
                    eng["gross_loss"] += tot_loss; eng["total_brok"] += brok_tot
                    net_loss_inr = pts_to_inr(-(tot_loss + brok_tot))
                    eng["markers_js"].append({"time": t_sec_ist, "position": "belowBar" if t_dir == 1 else "aboveBar", "color": "#f87171", "shape": "circle", "text": f"🛑 SL (₹{net_loss_inr:+,.0f})"})
                    eng["trade_logs"].insert(0, {"time": bar_ist, "type": f"{t_label} ({cur_qty}L)", "entry": eng["entry_price"], "exit": c, "status": "🛑 SHIELD SL", "pnl": f"-{loss_q:,.0f}p/L (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"})
                    eng["trade_logs"] = eng["trade_logs"][:50]; place_delta_demo_order(eng, close_side, cur_qty, tag="SL Exit", is_exit=True); eng["trade_dir"] = 0
            else:
                if ((c <= eng["stop_price"]) if t_dir == 1 else (c >= eng["stop_price"])) or ((n_trend == -1) if t_dir == 1 else (n_trend == 1)):
                    exit_p = max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"])
                    
                    tot_pnl_base = s1_lock_pts_q * base_qty
                    run_pts_add = (exit_p - eng["tp1_price"]) if t_dir == 1 else (eng["tp1_price"] - exit_p)
                    tot_pnl_add = run_pts_add * add_qty
                    tot_pnl = tot_pnl_base + tot_pnl_add

                    eng["gross_profit"] += tot_pnl; eng["total_brok"] += brok_tot
                    net_inr = pts_to_inr(tot_pnl - brok_tot)
                    eng["markers_js"].append({"time": t_sec_ist, "position": "aboveBar" if t_dir == 1 else "belowBar", "color": "#4ade80", "shape": "circle", "text": f"✅ S1 LOCK (₹{net_inr:+,.0f})"})
                    eng["trade_logs"].insert(0, {"time": bar_ist, "type": f"{t_label} ({cur_qty}L Pyramid)", "entry": eng["entry_price"], "exit": exit_p, "status": "✅ STAGE-1 PYRAMID LOCK", "pnl": f"+{s1_lock_pts_q:,.0f}p/L (Net ₹{net_inr:+,.0f})", "color": "#22c55e"})
                    eng["trade_logs"] = eng["trade_logs"][:50]; place_delta_demo_order(eng, close_side, cur_qty, tag="Lock Exit", is_exit=True); eng["trade_dir"] = 0

    # ========================================================================
    # ENTRY SIGNALS WITH MACRO TREND FILTER (DAILY VWAP)
    # ========================================================================
    ema21 = eng["ema21"]; vwap_live = eng["vwap"]; rsi14 = eng["rsi14"]
    q_dir = eng["q_dir"]; q_streak = eng["q_streak"]

    # 📌 Macro Trend Check: Price must be on the right side of the Daily VWAP
    bull_macro_ok = c > vwap_live
    bear_macro_ok = c < vwap_live

    bull_filter_ok = (h - l) <= unit_size * 1.90 and buy_dom_pct >= MIN_FLOW_DOM and 48.0 <= rsi14 < 76.0 and bull_macro_ok
    bear_filter_ok = (h - l) <= unit_size * 1.90 and sell_dom_pct >= MIN_FLOW_DOM and 24.0 < rsi14 <= 52.0 and bear_macro_ok

    trigger_flip_buy  = eng["pending_flip_buy"] and n_trend == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and n_trend == -1 and bear_filter_ok and c < o

    streak_ok = q_streak <= MAX_WAVE_STREAK; stretch_ok = abs(c - ema21) <= unit_size * MAX_DLINE_DIST
    trigger_cont_buy  = (not trigger_flip_buy) and n_trend == 1 and q_dir == 1 and step_up and bull_filter_ok and c > ema21 and streak_ok and stretch_ok
    trigger_cont_sell = (not trigger_flip_sell) and n_trend == -1 and q_dir == -1 and step_dn and bear_filter_ok and c < ema21 and streak_ok and stretch_ok

    if (eng["trade_dir"] == 0) and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
        is_long = trigger_flip_buy or trigger_cont_buy
        if is_long: eng["pending_flip_buy"] = False
        else: eng["pending_flip_sell"] = False

        eng["trade_dir"] = 1 if is_long else -1
        eng["active_qty"] = base_qty  # Reset to Base 25 Lots
        eng["entry_bar"] = idx; eng["entry_price"] = c; eng["max_fav_close"] = c
        eng["tp1_reached"] = False; eng["tp2_reached"] = False
        eng["entry_tag"] = "🔥 Q-Alpha (VWAP Sync)" if (trigger_flip_buy or trigger_flip_sell) else f"⚡ W#{q_streak} (VWAP Sync)"
        eng["entry_time_str"] = bar_ist

        eng["locked_tp1_pts"] = s1_trig_pts_q
        eng["locked_tp2_pts"] = unit_size * STAGE2_TRIG_UNITS
        eng["locked_sl_pts"]  = MAX_SL_PTS_PER_QTY

        eng["tp1_price"] = (c + eng["locked_tp1_pts"]) if is_long else (c - eng["locked_tp1_pts"])
        eng["tp2_price"] = (c + eng["locked_tp2_pts"]) if is_long else (c - eng["locked_tp2_pts"])
        eng["stop_price"] = (c - eng["locked_sl_pts"]) if is_long else (c + eng["locked_sl_pts"])
        eng["hard_stop_price"] = (c - unit_size * 1.65) if is_long else (c + unit_size * 1.65)

        eng["markers_js"].append({"time": t_sec_ist, "position": "belowBar" if is_long else "aboveBar", "color": "#00e676" if is_long else "#ff1744", "shape": "arrowUp" if is_long else "arrowDown", "text": f"{'BUY' if is_long else 'SELL'} {eng['entry_tag']}"})
        if eng.get("initialized", False):
            eng["live_order_active"] = True
            place_delta_demo_order(eng, "buy" if is_long else "sell", base_qty, tag=f"AI Base Entry", is_exit=False)
        else: eng["live_order_active"] = False

    eng["prev_close"] = c; eng["last_bar_time"] = bar_time_ms; eng["bar_count"] += 1

# ============================================================================
# ENGINE INITIALIZER & BACKGROUND WORKER
# ============================================================================
def init_locked_engine_once(eng):
    macro_range = calc_daily_atr5()
    eng["macro_range"] = macro_range; eng["unit_size"] = max(macro_range / float(FIXED_DIVISOR), MINTICK * 2.0)
    now_sec = int(time.time())
    days_back = 25
    eng["days_back"] = days_back
    anchor_start_ms = ((now_sec // 86400) * 86400 - (days_back * 86400)) * 1000
    klines = fetch_hl_klines_range(FIXED_TF, anchor_start_ms, now_sec * 1000)
    if klines and len(klines) > 30:
        for b in klines[:-1]: process_closed_bar(eng, b)
        eng["last_price"] = float(klines[-1][4])
        eng["initialized"] = True

def background_worker(eng, my_worker_id):
    init_delta_product_id(eng)
    last_poll = 0.0
    while True:
        if eng.get("active_worker_id") != my_worker_id: break
        try:
            if not eng.get("initialized", False): init_locked_engine_once(eng)
            if eng.get("initialized", False):
                now_ts = time.time()
                live_px = fetch_hl_live_mid_price()
                if live_px and live_px > 0:
                    eng["last_price"] = live_px
                
                if now_ts - last_poll >= 4.0:
                    klines = fetch_hl_klines_range(FIXED_TF, int(now_ts * 1000) - 8 * 900000, int(now_ts * 1000))
                    if klines and len(klines) >= 2:
                        for b in klines[:-1]: process_closed_bar(eng, b)
                        eng["last_price"] = float(klines[-1][4])
                    last_poll = now_ts
        except: pass
        time.sleep(2.0)

@st.cache_resource
def get_quantum_live_engine():
    worker_id = int(time.time() * 1000)
    eng = {
        "active_worker_id": worker_id, "initialized": False, "live_order_active": False, "delta_btc_product_id": 27, "delta_status": "🤖 Delta Live Algo: ACTIVE",
        "macro_range": 2800.0, "unit_size": 250.0, "days_back": 25, "active_qty": FIXED_BASE_QTY, "bar_count": 0, "last_bar_time": 0, "prev_close": 0.0, "tr_sum": 0.0, "atr14": 15.0,
        "ema21": 0.0, "vwap": 0.0, "cur_day": -1, "cum_pv": 0.0, "cum_v": 0.0, "up_sum": 0.0, "dn_sum": 0.0, "rma_up": 0.0, "rma_dn": 0.0, "rsi14": 50.0,
        "g1": 0.0, "g2": 0.0, "buy_v1": 0.0, "buy_v2": 0.0, "sell_v1": 0.0, "sell_v2": 0.0, "buy_dom_pct": 50.0, "sell_dom_pct": 50.0,
        "q_top": 0.0, "q_bot": 0.0, "q_dir": 1, "q_streak": 1, "q_core": 0.0, "support_band": None, "resistance_band": None, "n_trend": 1, "n_line": 0.0,
        "pending_flip_buy": False, "pending_flip_sell": False, "trade_dir": 0, "entry_bar": -1, "entry_price": 0.0, "tp1_price": 0.0, "tp2_price": 0.0,
        "stop_price": 0.0, "hard_stop_price": 0.0, "max_fav_close": 0.0, "locked_tp1_pts": 0.0, "locked_tp2_pts": 0.0, "locked_sl_pts": 0.0,
        "tp1_reached": False, "tp2_reached": False, "entry_tag": "", "entry_time_str": "", "wins": 0, "losses": 0, "tp2_hits": 0,
        "gross_profit": 0.0, "gross_loss": 0.0, "total_brok": 0.0, "candles_js": [], "qcore_js": [], "nline_js": [], "dline_js": [], "vwap_js": [], "markers_js": [], "trade_logs": [], "last_price": 0.0
    }
    init_locked_engine_once(eng)
    threading.Thread(target=background_worker, args=(eng, worker_id), daemon=True).start()
    return eng

eng = get_quantum_live_engine()
server_ip = get_server_public_ip()

# ============================================================================
# TOP CONTROL BAR (STEALTH VWAP DESIGN)
# ============================================================================
r1_c1, r1_c2, r1_c3, r1_c4 = st.columns([0.46, 0.18, 0.18, 0.18])
with r1_c1: st.markdown(f"**🌐 Server IP:** `{server_ip}` | <span style='color:#4ade80;font-weight:700;'>{eng.get('delta_status')}</span>", unsafe_allow_html=True)
with r1_c2:
    if st.button("🔌 Delta API कनेक्शन टेस्ट करें"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        eng["delta_status"] = f"✅ Delta Connected!" if ok else f"⚠️ Delta Error: {resp}"
        st.rerun()
with r1_c3:
    if st.button("🛑 Force Close Delta Trade"):
        if eng.get("trade_dir", 0) != 0:
            place_delta_demo_order(eng, "sell" if eng["trade_dir"] == 1 else "buy", eng["active_qty"], tag="Force Exit", is_exit=True)
            eng["trade_dir"] = 0; eng["live_order_active"] = False
        st.rerun()
with r1_c4:
    if st.button("🔄 चार्ट रिफ्रेश करें"): st.rerun()

st.markdown(f"""<div class="locked-bar">
  <div class="locked-pill"><span>🔒 Filtered Setup</span><b>{FIXED_TF.upper()} + Daily VWAP Anchor</b></div>
  <div class="locked-pill"><span>🔒 Pyramiding Strategy</span><b>Base 25L -> Adds 25L at S1</b></div>
  <div class="locked-pill"><span>🔒 Matrix Grid</span><b>Mode {FIXED_DIVISOR:.0f} (Balanced)</b></div>
  <div class="locked-pill"><span>🔒 Neural Shield</span><b>Core {FIXED_ST_MULT}</b></div>
</div>""", unsafe_allow_html=True)

if not eng.get("initialized", False):
    st.warning("⏳ Dr Devendra AI-Quantum Pro V21 (VWAP Filtered): लाइव चार्ट सिंक हो रहा है..."); st.stop()

tot_tr = eng["wins"] + eng["losses"]
wr_pct = (eng["wins"] / tot_tr * 100.0) if tot_tr > 0 else 0.0
net_pnl_pts = eng["gross_profit"] - eng["gross_loss"] - eng["total_brok"]
net_inr_val = pts_to_inr(net_pnl_pts)
matrix_col = "#00e676" if eng["n_trend"] == 1 else "#ff5252"

# ============================================================================
# INTERACTIVE CHART
# ============================================================================
chart_html = f"""<!DOCTYPE html>
<html>
<head>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0b0e14; color: #f8fafc; font-family: sans-serif; overflow: hidden; }}
  .chart-wrapper {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 14px; padding: 12px; }}
  .top-hud {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; margin-bottom: 8px; border-bottom: 1px solid #334155; flex-wrap: wrap; gap: 10px; }}
  .live-px {{ font-size: 28px; font-weight: 800; color: #ffffff; }}
  .badge {{ padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; border: 1px solid {matrix_col}; color: {matrix_col}; background: #1e293b; }}
  .legend-bar {{ display: flex; gap: 16px; font-size: 12px; color: #cbd5e1; margin-bottom: 8px; flex-wrap: wrap; align-items: center; }}
  .dot {{ width: 12px; height: 4px; border-radius: 2px; display: inline-block; }}
  .c-btn {{ background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 4px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 700; cursor: pointer; }}
  #tv-chart {{ width: 100%; height: 480px; border-radius: 8px; overflow: hidden; }}
</style>
</head>
<body>
<div class="chart-wrapper">
  <div class="top-hud">
    <div style="display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;">
      <span style="color:#38bdf8; font-weight:800; font-size:13px;">⚡ V21 VWAP PYRAMIDING (Max {FIXED_BASE_QTY + FIXED_PYRAMID_QTY}L)</span>
      <span class="live-px">${eng['last_price']:,.2f}</span>
      <span class="badge">{'BULLISH ▲' if eng['n_trend']==1 else 'BEARISH ▼'}</span>
      <span style="font-size:12px; color:#facc15; font-weight:700;">🧬 Q-Grid: {eng['unit_size']:,.1f}p | VWAP Anchor: {eng['vwap_js'][-1]['value']:,.1f}</span>
    </div>
    <div><button class="c-btn" onclick="chart.timeScale().scrollToRealTime()">⏩ Latest Candle</button> <button class="c-btn" onclick="chart.timeScale().fitContent()">🔍 Fit All Signals</button></div>
  </div>

  <div class="legend-bar">
    <div><span class="dot" style="background:#facc15;"></span> Q-Core</div>
    <div><span class="dot" style="background:#00e676;"></span><span class="dot" style="background:#ff5252;"></span> Neural Shield</div>
    <div><span class="dot" style="background:#38bdf8;"></span> D-Line</div>
    <div><span class="dot" style="background:#d946ef; width:20px; height:2px;"></span> Daily VWAP Anchor</div>
    <div style="margin-left:auto; color:#e2e8f0; font-weight:700;">
      🏆 Win Rate: <span style="color:#00e676;font-size:14px;">{wr_pct:.1f}%</span> ({eng['wins']}W/{eng['losses']}L) | 💰 Net Profit (After Fee): <span style="color:#4ade80;font-size:15px;">₹{net_inr_val:+,.0f}</span>
    </div>
  </div>
  <div id="tv-chart"></div>
</div>

<script>
const chart = LightweightCharts.createChart(document.getElementById('tv-chart'), {{
  layout: {{ background: {{ type: 'solid', color: '#090d16' }}, textColor: '#cbd5e1', fontSize: 12 }},
  grid: {{ vertLines: {{ color: '#1e293b' }}, horzLines: {{ color: '#1e293b' }} }},
  rightPriceScale: {{ borderColor: '#334155' }}, timeScale: {{ borderColor: '#334155', timeVisible: true, rightOffset: 8 }}
}});

const cSeries = chart.addCandlestickSeries({{ upColor: '#22c55e', downColor: '#ef4444', borderUpColor: '#22c55e', borderDownColor: '#ef4444', wickUpColor: '#22c55e', wickDownColor: '#ef4444' }});
cSeries.setData({json.dumps(eng['candles_js'])});
cSeries.setMarkers({json.dumps(eng['markers_js'])});

chart.addLineSeries({{ color: '#facc15', lineWidth: 2, lineType: LightweightCharts.LineType.WithSteps }}).setData({json.dumps(eng['qcore_js'])});
chart.addLineSeries({{ lineWidth: 3, lineType: LightweightCharts.LineType.WithSteps }}).setData({json.dumps(eng['nline_js'])});
chart.addLineSeries({{ color: '#38bdf8', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed }}).setData({json.dumps(eng['dline_js'])});
chart.addLineSeries({{ color: '#d946ef', lineWidth: 2, title: 'Daily VWAP' }}).setData({json.dumps(eng['vwap_js'])});

window.addEventListener('resize', () => chart.applyOptions({{ width: document.getElementById('tv-chart').clientWidth }}));
</script>
</body>
</html>"""
components.html(chart_html, height=580, scrolling=False)

# ============================================================================
# MASTER BACKTEST SUMMARY TABLE + SCALP TRADE LOGS
# ============================================================================
rows_html = "".join([f"""<tr style="border-bottom:1px solid #334155; font-size:12.5px;">
<td style="padding:7px; color:#94a3b8;">{lg['time']}</td><td style="padding:7px; color:#f8fafc; font-weight:bold;">{lg['type']}</td>
<td style="padding:7px; color:#cbd5e1;">{lg['entry']:,.1f} → {lg['exit']:,.1f}</td><td style="padding:7px; color:{lg['color']}; font-weight:bold;">{lg['status']}</td>
<td style="padding:7px; color:{lg['color']}; font-weight:bold; text-align:right;">{lg['pnl']}</td></tr>""" for lg in eng["trade_logs"]])

st.markdown(f"""<div class="t-grid">
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
  <div style="font-size:14px; font-weight:bold; color:#38bdf8; margin-bottom:10px;">📊 V21 VWAP PYRAMIDING BACKTEST (15M • UP TO 50 LOTS • {eng['days_back']} DAYS)</div>
  <table style="width:100%; border-collapse:collapse; font-size:13px;">
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Pyramiding Strategy</td><td style="padding:7px; color:#38bdf8; font-weight:bold; text-align:right;">Base {FIXED_BASE_QTY} Lots -> Adds {FIXED_PYRAMID_QTY} Lots at S1 Lock!</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Total Trades (W / L)</td><td style="padding:7px; color:#ffffff; font-weight:bold; text-align:right;">{tot_tr} Trades ({eng['wins']}W / {eng['losses']}L)</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Win Rate %</td><td style="padding:7px; color:#00e676; font-weight:800; font-size:15px; text-align:right;">🏆 {wr_pct:.1f}%</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Profit (Dynamic Lots)</td><td style="padding:7px; color:#4ade80; font-weight:bold; text-align:right;">+{eng['gross_profit']:,.0f} pts (₹{pts_to_inr(eng['gross_profit']):+,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Gross Loss (25 Lots Base)</td><td style="padding:7px; color:#f87171; font-weight:bold; text-align:right;">-{eng['gross_loss']:,.0f} pts (-₹{pts_to_inr(eng['gross_loss']):,.0f})</td></tr>
    <tr style="border-bottom:1px solid #334155;"><td style="padding:7px; color:#94a3b8;">Delta Brokerage</td><td style="padding:7px; color:#fca5a5; font-weight:bold; text-align:right;">-{eng['total_brok']:,.0f} pts (-₹{pts_to_inr(eng['total_brok']):,.0f})</td></tr>
    <tr style="background:#0f172a;"><td style="padding:9px 7px; color:#ffffff; font-weight:bold;">NET PROFIT (After Real Fee)</td><td style="padding:9px 7px; color:#00e676; font-weight:800; font-size:16px; text-align:right;">{net_pnl_pts:+,.0f} pts (₹{net_inr_val:+,.0f})</td></tr>
  </table>
</div>
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155;">
  <div style="font-size:14px; font-weight:bold; color:#f8fafc; margin-bottom:10px;">📜 V21 VWAP Pyramiding Scale-In ट्रेड इतिहास लॉग</div>
  <div style="max-height:260px; overflow-y:auto;">
    <table style="width:100%; border-collapse:collapse;">
      <thead><tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;"><th style="padding:6px;">समय (IST)</th><th style="padding:6px;">सिग्नल</th><th style="padding:6px;">Entry → Exit</th><th style="padding:6px;">स्टेटस</th><th style="padding:6px; text-align:right;">Net PnL (₹)</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
</div>""", unsafe_allow_html=True)

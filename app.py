import streamlit as st
import requests
import time
import threading
import json
from datetime import datetime, timedelta
import math
import streamlit.components.v1 as components

st.set_page_config(page_title="AI-Renko Pro & Multi-Chart Pro Terminal", layout="wide")

st.markdown("""<style>
.stApp { background-color: #0b0e14; color: #f8fafc; }
.block-container { padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
.t-grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
@media (min-width: 960px) { .t-grid { grid-template-columns: 1.15fr 0.85fr; } }
button[data-baseweb="tab"] { font-size: 15px !important; font-weight: 700 !important; color: #94a3b8 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# 10-QUANTITY & PINE SCRIPT PARAMETERS
# ============================================================================
TOTAL_QTY            = 10
TP1_BOOK_QTY         = 5
RUNNER_QTY           = 5

USE_TRAIL_BEYOND_TP2 = True
TRAIL_METHOD         = "Smart Brick + Peak Ratchet (Best)"
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
SIG_MODE             = "Supertrend + Brick-Step Re-Entry (Best)"
MIN_VOL_DOM          = 55.0

TP1_BRICKS           = 0.85
MID_LOCK_BRICKS      = 1.50
TP2_BRICKS           = 2.20
SL_BRICKS            = 1.40
ANTI_WICK_SL         = True
BROK_PER_QTY         = 1.5
MINTICK              = 0.1

YF_SYMBOLS           = ["^NSEI", "^NSEBANK", "^BSESN", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]
YF_INTERVALS         = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "6mo"}

def fmt_pts(pts):
    return f"{pts:,.1f}"

# ============================================================================
# YFINANCE FETCHER WITH SYNTHETIC TICK-VOLUME FALLBACK FOR INDIAN INDICES
# ============================================================================
def fetch_yf_chart(symbol, interval="5m"):
    rng = YF_INTERVALS.get(interval, "5d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={rng}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            res = r.json().get("chart", {}).get("result", [])
            if res:
                meta = res[0].get("meta", {})
                ts = res[0].get("timestamp", [])
                q = res[0].get("indicators", {}).get("quote", [{}])[0]
                opens = q.get("open", [])
                highs = q.get("high", [])
                lows = q.get("low", [])
                closes = q.get("close", [])
                vols = q.get("volume", [])
                candles = []
                for i in range(len(ts)):
                    if i < len(closes) and closes[i] is not None and opens[i] is not None:
                        o_val = round(float(opens[i]), 2)
                        h_val = round(float(highs[i]), 2)
                        l_val = round(float(lows[i]), 2)
                        c_val = round(float(closes[i]), 2)
                        raw_v = float(vols[i]) if (i < len(vols) and vols[i] is not None) else 0.0
                        # Synthetic tick-volume fallback when Yahoo Finance returns 0 volume on spot indices
                        syn_v = max(1.0, float(round((h_val - l_val) * 1000.0)))
                        final_v = raw_v if raw_v > 0 else syn_v
                        candles.append({
                            "time": int(ts[i]) + 19800,
                            "open": o_val,
                            "high": h_val,
                            "low": l_val,
                            "close": c_val,
                            "volume": final_v
                        })
                prev_close = meta.get("chartPreviousClose") or (candles[0]["open"] if candles else 0.0)
                return {"candles": candles[-300:], "prevClose": float(prev_close)}
    except Exception:
        pass
    return None

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
# STATEFUL INCREMENTAL BAR PROCESSOR (PERMANENT LOCK)
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
    bar_ist = (datetime.utcfromtimestamp(bar_time / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%I:%M %p")

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
        eng["brick_top"] = c
        eng["brick_bot"] = c - box_size
        eng["brick_dir"] = 1
        eng["brick_streak"] = 1
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

    # Manage Active 10-Qty Trade
    if eng["trade_dir"] != 0 and idx > eng["entry_bar"]:
        t_dir = eng["trade_dir"]
        t_label = "LONG" if t_dir == 1 else "SHORT"
        eng["max_fav_price"] = max(eng["max_fav_price"], h) if t_dir == 1 else min(eng["max_fav_price"], l)

        hit_tp1_now = (not eng["tp1_reached"]) and ((h >= eng["tp1_price"]) if t_dir == 1 else (l <= eng["tp1_price"]))
        if hit_tp1_now:
            eng["tp1_reached"] = True
            eng["wins"] += 1
            eng["booked_pnl_10q"] = eng["locked_tp1_pts"] * TP1_BOOK_QTY
            eng["gross_profit"] += eng["booked_pnl_10q"]
            eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)
            eng["open_qty"] = RUNNER_QTY
            eng["stop_price"] = eng["entry_price"]

        hit_mid_now = eng["tp1_reached"] and (not eng["mid_reached"]) and ((h >= eng["mid_lock_price"]) if t_dir == 1 else (l <= eng["mid_lock_price"]))
        if hit_mid_now:
            eng["mid_reached"] = True
            eng["stop_price"] = max(eng["stop_price"], eng["tp1_price"]) if t_dir == 1 else min(eng["stop_price"], eng["tp1_price"])

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
                runner_pnl_5q = safe_runner_pts * RUNNER_QTY

                eng["gross_profit"] += runner_pnl_5q
                total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_5q

                eng["last_result"] = f"🚀 Trail Exit (10Q): +{fmt_pts(total_trade_pnl)} pts [5Q TP1 + 5Q Trail]"
                eng["last_result_color"] = "#0369a1"
                eng["history"].insert(0, {
                    "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                    "exit": exit_p, "status": "🚀 5Q TP1 + 5Q TRAIL", "pnl": f"+{fmt_pts(total_trade_pnl)}", "color": "#38bdf8"
                })
                eng["history"] = eng["history"][:30]
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
                    loss_per_qty = min(abs(eng["entry_price"] - c), eng["locked_sl_pts"] * 1.15) if (ANTI_WICK_SL and not hard_crash) else eng["locked_sl_pts"]
                    total_loss_10q = loss_per_qty * TOTAL_QTY
                    eng["gross_loss"] += total_loss_10q
                    eng["total_brok"] += (BROK_PER_QTY * TOTAL_QTY)

                    eng["last_result"] = f"🛑 Full SL (10Q): -{fmt_pts(total_loss_10q)} pts (-{fmt_pts(loss_per_qty)}/Q)"
                    eng["last_result_color"] = "#991b1b"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": c, "status": "🛑 SL HIT (10Q)", "pnl": f"-{fmt_pts(total_loss_10q)}", "color": "#ef4444"
                    })
                    eng["history"] = eng["history"][:30]
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0
            else:
                hit_be_sl = (l <= eng["stop_price"]) if t_dir == 1 else (h >= eng["stop_price"])
                st_turned_bad = (eng["st_trend"] == -1) if t_dir == 1 else (eng["st_trend"] == 1)

                if (hit_be_sl or st_turned_bad) and not hit_tp1_now:
                    exit_p = eng["stop_price"] if hit_be_sl else (max(c, eng["stop_price"]) if t_dir == 1 else min(c, eng["stop_price"]))
                    runner_pts = max(0.0, (exit_p - eng["entry_price"]) if t_dir == 1 else (eng["entry_price"] - exit_p))
                    runner_pnl_5q = runner_pts * RUNNER_QTY
                    eng["gross_profit"] += runner_pnl_5q
                    total_trade_pnl = eng["booked_pnl_10q"] + runner_pnl_5q

                    status_tag = "✅ 5Q TP1 + 5Q MID-LOCK" if eng["mid_reached"] else "✅ 5Q TP1 + 5Q COST-EXIT"
                    eng["last_result"] = f"{status_tag}: +{fmt_pts(total_trade_pnl)} pts"
                    eng["last_result_color"] = "#166534"
                    eng["history"].insert(0, {
                        "time": bar_ist, "type": f"{t_label} (10Q)", "entry": eng["entry_price"],
                        "exit": exit_p, "status": status_tag, "pnl": f"+{fmt_pts(total_trade_pnl)}", "color": "#22c55e"
                    })
                    eng["history"] = eng["history"][:30]
                    eng["trade_dir"] = 0
                    eng["open_qty"] = 0

    # Check New Entry Signals
    ema21 = eng["ema21"]
    rsi_val = eng["rsi14"]

    candle_not_giant = (h - l) <= box_size * 1.85
    bull_filter_ok = candle_not_giant and buy_dom_pct >= 50.0 and rsi_val < 76.0
    bear_filter_ok = candle_not_giant and sell_dom_pct >= 50.0 and rsi_val > 24.0

    trigger_flip_buy = eng["pending_flip_buy"] and eng["st_trend"] == 1 and bull_filter_ok and c > o
    trigger_flip_sell = eng["pending_flip_sell"] and eng["st_trend"] == -1 and bear_filter_ok and c < o

    allow_re_entry = (SIG_MODE == "Supertrend + Brick-Step Re-Entry (Best)")
    raw_cont_buy = allow_re_entry and (not trigger_flip_buy) and eng["st_trend"] == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and rsi_val > 50.0 and rsi_val < 72.0 and candle_not_giant
    raw_cont_sell = allow_re_entry and (not trigger_flip_sell) and eng["st_trend"] == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and rsi_val < 50.0 and rsi_val > 28.0 and candle_not_giant

    streak_ok = (not USE_STREAK_FILTER) or (eng["brick_streak"] <= MAX_BRICK_STREAK)
    stretch_ok = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
    late_safe = streak_ok and stretch_ok

    trigger_cont_buy = raw_cont_buy and late_safe
    trigger_cont_sell = raw_cont_sell and late_safe

    can_open_trade = (eng["trade_dir"] == 0) or (eng["tp1_reached"] and (st_flip_buy or st_flip_sell))

    if can_open_trade and ((raw_cont_buy and not trigger_cont_buy) or (raw_cont_sell and not trigger_cont_sell)):
        eng["blocked_late"] += 1

    if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
        if eng["trade_dir"] != 0 and eng["tp1_reached"]:
            old_label = "LONG" if eng["trade_dir"] == 1 else "SHORT"
            runner_pts = max(0.0, (c - eng["entry_price"]) if eng["trade_dir"] == 1 else (eng["entry_price"] - c))
            runner_pnl_5q = runner_pts * RUNNER_QTY
            eng["gross_profit"] += runner_pnl_5q
            tot_flip_pnl = eng["booked_pnl_10q"] + runner_pnl_5q
            eng["history"].insert(0, {
                "time": bar_ist, "type": f"{old_label} (10Q)", "entry": eng["entry_price"],
                "exit": c, "status": "✅ 5Q TP1 + 5Q FLIP", "pnl": f"+{fmt_pts(tot_flip_pnl)}", "color": "#22c55e"
            })
            eng["history"] = eng["history"][:30]

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
        eng["hard_stop_price"] = (eng["stop_price"] - box_size * 0.5) if is_long else (eng["stop_price"] + box_size * 0.5)

    eng["prev_close"] = c
    eng["last_bar_time"] = bar_time
    eng["bar_count"] += 1

# ============================================================================
# 24x7 BACKGROUND WORKER (AI-RENKO + YFINANCE CACHE)
# ============================================================================
def background_worker(eng):
    primary_urls = [
        "https://data-api.binance.vision/api/v3",
        "https://api.binance.com/api/v3"
    ]
    last_1d_fetch = 0
    last_yf_fetch = 0

    while True:
        try:
            now_ts = time.time()

            if now_ts - last_yf_fetch > 60 or not eng["yf_cache"]:
                for sym in YF_SYMBOLS:
                    for tf in ["5m", "15m", "1m", "1h", "1d"]:
                        key = f"{sym}_{tf}"
                        if key not in eng["yf_cache"] or tf in ["1m", "5m", "15m"]:
                            res = fetch_yf_chart(sym, tf)
                            if res and res.get("candles"):
                                eng["yf_cache"][key] = res
                last_yf_fetch = now_ts

            if now_ts - last_1d_fetch > 300 or eng["macro_range"] is None:
                for base in primary_urls:
                    try:
                        r_d = requests.get(f"{base}/klines?symbol=BTCUSDT&interval=1d&limit=15", timeout=5)
                        if r_d.status_code == 200 and isinstance(r_d.json(), list):
                            d_val = calc_daily_atr5(r_d.json())
                            if d_val:
                                eng["macro_range"] = d_val
                                last_1d_fetch = now_ts
                            break
                    except Exception:
                        continue

            if not eng["initialized"]:
                for base in primary_urls:
                    try:
                        r_init = requests.get(f"{base}/klines?symbol=BTCUSDT&interval=1m&limit=1000", timeout=8)
                        if r_init.status_code == 200:
                            data = r_init.json()
                            if isinstance(data, list) and len(data) > 100:
                                for b in data[:-1]:
                                    process_single_closed_bar(eng, b)
                                eng["price"] = float(data[-1][4])
                                eng["initialized"] = True
                                break
                    except Exception:
                        continue
            else:
                for base in primary_urls:
                    try:
                        r_live = requests.get(f"{base}/klines?symbol=BTCUSDT&interval=1m&limit=5", timeout=5)
                        if r_live.status_code == 200:
                            data = r_live.json()
                            if isinstance(data, list) and len(data) >= 2:
                                for b in data[:-1]:
                                    process_single_closed_bar(eng, b)
                                eng["price"] = float(data[-1][4])
                                break
                    except Exception:
                        continue

            eng["ist_time"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
            eng["error"] = None

        except Exception as e:
            eng["error"] = str(e)

        time.sleep(2)

@st.cache_resource
def get_server_engine():
    eng = {
        "initialized": False,
        "bar_count": 0,
        "last_bar_time": 0,
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
        "box_size": 150.0,
        "brick_top": 0.0,
        "brick_bot": 0.0,
        "brick_dir": 1,
        "brick_streak": 1,
        "support_band": None,
        "resistance_band": None,
        "st_trend": 1,
        "st_line": 0.0,
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
        "yf_cache": {},
        "error": None
    }
    thread = threading.Thread(target=background_worker, args=(eng,), daemon=True)
    thread.start()
    return eng

eng = get_server_engine()

# ============================================================================
# TWO TABS: TAB 1 = AI-RENKO PRO | TAB 2 = MULTI-CHART PRO (10 INDICATORS)
# ============================================================================
tab_renko, tab_charts = st.tabs([
    "⚡ AI-Renko Pro Terminal (10-Qty Locked)",
    "📊 Multi-Chart Pro (10 Institutional Indicators)"
])

with tab_renko:
    terminal = st.empty()

with tab_charts:
    yf_json_str = json.dumps(eng.get("yf_cache", {}))
    multi_chart_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0b0e14; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; user-select: none; }
  .top-bar {
    height: 40px; background: #131722; border-bottom: 1px solid #2a2e39;
    display: flex; align-items: center; justify-content: space-between; padding: 0 14px;
  }
  .top-title { font-size: 14px; font-weight: 700; color: #e2e8f0; display: flex; align-items: center; gap: 10px; }
  .top-badge { font-size: 11px; background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 2px 8px; border-radius: 4px; }
  .top-controls { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #94a3b8; }
  select {
    background: #1e222d; color: #e2e8f0; border: 1px solid #363a45; border-radius: 4px;
    padding: 3px 6px; font-size: 12px; font-weight: 600; outline: none; cursor: pointer;
  }
  select:hover { border-color: #38bdf8; }
  #chart-grid {
    display: grid; width: 100vw; height: calc(100vh - 40px); gap: 4px; background: #06080c; padding: 4px;
  }
  .pane {
    background: #0f131c; border: 1px solid #1e222d; border-radius: 4px;
    display: flex; flex-direction: column; overflow: hidden; position: relative;
  }
  .pane-ctrl {
    height: 32px; background: #161b26; border-bottom: 1px solid #232834;
    display: flex; align-items: center; justify-content: space-between; padding: 0 6px; gap: 5px; z-index: 20;
  }
  .ctrl-left { display: flex; align-items: center; gap: 5px; flex: 1; min-width: 0; }
  .pane-ctrl select.sym-sel { width: 135px; max-width: 45%; }
  .pane-ctrl select.tf-sel { width: 58px; }
  .ind-dropdown { position: relative; display: inline-block; }
  .ind-btn {
    background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 4px;
    padding: 3px 8px; font-size: 11px; font-weight: 700; cursor: pointer; white-space: nowrap;
  }
  .ind-btn:hover { background: #334155; color: #ffffff; }
  .ind-menu {
    display: none; position: absolute; right: 0; top: 26px; width: 235px;
    background: #131722; border: 1px solid #363a45; border-radius: 6px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.75); padding: 6px 0; z-index: 100;
    max-height: 310px; overflow-y: auto;
  }
  .ind-menu.open { display: block; }
  .ind-item {
    display: flex; align-items: center; gap: 8px; padding: 5px 10px;
    font-size: 11.5px; color: #e2e8f0; cursor: pointer;
  }
  .ind-item:hover { background: #1e293b; }
  .ind-item input { accent-color: #38bdf8; cursor: pointer; }
  .ind-cat {
    font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase;
    padding: 4px 10px 2px; letter-spacing: 0.5px;
  }
  .ticker-bar {
    height: 26px; background: #11151f; border-bottom: 1px solid #1e222d;
    display: flex; align-items: center; justify-content: space-between; padding: 0 10px;
    font-size: 12px; transition: background-color 0.25s ease; z-index: 10;
  }
  .flash-up { background-color: rgba(16, 185, 129, 0.28) !important; }
  .flash-dn { background-color: rgba(239, 68, 68, 0.28) !important; }
  .tk-left { display: flex; align-items: center; gap: 6px; color: #94a3b8; font-weight: 600; overflow: hidden; white-space: nowrap; }
  .ind-tags { display: flex; gap: 3px; margin-left: 6px; }
  .ind-tag { font-size: 9.5px; background: #1e293b; color: #cbd5e1; padding: 1px 4px; border-radius: 3px; border: 1px solid #334155; }
  .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .dot-crypto { background: #10b981; box-shadow: 0 0 6px #10b981; }
  .dot-stock { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
  .tk-right { display: flex; align-items: baseline; gap: 8px; font-family: monospace; flex-shrink: 0; }
  .tk-price { font-size: 14px; font-weight: 800; }
  .tk-chg { font-size: 11px; font-weight: 600; }
  .up-col { color: #26a69a; }
  .dn-col { color: #ef5350; }
  .chart-box { flex: 1; width: 100%; position: relative; overflow: hidden; }
  .overlay-canvas { pointer-events: none; position: absolute; inset: 0; z-index: 5; }
</style>
</head>
<body>
<div class="top-bar">
  <div class="top-title">
    <span>Multi-chart dashboard</span>
    <span class="top-badge">⚡ 10 Institutional Indicators Active</span>
  </div>
  <div class="top-controls">
    <span>Number of charts</span>
    <select id="count-select">
      <option value="1">1</option>
      <option value="2">2</option>
      <option value="4" selected>4</option>
      <option value="6">6</option>
      <option value="8">8</option>
    </select>
  </div>
</div>
<div id="chart-grid"></div>

<script>
const SERVER_YF_CACHE = __INITIAL_YF_JSON__;

const SYMBOLS = [
  { id: "BTC", label: "BTC (Crypto)", type: "crypto", binance: "BTCUSDT" },
  { id: "ETH", label: "ETH (Crypto)", type: "crypto", binance: "ETHUSDT" },
  { id: "SOL", label: "SOL (Crypto)", type: "crypto", binance: "SOLUSDT" },
  { id: "BNB", label: "BNB (Crypto)", type: "crypto", binance: "BNBUSDT" },
  { id: "XRP", label: "XRP (Crypto)", type: "crypto", binance: "XRPUSDT" },
  { id: "^NSEI", label: "^NSEI (Nifty 50)", type: "yf" },
  { id: "^NSEBANK", label: "^NSEBANK (BankNifty)", type: "yf" },
  { id: "^BSESN", label: "^BSESN (Sensex)", type: "yf" },
  { id: "RELIANCE.NS", label: "RELIANCE.NS", type: "yf" },
  { id: "HDFCBANK.NS", label: "HDFCBANK.NS", type: "yf" },
  { id: "TCS.NS", label: "TCS.NS", type: "yf" }
];

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "1d"];

const INDICATOR_LIST = [
  { id: "vpvr", label: "1. Volume Profile (VPVR)", short: "VPVR", cat: "Canvas Smart Money" },
  { id: "fvg",  label: "2. Fair Value Gap (FVG)",  short: "FVG",  cat: "Canvas Smart Money" },
  { id: "ob",   label: "3. Order Blocks (OB)",     short: "OB",   cat: "Canvas Smart Money" },
  { id: "st",   label: "4. Supertrend (10, 3)",    short: "ST",   cat: "Trend & Overlays" },
  { id: "vwap", label: "5. Intraday VWAP",         short: "VWAP", cat: "Trend & Overlays" },
  { id: "ema",  label: "6. EMA Ribbon (9/21/50/200)", short: "EMA", cat: "Trend & Overlays" },
  { id: "bb",   label: "7. Bollinger Bands (20, 2)", short: "BB", cat: "Trend & Overlays" },
  { id: "cpr",  label: "8. Central Pivot Range (CPR)", short: "CPR", cat: "Trend & Overlays" },
  { id: "ms",   label: "9. Market Structure (BOS/CHOCH)", short: "SMC", cat: "Oscillators & Structure" },
  { id: "rsi",  label: "10. RSI (14) Sub-Pane",    short: "RSI",  cat: "Oscillators & Structure" }
];

const DEFAULT_PANES = [
  { sym: "BTC", tf: "5m",  inds: ["vpvr", "st", "vwap", "fvg"] },
  { sym: "BTC", tf: "15m", inds: ["ob", "ema", "ms"] },
  { sym: "^NSEI", tf: "5m", inds: ["vpvr", "st", "cpr"] },
  { sym: "^NSEI", tf: "15m", inds: ["fvg", "vwap", "rsi"] },
  { sym: "ETH", tf: "5m",  inds: ["st", "vwap"] },
  { sym: "^NSEBANK", tf: "5m", inds: ["vpvr", "st", "cpr"] },
  { sym: "SOL", tf: "15m", inds: ["ema", "bb"] },
  { sym: "RELIANCE.NS", tf: "5m", inds: ["st", "vwap"] }
];

let activePanes = [];
let hlSocket = null;

// Close open indicator menus when clicking outside
document.addEventListener("click", (e) => {
  if (!e.target.closest(".ind-dropdown")) {
    document.querySelectorAll(".ind-menu.open").forEach(m => m.classList.remove("open"));
  }
});

function getGridDims(count) {
  if (count === 1) return { cols: 1, rows: 1 };
  if (count === 2) return { cols: 2, rows: 1 };
  if (count === 4) return { cols: 2, rows: 2 };
  if (count === 6) return { cols: 3, rows: 2 };
  return { cols: 4, rows: 2 };
}

function saveConfig(count) {
  try {
    localStorage.setItem("mc_chart_count_v2", String(count));
    const cfg = activePanes.map(p => ({ sym: p.sym, tf: p.tf, inds: Array.from(p.inds) }));
    localStorage.setItem("mc_pane_cfg_v2", JSON.stringify(cfg));
  } catch (e) {}
}

function loadSavedConfigs() {
  try {
    const saved = JSON.parse(localStorage.getItem("mc_pane_cfg_v2") || "null");
    if (Array.isArray(saved) && saved.length > 0) {
      for (let i = 0; i < 8; i++) {
        if (saved[i] && saved[i].sym && saved[i].tf) {
          DEFAULT_PANES[i] = {
            sym: saved[i].sym,
            tf: saved[i].tf,
            inds: Array.isArray(saved[i].inds) ? saved[i].inds : DEFAULT_PANES[i].inds
          };
        }
      }
    }
  } catch (e) {}
}

function ensureVolumeFallback(candles) {
  return candles.map(c => {
    const rawV = Number(c.volume) || 0;
    const synV = Math.max(1, Math.round((c.high - c.low) * 1000));
    return { ...c, volume: rawV > 0 ? rawV : synV };
  });
}

async function fetchCryptoHistory(symObj, tf) {
  try {
    const tfMsMap = { "1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "1d": 86400000 };
    const endTime = Date.now();
    const startTime = endTime - (tfMsMap[tf] || 300000) * 260;
    const r = await fetch("https://api.hyperliquid.xyz/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "candleSnapshot",
        req: { coin: symObj.id, interval: tf, startTime: startTime, endTime: endTime }
      })
    });
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data) && data.length > 0) {
        const candles = ensureVolumeFallback(data.map(k => ({
          time: Math.floor(k.t / 1000) + 19800,
          open: parseFloat(k.o),
          high: parseFloat(k.h),
          low: parseFloat(k.l),
          close: parseFloat(k.c),
          volume: parseFloat(k.v)
        })));
        return { candles, prevClose: candles[0].open };
      }
    }
  } catch (e) {}

  try {
    const r = await fetch(`https://data-api.binance.vision/api/v3/klines?symbol=${symObj.binance}&interval=${tf}&limit=260`);
    if (r.ok) {
      const data = await r.json();
      const candles = ensureVolumeFallback(data.map(k => ({
        time: Math.floor(k[0] / 1000) + 19800,
        open: parseFloat(k[1]),
        high: parseFloat(k[2]),
        low: parseFloat(k[3]),
        close: parseFloat(k[4]),
        volume: parseFloat(k[5])
      })));
      return { candles, prevClose: candles[0].open };
    }
  } catch (e) {}
  return null;
}

async function fetchYfHistory(sym, tf) {
  const key = `${sym}_${tf}`;
  const rngMap = { "1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "6mo" };
  const rng = rngMap[tf] || "5d";
  const targetUrl = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=${tf}&range=${rng}`;
  const proxies = [
    `https://corsproxy.io/?${encodeURIComponent(targetUrl)}`,
    `https://api.allorigins.win/raw?url=${encodeURIComponent(targetUrl)}`
  ];

  for (const pUrl of proxies) {
    try {
      const r = await fetch(pUrl);
      if (r.ok) {
        const j = await r.json();
        const res = j?.chart?.result?.[0];
        if (res && res.timestamp) {
          const ts = res.timestamp;
          const q = res.indicators.quote[0];
          const rawCandles = [];
          for (let i = 0; i < ts.length; i++) {
            if (q.close[i] != null && q.open[i] != null) {
              rawCandles.push({
                time: ts[i] + 19800,
                open: parseFloat(q.open[i].toFixed(2)),
                high: parseFloat(q.high[i].toFixed(2)),
                low: parseFloat(q.low[i].toFixed(2)),
                close: parseFloat(q.close[i].toFixed(2)),
                volume: q.volume?.[i] || 0
              });
            }
          }
          if (rawCandles.length > 0) {
            const candles = ensureVolumeFallback(rawCandles);
            const prevClose = res.meta?.chartPreviousClose || candles[0].open;
            SERVER_YF_CACHE[key] = { candles, prevClose };
            return SERVER_YF_CACHE[key];
          }
        }
      }
    } catch (e) {}
  }

  if (SERVER_YF_CACHE[key]) {
    SERVER_YF_CACHE[key].candles = ensureVolumeFallback(SERVER_YF_CACHE[key].candles);
    return SERVER_YF_CACHE[key];
  }
  return null;
}

// ============================================================================
# MATHEMATICAL CALCULATIONS FOR ALL 10 PREMIUM INDICATORS
// ============================================================================
function calcEMA(candles, period) {
  const res = [];
  if (!candles.length) return res;
  const k = 2.0 / (period + 1.0);
  let ema = candles[0].close;
  for (let i = 0; i < candles.length; i++) {
    ema = i === 0 ? candles[0].close : candles[i].close * k + ema * (1.0 - k);
    res.push({ time: candles[i].time, value: ema });
  }
  return res;
}

function calcBollinger(candles, period = 20, mult = 2.0) {
  const basis = [], upper = [], lower = [];
  for (let i = 0; i < candles.length; i++) {
    if (i < period - 1) continue;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    const mean = sum / period;
    let sqSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const d = candles[j].close - mean;
      sqSum += d * d;
    }
    const stdev = Math.sqrt(sqSum / period);
    basis.push({ time: candles[i].time, value: mean });
    upper.push({ time: candles[i].time, value: mean + mult * stdev });
    lower.push({ time: candles[i].time, value: mean - mult * stdev });
  }
  return { basis, upper, lower };
}

function calcVWAP(candles) {
  const res = [];
  let cumPV = 0, cumV = 0, lastDay = null;
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const day = Math.floor(c.time / 86400);
    if (day !== lastDay) {
      cumPV = 0;
      cumV = 0;
      lastDay = day;
    }
    const typ = (c.high + c.low + c.close) / 3.0;
    const v = Math.max(1, c.volume);
    cumPV += typ * v;
    cumV += v;
    res.push({ time: c.time, value: cumPV / cumV });
  }
  return res;
}

function calcSupertrend(candles, period = 10, factor = 3.0) {
  const line = [];
  const markers = [];
  if (candles.length < 2) return { line, markers };

  const tr = new Array(candles.length).fill(0);
  const atr = new Array(candles.length).fill(0);
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) tr[i] = candles[i].high - candles[i].low;
    else {
      tr[i] = Math.max(
        candles[i].high - candles[i].low,
        Math.abs(candles[i].high - candles[i - 1].close),
        Math.abs(candles[i].low - candles[i - 1].close)
      );
    }
    if (i < period) {
      let s = 0;
      for (let j = 0; j <= i; j++) s += tr[j];
      atr[i] = s / (i + 1);
    } else {
      atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
    }
  }

  let upperBand = 0, lowerBand = 0, trend = 1;
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const hl2 = (c.high + c.low) / 2.0;
    const basicUpper = hl2 + factor * atr[i];
    const basicLower = hl2 - factor * atr[i];

    if (i === 0) {
      upperBand = basicUpper;
      lowerBand = basicLower;
      trend = 1;
    } else {
      upperBand = (basicUpper < upperBand || candles[i - 1].close > upperBand) ? basicUpper : upperBand;
      lowerBand = (basicLower > lowerBand || candles[i - 1].close < lowerBand) ? basicLower : lowerBand;
      const prevTrend = trend;
      if (prevTrend === -1 && c.close > upperBand) trend = 1;
      else if (prevTrend === 1 && c.close < lowerBand) trend = -1;

      if (trend === 1 && prevTrend === -1) {
        markers.push({ time: c.time, position: "belowBar", color: "#00e676", shape: "arrowUp", text: "BUY" });
      } else if (trend === -1 && prevTrend === 1) {
        markers.push({ time: c.time, position: "aboveBar", color: "#ff1744", shape: "arrowDown", text: "SELL" });
      }
    }
    line.push({
      time: c.time,
      value: trend === 1 ? lowerBand : upperBand,
      color: trend === 1 ? "#00e676" : "#ff1744"
    });
  }
  return { line, markers };
}

function calcCPR(candles) {
  const pArr = [], tcArr = [], bcArr = [];
  if (!candles.length) return { pArr, tcArr, bcArr };

  // Group by day (or 60-bar session blocks if single day)
  const dayStats = {};
  const dayOrder = [];
  candles.forEach(c => {
    const d = Math.floor(c.time / 86400);
    if (!dayStats[d]) {
      dayStats[d] = { h: c.high, l: c.low, c: c.close };
      dayOrder.push(d);
    } else {
      dayStats[d].h = Math.max(dayStats[d].h, c.high);
      dayStats[d].l = Math.min(dayStats[d].l, c.low);
      dayStats[d].c = c.close;
    }
  });

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const d = Math.floor(c.time / 86400);
    const dIdx = dayOrder.indexOf(d);
    const ref = dIdx > 0 ? dayStats[dayOrder[dIdx - 1]] : dayStats[d];
    const P = (ref.h + ref.l + ref.c) / 3.0;
    const BC = (ref.h + ref.l) / 2.0;
    const TC = (P - BC) + P;
    pArr.push({ time: c.time, value: P });
    tcArr.push({ time: c.time, value: Math.max(TC, BC) });
    bcArr.push({ time: c.time, value: Math.min(TC, BC) });
  }
  return { pArr, tcArr, bcArr };
}

function calcMarketStructure(candles) {
  const markers = [];
  if (candles.length < 10) return markers;
  let lastSwingHigh = null, lastSwingLow = null, structTrend = 0;

  for (let i = 2; i < candles.length - 2; i++) {
    const c = candles[i];
    if (c.high > candles[i - 1].high && c.high > candles[i - 2].high && c.high > candles[i + 1].high && c.high > candles[i + 2].high) {
      lastSwingHigh = { price: c.high, broken: false };
    }
    if (c.low < candles[i - 1].low && c.low < candles[i - 2].low && c.low < candles[i + 1].low && c.low < candles[i + 2].low) {
      lastSwingLow = { price: c.low, broken: false };
    }

    if (lastSwingHigh && !lastSwingHigh.broken && c.close > lastSwingHigh.price) {
      lastSwingHigh.broken = true;
      const lbl = structTrend === -1 ? "CHOCH" : "BOS";
      structTrend = 1;
      markers.push({ time: c.time, position: "aboveBar", color: "#38bdf8", shape: "circle", text: lbl });
    } else if (lastSwingLow && !lastSwingLow.broken && c.close < lastSwingLow.price) {
      lastSwingLow.broken = true;
      const lbl = structTrend === 1 ? "CHOCH" : "BOS";
      structTrend = -1;
      markers.push({ time: c.time, position: "belowBar", color: "#f59e0b", shape: "circle", text: lbl });
    }
  }
  return markers;
}

function calcRSI(candles, period = 14) {
  const res = [];
  if (candles.length < 2) return res;
  let rmaUp = 0, rmaDn = 0, upSum = 0, dnSum = 0;
  for (let i = 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    const up = Math.max(diff, 0);
    const dn = Math.max(-diff, 0);
    if (i <= period) {
      upSum += up;
      dnSum += dn;
      rmaUp = upSum / i;
      rmaDn = dnSum / i;
    } else {
      rmaUp = (rmaUp * (period - 1) + up) / period;
      rmaDn = (rmaDn * (period - 1) + dn) / period;
    }
    let val = 50;
    if (rmaDn === 0) val = 100;
    else if (rmaUp === 0) val = 0;
    else val = 100.0 - (100.0 / (1.0 + rmaUp / rmaDn));
    res.push({ time: candles[i].time, value: val });
  }
  return res;
}

function detectFVGAndOB(candles) {
  const fvgs = [];
  const obs = [];
  if (candles.length < 5) return { fvgs, obs };

  const lastTime = candles[candles.length - 1].time;

  for (let i = 2; i < candles.length; i++) {
    const c0 = candles[i - 2];
    const c1 = candles[i - 1];
    const c2 = candles[i];
    const body1 = Math.abs(c1.close - c1.open);
    const rng1 = Math.max(c1.high - c1.low, 0.0001);

    // Bullish FVG: c2.low > c0.high with strong middle body
    if (c2.low > c0.high && (body1 / rng1) > 0.45) {
      const top = c2.low;
      const bot = c0.high;
      let endTime = lastTime;
      let mitigated = false;
      for (let k = i + 1; k < candles.length; k++) {
        if (candles[k].low <= bot) {
          endTime = candles[k].time;
          mitigated = true;
          break;
        }
      }
      if (!mitigated || (candles.length - i) < 60) {
        fvgs.push({ type: "bull", startTime: c1.time, endTime, top, bot, mitigated });
      }

      // Check Bullish Order Block (last bearish candle prior to impulsive move)
      for (let b = i - 2; b >= Math.max(0, i - 5); b--) {
        if (candles[b].close < candles[b].open) {
          const obTop = candles[b].high;
          const obBot = candles[b].low;
          let obEnd = lastTime;
          let obMit = false;
          for (let k = i + 1; k < candles.length; k++) {
            if (candles[k].low < obBot) {
              obEnd = candles[k].time;
              obMit = true;
              break;
            }
          }
          if (!obMit) obs.push({ type: "bull", startTime: candles[b].time, endTime: obEnd, top: obTop, bot: obBot });
          break;
        }
      }
    }

    // Bearish FVG: c2.high < c0.low with strong middle body
    if (c2.high < c0.low && (body1 / rng1) > 0.45) {
      const top = c0.low;
      const bot = c2.high;
      let endTime = lastTime;
      let mitigated = false;
      for (let k = i + 1; k < candles.length; k++) {
        if (candles[k].high >= top) {
          endTime = candles[k].time;
          mitigated = true;
          break;
        }
      }
      if (!mitigated || (candles.length - i) < 60) {
        fvgs.push({ type: "bear", startTime: c1.time, endTime, top, bot, mitigated });
      }

      // Check Bearish Order Block (last bullish candle prior to impulsive drop)
      for (let b = i - 2; b >= Math.max(0, i - 5); b--) {
        if (candles[b].close > candles[b].open) {
          const obTop = candles[b].high;
          const obBot = candles[b].low;
          let obEnd = lastTime;
          let obMit = false;
          for (let k = i + 1; k < candles.length; k++) {
            if (candles[k].high > obTop) {
              obEnd = candles[k].time;
              obMit = true;
              break;
            }
          }
          if (!obMit) obs.push({ type: "bear", startTime: candles[b].time, endTime: obEnd, top: obTop, bot: obBot });
          break;
        }
      }
    }
  }

  return {
    fvgs: fvgs.slice(-14),
    obs: obs.slice(-10)
  };
}

// ============================================================================
# CUSTOM HTML5 CANVAS OVERLAY RENDERER (VPVR, FVG, ORDER BLOCKS)
// ============================================================================
function drawCanvasOverlays(pane) {
  const canvas = pane.canvas;
  if (!canvas || !pane.chartBox) return;
  const rect = pane.chartBox.getBoundingClientRect();
  if (canvas.width !== rect.width || canvas.height !== rect.height) {
    canvas.width = rect.width;
    canvas.height = rect.height;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!pane.candles || pane.candles.length < 5) return;

  const ts = pane.chart.timeScale();
  const plotWidth = ts.width() > 0 ? ts.width() : (canvas.width - 65);
  const lastCandleTime = pane.candles[pane.candles.length - 1].time;

  // 1. Draw Order Blocks (OB)
  if (pane.inds.has("ob") && pane.smcZones && pane.smcZones.obs) {
    pane.smcZones.obs.forEach(ob => {
      let x1 = ts.timeToCoordinate(ob.startTime);
      let x2 = ts.timeToCoordinate(ob.endTime);
      const y1 = pane.candleSeries.priceToCoordinate(ob.top);
      const y2 = pane.candleSeries.priceToCoordinate(ob.bot);
      if (y1 === null || y2 === null) return;
      if (x1 === null) x1 = 0;
      if (x2 === null || ob.endTime === lastCandleTime) x2 = plotWidth;
      const left = Math.max(0, Math.min(x1, x2));
      const right = Math.min(plotWidth, Math.max(x1, x2, left + 24));
      if (right <= 0 || left >= plotWidth) return;

      const topY = Math.min(y1, y2);
      const hY = Math.max(2, Math.abs(y2 - y1));

      ctx.fillStyle = ob.type === "bull" ? "rgba(59, 130, 246, 0.18)" : "rgba(168, 85, 247, 0.18)";
      ctx.strokeStyle = ob.type === "bull" ? "rgba(59, 130, 246, 0.65)" : "rgba(168, 85, 247, 0.65)";
      ctx.lineWidth = 1;
      ctx.fillRect(left, topY, right - left, hY);
      ctx.strokeRect(left, topY, right - left, hY);

      ctx.fillStyle = ob.type === "bull" ? "#60a5fa" : "#c084fc";
      ctx.font = "bold 9.5px sans-serif";
      ctx.fillText(ob.type === "bull" ? "Bull OB" : "Bear OB", left + 4, topY + 10);
    });
  }

  // 2. Draw Fair Value Gaps (FVG)
  if (pane.inds.has("fvg") && pane.smcZones && pane.smcZones.fvgs) {
    pane.smcZones.fvgs.forEach(fvg => {
      let x1 = ts.timeToCoordinate(fvg.startTime);
      let x2 = ts.timeToCoordinate(fvg.endTime);
      const y1 = pane.candleSeries.priceToCoordinate(fvg.top);
      const y2 = pane.candleSeries.priceToCoordinate(fvg.bot);
      if (y1 === null || y2 === null) return;
      if (x1 === null) x1 = 0;
      if (x2 === null || fvg.endTime === lastCandleTime) x2 = plotWidth;
      const left = Math.max(0, Math.min(x1, x2));
      const right = Math.min(plotWidth, Math.max(x1, x2, left + 20));
      if (right <= 0 || left >= plotWidth) return;

      const topY = Math.min(y1, y2);
      const hY = Math.max(2, Math.abs(y2 - y1));

      ctx.fillStyle = fvg.type === "bull" ? "rgba(0, 230, 118, 0.18)" : "rgba(255, 23, 68, 0.18)";
      ctx.strokeStyle = fvg.type === "bull" ? "rgba(0, 230, 118, 0.55)" : "rgba(255, 23, 68, 0.55)";
      ctx.lineWidth = 1;
      ctx.fillRect(left, topY, right - left, hY);
      ctx.strokeRect(left, topY, right - left, hY);

      ctx.fillStyle = fvg.type === "bull" ? "#00e676" : "#ff5252";
      ctx.font = "bold 9px sans-serif";
      ctx.fillText("FVG", left + 4, topY + 9);
    });
  }

  // 3. Draw Volume Profile (Visible Range - VPVR)
  if (pane.inds.has("vpvr")) {
    const logRange = ts.getVisibleLogicalRange();
    let startIdx = 0;
    let endIdx = pane.candles.length - 1;
    if (logRange) {
      startIdx = Math.max(0, Math.floor(logRange.from));
      endIdx = Math.min(pane.candles.length - 1, Math.ceil(logRange.to));
    }
    const vis = pane.candles.slice(startIdx, endIdx + 1);
    if (vis.length >= 3) {
      let minP = Infinity, maxP = -Infinity;
      vis.forEach(c => {
        if (c.low < minP) minP = c.low;
        if (c.high > maxP) maxP = c.high;
      });
      if (maxP > minP) {
        const numBins = 24;
        const step = (maxP - minP) / numBins;
        const upBins = new Array(numBins).fill(0);
        const dnBins = new Array(numBins).fill(0);
        let totalVol = 0;

        vis.forEach(c => {
          const mid = (c.high + c.low + c.close) / 3.0;
          let bIdx = Math.floor((mid - minP) / step);
          if (bIdx < 0) bIdx = 0;
          if (bIdx >= numBins) bIdx = numBins - 1;
          const v = Math.max(1, c.volume);
          if (c.close >= c.open) upBins[bIdx] += v;
          else dnBins[bIdx] += v;
          totalVol += v;
        });

        let maxBinVol = 0, pocIdx = 0;
        const totBins = new Array(numBins).fill(0);
        for (let b = 0; b < numBins; b++) {
          totBins[b] = upBins[b] + dnBins[b];
          if (totBins[b] > maxBinVol) {
            maxBinVol = totBins[b];
            pocIdx = b;
          }
        }

        // Calculate 70% Value Area (VAH / VAL) around POC
        let vaVol = totBins[pocIdx];
        let valIdx = pocIdx, vahIdx = pocIdx;
        const targetVa = totalVol * 0.70;
        while (vaVol < targetVa && (valIdx > 0 || vahIdx < numBins - 1)) {
          const nextUp = vahIdx < numBins - 1 ? totBins[vahIdx + 1] : -1;
          const nextDn = valIdx > 0 ? totBins[valIdx - 1] : -1;
          if (nextUp >= nextDn && vahIdx < numBins - 1) {
            vahIdx++;
            vaVol += totBins[vahIdx];
          } else if (valIdx > 0) {
            valIdx--;
            vaVol += totBins[valIdx];
          } else break;
        }

        const vahPrice = minP + (vahIdx + 1) * step;
        const valPrice = minP + valIdx * step;
        const yVah = pane.candleSeries.priceToCoordinate(vahPrice);
        const yVal = pane.candleSeries.priceToCoordinate(valPrice);
        if (yVah !== null && yVal !== null) {
          ctx.fillStyle = "rgba(255, 235, 59, 0.04)";
          ctx.fillRect(0, Math.min(yVah, yVal), plotWidth, Math.abs(yVal - yVah));
        }

        const maxBarW = plotWidth * 0.22;
        for (let b = 0; b < numBins; b++) {
          const pTop = minP + (b + 1) * step;
          const pBot = minP + b * step;
          const yTop = pane.candleSeries.priceToCoordinate(pTop);
          const yBot = pane.candleSeries.priceToCoordinate(pBot);
          if (yTop === null || yBot === null) continue;

          const barH = Math.max(2, Math.abs(yBot - yTop) - 1);
          const topCoord = Math.min(yTop, yBot);
          const totW = maxBinVol > 0 ? (totBins[b] / maxBinVol) * maxBarW : 0;
          const upW = totBins[b] > 0 ? (upBins[b] / totBins[b]) * totW : 0;
          const dnW = totW - upW;

          // Up-Volume (Green) + Down-Volume (Red) anchored to right edge of plot area
          ctx.fillStyle = "rgba(38, 166, 154, 0.38)";
          ctx.fillRect(plotWidth - totW, topCoord, upW, barH);
          ctx.fillStyle = "rgba(239, 83, 80, 0.38)";
          ctx.fillRect(plotWidth - dnW, topCoord, dnW, barH);

          if (b === pocIdx) {
            ctx.strokeStyle = "#ffeb3b";
            ctx.lineWidth = 1.2;
            ctx.strokeRect(plotWidth - totW, topCoord, totW, barH);
          }
        }

        // Draw POC Full-Width Horizontal Line
        const pocPrice = minP + (pocIdx + 0.5) * step;
        const yPoc = pane.candleSeries.priceToCoordinate(pocPrice);
        if (yPoc !== null) {
          ctx.beginPath();
          ctx.strokeStyle = "rgba(255, 235, 59, 0.85)";
          ctx.lineWidth = 1.5;
          ctx.setLineDash([4, 4]);
          ctx.moveTo(0, yPoc);
          ctx.lineTo(plotWidth, yPoc);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = "#ffeb3b";
          ctx.font = "bold 10px sans-serif";
          ctx.fillText(`POC ${pocPrice.toFixed(1)}`, plotWidth - 85, yPoc - 4);
        }
      }
    }
  }
}

// ============================================================================
# APPLY & UPDATE ALL 10 INDICATORS ON A PANE
// ============================================================================
function updatePaneIndicators(pane) {
  if (!pane.candles || pane.candles.length === 0) return;

  // Update active indicator tags in ticker bar & button count
  pane.indBtnEl.textContent = `Indicators (${pane.inds.size}) ▾`;
  pane.indTagsEl.innerHTML = "";
  INDICATOR_LIST.forEach(item => {
    if (pane.inds.has(item.id)) {
      const span = document.createElement("span");
      span.className = "ind-tag";
      span.textContent = item.short;
      pane.indTagsEl.appendChild(span);
    }
  });

  // Adjust scale margins if RSI (10) Sub-Pane is active
  const hasRsi = pane.inds.has("rsi");
  pane.chart.priceScale("right").applyOptions({
    scaleMargins: hasRsi ? { top: 0.05, bottom: 0.25 } : { top: 0.06, bottom: 0.14 }
  });
  pane.volSeries.priceScale().applyOptions({
    scaleMargins: hasRsi ? { top: 0.62, bottom: 0.25 } : { top: 0.82, bottom: 0.0 }
  });

  let allMarkers = [];

  // [4] Supertrend (10, 3)
  if (pane.inds.has("st")) {
    const stOut = calcSupertrend(pane.candles, 10, 3.0);
    pane.seriesMap.st.setData(stOut.line);
    allMarkers = allMarkers.concat(stOut.markers);
  } else {
    pane.seriesMap.st.setData([]);
  }

  // [5] Intraday VWAP
  if (pane.inds.has("vwap")) {
    pane.seriesMap.vwap.setData(calcVWAP(pane.candles));
  } else {
    pane.seriesMap.vwap.setData([]);
  }

  // [6] EMA Ribbon (9, 21, 50, 200)
  if (pane.inds.has("ema")) {
    pane.seriesMap.ema9.setData(calcEMA(pane.candles, 9));
    pane.seriesMap.ema21.setData(calcEMA(pane.candles, 21));
    pane.seriesMap.ema50.setData(calcEMA(pane.candles, 50));
    pane.seriesMap.ema200.setData(calcEMA(pane.candles, 200));
  } else {
    pane.seriesMap.ema9.setData([]);
    pane.seriesMap.ema21.setData([]);
    pane.seriesMap.ema50.setData([]);
    pane.seriesMap.ema200.setData([]);
  }

  // [7] Bollinger Bands (20, 2)
  if (pane.inds.has("bb")) {
    const bb = calcBollinger(pane.candles, 20, 2.0);
    pane.seriesMap.bbBasis.setData(bb.basis);
    pane.seriesMap.bbUpper.setData(bb.upper);
    pane.seriesMap.bbLower.setData(bb.lower);
  } else {
    pane.seriesMap.bbBasis.setData([]);
    pane.seriesMap.bbUpper.setData([]);
    pane.seriesMap.bbLower.setData([]);
  }

  // [8] Central Pivot Range (CPR)
  if (pane.inds.has("cpr")) {
    const cpr = calcCPR(pane.candles);
    pane.seriesMap.cprP.setData(cpr.pArr);
    pane.seriesMap.cprTC.setData(cpr.tcArr);
    pane.seriesMap.cprBC.setData(cpr.bcArr);
  } else {
    pane.seriesMap.cprP.setData([]);
    pane.seriesMap.cprTC.setData([]);
    pane.seriesMap.cprBC.setData([]);
  }

  // [9] Market Structure (BOS / CHOCH)
  if (pane.inds.has("ms")) {
    const msMarkers = calcMarketStructure(pane.candles);
    allMarkers = allMarkers.concat(msMarkers);
  }

  // Sort and set markers on candlestick series
  allMarkers.sort((a, b) => a.time - b.time);
  pane.candleSeries.setMarkers(allMarkers);

  // [10] RSI (14) Sub-Pane
  if (hasRsi) {
    const rsiData = calcRSI(pane.candles, 14);
    pane.seriesMap.rsi.setData(rsiData);
    if (!pane.rsiLinesCreated) {
      pane.seriesMap.rsi.createPriceLine({ price: 70, color: "rgba(239, 68, 68, 0.6)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "70" });
      pane.seriesMap.rsi.createPriceLine({ price: 30, color: "rgba(34, 197, 94, 0.6)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "30" });
      pane.rsiLinesCreated = true;
    }
  } else {
    pane.seriesMap.rsi.setData([]);
  }

  // Compute FVG and Order Block zones for Canvas
  if (pane.inds.has("fvg") || pane.inds.has("ob")) {
    pane.smcZones = detectFVGAndOB(pane.candles);
  } else {
    pane.smcZones = { fvgs: [], obs: [] };
  }

  requestAnimationFrame(() => drawCanvasOverlays(pane));
}

function updateTickerUI(pane, price, prevClose) {
  const oldPrice = pane.lastPrice;
  pane.lastPrice = price;
  const diff = price - (prevClose || price);
  const pct = prevClose ? (diff / prevClose) * 100.0 : 0.0;
  const sign = diff >= 0 ? "+" : "";
  const colClass = diff >= 0 ? "up-col" : "dn-col";

  pane.priceEl.className = "tk-price " + colClass;
  pane.chgEl.className = "tk-chg " + colClass;
  pane.priceEl.textContent = price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  pane.chgEl.textContent = `${sign}${diff.toFixed(2)} (${sign}${pct.toFixed(2)}%)`;

  if (oldPrice !== null && oldPrice !== price) {
    const flashClass = price > oldPrice ? "flash-up" : "flash-dn";
    pane.tickerEl.classList.remove("flash-up", "flash-dn");
    void pane.tickerEl.offsetWidth;
    pane.tickerEl.classList.add(flashClass);
    setTimeout(() => pane.tickerEl.classList.remove(flashClass), 350);
  }
}

async function loadPaneData(pane) {
  const symObj = SYMBOLS.find(s => s.id === pane.sym) || SYMBOLS[0];
  pane.symLabelEl.textContent = symObj.id;
  pane.dotEl.className = "dot " + (symObj.type === "crypto" ? "dot-crypto" : "dot-stock");

  let data = null;
  if (symObj.type === "crypto") {
    data = await fetchCryptoHistory(symObj, pane.tf);
  } else {
    data = await fetchYfHistory(symObj.id, pane.tf);
  }

  if (data && data.candles && data.candles.length > 0) {
    pane.candles = data.candles;
    pane.prevClose = data.prevClose;
    pane.candleSeries.setData(pane.candles);
    const volData = pane.candles.map(c => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(38, 166, 154, 0.30)" : "rgba(239, 83, 80, 0.30)"
    }));
    pane.volSeries.setData(volData);
    const lastC = pane.candles[pane.candles.length - 1];
    updateTickerUI(pane, lastC.close, pane.prevClose);
    updatePaneIndicators(pane);
  }
}

function buildGrid(count) {
  const grid = document.getElementById("chart-grid");
  activePanes.forEach(p => {
    if (p.ro) p.ro.disconnect();
    if (p.chart) p.chart.remove();
  });
  activePanes = [];
  grid.innerHTML = "";

  const dims = getGridDims(count);
  grid.style.gridTemplateColumns = `repeat(${dims.cols}, 1fr)`;
  grid.style.gridTemplateRows = `repeat(${dims.rows}, 1fr)`;

  for (let i = 0; i < count; i++) {
    const def = DEFAULT_PANES[i] || { sym: "BTC", tf: "5m", inds: ["vpvr", "st"] };
    const paneEl = document.createElement("div");
    paneEl.className = "pane";

    const ctrlEl = document.createElement("div");
    ctrlEl.className = "pane-ctrl";

    const leftGroup = document.createElement("div");
    leftGroup.className = "ctrl-left";

    const symSel = document.createElement("select");
    symSel.className = "sym-sel";
    SYMBOLS.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.label;
      if (s.id === def.sym) opt.selected = true;
      symSel.appendChild(opt);
    });

    const tfSel = document.createElement("select");
    tfSel.className = "tf-sel";
    TIMEFRAMES.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      if (t === def.tf) opt.selected = true;
      tfSel.appendChild(opt);
    });

    leftGroup.appendChild(symSel);
    leftGroup.appendChild(tfSel);

    // Multi-Select Indicators Dropdown Menu
    const indDrop = document.createElement("div");
    indDrop.className = "ind-dropdown";
    const indBtn = document.createElement("button");
    indBtn.className = "ind-btn";
    indBtn.textContent = `Indicators (${(def.inds || []).length}) ▾`;

    const indMenu = document.createElement("div");
    indMenu.className = "ind-menu";

    indBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".ind-menu.open").forEach(m => {
        if (m !== indMenu) m.classList.remove("open");
      });
      indMenu.classList.toggle("open");
    });

    indDrop.appendChild(indBtn);
    indDrop.appendChild(indMenu);

    ctrlEl.appendChild(leftGroup);
    ctrlEl.appendChild(indDrop);

    const tickerEl = document.createElement("div");
    tickerEl.className = "ticker-bar";
    tickerEl.innerHTML = `
      <div class="tk-left">
        <span class="dot dot-crypto"></span>
        <span class="sym-lbl">${def.sym}</span>
        <div class="ind-tags"></div>
      </div>
      <div class="tk-right"><span class="tk-price up-col">--</span><span class="tk-chg up-col">--</span></div>
    `;

    const chartBox = document.createElement("div");
    chartBox.className = "chart-box";

    const canvas = document.createElement("canvas");
    canvas.className = "overlay-canvas";
    chartBox.appendChild(canvas);

    paneEl.appendChild(ctrlEl);
    paneEl.appendChild(tickerEl);
    paneEl.appendChild(chartBox);
    grid.appendChild(paneEl);

    const chart = LightweightCharts.createChart(chartBox, {
      layout: { background: { type: "solid", color: "#0f131c" }, textColor: "#94a3b8", fontSize: 11 },
      grid: { vertLines: { color: "#181c27" }, horzLines: { color: "#181c27" } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#232834" },
      timeScale: { borderColor: "#232834", timeVisible: true, secondsVisible: false }
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350",
      borderUpColor: "#26a69a", borderDownColor: "#ef5350",
      wickUpColor: "#26a69a", wickDownColor: "#ef5350"
    });

    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
      lastValueVisible: false,
      priceLineVisible: false
    });
    volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    // Pre-create native indicator series for instant toggle
    const seriesMap = {
      st: chart.addLineSeries({ lineWidth: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      vwap: chart.addLineSeries({ color: "#ffeb3b", lineWidth: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      ema9: chart.addLineSeries({ color: "#00bcd4", lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      ema21: chart.addLineSeries({ color: "#ffeb3b", lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      ema50: chart.addLineSeries({ color: "#a855f7", lineWidth: 1.5, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      ema200: chart.addLineSeries({ color: "#ef4444", lineWidth: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      bbBasis: chart.addLineSeries({ color: "#38bdf8", lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      bbUpper: chart.addLineSeries({ color: "rgba(56, 189, 248, 0.75)", lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      bbLower: chart.addLineSeries({ color: "rgba(56, 189, 248, 0.75)", lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      cprP: chart.addLineSeries({ color: "#f472b6", lineWidth: 1, lineStyle: 3, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      cprTC: chart.addLineSeries({ color: "#c084fc", lineWidth: 1, lineStyle: 3, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      cprBC: chart.addLineSeries({ color: "#c084fc", lineWidth: 1, lineStyle: 3, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }),
      rsi: chart.addLineSeries({ color: "#e879f9", lineWidth: 1.5, priceScaleId: "rsi", lastValueVisible: true, priceLineVisible: false })
    };
    chart.priceScale("rsi").applyOptions({
      scaleMargins: { top: 0.78, bottom: 0.02 },
      borderVisible: false
    });

    const paneObj = {
      idx: i, sym: def.sym, tf: def.tf,
      inds: new Set(def.inds || []),
      chart, candleSeries, volSeries, seriesMap,
      chartBox, canvas,
      indBtnEl: indBtn,
      indTagsEl: tickerEl.querySelector(".ind-tags"),
      tickerEl,
      dotEl: tickerEl.querySelector(".dot"),
      symLabelEl: tickerEl.querySelector(".sym-lbl"),
      priceEl: tickerEl.querySelector(".tk-price"),
      chgEl: tickerEl.querySelector(".tk-chg"),
      candles: [], prevClose: 0, lastPrice: null,
      smcZones: { fvgs: [], obs: [] },
      rsiLinesCreated: false
    };

    // Populate Indicator Checkboxes grouped by category
    let lastCat = "";
    INDICATOR_LIST.forEach(ind => {
      if (ind.cat !== lastCat) {
        lastCat = ind.cat;
        const catEl = document.createElement("div");
        catEl.className = "ind-cat";
        catEl.textContent = lastCat;
        indMenu.appendChild(catEl);
      }
      const lbl = document.createElement("label");
      lbl.className = "ind-item";
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.checked = paneObj.inds.has(ind.id);
      chk.addEventListener("change", () => {
        if (chk.checked) paneObj.inds.add(ind.id);
        else paneObj.inds.delete(ind.id);
        DEFAULT_PANES[i].inds = Array.from(paneObj.inds);
        saveConfig(count);
        updatePaneIndicators(paneObj);
      });
      const txt = document.createElement("span");
      txt.textContent = ind.label;
      lbl.appendChild(chk);
      lbl.appendChild(txt);
      indMenu.appendChild(lbl);
    });

    // Subscribe to pan/zoom & resize for smooth Canvas redraw
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      requestAnimationFrame(() => drawCanvasOverlays(paneObj));
    });

    const ro = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.applyOptions({ width, height });
          requestAnimationFrame(() => drawCanvasOverlays(paneObj));
        }
      }
    });
    ro.observe(chartBox);
    paneObj.ro = ro;

    symSel.addEventListener("change", () => {
      paneObj.sym = symSel.value;
      DEFAULT_PANES[i].sym = paneObj.sym;
      paneObj.lastPrice = null;
      saveConfig(count);
      loadPaneData(paneObj);
    });

    tfSel.addEventListener("change", () => {
      paneObj.tf = tfSel.value;
      DEFAULT_PANES[i].tf = paneObj.tf;
      saveConfig(count);
      loadPaneData(paneObj);
    });

    activePanes.push(paneObj);
    loadPaneData(paneObj);
  }
}

function connectHyperliquidWs() {
  try {
    hlSocket = new WebSocket("wss://api.hyperliquid.xyz/ws");
    hlSocket.onopen = () => {
      hlSocket.send(JSON.stringify({ method: "subscribe", subscription: { type: "allMids" } }));
    };
    hlSocket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.channel === "allMids" && msg.data && msg.data.mids) {
          const mids = msg.data.mids;
          activePanes.forEach(pane => {
            if (mids[pane.sym] !== undefined && pane.candles.length > 0) {
              const liveP = parseFloat(mids[pane.sym]);
              if (!isNaN(liveP) && liveP > 0) {
                const lastC = pane.candles[pane.candles.length - 1];
                lastC.close = liveP;
                if (liveP > lastC.high) lastC.high = liveP;
                if (liveP < lastC.low) lastC.low = liveP;
                lastC.volume = Math.max(lastC.volume, Math.round((lastC.high - lastC.low) * 1000));
                pane.candleSeries.update(lastC);
                updateTickerUI(pane, liveP, pane.prevClose);
                updatePaneIndicators(pane);
              }
            }
          });
        }
      } catch (e) {}
    };
    hlSocket.onclose = () => setTimeout(connectHyperliquidWs, 3000);
  } catch (e) {}
}

setInterval(() => {
  activePanes.forEach(pane => {
    const symObj = SYMBOLS.find(s => s.id === pane.sym);
    if (symObj && symObj.type === "yf") {
      loadPaneData(pane);
    }
  });
}, 8000);

loadSavedConfigs();
const savedCount = parseInt(localStorage.getItem("mc_chart_count_v2") || "4", 10);
const validCount = [1, 2, 4, 6, 8].includes(savedCount) ? savedCount : 4;
const countSel = document.getElementById("count-select");
countSel.value = String(validCount);
buildGrid(validCount);
connectHyperliquidWs();

countSel.addEventListener("change", () => {
  const c = parseInt(countSel.value, 10);
  saveConfig(c);
  buildGrid(c);
});
</script>
</body>
</html>"""
    multi_chart_html = multi_chart_html.replace("__INITIAL_YF_JSON__", yf_json_str)
    components.html(multi_chart_html, height=820, scrolling=False)

# ============================================================================
# ZERO-BLINK LIVE RENDERING LOOP FOR TAB 1 (AI-RENKO PRO)
# ============================================================================
while True:
    if not eng["initialized"] or eng["price"] == 0.0:
        terminal.info("⏳ Dr Devendra AI-Renko PRO: 1000 कैंडल्स से परमानेंट स्टेट-लॉक इंजन सेटअप हो रहा है...")
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
            status_label = f"🚀 5Q TRAILING ABOVE TP2 ({t_type}) | 5Q Booked"
            sl_tag = "Trail SL (5Q)"
        elif eng["mid_reached"]:
            status_label = f"🔒 5Q TP1 BOOKED • SL AT TP1 ({t_type})"
            sl_tag = "SL @ TP1 (5Q)"
        elif eng["tp1_reached"]:
            status_label = f"✅ 5Q TP1 BOOKED • SL AT COST ({t_type})"
            sl_tag = "Cost SL (5Q)"
        else:
            status_label = f"🔥 ACTIVE {t_type} (10 Qty Open | {eng['entry_tag']} @ {eng['entry_time_str']})"
            sl_tag = "Init SL (10Q)"

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:15px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
<span style="background:{badge_bg}; color:white; padding:5px 11px; border-radius:6px; font-weight:bold; font-size:13px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:800;">{total_live_pnl:+,.1f} pts</span>
</div>
<div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:10px; background:#0b1324; padding:6px 10px; border-radius:6px;">
<span>📦 Open Qty: <b style="color:#f8fafc;">{open_qty}/10</b></span>
<span>💰 Booked (5Q): <b style="color:#4ade80;">+{booked_pnl:,.1f}p</b></span>
<span>⚡ Runner ({open_qty}Q): <b style="color:{pnl_color};">{open_pnl:+,.1f}p</b></span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; color:#cbd5e1; font-size:12px; background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
<div>Entry (10Q)<br><b style="color:#ffffff; font-size:14px;">{entry:,.1f}</b></div>
<div>TP1 (Book 5Q)<br><b style="color:#22c55e; font-size:14px;">{tp1:,.1f}</b></div>
<div>TP2 (Trail 5Q)<br><b style="color:#38bdf8; font-size:14px;">{tp2:,.1f}</b></div>
<div>{sl_tag}<br><b style="color:#ef4444; font-size:14px;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR CONFIRMED SIGNAL (STATE-LOCKED • 10 QTY)</div>
<div style="color:#94a3b8; font-size:12px; margin-top:4px;">Supertrend: <b>{st_line:,.1f}</b> | Streak: <b>#{brick_streak}</b> | EMA21: <b>{ema21:,.1f}</b> | RSI: <b>{rsi14:.1f}</b></div>
</div>"""

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
    setup_str = f"TP1(5Q): +{box_size * TP1_BRICKS:.0f}p | TP2(5Q): +{box_size * TP2_BRICKS:.0f}p | SL: -{box_size * SL_BRICKS:.0f}p"

    raw_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; border:1px solid #1e293b; box-shadow:0 8px 30px rgba(0,0,0,0.6); font-family:sans-serif;">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
<div>
<div style="font-size:12px; color:#38bdf8; font-weight:700;">⚡ DR DEVENDRA AI-RENKO PRO [PERMANENT STATE-LOCKED 10-QTY]</div>
<div style="font-size:34px; font-weight:800; color:#ffffff; line-height:1.15;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="background:#1e293b; border:1px solid {st_badge_col}; color:{st_badge_col}; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:inline-block; margin-bottom:4px;">{st_badge_text}</div>
<div style="font-size:12px; color:#cbd5e1;">🔒 Incremental Lock | {ist_time}</div>
</div>
</div>
<div class="t-grid">
<div>
<div style="margin-bottom:14px; background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
<div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:6px;">
<span style="color:#22c55e;">🟢 3-Bar Buy Dom: {buy_pct}%</span>
<span style="color:#e2e8f0;">Imbalance: {imbalance:+.2f}</span>
<span style="color:#ef4444;">Sell Dom: {sell_pct}% 🔴</span>
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
<div style="font-size:13px; font-weight:bold; color:#38bdf8; margin-bottom:8px;">📊 10-QTY MASTER BACKTEST TABLE (5Q TP1 Book + Cost SL + 5Q Trail)</div>
<table style="width:100%; border-collapse:collapse; font-size:13px;">
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">23H Range | 1 Brick</td><td style="padding:6px; color:#facc15; font-weight:bold; text-align:right;">{safe_range:,.1f} pts | Brick: {box_size:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Position Sizing Rule</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">10 Qty (5Q @ TP1 + Cost SL + 5Q Trail)</td></tr>
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
<span style="font-size:14px; font-weight:bold; color:#f8fafc;">📜 10-Qty ट्रेड इतिहास लॉग (Permanent Lock)</span>
<span style="font-size:11px; color:#94a3b8;">Blocked Late: {eng['blocked_late']}</span>
</div>
<div style="max-height:460px; overflow-y:auto;">
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:6px;">समय</th>
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

import streamlit as st
import requests
import time
import threading
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="Dr Devendra AI-Renko PRO Terminal", layout="wide")

# Streamlit के डिफ़ॉल्ट हेडर/फूटर छुपाने और डार्क बैकग्राउंड फिक्स करने के लिए CSS
st.markdown("""<style>
.stApp { background-color: #0b0f19; color: #f8fafc; }
.block-container { padding-top: 0.8rem !important; padding-bottom: 0.8rem !important; max-width: 100% !important; }
header, footer, #MainMenu { visibility: hidden; }
.t-grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
@media (min-width: 960px) { .t-grid { grid-template-columns: 1.15fr 0.85fr; } }
</style>""", unsafe_allow_html=True)

# ============================================================================
# PINE SCRIPT INPUT PARAMETERS (100% Exact Match)
# ============================================================================
CONFIRM_ON_CLOSE     = True
USE_TP_SL_ENGINE     = True
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
TP2_BRICKS           = 2.2
SL_BRICKS            = 1.4
ANTI_WICK_SL         = True
BROK_PTS             = 15.0
MINTICK              = 0.1

# ============================================================================
# HELPER FUNCTIONS (Pine Script ta.rma, ta.atr, ta.ema, ta.rsi, f_gaussian)
# ============================================================================
def calc_rma_series(vals, length):
    rma = [0.0] * len(vals)
    if not vals:
        return rma
    alpha = 1.0 / float(length)
    for i, v in enumerate(vals):
        if i < length - 1:
            rma[i] = sum(vals[:i + 1]) / float(i + 1)
        elif i == length - 1:
            rma[i] = sum(vals[:length]) / float(length)
        else:
            rma[i] = (rma[i - 1] * (length - 1) + v) / float(length)
    return rma

def calc_atr_series(highs, lows, closes, length):
    tr = [0.0] * len(closes)
    for i in range(len(closes)):
        if i == 0:
            tr[i] = highs[i] - lows[i]
        else:
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return calc_rma_series(tr, length)

def calc_ema_series(closes, length):
    ema = [0.0] * len(closes)
    if not closes:
        return ema
    k = 2.0 / float(length + 1)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = closes[i] * k + ema[i - 1] * (1.0 - k)
    return ema

def calc_rsi_series(closes, length=14):
    n = len(closes)
    if n == 0:
        return []
    ups = [0.0] * n
    downs = [0.0] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        ups[i] = max(diff, 0.0)
        downs[i] = max(-diff, 0.0)
    rma_up = calc_rma_series(ups, length)
    rma_dn = calc_rma_series(downs, length)
    rsi = [50.0] * n
    for i in range(n):
        if rma_dn[i] == 0:
            rsi[i] = 100.0
        elif rma_up[i] == 0:
            rsi[i] = 0.0
        else:
            rs = rma_up[i] / rma_dn[i]
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calc_gaussian_series(src, length=20):
    n = len(src)
    if n == 0:
        return []
    w = (2.0 * math.pi) / float(length)
    b = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a = -b + math.sqrt(b * b + 2.0 * b)
    g = [0.0] * n
    for i in range(n):
        if i == 0:
            g[i] = src[0]
        else:
            g1 = g[i - 1]
            g2 = g[i - 2] if i >= 2 else src[i]
            g[i] = (a ** 2) * src[i] + 2.0 * (1.0 - a) * g1 - ((1.0 - a) ** 2) * g2
    return g

def fmt_pts(pts):
    return f"{pts:,.1f}"

# ============================================================================
# EXACT PINE SCRIPT BAR-BY-BAR SIMULATION ENGINE
# ============================================================================
def run_pine_engine(klines_1m, klines_1d):
    # 1. Daily Macro Range (request.security('D', ta.atr(5)[1]))
    macro_range = None
    if klines_1d and len(klines_1d) >= ATR_PERIOD + 2:
        d_highs = [float(k[2]) for k in klines_1d]
        d_lows = [float(k[3]) for k in klines_1d]
        d_closes = [float(k[4]) for k in klines_1d]
        d_atr = calc_atr_series(d_highs, d_lows, d_closes, ATR_PERIOD)
        # [1] means previous confirmed daily candle
        macro_range = d_atr[-2]

    # अलग करें: क्लोज हो चुकीं पक्की कैंडल्स और अभी चल रही लाइव कैंडल
    closed_klines = klines_1m[:-1] if CONFIRM_ON_CLOSE else klines_1m
    live_kline = klines_1m[-1]
    live_price = float(live_kline[4])
    live_high = float(live_kline[2])
    live_low = float(live_kline[3])

    n = len(closed_klines)
    opens = [float(k[1]) for k in closed_klines]
    highs = [float(k[2]) for k in closed_klines]
    lows = [float(k[3]) for k in closed_klines]
    closes = [float(k[4]) for k in closed_klines]
    vols = [float(k[5]) for k in closed_klines]
    times = [int(k[0]) for k in closed_klines]

    atr14_s = calc_atr_series(highs, lows, closes, 14)
    gauss_s = calc_gaussian_series(closes, GAUSS_PERIOD)
    ema21_s = calc_ema_series(closes, 21)
    rsi14_s = calc_rsi_series(closes, 14)

    # 3-Bar Orderflow Series
    bar_buy_v = [0.0] * n
    bar_sell_v = [0.0] * n
    buy_dom_s = [50.0] * n
    sell_dom_s = [50.0] * n

    for i in range(n):
        rng = max(highs[i] - lows[i], MINTICK)
        u_wick = highs[i] - max(opens[i], closes[i])
        l_wick = min(opens[i], closes[i]) - lows[i]
        body = abs(closes[i] - opens[i])
        bull_score = (closes[i] - lows[i]) + (l_wick * 1.1) + (body * 0.85 if closes[i] > opens[i] else 0.0)
        bear_score = (highs[i] - closes[i]) + (u_wick * 1.1) + (body * 0.85 if closes[i] < opens[i] else 0.0)
        bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8)
        bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
        tot_pow = bull_pow + bear_pow
        bar_buy_v[i] = vols[i] * (bull_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5
        bar_sell_v[i] = vols[i] * (bear_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5

        b1 = bar_buy_v[i - 1] if i >= 1 else 0.0
        b2 = bar_buy_v[i - 2] if i >= 2 else 0.0
        s1 = bar_sell_v[i - 1] if i >= 1 else 0.0
        s2 = bar_sell_v[i - 2] if i >= 2 else 0.0

        roll_buy = (bar_buy_v[i] * 1.4) + b1 + b2
        roll_sell = (bar_sell_v[i] * 1.4) + s1 + s2
        roll_tot = roll_buy + roll_sell
        buy_dom_s[i] = (roll_buy / roll_tot) * 100.0 if roll_tot > 0 else 50.0
        sell_dom_s[i] = 100.0 - buy_dom_s[i]

    # State Variables (Exact Pine Script var variables)
    brick_top = closes[0]
    brick_bot = closes[0] - MANUAL_BOX
    brick_dir = 1
    brick_streak = 1

    support_band = None
    resistance_band = None
    st_trend = 1

    trade_dir = 0
    entry_bar = -1
    entry_price = 0.0
    tp1_price = 0.0
    tp2_price = 0.0
    stop_price = 0.0
    hard_stop_price = 0.0
    max_fav_price = 0.0
    locked_tp1_pts = 0.0
    locked_tp2_pts = 0.0
    locked_sl_pts = 0.0
    tp1_reached = False
    tp2_reached = False
    entry_tag = ""
    entry_time_str = ""

    total_wins = 0
    total_losses = 0
    tp2_runner_hits = 0
    blocked_late_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_brok = 0.0
    max_single_run_pts = 0.0

    pending_flip_buy = False
    pending_flip_sell = False

    history = []
    last_result = "अभी कोई ट्रेड क्लोज नहीं हुआ है"
    last_result_color = "#334155"

    safe_range = macro_range if (macro_range and macro_range > 0) else (atr14_s[-1] * 10.0)
    box_size = MANUAL_BOX

    for i in range(n):
        c = closes[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        bar_ist = (datetime.utcfromtimestamp(times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%I:%M %p")

        safe_range = macro_range if (macro_range and macro_range > 0) else (atr14_s[i] * 10.0)
        calc_auto_box = safe_range / RANGE_DIVISOR
        box_size = max(calc_auto_box if USE_AUTO_BOX else MANUAL_BOX, MINTICK * 2.0)

        eval_price = (c * 0.70 + gauss_s[i] * 0.30) if USE_GAUSSIAN else c
        ema21 = ema21_s[i]
        rsi_val = rsi14_s[i]
        buy_dom_pct = buy_dom_s[i]
        sell_dom_pct = sell_dom_s[i]

        # Step 3: Pure Renko Brick Engine
        brick_turned = False
        brick_step_up = False
        brick_step_dn = False

        if i == 0:
            brick_top = c
            brick_bot = c - box_size
            brick_dir = 1
            brick_streak = 1
        else:
            if eval_price >= brick_top + box_size:
                steps = int(math.floor((eval_price - brick_top) / box_size))
                brick_top = brick_top + (steps * box_size)
                brick_bot = brick_top - box_size
                brick_step_up = True
                if brick_dir == -1:
                    brick_turned = True
                    brick_streak = steps
                else:
                    brick_streak += steps
                brick_dir = 1
            elif eval_price <= brick_bot - box_size:
                steps = int(math.floor((brick_bot - eval_price) / box_size))
                brick_bot = brick_bot - (steps * box_size)
                brick_top = brick_bot + box_size
                brick_step_dn = True
                if brick_dir == 1:
                    brick_turned = True
                    brick_streak = steps
                else:
                    brick_streak += steps
                brick_dir = -1

        r_close = brick_top if brick_dir == 1 else brick_bot

        # Step 4: Supertrend on Renko
        band_dist = box_size * ST_FACTOR
        raw_supp = r_close - band_dist
        raw_res = r_close + band_dist

        prev_trend = st_trend
        prev_supp = support_band
        prev_res = resistance_band

        if prev_supp is None:
            support_band = raw_supp
        elif prev_trend == 1:
            support_band = raw_supp if (brick_dir == 1 and raw_supp > prev_supp) else prev_supp
        else:
            support_band = raw_supp

        if prev_res is None:
            resistance_band = raw_res
        elif prev_trend == -1:
            resistance_band = raw_res if (brick_dir == -1 and raw_res < prev_res) else prev_res
        else:
            resistance_band = raw_res

        if prev_trend == -1 and brick_dir == 1 and prev_res is not None and r_close > prev_res:
            st_trend = 1
            support_band = r_close - band_dist
        elif prev_trend == 1 and brick_dir == -1 and prev_supp is not None and r_close < prev_supp:
            st_trend = -1
            resistance_band = r_close + band_dist
        else:
            st_trend = prev_trend

        st_line = support_band if st_trend == 1 else resistance_band
        st_flip_buy = (st_trend == 1 and prev_trend == -1)
        st_flip_sell = (st_trend == -1 and prev_trend == 1)

        if st_flip_buy or st_flip_sell:
            brick_streak = 1

        # Step 5: Non-Repainting Backtest & Signal Engine (MODE B: TP/SL Engine)
        if st_flip_buy:
            pending_flip_buy = True
            pending_flip_sell = False
        if st_flip_sell:
            pending_flip_sell = True
            pending_flip_buy = False
        if st_trend == -1:
            pending_flip_buy = False
        if st_trend == 1:
            pending_flip_sell = False

        # A. Manage Active Trade
        if trade_dir != 0 and i > entry_bar:
            t_label = "LONG" if trade_dir == 1 else "SHORT"
            max_fav_price = max(max_fav_price, h) if trade_dir == 1 else min(max_fav_price, l)

            # 1. Check TP1
            hit_tp1_now = (not tp1_reached) and ((h >= tp1_price) if trade_dir == 1 else (l <= tp1_price))
            if hit_tp1_now:
                tp1_reached = True
                total_wins += 1
                gross_profit += locked_tp1_pts
                total_brok += BROK_PTS
                max_single_run_pts = max(max_single_run_pts, locked_tp1_pts)
                stop_price = (entry_price - box_size * 0.25) if trade_dir == 1 else (entry_price + box_size * 0.25)

            # 2. Check TP2
            hit_tp2_now = tp1_reached and (not tp2_reached) and ((h >= tp2_price) if trade_dir == 1 else (l <= tp2_price))
            if hit_tp2_now:
                tp2_reached = True
                tp2_runner_hits += 1
                if not USE_TRAIL_BEYOND_TP2:
                    bonus_pts = max(0.0, locked_tp2_pts - locked_tp1_pts)
                    gross_profit += (bonus_pts * 0.6)
                    max_single_run_pts = max(max_single_run_pts, locked_tp2_pts)
                    tot_won = locked_tp1_pts + (bonus_pts * 0.6)
                    last_result = f"🎯 TP2 Hit: +{fmt_pts(tot_won)} pts ({t_label})"
                    last_result_color = "#166534"
                    history.insert(0, {
                        "time": bar_ist, "type": t_label, "entry": entry_price,
                        "exit": tp2_price, "status": "🎯 TP2 HIT", "pnl": f"+{fmt_pts(tot_won)}", "color": "#22c55e"
                    })
                    trade_dir = 0
                else:
                    lock_floor = (tp2_price - box_size * 0.35) if trade_dir == 1 else (tp2_price + box_size * 0.35)
                    stop_price = max(stop_price, lock_floor) if trade_dir == 1 else min(stop_price, lock_floor)

            # 3. Unlimited Trailing Logic beyond TP2
            if trade_dir != 0 and tp2_reached and USE_TRAIL_BEYOND_TP2:
                gap_dist = box_size * TRAIL_LOCK_BRICKS
                brick_trail = (r_close - gap_dist) if trade_dir == 1 else (r_close + gap_dist)
                peak_trail = (max_fav_price - gap_dist * 1.15) if trade_dir == 1 else (max_fav_price + gap_dist * 1.15)

                if TRAIL_METHOD == "Pure Renko Brick Step Trail":
                    cand_trail = brick_trail
                elif TRAIL_METHOD == "Renko Supertrend Line Trail":
                    cand_trail = st_line
                else:
                    cand_trail = max(brick_trail, peak_trail) if trade_dir == 1 else min(brick_trail, peak_trail)

                stop_price = max(stop_price, cand_trail) if trade_dir == 1 else min(stop_price, cand_trail)

                hit_trail_sl = (l <= stop_price) if trade_dir == 1 else (h >= stop_price)
                st_reversed = (st_trend == -1) if trade_dir == 1 else (st_trend == 1)

                if (hit_trail_sl or st_reversed) and not hit_tp2_now:
                    exit_p = stop_price if hit_trail_sl else (max(c, stop_price) if trade_dir == 1 else min(c, stop_price))
                    total_run_pts = (exit_p - entry_price) if trade_dir == 1 else (entry_price - exit_p)
                    safe_run_pts = max(total_run_pts, locked_tp2_pts * 0.85)
                    extra_bonus_pts = max(0.0, safe_run_pts - locked_tp1_pts)

                    gross_profit += (extra_bonus_pts * 0.6)
                    max_single_run_pts = max(max_single_run_pts, safe_run_pts)
                    tot_won = locked_tp1_pts + (extra_bonus_pts * 0.6)

                    last_result = f"🚀 Trail Exit: +{fmt_pts(safe_run_pts)} pts ({t_label})"
                    last_result_color = "#0369a1"
                    history.insert(0, {
                        "time": bar_ist, "type": t_label, "entry": entry_price,
                        "exit": exit_p, "status": "🚀 TRAIL EXIT", "pnl": f"+{fmt_pts(safe_run_pts)}", "color": "#38bdf8"
                    })
                    trade_dir = 0

            # 4. Anti-Wick Renko Stop-Loss Check before TP2
            if trade_dir != 0 and not tp2_reached:
                wick_hit_sl = (l <= stop_price) if trade_dir == 1 else (h >= stop_price)
                close_hit_sl = (c <= stop_price) if trade_dir == 1 else (c >= stop_price)
                brick_turned_bad = (brick_dir == -1 and c < brick_bot) if trade_dir == 1 else (brick_dir == 1 and c > brick_top)
                st_turned_bad = (st_trend == -1) if trade_dir == 1 else (st_trend == 1)
                hard_crash = (l <= hard_stop_price) if trade_dir == 1 else (h >= hard_stop_price)

                sl_triggered = (close_hit_sl or brick_turned_bad or st_turned_bad or hard_crash) if ANTI_WICK_SL else (wick_hit_sl or st_turned_bad)

                if sl_triggered and not hit_tp1_now:
                    if not tp1_reached:
                        total_losses += 1
                        actual_loss = min(abs(entry_price - c), locked_sl_pts * 1.15) if (ANTI_WICK_SL and not hard_crash) else locked_sl_pts
                        gross_loss += actual_loss
                        total_brok += BROK_PTS
                        last_result = f"❌ SL Hit: -{fmt_pts(actual_loss)} pts ({t_label})"
                        last_result_color = "#991b1b"
                        history.insert(0, {
                            "time": bar_ist, "type": t_label, "entry": entry_price,
                            "exit": c, "status": "🛑 SL HIT", "pnl": f"-{fmt_pts(actual_loss)}", "color": "#ef4444"
                        })
                    else:
                        # TP1 पहले ही लॉक हो चुका था, रनर प्रोटेक्टेड SL कटा
                        last_result = f"✅ TP1 Locked (Runner Exit): +{fmt_pts(locked_tp1_pts)} pts ({t_label})"
                        last_result_color = "#166534"
                        history.insert(0, {
                            "time": bar_ist, "type": t_label, "entry": entry_price,
                            "exit": stop_price, "status": "✅ TP1 LOCKED", "pnl": f"+{fmt_pts(locked_tp1_pts)}", "color": "#22c55e"
                        })
                    trade_dir = 0

        # B. Check New Entry Signals & Safety Filters
        candle_not_giant = (h - l) <= box_size * 1.85
        bull_filter_ok = candle_not_giant and buy_dom_pct >= 50.0 and rsi_val < 76.0
        bear_filter_ok = candle_not_giant and sell_dom_pct >= 50.0 and rsi_val > 24.0

        trigger_flip_buy = pending_flip_buy and st_trend == 1 and bull_filter_ok and c > o
        trigger_flip_sell = pending_flip_sell and st_trend == -1 and bear_filter_ok and c < o

        allow_re_entry = (SIG_MODE == "Supertrend + Brick-Step Re-Entry (Best)")
        raw_cont_buy = allow_re_entry and (not trigger_flip_buy) and st_trend == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and rsi_val > 50.0 and rsi_val < 72.0 and candle_not_giant
        raw_cont_sell = allow_re_entry and (not trigger_flip_sell) and st_trend == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and rsi_val < 50.0 and rsi_val > 28.0 and candle_not_giant

        streak_ok = (not USE_STREAK_FILTER) or (brick_streak <= MAX_BRICK_STREAK)
        stretch_ok = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
        late_safe = streak_ok and stretch_ok

        trigger_cont_buy = raw_cont_buy and late_safe
        trigger_cont_sell = raw_cont_sell and late_safe

        can_open_trade = (trade_dir == 0) or (tp1_reached and (st_flip_buy or st_flip_sell))

        if can_open_trade and ((raw_cont_buy and not trigger_cont_buy) or (raw_cont_sell and not trigger_cont_sell)):
            blocked_late_trades += 1

        if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
            # अगर पहले का ट्रेड TP1 हिट करने के बाद उलटे सुपरट्रेंड फ्लिप से कट रहा है तो उसे हिस्ट्री में दर्ज करें
            if trade_dir != 0 and tp1_reached:
                old_label = "LONG" if trade_dir == 1 else "SHORT"
                history.insert(0, {
                    "time": bar_ist, "type": old_label, "entry": entry_price,
                    "exit": c, "status": "✅ TP1 + FLIP", "pnl": f"+{fmt_pts(locked_tp1_pts)}", "color": "#22c55e"
                })

            is_long = trigger_flip_buy or trigger_cont_buy
            if is_long:
                pending_flip_buy = False
            else:
                pending_flip_sell = False

            trade_dir = 1 if is_long else -1
            entry_bar = i
            entry_price = c
            max_fav_price = c
            tp1_reached = False
            tp2_reached = False
            entry_tag = f"🧱 Brick #{brick_streak}" if (trigger_cont_buy or trigger_cont_sell) else "🔥 ST Flip Entry"
            entry_time_str = bar_ist

            locked_tp1_pts = box_size * TP1_BRICKS
            locked_tp2_pts = box_size * TP2_BRICKS
            locked_sl_pts = box_size * SL_BRICKS

            tp1_price = (entry_price + locked_tp1_pts) if is_long else (entry_price - locked_tp1_pts)
            tp2_price = (entry_price + locked_tp2_pts) if is_long else (entry_price - locked_tp2_pts)
            stop_price = (entry_price - locked_sl_pts) if is_long else (entry_price + locked_sl_pts)
            hard_stop_price = (stop_price - box_size * 0.5) if is_long else (stop_price + box_size * 0.5)

    active_trade = None
    if trade_dir != 0:
        active_trade = {
            "type": "LONG" if trade_dir == 1 else "SHORT",
            "entry": entry_price,
            "tp1": tp1_price,
            "tp2": tp2_price,
            "sl": stop_price,
            "hard_sl": hard_stop_price,
            "tp1_pts": locked_tp1_pts,
            "tp2_pts": locked_tp2_pts,
            "sl_pts": locked_sl_pts,
            "tp1_hit": tp1_reached,
            "tp2_hit": tp2_reached,
            "tag": entry_tag,
            "time": entry_time_str
        }

    tot_trades = total_wins + total_losses
    win_rate = (float(total_wins) / float(tot_trades) * 100.0) if tot_trades > 0 else 0.0
    net_profit = gross_profit - gross_loss - total_brok

    return {
        "price": live_price,
        "safe_range": safe_range,
        "box_size": box_size,
        "brick_top": brick_top,
        "brick_bot": brick_bot,
        "brick_dir": brick_dir,
        "brick_streak": brick_streak,
        "st_trend": st_trend,
        "st_line": st_line,
        "ema21": ema21_s[-1],
        "rsi14": rsi14_s[-1],
        "buy_pct": int(round(buy_dom_s[-1])),
        "sell_pct": int(round(sell_dom_s[-1])),
        "imbalance": (buy_dom_s[-1] - sell_dom_s[-1]) / 100.0,
        "active_trade": active_trade,
        "wins": total_wins,
        "losses": total_losses,
        "tot_trades": tot_trades,
        "win_rate": win_rate,
        "tp2_hits": tp2_runner_hits,
        "blocked_late": blocked_late_trades,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_brok": total_brok,
        "net_pnl": net_profit,
        "last_result": last_result,
        "last_result_color": last_result_color,
        "history": history[:25]
    }

# ============================================================================
# 24x7 BACKGROUND SERVER WORKER
# ============================================================================
def background_worker(state):
    endpoints = [
        "https://api.binance.us/api/v3",
        "https://api.binance.com/api/v3",
        "https://data-api.binance.vision/api/v3"
    ]
    last_1d_fetch = 0
    cached_1d = []

    while True:
        try:
            now_ts = time.time()
            klines_1m = None

            for base in endpoints:
                try:
                    r1 = requests.get(f"{base}/klines?symbol=BTCUSDT&interval=1m&limit=500", timeout=5)
                    if r1.status_code == 200:
                        data = r1.json()
                        if isinstance(data, list) and len(data) > 50:
                            klines_1m = data
                            if now_ts - last_1d_fetch > 300 or not cached_1d:
                                r2 = requests.get(f"{base}/klines?symbol=BTCUSDT&interval=1d&limit=20", timeout=5)
                                if r2.status_code == 200 and isinstance(r2.json(), list):
                                    cached_1d = r2.json()
                                    last_1d_fetch = now_ts
                            break
                except Exception:
                    continue

            if klines_1m:
                res = run_pine_engine(klines_1m, cached_1d)
                ist_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")
                res["ist_time"] = ist_time
                res["error"] = None
                state.update(res)

        except Exception as e:
            state["error"] = str(e)

        time.sleep(2)

@st.cache_resource
def get_server_engine():
    state = {
        "price": 0.0,
        "safe_range": 0.0,
        "box_size": 150.0,
        "brick_top": 0.0,
        "brick_bot": 0.0,
        "brick_dir": 1,
        "brick_streak": 1,
        "st_trend": 1,
        "st_line": 0.0,
        "ema21": 0.0,
        "rsi14": 50.0,
        "buy_pct": 50,
        "sell_pct": 50,
        "imbalance": 0.0,
        "ist_time": "--:--:--",
        "active_trade": None,
        "wins": 0,
        "losses": 0,
        "tot_trades": 0,
        "win_rate": 0.0,
        "tp2_hits": 0,
        "blocked_late": 0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "total_brok": 0.0,
        "net_pnl": 0.0,
        "last_result": "अभी कोई ट्रेड क्लोज नहीं हुआ है",
        "last_result_color": "#334155",
        "history": [],
        "error": None
    }
    thread = threading.Thread(target=background_worker, args=(state,), daemon=True)
    thread.start()
    return state

state = get_server_engine()
terminal = st.empty()

# ============================================================================
# ZERO-BLINK IN-PLACE LIVE RENDERING LOOP
# ============================================================================
while True:
    if state["price"] == 0.0:
        terminal.info("⏳ Dr Devendra AI-Renko PRO इंजन से 500 कैंडल्स और Daily ATR डेटा लोड हो रहा है...")
        time.sleep(1)
        continue

    price = state["price"]
    box_size = state["box_size"]
    safe_range = state["safe_range"]
    st_trend = state["st_trend"]
    st_line = state["st_line"]
    brick_dir = state["brick_dir"]
    brick_streak = state["brick_streak"]
    ema21 = state["ema21"]
    rsi14 = state["rsi14"]
    buy_pct = state["buy_pct"]
    sell_pct = state["sell_pct"]
    imbalance = state["imbalance"]
    ist_time = state["ist_time"]
    trade = state["active_trade"]

    st_badge_text = "STATUS: BUY 🟢" if st_trend == 1 else "STATUS: SELL 🔴"
    st_badge_col = "#00c891" if st_trend == 1 else "#f03769"

    if trade is not None:
        t_type = trade["type"]
        entry = trade["entry"]
        tp1 = trade["tp1"]
        tp2 = trade["tp2"]
        sl = trade["sl"]
        pnl = (price - entry) if t_type == "LONG" else (entry - price)
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
        badge_bg = "#00af6e" if t_type == "LONG" else "#dc284b"

        if trade["tp2_hit"]:
            status_label = f"🚀 TRAILING ACTIVE ({t_type} | {trade['tag']})"
        elif trade["tp1_hit"]:
            status_label = f"✅ TP1 LOCKED • RUNNER PROTECTED ({t_type})"
        else:
            status_label = f"🔥 ACTIVE {t_type} ({trade['tag']} @ {trade['time']})"

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:15px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:6px;">
<span style="background:{badge_bg}; color:white; padding:5px 11px; border-radius:6px; font-weight:bold; font-size:13px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:800;">{pnl:+.1f} pts</span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; color:#cbd5e1; font-size:12px; background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
<div>Entry<br><b style="color:#ffffff; font-size:14px;">{entry:,.1f}</b></div>
<div>TP1 (+{trade['tp1_pts']:.0f}p)<br><b style="color:#22c55e; font-size:14px;">{tp1:,.1f}</b></div>
<div>TP2 (+{trade['tp2_pts']:.0f}p)<br><b style="color:#38bdf8; font-size:14px;">{tp2:,.1f}</b></div>
<div>Active SL<br><b style="color:#ef4444; font-size:14px;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR CONFIRMED CLOSE SIGNAL</div>
<div style="color:#94a3b8; font-size:12px; margin-top:4px;">Supertrend Line: <b>{st_line:,.1f}</b> | Brick Streak: <b>#{brick_streak}</b> | EMA21: <b>{ema21:,.1f}</b> | RSI: <b>{rsi14:.1f}</b></div>
</div>"""

    rows_html = ""
    if not state["history"]:
        rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी कोई ट्रेड क्लोज नहीं हुआ है</td></tr>"""
    else:
        for h in state["history"]:
            h_col = h.get("color", "#22c55e")
            rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:12px;">
<td style="padding:8px 6px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 6px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 6px; color:#cbd5e1;">{h['entry']:,.1f} → {h['exit']:,.1f}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 6px; color:{h_col}; font-weight:bold; text-align:right;">{h['pnl']} pts</td>
</tr>"""

    net_color = "#00e676" if state["net_pnl"] >= 0 else "#ff5252"
    wr_color = "#00e676" if state["win_rate"] >= 60.0 else "#facc15"
    setup_str = f"+{box_size * TP1_BRICKS:.1f} / +{box_size * TP2_BRICKS:.1f} / -{box_size * SL_BRICKS:.1f}"

    raw_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; border:1px solid #1e293b; box-shadow:0 8px 30px rgba(0,0,0,0.6); font-family:sans-serif;">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
<div>
<div style="font-size:12px; color:#38bdf8; font-weight:700;">⚡ DR DEVENDRA AI-RENKO [CONFIRMED CLOSE ALGO PRO]</div>
<div style="font-size:34px; font-weight:800; color:#ffffff; line-height:1.15;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="background:#1e293b; border:1px solid {st_badge_col}; color:{st_badge_col}; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:inline-block; margin-bottom:4px;">{st_badge_text}</div>
<div style="font-size:12px; color:#cbd5e1;">🔒 Close-Locked | {ist_time} (IST)</div>
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
<div style="background:{state['last_result_color']}; color:#ffffff; padding:10px 14px; border-radius:8px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:14px;">
पिछला परिणाम: {state['last_result']}
</div>
<div style="background:#1e293b; border-radius:12px; padding:12px; border:1px solid #334155;">
<div style="font-size:13px; font-weight:bold; color:#38bdf8; margin-bottom:8px;">📊 MASTER ALGO BACKTEST TABLE (Pine Script 10-Row)</div>
<table style="width:100%; border-collapse:collapse; font-size:13px;">
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">23H Range | 1 Brick</td><td style="padding:6px; color:#facc15; font-weight:bold; text-align:right;">{safe_range:,.1f} pts | Brick: {box_size:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Active Algo Mode</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">🔒 Close-Locked | Trail ON</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Setup (TP1 / TP2 / SL)</td><td style="padding:6px; color:#38bdf8; font-weight:bold; text-align:right;">{setup_str}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Total Trades (W / L)</td><td style="padding:6px; color:#ffffff; font-weight:bold; text-align:right;">{state['tot_trades']} ({state['wins']}W / {state['losses']}L)</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Win Rate % | Runners</td><td style="padding:6px; color:{wr_color}; font-weight:bold; text-align:right;">{state['win_rate']:.1f}% | 🎯 TP2: {state['tp2_hits']}</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Points Won</td><td style="padding:6px; color:#4ade80; font-weight:bold; text-align:right;">+{state['gross_profit']:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Gross Points Lost</td><td style="padding:6px; color:#f87171; font-weight:bold; text-align:right;">-{state['gross_loss']:,.1f} pts</td></tr>
<tr style="border-bottom:1px solid #334155;"><td style="padding:6px; color:#94a3b8;">Total Brokerage/Tax (15p)</td><td style="padding:6px; color:#fca5a5; font-weight:bold; text-align:right;">-{state['total_brok']:,.1f} pts ({state['tot_trades']} Trds)</td></tr>
<tr style="background:#0f172a;"><td style="padding:8px 6px; color:#ffffff; font-weight:bold;">NET PROFIT (Points)</td><td style="padding:8px 6px; color:{net_color}; font-weight:800; font-size:15px; text-align:right;">{state['net_pnl']:+,.1f} pts</td></tr>
</table>
</div>
</div>
<div>
<div style="background:#1e293b; border-radius:12px; padding:14px; border:1px solid #334155; height:100%; box-sizing:border-box;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<span style="font-size:14px; font-weight:bold; color:#f8fafc;">📜 AI-Renko ट्रेड इतिहास लॉग</span>
<span style="font-size:11px; color:#94a3b8;">Blocked Late: {state['blocked_late']}</span>
</div>
<div style="max-height:460px; overflow-y:auto;">
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:6px;">समय</th>
<th style="padding:6px;">ट्रेड</th>
<th style="padding:6px;">Entry → Exit</th>
<th style="padding:6px;">स्टेटस</th>
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

    # हर लाइन के आगे के स्पेस हटाना ताकि Markdown कभी इसे कोड-ब्लॉक न समझे
    clean_html = "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())
    terminal.markdown(clean_html, unsafe_allow_html=True)
    time.sleep(2)

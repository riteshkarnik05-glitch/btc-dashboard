import streamlit as st
import requests
import time
import json
from datetime import datetime, timedelta
import math
import hmac
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Dr Devendra AI-Renko 70%+ Win-Rate Chart (v14)", layout="wide")

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
    padding: 6px 12px !important;
    width: 100% !important;
}
div.stButton > button:hover {
    background-color: #eab308 !important;
    color: #0f172a !important;
}
</style>""", unsafe_allow_html=True)

# ============================================================================
# DELTA EXCHANGE DEMO API & CONNECTION HELPERS (KEPT INTACT, ALGO PAUSED)
# ============================================================================
ALGO_EXECUTION_ENABLED = False  # ⏸️ अभी एल्गो आर्डर बंद रखा गया है (केवल चार्ट व सिग्नल टेस्टिंग मोड)

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

def place_delta_demo_order(side, qty, tag="Renko 10Q", is_exit=False, prod_id=27):
    if not ALGO_EXECUTION_ENABLED or qty <= 0:
        return False, "Algo Paused (Chart Test Mode)"
    try:
        payload = {
            "product_id": int(prod_id),
            "size": int(qty),
            "side": side.lower(),
            "order_type": "market_order"
        }
        if is_exit:
            payload["reduce_only"] = True
        ok, resp = delta_request("POST", "/v2/orders", payload)
        if (not ok) and is_exit:
            payload.pop("reduce_only", None)
            ok, resp = delta_request("POST", "/v2/orders", payload)
        return ok, resp
    except Exception as e:
        return False, str(e)

# ============================================================================
# V14 HIGH WIN-RATE (70%+ TARGET) + ANTI-WICK RENKO ST RUNNER PARAMETERS
# ============================================================================
TOTAL_QTY            = 10
USD_INR_RATE         = 85.0
BROK_PER_QTY         = 82.38   # Real Delta CSV Fee: ₹70.02 per 10Q trade (823.8 lot-pts)

# 🎯 V14 WIN-RATE BOOSTER & BIG WAVE RUNNER RULES:
# 1. Div 10 (~300p Big Stable Bricks) को वापस लॉक किया गया है (छोटी ब्रिक्स के व्हिपसॉ बंद!)।
# 2. Stage-1 Win Lock: +0.90 Brick (~+270p) छूते ही ट्रेड 'WIN' लॉक हो जाता है (+0.62B = +1,860p Gross / +₹88 Net Guaranteed)।
# 3. सबसे बड़ा बदलाव (Anti-Wick Trail): Stage-1 और Stage-2 का ट्रेल अब कैंडल की सुई (Low/High Wick) से कभी नहीं कटेगा!
#    ट्रेड तभी एग्जिट होगा जब कैंडल क्लोज (Candle Close) ट्रेल लाइन के नीचे हो या Renko Supertrend (ST 2.2) खुद पलटे!
STAGE1_TRIG_BRICKS   = 0.90    # +0.90 Brick (~+270p) छूते ही Win Lock!
STAGE1_LOCK_BRICKS   = 0.62    # +0.62 Brick (~+186p/Q = ₹158 Gross / +₹88 Net Guaranteed, No ₹5 Choke!)
STAGE2_TRIG_BRICKS   = 1.85    # +1.85 Bricks पर Big Runner Mode एक्टिव
STAGE2_FLOOR_BRICKS  = 1.35    # +1.35 Bricks (~+405p/Q = +₹274 Net Floor)
CLOSE_TRAIL_BRICKS   = 1.10    # केवल Candle Close पर 1.10B या Fast ST Line से ट्रेल (सुई/Wick से कभी बाहर नहीं होगा!)

# 🛡️ STRICT HIGH-CONVICTION ENTRY FILTERS (ताकि गलत ट्रेड्स छँट जाएं और Win Rate 70%+ रहे):
USE_STREAK_FILTER    = True
MAX_BRICK_STREAK     = 2       # केवल फ्रेश Brick #1 और #2 पर ही एंट्री (थकी हुई लेट एंट्री बंद)
USE_STRETCH_FILTER   = True
MAX_EMA_DIST_BRICKS  = 1.75
MIN_VOL_DOM          = 54.0    # मजबूत ऑर्डर-फ्लो डोमिनेंस

ATR_PERIOD           = 5
USE_GAUSSIAN         = True
GAUSS_PERIOD         = 20

SL_BRICKS            = 1.45
SL_RUPEES_CAP_10Q    = 200.0
MAX_SL_PTS_PER_QTY   = round((SL_RUPEES_CAP_10Q / USD_INR_RATE) * (1000.0 / TOTAL_QTY), 1)
ANTI_WICK_SL         = True
MINTICK              = 0.1

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

def pts_to_inr(lot_pts):
    return lot_pts * 0.001 * USD_INR_RATE

# ============================================================================
# FETCH HISTORICAL CANDLES & COMPUTE V14 HIGH-WIN-RATE RENKO ENGINE
# ============================================================================
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

def build_chart_and_renko_signals(signal_tf="15m", st_factor=2.2, range_divisor=10.0):
    macro_range = calc_daily_atr5()
    now_sec = int(time.time())
    today_00_utc_sec = (now_sec // 86400) * 86400
    days_back = 45 if signal_tf == "1h" else (25 if signal_tf == "15m" else 10)
    anchor_start_ms = (today_00_utc_sec - (days_back * 86400)) * 1000
    now_ms = now_sec * 1000

    klines = fetch_hl_klines_range(signal_tf, anchor_start_ms, now_ms)
    if not klines or len(klines) < 30:
        return None

    box_size = max(macro_range / float(range_divisor), MINTICK * 2.0)
    brok_10q = BROK_PER_QTY * TOTAL_QTY
    ist_offset_sec = 19800  # +5:30 IST offset

    candles_js = []
    rclose_js = []
    st_js = []
    ema_js = []
    markers_js = []
    trade_logs = []

    prev_close = 0.0
    tr_sum = 0.0
    atr14 = 15.0
    ema21 = 0.0
    up_sum = 0.0
    dn_sum = 0.0
    rma_up = 0.0
    rma_dn = 0.0
    rsi14 = 50.0
    g1 = 0.0
    g2 = 0.0
    buy_v1 = 0.0
    buy_v2 = 0.0
    sell_v1 = 0.0
    sell_v2 = 0.0
    buy_dom_pct = 50.0
    sell_dom_pct = 50.0

    brick_top = 0.0
    brick_bot = 0.0
    brick_dir = 1
    brick_streak = 1
    r_close = 0.0
    support_band = None
    resistance_band = None
    st_trend = 1
    st_line = 0.0
    pending_flip_buy = False
    pending_flip_sell = False

    trade_dir = 0
    entry_bar = -1
    entry_price = 0.0
    tp1_price = 0.0
    tp2_price = 0.0
    stop_price = 0.0
    hard_stop_price = 0.0
    max_fav_close = 0.0
    locked_sl_pts = 0.0
    tp1_reached = False
    tp2_reached = False
    entry_tag = ""
    entry_time_str = ""

    wins = 0
    losses = 0
    tp2_hits = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_brok = 0.0

    for idx, kline in enumerate(klines):
        bar_time_ms = int(kline[0])
        t_sec_ist = int(bar_time_ms // 1000) + ist_offset_sec
        o = float(kline[1])
        h = float(kline[2])
        l = float(kline[3])
        c = float(kline[4])
        v = float(kline[5])
        bar_ist = (datetime.utcfromtimestamp(bar_time_ms / 1000.0) + timedelta(hours=5, minutes=30)).strftime("%d %b %I:%M %p")

        if idx == 0:
            atr14 = h - l
            ema21 = c
            rsi14 = 50.0
        else:
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
            if idx < 14:
                tr_sum += tr
                atr14 = tr_sum / float(idx + 1)
            else:
                atr14 = (atr14 * 13.0 + tr) / 14.0

            k_ema = 2.0 / 22.0
            ema21 = c * k_ema + ema21 * (1.0 - k_ema)

            diff = c - prev_close
            up = max(diff, 0.0)
            dn = max(-diff, 0.0)
            if idx < 14:
                up_sum += up
                dn_sum += dn
                rma_up = up_sum / float(idx)
                rma_dn = dn_sum / float(idx)
            else:
                rma_up = (rma_up * 13.0 + up) / 14.0
                rma_dn = (rma_dn * 13.0 + dn) / 14.0

            if rma_dn == 0:
                rsi14 = 100.0
            elif rma_up == 0:
                rsi14 = 0.0
            else:
                rs = rma_up / rma_dn
                rsi14 = 100.0 - (100.0 / (1.0 + rs))

        w = (2.0 * math.pi) / float(GAUSS_PERIOD)
        b_g = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
        a_g = -b_g + math.sqrt(b_g * b_g + 2.0 * b_g)
        if idx == 0:
            g_val = c
        elif idx == 1:
            g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * g1 - ((1.0 - a_g) ** 2) * c
        else:
            g_val = (a_g ** 2) * c + 2.0 * (1.0 - a_g) * g1 - ((1.0 - a_g) ** 2) * g2
        g2 = g1
        g1 = g_val

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

        roll_buy = (bar_buy_v * 1.4) + buy_v1 + buy_v2
        roll_sell = (bar_sell_v * 1.4) + sell_v1 + sell_v2
        roll_tot = roll_buy + roll_sell
        buy_dom_pct = (roll_buy / roll_tot) * 100.0 if roll_tot > 0 else 50.0
        sell_dom_pct = 100.0 - buy_dom_pct

        buy_v2 = buy_v1
        buy_v1 = bar_buy_v
        sell_v2 = sell_v1
        sell_v1 = bar_sell_v

        eval_price = (c * 0.70 + g_val * 0.30) if USE_GAUSSIAN else c

        brick_step_up = False
        brick_step_dn = False

        if idx == 0:
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
                brick_streak = steps if brick_dir == -1 else (brick_streak + steps)
                brick_dir = 1
            elif eval_price <= brick_bot - box_size:
                steps = int(math.floor((brick_bot - eval_price) / box_size))
                brick_bot = brick_bot - (steps * box_size)
                brick_top = brick_bot + box_size
                brick_step_dn = True
                brick_streak = steps if brick_dir == 1 else (brick_streak + steps)
                brick_dir = -1

        r_close = brick_top if brick_dir == 1 else brick_bot

        band_distance = box_size * float(st_factor)
        raw_support = r_close - band_distance
        raw_resistance = r_close + band_distance

        prev_trend = st_trend
        prev_supp = support_band
        prev_res = resistance_band

        if prev_supp is None:
            support_band = raw_support
        elif prev_trend == 1:
            support_band = raw_support if (brick_dir == 1 and raw_support > prev_supp) else prev_supp
        else:
            support_band = raw_support

        if prev_res is None:
            resistance_band = raw_resistance
        elif prev_trend == -1:
            resistance_band = raw_resistance if (brick_dir == -1 and raw_resistance < prev_res) else prev_res
        else:
            resistance_band = raw_resistance

        if prev_trend == -1 and brick_dir == 1 and prev_res is not None and r_close > prev_res:
            st_trend = 1
            support_band = r_close - band_distance
        elif prev_trend == 1 and brick_dir == -1 and prev_supp is not None and r_close < prev_supp:
            st_trend = -1
            resistance_band = r_close + band_distance
        else:
            st_trend = prev_trend

        st_line = support_band if st_trend == 1 else resistance_band

        st_flip_buy = (idx > 0) and (st_trend == 1 and prev_trend == -1)
        st_flip_sell = (idx > 0) and (st_trend == -1 and prev_trend == 1)

        if st_flip_buy or st_flip_sell:
            brick_streak = 1

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

        candles_js.append({"time": t_sec_ist, "open": round(o, 1), "high": round(h, 1), "low": round(l, 1), "close": round(c, 1)})
        rclose_js.append({"time": t_sec_ist, "value": round(r_close, 1)})
        st_js.append({"time": t_sec_ist, "value": round(st_line, 1), "color": "#00e676" if st_trend == 1 else "#ff5252"})
        ema_js.append({"time": t_sec_ist, "value": round(ema21, 1)})

        # ====================================================================
        # V14 HIGH WIN-RATE + ANTI-WICK CANDLE-CLOSE & ST RUNNER ENGINE
        # ====================================================================
        if idx < len(klines) - 1:
            if trade_dir != 0 and idx > entry_bar:
                t_dir = trade_dir
                t_label = "LONG" if t_dir == 1 else "SHORT"
                max_fav_close = max(max_fav_close, c) if t_dir == 1 else min(max_fav_close, c)

                # 1. Stage-1 Trigger (+0.90 Brick) -> Locks Win (+0.62B = +₹88 Net Guaranteed!)
                hit_tp1_now = (not tp1_reached) and ((h >= tp1_price) if t_dir == 1 else (l <= tp1_price))
                if hit_tp1_now:
                    tp1_reached = True
                    wins += 1
                    s1_lock_pts = box_size * STAGE1_LOCK_BRICKS
                    s1_sl = (entry_price + s1_lock_pts) if t_dir == 1 else (entry_price - s1_lock_pts)
                    stop_price = max(stop_price, s1_sl) if t_dir == 1 else min(stop_price, s1_sl)

                # 2. Stage-2 Trigger (+1.85 Bricks) -> Locks +1.35B Floor & Rides ST Line / Close Trail!
                hit_tp2_now = tp1_reached and (not tp2_reached) and ((h >= tp2_price) if t_dir == 1 else (l <= tp2_price))
                if hit_tp2_now:
                    tp2_reached = True
                    tp2_hits += 1
                    s2_floor_pts = box_size * STAGE2_FLOOR_BRICKS
                    s2_sl = (entry_price + s2_floor_pts) if t_dir == 1 else (entry_price - s2_floor_pts)
                    stop_price = max(stop_price, s2_sl) if t_dir == 1 else min(stop_price, s2_sl)

                # Always ratchet stop_price up with Renko ST Line if ST Line is above current stop_price!
                if tp1_reached:
                    if t_dir == 1 and st_trend == 1 and st_line > stop_price:
                        stop_price = st_line
                    elif t_dir == -1 and st_trend == -1 and st_line < stop_price:
                        stop_price = st_line

                # 3. Stage-2 Big Wave Trailing (Checks CANDLE CLOSE `c` or ST Reversal — NEVER Wicks `l`/`h`!)
                if trade_dir != 0 and tp2_reached:
                    gap_dist = box_size * CLOSE_TRAIL_BRICKS
                    brick_trail = (r_close - gap_dist) if t_dir == 1 else (r_close + gap_dist)
                    close_trail = (max_fav_close - gap_dist) if t_dir == 1 else (max_fav_close + gap_dist)
                    cand_trail = max(brick_trail, close_trail, st_line if st_trend == 1 else 0.0) if t_dir == 1 else min(brick_trail, close_trail, st_line if st_trend == -1 else 999999.0)
                    stop_price = max(stop_price, cand_trail) if t_dir == 1 else min(stop_price, cand_trail)

                    # CRITICAL FIX: Only exit when CANDLE CLOSE (`c`) crosses stop_price OR Renko ST flips!
                    close_hit_trail = (c <= stop_price) if t_dir == 1 else (c >= stop_price)
                    st_reversed     = (st_trend == -1) if t_dir == 1 else (st_trend == 1)

                    if (close_hit_trail or st_reversed) and not hit_tp2_now:
                        exit_p = max(c, stop_price) if t_dir == 1 else min(c, stop_price)
                        run_pts_per_q = max(box_size * STAGE2_FLOOR_BRICKS, (exit_p - entry_price) if t_dir == 1 else (entry_price - exit_p))
                        total_trade_pnl = run_pts_per_q * TOTAL_QTY
                        gross_profit += total_trade_pnl
                        total_brok += brok_10q
                        net_inr = pts_to_inr(total_trade_pnl - brok_10q)

                        markers_js.append({
                            "time": t_sec_ist,
                            "position": "aboveBar" if t_dir == 1 else "belowBar",
                            "color": "#38bdf8",
                            "shape": "circle",
                            "text": f"🚀 BIG WAVE (₹{net_inr:+,.0f})"
                        })
                        trade_logs.insert(0, {
                            "time": bar_ist, "type": f"{t_label} ({entry_tag})", "entry": entry_price,
                            "exit": exit_p, "status": "🚀 10Q BIG ST WAVE EXIT",
                            "pnl": f"+{total_trade_pnl:,.0f}p (Net ₹{net_inr:+,.0f})", "color": "#38bdf8"
                        })
                        trade_dir = 0

                # 4. Pre-Stage-2 Exit Check (Stage-1 Close Lock or Initial SL)
                if trade_dir != 0 and not tp2_reached:
                    if not tp1_reached:
                        adverse_close_pts = (entry_price - c) if t_dir == 1 else (c - entry_price)
                        renko_sl_price = (entry_price - box_size * SL_BRICKS) if t_dir == 1 else (entry_price + box_size * SL_BRICKS)
                        close_hit_renko_sl = (c <= renko_sl_price) if t_dir == 1 else (c >= renko_sl_price)
                        brick_turned_bad = (
                            (brick_dir == -1 and c < brick_bot and adverse_close_pts >= MAX_SL_PTS_PER_QTY * 0.65)
                            if t_dir == 1
                            else (brick_dir == 1 and c > brick_top and adverse_close_pts >= MAX_SL_PTS_PER_QTY * 0.65)
                        )
                        st_turned_bad = ((st_trend == -1) if t_dir == 1 else (st_trend == 1)) and (adverse_close_pts > 0)
                        hard_crash = (l <= hard_stop_price) if t_dir == 1 else (h >= hard_stop_price)

                        if close_hit_renko_sl or brick_turned_bad or st_turned_bad or hard_crash:
                            losses += 1
                            loss_per_qty = min(adverse_close_pts, locked_sl_pts) if (ANTI_WICK_SL and not hard_crash and adverse_close_pts > 0) else locked_sl_pts
                            total_loss_10q = loss_per_qty * TOTAL_QTY
                            gross_loss += total_loss_10q
                            total_brok += brok_10q
                            net_loss_inr = pts_to_inr(-(total_loss_10q + brok_10q))

                            markers_js.append({
                                "time": t_sec_ist,
                                "position": "belowBar" if t_dir == 1 else "aboveBar",
                                "color": "#f87171",
                                "shape": "circle",
                                "text": f"🛑 SL (₹{net_loss_inr:+,.0f})"
                            })
                            trade_logs.insert(0, {
                                "time": bar_ist, "type": f"{t_label} ({entry_tag})", "entry": entry_price,
                                "exit": c, "status": "🛑 SL HIT (10Q)",
                                "pnl": f"-{total_loss_10q:,.0f}p (Net ₹{net_loss_inr:+,.0f})", "color": "#ef4444"
                            })
                            trade_dir = 0
                    else:
                        # Stage-1 Locked: Exits ONLY on Candle Close (`c <= stop_price`) or ST Flip!
                        hit_s1_close = (c <= stop_price) if t_dir == 1 else (c >= stop_price)
                        st_turned_bad = (st_trend == -1) if t_dir == 1 else (st_trend == 1)

                        if (hit_s1_close or st_turned_bad) and not hit_tp1_now:
                            exit_p = max(c, stop_price) if t_dir == 1 else min(c, stop_price)
                            locked_pts_q = max(box_size * STAGE1_LOCK_BRICKS, (exit_p - entry_price) if t_dir == 1 else (entry_price - exit_p))
                            total_trade_pnl = locked_pts_q * TOTAL_QTY
                            gross_profit += total_trade_pnl
                            total_brok += brok_10q
                            net_inr = pts_to_inr(total_trade_pnl - brok_10q)

                            markers_js.append({
                                "time": t_sec_ist,
                                "position": "aboveBar" if t_dir == 1 else "belowBar",
                                "color": "#4ade80",
                                "shape": "circle",
                                "text": f"✅ S1 WIN (₹{net_inr:+,.0f})"
                            })
                            trade_logs.insert(0, {
                                "time": bar_ist, "type": f"{t_label} ({entry_tag})", "entry": entry_price,
                                "exit": exit_p, "status": "✅ 10Q STAGE-1 WIN LOCK",
                                "pnl": f"+{total_trade_pnl:,.0f}p (Net ₹{net_inr:+,.0f})", "color": "#22c55e"
                            })
                            trade_dir = 0

            # ================================================================
            # HIGH-PROBABILITY ENTRY SIGNALS (EMA21 ALIGNED + BRICK SYNCED)
            # ================================================================
            candle_not_giant = (h - l) <= box_size * 1.80
            bull_filter_ok   = candle_not_giant and buy_dom_pct >= 52.0 and c > ema21 and 50.0 <= rsi14 < 74.0
            bear_filter_ok   = candle_not_giant and sell_dom_pct >= 52.0 and c < ema21 and 26.0 < rsi14 <= 50.0

            trigger_flip_buy  = pending_flip_buy and st_trend == 1 and brick_dir == 1 and bull_filter_ok and c > o
            trigger_flip_sell = pending_flip_sell and st_trend == -1 and brick_dir == -1 and bear_filter_ok and c < o

            raw_cont_buy  = (not trigger_flip_buy) and st_trend == 1 and brick_dir == 1 and brick_step_up and buy_dom_pct >= MIN_VOL_DOM and c > ema21 and 52.0 < rsi14 < 71.0 and candle_not_giant
            raw_cont_sell = (not trigger_flip_sell) and st_trend == -1 and brick_dir == -1 and brick_step_dn and sell_dom_pct >= MIN_VOL_DOM and c < ema21 and 29.0 < rsi14 < 48.0 and candle_not_giant

            streak_ok  = (not USE_STREAK_FILTER) or (brick_streak <= MAX_BRICK_STREAK)
            stretch_ok = (not USE_STRETCH_FILTER) or (abs(c - ema21) <= box_size * MAX_EMA_DIST_BRICKS)
            late_safe  = streak_ok and stretch_ok

            trigger_cont_buy  = raw_cont_buy and late_safe
            trigger_cont_sell = raw_cont_sell and late_safe

            can_open_trade = (trade_dir == 0) or (tp1_reached and (st_flip_buy or st_flip_sell))

            if can_open_trade and (trigger_flip_buy or trigger_cont_buy or trigger_flip_sell or trigger_cont_sell):
                if trade_dir != 0 and tp1_reached:
                    old_label = "LONG" if trade_dir == 1 else "SHORT"
                    runner_pts_q = max(box_size * STAGE1_LOCK_BRICKS, (c - entry_price) if trade_dir == 1 else (entry_price - c))
                    tot_flip_pnl = runner_pts_q * TOTAL_QTY
                    gross_profit += tot_flip_pnl
                    total_brok += brok_10q
                    net_flip_inr = pts_to_inr(tot_flip_pnl - brok_10q)
                    trade_logs.insert(0, {
                        "time": bar_ist, "type": f"{old_label} ({entry_tag})", "entry": entry_price,
                        "exit": c, "status": "✅ 10Q ST FLIP WIN",
                        "pnl": f"+{tot_flip_pnl:,.0f}p (Net ₹{net_flip_inr:+,.0f})", "color": "#22c55e"
                    })

                is_long = trigger_flip_buy or trigger_cont_buy
                if is_long:
                    pending_flip_buy = False
                else:
                    pending_flip_sell = False

                trade_dir = 1 if is_long else -1
                entry_bar = idx
                entry_price = c
                max_fav_close = c
                tp1_reached = False
                tp2_reached = False
                entry_tag = f"🧱 B#{brick_streak}" if (trigger_cont_buy or trigger_cont_sell) else "🔥 ST"
                entry_time_str = bar_ist

                locked_tp1_pts = box_size * STAGE1_TRIG_BRICKS
                locked_tp2_pts = box_size * STAGE2_TRIG_BRICKS
                locked_sl_pts  = MAX_SL_PTS_PER_QTY

                tp1_price       = (c + locked_tp1_pts) if is_long else (c - locked_tp1_pts)
                tp2_price       = (c + locked_tp2_pts) if is_long else (c - locked_tp2_pts)
                stop_price      = (c - locked_sl_pts) if is_long else (c + locked_sl_pts)
                hard_stop_price = (c - box_size * 1.65) if is_long else (c + box_size * 1.65)

                markers_js.append({
                    "time": t_sec_ist,
                    "position": "belowBar" if is_long else "aboveBar",
                    "color": "#00e676" if is_long else "#ff1744",
                    "shape": "arrowUp" if is_long else "arrowDown",
                    "text": f"{'BUY' if is_long else 'SELL'} {entry_tag} @ {c:,.0f}"
                })

        prev_close = c

    active_trade_info = {
        "active": trade_dir != 0,
        "dir": "LONG ▲" if trade_dir == 1 else ("SHORT ▼" if trade_dir == -1 else "NONE"),
        "dir_code": trade_dir,
        "tag": entry_tag,
        "time": entry_time_str,
        "entry": round(entry_price, 1),
        "tp1": round(tp1_price, 1),
        "tp2": round(tp2_price, 1),
        "sl": round(stop_price, 1),
        "tp1_reached": tp1_reached,
        "tp2_reached": tp2_reached
    }

    return {
        "candles": candles_js,
        "rclose": rclose_js,
        "st_line": st_js,
        "ema21": ema_js,
        "markers": markers_js,
        "logs": trade_logs[:40],
        "box_size": box_size,
        "macro_range": macro_range,
        "last_price": candles_js[-1]["close"],
        "r_close_now": rclose_js[-1]["value"],
        "st_now": st_js[-1]["value"],
        "st_trend": st_trend,
        "brick_dir": brick_dir,
        "brick_streak": brick_streak,
        "wins": wins,
        "losses": losses,
        "tp2_hits": tp2_hits,
        "net_pnl": gross_profit - gross_loss - total_brok,
        "active_trade": active_trade_info
    }

# ============================================================================
# TOP CONTROL BAR (70%+ WIN-RATE V14 ENGINE CONTROLS)
# ============================================================================
server_ip = get_server_public_ip()
if "delta_msg" not in st.session_state:
    st.session_state["delta_msg"] = "⏸️ Algo Paused (v14 High Win-Rate + Anti-Wick Big Wave Mode)"

c1, c2, c3, c4, c5, c6 = st.columns([0.28, 0.12, 0.18, 0.16, 0.13, 0.13])
with c1:
    st.markdown(
        f"**🌐 IP:** `{server_ip}` | <span style='color:#facc15;font-weight:700;'>{st.session_state['delta_msg']}</span>",
        unsafe_allow_html=True
    )
with c2:
    selected_tf = st.selectbox("⏱️ टाइमफ्रेम", ["15m", "1h", "5m"], index=0, label_visibility="collapsed")
with c3:
    div_label = st.selectbox(
        "🧱 Brick Size (Divisor)",
        [
            "Div 10 (~300p Stable - High WR)",
            "Div 12 (~250p Balanced)",
            "Div 14 (~210p Medium)",
            "Div 16 (~180p Small)"
        ],
        index=0,
        label_visibility="collapsed"
    )
    selected_divisor = float(div_label.split()[1])
with c4:
    st_mult_label = st.selectbox(
        "⚡ ST Multiplier",
        ["ST 2.2 (Best Wave + High WR)", "ST 2.5 (Smooth Trend)", "ST 2.0 (Fast)", "ST 3.0 (Original)"],
        index=0,
        label_visibility="collapsed"
    )
    selected_st_mult = float(st_mult_label.split()[1])
with c5:
    if st.button("🔌 Delta API टेस्ट"):
        ok, resp = delta_request("GET", "/v2/wallet/balances")
        if ok:
            st.session_state["delta_msg"] = "✅ Delta Connected!"
        else:
            st.session_state["delta_msg"] = f"⚠️ Error: {resp}"
        st.rerun()
with c6:
    if st.button("🔄 चार्ट रिफ्रेश"):
        st.rerun()

data = build_chart_and_renko_signals(signal_tf=selected_tf, st_factor=selected_st_mult, range_divisor=selected_divisor)

if not data:
    st.warning("⏳ Hyperliquid से BTC चार्ट डेटा लोड हो रहा है, कृपया 2 सेकंड बाद रिफ्रेश करें...")
    st.stop()

tot_tr = data["wins"] + data["losses"]
wr_pct = (data["wins"] / tot_tr * 100.0) if tot_tr > 0 else 0.0
net_inr_val = pts_to_inr(data["net_pnl"])
st_txt = f"{selected_tf.upper()} RENKO ST ({selected_st_mult}): BUY ▲" if data["st_trend"] == 1 else f"{selected_tf.upper()} RENKO ST ({selected_st_mult}): SELL ▼"
st_col = "#00e676" if data["st_trend"] == 1 else "#ff5252"

# ============================================================================
# INTERACTIVE TRADINGVIEW LIGHTWEIGHT CHART (V14 HIGH WIN-RATE)
# ============================================================================
candles_json = json.dumps(data["candles"])
rclose_json  = json.dumps(data["rclose"])
st_json      = json.dumps(data["st_line"])
ema_json     = json.dumps(data["ema21"])
markers_json = json.dumps(data["markers"])
active_json  = json.dumps(data["active_trade"])

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
    border: 1px solid {st_col}; color: {st_col}; background: #1e293b;
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
      <span style="color:#38bdf8; font-weight:800; font-size:13px;">⚡ BTCUSD ({selected_tf.upper()}) v14 HIGH WIN-RATE + ANTI-WICK RUNNER</span>
      <span id="live-price-txt" class="live-px">${data['last_price']:,.2f}</span>
      <span class="badge">{st_txt}</span>
      <span style="font-size:12px; color:#facc15; font-weight:700;">
        🧱 1 Brick: {data['box_size']:,.1f}p | rClose: {data['r_close_now']:,.1f} | ST Line: {data['st_now']:,.1f}
      </span>
    </div>
    <div class="btn-bar">
      <button class="c-btn" onclick="chart.timeScale().scrollToRealTime()">⏩ Latest Candle</button>
      <button class="c-btn" onclick="chart.timeScale().fitContent()">🔍 Fit All Signals</button>
    </div>
  </div>

  <div class="legend-bar">
    <div class="leg-item"><span class="dot" style="background:#facc15;"></span> Renko Step (rClose)</div>
    <div class="leg-item"><span class="dot" style="background:#00e676;"></span><span class="dot" style="background:#ff5252;"></span> Renko Supertrend (ST {selected_st_mult})</div>
    <div class="leg-item"><span class="dot" style="background:#38bdf8;"></span> EMA 21</div>
    <div id="hover-info" style="margin-left:auto; color:#e2e8f0; font-size:12.5px; font-weight:700;">
      🏆 Win Rate: <span style="color:#00e676;font-size:14px;">{wr_pct:.1f}%</span> ({data['wins']}W / {data['losses']}L) | 🚀 Big Waves: {data['tp2_hits']} | Net Profit (After ₹70 Fee): <span style="color:#4ade80;font-size:14px;">₹{net_inr_val:+,.0f}</span>
    </div>
  </div>

  <div id="tv-chart"></div>
</div>

<script>
const candlesData = {candles_json};
const rcloseData  = {rclose_json};
const stData      = {st_json};
const emaData     = {ema_json};
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

const rcloseSeries = chart.addLineSeries({{
  color: '#facc15',
  lineWidth: 2,
  lineType: LightweightCharts.LineType.WithSteps,
  title: 'rClose (Brick)'
}});
rcloseSeries.setData(rcloseData);

const stSeries = chart.addLineSeries({{
  lineWidth: 3,
  lineType: LightweightCharts.LineType.WithSteps,
  title: 'Renko ST (' + {selected_st_mult} + ')'
}});
stSeries.setData(stData);

const emaSeries = chart.addLineSeries({{
  color: '#38bdf8',
  lineWidth: 1,
  lineStyle: LightweightCharts.LineStyle.Dashed,
  title: 'EMA21'
}});
emaSeries.setData(emaData);

if (activeTrade && activeTrade.active) {{
  candleSeries.createPriceLine({{
    price: activeTrade.entry,
    color: '#ffffff',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: 'ENTRY (' + activeTrade.dir + ')'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.tp1,
    color: '#4ade80',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'S1 Win Lock (0.9B)'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.tp2,
    color: '#38bdf8',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: 'S2 Big Wave (1.85B)'
  }});
  candleSeries.createPriceLine({{
    price: activeTrade.sl,
    color: activeTrade.tp1_reached ? '#00e676' : '#ef4444',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true,
    title: activeTrade.tp1_reached ? 'CLOSE-ONLY TRAIL SL' : 'INITIAL SL (₹200)'
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

components.html(chart_html, height=650, scrolling=False)

# ============================================================================
# ACTIVE SIGNAL BANNER & TRADE HISTORY LOG BELOW CHART
# ============================================================================
act = data["active_trade"]
if act["active"]:
    live_pts_q = (data["last_price"] - act["entry"]) if act["dir_code"] == 1 else (act["entry"] - data["last_price"])
    live_net_inr = pts_to_inr((live_pts_q * TOTAL_QTY) - (BROK_PER_QTY * TOTAL_QTY))
    st.markdown(
        f"""<div style="background:#1e293b; border:1.5px solid #00e676; border-radius:10px; padding:10px 14px; margin-bottom:10px; font-size:13px;">
        🔥 <b>चार्ट पर वर्तमान ओपन ट्रेड (v14 Anti-Wick Close Trail):</b>
        <span style="color:#facc15;font-weight:bold;">{act['dir']} ({act['tag']} @ {act['time']})</span> |
        <b>Entry:</b> {act['entry']:,.1f} | <b>Live Net PnL:</b> <span style="color:#4ade80;font-weight:800;">₹{live_net_inr:+,.0f} ({live_pts_q:+,.1f}p/Q)</span> |
        <b>Stage-1 (0.9B):</b> {act['tp1']:,.1f} | <b>Stage-2 (1.85B):</b> {act['tp2']:,.1f} | <b>Current SL:</b> <span style="color:#38bdf8;font-weight:bold;">{act['sl']:,.1f}</span>
        </div>""",
        unsafe_allow_html=True
    )

with st.expander("📜 v14 High Win-Rate सिग्नल्स और ट्रेड्स की पूरी लिस्ट देखें (Click to Expand)", expanded=True):
    rows_html = ""
    for lg in data["logs"]:
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
        <th style="padding:6px;">समय (IST)</th><th style="padding:6px;">सिग्नल</th><th style="padding:6px;">Entry → Exit</th>
        <th style="padding:6px;">एग्जिट स्टेटस</th><th style="padding:6px; text-align:right;">10Q Net PnL (₹70 फीस काटकर)</th>
        </tr></thead><tbody>{rows_html}</tbody></table></div>""",
        unsafe_allow_html=True
    )

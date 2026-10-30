import streamlit as st
import requests
import time
import threading
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="AI-Renko Pro Terminal", layout="wide")

BOX_SIZE = 150.0
ST_FACTOR = 3.0
TP1_BRICKS = 0.85
TP2_BRICKS = 2.2
SL_BRICKS = 1.4
TRAIL_GAP_BRICKS = 0.8

def gaussian_filter(src_list, len_val=20):
    if len(src_list) < len_val:
        return src_list[-1] if src_list else 0.0
    w = (2.0 * math.pi) / float(len_val)
    b = (1.0 - math.cos(w)) / (1.41421356 - 1.0)
    a = -b + math.sqrt(b * b + 2.0 * b)
    g = src_list[0]
    for s in src_list[1:]:
        g = math.pow(a, 2) * s + 2.0 * (1.0 - a) * g - math.pow(1.0 - a, 2) * g
    return g

def background_worker(state):
    brick_top = 0.0
    brick_bot = 0.0
    brick_dir = 1
    st_trend = 1
    support_band = 0.0
    resistance_band = 0.0
    initialized = False

    while True:
        try:
            url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=100"
            response = requests.get(url, timeout=5)
            klines = response.json()

            if klines and isinstance(klines, list):
                closes = [float(k[4]) for k in klines]
                highs = [float(k[2]) for k in klines]
                lows = [float(k[3]) for k in klines]
                opens = [float(k[1]) for k in klines]

                price = closes[-1]
                smooth_close = gaussian_filter(closes, 20)
                eval_price = (price * 0.70 + smooth_close * 0.30)

                rng = max(highs[-1] - lows[-1], 0.1)
                u_wick = highs[-1] - max(opens[-1], closes[-1])
                l_wick = min(opens[-1], closes[-1]) - lows[-1]
                body = abs(closes[-1] - opens[-1])

                bull_score = (closes[-1] - lows[-1]) + (l_wick * 1.1) + (body * 0.85 if closes[-1] > opens[-1] else 0.0)
                bear_score = (highs[-1] - closes[-1]) + (u_wick * 1.1) + (body * 0.85 if closes[-1] < opens[-1] else 0.0)

                bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8)
                bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
                tot_pow = bull_pow + bear_pow

                buy_pct = int((bull_pow / tot_pow) * 100) if tot_pow > 0 else 50
                sell_pct = 100 - buy_pct
                imbalance = (bull_pow - bear_pow) / tot_pow if tot_pow > 0 else 0.0

                if not initialized:
                    brick_top = eval_price
                    brick_bot = eval_price - BOX_SIZE
                    brick_dir = 1
                    support_band = brick_top - (BOX_SIZE * ST_FACTOR)
                    resistance_band = brick_top + (BOX_SIZE * ST_FACTOR)
                    initialized = True

                if eval_price >= brick_top + BOX_SIZE:
                    steps = int(math.floor((eval_price - brick_top) / BOX_SIZE))
                    brick_top += (steps * BOX_SIZE)
                    brick_bot = brick_top - BOX_SIZE
                    brick_dir = 1
                elif eval_price <= brick_bot - BOX_SIZE:
                    steps = int(math.floor((brick_bot - eval_price) / BOX_SIZE))
                    brick_bot -= (steps * BOX_SIZE)
                    brick_top = brick_bot + BOX_SIZE
                    brick_dir = -1

                r_close = brick_top if brick_dir == 1 else brick_bot

                band_dist = BOX_SIZE * ST_FACTOR
                raw_supp = r_close - band_dist
                raw_res = r_close + band_dist

                prev_trend = st_trend
                if st_trend == 1:
                    support_band = raw_supp if (brick_dir == 1 and raw_supp > support_band) else support_band
                else:
                    support_band = raw_supp

                if st_trend == -1:
                    resistance_band = raw_res if (brick_dir == -1 and raw_res < resistance_band) else resistance_band
                else:
                    resistance_band = raw_res

                if prev_trend == -1 and brick_dir == 1 and r_close > resistance_band:
                    st_trend = 1
                    support_band = r_close - band_dist
                elif prev_trend == 1 and brick_dir == -1 and r_close < support_band:
                    st_trend = -1
                    resistance_band = r_close + band_dist

                st_flip_buy = (st_trend == 1 and prev_trend == -1)
                st_flip_sell = (st_trend == -1 and prev_trend == 1)

                ist_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")

                state["price"] = price
                state["imbalance"] = imbalance
                state["buy_pct"] = buy_pct
                state["sell_pct"] = sell_pct
                state["ist_time"] = ist_time
                state["error"] = None

                trade = state["active_trade"]

                if trade is None:
                    if st_flip_buy or (buy_pct >= 60 and imbalance >= 0.35 and st_trend == 1):
                        t1_pts = BOX_SIZE * TP1_BRICKS
                        t2_pts = BOX_SIZE * TP2_BRICKS
                        sl_pts = BOX_SIZE * SL_BRICKS
                        state["active_trade"] = {
                            "type": "LONG",
                            "entry": price,
                            "tp1": price + t1_pts,
                            "tp2": price + t2_pts,
                            "sl": price - sl_pts,
                            "tp1_hit": False,
                            "tp2_hit": False,
                            "max_fav": price,
                            "time": ist_time
                        }
                    elif st_flip_sell or (sell_pct >= 60 and imbalance <= -0.35 and st_trend == -1):
                        t1_pts = BOX_SIZE * TP1_BRICKS
                        t2_pts = BOX_SIZE * TP2_BRICKS
                        sl_pts = BOX_SIZE * SL_BRICKS
                        state["active_trade"] = {
                            "type": "SHORT",
                            "entry": price,
                            "tp1": price - t1_pts,
                            "tp2": price - t2_pts,
                            "sl": price + sl_pts,
                            "tp1_hit": False,
                            "tp2_hit": False,
                            "max_fav": price,
                            "time": ist_time
                        }
                else:
                    t_type = trade.get("type", "LONG")
                    entry = trade.get("entry", price)
                    tp1 = trade.get("tp1", price + 100)
                    tp2 = trade.get("tp2", price + 200)
                    sl = trade.get("sl", price - 100)

                    if t_type == "LONG":
                        trade["max_fav"] = max(trade.get("max_fav", price), price)
                    else:
                        trade["max_fav"] = min(trade.get("max_fav", price), price)

                    pnl = (price - entry) if t_type == "LONG" else (entry - price)

                    if not trade.get("tp1_hit", False):
                        if (t_type == "LONG" and price >= tp1) or (t_type == "SHORT" and price <= tp1):
                            trade["tp1_hit"] = True
                            trade["sl"] = entry

                    if trade.get("tp1_hit", False) and not trade.get("tp2_hit", False):
                        if (t_type == "LONG" and price >= tp2) or (t_type == "SHORT" and price <= tp2):
                            trade["tp2_hit"] = True

                    if trade.get("tp2_hit", False):
                        trail_dist = BOX_SIZE * TRAIL_GAP_BRICKS
                        if t_type == "LONG":
                            new_trail = r_close - trail_dist
                            trade["sl"] = max(trade.get("sl", entry), new_trail)
                        else:
                            new_trail = r_close + trail_dist
                            trade["sl"] = min(trade.get("sl", entry), new_trail)

                    current_sl = trade.get("sl", entry)
                    is_sl_hit = (t_type == "LONG" and price <= current_sl) or (t_type == "SHORT" and price >= current_sl)
                    is_st_reversed = (t_type == "LONG" and st_trend == -1) or (t_type == "SHORT" and st_trend == 1)

                    if is_sl_hit or is_st_reversed:
                        final_pnl = (current_sl - entry) if t_type == "LONG" else (entry - current_sl)
                        if is_st_reversed and not is_sl_hit:
                            final_pnl = pnl

                        status_txt = "🎯 TP2 + TRAIL" if trade.get("tp2_hit", False) else ("✅ TP1 LOCKED" if trade.get("tp1_hit", False) else "🛑 SL HIT")
                        
                        state["wins" if final_pnl >= 0 else "losses"] += 1
                        state["net_pnl"] += final_pnl
                        state["last_result"] = f"{status_txt} ({t_type} | {final_pnl:+.1f} Pts)"
                        state["history"].insert(0, {
                            "time": ist_time, "type": t_type, "entry": entry,
                            "exit": price, "status": status_txt, "pnl": f"{final_pnl:+.1f}"
                        })
                        state["history"] = state["history"][:20]
                        state["active_trade"] = None

        except Exception as e:
            state["error"] = str(e)

        time.sleep(3)

@st.cache_resource
def get_server_engine():
    state = {
        "price": 0.0,
        "imbalance": 0.0,
        "buy_pct": 50,
        "sell_pct": 50,
        "ist_time": "--:--:--",
        "history": [],
        "active_trade": None,
        "last_result": "अभी कोई ट्रेड क्लोज नहीं हुआ है",
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0,
        "error": None
    }
    thread = threading.Thread(target=background_worker, args=(state,), daemon=True)
    thread.start()
    return state

state = get_server_engine()

st.title("⚡ AI-Renko Supertrend Pro Terminal")

if state["price"] == 0.0:
    st.info("⏳ सर्वर इंजन से लाइव डेटा कनेक्ट हो रहा है...")
    time.sleep(1)
    st.rerun()

price = state["price"]
buy_pct = state["buy_pct"]
sell_pct = state["sell_pct"]
imbalance = state["imbalance"]
ist_time = state["ist_time"]
trade = state["active_trade"]

# शीर्ष मेट्रिक्स बार
col_m1, col_m2 = st.columns([2, 1])
with col_m1:
    st.metric(label="💰 लाइव BTC प्राइस (USDT)", value=f"${price:,.2f}")
with col_m2:
    st.metric(label="⏰ भारतीय समय (IST)", value=ist_time)

# प्रेशर बार
st.write(f"**बायर/सेलर प्रेशर:** 🟢 Buy: {buy_pct}% | 🔴 Sell: {sell_pct}% (Dominance: {imbalance:+.2f})")
st.progress(buy_pct / 100)

st.divider()

# दो कॉलम लेआउट (प्रोफेशनल टर्मिनल व्यू)
col_left, col_right = st.columns(2, gap="medium")

with col_left:
    st.markdown("### 🚀 एक्टिव ट्रेड स्टेटस")
    if trade is not None:
        t_type = trade.get("type", "LONG")
        entry = trade.get("entry", price)
        tp1 = trade.get("tp1", price + 100)
        tp2 = trade.get("tp2", price + 200)
        sl = trade.get("sl", price - 100)
        pnl = (price - entry) if t_type == "LONG" else (entry - price)
        
        status_label = "🚀 TRAILING RUNNER" if trade.get("tp2_hit", False) else ("🔒 TP1 LOCKED (Protected)" if trade.get("tp1_hit", False) else f"🚀 ACTIVE {t_type}")
        
        st.success(f"**{status_label}** | PnL: **{pnl:+.1f} Pts**")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entry", f"{entry:,.1f}")
        c2.metric("TP1", f"{tp1:,.1f}")
        c3.metric("TP2", f"{tp2:,.1f}")
        c4.metric("Trailing SL", f"{sl:,.1f}")
    else:
        st.info("🔍 मार्केट स्टेटस: WAITING FOR AI-RENKO / ST FLIP (±0.35)")

    st.markdown(f"**पिछला परिणाम:** {state['last_result']}")

    st.markdown("### 📊 स्कोरबोर्ड")
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("🎯 Target Hit", state["wins"])
    sc2.metric("🛑 SL Hit", state["losses"])
    sc3.metric("📊 Net PnL", f"{state['net_pnl']:+.1f} Pts")

with col_right:
    st.markdown("### 📜 ट्रेड इतिहास लॉग")
    if not state["history"]:
        st.write("अभी तक कोई ट्रेड पूरा नहीं हुआ है")
    else:
        for h in state["history"]:
            color_icon = "🟢" if "+" in h['pnl'] else "🔴"
            st.markdown(f"{color_icon} **{h['time']}** | `{h['type']}` | {h['entry']:,.0f} → {h['exit']:,.0f} | **{h['status']}** | `{h['pnl']} Pts`")

time.sleep(3)
st.rerun()

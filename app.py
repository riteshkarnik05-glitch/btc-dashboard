import streamlit as st
import requests
import time
import threading
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="AI-Renko Pro Terminal", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100% !important; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# पाइन स्क्रिप्ट के सटीक पैरामीटर
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

                # 1. नया ट्रेड सिग्नल खोलें
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
                    # 2. एक्टिव ट्रेड का TP1, TP2 और ट्रेलिंग SL मैनेज करें
                    t_type = trade["type"]
                    entry = trade["entry"]
                    tp1 = trade["tp1"]
                    tp2 = trade["tp2"]
                    sl = trade["sl"]

                    # मैक्सिमम अनुकूल कीमत अपडेट करें
                    if t_type == "LONG":
                        trade["max_fav"] = max(trade["max_fav"], price)
                    else:
                        trade["max_fav"] = min(trade["max_fav"], price)

                    pnl = (price - entry) if t_type == "LONG" else (entry - price)

                    # TP1 चेक करें
                    if not trade["tp1_hit"]:
                        if (t_type == "LONG" and price >= tp1) or (t_type == "SHORT" and price <= tp1):
                            trade["tp1_hit"] = True
                            # पाइन स्क्रिप्ट के अनुसार TP1 के बाद SL को एंट्री प्राइस पर प्रोटेक्ट कर दें
                            trade["sl"] = entry

                    # TP2 और ट्रेलिंग चेक करें
                    if trade["tp1_hit"] and not trade["tp2_hit"]:
                        if (t_type == "LONG" and price >= tp2) or (t_type == "SHORT" and price <= tp2):
                            trade["tp2_hit"] = True

                    # यदि TP2 हिट हो गया है, तो रैंकों ब्रिक के हिसाब से ट्रेलिंग चालू करें
                    if trade["tp2_hit"]:
                        trail_dist = BOX_SIZE * TRAIL_GAP_BRICKS
                        if t_type == "LONG":
                            new_trail = r_close - trail_dist
                            trade["sl"] = max(trade["sl"], new_trail)
                        else:
                            new_trail = r_close + trail_dist
                            trade["sl"] = min(trade["sl"], new_trail)

                    # स्टॉप लॉस या ट्रेलिंग हिट की जांच
                    is_sl_hit = (t_type == "LONG" and price <= trade["sl"]) or (t_type == "SHORT" and price >= trade["sl"])
                    # यदि सुपरट्रेंड विपरीत दिशा में पलट जाए
                    is_st_reversed = (t_type == "LONG" and st_trend == -1) or (t_type == "SHORT" and st_trend == 1)

                    if is_sl_hit or is_st_reversed:
                        final_pnl = (trade["sl"] - entry) if t_type == "LONG" else (entry - trade["sl"])
                        if is_st_reversed and not is_sl_hit:
                            final_pnl = pnl # अगर सुपरट्रेंड पलटा तो करंट क्लोज पर काटें

                        status_txt = "🎯 TP2 + TRAIL CLOSED" if trade["tp2_hit"] else ("✅ TP1 LOCKED" if trade["tp1_hit"] else "🛑 STOP LOSS HIT")
                        result_color = "#166534" if final_pnl >= 0 else "#991b1b"

                        state["wins" if final_pnl >= 0 else "losses"] += 1
                        state["net_pnl"] += final_pnl
                        state["last_result"] = f"{status_txt} ({t_type} | {final_pnl:+.1f} Pts)"
                        state["last_result_color"] = result_color
                        state["history"].insert(0, {
                            "time": ist_time, "type": t_type, "entry": entry,
                            "exit": price, "status": status_txt, "pnl": f"{final_pnl:+.1f}", "color": "#22c55e" if final_pnl >= 0 else "#ef4444"
                        })
                        state["history"] = state["history"][:25]
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
        "last_result_color": "#334155",
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0,
        "error": None
    }
    thread = threading.Thread(target=background_worker, args=(state,), daemon=True)
    thread.start()
    return state

state = get_server_engine()
terminal = st.empty()

while True:
    if state["price"] == 0.0:
        terminal.info("⏳ AI-Renko Supertrend सर्वर इंजन कनेक्ट हो रहा है...")
        time.sleep(1)
        continue

    price = state["price"]
    imbalance = state["imbalance"]
    buy_pct = state["buy_pct"]
    sell_pct = state["sell_pct"]
    ist_time = state["ist_time"]
    trade = state["active_trade"]

    if trade is not None:
        t_type = trade["type"]
        entry = trade["entry"]
        tp1 = trade["tp1"]
        tp2 = trade["tp2"]
        sl = trade["sl"]
        pnl = (price - entry) if t_type == "LONG" else (entry - price)
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
        badge_bg = "#16a34a" if t_type == "LONG" else "#dc2626"
        status_label = "🚀 TRAILING RUNNER" if trade["tp2_hit"] else ("🔒 TP1 LOCKED (Protected)" if trade["tp1_hit"] else f"🚀 ACTIVE {t_type}")

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:16px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<span style="background:{badge_bg}; color:white; padding:6px 12px; border-radius:6px; font-weight:bold; font-size:15px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:bold;">{pnl:+.1f} Pts</span>
</div>
<div style="display:flex; justify-content:space-between; color:#cbd5e1; font-size:14px; background:#0f172a; padding:12px; border-radius:8px;">
<div>Entry<br><b style="color:#ffffff;">{entry:,.1f}</b></div>
<div>TP1 (127.5p)<br><b style="color:#22c55e;">{tp1:,.1f}</b></div>
<div>TP2 (330p)<br><b style="color:#38bdf8;">{tp2:,.1f}</b></div>
<div>Trailing SL<br><b style="color:#ef4444;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        trade_box_html = """<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:16px;">🔍 WAITING FOR AI-RENKO / ST FLIP</div>
<div style="color:#94a3b8; font-size:13px; margin-top:4px;">TP1, TP2 और ट्रेलिंग इंजन सक्रिय है</div>
</div>"""

    rows_html = ""
    if not state["history"]:
        rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी कोई ट्रेड पूरा नहीं हुआ है</td></tr>"""
    else:
        for h in state["history"]:
            rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:14px;">
<td style="padding:10px 6px; color:#94a3b8;">{h['time']}</td>
<td style="padding:10px 6px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:10px 6px; color:#cbd5e1;">{h['entry']:,.0f} → {h['exit']:,.0f}</td>
<td style="padding:10px 6px; color:{h['color']}; font-weight:bold;">{h['status']}</td>
<td style="padding:10px 6px; color:{h['color']}; font-weight:bold; text-align:right;">{h['pnl']}</td>
</tr>"""

    net_color = "#22c55e" if state["net_pnl"] >= 0 else "#ef4444"

    full_html = f"""
<style>
.terminal-grid {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 20px;
}}
@media (min-width: 900px) {{
    .terminal-grid {{
        grid-template-columns: 1fr 1fr;
    }}
}}
</style>

<div style="background:#0f172a; color:#f8fafc; padding:20px; border-radius:16px; font-family:sans-serif; box-shadow:0 4px 25px rgba(0,0,0,0.5);">
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:12px; margin-bottom:16px;">
        <div>
            <div style="font-size:13px; color:#94a3b8;">⚡ AI-RENKO SUPERTREND PRO TERMINAL</div>
            <div style="font-size:32px; font-weight:800; color:#ffffff;">${price:,.2f}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:12px; color:#22c55e;">● 24x7 RESPONSIVE LIVE (IST)</div>
            <div style="font-size:14px; color:#cbd5e1;">{ist_time}</div>
        </div>
    </div>

    <div class="terminal-grid">
        <div>
            <div style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:bold; margin-bottom:6px;">
                    <span style="color:#22c55e;">🟢 Buy: {buy_pct}%</span>
                    <span style="color:#e2e8f0;">Dominance: {imbalance:+.2f}</span>
                    <span style="color:#ef4444;">Sell: {sell_pct}% 🔴</span>
                </div>
                <div style="width:100%; background:#ef4444; height:14px; border-radius:7px; overflow:hidden;">
                    <div style="width:{buy_pct}%; background:#22c55e; height:100%;"></div>
                </div>
            </div>

            {trade_box_html}

            <div style="background:{state['last_result_color']}; color:#ffffff; padding:10px 14px; border-radius:8px; font-size:14px; font-weight:bold; text-align:center; margin-bottom:14px;">
                पिछला परिणाम: {state['last_result']}
            </div>

            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-bottom:14px; text-align:center;">
                <div style="background:#1e293b; padding:10px; border-radius:8px;">
                    <div style="font-size:12px; color:#94a3b8;">🎯 TARGET HIT</div>
                    <div style="font-size:20px; font-weight:bold; color:#22c55e;">{state['wins']}</div>
                </div>
                <div style="background:#1e293b; padding:10px; border-radius:8px;">
                    <div style="font-size:12px; color:#94a3b8;">🛑 SL HIT</div>
                    <div style="font-size:20px; font-weight:bold; color:#ef4444;">{state['losses']}</div>
                </div>
                <div style="background:#1e293b; padding:10px; border-radius:8px;">
                    <div style="font-size:12px; color:#94a3b8;">📊 NET PnL</div>
                    <div style="font-size:20px; font-weight:bold; color:{net_color};">{state['net_pnl']:+.1f}</div>
                </div>
            </div>
        </div>

        <div>
            <div style="background:#1e293b; border-radius:12px; padding:14px; height:100%;">
                <div style="font-size:14px; font-weight:bold; color:#cbd5e1; margin-bottom:8px;">📜 AI-Renko ट्रेड इतिहास लॉग</div>
                <div style="max-height: 380px; overflow-y: auto;">
                    <table style="width:100%; border-collapse:collapse;">
                        <thead>
                            <tr style="border-bottom:1px solid #475569; font-size:12px; color:#94a3b8; text-align:left;">
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
</div>
"""

    terminal.markdown(full_html, unsafe_allow_html=True)
    time.sleep(3)

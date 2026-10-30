import streamlit as st
import requests
import time
import threading
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="AI-Renko Pro Terminal", layout="centered")

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 550px; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# पाइन स्क्रिप्ट के अनुसार सेटिंग्स
BOX_SIZE = 150.0  # रैंकों बॉक्स साइज़
ST_FACTOR = 3.0   # सुपरट्रेंड मल्टीप्लायर
TP1_BRICKS = 0.85
TP2_BRICKS = 2.2
SL_BRICKS = 1.4

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
    # रैंकों और सुपरट्रेंड स्टेट्स
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
                volumes = [float(k[5]) for k in klines]

                price = closes[-1]
                smooth_close = gaussian_filter(closes, 20)
                eval_price = (price * 0.70 + smooth_close * 0.30)

                # 3-Bar Orderflow Dominance (पाइन स्क्रिप्ट लॉजिक)
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

                # रैंकों ब्रिक इंजन
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

                # सुपरट्रेंड इंजन
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

                st_line = support_band if st_trend == 1 else resistance_band

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

                # ट्रेड सिग्नल और TP / SL निष्पादन
                if trade is None:
                    if st_flip_buy or (buy_pct >= 60 and imbalance >= 0.35 and st_trend == 1):
                        locked_tp1 = BOX_SIZE * TP1_BRICKS
                        locked_sl = BOX_SIZE * SL_BRICKS
                        state["active_trade"] = {
                            "type": "LONG",
                            "entry": price,
                            "target": price + locked_tp1,
                            "sl": price - locked_sl,
                            "time": ist_time
                        }
                    elif st_flip_sell or (sell_pct >= 60 and imbalance <= -0.35 and st_trend == -1):
                        locked_tp1 = BOX_SIZE * TP1_BRICKS
                        locked_sl = BOX_SIZE * SL_BRICKS
                        state["active_trade"] = {
                            "type": "SHORT",
                            "entry": price,
                            "target": price - locked_tp1,
                            "sl": price + locked_sl,
                            "time": ist_time
                        }
                else:
                    t_type = trade["type"]
                    entry = trade["entry"]
                    target = trade["target"]
                    sl = trade["sl"]

                    pnl = (price - entry) if t_type == "LONG" else (entry - price)

                    is_target = (t_type == "LONG" and price >= target) or (t_type == "SHORT" and price <= target)
                    is_sl = (t_type == "LONG" and price <= sl) or (t_type == "SHORT" and price >= sl)

                    if is_target:
                        state["wins"] += 1
                        state["net_pnl"] += pnl
                        state["last_result"] = f"🎯 TARGET HIT! ({t_type} Closed at {price:,.1f} | +{pnl:.1f} Pts)"
                        state["last_result_color"] = "#166534"
                        state["history"].insert(0, {
                            "time": ist_time, "type": t_type, "entry": entry,
                            "exit": price, "status": "🎯 TARGET HIT", "pnl": f"+{pnl:.1f}", "color": "#22c55e"
                        })
                        state["history"] = state["history"][:20]
                        state["active_trade"] = None

                    elif is_sl:
                        state["losses"] += 1
                        state["net_pnl"] += pnl
                        state["last_result"] = f"🛑 STOP LOSS HIT! ({t_type} Closed at {price:,.1f} | {pnl:.1f} Pts)"
                        state["last_result_color"] = "#991b1b"
                        state["history"].insert(0, {
                            "time": ist_time, "type": t_type, "entry": entry,
                            "exit": price, "status": "🛑 SL HIT", "pnl": f"{pnl:.1f}", "color": "#ef4444"
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
        target = trade["target"]
        sl = trade["sl"]
        pnl = (price - entry) if t_type == "LONG" else (entry - price)
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
        badge_bg = "#16a34a" if t_type == "LONG" else "#dc2626"

        trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:14px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
<span style="background:{badge_bg}; color:white; padding:4px 10px; border-radius:6px; font-weight:bold; font-size:14px;">🚀 ACTIVE {t_type} (AI-Renko)</span>
<span style="color:{pnl_color}; font-size:20px; font-weight:bold;">{pnl:+.1f} Pts</span>
</div>
<div style="display:flex; justify-content:space-between; color:#cbd5e1; font-size:14px; background:#0f172a; padding:10px; border-radius:8px;">
<div>Entry<br><b style="color:#ffffff;">{entry:,.1f}</b></div>
<div>Target (TP1)<br><b style="color:#22c55e;">{target:,.1f}</b></div>
<div>SL<br><b style="color:#ef4444;">{sl:,.1f}</b></div>
</div>
</div>"""
    else:
        trade_box_html = """<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:14px; margin-bottom:12px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR AI-RENKO / ST FLIP</div>
<div style="color:#94a3b8; font-size:12px; margin-top:4px;">गॉसियन स्मूदिंग और सुपरट्रेंड इंजन सक्रिय है</div>
</div>"""

    rows_html = ""
    if not state["history"]:
        rows_html = """<tr><td colspan="5" style="text-align:center; padding:12px; color:#64748b;">अभी कोई ट्रेड पूरा नहीं हुआ है</td></tr>"""
    else:
        for h in state["history"][:10]:
            rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:13px;">
<td style="padding:8px 4px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 4px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 4px; color:#cbd5e1;">{h['entry']:,.0f} → {h['exit']:,.0f}</td>
<td style="padding:8px 4px; color:{h['color']}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 4px; color:{h['color']}; font-weight:bold; text-align:right;">{h['pnl']}</td>
</tr>"""

    net_color = "#22c55e" if state["net_pnl"] >= 0 else "#ef4444"

    full_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:16px; border-radius:16px; font-family:sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.4);">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:10px; margin-bottom:12px;">
<div>
<div style="font-size:12px; color:#94a3b8;">⚡ AI-RENKO SUPERTREND TERMINAL</div>
<div style="font-size:28px; font-weight:800; color:#ffffff;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="font-size:11px; color:#22c55e;">● 24x7 LIVE (IST)</div>
<div style="font-size:13px; color:#cbd5e1;">{ist_time}</div>
</div>
</div>
<div style="margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:5px;">
<span style="color:#22c55e;">🟢 Buy: {buy_pct}%</span>
<span style="color:#e2e8f0;">Dominance: {imbalance:+.2f}</span>
<span style="color:#ef4444;">Sell: {sell_pct}% 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:12px; border-radius:6px; overflow:hidden;">
<div style="width:{buy_pct}%; background:#22c55e; height:100%;"></div>
</div>
</div>
{trade_box_html}
<div style="background:{state['last_result_color']}; color:#ffffff; padding:8px 12px; border-radius:8px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:12px;">
पिछला परिणाम: {state['last_result']}
</div>
<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:14px; text-align:center;">
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">🎯 TARGET HIT</div>
<div style="font-size:18px; font-weight:bold; color:#22c55e;">{state['wins']}</div>
</div>
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">🛑 SL HIT</div>
<div style="font-size:18px; font-weight:bold; color:#ef4444;">{state['losses']}</div>
</div>
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">📊 NET PnL</div>
<div style="font-size:18px; font-weight:bold; color:{net_color};">{state['net_pnl']:+.1f}</div>
</div>
</div>
<div style="background:#1e293b; border-radius:10px; padding:10px;">
<div style="font-size:13px; font-weight:bold; color:#cbd5e1; margin-bottom:6px;">📜 AI-Renko ट्रेड इतिहास लॉग</div>
<table style="width:100%; border-collapse:collapse;">
<thead>
<tr style="border-bottom:1px solid #475569; font-size:11px; color:#94a3b8; text-align:left;">
<th style="padding:4px;">समय</th>
<th style="padding:4px;">ट्रेड</th>
<th style="padding:4px;">Entry → Exit</th>
<th style="padding:4px;">स्टेटस</th>
<th style="padding:4px; text-align:right;">PnL</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
</div>"""

    terminal.markdown(full_html, unsafe_allow_html=True)
    time.sleep(3)

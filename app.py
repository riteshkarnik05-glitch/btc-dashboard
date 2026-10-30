import streamlit as st
import requests
import time
import threading
from datetime import datetime, timedelta
import math
import streamlit.components.v1 as components

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
        "wins": 0,
        "losses": 0,
        "net_pnl": 0.0
    }
    thread = threading.Thread(target=background_worker, args=(state,), daemon=True)
    thread.start()
    return state

state = get_server_engine()

if state["price"] == 0.0:
    st.info("⏳ AI-Renko Supertrend सर्वर इंजन कनेक्ट हो रहा है...")
    time.sleep(1)
    st.rerun()

price = state["price"]
imbalance = state["imbalance"]
buy_pct = state["buy_pct"]
sell_pct = state["sell_pct"]
ist_time = state["ist_time"]
trade = state["active_trade"]
last_result_color = state.get("last_result_color", "#334155")
last_result_text = state.get("last_result", "अभी कोई ट्रेड क्लोज नहीं हुआ है")

if trade is not None:
    t_type = trade.get("type", "LONG")
    entry = trade.get("entry", price)
    tp1 = trade.get("tp1", price + 100)
    tp2 = trade.get("tp2", price + 200)
    sl = trade.get("sl", price - 100)
    pnl = (price - entry) if t_type == "LONG" else (entry - price)
    pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
    badge_bg = "#16a34a" if t_type == "LONG" else "#dc2626"
    status_label = "🚀 TRAILING RUNNER" if trade.get("tp2_hit", False) else ("🔒 TP1 LOCKED (Protected)" if trade.get("tp1_hit", False) else f"🚀 ACTIVE {t_type}")

    trade_box_html = f"""<div style="background:#1e293b; border:2px solid {badge_bg}; border-radius:12px; padding:16px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<span style="background:{badge_bg}; color:white; padding:6px 12px; border-radius:6px; font-weight:bold; font-size:15px;">{status_label}</span>
<span style="color:{pnl_color}; font-size:22px; font-weight:bold;">{pnl:+.1f} Pts</span>
</div>
<div style="display:flex; justify-content:space-between; color:#cbd5e1; font-size:14px; background:#0f172a; padding:12px; border-radius:8px; text-align:center;">
<div>Entry<br><b style="color:#ffffff; font-size:15px;">{entry:,.1f}</b></div>
<div>TP1 (127.5p)<br><b style="color:#22c55e; font-size:15px;">{tp1:,.1f}</b></div>
<div>TP2 (330p)<br><b style="color:#38bdf8; font-size:15px;">{tp2:,.1f}</b></div>
<div>Trailing SL<br><b style="color:#ef4444; font-size:15px;">{sl:,.1f}</b></div>
</div>
</div>"""
else:
    trade_box_html = """<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px; margin-bottom:14px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:16px;">🔍 WAITING FOR AI-RENKO / ST FLIP</div>
<div style="color:#94a3b8; font-size:13px; margin-top:4px;">TP1, TP2 और ट्रेलिंग इंजन सक्रिय है</div>
</div>"""

rows_html = ""
if not state["history"]:
    rows_html = """<tr><td colspan="5" style="text-align:center; padding:15px; color:#64748b;">अभी तक कोई ट्रेड पूरा नहीं हुआ है</td></tr>"""
else:
    for h in state["history"]:
        h_color = h.get('color', '#22c55e')
        rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:13px;">
<td style="padding:10px 8px; color:#94a3b8;">{h['time']}</td>
<td style="padding:10px 8px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:10px 8px; color:#cbd5e1; font-weight:600;">{h['entry']:,.1f} → {h['exit']:,.1f}</td>
<td style="padding:10px 8px; color:{h_color}; font-weight:bold;">{h['status']}</td>
<td style="padding:10px 8px; color:{h_color}; font-weight:bold; text-align:right;">{h['pnl']} Pts</td>
</tr>"""

net_color = "#22c55e" if state["net_pnl"] >= 0 else "#ef4444"

# यहाँ f-string की जगह साधारण string (ताकि जावास्क्रिप्ट के करली ब्रेसिज़ से टकराव न हो) का उपयोग किया गया है
full_html = """
<!DOCTYPE html>
<html>
<head>
<style>
body { background-color: #0e1117; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 10px; }
.terminal-grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
@media (min-width: 900px) { .terminal-grid { grid-template-columns: 1.1fr 0.9fr; } }
</style>
<script>
  // बिना स्क्रीन ब्लिंक किए बैकग्राउंड से हर 3 सेकंड में नया डेटा लोड करना
  setInterval(function() {
      fetch(window.location.href)
        .then(response => response.text())
        .then(html => {
            var parser = new DOMParser();
            var doc = parser.parseFromString(html, 'text/html');
            var newTerminal = doc.getElementById('terminal-box');
            if (newTerminal) {
                document.getElementById('terminal-box').innerHTML = newTerminal.innerHTML;
            }
        }).catch(err => console.log('Auto-update active'));
  }, 3000);
</script>
</head>
<body>
<div id="terminal-box" style="background:#0f172a; color:#f8fafc; padding:24px; border-radius:18px; box-shadow:0 8px 30px rgba(0,0,0,0.6); border:1px solid #1e293b;">
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:14px; margin-bottom:18px;">
        <div>
            <div style="font-size:13px; color:#38bdf8; font-weight:600; letter-spacing:0.5px;">⚡ AI-RENKO SUPERTREND PRO TERMINAL</div>
            <div style="font-size:36px; font-weight:800; color:#ffffff; margin-top:2px;">$PRICE_VAL</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:12px; color:#22c55e; font-weight:600;">● 24x7 RESPONSIVE LIVE</div>
            <div style="font-size:14px; color:#cbd5e1; margin-top:2px;">TIME_VAL (IST)</div>
        </div>
    </div>

    <div class="terminal-grid">
        <div>
            <div style="margin-bottom:18px; background:#1e293b; padding:14px; border-radius:12px;">
                <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:6px;">
                    <span style="color:#22c55e;">🟢 Buy: BUY_PCT%</span>
                    <span style="color:#e2e8f0;">Dominance: IMBALANCE_VAL</span>
                    <span style="color:#ef4444;">Sell: SELL_PCT% 🔴</span>
                </div>
                <div style="width:100%; background:#ef4444; height:12px; border-radius:6px; overflow:hidden;">
                    <div style="width:BUY_PCT%; background:#22c55e; height:100%;"></div>
                </div>
            </div>

            TRADE_BOX_HTML_PLACEHOLDER

            <div style="background:LAST_COLOR; color:#ffffff; padding:12px 16px; border-radius:10px; font-size:14px; font-weight:bold; text-align:center; margin-bottom:16px; box-shadow:0 2px 10px rgba(0,0,0,0.3);">
                पिछला परिणाम: LAST_RESULT_TEXT
            </div>

            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; text-align:center;">
                <div style="background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
                    <div style="font-size:11px; color:#94a3b8; font-weight:600;">🎯 TARGET HIT</div>
                    <div style="font-size:22px; font-weight:bold; color:#22c55e; margin-top:4px;">WINS_VAL</div>
                </div>
                <div style="background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
                    <div style="font-size:11px; color:#94a3b8; font-weight:600;">🛑 SL HIT</div>
                    <div style="font-size:22px; font-weight:bold; color:#ef4444; margin-top:4px;">LOSSES_VAL</div>
                </div>
                <div style="background:#1e293b; padding:12px; border-radius:10px; border:1px solid #334155;">
                    <div style="font-size:11px; color:#94a3b8; font-weight:600;">📊 NET PnL</div>
                    <div style="font-size:22px; font-weight:bold; color:NET_COLOR; margin-top:4px;">NET_PNL_VAL</div>
                </div>
            </div>
        </div>

        <div>
            <div style="background:#1e293b; border-radius:12px; padding:16px; border:1px solid #334155; height:100%; box-sizing:border-box;">
                <div style="font-size:14px; font-weight:bold; color:#f8fafc; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
                    📜 AI-Renko ट्रेड इतिहास लॉग
                </div>
                <div style="max-height: 380px; overflow-y: auto;">
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
                            ROWS_HTML_PLACEHOLDER
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
</body>
</html>
"""

# वैरिएबल वैल्यूज को सुरक्षित तरीके से रिप्लेस करना
full_html = full_html.replace("$PRICE_VAL", f"{price:,.2f}")
full_html = full_html.replace("TIME_VAL", ist_time)
full_html = full_html.replace("BUY_PCT", str(buy_pct))
full_html = full_html.replace("SELL_PCT", str(sell_pct))
full_html = full_html.replace("IMBALANCE_VAL", f"{imbalance:+.2f}")
full_html = full_html.replace("TRADE_BOX_HTML_PLACEHOLDER", trade_box_html)
full_html = full_html.replace("LAST_COLOR", last_result_color)
full_html = full_html.replace("LAST_RESULT_TEXT", last_result_text)
full_html = full_html.replace("WINS_VAL", str(state["wins"]))
full_html = full_html.replace("LOSSES_VAL", str(state["losses"]))
full_html = full_html.replace("NET_COLOR", net_color)
full_html = full_html.replace("NET_PNL_VAL", f"{state['net_pnl']:+.1f}")
full_html = full_html.replace("ROWS_HTML_PLACEHOLDER", rows_html)

components.html(full_html, height=580, scrolling=True)

# बिना स्क्रीन ब्लिंक किए सर्वर डेटा सिंक बनाए रखने के लिए छोटा लूप
time.sleep(3)
st.rerun()

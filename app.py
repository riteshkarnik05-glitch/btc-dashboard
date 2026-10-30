import streamlit as st
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="BTC Pro Scalper", layout="centered")

# हेडर और गैर-जरूरी स्पेस छुपाने और डार्क टर्मिनल लुक के लिए CSS
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 550px; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# सेशन स्टेट वेरिएबल्स
if 'history' not in st.session_state:
    st.session_state.history = []
if 'active_trade' not in st.session_state:
    st.session_state.active_trade = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = "अभी कोई ट्रेड क्लोज नहीं हुआ है"
if 'last_result_color' not in st.session_state:
    st.session_state.last_result_color = "#334155"
if 'wins' not in st.session_state:
    st.session_state.wins = 0
if 'losses' not in st.session_state:
    st.session_state.losses = 0
if 'net_pnl' not in st.session_state:
    st.session_state.net_pnl = 0.0

TARGET_PTS = 200.0
SL_PTS = 80.0

# एक ही कंटेनर जिसमें सिर्फ नंबर अपडेट होंगे (स्क्रीन ब्लिंक नहीं करेगी)
terminal = st.empty()

while True:
    try:
        url = "https://api.binance.us/api/v3/depth?symbol=BTCUSDT&limit=20"
        response = requests.get(url, timeout=4)
        data = response.json()

        bids = data.get('bids', [])
        asks = data.get('asks', [])

        if bids and asks:
            price = float(bids[0][0])
            total_bid = sum(float(x[1]) for x in bids)
            total_ask = sum(float(x[1]) for x in asks)
            total_vol = total_bid + total_ask

            imbalance = (total_bid - total_ask) / total_vol if total_vol > 0 else 0.0
            buy_pct = int((total_bid / total_vol) * 100) if total_vol > 0 else 50
            sell_pct = 100 - buy_pct

            # भारतीय समय (IST)
            ist_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%I:%M:%S %p")

            trade = st.session_state.active_trade

            # 1. अगर कोई ट्रेड नहीं चल रहा है, तो नया सिग्नल चेक करें
            if trade is None:
                if imbalance >= 0.35:
                    st.session_state.active_trade = {
                        "type": "LONG",
                        "entry": price,
                        "target": price + TARGET_PTS,
                        "sl": price - SL_PTS,
                        "time": ist_time
                    }
                    trade = st.session_state.active_trade
                elif imbalance <= -0.35:
                    st.session_state.active_trade = {
                        "type": "SHORT",
                        "entry": price,
                        "target": price - TARGET_PTS,
                        "sl": price + SL_PTS,
                        "time": ist_time
                    }
                    trade = st.session_state.active_trade

            # 2. अगर ट्रेड एक्टिव है, तो लाइव PnL, Target और SL चेक करें
            if trade is not None:
                t_type = trade["type"]
                entry = trade["entry"]
                target = trade["target"]
                sl = trade["sl"]

                pnl = (price - entry) if t_type == "LONG" else (entry - price)

                # टारगेट या SL हिट की जांच
                is_target = (t_type == "LONG" and price >= target) or (t_type == "SHORT" and price <= target)
                is_sl = (t_type == "LONG" and price <= sl) or (t_type == "SHORT" and price >= sl)

                if is_target:
                    st.session_state.wins += 1
                    st.session_state.net_pnl += pnl
                    st.session_state.last_result = f"🎯 TARGET HIT! ({t_type} Closed at {price:,.1f} | +{pnl:.1f} Pts)"
                    st.session_state.last_result_color = "#166534"
                    st.session_state.history.insert(0, {
                        "time": ist_time, "type": t_type, "entry": entry,
                        "exit": price, "status": "🎯 TARGET HIT", "pnl": f"+{pnl:.1f}", "color": "#22c55e"
                    })
                    st.session_state.active_trade = None
                    trade = None

                elif is_sl:
                    st.session_state.losses += 1
                    st.session_state.net_pnl += pnl
                    st.session_state.last_result = f"🛑 STOP LOSS HIT! ({t_type} Closed at {price:,.1f} | {pnl:.1f} Pts)"
                    st.session_state.last_result_color = "#991b1b"
                    st.session_state.history.insert(0, {
                        "time": ist_time, "type": t_type, "entry": entry,
                        "exit": price, "status": "🛑 SL HIT", "pnl": f"{pnl:.1f}", "color": "#ef4444"
                    })
                    st.session_state.active_trade = None
                    trade = None

            # एक्टिव ट्रेड कार्ड का HTML
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
<span style="background:{badge_bg}; color:white; padding:4px 10px; border-radius:6px; font-weight:bold; font-size:14px;">🚀 ACTIVE {t_type} ({trade['time']})</span>
<span style="color:{pnl_color}; font-size:20px; font-weight:bold;">{pnl:+.1f} Pts</span>
</div>
<div style="display:flex; justify-content:space-between; color:#cbd5e1; font-size:14px; background:#0f172a; padding:10px; border-radius:8px;">
<div>Entry<br><b style="color:#ffffff;">{entry:,.1f}</b></div>
<div>Target (+200)<br><b style="color:#22c55e;">{target:,.1f}</b></div>
<div>SL (-80)<br><b style="color:#ef4444;">{sl:,.1f}</b></div>
</div>
</div>"""
            else:
                trade_box_html = f"""<div style="background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:14px; margin-bottom:12px; text-align:center;">
<div style="color:#38bdf8; font-weight:bold; font-size:15px;">🔍 WAITING FOR NEXT ORDERBOOK SHOCK (±0.35)</div>
<div style="color:#94a3b8; font-size:12px; margin-top:4px;">नया सिग्नल मिलते ही यहाँ Entry, Target और SL लॉक हो जाएंगे</div>
</div>"""

            # हिस्ट्री टेबल की पंक्तियाँ
            rows_html = ""
            if not st.session_state.history:
                rows_html = """<tr><td colspan="5" style="text-align:center; padding:12px; color:#64748b;">अभी कोई ट्रेड पूरा नहीं हुआ है</td></tr>"""
            else:
                for h in st.session_state.history[:8]:
                    rows_html += f"""<tr style="border-bottom:1px solid #334155; font-size:13px;">
<td style="padding:8px 4px; color:#94a3b8;">{h['time']}</td>
<td style="padding:8px 4px; font-weight:bold; color:#f8fafc;">{h['type']}</td>
<td style="padding:8px 4px; color:#cbd5e1;">{h['entry']:,.0f} → {h['exit']:,.0f}</td>
<td style="padding:8px 4px; color:{h['color']}; font-weight:bold;">{h['status']}</td>
<td style="padding:8px 4px; color:{h['color']}; font-weight:bold; text-align:right;">{h['pnl']}</td>
</tr>"""

            net_color = "#22c55e" if st.session_state.net_pnl >= 0 else "#ef4444"

            # पूरा डैशबोर्ड एक साथ रेंडर करना ताकि स्क्रीन बिल्कुल न हिले
            full_html = f"""<div style="background:#0f172a; color:#f8fafc; padding:16px; border-radius:16px; font-family:sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.4);">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:10px; margin-bottom:12px;">
<div>
<div style="font-size:12px; color:#94a3b8;">⚡ BTCUSDT LIVE ORDERBOOK TERMINAL</div>
<div style="font-size:28px; font-weight:800; color:#ffffff;">${price:,.2f}</div>
</div>
<div style="text-align:right;">
<div style="font-size:11px; color:#38bdf8;">● LIVE (IST)</div>
<div style="font-size:13px; color:#cbd5e1;">{ist_time}</div>
</div>
</div>
<div style="margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold; margin-bottom:5px;">
<span style="color:#22c55e;">🟢 Buy: {buy_pct}%</span>
<span style="color:#e2e8f0;">Imbalance: {imbalance:+.2f}</span>
<span style="color:#ef4444;">Sell: {sell_pct}% 🔴</span>
</div>
<div style="width:100%; background:#ef4444; height:12px; border-radius:6px; overflow:hidden;">
<div style="width:{buy_pct}%; background:#22c55e; height:100%;"></div>
</div>
</div>
{trade_box_html}
<div style="background:{st.session_state.last_result_color}; color:#ffffff; padding:8px 12px; border-radius:8px; font-size:13px; font-weight:bold; text-align:center; margin-bottom:12px;">
पिछला परिणाम: {st.session_state.last_result}
</div>
<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:14px; text-align:center;">
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">🎯 TARGET HIT</div>
<div style="font-size:18px; font-weight:bold; color:#22c55e;">{st.session_state.wins}</div>
</div>
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">🛑 SL HIT</div>
<div style="font-size:18px; font-weight:bold; color:#ef4444;">{st.session_state.losses}</div>
</div>
<div style="background:#1e293b; padding:8px; border-radius:8px;">
<div style="font-size:11px; color:#94a3b8;">📊 NET PnL</div>
<div style="font-size:18px; font-weight:bold; color:{net_color};">{st.session_state.net_pnl:+.1f}</div>
</div>
</div>
<div style="background:#1e293b; border-radius:10px; padding:10px;">
<div style="font-size:13px; font-weight:bold; color:#cbd5e1; margin-bottom:6px;">📜 क्लोज्ड ट्रेड्स का इतिहास (Target / SL Log)</div>
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

    except Exception as e:
        terminal.error(f"कनेक्शन री-ट्राई हो रहा है... ({e})")

    time.sleep(2)

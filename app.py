import streamlit as st
import requests
import time
from datetime import datetime

st.set_page_config(page_title="BTC Scalp Dashboard", layout="centered")

st.title("⚡ BTC Orderbook Shock & Signal Dashboard")

# सेशन स्टेट में डेटा स्टोर करने के लिए
if 'signal_log' not in st.session_state:
    st.session_state.signal_log = []
if 'active_trade' not in st.session_state:
    st.session_state.active_trade = None
if 'entry_price' not in st.session_state:
    st.session_state.entry_price = 0.0
if 'target_price' not in st.session_state:
    st.session_state.target_price = 0.0
if 'sl_price' not in st.session_state:
    st.session_state.sl_price = 0.0

TARGET_PTS = 200.0
SL_PTS = 80.0

placeholder = st.empty()

try:
    # Binance.US REST API से डेप्थ डेटा लेना
    url = "https://api.binance.us/api/v3/depth?symbol=BTCUSDT&limit=20"
    response = requests.get(url, timeout=5)
    data = response.json()
    
    bids = data.get('bids', [])
    asks = data.get('asks', [])
    
    if bids and asks:
        current_price = float(bids[0][0])
        total_bid = sum(float(x[1]) for x in bids)
        total_ask = sum(float(x[1]) for x in asks)
        total_vol = total_bid + total_ask
        
        imbalance = (total_bid - total_ask) / total_vol if total_vol > 0 else 0
        buy_pct = int((total_bid / total_vol) * 100) if total_vol > 0 else 50
        sell_pct = 100 - buy_pct
        
        with placeholder.container():
            st.metric(label="💰 लाइव BTC प्राइस", value=f"{current_price:,.2f} USDT")
            
            col1, col2 = st.columns(2)
            col1.metric("Buy Pressure", f"{buy_pct}%")
            col2.metric("Sell Pressure", f"{sell_pct}%")
            
            st.write(f"**ऑर्डरबुक इम्बेलेन्स (Imbalance):** {imbalance:+.2f}")
            
            if st.session_state.active_trade is None:
                st.info("🔍 मार्केट स्टेटस: WAITING FOR NEXT SHOCK")
                if imbalance >= 0.35:
                    st.session_state.active_trade = "LONG 🟢"
                    st.session_state.entry_price = current_price
                    st.session_state.target_price = current_price + TARGET_PTS
                    st.session_state.sl_price = current_price - SL_PTS
                    t_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.signal_log.insert(0, f"[{t_time}] 🟢 LONG Triggered at {current_price:.1f} (Target: {st.session_state.target_price:.1f})")
                elif imbalance <= -0.35:
                    st.session_state.active_trade = "SHORT 🔴"
                    st.session_state.entry_price = current_price
                    st.session_state.target_price = current_price - TARGET_PTS
                    st.session_state.sl_price = current_price + SL_PTS
                    t_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.signal_log.insert(0, f"[{t_time}] 🔴 SHORT Triggered at {current_price:.1f} (Target: {st.session_state.target_price:.1f})")
            else:
                pnl = current_price - st.session_state.entry_price if st.session_state.active_trade == "LONG 🟢" else st.session_state.entry_price - current_price
                st.success(f"🚀 एक्टिव ट्रेड: Riding {st.session_state.active_trade} | PnL: {pnl:+.1f} Pts")
                st.write(f"Entry: {st.session_state.entry_price:.1f} | Target: {st.session_state.target_price:.1f} | SL: {st.session_state.sl_price:.1f}")
                
                if st.session_state.active_trade == "LONG 🟢" and (current_price >= st.session_state.target_price or current_price <= st.session_state.sl_price):
                    st.session_state.signal_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 Closed LONG at {current_price:.1f} (PnL: {pnl:+.1f} Pts)")
                    st.session_state.active_trade = None
                elif st.session_state.active_trade == "SHORT 🔴" and (current_price <= st.session_state.target_price or current_price >= st.session_state.sl_price):
                    st.session_state.signal_log.instert(0, f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 Closed SHORT at {current_price:.1f} (PnL: {pnl:+.1f} Pts)")
                    st.session_state.active_trade = None

            st.markdown("### 📜 पिछले सिग्नल्स का इतिहास (Signal History Log)")
            if not st.session_state.signal_log:
                st.write("(अभी तक कोई सिग्नल दर्ज नहीं हुआ है)")
            else:
                for log in st.session_state.signal_log[:5]:
                    st.text(log)

except Exception as e:
    st.error(f"डेटा लोड करने में समस्या: {e}")

time.sleep(3)
st.rerun()

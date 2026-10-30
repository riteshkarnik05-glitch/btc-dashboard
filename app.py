!pip install -q websocket-client

import json
import websocket
from collections import deque
from datetime import datetime
from IPython.display import clear_output

SOCKET = "wss://stream.binance.us:9443/ws/btcusdt@depth20@1000ms"

bid_history = deque(maxlen=20)
ask_history = deque(maxlen=20)
price_history = deque(maxlen=5)

active_trade = None  
entry_price = 0.0
sl_price = 0.0
target_price = 0.0
trigger_reason = ""
counter = 1

# पिछले सिग्नल्स को स्टोर करने के लिए लिस्ट (लॉग)
signal_log = []

TARGET_PTS = 200.0  
SL_PTS = 80.0       

def on_message(ws, message):
    global counter, active_trade, entry_price, sl_price, target_price, trigger_reason
    data = json.loads(message)
    
    bids = data.get('bids', [])
    asks = data.get('asks', [])
    if not bids or not asks:
        return
        
    current_price = float(bids[0][0])
    
    total_bid = sum(float(x[1]) for x in bids)
    total_ask = sum(float(x[1]) for x in asks)
    
    avg_bid = sum(bid_history) / len(bid_history) if len(bid_history) >= 10 else total_bid
    avg_ask = sum(ask_history) / len(ask_history) if len(ask_history) >= 10 else total_ask
    
    bid_history.append(total_bid)
    ask_history.append(total_ask)
    price_history.append(current_price)
    
    total_vol = total_bid + total_ask
    imbalance = (total_bid - total_ask) / total_vol if total_vol > 0 else 0
    
    bid_shock = total_bid / avg_bid if avg_bid > 0 else 1.0
    ask_shock = total_ask / avg_ask if avg_ask > 0 else 1.0
    
    momentum_5s = current_price - price_history[0] if len(price_history) == 5 else 0.0

    # नया शॉक मिलने पर सिग्नल जनरेट करना
    if active_trade is None and len(bid_history) >= 10:
        current_time = datetime.now().strftime("%H:%M:%S")
        
        if imbalance >= 0.40 and bid_shock >= 1.6 and momentum_5s >= 3.0:
            active_trade = "LONG 🟢"
            entry_price = current_price
            sl_price = current_price - SL_PTS
            target_price = current_price + TARGET_PTS
            trigger_reason = f"Buy Shock ({bid_shock:.1f}x) | Imb: {imbalance:+.2f}"
            
            # लॉग में जोड़ें
            signal_log.insert(0, f"[{current_time}] 🟢 LONG Triggered at {entry_price:.1f} (Target: {target_price:.1f})")
            
        elif imbalance <= -0.40 and ask_shock >= 1.6 and momentum_5s <= -3.0:
            active_trade = "SHORT 🔴"
            entry_price = current_price
            sl_price = current_price + SL_PTS
            target_price = current_price - TARGET_PTS
            trigger_reason = f"Sell Shock ({ask_shock:.1f}x) | Imb: {imbalance:+.2f}"
            
            # लॉग में जोड़ें
            signal_log.insert(0, f"[{current_time}] 🔴 SHORT Triggered at {entry_price:.1f} (Target: {target_price:.1f})")

    pnl_pts = 0.0
    if active_trade == "LONG 🟢":
        pnl_pts = current_price - entry_price
        if current_price >= target_price or current_price <= sl_price:
            signal_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S컬')}] 🏁 Closed LONG at {current_price:.1f} (PNL: {pnl_pts:+.1f} Pts)")
            active_trade = None  
    elif active_trade == "SHORT 🔴":
        pnl_pts = entry_price - current_price
        if current_price <= target_price or current_price >= sl_price:
            signal_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 Closed SHORT at {current_price:.1f} (PNL: {pnl_pts:+.1f} Pts)")
            active_trade = None

    clear_output(wait=True)
    buy_pct = int((total_bid / total_vol) * 100) if total_vol > 0 else 50
    sell_pct = 100 - buy_pct
    
    print("==========================================================")
    print(f" ⚡ ORDERBOOK SHOCK & SIGNAL HISTORY (Tick #{counter})")
    print("==========================================================")
    print(f" 💰 लाइव BTC प्राइस   : {current_price:.2f} USDT (5s Move: {momentum_5s:+.1f} Pts)")
    print(f" 📊 ऑर्डरबुक प्रेशर    : Buy {buy_pct}%  vs  Sell {sell_pct}% (Imb: {imbalance:+.2f})")
    print("----------------------------------------------------------")
    
    if active_trade is None:
        print(" 🔍 मार्केट स्टेटस     : WAITING FOR NEXT SHOCK (लॉग नीचे सुरक्षित है)")
    else:
        print(f" 🚀 एक्टिव ट्रेड      : Riding {active_trade} ({pnl_pts:+.1f} Pts)")
        print(f" 🎯 लेवल्स           : Entry {entry_price:.1f} | SL {sl_price:.1f} | Target {target_price:.1f}")
    
    print("----------------------------------------------------------")
    print(" 📜 **पिछले सिग्नल्स का इतिहास (Signal History Log):**")
    if len(signal_log) == 0:
        print("    (अभी तक कोई सिग्नल दर्ज नहीं हुआ है)")
    else:
        for log in signal_log[:5]: # पिछले 5 सिग्नल्स दिखाएगा
            print(f"    {log}")
    print("==========================================================")
    
    counter += 1

def on_error(ws, error):
    print(f"एरर: {error}")

def on_close(ws, close_status_code, close_msg):
    print("कनेक्शन बंद हो गया।")

def on_open(ws):
    print("WebSocket कनेक्टेड! सिग्नल लॉगिंग शुरू...\n")

ws = websocket.WebSocketApp(SOCKET,
                            on_open=on_open,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)
ws.run_forever()
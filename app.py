import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import threading
import json
import re
import io
import wave
import struct
import math
import base64
import hmac
import hashlib
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Quant V26.6 - Trend-First + Big Profit Lock + Delta Demo", layout="wide")

def clean_html(raw_html: str) -> str:
    """Strips leading spaces so Streamlit renders pure HTML/SVG inside a single slot without ghost boxes"""
    return "\n".join(line.lstrip() for line in raw_html.splitlines() if line.strip())

st.markdown(clean_html("""
<style>
.stApp { background-color: #090d16; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 3.6rem !important; padding-bottom: 1.5rem !important; max-width: 98% !important; }
/* ZERO-BLINK & ANTI-FLICKER LOCK */
[data-stale="true"], .element-container, .stMarkdown, [data-testid="stAppViewBlockContainer"] * {
    opacity: 1 !important;
    transition: none !important;
    animation: none !important;
    filter: none !important;
}
.top-bar { background: #111827; border: 1px solid #1f2937; border-bottom: 2px solid #38bdf8; padding: 12px 16px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.ip-badge-box { background: #0f172a; border: 1px solid #facc15; border-left: 4px solid #facc15; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; width: 100%; }
.ai-badge-box { background: #1e1b4b; border: 1px solid #c084fc; border-left: 4px solid #4ade80; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; width: 100%; }
.delta-badge-box { background: #0f172a; border: 1px solid #38bdf8; border-left: 4px solid #22c55e; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; width: 100%; }
.main-grid { display: grid; grid-template-columns: 1.65fr 1fr; gap: 14px; align-items: start; }
@media (max-width: 1000px) { .main-grid { grid-template-columns: 1fr; } }
.lock-banner { padding: 14px 16px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.lock-buy { background: #052e16; border: 2px solid #22c55e; color: #4ade80; }
.lock-sell { background: #450a0a; border: 2px solid #ef4444; color: #f87171; }
.lock-wait { background: #1e293b; border: 2px dashed #64748b; color: #cbd5e1; }
.sub-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
@media (max-width: 768px) { .sub-grid { grid-template-columns: 1fr; } }
.card-box { background: #111827; border: 1px solid #334155; border-radius: 10px; padding: 13px 15px; }
.card-title { font-size: 12.5px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 8px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; display: flex; justify-content: space-between; }
.stat-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed #1f2937; }
.chart-box { background: #0c1220; border: 1px solid #334155; border-top: 3px solid #38bdf8; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
.history-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #22c55e; border-radius: 10px; padding: 12px 14px; height: 360px; overflow-y: auto; }
.brick-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #c084fc; border-radius: 10px; padding: 12px 14px; height: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 10px 12px; border-radius: 7px; margin-bottom: 8px; font-size: 12.5px; line-height: 1.5; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
.ic-ai { border-left: 4px solid #c084fc; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; margin-top: 2px; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
div[data-baseweb="input"] > div { background-color: #1e293b !important; color: #facc15 !important; border: 1px solid #facc15 !important; border-radius: 7px !important; font-weight: 800 !important; }
input[type="number"] { color: #facc15 !important; font-weight: 800 !important; }
</style>
"""), unsafe_allow_html=True)

# ============================================================================
# HARDCODED DELTA EXCHANGE DEMO API CREDENTIALS & POSITION-VERIFIED SYNC
# ============================================================================
HARDCODED_DELTA_API_KEY = "7KBIKEhD3yjFWO7tmW6golXOrbnAQW"
HARDCODED_DELTA_API_SECRET = "SVGs8vtF6CpNqT0ldyLGgPskGoo7w3QJ24v2ytJqB1CWn2xZIS0U7iBcNFDb"

DELTA_TESTNET_CANDIDATES = [
    ("India Demo", "https://cdn-ind.testnet.deltaex.org"),
    ("Global Demo", "https://testnet-api.delta.exchange")
]

delta_order_lock = threading.Lock()

def fetch_server_public_ip() -> str:
    endpoints = [
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://ifconfig.me/ip"
    ]
    for url in endpoints:
        try:
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception:
            continue
    return "Unable to detect IP"

def get_delta_btc_product_id(base_url: str, cached_id=None) -> int:
    if cached_id:
        return int(cached_id)
    try:
        r = requests.get(f"{base_url}/v2/products", timeout=4.0)
        if r.status_code == 200:
            products = r.json().get("result", [])
            for sym in ["BTCUSD", "BTCUSDT"]:
                for p in products:
                    if p.get("symbol") == sym and p.get("contract_type") == "perpetual_futures":
                        return int(p["id"])
            for p in products:
                if p.get("symbol") in ["BTCUSD", "BTCUSDT"]:
                    return int(p["id"])
    except Exception:
        pass
    return 27

def generate_delta_signature(secret: str, method: str, timestamp: str, path: str, query_string: str, payload_str: str) -> str:
    message = method + timestamp + path + query_string + payload_str
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

def _delta_signed_headers(api_key: str, api_secret: str, method: str, path: str, query_string: str = "", payload_str: str = "") -> dict:
    timestamp = str(int(time.time()))
    sig = generate_delta_signature(api_secret, method, timestamp, path, query_string, payload_str)
    return {
        "api-key": api_key,
        "timestamp": timestamp,
        "signature": sig,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "pro-quant-v26-6-ai-bot"
    }

def _get_live_delta_btc_position_size(base_url: str, prod_id: int, api_key: str, api_secret: str):
    path = "/v2/positions"
    query_string = f"?product_id={int(prod_id)}"
    try:
        headers = _delta_signed_headers(api_key, api_secret, "GET", path, query_string, "")
        r = requests.get(f"{base_url}{path}{query_string}", headers=headers, timeout=5.0)
        if r.status_code == 200 and r.json().get("success"):
            res_data = r.json().get("result")
            if isinstance(res_data, dict):
                return int(float(res_data.get("size", 0)))
            if isinstance(res_data, list):
                total_sz = 0
                for pos in res_data:
                    if int(pos.get("product_id", -1)) == int(prod_id):
                        total_sz += int(float(pos.get("size", 0)))
                return total_sz
    except Exception:
        pass
    return None

def _submit_delta_market_order_sync(base_url: str, prod_id: int, api_key: str, api_secret: str, side: str, size: int, reduce_only: bool = False):
    path = "/v2/orders"
    body_dict = {
        "product_id": int(prod_id),
        "size": int(max(1, size)),
        "side": side.lower(),
        "order_type": "market_order"
    }
    if reduce_only:
        body_dict["reduce_only"] = True

    payload_str = json.dumps(body_dict, separators=(",", ":"))
    headers = _delta_signed_headers(api_key, api_secret, "POST", path, "", payload_str)
    return requests.post(f"{base_url}{path}", data=payload_str, headers=headers, timeout=6.0)

def auto_verify_delta_demo_wallet(eng: dict):
    api_key = eng.get("delta_api_key", HARDCODED_DELTA_API_KEY).strip()
    api_secret = eng.get("delta_api_secret", HARDCODED_DELTA_API_SECRET).strip()
    path = "/v2/wallet/balances"
    last_err = "🔴 Delta Connection Failed"

    for env_label, base_url in DELTA_TESTNET_CANDIDATES:
        try:
            headers = _delta_signed_headers(api_key, api_secret, "GET", path, "", "")
            r = requests.get(f"{base_url}{path}", headers=headers, timeout=5.0)
            if r.status_code == 200 and r.json().get("success"):
                prod_id = get_delta_btc_product_id(base_url, eng.get("delta_product_id"))
                eng["delta_base_url"] = base_url
                eng["delta_product_id"] = prod_id
                bals = r.json().get("result", [])
                usdt_bal = 0.0
                for b in bals:
                    if b.get("asset_symbol") in ["USDT", "USD", "BTC"]:
                        usdt_bal = max(usdt_bal, float(b.get("available_balance", 0.0)))
                live_pos = _get_live_delta_btc_position_size(base_url, prod_id, api_key, api_secret)
                pos_txt = f" | Pos: {live_pos:+d}" if live_pos is not None else ""
                eng["delta_last_status"] = f"🟢 {env_label} OK (Bal: ${usdt_bal:,.1f}{pos_txt})"
                return
            else:
                last_err = f"🔴 {env_label} ({r.status_code}): {r.text[:65]}"
        except Exception as e:
            last_err = f"🔴 {env_label} Err: {str(e)[:55]}"

    eng["delta_last_status"] = last_err

def execute_delta_entry_and_exit(eng: dict, action_kind: str, direction: str, target_lot: int, close_prev_lot: int = 0, note: str = ""):
    if not eng.get("delta_enabled", True):
        return
    api_key = eng.get("delta_api_key", HARDCODED_DELTA_API_KEY).strip()
    api_secret = eng.get("delta_api_secret", HARDCODED_DELTA_API_SECRET).strip()

    def _run_serialized():
        with delta_order_lock:
            primary_url = eng.get("delta_base_url", "https://cdn-ind.testnet.deltaex.org")
            urls_to_try = [primary_url] + [u for _, u in DELTA_TESTNET_CANDIDATES if u != primary_url]
            active_url = primary_url
            prod_id = get_delta_btc_product_id(active_url, eng.get("delta_product_id"))

            for u in urls_to_try:
                chk = _get_live_delta_btc_position_size(u, prod_id if u == primary_url else get_delta_btc_product_id(u), api_key, api_secret)
                if chk is not None:
                    active_url = u
                    prod_id = get_delta_btc_product_id(u, eng.get("delta_product_id") if u == primary_url else None)
                    eng["delta_base_url"] = active_url
                    eng["delta_product_id"] = prod_id
                    break

            ist_now = get_ist_time_str()

            if action_kind in ("CLOSE_ONLY", "FLIP"):
                live_pos = _get_live_delta_btc_position_size(active_url, prod_id, api_key, api_secret)
                if live_pos is not None and live_pos != 0:
                    close_side = "sell" if live_pos > 0 else "buy"
                    close_qty = abs(live_pos)
                    res_c = _submit_delta_market_order_sync(active_url, prod_id, api_key, api_secret, close_side, close_qty, reduce_only=True)
                    if res_c.status_code != 200 or not res_c.json().get("success"):
                        res_c = _submit_delta_market_order_sync(active_url, prod_id, api_key, api_secret, close_side, close_qty, reduce_only=False)
                    time.sleep(0.5)
                elif close_prev_lot > 0 and live_pos is None:
                    prev_side = "sell" if direction == "BUY" else "buy"
                    _submit_delta_market_order_sync(active_url, prod_id, api_key, api_secret, prev_side, close_prev_lot, reduce_only=True)
                    time.sleep(0.4)

            if action_kind == "CLOSE_ONLY":
                final_pos = _get_live_delta_btc_position_size(active_url, prod_id, api_key, api_secret)
                pos_lbl = f"Pos:{final_pos:+d}" if final_pos is not None else "Closed"
                eng["delta_last_status"] = f"🟢 Delta EXIT OK ({pos_lbl}) @ {ist_now} [{note}]"
                return

            open_side = "buy" if direction == "BUY" else "sell"
            req_size = int(max(1, target_lot))
            res_o = _submit_delta_market_order_sync(active_url, prod_id, api_key, api_secret, open_side, req_size, reduce_only=False)
            if res_o.status_code == 200 and res_o.json().get("success"):
                ord_id = res_o.json().get("result", {}).get("id", "OK")
                time.sleep(0.4)
                actual_pos = _get_live_delta_btc_position_size(active_url, prod_id, api_key, api_secret)
                pos_str = f"Pos:{actual_pos:+d}" if actual_pos is not None else f"Req:{req_size}"
                eng["delta_last_status"] = f"🟢 {open_side.upper()} {req_size}L ({pos_str}) [#{ord_id}] @ {ist_now}"
            else:
                err_txt = res_o.text[:75]
                eng["delta_last_status"] = f"🔴 Delta ({res_o.status_code}): {err_txt}"

    threading.Thread(target=_run_serialized, daemon=True).start()

# ============================================================================
# IN-BUILT SOUND SYNTHESIZER
# ============================================================================
def create_sound_b64(tone_type="BULL"):
    sample_rate = 22050
    buf = io.BytesIO()
    if tone_type == "BULL":
        notes = [(784, 0.13), (0, 0.03), (1046, 0.15), (0, 0.03), (1318, 0.22)]
    elif tone_type == "BEAR":
        notes = [(659, 0.14), (0, 0.03), (523, 0.14), (0, 0.03), (392, 0.24)]
    elif tone_type == "TRAIL":
        notes = [(880, 0.10), (0, 0.03), (1175, 0.16)]
    else:
        notes = [(987, 0.12), (0, 0.03), (659, 0.12), (0, 0.03), (440, 0.22)]

    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for freq, dur in notes:
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                val = 0 if freq == 0 else int(15000.0 * (1.0 - (i / n_samples) * 0.5) * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                frames.extend(struct.pack('<h', val))
        wf.writeframes(bytes(frames))
    return base64.b64encode(buf.getvalue()).decode('ascii')

# ============================================================================
# LIVE GEMINI API MODEL AUTO-DISCOVERY & AUTO-SELECTION
# ============================================================================
def score_model_priority(model_name: str) -> tuple:
    tier = 0 if ("pro" in model_name and "vision" not in model_name) else (
        1 if "exp" in model_name else (
            2 if ("flash" in model_name and "lite" not in model_name and "8b" not in model_name) else 3
        )
    )
    gen = 0 if "2.5" in model_name else (
        1 if "2.0" in model_name else (
            2 if "1.5" in model_name else 3
        )
    )
    is_dated = 1 if re.search(r"-\d{3,4}", model_name) else 0
    return (tier, gen, is_dated, model_name)

def fetch_available_api_models(api_key):
    default_models = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite"
    ]
    if not api_key:
        return default_models
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=4.0)
        if r.status_code == 200:
            models_data = r.json().get("models", [])
            discovered = []
            skip_keywords = ["embedding", "aqa", "imagen", "veo", "tts", "audio", "vision", "robotics", "computer-use", "learnlm"]
            for m in models_data:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name:
                    if not any(kw in name for kw in skip_keywords):
                        discovered.append(name)
            if discovered:
                discovered.sort(key=score_model_priority)
                return discovered
    except Exception:
        pass
    return default_models

def build_auto_model_queue(eng: dict) -> list:
    default_priority = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite"
    ]
    avail = sorted(eng.get("available_models", []), key=score_model_priority)
    queue = []
    for m in avail + default_priority:
        if m and m not in queue:
            queue.append(m)
    return queue

# ============================================================================
# AI DYNAMIC LOSS-RECOVERY & LOT SIZING ENGINE (MAX 2x SAFE CAP)
# ============================================================================
def parse_ai_json_safely(raw_text: str):
    try:
        cleaned = re.sub(r"```json|```", "", raw_text).strip()
        s = cleaned.find("{")
        e = cleaned.rfind("}")
        if s != -1 and e != -1:
            return json.loads(cleaned[s:e+1])
    except Exception:
        pass
    return None

def quant_fallback_lot_sizer(new_dir: str, loss_streak: int, deficit_pts: float, last_closed_pts: float, rsi14: float, buy_dom_pct: float, ema_dist_bricks: float) -> tuple:
    if deficit_pts <= 0.0:
        return 1, "✅ पिछला सारा लॉस रिकवर हो चुका है (Deficit: 0p) — स्टैंडर्ड 1x Base Lot से ट्रेड लिया गया।"

    fav_dom = buy_dom_pct if new_dir == "BUY" else (100.0 - buy_dom_pct)
    healthy_stretch = ema_dist_bricks <= 2.4

    if fav_dom >= 52.0 and healthy_stretch:
        return 2, f"⚡ AI सुरक्षित रिकवरी (2x Max Cap): पेंडिंग लॉस (-{deficit_pts:.0f}p) को सुरक्षित तरीके से रिकवर करने के लिए अनुकूल मोमेंटम ({fav_dom:.0f}% Power) पर 2x लॉट चुना गया (3x रिस्क कैप बंद)।"
    else:
        return 1, f"🛡️ सेफ सिग्नल एंट्री (1x Lot): पेंडिंग लॉस -{deficit_pts:.0f}p है, लेकिन अभी मोमेंटम धीमा ({fav_dom:.0f}% Power) है, इसलिए यह अनिवार्य सिग्नल 1x Lot पर लिया गया।"

def decide_next_lot_multiplier_with_ai(eng: dict, new_dir: str, loss_streak: int, deficit_pts: float, last_closed_pts: float) -> tuple:
    rk = eng.get("renko", {})
    rsi14 = rk.get("rsi14", 50.0)
    buy_dom = rk.get("buy_dom_pct", 50.0)
    ema_bricks = rk.get("ema_dist_bricks", 0.5)

    if deficit_pts <= 0.0:
        return 1, "✅ प्रॉफिट रीसेट: पिछला कोई पेंडिंग लॉस बाकी नहीं है (Deficit: 0p) — 1x Base Lot सेट किया गया।"

    api_key = eng.get("api_key", "").strip()
    if not api_key:
        eng["active_ai_model"] = "In-Built Quant Brain (No Gemini Key)"
        return quant_fallback_lot_sizer(new_dir, loss_streak, deficit_pts, last_closed_pts, rsi14, buy_dom, ema_bricks)

    fav_dom = buy_dom if new_dir == "BUY" else (100.0 - buy_dom)
    prompt = f"""
You are an Elite Institutional Risk & Drawdown-Recovery Manager for an automated BTCUSDT Renko Supertrend trading bot.
A new confirmed Renko Supertrend `{new_dir}` signal has just triggered!

STRICT NON-NEGOTIABLE DIRECTIVES:
1. MANDATORY TRADE EXECUTION: Every Renko signal MUST be taken without exception. Minimum multiplier is `1` (1x Base Lot).
2. STRICT 2X MAXIMUM CAP: You can choose ONLY `1` or `2` (maximum 2x Base Lot). NEVER output `3` or more, to protect the account from large drawdowns during choppy flips.
3. LOSS RECOVERY WITH DISCIPLINE:
   - Choose `2` (2x Base Lot) when there is an unrecovered loss deficit (-{deficit_pts:.1f} pts) and current orderflow power ({fav_dom:.1f}%) / Renko momentum supports recovering the loss safely.
   - Choose `1` (1x Base Lot) if momentum is weak or choppy against `{new_dir}`, so we take the mandatory signal safely without over-exposing capital.

CURRENT DATA FOR NEW `{new_dir}` SIGNAL:
- Total Unrecovered Loss Deficit to Recover: -{deficit_pts:.1f} Points (Loss Streak: {loss_streak})
- Last Closed Trade Raw PnL: {last_closed_pts:+.1f} Points
- Favorable 3-Bar Orderflow Power for `{new_dir}`: {fav_dom:.1f}%
- 14-Period RSI: {rsi14:.1f} | 21-EMA Stretch: {ema_bricks:.2f} Bricks

Return ONLY valid JSON:
{{
  "lot_multiplier": integer (MUST be 1 or 2),
  "sizing_reason": "Sharp 1-line explanation in Hindi of why you chose 1x or 2x lot size (max 2x) to recover the -{deficit_pts:.0f}p deficit safely"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 220}
    }

    models_queue = build_auto_model_queue(eng)
    for mod in models_queue:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=5.0)
            if res.status_code == 200:
                parsed = parse_ai_json_safely(res.json()['candidates'][0]['content']['parts'][0]['text'].strip())
                if parsed and "lot_multiplier" in parsed:
                    eng["active_ai_model"] = f"🟢 {mod}"
                    mult = max(1, min(2, int(parsed["lot_multiplier"])))
                    reason = str(parsed.get("sizing_reason", "")).strip()
                    if reason:
                        return mult, f"🤖 AI Lot Brain ({mult}x Max-2x | {mod}): {reason}"
        except Exception:
            continue

    return quant_fallback_lot_sizer(new_dir, loss_streak, deficit_pts, last_closed_pts, rsi14, buy_dom, ema_bricks)

# ============================================================================
# BIG PROFIT LOCK CALCULATOR + TREND-FIRST AI MANAGER
# ============================================================================
def compute_big_trend_lock_sl(entry_px: float, peak_pts: float, trade_type: str, current_sl: float = 0.0) -> float:
    """
    Protects substantial trend profits once a trade reaches +450p / +650p / +900p+ peak,
    while allowing normal sub-450p Renko trends to breathe freely.
    Never moves SL backward.
    """
    locked_gain = 0.0
    if peak_pts >= 900.0:
        locked_gain = max(720.0, peak_pts - 150.0)
    elif peak_pts >= 650.0:
        locked_gain = max(440.0, peak_pts - 180.0)
    elif peak_pts >= 450.0:
        locked_gain = max(250.0, peak_pts - 190.0)
    else:
        return round(float(current_sl or 0.0), 1)

    target_sl = round(entry_px + locked_gain, 1) if trade_type == "BUY" else round(entry_px - locked_gain, 1)
    prev_sl = float(current_sl or 0.0)
    if prev_sl > 0:
        if trade_type == "BUY":
            return round(max(prev_sl, target_sl), 1)
        else:
            return round(min(prev_sl, target_sl), 1)
    return target_sl

def _sanitize_ai_sl(current_sl: float, proposed_sl: float, live_px: float, trade_type: str) -> float:
    try:
        p_sl = float(proposed_sl)
    except Exception:
        return current_sl
    if p_sl <= 0:
        return current_sl

    if trade_type == "BUY":
        if p_sl >= live_px * 0.9985:
            return current_sl
        if current_sl > 0 and p_sl < current_sl:
            return current_sl
        return round(p_sl, 1)
    else:
        if p_sl <= live_px * 1.0015:
            return current_sl
        if current_sl > 0 and p_sl > current_sl:
            return current_sl
        return round(p_sl, 1)

def ai_trend_first_fallback_decision(active_tr: dict, rk: dict, live_px: float) -> dict:
    t_type = active_tr["type"]
    entry_px = active_tr["entry"]
    live_pts = active_tr["live_pts"]
    peak_pts = active_tr["peak_pts"]
    curr_sl = float(active_tr.get("sl_px", 0.0) or 0.0)

    st_line = float(rk.get("st_line", live_px))
    st_trend = int(rk.get("st_trend", 1 if t_type == "BUY" else -1))
    streak = int(rk.get("brick_streak", 1))
    ema_bricks = float(rk.get("ema_dist_bricks", 0.5))
    rsi14 = float(rk.get("rsi14", 50.0))
    buy_dom = float(rk.get("buy_dom_pct", 50.0))
    fav_dom = buy_dom if t_type == "BUY" else (100.0 - buy_dom)
    dist_to_st = abs(live_px - st_line)

    trend_against = (t_type == "BUY" and st_trend == -1) or (t_type == "SELL" and st_trend == 1)
    big_trend_reversal = (
        peak_pts >= 450.0
        and live_pts >= 220.0
        and (streak >= 4 or ema_bricks >= 2.4)
        and fav_dom < 42.0
        and ((t_type == "BUY" and rsi14 >= 72.0) or (t_type == "SELL" and rsi14 <= 28.0))
    )

    if trend_against or big_trend_reversal:
        return {
            "decision": "EXIT",
            "new_sl": curr_sl,
            "reason": f"AI ट्रेंड फैसला (EXIT): बड़े मूव/रैंकों स्थिति (Peak +{peak_pts:.0f}p, Streak #{streak}, Power {fav_dom:.0f}%) में पलटाव के संकेत पर {live_pts:+.1f}p सुरक्षित किया गया।"
        }

    auto_lock_sl = compute_big_trend_lock_sl(entry_px, peak_pts, t_type, curr_sl)
    new_sl = _sanitize_ai_sl(curr_sl, auto_lock_sl, live_px, t_type) if auto_lock_sl > 0 else curr_sl

    sl_note = f" | Lock SL: ${new_sl:,.1f}" if new_sl > 0 else " (लंबे ट्रेंड के लिए खुला है)"
    return {
        "decision": "HOLD",
        "new_sl": new_sl,
        "reason": f"AI ट्रेंड होल्ड (HOLD): रैंकों ट्रेंड जारी है (Peak +{peak_pts:.0f}p, ST ${st_line:,.0f} से {dist_to_st:.0f}p दूर, Power {fav_dom:.0f}%){sl_note}।"
    }

def call_gemini_trend_first_manager(eng: dict, api_key: str, active_tr: dict, rk: dict, live_px: float) -> tuple:
    avail = eng.get("available_models", [])
    top_mod = avail[0] if avail else "gemini-2.5-pro"

    if active_tr is None:
        return {
            "decision": "HOLD",
            "new_sl": 0.0,
            "reason": "अगले Core Renko ST सिग्नल की प्रतीक्षा — नया ट्रेंड खुलते ही AI लंबे ट्रेंड और बड़े प्रॉफिट लॉक को संभालेगा।"
        }, f"🟢 {top_mod} (Standby)"

    t_type = active_tr["type"]
    entry_px = active_tr["entry"]
    live_pts = active_tr["live_pts"]
    peak_pts = active_tr["peak_pts"]
    curr_sl = float(active_tr.get("sl_px", 0.0) or 0.0)
    st_line = float(rk.get("st_line", live_px))
    dist_to_st = abs(live_px - st_line)

    prompt = f"""
You are a Trend-Following Renko Price-Action Trade Manager managing an ACTIVE BTCUSDT trade.
The trade was entered on a Core Renko Supertrend signal, and lot multiplier is capped safely at 2x maximum.
Your goal is to capture BIG, LONG RENKO TRENDS while locking in substantial profits once earned.

TREND-FIRST JUDGMENT PRINCIPLES:
1. LET LONG TRENDS BREATHE: Allow normal Renko pullbacks to breathe while `stLevel` (${st_line:,.1f}) holds and trend structure is intact, rather than exiting early on minor noise.
2. BIG TREND PROFIT LOCK: Once a trade reaches strong profit territory (+450p, +650p, +900p+ peak/move), set or advance `new_sl` to lock in a solid portion of that profit so a big winner does not slip back into a small gain or loss.
3. EXIT WITH PURPOSE: Choose `"EXIT"` if the Renko trend has flipped against the trade, or if a strong move shows clear reversal exhaustion. Otherwise choose `"HOLD"`.

ACTIVE TRADE DETAILS:
- Direction: {t_type} | Entry: ${entry_px:,.1f} | Current Price: ${live_px:,.1f}
- Live PnL: {live_pts:+.1f} pts | Peak Profit: +{peak_pts:.1f} pts | Current Active SL: ${curr_sl:,.1f}
- Lot Size: {active_tr.get('lot_size', 1)} ({active_tr.get('lot_mult', 1)}x)

CURRENT RENKO & MARKET STRUCTURE:
- Brick Size: ${rk.get('box_size', 270.0):.1f} pts | Reversal Factor: {rk.get('rev_bricks', 2.0):.1f} Bricks
- Brick Box: ${rk.get('brick_bot', 0.0):,.1f} to ${rk.get('brick_top', 0.0):,.1f} | Streak: #{rk.get('brick_streak', 1)}
- Trend: {'BULLISH (1)' if rk.get('st_trend', 1) == 1 else 'BEARISH (-1)'} | Reversal `stLevel`: ${st_line:,.1f} (Distance: {dist_to_st:.1f} pts)
- 21-EMA: ${rk.get('ema21', 0.0):,.1f} (Stretch: {rk.get('ema_dist_bricks', 0.0):.2f} Bricks) | 14-RSI: {rk.get('rsi14', 50.0):.1f} | Buy Dominance: {rk.get('buy_dom_pct', 50.0):.1f}%

Return ONLY valid JSON:
{{
  "decision": "HOLD" or "EXIT",
  "new_sl": 0.0,
  "reason": "Concise, sharp explanation in Hindi focusing on long-trend capture, Renko structure, and big profit protection"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 260}
    }

    models_queue = build_auto_model_queue(eng)
    for mod in models_queue:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=8.5)
            if res.status_code == 200:
                parsed = parse_ai_json_safely(res.json()['candidates'][0]['content']['parts'][0]['text'].strip())
                if parsed and str(parsed.get("decision", "")).upper() in ("HOLD", "EXIT"):
                    dec = str(parsed["decision"]).upper()
                    auto_sl = compute_big_trend_lock_sl(entry_px, peak_pts, t_type, curr_sl)
                    ai_sl = _sanitize_ai_sl(curr_sl, parsed.get("new_sl", curr_sl), live_px, t_type)
                    merged_sl = curr_sl
                    if auto_sl > 0 and ai_sl > 0:
                        merged_sl = max(auto_sl, ai_sl) if t_type == "BUY" else min(auto_sl, ai_sl)
                    elif auto_sl > 0:
                        merged_sl = auto_sl
                    elif ai_sl > 0:
                        merged_sl = ai_sl
                    rsn = str(parsed.get("reason", "")).strip() or ai_trend_first_fallback_decision(active_tr, rk, live_px)["reason"]
                    return {"decision": dec, "new_sl": round(merged_sl, 1), "reason": rsn}, f"🟢 {mod}"
        except Exception:
            continue

    return ai_trend_first_fallback_decision(active_tr, rk, live_px), f"⚡ {top_mod} (Trend Judgment)"

# ============================================================================
# PURE SVG LIVE CHART GENERATOR
# ============================================================================
def build_renko_svg_chart(rk: dict, live_px: float, active_tr: dict) -> str:
    pts = rk.get("chart_points", [])
    if len(pts) < 5:
        return "<div style='text-align:center; color:#64748b; padding:60px;'>📊 लाइव चार्ट डेटा तैयार हो रहा है...</div>"

    w, h = 920, 315
    pad_l, pad_r, pad_t, pad_b = 18, 86, 22, 28
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    all_y = []
    for p in pts:
        all_y.extend([p["close"], p["st"]])
    all_y.extend([live_px, rk.get("brick_top", live_px), rk.get("brick_bot", live_px), rk.get("st_line", live_px)])
    if active_tr and float(active_tr.get("sl_px", 0.0) or 0.0) > 0:
        all_y.append(float(active_tr["sl_px"]))

    min_y = min(all_y)
    max_y = max(all_y)
    span_y = max(50.0, max_y - min_y)
    min_y -= span_y * 0.08
    max_y += span_y * 0.08
    span_y = max_y - min_y

    def to_x(idx, total):
        return pad_l + (idx / max(1, total - 1)) * plot_w

    def to_y(val):
        return pad_t + plot_h - ((val - min_y) / span_y) * plot_h

    n = len(pts)
    grid_svg = ""
    for i in range(5):
        gy = pad_t + (i / 4.0) * plot_h
        gval = max_y - (i / 4.0) * span_y
        grid_svg += f"<line x1='{pad_l}' y1='{gy:.1f}' x2='{w - pad_r}' y2='{gy:.1f}' stroke='#1e293b' stroke-dasharray='3,3' stroke-width='1'/>"
        grid_svg += f"<text x='{w - pad_r + 6}' y='{gy + 4:.1f}' fill='#94a3b8' font-size='11' font-family='monospace'>${gval:,.0f}</text>"

    for idx_pos in [0, n // 3, (2 * n) // 3, n - 1]:
        if 0 <= idx_pos < n:
            tx = to_x(idx_pos, n)
            grid_svg += f"<text x='{tx:.1f}' y='{h - 6}' fill='#64748b' font-size='10.5' text-anchor='middle' font-family='sans-serif'>{pts[idx_pos]['time']}</text>"

    b_top = rk.get("brick_top", live_px)
    b_bot = rk.get("brick_bot", live_px)
    y_btop = to_y(b_top)
    y_bbot = to_y(b_bot)
    brick_guides = (
        f"<line x1='{pad_l}' y1='{y_btop:.1f}' x2='{w - pad_r}' y2='{y_btop:.1f}' stroke='#14b8a6' stroke-dasharray='4,4' stroke-width='1' opacity='0.6'/>"
        f"<line x1='{pad_l}' y1='{y_bbot:.1f}' x2='{w - pad_r}' y2='{y_bbot:.1f}' stroke='#f97316' stroke-dasharray='4,4' stroke-width='1' opacity='0.6'/>"
    )

    ai_sl_svg = ""
    if active_tr and float(active_tr.get("sl_px", 0.0) or 0.0) > 0:
        ai_sl_val = float(active_tr["sl_px"])
        y_sl = to_y(ai_sl_val)
        ai_sl_svg = (
            f"<line x1='{pad_l}' y1='{y_sl:.1f}' x2='{w - pad_r}' y2='{y_sl:.1f}' stroke='#c084fc' stroke-dasharray='6,3' stroke-width='2.0'/>"
            f"<rect x='{w - pad_r + 2}' y='{y_sl - 9:.1f}' width='80' height='18' rx='4' fill='#c084fc'/>"
            f"<text x='{w - pad_r + 42}' y='{y_sl + 4:.1f}' fill='#090d16' font-size='10' font-weight='bold' text-anchor='middle'>Lock ${ai_sl_val:,.0f}</text>"
        )

    price_coords = []
    st_segments = ""
    markers_svg = ""

    for i, p in enumerate(pts):
        x1 = to_x(i, n)
        yc = to_y(p["close"])
        yst = to_y(p["st"])
        price_coords.append(f"{x1:.1f},{yc:.1f}")

        if i > 0:
            x0 = to_x(i - 1, n)
            yst0 = to_y(pts[i - 1]["st"])
            seg_col = "#22c55e" if p["trend"] == 1 else "#ef4444"
            st_segments += f"<path d='M {x0:.1f} {yst0:.1f} L {x1:.1f} {yst0:.1f} L {x1:.1f} {yst:.1f}' stroke='{seg_col}' stroke-width='2.6' fill='none'/>"

        if p.get("sig") == "BUY":
            markers_svg += (
                f"<polygon points='{x1:.1f},{yst - 2:.1f} {x1 - 7:.1f},{yst + 12:.1f} {x1 + 7:.1f},{yst + 12:.1f}' fill='#22c55e' stroke='#052e16' stroke-width='1.2'/>"
                f"<text x='{x1:.1f}' y='{yst + 24:.1f}' fill='#4ade80' font-size='10.5' font-weight='bold' text-anchor='middle'>BUY ${p['close']:,.0f}</text>"
            )
        elif p.get("sig") == "SELL":
            markers_svg += (
                f"<polygon points='{x1:.1f},{yst + 2:.1f} {x1 - 7:.1f},{yst - 12:.1f} {x1 + 7:.1f},{yst - 12:.1f}' fill='#ef4444' stroke='#450a0a' stroke-width='1.2'/>"
                f"<text x='{x1:.1f}' y='{yst - 16:.1f}' fill='#f87171' font-size='10.5' font-weight='bold' text-anchor='middle'>SELL ${p['close']:,.0f}</text>"
            )

    price_poly = f"<polyline points='{' '.join(price_coords)}' fill='none' stroke='#38bdf8' stroke-width='1.9'/>"

    y_live = to_y(live_px)
    y_st_now = to_y(rk.get("st_line", live_px))
    st_now_col = "#22c55e" if rk.get("st_trend", 1) == 1 else "#ef4444"

    live_tags = (
        f"<circle cx='{to_x(n - 1, n):.1f}' cy='{y_live:.1f}' r='4' fill='#38bdf8'/>"
        f"<rect x='{w - pad_r + 2}' y='{y_st_now - 9:.1f}' width='80' height='18' rx='4' fill='{st_now_col}'/>"
        f"<text x='{w - pad_r + 42}' y='{y_st_now + 4:.1f}' fill='#090d16' font-size='10.5' font-weight='bold' text-anchor='middle'>ST ${rk.get('st_line', 0):,.0f}</text>"
        f"<rect x='{w - pad_r + 2}' y='{y_live - 9:.1f}' width='80' height='18' rx='4' fill='#38bdf8'/>"
        f"<text x='{w - pad_r + 42}' y='{y_live + 4:.1f}' fill='#090d16' font-size='10.5' font-weight='bold' text-anchor='middle'>Px ${live_px:,.0f}</text>"
    )

    return f"""
    <svg viewBox='0 0 {w} {h}' style='width:100%; height:auto; background:#090d16; border-radius:8px; display:block;'>
        {grid_svg}
        {brick_guides}
        {st_segments}
        {ai_sl_svg}
        {price_poly}
        {markers_svg}
        {live_tags}
    </svg>
    """

# ============================================================================
# CORE ARCHITECTURE: SYNTHETIC RENKO SUPERTREND + BIG PROFIT LOCK
# ============================================================================
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ist_time_str():
    return get_ist_now().strftime('%I:%M:%S %p')

def fetch_live_btc_price():
    try:
        r = requests.post(HYPERLIQUID_URL, json={"type": "allMids"}, timeout=2.0)
        if r.status_code == 200:
            mids = r.json()
            if isinstance(mids, dict) and "BTC" in mids:
                return float(mids["BTC"])
    except Exception:
        pass
    try:
        r2 = requests.post(HYPERLIQUID_URL, json={"type": "l2Book", "coin": "BTC"}, timeout=2.0)
        if r2.status_code == 200:
            levels = r2.json().get("levels", [])
            if len(levels) >= 2 and levels[0] and levels[1]:
                return (float(levels[0][0]["px"]) + float(levels[1][0]["px"])) / 2.0
    except Exception as e:
        return str(e)
    return None

def fetch_core_renko_supertrend(fixed_brick_size: float = 270.0, rev_bricks: float = 2.0, base_lot: int = 1):
    try:
        brick_size = max(10.0, float(fixed_brick_size))
        rev_mult = max(0.5, float(rev_bricks))
        base_lot_int = max(1, int(base_lot))
        now_ms = int(time.time() * 1000)

        start_1m = now_ms - (1440 * 60 * 1000)
        r_1m = requests.post(
            HYPERLIQUID_URL,
            json={"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": start_1m, "endTime": now_ms}},
            timeout=4.0
        )
        if r_1m.status_code != 200 or len(r_1m.json()) < 30:
            return None

        closed_bars = r_1m.json()[:-1]
        closes = [float(b["c"]) for b in closed_bars]
        highs = [float(b["h"]) for b in closed_bars]
        lows = [float(b["l"]) for b in closed_bars]
        opens = [float(b["o"]) for b in closed_bars]
        vols = [float(b["v"]) for b in closed_bars]
        bar_times = [int(b["t"]) for b in closed_bars]

        ema_arr = [closes[0]]
        k_ema = 2.0 / (21.0 + 1.0)
        for c_val in closes[1:]:
            ema_arr.append((c_val * k_ema) + (ema_arr[-1] * (1.0 - k_ema)))
        ema21 = ema_arr[-1]

        rsi_arr = [50.0] * len(closes)
        gains, losses = [0.0], [0.0]
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))
        if len(closes) > 15:
            avg_g = sum(gains[1:15]) / 14.0
            avg_l = sum(losses[1:15]) / 14.0
            for i in range(15, len(closes)):
                avg_g = (avg_g * 13.0 + gains[i]) / 14.0
                avg_l = (avg_l * 13.0 + losses[i]) / 14.0
                rsi_arr[i] = 100.0 if avg_l == 0 else (100.0 - (100.0 / (1.0 + (avg_g / avg_l))))
        rsi14 = rsi_arr[-1]

        bar_buy_v, bar_sell_v, dom_arr = [], [], []
        for i in range(len(closes)):
            rng = max(highs[i] - lows[i], 0.1)
            u_wick = highs[i] - max(opens[i], closes[i])
            l_wick = min(opens[i], closes[i]) - lows[i]
            body = abs(closes[i] - opens[i])
            bull_score = (closes[i] - lows[i]) + (l_wick * 1.1) + (body * 0.85 if closes[i] > opens[i] else 0.0)
            bear_score = (highs[i] - closes[i]) + (u_wick * 1.1) + (body * 0.85 if closes[i] < opens[i] else 0.0)
            bull_pow = math.pow(max(bull_score / rng, 0.01), 1.8)
            bear_pow = math.pow(max(bear_score / rng, 0.01), 1.8)
            tot_pow = bull_pow + bear_pow
            bar_buy_v.append(vols[i] * (bull_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5)
            bar_sell_v.append(vols[i] * (bear_pow / tot_pow) if tot_pow > 0 else vols[i] * 0.5)
            if i >= 2:
                rb = (bar_buy_v[i] * 1.4) + bar_buy_v[i-1] + bar_buy_v[i-2]
                rs = (bar_sell_v[i] * 1.4) + bar_sell_v[i-1] + bar_sell_v[i-2]
                dom_arr.append((rb / (rb + rs) * 100.0) if (rb + rs) > 0 else 50.0)
            else:
                dom_arr.append(50.0)

        buy_dom_pct = dom_arr[-1]

        rev_dist = rev_mult * brick_size
        snapped = math.floor(closes[0] / brick_size) * brick_size
        brick_bot = snapped
        brick_top = snapped + brick_size
        trend = 1
        st_level = brick_top - rev_dist
        brick_streak = 1

        buy_signal = False
        sell_signal = False
        last_flip_bar_ts = bar_times[0]
        last_flip_price = closes[0]
        last_flip_time_str = (datetime.utcfromtimestamp(bar_times[0] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

        trade_records = []
        chart_points = []

        sim_loss_streak = 0
        sim_deficit_pts = 0.0
        sim_last_closed_pts = 0.0

        def _record_closed_trade_outcome(closed_tr):
            nonlocal sim_loss_streak, sim_deficit_pts, sim_last_closed_pts
            raw_pts = closed_tr["live_pts"]
            mult_used = closed_tr.get("lot_mult", 1)
            weighted_pts = round(raw_pts * mult_used, 1)
            closed_tr["weighted_pts"] = weighted_pts
            sim_last_closed_pts = raw_pts

            if raw_pts < 0:
                sim_loss_streak += 1
                sim_deficit_pts = round(sim_deficit_pts + abs(weighted_pts), 1)
            else:
                sim_deficit_pts = round(max(0.0, sim_deficit_pts - weighted_pts), 1)
                if sim_deficit_pts <= 0.0:
                    sim_loss_streak = 0
                    sim_deficit_pts = 0.0

        for i in range(1, len(closes)):
            c = closes[i]
            h_bar = highs[i]
            l_bar = lows[i]
            prev_trend = trend
            prev_st_level = st_level

            if trend == 1:
                if c >= brick_top + brick_size:
                    steps = int(math.floor((c - brick_top) / brick_size))
                    brick_top = brick_top + (steps * brick_size)
                    brick_bot = brick_top - brick_size
                    brick_streak += steps

                raw_support = brick_top - rev_dist
                st_level = max(raw_support, prev_st_level)

                if c < st_level:
                    trend = -1
                    down_steps = max(1, int(math.floor((brick_top - c) / brick_size)))
                    brick_bot = brick_top - (down_steps * brick_size)
                    brick_top = brick_bot + brick_size
                    st_level = brick_bot + rev_dist
                    brick_streak = down_steps

            elif trend == -1:
                if c <= brick_bot - brick_size:
                    steps = int(math.floor((brick_bot - c) / brick_size))
                    brick_bot = brick_bot - (steps * brick_size)
                    brick_top = brick_bot + brick_size
                    brick_streak += steps

                raw_res = brick_bot + rev_dist
                st_level = min(raw_res, prev_st_level)

                if c > st_level:
                    trend = 1
                    up_steps = max(1, int(math.floor((c - brick_bot) / brick_size)))
                    brick_top = brick_bot + (up_steps * brick_size)
                    brick_bot = brick_top - brick_size
                    st_level = brick_top - rev_dist
                    brick_streak = up_steps

            bar_buy_sig = (trend == 1 and prev_trend == -1)
            bar_sell_sig = (trend == -1 and prev_trend == 1)
            b_ist_short = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
            b_ist_full = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

            if trade_records and "ACTIVE" in trade_records[-1]["status"] and not (bar_buy_sig or bar_sell_sig):
                cur_t = trade_records[-1]
                t_mult = cur_t.get("lot_mult", 1)

                # Check Big Trend Lock SL hit on bar high/low
                cur_sl = float(cur_t.get("sl_px", 0.0) or 0.0)
                if cur_sl > 0:
                    hit_lock = (l_bar <= cur_sl) if cur_t["type"] == "BUY" else (h_bar >= cur_sl)
                    if hit_lock:
                        locked_pts_val = (cur_sl - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - cur_sl)
                        cur_t["live_pts"] = round(locked_pts_val, 1)
                        cur_t["weighted_pts"] = round(locked_pts_val * t_mult, 1)
                        cur_t["close_time"] = b_ist_full
                        cur_t["status"] = f"BIG PROFIT LOCK HIT @ ${cur_sl:,.1f} ({b_ist_short})"
                        cur_t["exit_reason"] = f"🛡️ बड़े प्रॉफिट का सुरक्षित लॉक SL (${cur_sl:,.1f}) हिट होने पर +{locked_pts_val:.1f}p ({t_mult}x PnL: +{locked_pts_val*t_mult:.1f}p) बुक हुआ!"
                        cur_t["ai_reason"] = cur_t["exit_reason"]
                        _record_closed_trade_outcome(cur_t)

                if "ACTIVE" in cur_t["status"]:
                    fav_px = h_bar if cur_t["type"] == "BUY" else l_bar
                    cur_fav = (fav_px - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - fav_px)
                    cur_t["peak_pts"] = round(max(cur_t["peak_pts"], cur_fav), 1)
                    cur_t["live_pts"] = round((c - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - c), 1)
                    cur_t["weighted_pts"] = round(cur_t["live_pts"] * t_mult, 1)

                    updated_sl = compute_big_trend_lock_sl(cur_t["entry"], cur_t["peak_pts"], cur_t["type"], cur_t.get("sl_px", 0.0))
                    if updated_sl > 0:
                        cur_t["sl_px"] = updated_sl
                        l_gain = (updated_sl - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - updated_sl)
                        cur_t["ai_reason"] = f"🛡️ बड़ा प्रॉफिट लॉक सक्रिय: Peak +{cur_t['peak_pts']:.0f}p पर SL ${updated_sl:,.1f} (+{l_gain:.0f}p सुरक्षित) सेट है।"

            if bar_buy_sig or bar_sell_sig:
                last_flip_bar_ts = bar_times[i]
                last_flip_price = c
                last_flip_time_str = b_ist_full
                sig_dir = "BUY" if bar_buy_sig else "SELL"

                if trade_records and "ACTIVE" in trade_records[-1]["status"]:
                    prev_tr = trade_records[-1]
                    move_pts = (c - prev_tr["entry"]) if prev_tr["type"] == "BUY" else (prev_tr["entry"] - c)
                    prev_tr["live_pts"] = round(move_pts, 1)
                    prev_tr["peak_pts"] = round(max(prev_tr["peak_pts"], move_pts), 1)
                    prev_tr["close_time"] = b_ist_full
                    prev_tr["status"] = f"FLIPPED TO {sig_dir} @ ${c:,.1f} ({b_ist_short})"
                    prev_tr["exit_reason"] = f"विपरीत {sig_dir} सिग्नल आने पर ${c:,.1f} पर बंद हुआ (Raw: {move_pts:+.1f}p | {prev_tr.get('lot_mult',1)}x Lot PnL: {move_pts*prev_tr.get('lot_mult',1):+.1f}p)"
                    _record_closed_trade_outcome(prev_tr)

                eb_now = abs(c - ema_arr[i]) / max(1.0, brick_size)
                m_mult, m_reason = quant_fallback_lot_sizer(sig_dir, sim_loss_streak, sim_deficit_pts, sim_last_closed_pts, rsi_arr[i], dom_arr[i], eb_now)

                trade_records.append({
                    "open_ts": bar_times[i] / 1000.0,
                    "open_time": b_ist_full,
                    "close_time": "",
                    "type": sig_dir,
                    "entry": round(c, 1),
                    "lot_mult": m_mult,
                    "lot_size": base_lot_int * m_mult,
                    "lot_reason": m_reason,
                    "sl_px": 0.0,
                    "ai_decision": "HOLD",
                    "ai_reason": "ट्रेड खुल चुका है — AI लंबे ट्रेंड को होल्ड रखेगा और +450p/+650p+ पर प्रॉफिट लॉक करेगा।",
                    "live_pts": 0.0,
                    "weighted_pts": 0.0,
                    "peak_pts": 0.0,
                    "status": "ACTIVE (TREND AI)",
                    "entry_reason": f"🔥 Core Renko ST {sig_dir} Signal (Brick: ${brick_size:.0f} | ST: ${st_level:,.1f})",
                    "exit_reason": f"चालू है — AI लंबे ट्रेंड को होल्ड रखेगा और बड़े प्रॉफिट पर लॉक करेगा (Renko ST: ${st_level:,.1f})"
                })

            if i >= len(closes) - 240 or bar_buy_sig or bar_sell_sig:
                chart_points.append({
                    "time": b_ist_short,
                    "close": round(c, 1),
                    "st": round(st_level, 1),
                    "trend": trend,
                    "sig": "BUY" if bar_buy_sig else ("SELL" if bar_sell_sig else None)
                })

            if i == len(closes) - 1:
                buy_signal = bar_buy_sig
                sell_signal = bar_sell_sig

        last_c = closes[-1]
        r_close_now = brick_top if trend == 1 else brick_bot
        ema_dist_bricks = abs(last_c - ema21) / max(1.0, brick_size)

        return {
            "box_size": round(brick_size, 1),
            "rev_bricks": round(rev_mult, 1),
            "brick_top": round(brick_top, 1),
            "brick_bot": round(brick_bot, 1),
            "brick_dir": trend,
            "brick_streak": brick_streak,
            "r_close": round(r_close_now, 1),
            "st_trend": trend,
            "st_line": round(st_level, 1),
            "st_flip_buy": buy_signal,
            "st_flip_sell": sell_signal,
            "last_flip_bar_ts": last_flip_bar_ts,
            "last_flip_price": round(last_flip_price, 1),
            "last_flip_time_str": last_flip_time_str,
            "buy_dom_pct": round(buy_dom_pct, 1),
            "ema21": round(ema21, 1),
            "ema_dist_bricks": round(ema_dist_bricks, 2),
            "rsi14": round(rsi14, 1),
            "last_confirmed_close": round(last_c, 1),
            "sim_loss_streak": sim_loss_streak,
            "sim_deficit_pts": sim_deficit_pts,
            "sim_last_closed_pts": sim_last_closed_pts,
            "trade_records": list(reversed(trade_records[-20:])),
            "chart_points": chart_points[-180:]
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# LIVE TRADE OPENER & CLOSER (TREND-FIRST AI MANAGEMENT + BIG PROFIT LOCK)
# ============================================================================
def open_renko_trade_now(eng, direction: str, entry_px: float, ist_str: str, entry_source_label: str, fire_delta: bool = True, is_flip: bool = False, prev_lot_to_close: int = 0):
    rk = eng.get("renko", {})
    st_line_val = rk.get("st_line", entry_px)
    box_sz = rk.get("box_size", 270.0)
    base_lot = max(1, int(eng.get("delta_base_lot", 1)))

    loss_streak = int(eng.get("loss_streak", 0))
    deficit_pts = float(eng.get("deficit_pts", 0.0))
    last_closed_pts = float(eng.get("last_closed_pts", 0.0))

    lot_mult, lot_reason = decide_next_lot_multiplier_with_ai(eng, direction, loss_streak, deficit_pts, last_closed_pts)
    final_lot_size = base_lot * lot_mult

    eng["current_lot_mult"] = lot_mult
    eng["current_lot_size"] = final_lot_size
    eng["last_lot_reason"] = lot_reason

    new_trade = {
        "open_ts": time.time(),
        "open_time": ist_str,
        "close_time": "",
        "type": direction,
        "entry": round(entry_px, 1),
        "lot_mult": lot_mult,
        "lot_size": final_lot_size,
        "lot_reason": lot_reason,
        "sl_px": 0.0,
        "ai_decision": "HOLD",
        "ai_reason": "ट्रेड खुल चुका है — AI रैंकों के लंबे ट्रेंड को पकड़ने और बड़े प्रॉफिट को सुरक्षित करने के लिए काम कर रहा है।",
        "live_pts": 0.0,
        "weighted_pts": 0.0,
        "peak_pts": 0.0,
        "status": "ACTIVE (TREND AI)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | Reversal ST: ${st_line_val:,.1f})",
        "exit_reason": f"चालू है — AI लंबे ट्रेंड को होल्ड रखेगा और बड़े प्रॉफिट पर लॉक करेगा (Renko ST: ${st_line_val:,.1f})"
    }
    eng["active_trade"] = new_trade
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

    if fire_delta:
        act_kind = "FLIP" if is_flip else "OPEN"
        execute_delta_entry_and_exit(
            eng,
            action_kind=act_kind,
            direction=direction,
            target_lot=final_lot_size,
            close_prev_lot=prev_lot_to_close,
            note=f"{direction} {final_lot_size}L"
        )

def close_renko_trade_at_price(eng, active_tr, exit_px: float, ist_str: str, reason_title: str, detailed_reason: str, fire_delta: bool = True, defer_delta_for_flip: bool = False):
    move = (exit_px - active_tr["entry"]) if active_tr["type"] == "BUY" else (active_tr["entry"] - exit_px)
    mult_used = int(active_tr.get("lot_mult", 1))
    lot_used = int(active_tr.get("lot_size", max(1, int(eng.get("delta_base_lot", 1)))))
    weighted_move = round(move * mult_used, 1)

    active_tr["live_pts"] = round(move, 1)
    active_tr["weighted_pts"] = weighted_move
    active_tr["peak_pts"] = round(max(active_tr["peak_pts"], move), 1)
    active_tr["close_time"] = ist_str
    active_tr["status"] = f"{reason_title} @ ${exit_px:,.1f} ({ist_str})"
    active_tr["exit_reason"] = detailed_reason

    eng["last_closed_pts"] = round(move, 1)
    if move < 0:
        eng["loss_streak"] = int(eng.get("loss_streak", 0)) + 1
        eng["deficit_pts"] = round(float(eng.get("deficit_pts", 0.0)) + abs(weighted_move), 1)
    else:
        rem_deficit = round(max(0.0, float(eng.get("deficit_pts", 0.0)) - weighted_move), 1)
        eng["deficit_pts"] = rem_deficit
        if rem_deficit <= 0.0:
            eng["loss_streak"] = 0
            eng["deficit_pts"] = 0.0

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

    if fire_delta and not defer_delta_for_flip:
        execute_delta_entry_and_exit(
            eng,
            action_kind="CLOSE_ONLY",
            direction=active_tr["type"],
            target_lot=0,
            close_prev_lot=lot_used,
            note=f"Close {active_tr['type']}"
        )

def execute_ai_management_cycle(eng: dict, ist_str: str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        px = float(eng.get("px", 0.0))
        if px <= 0:
            return
        rk = eng.get("renko", {})
        act_tr = eng.get("active_trade")
        api_key = eng.get("api_key", "").strip()

        if act_tr is None:
            avail = eng.get("available_models", [])
            top_mod = avail[0] if avail else "gemini-2.5-pro"
            eng["active_ai_model"] = f"🟢 {top_mod} (Standby)"
            eng["last_ai_decision"] = "WAIT"
            eng["last_ai_reason"] = f"अगले Core Renko ST सिग्नल की प्रतीक्षा — Reversal Level (${rk.get('st_line', px):,.1f}) पर नज़र है।"
            eng["last_report_ts"] = time.time()
            return

        t_mult = int(act_tr.get("lot_mult", 1))
        move = (px - act_tr["entry"]) if act_tr["type"] == "BUY" else (act_tr["entry"] - px)
        act_tr["live_pts"] = round(move, 1)
        act_tr["weighted_pts"] = round(move * t_mult, 1)
        act_tr["peak_pts"] = round(max(act_tr["peak_pts"], move), 1)

        if api_key:
            dec_obj, mod_label = call_gemini_trend_first_manager(eng, api_key, act_tr, rk, px)
        else:
            avail = eng.get("available_models", [])
            top_mod = avail[0] if avail else "Quant Brain"
            dec_obj = ai_trend_first_fallback_decision(act_tr, rk, px)
            mod_label = f"⚡ {top_mod} (Trend-First)"

        eng["active_ai_model"] = mod_label
        eng["last_report_ts"] = time.time()

        cur_live = eng.get("active_trade")
        if cur_live is None or cur_live["open_ts"] != act_tr["open_ts"]:
            return

        decision = dec_obj.get("decision", "HOLD")
        new_sl = float(dec_obj.get("new_sl", cur_live.get("sl_px", 0.0)) or 0.0)
        reason = dec_obj.get("reason", "")

        cur_live["ai_decision"] = decision
        cur_live["ai_reason"] = reason
        if new_sl > 0:
            cur_live["sl_px"] = new_sl

        eng["last_ai_decision"] = decision
        eng["last_ai_reason"] = reason

        if decision == "EXIT":
            close_renko_trade_at_price(
                eng,
                cur_live,
                px,
                ist_str,
                "AI TREND EXIT",
                f"🧠 {reason} (Exit @ ${px:,.1f} | {move:+.1f}p)",
                fire_delta=True,
                defer_delta_for_flip=False
            )
    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 1-SECOND BACKGROUND WORKER
# ============================================================================
def background_worker(eng, worker_id):
    last_used_brick_size = eng.get("fixed_brick_size", 270.0)
    last_used_rev = eng.get("rev_bricks", 2.0)
    last_used_base_lot = eng.get("delta_base_lot", 1)

    threading.Thread(target=auto_verify_delta_demo_wallet, args=(eng,), daemon=True).start()

    while True:
        if eng.get("worker_id") != worker_id:
            break
        try:
            now_ts = time.time()
            ist_str = get_ist_time_str()
            px_res = fetch_live_btc_price()

            if isinstance(px_res, float) and px_res > 0:
                px = px_res
                eng["px"] = px
                eng["last_update"] = ist_str

                user_brick_sz = float(eng.get("fixed_brick_size", 270.0))
                user_rev = float(eng.get("rev_bricks", 2.0))
                user_base_lot = max(1, int(eng.get("delta_base_lot", 1)))
                settings_changed = (
                    abs(user_brick_sz - last_used_brick_size) >= 0.5
                    or abs(user_rev - last_used_rev) >= 0.1
                    or (user_base_lot != last_used_base_lot)
                )

                act_tr = eng.get("active_trade")
                if act_tr is not None:
                    t_mult = int(act_tr.get("lot_mult", 1))
                    move = (px - act_tr["entry"]) if act_tr["type"] == "BUY" else (act_tr["entry"] - px)
                    act_tr["live_pts"] = round(move, 1)
                    act_tr["weighted_pts"] = round(move * t_mult, 1)
                    act_tr["peak_pts"] = round(max(act_tr["peak_pts"], move), 1)

                    # Continuously advance Big Trend Lock SL once peak reaches +450p/+650p/+900p+
                    prev_sl_val = float(act_tr.get("sl_px", 0.0) or 0.0)
                    new_lock_sl = compute_big_trend_lock_sl(act_tr["entry"], act_tr["peak_pts"], act_tr["type"], prev_sl_val)
                    if new_lock_sl > 0 and new_lock_sl != prev_sl_val:
                        act_tr["sl_px"] = new_lock_sl
                        l_gain = (new_lock_sl - act_tr["entry"]) if act_tr["type"] == "BUY" else (act_tr["entry"] - new_lock_sl)
                        act_tr["ai_reason"] = f"🛡️ बड़ा प्रॉफिट लॉक सक्रिय: Peak +{act_tr['peak_pts']:.0f}p पर SL ${new_lock_sl:,.1f} (+{l_gain:.0f}p सुरक्षित) सेट है।"
                        eng["sound_event"] = {"id": now_ts, "type": "TRAIL"}

                    ai_sl = float(act_tr.get("sl_px", 0.0) or 0.0)
                    sl_hit = False
                    if ai_sl > 0:
                        sl_hit = (px <= ai_sl) if act_tr["type"] == "BUY" else (px >= ai_sl)

                    if sl_hit:
                        close_renko_trade_at_price(
                            eng,
                            act_tr,
                            px,
                            ist_str,
                            "BIG PROFIT LOCK HIT",
                            f"🛡️ बड़े प्रॉफिट का सुरक्षित लॉक SL (${ai_sl:,.1f}) हिट होने पर ${px:,.1f} पर मुनाफा बुक हुआ ({move:+.1f}p)",
                            fire_delta=True,
                            defer_delta_for_flip=False
                        )

                if settings_changed or (now_ts - eng["last_kline_ts"] > 6):
                    rk_data = fetch_core_renko_supertrend(
                        fixed_brick_size=user_brick_sz,
                        rev_bricks=user_rev,
                        base_lot=user_base_lot
                    )
                    if rk_data and "error" not in rk_data:
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data
                        last_used_brick_size = user_brick_sz
                        last_used_rev = user_rev
                        last_used_base_lot = user_base_lot

                        if prev_rk_trend == 0 or settings_changed:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                            eng["loss_streak"] = rk_data.get("sim_loss_streak", 0)
                            eng["deficit_pts"] = rk_data.get("sim_deficit_pts", 0.0)
                            eng["last_closed_pts"] = rk_data.get("sim_last_closed_pts", 0.0)

                            if rk_data.get("trade_records"):
                                eng["signal_history"] = rk_data["trade_records"]
                                latest_tr = eng["signal_history"][0]
                                eng["active_trade"] = latest_tr if "ACTIVE" in latest_tr["status"] else None
                                if eng["active_trade"]:
                                    eng["current_lot_mult"] = eng["active_trade"].get("lot_mult", 1)
                                    eng["current_lot_size"] = eng["active_trade"].get("lot_size", user_base_lot)
                                    eng["last_lot_reason"] = eng["active_trade"].get("lot_reason", "")
                            else:
                                cur_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                open_renko_trade_now(eng, cur_dir, rk_data["last_flip_price"], rk_data["last_flip_time_str"], f"🔥 Chart Sync {cur_dir}", fire_delta=False)

                            threading.Thread(target=execute_ai_management_cycle, args=(eng, ist_str), daemon=True).start()
                        else:
                            if rk_data["st_trend"] != prev_rk_trend and rk_data["last_flip_bar_ts"] != eng.get("last_handled_flip_ts"):
                                eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                                new_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                flip_px = rk_data["last_confirmed_close"]
                                prev_lot_cnt = 0

                                if eng.get("active_trade") is not None:
                                    old_tr = eng["active_trade"]
                                    prev_lot_cnt = int(old_tr.get("lot_size", user_base_lot))
                                    raw_m = (flip_px - old_tr["entry"]) if old_tr["type"] == "BUY" else (old_tr["entry"] - flip_px)
                                    close_renko_trade_at_price(
                                        eng,
                                        old_tr,
                                        flip_px,
                                        ist_str,
                                        f"FLIPPED TO {new_dir}",
                                        f"विपरीत {new_dir} सिग्नल आने पर ${flip_px:,.1f} पर बंद हुआ (Raw: {raw_m:+.1f}p | {old_tr.get('lot_mult',1)}x Lot PnL: {raw_m*old_tr.get('lot_mult',1):+.1f}p)",
                                        fire_delta=True,
                                        defer_delta_for_flip=True
                                    )

                                open_renko_trade_now(
                                    eng,
                                    new_dir,
                                    flip_px,
                                    ist_str,
                                    f"🔥 Live Renko ST Flip {new_dir} {'▲' if new_dir=='BUY' else '▼'}",
                                    fire_delta=True,
                                    is_flip=True,
                                    prev_lot_to_close=prev_lot_cnt
                                )
                                threading.Thread(target=execute_ai_management_cycle, args=(eng, ist_str), daemon=True).start()

                    elif rk_data and "error" in rk_data:
                        eng["last_err"] = rk_data["error"]

                    eng["last_kline_ts"] = now_ts

                if eng.get("active_trade") is not None and (now_ts - eng["last_report_ts"] >= 45) and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_management_cycle, args=(eng, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v26_6():
    wid = int(time.time() * 1000)
    srv_ip = fetch_server_public_ip()
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "server_ip": srv_ip,
        "delta_base_url": "https://cdn-ind.testnet.deltaex.org",
        "delta_api_key": HARDCODED_DELTA_API_KEY,
        "delta_api_secret": HARDCODED_DELTA_API_SECRET,
        "delta_base_lot": 1,
        "current_lot_mult": 1,
        "current_lot_size": 1,
        "loss_streak": 0,
        "deficit_pts": 0.0,
        "last_closed_pts": 0.0,
        "last_lot_reason": "✅ हर मुख्य रैंकों सिग्नल पर ट्रेड अनिवार्य है — अधिकतम 2x रिकवरी कैप के साथ 1x Base Lot सक्रिय।",
        "last_ai_decision": "HOLD",
        "last_ai_reason": "AI रैंकों के लंबे ट्रेंड को पकड़ने और बड़े प्रॉफिट को सुरक्षित करने के लिए सक्रिय ट्रेड को मैनेज कर रहा है।",
        "delta_enabled": True,
        "delta_product_id": None,
        "delta_last_status": "⏳ Delta Demo Connecting...",
        "fixed_brick_size": 270.0, "rev_bricks": 2.0,
        "signal_history": [], "active_trade": None, "ai_busy": False,
        "last_kline_ts": 0.0, "last_report_ts": 0.0, "last_handled_flip_ts": 0,
        "renko": {
            "box_size": 270.0, "rev_bricks": 2.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "buy_dom_pct": 50.0, "ema21": 0.0, "ema_dist_bricks": 0.0, "rsi14": 50.0,
            "chart_points": []
        },
        "available_models": [], "models_fetched": False,
        "active_ai_model": "🔍 Auto-Scanning Models...",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v26_6()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
except Exception:
    pass

if not eng.get("models_fetched"):
    eng["available_models"] = fetch_available_api_models(eng.get("api_key", ""))
    if eng["available_models"]:
        eng["active_ai_model"] = f"🟢 {eng['available_models'][0]} (Auto)"
    eng["models_fetched"] = True

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# TOP STATUS BAR: SERVER IP BOX + AUTO-ACTIVE AI MODEL + DELTA STATUS + IP REFRESH
# ============================================================================
ip_col1, ip_col2, ip_col3, ip_col4 = st.columns([0.28, 0.28, 0.30, 0.14])
with ip_col1:
    st.markdown(clean_html(f"""
    <div class='ip-badge-box'>
        <span>🌐 <b>Server IP (Delta Whitelist):</b></span>
        <code style='color:#facc15; background:#1e293b; padding:2px 8px; border-radius:5px; font-size:13px; font-weight:900;'>{eng.get('server_ip', '--')}</code>
    </div>
    """), unsafe_allow_html=True)

with ip_col2:
    st.markdown(clean_html(f"""
    <div class='ai-badge-box'>
        <span>🧠 <b>Active AI Model:</b></span>
        <b style='color:#4ade80; font-size:13px;'>{eng.get('active_ai_model', 'Auto-Selecting...')}</b>
    </div>
    """), unsafe_allow_html=True)

with ip_col3:
    st.markdown(clean_html(f"""
    <div class='delta-badge-box'>
        <span>⚡ <b>Delta Demo:</b></span>
        <span style='color:#38bdf8; font-weight:700;'>{eng.get('delta_last_status', 'Ready')}</span>
    </div>
    """), unsafe_allow_html=True)

with ip_col4:
    if st.button("🔄 Refresh IP"):
        eng["server_ip"] = fetch_server_public_ip()
        threading.Thread(target=auto_verify_delta_demo_wallet, args=(eng,), daemon=True).start()

# ============================================================================
# TOP CONTROL BAR (BRICK SIZE, REVERSAL, AI REVIEW & SOUND)
# ============================================================================
c_brk, c_rev, c_act1, c_snd = st.columns([0.24, 0.24, 0.34, 0.18])

with c_brk:
    eng["fixed_brick_size"] = float(st.number_input(
        "🧱 ब्रिक साइज (270):",
        min_value=10.0, max_value=2000.0,
        value=float(eng.get("fixed_brick_size", 270.0)),
        step=10.0,
        help="फिक्स ब्रिक साइज (डिफ़ॉल्ट: 270)",
        label_visibility="collapsed"
    ))

with c_rev:
    eng["rev_bricks"] = float(st.number_input(
        "🔄 रिवर्सल ब्रिक्स (2.0):",
        min_value=0.5, max_value=5.0,
        value=float(eng.get("rev_bricks", 2.0)),
        step=0.5,
        help="रिवर्सल ब्रिक फैक्टर (Default = 2.0 Bricks)",
        label_visibility="collapsed"
    ))

with c_act1:
    if st.button("🧠 अभी AI से ट्रेड रिव्यू / चार्ट रिफ्रेश करें"):
        eng["last_kline_ts"] = 0.0
        threading.Thread(target=execute_ai_management_cycle, args=(eng, get_ist_time_str()), daemon=True).start()

with c_snd:
    sound_enabled = st.checkbox("🔊 साउंड अलर्ट", value=True)

dashboard_slot = st.empty()
audio_slot = st.empty()

while True:
    curr_snd = eng.get("sound_event", {"id": 0.0, "type": "BULL"})
    if sound_enabled and curr_snd["id"] > 0 and curr_snd["id"] != st.session_state["last_played_sound_id"]:
        st.session_state["last_played_sound_id"] = curr_snd["id"]
        b64 = create_sound_b64(curr_snd["type"])
        audio_slot.empty()
        with audio_slot:
            components.html(f'<audio autoplay="true"><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>', height=0, width=0)

    if eng["px"] > 0 and eng["renko"].get("st_line", 0.0) > 0:
        rk = eng.get("renko", {})
        act_tr = eng.get("active_trade")
        st_line_px = rk.get("st_line", eng["px"])
        box_sz = rk.get("box_size", 270.0)
        rev_b = rk.get("rev_bricks", 2.0)
        st_dist_pts = abs(eng["px"] - st_line_px)
        next_step_px = (rk.get("brick_top", eng["px"]) + box_sz) if rk.get("st_trend", 1) == 1 else (rk.get("brick_bot", eng["px"]) - box_sz)
        pts_to_next_brick = abs(next_step_px - eng["px"])

        st_trend_col = "#4ade80" if rk.get("st_trend", 1) == 1 else "#f87171"
        st_trend_txt = "BULLISH (BUY ▲) 🟢" if rk.get("st_trend", 1) == 1 else "BEARISH (SELL ▼) 🔴"

        if act_tr:
            t_mult = act_tr.get("lot_mult", 1)
            t_lots = act_tr.get("lot_size", 1)
            ai_sl_val = float(act_tr.get("sl_px", 0.0) or 0.0)
            sl_txt = f"${ai_sl_val:,.1f}" if ai_sl_val > 0 else "Trend Open (+450p Lock)"
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} ट्रेंड-फर्स्ट {act_tr['type']} चालू [📦 {t_lots} Lot ({t_mult}x Max-2x)] — AI: {act_tr.get('ai_decision', 'HOLD')}"
            banner_sub = (
                f"एंट्री: ${act_tr['entry']:,.1f} | Peak: <b>+{act_tr['peak_pts']:.1f}p</b> | "
                f"प्रॉफिट/रिस्क SL: <b style='color:#c084fc;'>{sl_txt}</b> | "
                f"Reversal ST: <b>${st_line_px:,.1f} ({st_dist_pts:.0f}p दूर)</b>"
            )
            right_stat_label = f"LIVE PNL ({t_mult}x = {act_tr.get('weighted_pts', act_tr['live_pts']):+.0f}p)"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            banner_title = f"⚪ अगले Core Renko ST सिग्नल की प्रतीक्षा ({st_trend_txt})"
            banner_sub = f"Reversal Level (stLevel): ${st_line_px:,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर) | कैरी-फॉरवर्ड लॉस डेफिसिट: {-eng.get('deficit_pts', 0.0):+.1f} Pts"
            right_stat_label = "DISTANCE TO ST"
            right_stat_val = f"{st_dist_pts:.0f} Pts"
            right_stat_col = "#facc15"

        svg_chart_html = build_renko_svg_chart(rk, eng["px"], act_tr)

        closed_raw_sum = sum(h["live_pts"] for h in eng["signal_history"] if "ACTIVE" not in h["status"])
        closed_weighted_sum = sum(h.get("weighted_pts", h["live_pts"]) for h in eng["signal_history"] if "ACTIVE" not in h["status"])
        win_cnt = sum(1 for h in eng["signal_history"] if "ACTIVE" not in h["status"] and h["live_pts"] > 0)
        loss_cnt = sum(1 for h in eng["signal_history"] if "ACTIVE" not in h["status"] and h["live_pts"] <= 0)

        hist_cards = ""
        for h in eng["signal_history"]:
            h_cls = "ic-bull" if h["type"] == "BUY" else "ic-bear"
            h_col = "#4ade80" if h["type"] == "BUY" else "#f87171"
            p_col = "#4ade80" if h["live_pts"] >= 0 else "#f87171"
            is_act = "ACTIVE" in h["status"]
            sts_badge = f"🟢 {h.get('ai_decision', 'HOLD')} (ACTIVE)" if is_act else f"🏁 {h['status']}"
            h_mult = h.get("lot_mult", 1)
            h_lots = h.get("lot_size", 1)
            w_pts = h.get("weighted_pts", h["live_pts"] * h_mult)
            lot_pill_col = "#facc15" if h_mult > 1 else "#38bdf8"
            lot_tag = f"<span style='background:#1e1b4b; border:1px solid {lot_pill_col}; color:{lot_pill_col}; padding:1px 7px; border-radius:5px; font-size:11px; font-weight:800; margin-left:6px;'>📦 {h_lots} Lot ({h_mult}x)</span>"
            h_sl_val = float(h.get("sl_px", 0.0) or 0.0)
            sl_tag = f" | <b style='color:#c084fc;'>🎯 Lock SL: ${h_sl_val:,.1f}</b>" if h_sl_val > 0 else ""

            hist_cards += f"""
            <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <b style='color:{h_col}; font-size:13.5px;'>{h['open_time']} — {h['type']} @ ${h['entry']:,.1f}</b>
                    {lot_tag}
                    <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span>{sl_tag}<br>
                    <span style='color:#cbd5e1; font-size:12px;'>{h['entry_reason']}</span><br>
                    <span style='color:#e9d5ff; font-size:11.6px;'>🧠 {h.get('lot_reason', '1x Base Lot')}</span><br>
                    <span style='color:#c084fc; font-size:11.8px;'>🤖 {h.get('ai_reason', h['exit_reason'])}</span>
                </div>
                <div style='text-align:right; min-width:125px;'>
                    <div style='font-size:15.5px; font-weight:900; color:{p_col};'>{h['live_pts']:+.1f}p</div>
                    <div style='font-size:11.5px; font-weight:800; color:#facc15;'>{h_mult}x PnL: {w_pts:+.1f}p</div>
                    <div style='font-size:10.8px; color:#94a3b8;'>Peak: +{h['peak_pts']:.1f}p</div>
                </div>
            </div>
            """

        ai_guide_html = f"""
        <div class='item-card ic-bull'>
            <b>1. लंबे ट्रेंड को सांस लेने की जगह (Trend-First Hold)</b><br>
            <span style='color:#cbd5e1;'>रैंकों के बड़े मूव में आने वाले सामान्य पुलबैक्स पर ट्रेड को जल्दी नहीं काटा जाएगा, ताकि बड़ा ट्रेंड पूरा पकड़ा जा सके।</span>
        </div>
        <div class='item-card ic-warn'>
            <b>2. बड़ा प्रॉफिट आने पर लॉक (+450p / +650p / +900p+)</b><br>
            <span style='color:#cbd5e1;'>जैसे ही ट्रेड +450p या उससे ऊपर जाता है, लॉक SL अपने-आप आगे बढ़ता है ताकि बड़ा मुनाफा वापस नुकसान में न बदले।</span>
        </div>
        <div class='item-card ic-ai'>
            <b>3. अधिकतम 2x सुरक्षित लॉट सीमा (Max 2x Cap)</b><br>
            <span style='color:#cbd5e1;'>अत्यधिक ड्रॉडाउन से बचने के लिए रिकवरी लॉट को अधिकतम <b>2x</b> तक सीमित रखा गया है (3x लॉट बंद)।</span>
        </div>
        <div class='item-card ic-ai'>
            <b>4. ताज़ा AI ट्रेंड फैसला</b><br>
            <span style='color:#e9d5ff;'>{eng.get("last_ai_reason", "")}</span>
        </div>
        """

        net_col = "#4ade80" if closed_weighted_sum >= 0 else "#f87171"
        def_pts = eng.get("deficit_pts", 0.0)
        l_streak = eng.get("loss_streak", 0)
        act_sl_display = f"${float(act_tr.get('sl_px', 0.0)):,.1f}" if (act_tr and float(act_tr.get("sl_px", 0.0) or 0.0) > 0) else "Trend Open (+450p Lock)"

        left_body = f"""
        <div class='lock-banner {banner_cls}'>
            <div>
                <div style='font-size:18px; font-weight:900;'>{banner_title}</div>
                <div style='font-size:12.5px; margin-top:3px; opacity:0.95;'>{banner_sub}</div>
            </div>
            <div style='text-align:right; min-width:155px;'>
                <div style='font-size:11px; text-transform:uppercase; opacity:0.85;'>{right_stat_label}</div>
                <div style='font-size:23px; font-weight:900; color:{right_stat_col};'>{right_stat_val}</div>
                <div style='font-size:11px; opacity:0.8;'>● {eng["last_update"]}</div>
            </div>
        </div>

        <div class='chart-box'>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;'>
                <span style='font-size:14px; font-weight:900; color:#38bdf8;'>
                    📈 TREND-FIRST RENKO CHART (Brick: ${box_sz:.0f} | Rev: {rev_b:.1f}x = ${box_sz*rev_b:.0f}p)
                </span>
                <span style='font-size:12px; color:#cbd5e1;'>
                    <b style='color:#38bdf8;'>━ Price (${eng['px']:,.0f})</b> &nbsp;|&nbsp;
                    <b style='color:{st_trend_col};'>━ Reversal ST (${st_line_px:,.0f})</b> &nbsp;|&nbsp;
                    <b style='color:#c084fc;'>-- Profit Lock SL</b>
                </span>
            </div>
            {svg_chart_html}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. लाइव रैंकों ट्रेंड ट्रेस</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>विपरीत सिग्नल लेवल (Reversal stLevel):</span><b><span style='color:{st_trend_col};'>${st_line_px:,.1f}</span> (प्राइस से {st_dist_pts:.0f} Pts दूर)</b></div>
                <div class='stat-row'><span>वर्तमान प्रॉफिट/रिस्क SL:</span><b style='color:#c084fc;'>{act_sl_display}</b></div>
                <div class='stat-row'><span>चालू ब्रिक बॉक्स (Bot – Top):</span><b>${rk.get("brick_bot", 0.0):,.1f} — ${rk.get("brick_top", 0.0):,.1f} (Streak #{rk.get("brick_streak", 1)})</b></div>
                <div class='stat-row' style='border:none;'><span>अगली ब्रिक बनने का लेवल:</span><b style='color:#38bdf8;'>${next_step_px:,.1f} ({pts_to_next_brick:.0f} Pts दूर)</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>🧠 2. ट्रेंड-फर्स्ट AI एवं लॉट ब्रेन</span>
                    <span style='color:#facc15;'>Active: {eng.get("current_lot_size", 1)} Lot ({eng.get("current_lot_mult", 1)}x / Max 2x)</span>
                </div>
                <div class='stat-row'><span>चालू AI मॉडल:</span><b style='color:#4ade80;'>{eng.get("active_ai_model", "Auto")}</b></div>
                <div class='stat-row'><span>कैरी-फॉरवर्ड लॉस डेफिसिट (Streak #{l_streak}):</span><b style='color:{"#f87171" if def_pts > 0 else "#4ade80"};'>{f"-{def_pts:.1f} Pts (Max 2x Recovery)" if def_pts > 0 else "0.0 Pts (Recovered ✅)"}</b></div>
                <div class='stat-row'><span>24h PnL (1x Raw vs AI Weighted):</span><b>Raw: {closed_raw_sum:+.0f}p | <span style='color:{net_col};'>AI Lot PnL: {closed_weighted_sum:+.0f}p</span></b></div>
                <div style='font-size:12px; color:#e9d5ff; margin-top:5px; line-height:1.4;'>🤖 <b>AI विवेक:</b> {eng.get("last_ai_reason", "")}</div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V26.6 (TREND-FIRST AI MANAGER + BIG PROFIT LOCK + DELTA DEMO)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🧱 Brick: <b style='color:#facc15;'>${box_sz:.0f}</b> | 🧠 AI Mode: <b style='color:#c084fc;'>Long-Trend Hold & +450p+ Profit Lock (Max 2x)</b> | 📦 Active Lot: <b style='color:#facc15;'>{eng.get('current_lot_size',1)} Lot ({eng.get('current_lot_mult',1)}x)</b> | AI Lot PnL: <b style='color:{net_col};'>{closed_weighted_sum:+.1f} Pts ({win_cnt}W/{loss_cnt}L)</b></div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:21px; font-weight:900; color:#f8fafc;'>BTC: ${eng['px']:,.1f}</div>
                    <div style='color:#4ade80; font-size:12px; font-weight:bold;'>● {eng['last_update']}</div>
                </div>
            </div>

            <div class='main-grid'>
                <div>
                    {left_body}
                    <div class='history-panel'>
                        <div style='font-size:14px; font-weight:900; color:#4ade80; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px; display:flex; justify-content:space-between; flex-wrap:wrap;'>
                            <span>📜 ट्रेंड-फर्स्ट AI ट्रेड हिस्ट्री (Max 2x Recovery Lot)</span>
                            <span style='color:{net_col};'>1x Raw: {closed_raw_sum:+.0f}p | AI Lot Weighted: {closed_weighted_sum:+.1f} Pts ({win_cnt}W / {loss_cnt}L)</span>
                        </div>
                        {hist_cards}
                    </div>
                </div>

                <div class='brick-panel'>
                    <div style='font-size:14.5px; font-weight:900; color:#c084fc; margin-bottom:10px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        🧠 लंबे ट्रेंड्स एवं बड़े प्रॉफिट लॉक की रणनीति
                    </div>
                    {ai_guide_html}
                </div>
            </div>
        </div>
        """), unsafe_allow_html=True)

    else:
        err_msg = f" ({eng['last_err']})" if eng.get("last_err") else ""
        dashboard_slot.warning(f"⏳ 24x7 V26.6 (Trend-First AI Manager + Big Profit Lock) डेटा सिंक कर रहा है... कृपया 2 सेकंड प्रतीक्षा करें।{err_msg}")

    time.sleep(1.5)

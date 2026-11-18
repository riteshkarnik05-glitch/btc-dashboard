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

st.set_page_config(page_title="Pro Quant V26.1 - +300p/+500p Hybrid + AI Lot + Delta Demo", layout="wide")

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
.ip-badge-box { background: #0f172a; border: 1px solid #facc15; border-left: 4px solid #facc15; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; }
.delta-badge-box { background: #0f172a; border: 1px solid #38bdf8; border-left: 4px solid #22c55e; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; }
.lot-badge-box { background: #1e1b4b; border: 1px solid #c084fc; border-left: 4px solid #facc15; padding: 6px 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: #f8fafc; }
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
.brick-panel { background: #111827; border: 1px solid #334155; border-top: 3px solid #facc15; border-radius: 10px; padding: 12px 14px; height: 995px; overflow-y: auto; }
.item-card { background: #090d16; border: 1px solid #1f2937; padding: 9px 11px; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; line-height: 1.45; }
.ic-bull { border-left: 4px solid #22c55e; }
.ic-bear { border-left: 4px solid #ef4444; }
.ic-warn { border-left: 4px solid #facc15; }
.ic-active-stage { background: #172554; border: 1px solid #38bdf8; border-left: 5px solid #facc15; }
div.stButton > button { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #38bdf8 !important; border-radius: 7px !important; font-weight: 700 !important; width: 100%; margin-top: 2px; }
div.stButton > button:hover { background-color: #38bdf8 !important; color: #090d16 !important; }
div[data-baseweb="select"] > div { background-color: #1e293b !important; color: #f8fafc !important; border: 1px solid #c084fc !important; border-radius: 7px !important; font-weight: 700 !important; }
div[data-baseweb="input"] > div { background-color: #1e293b !important; color: #facc15 !important; border: 1px solid #facc15 !important; border-radius: 7px !important; font-weight: 800 !important; }
input[type="number"], input[type="text"], input[type="password"] { color: #facc15 !important; font-weight: 800 !important; }
</style>
"""), unsafe_allow_html=True)

# ============================================================================
# SERVER PUBLIC IP FETCHER & DELTA EXCHANGE DEMO API EXECUTION ENGINE
# ============================================================================
DELTA_ENV_URLS = {
    "🇮🇳 Delta India Testnet (Demo)": "https://cdn-ind.testnet.deltaex.org",
    "🌐 Delta Global Testnet (Demo)": "https://testnet-api.delta.exchange"
}

def fetch_server_public_ip() -> str:
    """Fetches the server's public outbound IPv4 address for Delta API whitelisting"""
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

def place_delta_demo_order(eng: dict, side: str, size: int, reduce_only: bool = False, note: str = ""):
    """Fires a Market Order on Delta Exchange Demo (Testnet) with the exact AI-decided lot size"""
    if not eng.get("delta_enabled", False):
        return
    api_key = eng.get("delta_api_key", "").strip()
    api_secret = eng.get("delta_api_secret", "").strip()
    if not api_key or not api_secret:
        eng["delta_last_status"] = f"⚠️ Delta Keys खाली हैं ({note}: {size} Lot Skipped)"
        return

    def _order_worker():
        try:
            base_url = DELTA_ENV_URLS.get(eng.get("delta_env"), "https://cdn-ind.testnet.deltaex.org")
            prod_id = get_delta_btc_product_id(base_url, eng.get("delta_product_id"))
            eng["delta_product_id"] = prod_id

            path = "/v2/orders"
            timestamp = str(int(time.time()))
            body_dict = {
                "product_id": int(prod_id),
                "size": int(max(1, size)),
                "side": side.lower(),
                "order_type": "market_order"
            }
            if reduce_only:
                body_dict["reduce_only"] = True

            payload_str = json.dumps(body_dict, separators=(",", ":"))
            sig = generate_delta_signature(api_secret, "POST", timestamp, path, "", payload_str)

            headers = {
                "api-key": api_key,
                "timestamp": timestamp,
                "signature": sig,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "pro-quant-v26-1-bot"
            }

            res = requests.post(f"{base_url}{path}", data=payload_str, headers=headers, timeout=6.0)
            ist_now = get_ist_time_str()
            if res.status_code == 200 and res.json().get("success"):
                ord_data = res.json().get("result", {})
                ord_id = ord_data.get("id", "OK")
                eng["delta_last_status"] = f"🟢 Delta {side.upper()} ({size} Lot) OK [ID:{ord_id}] @ {ist_now} ({note})"
            else:
                err_txt = res.text[:85]
                eng["delta_last_status"] = f"🔴 Delta Error ({res.status_code}): {err_txt}"
        except Exception as e:
            eng["delta_last_status"] = f"🔴 Delta Exception: {str(e)[:70]}"

    threading.Thread(target=_order_worker, daemon=True).start()

def check_delta_demo_wallet(eng: dict):
    api_key = eng.get("delta_api_key", "").strip()
    api_secret = eng.get("delta_api_secret", "").strip()
    if not api_key or not api_secret:
        eng["delta_last_status"] = "⚠️ कृपया पहले Delta Demo API Key और Secret दर्ज करें।"
        return

    try:
        base_url = DELTA_ENV_URLS.get(eng.get("delta_env"), "https://cdn-ind.testnet.deltaex.org")
        path = "/v2/wallet/balances"
        timestamp = str(int(time.time()))
        sig = generate_delta_signature(api_secret, "GET", timestamp, path, "", "")
        headers = {
            "api-key": api_key,
            "timestamp": timestamp,
            "signature": sig,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "pro-quant-v26-1-bot"
        }
        r = requests.get(f"{base_url}{path}", headers=headers, timeout=5.0)
        if r.status_code == 200 and r.json().get("success"):
            bals = r.json().get("result", [])
            usdt_bal = 0.0
            for b in bals:
                if b.get("asset_symbol") in ["USDT", "USD", "BTC"]:
                    usdt_bal = max(usdt_bal, float(b.get("available_balance", 0.0)))
            eng["delta_last_status"] = f"🟢 Delta Connected! Balance: ${usdt_bal:,.2f} ({get_ist_time_str()})"
        else:
            eng["delta_last_status"] = f"🔴 Auth Error ({r.status_code}): {r.text[:85]}"
    except Exception as e:
        eng["delta_last_status"] = f"🔴 Connection Error: {str(e)[:70]}"

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
# LIVE GEMINI API MODEL DISCOVERY (PRO-MODEL PRIORITY)
# ============================================================================
AUTO_MODEL_LABEL = "🤖 Auto (Pro/Advanced Priority)"

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
        "gemini-1.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
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

# ============================================================================
# AI DYNAMIC LOSS-RECOVERY & LOT SIZING ENGINE (MANDATORY ENTRY ON EVERY SIGNAL)
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
    """
    Intelligent Quant Fallback Brain for Dynamic Recovery Lot Multiplier (1x, 2x, or 3x):
    - NEVER skips a Renko signal (minimum multiplier = 1).
    - Resets to 1x when there is no pending loss deficit or after a profitable recovery.
    - Can scale up to 2x or 3x even after a SINGLE loss if momentum supports recovery!
    """
    if deficit_pts <= 0 or loss_streak <= 0:
        return 1, "✅ पिछला कोई पेंडिंग लॉस नहीं है — स्टैंडर्ड 1x Base Lot से ट्रेड लिया गया।"

    fav_dom = buy_dom_pct if new_dir == "BUY" else (100.0 - buy_dom_pct)
    fav_rsi = (52.0 <= rsi14 <= 72.0) if new_dir == "BUY" else (28.0 <= rsi14 <= 48.0)
    healthy_stretch = ema_dist_bricks <= 2.3

    if (deficit_pts >= 450.0 or loss_streak >= 2) and fav_dom >= 60.0 and fav_rsi and healthy_stretch:
        return 3, f"🔥 AI रिकवरी स्ट्राइक (3x Lot): पेंडिंग लॉस (-{deficit_pts:.0f}p) को एक ही ट्रेंड में कवर करने और तगड़े मोमेंटम ({fav_dom:.0f}% Power, RSI {rsi14:.0f}) को देखते हुए क्वांटिटी 3 गुना की गई!"
    elif fav_dom >= 53.0 and healthy_stretch:
        return 2, f"⚡ AI स्मार्ट रिकवरी (2x Lot): पिछले लॉस (-{deficit_pts:.0f}p, Streak #{loss_streak}) को तेज़ी से कवर करने के लिए अनुकूल मोमेंटम ({fav_dom:.0f}% Power) देखकर क्वांटिटी 2 गुना की गई।"
    else:
        return 1, f"🛡️ सेफ सिग्नल एंट्री (1x Lot): पेंडिंग लॉस -{deficit_pts:.0f}p है, लेकिन अभी मोमेंटम धीमा ({fav_dom:.0f}% Power) है, इसलिए रैंकों सिग्नल अनिवार्य रूप से 1x Base Lot पर लिया गया।"

def decide_next_lot_multiplier_with_ai(eng: dict, new_dir: str, loss_streak: int, deficit_pts: float, last_closed_pts: float) -> tuple:
    rk = eng.get("renko", {})
    rsi14 = rk.get("rsi14", 50.0)
    buy_dom = rk.get("buy_dom_pct", 50.0)
    ema_bricks = rk.get("ema_dist_bricks", 0.5)

    if deficit_pts <= 0 or loss_streak <= 0:
        return 1, "✅ प्रॉफिट रीसेट: पिछला कोई पेंडिंग लॉस नहीं है — 1x Base Lot सेट किया गया।"

    api_key = eng.get("api_key", "").strip()
    if not api_key:
        return quant_fallback_lot_sizer(new_dir, loss_streak, deficit_pts, last_closed_pts, rsi14, buy_dom, ema_bricks)

    fav_dom = buy_dom if new_dir == "BUY" else (100.0 - buy_dom)
    prompt = f"""
You are an Elite Institutional Risk & Drawdown-Recovery Manager for an automated BTCUSDT Renko Supertrend trading bot.
A new confirmed Renko Supertrend `{new_dir}` signal has just triggered!

STRICT NON-NEGOTIABLE DIRECTIVES:
1. MANDATORY TRADE EXECUTION: Every Renko signal MUST be taken without exception. You can NEVER output `0` lots or skip a signal. Minimum multiplier is `1` (1x Base Lot).
2. NO 2-LOSS WAIT RESTRICTION: Even after a SINGLE loss (`loss_streak == 1`), you have full authority to increase the lot multiplier to `2` or `3` if you judge that the new signal has good momentum to recover the previous loss quickly.
3. PRIMARY GOAL — LOSS RECOVERY: Your main goal is to recover the `Unrecovered Loss Deficit` (-{deficit_pts:.1f} pts) smartly using your intelligence:
   - Choose `1` (1x Base Lot) if current market momentum looks choppy, exhausted, or weak (so we take the mandatory signal safely without over-risking).
   - Choose `2` (2x Base Lot) if momentum is supportive and we want to recover the previous loss efficiently.
   - Choose `3` (3x Base Lot, Maximum Safety Cap) if the unrecovered deficit is significant AND orderflow/RSI momentum is strong for a breakout trend run.

CURRENT LOSS & MOMENTUM DATA FOR NEW `{new_dir}` SIGNAL:
- Consecutive Losses (`loss_streak`): {loss_streak}
- Last Closed Trade PnL: {last_closed_pts:+.1f} Points
- Total Unrecovered Loss Deficit to Recover: -{deficit_pts:.1f} Points
- Favorable 3-Bar Orderflow Power for `{new_dir}`: {fav_dom:.1f}%
- 14-Period RSI: {rsi14:.1f}
- 21-EMA Stretch (in Renko Bricks): {ema_bricks:.2f} Bricks (Healthy if < 2.2)

Return ONLY valid JSON:
{{
  "lot_multiplier": integer (MUST be 1, 2, or 3),
  "sizing_reason": "Sharp 1-line explanation in Hindi of why you chose 1x, 2x, or 3x lot size to handle this mandatory Renko signal and recover the -{deficit_pts:.0f}p deficit"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 220}
    }

    selected_model = eng.get("selected_model", AUTO_MODEL_LABEL)
    pro_first = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
    models_queue = [selected_model] + [m for m in pro_first if m != selected_model] if (selected_model and selected_model != AUTO_MODEL_LABEL) else pro_first

    for mod in models_queue[:3]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=4.5)
            if res.status_code == 200:
                parsed = parse_ai_json_safely(res.json()['candidates'][0]['content']['parts'][0]['text'].strip())
                if parsed and "lot_multiplier" in parsed:
                    mult = max(1, min(3, int(parsed["lot_multiplier"])))
                    reason = str(parsed.get("sizing_reason", "")).strip()
                    if reason:
                        return mult, f"🤖 AI Lot Brain ({mult}x): {reason}"
        except Exception:
            continue

    return quant_fallback_lot_sizer(new_dir, loss_streak, deficit_pts, last_closed_pts, rsi14, buy_dom, ema_bricks)

# ============================================================================
# SMART HYBRID PROFIT PROTECTION CALCULATOR (UPDATED TO +300p / +500p / +900p)
# ============================================================================
def compute_hybrid_protection(entry_px: float, peak_pts: float, trade_type: str, st_line: float) -> dict:
    """
    Computes the Updated Smart Hybrid Profit-Locking Stage & Protected Stop-Loss Price:
    - Phase 1 (Peak < +300p): Pure Signal-to-Signal (Exit ONLY on Renko ST Flip at stLevel).
    - Phase 2 (Peak +300p to +499p): Breakeven+ Shield (Locks max(+120p, Peak - 180p) so +300p never turns into a loss!).
    - Phase 3 (Peak +500p to +899p): Big Profit Lock (Trails 140p behind Peak, locking +360p to +759p).
    - Phase 4 (Peak >= +900p): Parabolic Tight Lock (Trails 110p behind Peak, locking +790p to +2700p+).
    """
    if peak_pts < 300.0:
        return {
            "phase": 1,
            "phase_name": "PHASE 1: PURE SIGNAL-TO-SIGNAL (< +300p)",
            "shield_active": False,
            "locked_pts": 0.0,
            "protect_sl": st_line,
            "gap_from_peak": 0.0,
            "rule_hi": f"Peak (+{peak_pts:.0f}p) अभी +300p से कम है — कोई बीच का SL नहीं, केवल Reversal ST (${st_line:,.1f}) पर ही ट्रेड पलटेगा।"
        }
    elif peak_pts < 500.0:
        gap = 180.0
        locked_pts = round(max(120.0, peak_pts - gap), 1)
        prot_sl = round(entry_px + locked_pts, 1) if trade_type == "BUY" else round(entry_px - locked_pts, 1)
        return {
            "phase": 2,
            "phase_name": "PHASE 2: BREAKEVEN+ SHIELD (+300p–500p)",
            "shield_active": True,
            "locked_pts": locked_pts,
            "protect_sl": prot_sl,
            "gap_from_peak": round(peak_pts - locked_pts, 1),
            "rule_hi": f"🛡️ +300p शील्ड ऑन! अब यह ट्रेड नुकसान में नहीं जा सकता — कम से कम +{locked_pts:.1f} Pts (${prot_sl:,.1f}) पक्का लॉक।"
        }
    elif peak_pts < 900.0:
        gap = 140.0
        locked_pts = round(max(360.0, peak_pts - gap), 1)
        prot_sl = round(entry_px + locked_pts, 1) if trade_type == "BUY" else round(entry_px - locked_pts, 1)
        return {
            "phase": 3,
            "phase_name": "PHASE 3: BIG PROFIT LOCK (+500p–900p)",
            "shield_active": True,
            "locked_pts": locked_pts,
            "protect_sl": prot_sl,
            "gap_from_peak": gap,
            "rule_hi": f"🚀 +500p बिग प्रॉफिट लॉक सक्रिय! Peak (+{peak_pts:.0f}p) से सिर्फ 140p पीछे +{locked_pts:.1f} Pts (${prot_sl:,.1f}) लॉक।"
        }
    else:
        gap = 110.0
        locked_pts = round(max(790.0, peak_pts - gap), 1)
        prot_sl = round(entry_px + locked_pts, 1) if trade_type == "BUY" else round(entry_px - locked_pts, 1)
        return {
            "phase": 4,
            "phase_name": "PHASE 4: PARABOLIC TIGHT LOCK (+900p+)",
            "shield_active": True,
            "locked_pts": locked_pts,
            "protect_sl": prot_sl,
            "gap_from_peak": gap,
            "rule_hi": f"🔥 +900p+ पैराबोलिक लॉक! Peak (+{peak_pts:.0f}p) से 110p टाइट गैप पर +{locked_pts:.1f} Pts (${prot_sl:,.1f}) पक्का लॉक!"
        }

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
    if active_tr and active_tr.get("shield_active") and active_tr.get("protect_sl", 0) > 0:
        all_y.append(active_tr["protect_sl"])

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

    shield_svg = ""
    if active_tr and active_tr.get("shield_active") and active_tr.get("protect_sl", 0) > 0:
        y_sh = to_y(active_tr["protect_sl"])
        shield_svg = (
            f"<line x1='{pad_l}' y1='{y_sh:.1f}' x2='{w - pad_r}' y2='{y_sh:.1f}' stroke='#facc15' stroke-dasharray='6,3' stroke-width='2.0'/>"
            f"<rect x='{w - pad_r + 2}' y='{y_sh - 9:.1f}' width='80' height='18' rx='4' fill='#facc15'/>"
            f"<text x='{w - pad_r + 42}' y='{y_sh + 4:.1f}' fill='#090d16' font-size='10' font-weight='bold' text-anchor='middle'>Lock ${active_tr['protect_sl']:,.0f}</text>"
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
        {shield_svg}
        {price_poly}
        {markers_svg}
        {live_tags}
    </svg>
    """

# ============================================================================
# CORE ARCHITECTURE: SYNTHETIC RENKO SUPERTREND + AI RECOVERY LOT TRACKER
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

def fetch_core_renko_supertrend(fixed_brick_size: float = 270.0, rev_bricks: float = 2.0, allow_pullback_reentry: bool = False, base_lot: int = 1):
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

        brick_events = []
        hybrid_trades = []
        chart_points = []
        sim_reentry_armed = False
        sim_reentry_dir = 0

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
                if sim_deficit_pts == 0.0 or raw_pts >= 120.0:
                    sim_loss_streak = 0
                    sim_deficit_pts = 0.0

        for i in range(1, len(closes)):
            c = closes[i]
            h_bar = highs[i]
            l_bar = lows[i]
            prev_trend = trend
            prev_st_level = st_level
            stepped_bricks = 0
            flipped_now = False

            if trend == 1:
                if c >= brick_top + brick_size:
                    steps = int(math.floor((c - brick_top) / brick_size))
                    brick_top = brick_top + (steps * brick_size)
                    brick_bot = brick_top - brick_size
                    brick_streak += steps
                    stepped_bricks = steps

                raw_support = brick_top - rev_dist
                st_level = max(raw_support, prev_st_level)

                if c < st_level:
                    trend = -1
                    down_steps = max(1, int(math.floor((brick_top - c) / brick_size)))
                    brick_bot = brick_top - (down_steps * brick_size)
                    brick_top = brick_bot + brick_size
                    st_level = brick_bot + rev_dist
                    brick_streak = down_steps
                    flipped_now = True

            elif trend == -1:
                if c <= brick_bot - brick_size:
                    steps = int(math.floor((brick_bot - c) / brick_size))
                    brick_bot = brick_bot - (steps * brick_size)
                    brick_top = brick_bot + brick_size
                    brick_streak += steps
                    stepped_bricks = steps

                raw_res = brick_bot + rev_dist
                st_level = min(raw_res, prev_st_level)

                if c > st_level:
                    trend = 1
                    up_steps = max(1, int(math.floor((c - brick_bot) / brick_size)))
                    brick_top = brick_bot + (up_steps * brick_size)
                    brick_bot = brick_top - brick_size
                    st_level = brick_top - rev_dist
                    brick_streak = up_steps
                    flipped_now = True

            bar_buy_sig = (trend == 1 and prev_trend == -1)
            bar_sell_sig = (trend == -1 and prev_trend == 1)
            b_ist_short = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
            b_ist_full = (datetime.utcfromtimestamp(bar_times[i] / 1000.0) + timedelta(hours=5, minutes=30)).strftime('%I:%M:%S %p')

            if hybrid_trades and "ACTIVE" in hybrid_trades[-1]["status"] and not (bar_buy_sig or bar_sell_sig):
                cur_t = hybrid_trades[-1]
                if cur_t.get("shield_active"):
                    prot_sl = cur_t["protect_sl"]
                    hit_shield = (l_bar <= prot_sl) if cur_t["type"] == "BUY" else (h_bar >= prot_sl)
                    if hit_shield:
                        booked_pts = cur_t["locked_pts"]
                        cur_t["live_pts"] = round(booked_pts, 1)
                        cur_t["close_time"] = b_ist_full
                        cur_t["status"] = f"HYBRID PHASE {cur_t['phase']} LOCK @ ${prot_sl:,.1f} ({b_ist_short})"
                        cur_t["exit_reason"] = (
                            f"🛡️ स्मार्ट हाइब्रिड लॉक हिट! Peak +{cur_t['peak_pts']:.1f}p से पलटने पर ST फ्लिप का इंतज़ार किए बिना "
                            f"${prot_sl:,.1f} पर +{booked_pts:.1f} Pts सुरक्षित बुक किए गए!"
                        )
                        _record_closed_trade_outcome(cur_t)
                        if allow_pullback_reentry and abs(prot_sl - st_level) >= 240.0:
                            sim_reentry_armed = True
                            sim_reentry_dir = 1 if cur_t["type"] == "BUY" else -1

                if "ACTIVE" in cur_t["status"]:
                    fav_px = h_bar if cur_t["type"] == "BUY" else l_bar
                    cur_fav = (fav_px - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - fav_px)
                    cur_t["peak_pts"] = round(max(cur_t["peak_pts"], cur_fav), 1)
                    cur_t["live_pts"] = round((c - cur_t["entry"]) if cur_t["type"] == "BUY" else (cur_t["entry"] - c), 1)
                    cur_t["weighted_pts"] = round(cur_t["live_pts"] * cur_t.get("lot_mult", 1), 1)

                    hyb = compute_hybrid_protection(cur_t["entry"], cur_t["peak_pts"], cur_t["type"], st_level)
                    cur_t["phase"] = hyb["phase"]
                    cur_t["phase_name"] = hyb["phase_name"]
                    if hyb["shield_active"]:
                        cur_t["shield_active"] = True
                        if cur_t["type"] == "BUY":
                            cur_t["protect_sl"] = max(cur_t.get("protect_sl", 0.0), hyb["protect_sl"])
                            cur_t["locked_pts"] = round(cur_t["protect_sl"] - cur_t["entry"], 1)
                        else:
                            old_psl = cur_t.get("protect_sl", 999999.0)
                            cur_t["protect_sl"] = min(old_psl if old_psl > 0 else 999999.0, hyb["protect_sl"])
                            cur_t["locked_pts"] = round(cur_t["entry"] - cur_t["protect_sl"], 1)
                    else:
                        cur_t["protect_sl"] = st_level

            if allow_pullback_reentry and sim_reentry_armed and not (bar_buy_sig or bar_sell_sig):
                if sim_reentry_dir != trend:
                    sim_reentry_armed = False
                else:
                    re_dir = "BUY" if sim_reentry_dir == 1 else "SELL"
                    re_cond = (st_level + 20.0 <= l_bar <= st_level + 95.0 and c > st_level + 25.0) if sim_reentry_dir == 1 else (st_level - 95.0 <= h_bar <= st_level - 20.0 and c < st_level - 25.0)
                    if re_cond:
                        sim_reentry_armed = False
                        eb_now = abs(c - ema_arr[i]) / max(1.0, brick_size)
                        m_mult, m_reason = quant_fallback_lot_sizer(re_dir, sim_loss_streak, sim_deficit_pts, sim_last_closed_pts, rsi_arr[i], dom_arr[i], eb_now)
                        hybrid_trades.append({
                            "open_ts": bar_times[i] / 1000.0,
                            "open_time": b_ist_full,
                            "close_time": "",
                            "type": re_dir,
                            "entry": round(c, 1),
                            "lot_mult": m_mult,
                            "lot_size": base_lot_int * m_mult,
                            "lot_reason": m_reason,
                            "live_pts": 0.0,
                            "weighted_pts": 0.0,
                            "peak_pts": 0.0,
                            "phase": 1,
                            "phase_name": "PHASE 1: PURE SIGNAL-TO-SIGNAL",
                            "shield_active": False,
                            "locked_pts": 0.0,
                            "protect_sl": round(st_level, 1),
                            "status": "ACTIVE (HYBRID RE-ENTRY)",
                            "entry_reason": f"🔄 ST Pullback Re-Entry {re_dir} (Brick: ${brick_size:.0f} | ST: ${st_level:,.1f})",
                            "exit_reason": "चालू है — +300p पर Breakeven Shield और +500p पर Peak Lock ऑन होगा"
                        })

            if bar_buy_sig or bar_sell_sig:
                last_flip_bar_ts = bar_times[i]
                last_flip_price = c
                last_flip_time_str = b_ist_full
                sig_dir = "BUY" if bar_buy_sig else "SELL"
                sim_reentry_armed = False

                if hybrid_trades and "ACTIVE" in hybrid_trades[-1]["status"]:
                    prev_tr = hybrid_trades[-1]
                    move_pts = (c - prev_tr["entry"]) if prev_tr["type"] == "BUY" else (prev_tr["entry"] - c)
                    prev_tr["live_pts"] = round(move_pts, 1)
                    prev_tr["peak_pts"] = round(max(prev_tr["peak_pts"], move_pts), 1)
                    prev_tr["close_time"] = b_ist_full
                    prev_tr["status"] = f"FLIPPED TO {sig_dir} @ ${c:,.1f} ({b_ist_short})"
                    prev_tr["exit_reason"] = f"विपरीत {sig_dir} सिग्नल आने पर ${c:,.1f} पर बंद हुआ (Raw: {move_pts:+.1f}p | {prev_tr.get('lot_mult',1)}x Lot PnL: {move_pts*prev_tr.get('lot_mult',1):+.1f}p)"
                    _record_closed_trade_outcome(prev_tr)

                eb_now = abs(c - ema_arr[i]) / max(1.0, brick_size)
                m_mult, m_reason = quant_fallback_lot_sizer(sig_dir, sim_loss_streak, sim_deficit_pts, sim_last_closed_pts, rsi_arr[i], dom_arr[i], eb_now)

                hybrid_trades.append({
                    "open_ts": bar_times[i] / 1000.0,
                    "open_time": b_ist_full,
                    "close_time": "",
                    "type": sig_dir,
                    "entry": round(c, 1),
                    "lot_mult": m_mult,
                    "lot_size": base_lot_int * m_mult,
                    "lot_reason": m_reason,
                    "live_pts": 0.0,
                    "weighted_pts": 0.0,
                    "peak_pts": 0.0,
                    "phase": 1,
                    "phase_name": "PHASE 1: PURE SIGNAL-TO-SIGNAL",
                    "shield_active": False,
                    "locked_pts": 0.0,
                    "protect_sl": round(st_level, 1),
                    "status": "ACTIVE (SMART HYBRID)",
                    "entry_reason": f"🔥 Core Renko ST {sig_dir} Signal (Brick: ${brick_size:.0f} | ST: ${st_level:,.1f})",
                    "exit_reason": f"चालू है — +300p से पहले केवल ST Flip (${st_level:,.1f}) पर कटेगा; +300p/+500p पार होते ही प्रॉफिट लॉक करेगा"
                })

            if stepped_bricks > 0 or flipped_now:
                brick_events.append({
                    "time": b_ist_short,
                    "dir": "BULLISH 🟢" if trend == 1 else "BEARISH 🔴",
                    "cls": "ic-bull" if trend == 1 else "ic-bear",
                    "brick_top": round(brick_top, 1),
                    "brick_bot": round(brick_bot, 1),
                    "streak": brick_streak,
                    "st_line": round(st_level, 1),
                    "flip": f"🔥 BUY @ ${c:,.0f} ▲" if bar_buy_sig else (f"🔥 SELL @ ${c:,.0f} ▼" if bar_sell_sig else "")
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
            "brick_events": list(reversed(brick_events[-20:])),
            "hybrid_trades": list(reversed(hybrid_trades[-20:])),
            "chart_points": chart_points[-180:]
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# LIVE HYBRID TRADE OPENER & CLOSER (WITH AI DYNAMIC LOT SIZE & DELTA EXECUTION)
# ============================================================================
def open_hybrid_trade_now(eng, direction: str, entry_px: float, ist_str: str, entry_source_label: str, fire_delta: bool = True):
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
        "live_pts": 0.0,
        "weighted_pts": 0.0,
        "peak_pts": 0.0,
        "phase": 1,
        "phase_name": "PHASE 1: PURE SIGNAL-TO-SIGNAL",
        "shield_active": False,
        "locked_pts": 0.0,
        "protect_sl": round(st_line_val, 1),
        "status": "ACTIVE (SMART HYBRID)",
        "entry_reason": f"{entry_source_label} (Brick: ${box_sz:.0f} | Reversal ST: ${st_line_val:,.1f})",
        "exit_reason": f"चालू है — +300p से पहले केवल ST Flip (${st_line_val:,.1f}) पर कटेगा; +300p/+500p पार होते ही प्रॉफिट लॉक करेगा"
    }
    eng["active_trade"] = new_trade
    eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
    eng["signal_history"].insert(0, new_trade)
    eng["signal_history"] = eng["signal_history"][:30]
    eng["sound_event"] = {"id": time.time(), "type": "BULL" if direction == "BUY" else "BEAR"}

    if fire_delta:
        delta_side = "buy" if direction == "BUY" else "sell"
        place_delta_demo_order(eng, side=delta_side, size=final_lot_size, reduce_only=False, note=f"Entry {direction} [{lot_mult}x Lot]")

def close_hybrid_trade_at_price(eng, active_tr, exit_px: float, ist_str: str, reason_title: str, detailed_reason: str, fire_delta: bool = True):
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
        if rem_deficit == 0.0 or move >= 120.0:
            eng["loss_streak"] = 0
            eng["deficit_pts"] = 0.0

    eng["active_trade"] = None
    eng["sound_event"] = {"id": time.time(), "type": "EXIT"}

    if fire_delta:
        close_side = "sell" if active_tr["type"] == "BUY" else "buy"
        place_delta_demo_order(eng, side=close_side, size=lot_used, reduce_only=True, note=f"Exit {active_tr['type']} [{lot_used} Lot]")

    rk = eng.get("renko", {})
    st_line_now = rk.get("st_line", 0.0)
    st_trend_now = rk.get("st_trend", 0)
    tr_dir_int = 1 if active_tr["type"] == "BUY" else -1
    if eng.get("allow_pullback_reentry") and move >= 120.0 and st_trend_now == tr_dir_int and abs(exit_px - st_line_now) >= 240.0 and "FLIP" not in reason_title:
        eng["reentry_watch"] = {
            "armed": True,
            "dir": tr_dir_int,
            "dir_str": active_tr["type"],
            "armed_ts": time.time(),
            "reason": f"पिछला {active_tr['type']} ट्रेड +{move:.1f}p के हाइब्रिड प्रॉफिट में बुक हुआ। प्राइस के Reversal Level (${st_line_now:,.0f}) के पास आने पर री-एंट्री होगी।"
        }

# ============================================================================
# AI SMART HYBRID COMMENTARY & PROFIT LOCK REFINEMENT ENGINE
# ============================================================================
def hybrid_commentary_backup_brain(ctx, active_trade):
    px = ctx["px"]
    rk = ctx["renko"]
    st_line = rk.get("st_line", px)
    box_sz = rk.get("box_size", 270.0)
    rev_b = rk.get("rev_bricks", 2.0)
    dist_to_flip = abs(px - st_line)
    next_brick_px = (rk.get("brick_top", px) + box_sz) if rk.get("st_trend", 1) == 1 else (rk.get("brick_bot", px) - box_sz)

    if active_trade is None:
        return {
            "headline": f"हाइब्रिड प्रॉफिट बुक हो चुका है — अगला रैंकों सिग्नल आते ही 100% अनिवार्य एंट्री ली जाएगी (Reversal Level: ${st_line:,.0f} | {dist_to_flip:.0f} Pts दूर)।",
            "renko_structure": f"Fixed Brick: ${box_sz:.0f} (Rev: {rev_b:.1f}x = ${box_sz*rev_b:.0f}p) | अगली ब्रिक स्टेप: ${next_brick_px:,.0f} पर।",
            "extension_check": f"21-EMA: ${rk.get('ema21', 0):,.0f} | 14-RSI: {rk.get('rsi14', 50):.1f} | 3-Bar Power: {rk.get('buy_dom_pct', 50):.0f}% Buy।"
        }

    hyb = compute_hybrid_protection(active_trade["entry"], active_trade["peak_pts"], active_trade["type"], st_line)
    return {
        "headline": hyb["rule_hi"],
        "renko_structure": f"Brick Box: ${rk.get('brick_bot', 0):,.0f}–${rk.get('brick_top', 0):,.0f} (Streak #{rk.get('brick_streak', 1)}) | ST Reversal Level: ${st_line:,.1f} ({dist_to_flip:.0f}p दूर)।",
        "extension_check": f"Active Phase: {hyb['phase_name']} | Lot: {active_trade.get('lot_size', 1)} ({active_trade.get('lot_mult', 1)}x) | RSI: {rk.get('rsi14', 50):.1f}"
    }

def call_gemini_hybrid_engine(api_key, ctx, active_trade, selected_model, available_models):
    if active_trade is None:
        return hybrid_commentary_backup_brain(ctx, None), "🟢 Smart Hybrid Watcher"

    px = ctx["px"]
    rk = ctx["renko"]
    t_type = active_trade["type"]
    live_pts = active_trade["live_pts"]
    peak_pts = active_trade["peak_pts"]
    st_line = rk.get("st_line", px)
    hyb = compute_hybrid_protection(active_trade["entry"], peak_pts, t_type, st_line)

    prompt = f"""
You are a Quantitative Smart-Hybrid Renko Trade Manager monitoring an ACTIVE BTCUSDT trade ('AI Renko Supertrend [Core Architecture]').
Mandatory System Rules:
- Every Renko Supertrend signal is taken unconditionally.
- Current Trade Lot Size: {active_trade.get('lot_size', 1)} Lots ({active_trade.get('lot_mult', 1)}x Recovery Multiplier).
- Phase 1 (Peak < +300p): Pure Signal-to-Signal (only exit if candle closes beyond Reversal Level `stLevel` = ${st_line:,.1f}).
- Phase 2 (Peak +300p to +499p): Breakeven+ Shield active at ${hyb['protect_sl']:,.1f} (+{hyb['locked_pts']:.1f}p locked).
- Phase 3 (Peak +500p to +899p): Big Profit Lock active at ${hyb['protect_sl']:,.1f} (140p gap from Peak).
- Phase 4 (Peak >= +900p): Parabolic Tight Lock active at ${hyb['protect_sl']:,.1f} (110p gap from Peak).

ACTIVE TRADE STATUS:
- Direction: {t_type} | Entry: ${active_trade['entry']:,.1f} | Current Price: ${px:,.1f}
- Live PnL: {live_pts:+.1f} pts | Peak Profit: +{peak_pts:.1f} pts | Current Phase: {hyb['phase_name']}
- Protected Hybrid SL: ${active_trade.get('protect_sl', st_line):,.1f} | Renko Reversal Level (`stLevel`): ${st_line:,.1f}
- 14-RSI: {rk.get('rsi14', 50):.1f} | 21-EMA Stretch: {rk.get('ema_dist_bricks', 0):.2f} bricks

Return ONLY valid JSON with sharp Hindi explanations:
{{
  "headline": "Sharp 1-line Hindi status explaining the current Hybrid Phase, Peak Profit, and Protected SL level",
  "renko_structure": "Sharp 1-line Hindi analysis of Brick Box and distance to stLevel (${st_line:,.0f})",
  "extension_check": "Sharp 1-line Hindi momentum check (RSI, EMA stretch, and lot recovery status)"
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
    }

    pro_first_priority = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    sorted_avail = sorted(available_models or [], key=score_model_priority)
    combined_auto = []
    for m in sorted_avail + pro_first_priority:
        if m not in combined_auto:
            combined_auto.append(m)

    models_queue = [selected_model] + [m for m in combined_auto if m != selected_model] if (selected_model and selected_model != AUTO_MODEL_LABEL) else combined_auto

    for mod in models_queue:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=9.0)
            if res.status_code == 200:
                parsed = parse_ai_json_safely(res.json()['candidates'][0]['content']['parts'][0]['text'].strip())
                if parsed:
                    return parsed, f"🟢 Smart Hybrid AI ({mod})"
        except Exception:
            continue

    return hybrid_commentary_backup_brain(ctx, active_trade), "⚡ Smart Hybrid Brain"

def execute_ai_cycle_thread(eng, now_ts, ist_str):
    if eng.get("ai_busy"):
        return
    eng["ai_busy"] = True
    try:
        px = eng["px"]
        if px <= 0:
            return
        rk = eng.get("renko", {})
        ctx = {"time": ist_str, "px": px, "renko": rk}
        api_key = eng.get("api_key", "").strip()
        selected_mod = eng.get("selected_model", AUTO_MODEL_LABEL)

        if api_key and eng.get("active_trade") is not None:
            ai_json, status_str = call_gemini_hybrid_engine(api_key, ctx, eng.get("active_trade"), selected_mod, eng.get("available_models"))
        else:
            ai_json, status_str = hybrid_commentary_backup_brain(ctx, eng.get("active_trade")), "🟢 Smart Hybrid + AI Lot Engine"

        eng["ai_status"] = status_str
        eng["last_report_ts"] = time.time()
        eng["ai_json_view"].update({
            "headline": ai_json.get("headline", ""),
            "renko_structure": ai_json.get("renko_structure", ""),
            "extension_check": ai_json.get("extension_check", "")
        })
    finally:
        eng["ai_busy"] = False

# ============================================================================
# 24x7 1-SECOND BACKGROUND WORKER (MANDATORY RENKO FLIP + +300p/+500p LOCK)
# ============================================================================
def background_worker(eng, worker_id):
    last_used_brick_size = eng.get("fixed_brick_size", 270.0)
    last_used_rev = eng.get("rev_bricks", 2.0)
    last_used_reentry = eng.get("allow_pullback_reentry", False)
    last_used_base_lot = eng.get("delta_base_lot", 1)

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
                user_reentry = bool(eng.get("allow_pullback_reentry", False))
                user_base_lot = max(1, int(eng.get("delta_base_lot", 1)))
                settings_changed = (
                    abs(user_brick_sz - last_used_brick_size) >= 0.5
                    or abs(user_rev - last_used_rev) >= 0.1
                    or (user_reentry != last_used_reentry)
                    or (user_base_lot != last_used_base_lot)
                )

                # 1. 1-SECOND SMART HYBRID PROFIT SHIELD (+300p) & PEAK LOCK (+500p/+900p) GUARD
                act_tr = eng.get("active_trade")
                rk_now = eng.get("renko", {})
                st_line_now = rk_now.get("st_line", px)

                if act_tr is not None:
                    move = (px - act_tr["entry"]) if act_tr["type"] == "BUY" else (act_tr["entry"] - px)
                    act_tr["live_pts"] = round(move, 1)
                    act_tr["weighted_pts"] = round(move * act_tr.get("lot_mult", 1), 1)
                    act_tr["peak_pts"] = round(max(act_tr["peak_pts"], move), 1)

                    hyb = compute_hybrid_protection(act_tr["entry"], act_tr["peak_pts"], act_tr["type"], st_line_now)
                    prev_phase = act_tr.get("phase", 1)
                    act_tr["phase"] = hyb["phase"]
                    act_tr["phase_name"] = hyb["phase_name"]

                    if hyb["shield_active"]:
                        act_tr["shield_active"] = True
                        if act_tr["type"] == "BUY":
                            new_psl = max(act_tr.get("protect_sl", 0.0), hyb["protect_sl"])
                            act_tr["protect_sl"] = round(new_psl, 1)
                            act_tr["locked_pts"] = round(act_tr["protect_sl"] - act_tr["entry"], 1)
                            shield_hit = px <= act_tr["protect_sl"]
                        else:
                            old_psl = act_tr.get("protect_sl", 0.0)
                            new_psl = min(old_psl if old_psl > 0 else 999999.0, hyb["protect_sl"])
                            act_tr["protect_sl"] = round(new_psl, 1)
                            act_tr["locked_pts"] = round(act_tr["entry"] - act_tr["protect_sl"], 1)
                            shield_hit = px >= act_tr["protect_sl"]

                        if hyb["phase"] > prev_phase:
                            eng["sound_event"] = {"id": now_ts, "type": "TRAIL"}

                        if shield_hit:
                            booked = act_tr["locked_pts"]
                            close_hybrid_trade_at_price(
                                eng, act_tr, px, ist_str,
                                f"HYBRID PHASE {hyb['phase']} PROFIT LOCK",
                                f"🛡️ स्मार्ट हाइब्रिड लॉक हिट! Peak +{act_tr['peak_pts']:.1f}p से पलटने पर ${act_tr['protect_sl']:,.1f} पर +{booked:.1f} Pts ({act_tr.get('lot_size',1)} Lot) सुरक्षित बुक!",
                                fire_delta=True
                            )
                    else:
                        act_tr["protect_sl"] = round(st_line_now, 1)
                        dist_now = abs(px - st_line_now)
                        act_tr["exit_reason"] = f"फेज 1 (Pure Signal): अभी Peak (+{act_tr['peak_pts']:.0f}p) < +300p है — केवल ST Flip (${st_line_now:,.1f} | {dist_now:.0f}p दूर) पर कटेगा"

                # 2. OPTIONAL PULLBACK RE-ENTRY WATCHER
                rw = eng.get("reentry_watch", {"armed": False})
                if eng.get("active_trade") is None and user_reentry and rw.get("armed") and st_line_now > 0:
                    if rk_now.get("st_trend", 0) != rw["dir"]:
                        eng["reentry_watch"] = {"armed": False, "dir": 0, "reason": ""}
                    elif (now_ts - rw.get("armed_ts", 0.0)) >= 45.0:
                        if rw["dir"] == 1 and (st_line_now + 20.0 <= px <= st_line_now + 90.0):
                            open_hybrid_trade_now(eng, "BUY", px, ist_str, "🔄 Hybrid ST Pullback Re-Entry ▲", fire_delta=True)
                        elif rw["dir"] == -1 and (st_line_now - 90.0 <= px <= st_line_now - 20.0):
                            open_hybrid_trade_now(eng, "SELL", px, ist_str, "🔄 Hybrid ST Pullback Re-Entry ▼", fire_delta=True)

                # 3. UPDATE CORE RENKO SUPERTREND & MANDATORY FLIP EXECUTION
                if settings_changed or (now_ts - eng["last_kline_ts"] > 6):
                    rk_data = fetch_core_renko_supertrend(
                        fixed_brick_size=user_brick_sz,
                        rev_bricks=user_rev,
                        allow_pullback_reentry=user_reentry,
                        base_lot=user_base_lot
                    )
                    if rk_data and "error" not in rk_data:
                        prev_rk_trend = eng["renko"].get("st_trend", 0)
                        eng["renko"] = rk_data
                        last_used_brick_size = user_brick_sz
                        last_used_rev = user_rev
                        last_used_reentry = user_reentry
                        last_used_base_lot = user_base_lot

                        if prev_rk_trend == 0 or settings_changed:
                            eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                            eng["loss_streak"] = rk_data.get("sim_loss_streak", 0)
                            eng["deficit_pts"] = rk_data.get("sim_deficit_pts", 0.0)
                            eng["last_closed_pts"] = rk_data.get("sim_last_closed_pts", 0.0)

                            if rk_data.get("hybrid_trades"):
                                eng["signal_history"] = rk_data["hybrid_trades"]
                                latest_tr = eng["signal_history"][0]
                                eng["active_trade"] = latest_tr if "ACTIVE" in latest_tr["status"] else None
                                if eng["active_trade"]:
                                    eng["current_lot_mult"] = eng["active_trade"].get("lot_mult", 1)
                                    eng["current_lot_size"] = eng["active_trade"].get("lot_size", user_base_lot)
                                    eng["last_lot_reason"] = eng["active_trade"].get("lot_reason", "")
                            else:
                                cur_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                open_hybrid_trade_now(eng, cur_dir, rk_data["last_flip_price"], rk_data["last_flip_time_str"], f"🔥 Chart Sync {cur_dir}", fire_delta=False)
                            threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()
                        else:
                            if rk_data["st_trend"] != prev_rk_trend and rk_data["last_flip_bar_ts"] != eng.get("last_handled_flip_ts"):
                                eng["last_handled_flip_ts"] = rk_data["last_flip_bar_ts"]
                                new_dir = "BUY" if rk_data["st_trend"] == 1 else "SELL"
                                flip_px = rk_data["last_confirmed_close"]

                                if eng.get("active_trade") is not None:
                                    old_tr = eng["active_trade"]
                                    raw_m = (flip_px - old_tr["entry"]) if old_tr["type"] == "BUY" else (old_tr["entry"] - flip_px)
                                    close_hybrid_trade_at_price(
                                        eng, old_tr, flip_px, ist_str,
                                        f"FLIPPED TO {new_dir}",
                                        f"विपरीत {new_dir} सिग्नल आने पर ${flip_px:,.1f} पर बंद हुआ (Raw: {raw_m:+.1f}p | {old_tr.get('lot_mult',1)}x Lot PnL: {raw_m*old_tr.get('lot_mult',1):+.1f}p)",
                                        fire_delta=True
                                    )

                                open_hybrid_trade_now(eng, new_dir, flip_px, ist_str, f"🔥 Live Renko ST Flip {new_dir} {'▲' if new_dir=='BUY' else '▼'}", fire_delta=True)
                                threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

                    elif rk_data and "error" in rk_data:
                        eng["last_err"] = rk_data["error"]

                    eng["last_kline_ts"] = now_ts

                if now_ts - eng["last_report_ts"] >= 180 and not eng.get("ai_busy"):
                    threading.Thread(target=execute_ai_cycle_thread, args=(eng, now_ts, ist_str), daemon=True).start()

        except Exception as e:
            eng["last_err"] = str(e)
        time.sleep(1)

@st.cache_resource
def get_master_engine_v26_1():
    wid = int(time.time() * 1000)
    srv_ip = fetch_server_public_ip()
    eng = {
        "worker_id": wid, "px": 0.0, "last_update": "--:--:--",
        "server_ip": srv_ip,
        "delta_env": "🇮🇳 Delta India Testnet (Demo)",
        "delta_api_key": "",
        "delta_api_secret": "",
        "delta_base_lot": 1,
        "current_lot_mult": 1,
        "current_lot_size": 1,
        "loss_streak": 0,
        "deficit_pts": 0.0,
        "last_closed_pts": 0.0,
        "last_lot_reason": "✅ हर रैंकों सिग्नल पर ट्रेड अनिवार्य है — शुरुआती 1x Base Lot सक्रिय।",
        "delta_enabled": True,
        "delta_product_id": None,
        "delta_last_status": "⚪ Delta Demo Ready (API Keys सेट करें)",
        "fixed_brick_size": 270.0, "rev_bricks": 2.0, "allow_pullback_reentry": False,
        "signal_history": [], "active_trade": None, "ai_busy": False,
        "reentry_watch": {"armed": False, "dir": 0, "reason": ""},
        "last_kline_ts": 0.0, "last_report_ts": 0.0, "last_handled_flip_ts": 0,
        "renko": {
            "box_size": 270.0, "rev_bricks": 2.0,
            "brick_top": 0.0, "brick_bot": 0.0, "brick_dir": 1, "brick_streak": 1,
            "r_close": 0.0, "st_trend": 0, "st_line": 0.0,
            "buy_dom_pct": 50.0, "ema21": 0.0, "ema_dist_bricks": 0.0, "rsi14": 50.0,
            "brick_events": [], "chart_points": []
        },
        "available_models": [], "models_fetched": False, "selected_model": AUTO_MODEL_LABEL,
        "ai_json_view": {
            "headline": "⏳ Smart Hybrid (+300p/+500p Lock) + AI Recovery Lot Engine सिंक हो रहा है...",
            "renko_structure": "फिक्स ब्रिक बॉक्स और Reversal Level लोड हो रहा है...",
            "extension_check": "21-EMA और RSI की गणना हो रही है..."
        },
        "ai_status": "🟢 Smart Hybrid + AI Lot Sizer",
        "sound_event": {"id": 0.0, "type": "BULL"},
        "api_key": "", "last_err": None
    }
    threading.Thread(target=background_worker, args=(eng, wid), daemon=True).start()
    return eng

eng = get_master_engine_v26_1()

try:
    if "GEMINI_API_KEY" in st.secrets:
        eng["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
    if "DELTA_API_KEY" in st.secrets and not eng["delta_api_key"]:
        eng["delta_api_key"] = str(st.secrets["DELTA_API_KEY"]).strip()
    if "DELTA_API_SECRET" in st.secrets and not eng["delta_api_secret"]:
        eng["delta_api_secret"] = str(st.secrets["DELTA_API_SECRET"]).strip()
except Exception:
    pass

if not eng.get("models_fetched"):
    eng["available_models"] = fetch_available_api_models(eng.get("api_key", ""))
    eng["models_fetched"] = True

if "last_played_sound_id" not in st.session_state:
    st.session_state["last_played_sound_id"] = 0.0

# ============================================================================
# COMPACT SERVER IP DISPLAY BOX, AI LOT STATUS & DELTA DEMO API SETUP BAR
# ============================================================================
ip_col1, ip_col2, ip_col3, ip_col4 = st.columns([0.27, 0.31, 0.28, 0.14])
with ip_col1:
    st.markdown(clean_html(f"""
    <div class='ip-badge-box'>
        <span>🌐 <b>Server IP (Delta Whitelist):</b></span>
        <code style='color:#facc15; background:#1e293b; padding:2px 8px; border-radius:5px; font-size:13px; font-weight:900;'>{eng.get('server_ip', '--')}</code>
    </div>
    """), unsafe_allow_html=True)

with ip_col2:
    st.markdown(clean_html(f"""
    <div class='lot-badge-box'>
        <span>📦 <b>AI Active Lot:</b> <b style='color:#facc15;'>{eng.get('current_lot_size', 1)} Lot ({eng.get('current_lot_mult', 1)}x)</b></span>
        <span>| <b>Deficit:</b> <b style='color:{"#f87171" if eng.get("deficit_pts",0)>0 else "#4ade80"};'>{-eng.get("deficit_pts", 0.0):+.0f}p</b></span>
    </div>
    """), unsafe_allow_html=True)

with ip_col3:
    st.markdown(clean_html(f"""
    <div class='delta-badge-box'>
        <span>⚡ <b>Delta:</b></span>
        <span style='color:#38bdf8; font-weight:700;'>{eng.get('delta_last_status', 'Ready')}</span>
    </div>
    """), unsafe_allow_html=True)

with ip_col4:
    if st.button("🔄 Refresh IP"):
        eng["server_ip"] = fetch_server_public_ip()

with st.expander("⚙️ Delta Exchange Demo API एवं Base Lot सेटअप (यहाँ API Key डालें)", expanded=False):
    d_c1, d_c2, d_c3, d_c4, d_c5 = st.columns([0.24, 0.24, 0.24, 0.14, 0.14])
    with d_c1:
        env_list = list(DELTA_ENV_URLS.keys())
        cur_env_idx = env_list.index(eng["delta_env"]) if eng.get("delta_env") in env_list else 0
        eng["delta_env"] = st.selectbox("Delta Demo Server:", options=env_list, index=cur_env_idx)
    with d_c2:
        eng["delta_api_key"] = st.text_input("🔑 Delta Demo API Key:", value=eng.get("delta_api_key", ""), type="password")
    with d_c3:
        eng["delta_api_secret"] = st.text_input("🔒 Delta Demo API Secret:", value=eng.get("delta_api_secret", ""), type="password")
    with d_c4:
        eng["delta_base_lot"] = int(st.number_input("📦 Base Lot (1x):", min_value=1, max_value=500, value=int(eng.get("delta_base_lot", 1)), step=1, help="सामान्य ट्रेड का बेस लॉट (AI लॉस रिकवरी के समय इसे 1x, 2x या 3x करेगा)"))
    with d_c5:
        eng["delta_enabled"] = st.checkbox("⚡ Auto-Trade ON", value=bool(eng.get("delta_enabled", True)))

    b_c1, b_c2, b_c3 = st.columns(3)
    with b_c1:
        if st.button("🔍 Check Delta Demo Connection & Balance"):
            check_delta_demo_wallet(eng)
    with b_c2:
        if st.button("🟢 Test Demo BUY (Active AI Lot)"):
            place_delta_demo_order(eng, side="buy", size=int(eng.get("current_lot_size", 1)), reduce_only=False, note="Manual Test BUY")
    with b_c3:
        if st.button("🔴 Test Demo SELL (Active AI Lot)"):
            place_delta_demo_order(eng, side="sell", size=int(eng.get("current_lot_size", 1)), reduce_only=False, note="Manual Test SELL")

# ============================================================================
# TOP CONTROL BAR (UNTOUCHED CONTROLS)
# ============================================================================
c_mod, c_brk, c_rev, c_re, c_act1, c_snd = st.columns([0.21, 0.14, 0.14, 0.19, 0.20, 0.12])

with c_mod:
    dropdown_options = [AUTO_MODEL_LABEL] + eng.get("available_models", [])
    curr_sel = eng.get("selected_model", AUTO_MODEL_LABEL)
    sel_idx = dropdown_options.index(curr_sel) if curr_sel in dropdown_options else 0
    eng["selected_model"] = st.selectbox("🧠 AI मॉडल:", options=dropdown_options, index=sel_idx, label_visibility="collapsed")

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

with c_re:
    eng["allow_pullback_reentry"] = st.checkbox(
        "🔄 ST Pullback Re-Entry",
        value=bool(eng.get("allow_pullback_reentry", False)),
        help="ऑन करने पर: अगर ट्रेड +300p/+500p लॉक में कटता है और प्राइस वापस ST Line के पास आता है, तो दोबारा एंट्री लेगा।"
    )

with c_act1:
    if st.button("🤖 हाइब्रिड स्टेटस / चार्ट रिफ्रेश"):
        eng["last_kline_ts"] = 0.0
        threading.Thread(target=execute_ai_cycle_thread, args=(eng, time.time(), get_ist_time_str()), daemon=True).start()

with c_snd:
    sound_enabled = st.checkbox("🔊 साउंड", value=True)

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

        cur_hyb = compute_hybrid_protection(
            act_tr["entry"] if act_tr else eng["px"],
            act_tr["peak_pts"] if act_tr else 0.0,
            act_tr["type"] if act_tr else ("BUY" if rk.get("st_trend", 1) == 1 else "SELL"),
            st_line_px
        )

        if act_tr:
            t_mult = act_tr.get("lot_mult", 1)
            t_lots = act_tr.get("lot_size", 1)
            banner_cls = "lock-buy" if act_tr["type"] == "BUY" else "lock-sell"
            if act_tr.get("shield_active"):
                prot_px = act_tr.get("protect_sl", st_line_px)
                lck_pts = act_tr.get("locked_pts", 0.0)
                banner_title = f"🛡️ हाइब्रिड {act_tr['type']} चालू [{t_lots} Lot / {t_mult}x] ({cur_hyb['phase_name']}) — +{lck_pts:.1f}p लॉक!"
                banner_sub = (
                    f"एंट्री: ${act_tr['entry']:,.1f} | Peak: <b>+{act_tr['peak_pts']:.1f}p</b> | "
                    f"प्रोटेक्टेड SL: <b style='color:#facc15;'>${prot_px:,.1f} (+{lck_pts:.1f}p)</b> | "
                    f"AI Lot: <b style='color:#c084fc;'>{t_lots} Lot ({t_mult}x)</b>"
                )
            else:
                pts_to_shield = max(0.0, 300.0 - act_tr["peak_pts"])
                banner_title = f"{'🟢' if act_tr['type']=='BUY' else '🔴'} स्मार्ट हाइब्रिड {act_tr['type']} चालू [📦 {t_lots} Lot ({t_mult}x)]"
                banner_sub = (
                    f"एंट्री: ${act_tr['entry']:,.1f} | Peak: +{act_tr['peak_pts']:.1f}p (+300p Shield में {pts_to_shield:.0f}p बाकी) | "
                    f"Reversal ST: <b>${st_line_px:,.1f} ({st_dist_pts:.0f}p दूर)</b>"
                )
            right_stat_label = f"LIVE PNL ({t_mult}x = {act_tr.get('weighted_pts', act_tr['live_pts']):+.0f}p)"
            right_stat_val = f"{act_tr['live_pts']:+.1f} Pts"
            right_stat_col = "#4ade80" if act_tr["live_pts"] >= 0 else "#f87171"
        else:
            banner_cls = "lock-wait"
            banner_title = f"🏁 हाइब्रिड प्रॉफिट बुक — अगले Renko ST सिग्नल पर 100% अनिवार्य एंट्री होगी ({st_trend_txt})"
            banner_sub = f"Reversal Level (stLevel): ${st_line_px:,.1f} (प्राइस से {st_dist_pts:.0f} Pts दूर) | पेंडिंग लॉस डेफिसिट: {-eng.get('deficit_pts', 0.0):+.1f} Pts"
            right_stat_label = "DISTANCE TO FLIP"
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
            sts_badge = f"🟢 {h.get('phase_name', 'ACTIVE')}" if is_act else f"🏁 {h['status']}"
            h_mult = h.get("lot_mult", 1)
            h_lots = h.get("lot_size", 1)
            w_pts = h.get("weighted_pts", h["live_pts"] * h_mult)
            lot_pill_col = "#facc15" if h_mult > 1 else "#38bdf8"
            lot_tag = f"<span style='background:#1e1b4b; border:1px solid {lot_pill_col}; color:{lot_pill_col}; padding:1px 7px; border-radius:5px; font-size:11px; font-weight:800; margin-left:6px;'>📦 {h_lots} Lot ({h_mult}x)</span>"
            shield_tag = (
                f" | <b style='color:#facc15;'>🛡️ Locked: +{h.get('locked_pts', 0):.1f}p (@ ${h.get('protect_sl', 0):,.1f})</b>"
                if h.get("shield_active") else ""
            )

            hist_cards += f"""
            <div class='item-card {h_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <b style='color:{h_col}; font-size:13.5px;'>{h['open_time']} — {h['type']} @ ${h['entry']:,.1f}</b>
                    {lot_tag}
                    <span style='font-size:11.5px; color:#facc15; margin-left:6px;'>[{sts_badge}]</span>{shield_tag}<br>
                    <span style='color:#cbd5e1; font-size:12px;'>{h['entry_reason']}</span><br>
                    <span style='color:#e9d5ff; font-size:11.6px;'>🧠 {h.get('lot_reason', '1x Base Lot')}</span><br>
                    <span style='color:#38bdf8; font-size:11.8px;'>{h['exit_reason']}</span>
                </div>
                <div style='text-align:right; min-width:125px;'>
                    <div style='font-size:15.5px; font-weight:900; color:{p_col};'>{h['live_pts']:+.1f}p</div>
                    <div style='font-size:11.5px; font-weight:800; color:#facc15;'>{h_mult}x PnL: {w_pts:+.1f}p</div>
                    <div style='font-size:10.8px; color:#94a3b8;'>Peak: +{h['peak_pts']:.1f}p</div>
                </div>
            </div>
            """

        cur_ph = cur_hyb["phase"] if act_tr else 0
        hybrid_roadmap_html = f"""
        <div class='item-card {"ic-active-stage" if cur_ph == 1 else "ic-warn"}'>
            <b>⚡ PHASE 1: प्योर सिग्नल-टू-सिग्नल (Peak: 0 से +299 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: हर रैंकों सिग्नल पर 100% ट्रेड खुलेगा। +300p से पहले केवल Reversal Level (<b>${st_line_px:,.0f}</b>) पर ही ट्रेड पलटेगा।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_ph == 2 else "ic-bull"}'>
            <b>🛡️ PHASE 2: ब्रेक-ईवन+ शील्ड (Peak: +300 से +499 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: +300p पार होते ही ट्रेड कभी लॉस में नहीं कटेगा! कम से कम <b>+120p से +319p</b> (Peak - 180p) पक्का लॉक।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_ph == 3 else "ic-bull"}'>
            <b>🚀 PHASE 3: बिग प्रॉफिट लॉक (Peak: +500 से +899 Pts)</b><br>
            <span style='color:#cbd5e1;'>नियम: +500p पार होते ही Peak से सिर्फ <b>140 Pts पीछे</b> ट्रेलिंग लॉक (जैसे +640p Peak पर <b>+500p</b> पक्का बुक)।</span>
        </div>
        <div class='item-card {"ic-active-stage" if cur_ph == 4 else "ic-bull"}'>
            <b>🔥 PHASE 4: पैराबोलिक टाइट लॉक (Peak: +900 Pts से ऊपर)</b><br>
            <span style='color:#cbd5e1;'>नियम: +900p+ की बड़ी रैली में Peak से सिर्फ <b>110 Pts पीछे</b> टाइट लॉक (जैसे +1069p Peak पर <b>+959p</b> पक्का बुक)!</span>
        </div>
        """

        brick_cards = ""
        for idx, b in enumerate(rk.get("brick_events", []), 1):
            flip_tag = f"<span style='color:#facc15; font-weight:900; margin-left:6px;'>{b['flip']}</span>" if b["flip"] else ""
            brick_cards += f"""
            <div class='item-card {b['cls']}'>
                <div style='display:flex; justify-content:space-between; font-weight:800;'>
                    <span>#{idx} 🕒 {b['time']} | {b['dir']} (#{b['streak']})</span>
                    <span style='color:#38bdf8;'>Box: ${b['brick_bot']:,.0f}–${b['brick_top']:,.0f}</span>
                </div>
                <div style='color:#cbd5e1; font-size:11.8px; margin-top:2px;'>
                    Reversal Level (stLevel): <b>${b['st_line']:,.1f}</b> {flip_tag}
                </div>
            </div>
            """

        net_col = "#4ade80" if closed_weighted_sum >= 0 else "#f87171"
        def_pts = eng.get("deficit_pts", 0.0)
        l_streak = eng.get("loss_streak", 0)

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
                    📈 SMART HYBRID RENKO CHART (Brick: ${box_sz:.0f} | Rev: {rev_b:.1f}x = ${box_sz*rev_b:.0f}p)
                </span>
                <span style='font-size:12px; color:#cbd5e1;'>
                    <b style='color:#38bdf8;'>━ Price (${eng['px']:,.0f})</b> &nbsp;|&nbsp;
                    <b style='color:{st_trend_col};'>━ Reversal ST (${st_line_px:,.0f})</b> &nbsp;|&nbsp;
                    <b style='color:#facc15;'>-- Hybrid Lock SL (+300p/+500p)</b>
                </span>
            </div>
            {svg_chart_html}
        </div>

        <div class='sub-grid'>
            <div class='card-box'>
                <div class='card-title'>
                    <span>🧱 1. लाइव रैंकों एवं हाइब्रिड शील्ड ट्रेस</span>
                    <span style='color:{st_trend_col};'>{st_trend_txt}</span>
                </div>
                <div class='stat-row'><span>विपरीत सिग्नल लेवल (Reversal stLevel):</span><b><span style='color:{st_trend_col};'>${st_line_px:,.1f}</span> (प्राइस से {st_dist_pts:.0f} Pts दूर)</b></div>
                <div class='stat-row'><span>हाइब्रिड प्रोटेक्टेड SL (+300p/+500p):</span><b style='color:#facc15;'>{f"${act_tr['protect_sl']:,.1f} (+{act_tr['locked_pts']:.1f}p Locked)" if (act_tr and act_tr.get("shield_active")) else "Waiting for +300p Peak"}</b></div>
                <div class='stat-row'><span>चालू ब्रिक बॉक्स (Bot – Top):</span><b>${rk.get("brick_bot", 0.0):,.1f} — ${rk.get("brick_top", 0.0):,.1f} (Streak #{rk.get("brick_streak", 1)})</b></div>
                <div class='stat-row' style='border:none;'><span>अगली ब्रिक बनने का लेवल:</span><b style='color:#38bdf8;'>${next_step_px:,.1f} ({pts_to_next_brick:.0f} Pts दूर)</b></div>
            </div>

            <div class='card-box'>
                <div class='card-title'>
                    <span>📦 2. AI लॉस-रिकवरी एवं लॉट साइज़िंग ब्रेन</span>
                    <span style='color:#facc15;'>Active: {eng.get("current_lot_size", 1)} Lot ({eng.get("current_lot_mult", 1)}x)</span>
                </div>
                <div class='stat-row'><span>सिग्नल एग्जीक्यूशन नियम:</span><b style='color:#4ade80;'>100% Mandatory (हर सिग्नल पर ट्रेड)</b></div>
                <div class='stat-row'><span>पेंडिंग रिकवरी डेफिसिट (Loss Streak #{l_streak}):</span><b style='color:{"#f87171" if def_pts > 0 else "#4ade80"};'>{f"-{def_pts:.1f} Pts (Recovery Mode)" if def_pts > 0 else "0.0 Pts (All Recovered ✅)"}</b></div>
                <div class='stat-row'><span>24h PnL (1x Raw vs AI Weighted):</span><b>Raw: {closed_raw_sum:+.0f}p | <span style='color:{net_col};'>AI Lot PnL: {closed_weighted_sum:+.0f}p</span></b></div>
                <div style='font-size:12px; color:#e9d5ff; margin-top:5px; line-height:1.4;'>🧠 <b>AI निर्णय:</b> {eng.get("last_lot_reason", "")}</div>
            </div>
        </div>
        """

        dashboard_slot.markdown(clean_html(f"""
        <div>
            <div class='top-bar'>
                <div>
                    <div style='font-size:19px; font-weight:900; color:#38bdf8;'>⚡ PRO QUANT V26.1 (+300p/+500p HYBRID + AI LOT SIZER + DELTA DEMO)</div>
                    <div style='font-size:12.5px; color:#94a3b8; margin-top:2px;'>🧱 Brick: <b style='color:#facc15;'>${box_sz:.0f}</b> | 🛡️ Hybrid: <b>+300p Shield & +500p/+900p Peak Lock</b> | 📦 Active Lot: <b style='color:#facc15;'>{eng.get('current_lot_size',1)} Lot ({eng.get('current_lot_mult',1)}x)</b> | AI Lot PnL: <b style='color:{net_col};'>{closed_weighted_sum:+.1f} Pts ({win_cnt}W/{loss_cnt}L)</b></div>
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
                            <span>📜 स्मार्ट हाइब्रिड (+300p/+500p) + AI लॉट रिकवरी हिस्ट्री</span>
                            <span style='color:{net_col};'>1x Raw: {closed_raw_sum:+.0f}p | AI Lot Weighted: {closed_weighted_sum:+.1f} Pts ({win_cnt}W / {loss_cnt}L)</span>
                        </div>
                        {hist_cards}
                    </div>
                </div>

                <div class='brick-panel'>
                    <div style='font-size:14.5px; font-weight:900; color:#facc15; margin-bottom:8px; border-bottom:1px solid #334155; padding-bottom:6px;'>
                        🛡️ 4-फेज स्मार्ट हाइब्रिड प्रॉफिट प्रोटेक्शन रोडमैप (+300p / +500p / +900p)
                    </div>
                    {hybrid_roadmap_html}
                    <div style='font-size:13.5px; font-weight:900; color:#38bdf8; margin:12px 0 8px 0; border-bottom:1px solid #334155; padding-bottom:5px;'>
                        🧱 ताज़ा कन्फर्म्ड रैंकों ब्रिक स्टेप्स एवं सिग्नल लॉग
                    </div>
                    {brick_cards}
                </div>
            </div>
        </div>
        """), unsafe_allow_html=True)

    else:
        err_msg = f" ({eng['last_err']})" if eng.get("last_err") else ""
        dashboard_slot.warning(f"⏳ 24x7 V26.1 (+300p/+500p Smart Hybrid + AI Lot Engine) डेटा सिंक कर रहा है... कृपया 2 सेकंड प्रतीक्षा करें।{err_msg}")

    time.sleep(1.5)

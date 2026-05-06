"""
AgriShield — Narrator Agent
Uses Azure OpenAI GPT-4o to generate personalised 7-day farmer survival plans.
Delivers via Telegram Bot API (t.me/AgriShield_sai_bot).

Matches orchestrator.py call signature:
    send_farmer_plan(farmer, risk, market_data, crop_loss, azure_client)
"""

import requests
import json
from datetime import datetime
from openai import AzureOpenAI
from config import (
    TELEGRAM_BOT_TOKEN,
    AZURE_DEPLOYMENT_NAME,
)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ── Language instructions ──────────────────────────────────────────────────
LANGUAGE_MAP = {
    "te": ("Telugu",  "Write entirely in Telugu script (తెలుగు). Simple village-level Telugu, not formal."),
    "hi": ("Hindi",   "Write entirely in Hindi. Simple conversational Hindi a farmer understands."),
    "mr": ("Marathi", "Write entirely in Marathi. Simple rural Marathi."),
    "kn": ("Kannada", "Write entirely in Kannada. Simple everyday Kannada."),
    "ta": ("Tamil",   "Write entirely in Tamil. Simple conversational Tamil."),
    "en": ("English", "Write in very simple English. No technical terms."),
}

DEFAULT_LANGUAGE = "te"   # Telugu — primary farmer language in Andhra Pradesh


# ─────────────────────────────────────────────────────────────────────────────
#  Plan generation via Azure OpenAI
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(farmer: dict, risk: dict, market_data: dict, crop_loss: dict) -> str:
    lang_code = farmer.get("language", DEFAULT_LANGUAGE)
    lang_name, lang_instruction = LANGUAGE_MAP.get(lang_code, LANGUAGE_MAP["te"])

    risk_type    = risk.get("risk_type", "flood").upper()
    prob_pct     = int(risk.get("probability", 0.75) * 100)
    days_left    = risk.get("days_to_impact", 7)
    district     = farmer.get("district", "your district")
    crop         = farmer.get("crop", "your crop")
    area         = farmer.get("area_acres", 1.0)
    farmer_name  = farmer.get("name", "Farmer")

    # Monetary impact
    full_value   = crop_loss.get("full_crop_value_rs",     0)
    loss_value   = crop_loss.get("expected_loss_value_rs", 0)
    claim_est    = crop_loss.get("pmfby_claim_est_rs",     0)
    loss_pct     = crop_loss.get("expected_loss_pct",      0)

    # Market data
    modal_price  = market_data.get("modal_price_rs",  0)
    mandi_name   = market_data.get("market",          "nearest mandi")
    mandi_action = market_data.get("recommendation",  "Sell before disaster hits.")
    priority     = market_data.get("priority",        "URGENT")

    # Affected villages
    affected = ", ".join(risk.get("affected_villages", [district]))

    return f"""
You are AgriShield, a trusted agricultural advisor helping Indian farmers survive disasters.

{lang_instruction}

SITUATION:
- Farmer name: {farmer_name}
- District: {district} | Crop: {crop} on {area} acres
- DISASTER ALERT: {risk_type} in {days_left} days — {prob_pct}% probability
- Affected areas: {affected}
- Full crop value: Rs {full_value:,.0f}
- If no action taken: you lose Rs {loss_value:,.0f} ({loss_pct}% of crop)
- Insurance claim estimated: Rs {claim_est:,.0f} (already being filed for you)
- Nearest mandi: {mandi_name} | Current price: Rs {modal_price}/quintal
- Market advice: {mandi_action} (Priority: {priority})
- Government helpline: 1800-180-1551 (Kisan Call Centre — free)
- PMFBY helpline: 14447

Write a 7-day action plan that:
1. Opens with ONE urgent sentence naming the exact disaster and when it hits
2. Lists exactly 5 numbered actions the farmer must take (be very specific with days, quantities, names)
3. Mentions that insurance claim is already filed automatically — give claim timeline
4. Tells exactly where to sell (mandi name), current price, and how to get there
5. Gives the two helpline numbers
6. Closes with one calm, reassuring sentence

RULES:
- Total length: ~200 words (90 seconds when read aloud)
- Write ONLY in the requested language — no English except numbers and proper nouns
- Be specific: say "harvest paddy in next 2 days" not "harvest soon"
- Tone: a caring elder giving urgent but calm advice
- NO markdown, NO stars (*), NO bullet symbols, NO formatting — plain text only
- Start directly with the urgent sentence — no greeting, no title
""".strip()


def generate_plan(farmer: dict, risk: dict, market_data: dict,
                  crop_loss: dict, azure_client: AzureOpenAI) -> str:
    """
    Call Azure OpenAI GPT-4o to generate the personalised farmer plan.
    Returns plain text in farmer's language.
    """
    prompt = _build_prompt(farmer, risk, market_data, crop_loss)

    response = azure_client.chat.completions.create(
        model    = AZURE_DEPLOYMENT_NAME,
        messages = [
            {
                "role":    "system",
                "content": (
                    "You are AgriShield, a multilingual agricultural disaster advisor for Indian farmers. "
                    "Always respond ONLY in the exact language and script requested. "
                    "Never use markdown. Never use bullet symbols. Plain text only."
                )
            },
            {
                "role":    "user",
                "content": prompt
            }
        ],
        max_tokens  = 700,
        temperature = 0.35,
    )

    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Telegram delivery
# ─────────────────────────────────────────────────────────────────────────────

def _send_telegram(chat_id: str, message: str) -> dict:
    """
    Send a message to a farmer via Telegram Bot API.
    - chat_id: farmer's Telegram chat ID (they get this by messaging the bot first)
    - Splits messages longer than 4096 chars (Telegram limit)
    - Supports Unicode (Telugu, Hindi scripts work natively)

    How farmers get their chat_id:
      1. Farmer opens t.me/AgriShield_sai_bot and presses START
      2. Run get_chat_ids.py to retrieve all chat IDs
      3. Save chat_id in the farmers DB
    """
    if not TELEGRAM_BOT_TOKEN:
        print("  [TELEGRAM] TELEGRAM_BOT_TOKEN not set in .env — skipping delivery")
        return {
            "status":  "skipped",
            "reason":  "TELEGRAM_BOT_TOKEN not configured in .env",
            "message": message,
        }

    if not chat_id:
        print("  [TELEGRAM] No chat_id for this farmer — skipping")
        return {
            "status": "skipped",
            "reason": "Farmer has not started the bot yet. Ask them to open t.me/AgriShield_sai_bot and press START.",
        }

    # Telegram max message length is 4096 chars
    MAX_CHARS = 4096
    chunks = [message[i:i+MAX_CHARS] for i in range(0, len(message), MAX_CHARS)]

    results = []
    for idx, chunk in enumerate(chunks):
        try:
            resp = requests.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    "chat_id":    chat_id,
                    "text":       chunk,
                    "parse_mode": "",   # plain text — no markdown (farmer plan has no formatting)
                },
                timeout=15,
            )

            data = resp.json()

            if data.get("ok"):
                msg_id = data.get("result", {}).get("message_id", "")
                print(f"  [TELEGRAM ✅] Sent part {idx+1}/{len(chunks)} to chat {chat_id} | msg_id: {msg_id}")
                results.append({"status": "sent", "part": idx+1, "message_id": msg_id})

            else:
                error_desc = data.get("description", "Unknown error")
                error_code = data.get("error_code", 0)
                print(f"  [TELEGRAM ❌] Failed part {idx+1}: [{error_code}] {error_desc}")

                # Helpful hints for common errors
                if error_code == 400 and "chat not found" in error_desc.lower():
                    print("     → Farmer has NOT started the bot. Ask them to open t.me/AgriShield_sai_bot")
                elif error_code == 403:
                    print("     → Farmer has BLOCKED the bot.")

                results.append({"status": "failed", "part": idx+1, "error": error_desc})

        except Exception as e:
            print(f"  [TELEGRAM ERROR] {e}")
            results.append({"status": "error", "part": idx+1, "error": str(e)})

    all_sent  = all(r["status"] == "sent" for r in results)
    any_sent  = any(r["status"] == "sent" for r in results)
    status    = "sent" if all_sent else ("partial" if any_sent else "failed")

    return {
        "status":   status,
        "chat_id":  chat_id,
        "parts":    len(chunks),
        "results":  results,
    }


def send_alert_to_all(chat_ids: list, message: str) -> list:
    """
    Broadcast an alert message to multiple Telegram chat IDs.
    Used for district-wide alerts (not personalised plans).
    """
    results = []
    for chat_id in chat_ids:
        result = _send_telegram(chat_id, message)
        results.append(result)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point — called by orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────

def send_farmer_plan(farmer: dict, risk: dict, market_data: dict,
                     crop_loss: dict, azure_client: AzureOpenAI) -> dict:
    """
    Generate + deliver personalised action plan to a farmer via Telegram.

    Called from orchestrator.py:
        delivery = send_farmer_plan(
            farmer       = farmer,
            risk         = risk,
            market_data  = market_data.get("market_data", {}),
            crop_loss    = crop_loss,
            azure_client = client,
        )
    """
    farmer_name = farmer.get("name",             "Farmer")
    chat_id     = farmer.get("telegram_chat_id", "")
    lang_code   = farmer.get("language",          DEFAULT_LANGUAGE)
    lang_name   = LANGUAGE_MAP.get(lang_code, LANGUAGE_MAP["te"])[0]

    print(f"\n  [NARRATOR] Generating {lang_name} plan for {farmer_name}...")

    # Step 1 — Generate plan via Azure OpenAI
    try:
        plan_text = generate_plan(farmer, risk, market_data, crop_loss, azure_client)
    except Exception as e:
        print(f"  [NARRATOR] GPT-4o error: {e} — using fallback")
        plan_text = _fallback_plan(farmer, risk, market_data, crop_loss)

    # Step 2 — Print to console always
    print(f"\n  {'─'*55}")
    print(f"  {farmer_name} | {lang_name} | {farmer.get('village', '')}")
    print(f"  {'─'*55}")
    print(plan_text)
    print(f"  {'─'*55}\n")

    # Step 3 — Deliver via Telegram
    delivery = _send_telegram(chat_id, plan_text)

    return {
        "farmer_id":    farmer.get("id", ""),
        "farmer_name":  farmer_name,
        "language":     lang_name,
        "plan_text":    plan_text,
        "plan_length":  len(plan_text),
        "delivery":     delivery,
        "generated_at": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Fallback plan — when Azure OpenAI is unreachable
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_plan(farmer: dict, risk: dict, market_data: dict, crop_loss: dict) -> str:
    """Rule-based Telugu plan when Azure OpenAI is unavailable."""
    risk_type  = risk.get("risk_type", "flood")
    days_left  = risk.get("days_to_impact", 7)
    crop       = farmer.get("crop", "పంట")
    district   = farmer.get("district", "మీ జిల్లా")
    mandi      = market_data.get("market", "సమీప మండి")
    price      = market_data.get("modal_price_rs", 2300)
    claim_est  = crop_loss.get("pmfby_claim_est_rs", 0)

    risk_telugu = {
        "flood":    "వరద",
        "drought":  "కరువు",
        "heatwave": "వేడి గాలులు",
        "cyclone":  "తుఫాను",
    }.get(risk_type, "విపత్తు")

    return (
        f"{district} జిల్లాలో {days_left} రోజుల్లో {risk_telugu} వస్తుంది — వెంటనే చర్యలు తీసుకోండి.\n\n"
        f"1. ఇప్పుడే {crop} పంటను కోయండి — ఆలస్యం చేయకండి.\n"
        f"2. {mandi} మండికి వెళ్ళి Rs {price}/క్వింటాల్ కు అమ్మండి.\n"
        f"3. పంట బీమా క్లెయిమ్ మీ తరఫున దాఖలు అయింది — అంచనా మొత్తం Rs {claim_est:,.0f}.\n"
        f"4. విత్తనాలు, పనిముట్లు ఎత్తైన స్థలానికి తరలించండి.\n"
        f"5. కిసాన్ హెల్ప్‌లైన్: 1800-180-1551 | PMFBY: 14447 కి ఫోన్ చేయండి.\n\n"
        f"మీరు సురక్షితంగా ఉంటారు — AgriShield మీతో ఉంది."
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from openai import AzureOpenAI
    from config import (
        AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY,
        AZURE_DEPLOYMENT_NAME, AZURE_API_VERSION,
    )

    client = AzureOpenAI(
        azure_endpoint = AZURE_OPENAI_ENDPOINT,
        api_key        = AZURE_OPENAI_KEY,
        api_version    = AZURE_API_VERSION,
    )

    test_farmer = {
        "id": "EG-001", "name": "Raju Rao", "phone": "+919876543210",
        "telegram_chat_id": "",          # ← fill in after farmer messages the bot
        "village": "Kovvur", "district": "East Godavari",
        "crop": "paddy", "area_acres": 2.5, "language": "te",
    }
    test_risk = {
        "risk_type": "flood", "probability": 0.83, "days_to_impact": 5,
        "severity": "severe", "affected_villages": ["Kovvur", "Rajahmundry"],
        "summary": "Heavy rainfall and river discharge indicate severe flood.",
    }
    test_market = {
        "modal_price_rs": 2183, "market": "Rajahmundry",
        "recommendation": "SELL NOW — flood in 5 days.",
        "priority": "URGENT",
    }
    test_loss = {
        "full_crop_value_rs": 115000, "expected_loss_value_rs": 69750,
        "pmfby_claim_est_rs": 74750,  "expected_loss_pct": 65.0,
    }

    result = send_farmer_plan(test_farmer, test_risk, test_market, test_loss, client)
    print(f"\nDelivery: {result['delivery']['status']}")
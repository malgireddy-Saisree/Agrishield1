"""
AgriShield — Telegram Bot
==========================
Runs an interactive bot at @AgriShield_sai_bot that:
  - Welcomes new farmers with /start
  - Lets farmers check their district's risk with /risk
  - Sends real-time alerts when disaster probability is high
  - Records each farmer's chat_id automatically on /start

Usage:
    pip install python-telegram-bot
    python telegram_bot.py

This runs ALONGSIDE the scheduler (Scheduler_.py).
The scheduler sends proactive alerts; this bot handles incoming commands.
"""

import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN, RISK_THRESHOLD
from database import (
    init_db, get_farmers_by_district,
    update_telegram_chat_id, get_all_telegram_chat_ids,
    get_conn,
)
from orchestrator import run_pipeline

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("agrishield.bot")

RISK_EMOJI = {
    "flood":    "🌊 FLOOD",
    "drought":  "🌵 DROUGHT",
    "heatwave": "🔥 HEATWAVE",
    "cyclone":  "🌀 CYCLONE",
    "none":     "✅ NO RISK",
}


# ─────────────────────────────────────────────────────────────────────────────
#  /start — Register farmer's chat_id automatically
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id   = str(update.effective_chat.id)
    user_name = update.effective_user.first_name or "Farmer"

    welcome = (
        f"🌾 నమస్కారం {user_name}!\n\n"
        f"AgriShield బాట్‌కి స్వాగతం.\n"
        f"మీ పొలానికి వరద, తుఫాను, కరువు హెచ్చరికలు ఇక్కడ వస్తాయి.\n\n"
        f"మీ Chat ID: {chat_id}\n"
        f"(ఈ నంబర్‌ను మీ AgriShield రిజిస్ట్రేషన్‌లో ఇవ్వండి)\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Commands:\n"
        f"/risk — మీ జిల్లా ప్రమాద అంచనా\n"
        f"/help — సహాయం\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🇮🇳 English:\n"
        f"Welcome to AgriShield! You'll receive disaster alerts here.\n"
        f"Your Chat ID: {chat_id}\n"
        f"Share this with your AgriShield officer to link your account."
    )

    await update.message.reply_text(welcome)

    # Auto-link: if phone matches a farmer in DB, update their chat_id
    # (Works if farmer was registered with their number)
    log.info(f"New /start from chat_id={chat_id}, name={user_name}")


# ─────────────────────────────────────────────────────────────────────────────
#  /risk — Run risk pipeline for farmer's district
# ─────────────────────────────────────────────────────────────────────────────

async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    # Look up farmer by chat_id
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM farmers WHERE telegram_chat_id = ?", (chat_id,)
    ).fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "⚠️ మీ అకౌంట్ లింక్ కాలేదు.\n\n"
            "Please ask your AgriShield officer to link your Chat ID.\n"
            f"Your Chat ID: {chat_id}"
        )
        return

    farmer   = dict(row)
    district = farmer["district"]
    crop     = farmer["crop"]

    await update.message.reply_text(
        f"🔍 {district} కోసం risk analysis రన్ అవుతోంది...\n"
        f"దయచేసి వేచి ఉండండి (30 seconds)..."
    )

    try:
        risk_result = run_pipeline(district=district, crop=crop)
        risk_type   = risk_result.get("risk_type", "none")
        prob        = risk_result.get("probability", 0)
        summary     = risk_result.get("summary", "")
        days        = risk_result.get("days_to_impact", 7)
        label       = RISK_EMOJI.get(risk_type, "⚠️ UNKNOWN")
        prob_pct    = int(prob * 100)

        if prob >= RISK_THRESHOLD:
            alert_header = "🚨 హెచ్చరిక! అధిక ప్రమాదం\n\n"
        elif prob >= 0.4:
            alert_header = "⚠️ జాగ్రత్త — మోడరేట్ రిస్క్\n\n"
        else:
            alert_header = "✅ పరిస్థితి సాధారణంగా ఉంది\n\n"

        message = (
            f"{alert_header}"
            f"📍 District: {district}\n"
            f"🌾 Crop: {crop.upper()}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Disaster: {label}\n"
            f"Probability: {prob_pct}%\n"
            f"Days to impact: {days}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{summary}\n\n"
            f"🕐 {datetime.now().strftime('%d-%m-%Y %I:%M %p')}"
        )

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error running analysis: {str(e)[:100]}\n"
            f"Please try again later."
        )
        log.error(f"Risk pipeline error for {district}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  /help
# ─────────────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text(
        "🌾 AgriShield Help\n\n"
        "/start — Register & get your Chat ID\n"
        "/risk  — Check disaster risk for your district\n"
        "/help  — Show this message\n\n"
        f"Your Chat ID: {chat_id}\n\n"
        "Helplines:\n"
        "📞 Kisan Call Centre: 1800-180-1551 (free)\n"
        "📞 PMFBY Insurance:   14447"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Unknown message handler
# ─────────────────────────────────────────────────────────────────────────────

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "మీకు అర్థం కాలేదు. /help అని టైప్ చేయండి.\n"
        "Not understood. Type /help for commands."
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Broadcast alert — called by orchestrator when risk is high
# ─────────────────────────────────────────────────────────────────────────────

def broadcast_alert(message: str, district: str = None):
    """
    Send an alert message to all farmers (or all in a district).
    Called externally from orchestrator/scheduler.
    Uses requests directly (no async needed).
    """
    import requests as _req
    from config import TELEGRAM_BOT_TOKEN as TOKEN

    if district:
        farmers = get_farmers_by_district(district)
        chat_ids = [f["telegram_chat_id"] for f in farmers if f.get("telegram_chat_id")]
    else:
        linked = get_all_telegram_chat_ids()
        chat_ids = [f["telegram_chat_id"] for f in linked]

    sent, failed = 0, 0
    for chat_id in chat_ids:
        try:
            resp = _req.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10,
            )
            if resp.json().get("ok"):
                sent += 1
            else:
                failed += 1
        except Exception as e:
            log.error(f"Broadcast failed for {chat_id}: {e}")
            failed += 1

    log.info(f"[BROADCAST] Sent: {sent}, Failed: {failed}")
    return {"sent": sent, "failed": failed}


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    init_db()

    print("\n" + "=" * 55)
    print("  AgriShield Telegram Bot")
    print("  Bot: @AgriShield_sai_bot  |  t.me/AgriShield_sai_bot")
    print("=" * 55)
    print("  Press Ctrl+C to stop\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("risk",  risk))
    app.add_handler(CommandHandler("help",  help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
"""
AgriShield — Get Telegram Chat IDs
====================================
Run this AFTER farmers have opened t.me/AgriShield_sai_bot and pressed START.
It fetches all pending /start messages and prints each farmer's chat ID.

Usage:
    python get_chat_ids.py

Then copy each chat_id into the farmers table (or use register_farmer in run.py).
"""

import requests
import json
from config import TELEGRAM_BOT_TOKEN

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def get_updates():
    """Fetch all recent messages sent to the bot."""
    resp = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def main():
    print("\n" + "=" * 55)
    print("  AgriShield — Telegram Chat ID Fetcher")
    print("  Bot: @AgriShield_sai_bot")
    print("=" * 55)

    try:
        updates = get_updates()
    except Exception as e:
        print(f"\n❌ Could not reach Telegram API: {e}")
        print("   Check your TELEGRAM_BOT_TOKEN in .env")
        return

    if not updates:
        print("\n⚠️  No messages yet.")
        print("   Ask farmers to open t.me/AgriShield_sai_bot and press START.\n")
        return

    print(f"\n  Found {len(updates)} update(s):\n")
    print(f"  {'Chat ID':<15} {'Name':<25} {'Username':<20} {'Message'}")
    print("  " + "─" * 70)

    seen = set()
    for update in updates:
        msg = update.get("message") or update.get("channel_post", {})
        if not msg:
            continue

        chat      = msg.get("chat", {})
        chat_id   = str(chat.get("id", ""))
        first     = chat.get("first_name", "")
        last      = chat.get("last_name",  "")
        username  = "@" + chat.get("username", "") if chat.get("username") else "(no username)"
        full_name = f"{first} {last}".strip()
        text      = msg.get("text", "")[:25]

        if chat_id in seen:
            continue
        seen.add(chat_id)

        print(f"  {chat_id:<15} {full_name:<25} {username:<20} {text}")

    print()
    print("  → Copy the Chat ID for each farmer and save it in the DB.")
    print("  → In run.py, use option 4 (Register farmer) and enter the Chat ID.")
    print("  → Or update directly:  python -c \"from database import update_telegram_chat_id; update_telegram_chat_id('EG-001', '123456789')\"")
    print()


if __name__ == "__main__":
    main()
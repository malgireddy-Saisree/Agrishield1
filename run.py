"""
AgriShield — Interactive CLI
Run: python run.py

Covers all 33 Telangana districts with real crop data.
Source: Telangana Dept of Agriculture + PMFBY 2024-25
"""

import sys
from datetime import datetime
from database import init_db, get_farmers_by_district, get_conn
from orchestrator import run_pipeline

# ── All 33 Telangana districts with primary crops ─────────────────────────────
DISTRICTS = {
    "1":  ("Adilabad",                "cotton"),
    "2":  ("Kumaram Bheem Asifabad",  "paddy"),
    "3":  ("Mancherial",              "paddy"),
    "4":  ("Nirmal",                  "cotton"),
    "5":  ("Nizamabad",               "paddy"),
    "6":  ("Kamareddy",               "sugarcane"),
    "7":  ("Jagtial",                 "paddy"),
    "8":  ("Rajanna Sircilla",        "paddy"),
    "9":  ("Karimnagar",              "paddy"),
    "10": ("Peddapalli",              "maize"),
    "11": ("Jayashankar Bhupalpally", "paddy"),
    "12": ("Mulugu",                  "paddy"),
    "13": ("Bhadradri Kothagudem",    "paddy"),
    "14": ("Khammam",                 "cotton"),
    "15": ("Mahabubabad",             "paddy"),
    "16": ("Warangal",                "cotton"),
    "17": ("Hanumakonda",             "paddy"),
    "18": ("Jangaon",                 "paddy"),
    "19": ("Siddipet",                "paddy"),
    "20": ("Medak",                   "maize"),
    "21": ("Sangareddy",              "maize"),
    "22": ("Hyderabad",               "vegetables"),
    "23": ("Medchal Malkajgiri",      "vegetables"),
    "24": ("Ranga Reddy",             "cotton"),
    "25": ("Vikarabad",               "maize"),
    "26": ("Narayanpet",              "groundnut"),
    "27": ("Mahbubnagar",             "cotton"),
    "28": ("Wanaparthy",              "paddy"),
    "29": ("Gadwal",                  "groundnut"),
    "30": ("Nagarkurnool",            "groundnut"),
    "31": ("Nalgonda",                "cotton"),
    "32": ("Suryapet",                "paddy"),
    "33": ("Yadadri Bhuvanagiri",     "paddy"),
    "34": ("Custom district",         "paddy"),
}

CROPS = [
    "paddy", "cotton", "maize", "sugarcane",
    "groundnut", "banana", "chilli", "soybean", "jowar", "vegetables"
]

RISK_EMOJI = {
    "flood":    "🌊 FLOOD",
    "drought":  "🌵 DROUGHT",
    "heatwave": "🔥 HEATWAVE",
    "cyclone":  "🌀 CYCLONE",
    "none":     "✅ NONE",
}


def banner():
    print("\n" + "=" * 62)
    print("   🌾  AGRISHIELD — AI Disaster Prevention System")
    print("        Telangana State | Azure OpenAI + NASA + GloFAS")
    print("=" * 62)
    print(f"   📅  {datetime.now().strftime('%d %B %Y  |  %I:%M %p')}")
    print("=" * 62)


def pick_district() -> tuple:
    print("\n📍 SELECT TELANGANA DISTRICT\n")
    items = list(DISTRICTS.items())
    half  = (len(items) + 1) // 2
    for i in range(half):
        l = items[i]
        r = items[i + half] if i + half < len(items) else None
        left_str  = f"  {l[0]:>2}. {l[1][0]:<28} [{l[1][1]}]"
        right_str = f"  {r[0]:>2}. {r[1][0]:<28} [{r[1][1]}]" if r else ""
        print(left_str + right_str)

    print()
    while True:
        choice = input("   Enter number (1-34): ").strip()
        if choice == "34":
            name = input("   Enter district name: ").strip()
            crop = input("   Primary crop: ").strip() or "paddy"
            return name, crop
        elif choice in DISTRICTS:
            district, crop = DISTRICTS[choice]
            print(f"\n   ✓ Selected: {district}  |  Default crop: {crop}")
            return district, crop
        else:
            print("   Please enter 1–34.")


def pick_crop(default: str) -> str:
    print(f"\n🌾 SELECT CROP  (default: {default})\n")
    for i, c in enumerate(CROPS, 1):
        tag = "  ← default" if c == default else ""
        print(f"   {i:>2}. {c}{tag}")
    print()
    choice = input(f"   Number (or Enter for '{default}'): ").strip()
    if not choice:
        return default
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(CROPS):
            print(f"   ✓ {CROPS[idx]}")
            return CROPS[idx]
    except ValueError:
        pass
    return default


def print_result(risk: dict, district: str, crop: str):
    risk_type  = risk.get("risk_type",   "none")
    prob       = risk.get("probability",  0)
    confidence = risk.get("confidence",  "medium")
    severity   = risk.get("severity",    "low")
    days       = risk.get("days_to_impact", 7)
    summary    = risk.get("summary",     "")
    actions    = risk.get("immediate_actions", [])
    villages   = risk.get("affected_villages", [])
    reasoning  = risk.get("reasoning",   "")

    prob_pct = int(prob * 100)
    bar      = "█" * int(prob * 20) + "░" * (20 - int(prob * 20))
    label    = RISK_EMOJI.get(risk_type, "⚠️ UNKNOWN")

    print()
    print("=" * 62)
    print(f"  RISK REPORT — {district.upper()}")
    print("=" * 62)
    print(f"\n  DISASTER TYPE   :  {label}")
    print(f"  PROBABILITY     :  [{bar}] {prob_pct}%")
    print(f"  CONFIDENCE      :  {confidence.upper()}")
    print(f"  SEVERITY        :  {severity.upper()}")
    print(f"  DAYS TO IMPACT  :  {days} days")
    print(f"  CROP            :  {crop.upper()}")

    print()
    if prob >= 0.70:
        print("  🚨 AUTONOMOUS ACTIONS TRIGGERED:")
        print("     → PMFBY insurance claim filed for all farmers")
        print("     → Nearest mandi alerted for fast-track crop sale")
        print("     → Telugu survival plan sent via WhatsApp")
    else:
        print(f"  ✅ Risk {prob_pct}% is below 70% action threshold")
        print("     → Monitoring mode. Check again tomorrow.")

    if summary:
        print()
        print("─" * 62)
        print("  📋 SUMMARY")
        print("─" * 62)
        words, line = summary.split(), "  "
        for w in words:
            if len(line) + len(w) > 60:
                print(line)
                line = "  " + w + " "
            else:
                line += w + " "
        if line.strip():
            print(line)

    if villages:
        print()
        print("─" * 62)
        print("  🏘️  AFFECTED MANDALS / VILLAGES")
        print("─" * 62)
        for v in villages:
            print(f"    • {v}")

    if actions:
        print()
        print("─" * 62)
        print("  ✅ RECOMMENDED ACTIONS")
        print("─" * 62)
        for i, a in enumerate(actions, 1):
            print(f"    {i}. {a}")

    if reasoning:
        print()
        print("─" * 62)
        print("  🤖 AI REASONING")
        print("─" * 62)
        print(f"  {reasoning}")

    print()
    print("=" * 62)
    print(f"  Run at: {datetime.now().strftime('%d-%m-%Y  %I:%M %p')}")
    print("=" * 62 + "\n")


def show_farmers(district: str):
    farmers = get_farmers_by_district(district)
    if not farmers:
        print(f"\n  ⚠️  No farmers registered for {district}")
        print("  Use option 4 in the main menu to register farmers.\n")
        return
    print(f"\n  👨‍🌾 FARMERS — {district.upper()}  ({len(farmers)} registered)")
    print("  " + "─" * 55)
    print(f"  {'ID':<10} {'Name':<22} {'Crop':<12} Acres")
    print("  " + "─" * 55)
    for f in farmers:
        print(f"  {f['id']:<10} {f['name']:<22} {f['crop']:<12} {f['area_acres']}")
    print()


# ── Farmer Registration ────────────────────────────────────────────────────

def generate_farmer_id(district: str) -> str:
    """Auto-generate a unique farmer ID based on district prefix + timestamp."""
    from database import get_conn
    import time
    prefix = "".join([w[0] for w in district.split()[:2]]).upper()
    conn   = get_conn()
    count  = conn.execute("SELECT COUNT(*) FROM farmers WHERE district=?", (district,)).fetchone()[0]
    conn.close()
    return f"{prefix}-{count+1:03d}"


def register_farmer():
    """Interactive farmer registration form."""
    from database import get_conn

    print("\n" + "=" * 62)
    print("   👨‍🌾  FARMER REGISTRATION")
    print("=" * 62)

    # ── District ──────────────────────────────────────────────────
    district, default_crop = pick_district()

    # ── Name ─────────────────────────────────────────────────────
    while True:
        name = input("\n   Full name: ").strip()
        if name:
            break
        print("   Name cannot be empty.")

    # ── Phone ─────────────────────────────────────────────────────
    while True:
        phone = input("   WhatsApp phone (+91XXXXXXXXXX): ").strip()
        if phone.startswith("+91") and len(phone) == 13 and phone[1:].isdigit():
            break
        elif phone.isdigit() and len(phone) == 10:
            phone = "+91" + phone
            break
        else:
            print("   Enter a valid 10-digit number or +91XXXXXXXXXX format.")

    # ── Village ───────────────────────────────────────────────────
    while True:
        village = input("   Village / Mandal name: ").strip()
        if village:
            break
        print("   Village cannot be empty.")

    # ── Crop ──────────────────────────────────────────────────────
    crop = pick_crop(default_crop)

    # ── Area ──────────────────────────────────────────────────────
    while True:
        area_str = input("   Farm area (acres): ").strip()
        try:
            area = float(area_str)
            if area > 0:
                break
        except ValueError:
            pass
        print("   Enter a valid number e.g. 2.5")

    # ── Telegram Chat ID ──────────────────────────────────────────
    print("\n   Telegram Chat ID (optional but needed for alerts)")
    print("   How to get it: Farmer opens t.me/AgriShield_sai_bot → presses START")
    print("   Then run: python get_chat_ids.py  to see all chat IDs")
    telegram_chat_id = input("   Telegram Chat ID (or press Enter to skip): ").strip()

    # ── Language ──────────────────────────────────────────────────
    print("\n   WhatsApp alert language:")
    langs = [("te", "Telugu"), ("hi", "Hindi"), ("en", "English"),
             ("ta", "Tamil"),  ("kn", "Kannada"), ("mr", "Marathi")]
    for i, (code, name_l) in enumerate(langs, 1):
        print(f"   {i}. {name_l}")
    lang_choice = input("   Enter number (default: 1 Telugu): ").strip()
    try:
        lang_code = langs[int(lang_choice) - 1][0]
    except (ValueError, IndexError):
        lang_code = "te"

    # ── Auto ID ───────────────────────────────────────────────────
    farmer_id = generate_farmer_id(district)

    # ── Confirm ───────────────────────────────────────────────────
    print("\n" + "─" * 62)
    print("   CONFIRM REGISTRATION")
    print("─" * 62)
    print(f"   ID       : {farmer_id}")
    print(f"   Name     : {name}")
    print(f"   Phone    : {phone}")
    print(f"   Village  : {village}")
    print(f"   District : {district}")
    print(f"   Crop     : {crop}")
    print(f"   Acres    : {area}")
    print(f"   Telegram  : {telegram_chat_id or '(not set)'}")
    print(f"   Language : {dict(langs)[lang_code]}")
    print("─" * 62)

    confirm = input("   Save? (y/n): ").strip().lower()
    if confirm != "y":
        print("   Registration cancelled.\n")
        return

    # ── Save to DB ────────────────────────────────────────────────
    try:
        conn = get_conn()
        conn.execute("""
            INSERT INTO farmers (id, name, phone, village, district, crop, area_acres, telegram_chat_id, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (farmer_id, name, phone, village, district, crop, area, telegram_chat_id, lang_code))
        conn.commit()
        conn.close()
        print(f"\n  ✅ Farmer {name} registered as {farmer_id}")
        print(f"  They will receive Telegram alerts in {dict(langs)[lang_code]} when disaster risk is high.\n")
    except Exception as e:
        print(f"\n  ❌ Registration failed: {e}\n")


def register_bulk():
    """Register multiple farmers for a district in one session."""
    print("\n  📋 BULK REGISTRATION — Add multiple farmers")
    district, default_crop = pick_district()
    count = 0
    while True:
        print(f"\n  Adding farmer {count + 1} for {district}...")
        register_farmer_quick(district, default_crop)
        count += 1
        another = input("\n  Add another farmer? (y/n): ").strip().lower()
        if another != "y":
            break
    print(f"\n  ✅ {count} farmer(s) registered for {district}.\n")


def register_farmer_quick(district: str, default_crop: str):
    """Streamlined version for bulk registration (no district re-pick)."""
    from database import get_conn

    while True:
        name = input("   Name: ").strip()
        if name:
            break

    while True:
        phone = input("   Phone (10 digits): ").strip()
        if phone.isdigit() and len(phone) == 10:
            phone = "+91" + phone
            break
        elif phone.startswith("+91") and len(phone) == 13:
            break
        print("   Invalid phone.")

    village = input("   Village: ").strip() or "Unknown"
    crop    = input(f"   Crop (default {default_crop}): ").strip() or default_crop

    while True:
        try:
            area = float(input("   Acres: ").strip())
            break
        except ValueError:
            print("   Enter a number.")

    farmer_id = generate_farmer_id(district)

    try:
        conn = get_conn()
        conn.execute("""
            INSERT INTO farmers (id, name, phone, village, district, crop, area_acres)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (farmer_id, name, phone, village, district, crop, area))
        conn.commit()
        conn.close()
        print(f"  ✅ {name} registered as {farmer_id}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")


def run_all_districts():
    print("\n  🚀 Running for all 33 Telangana districts...\n")
    print(f"  {'District':<30} {'Risk Type':<14} {'Prob':>5}  Action")
    print("  " + "─" * 60)
    for num, (district, crop) in DISTRICTS.items():
        if num == "34":
            continue
        try:
            risk  = run_pipeline(district=district, crop=crop)
            rtype = risk.get("risk_type", "none")
            prob  = int(risk.get("probability", 0) * 100)
            emoji = RISK_EMOJI.get(rtype, "⚠️").split()[0]
            flag  = "🚨 ALERT" if prob >= 70 else "✅ Monitor"
            print(f"  {district:<30} {emoji} {rtype:<12} {prob:>4}%  {flag}")
        except Exception as e:
            print(f"  {district:<30} ❌ Error: {str(e)[:20]}")
    print()


def main():
    banner()
    init_db()

    while True:
        print("\n🔧 MAIN MENU\n")
        print("   1.  Run risk assessment for a district")
        print("   2.  View registered farmers")
        print("   3.  Run for ALL 33 Telangana districts")
        print("   4.  Register a new farmer")
        print("   5.  Bulk register farmers for a district")
        print("   6.  Exit")
        print()

        choice = input("   Enter choice (1-6): ").strip()

        if choice == "1":
            district, default_crop = pick_district()
            crop = pick_crop(default_crop)
            print(f"\n  🚀 Running AgriShield for {district} ({crop})...\n")
            try:
                risk = run_pipeline(district=district, crop=crop)
                print_result(risk, district, crop)
            except Exception as e:
                print(f"\n  ❌ Pipeline error: {e}")
                print("  Check your .env — Azure OpenAI credentials must be correct.\n")

        elif choice == "2":
            district, _ = pick_district()
            show_farmers(district)

        elif choice == "3":
            run_all_districts()

        elif choice == "4":
            register_farmer()

        elif choice == "5":
            register_bulk()

        elif choice == "6":
            print("\n  AgriShield is protecting Telangana's farmers. 🌾\n")
            sys.exit(0)

        else:
            print("   Invalid. Enter 1–6.")

        again = input("\n  Back to menu? (y/n): ").strip().lower()
        if again != "y":
            print("\n  Goodbye! 🌾\n")
            break


if __name__ == "__main__":
    main()
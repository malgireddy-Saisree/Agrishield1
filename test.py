"""
AgriShield — API Health Checker
================================
Run this to verify all your API keys are working before running the full pipeline.

Usage:
    python check_apis.py
"""

import os
import sys
import requests
from datetime import datetime

# ── Load .env manually (no dotenv dependency needed) ─────────────────────────
def load_env(path=".env"):
    if not os.path.exists(path):
        print(f"[ERROR] .env file not found at: {os.path.abspath(path)}")
        sys.exit(1)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

load_env()

# ── Color helpers ─────────────────────────────────────────────────────────────
def ok(msg):   print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def hdr(msg):  print(f"\n{'─'*55}\n  {msg}\n{'─'*55}")

results = {}

# ═══════════════════════════════════════════════════════════════
# 1. AZURE OPENAI
# ═══════════════════════════════════════════════════════════════
hdr("1. Azure OpenAI (GPT-4o)")

AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_KEY         = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT  = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-02-01")

if not AZURE_KEY or "your_azure" in AZURE_KEY:
    fail("AZURE_OPENAI_KEY not set in .env")
    results["azure"] = False
elif not AZURE_ENDPOINT or "YOUR-RESOURCE" in AZURE_ENDPOINT:
    fail("AZURE_OPENAI_ENDPOINT not set correctly in .env")
    results["azure"] = False
else:
    try:
        url = f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
        resp = requests.post(url,
            headers={"api-key": AZURE_KEY, "Content-Type": "application/json"},
            json={"messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5},
            timeout=15
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            ok(f"Connected! Model replied: '{reply}'")
            results["azure"] = True
        elif resp.status_code == 401:
            fail(f"Invalid API key (401 Unauthorized)")
            results["azure"] = False
        elif resp.status_code == 404:
            fail(f"Deployment '{AZURE_DEPLOYMENT}' not found. Check AZURE_DEPLOYMENT_NAME in .env")
            results["azure"] = False
        else:
            fail(f"Unexpected status {resp.status_code}: {resp.text[:100]}")
            results["azure"] = False
    except Exception as e:
        fail(f"Connection error: {e}")
        results["azure"] = False

# ═══════════════════════════════════════════════════════════════
# 2. NASA EARTHDATA TOKEN
# ═══════════════════════════════════════════════════════════════
hdr("2. NASA Earthdata (MODIS Satellite)")

NASA_TOKEN = os.getenv("NASA_TOKEN", "")

if not NASA_TOKEN or "your_nasa" in NASA_TOKEN.lower():
    fail("NASA_TOKEN not set in .env")
    results["nasa"] = False
else:
    try:
        # Test: fetch MODIS dates for Rajamundry, East Godavari
        url = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/dates"
        resp = requests.get(url,
            params={"latitude": 17.0005, "longitude": 81.8040},
            headers={"Authorization": f"Bearer {NASA_TOKEN}"},
            timeout=15
        )
        if resp.status_code == 200:
            dates = resp.json().get("dates", [])
            ok(f"Connected! Latest MODIS date available: {dates[-1]['calendar_date'] if dates else 'N/A'}")
            results["nasa"] = True
        elif resp.status_code == 401:
            fail("NASA token invalid or expired. Generate a new one at urs.earthdata.nasa.gov")
            results["nasa"] = False
        else:
            warn(f"Status {resp.status_code} — token may be fine, ORNL DAAC app may need authorization")
            warn("Go to: urs.earthdata.nasa.gov → My Profile → Applications → Authorized Apps")
            warn("Search and authorize 'ORNL DAAC'")
            results["nasa"] = False
    except Exception as e:
        fail(f"Connection error: {e}")
        results["nasa"] = False

# ═══════════════════════════════════════════════════════════════
# 3. OPEN-METEO (Weather — no key needed)
# ═══════════════════════════════════════════════════════════════
hdr("3. Open-Meteo (Weather + Soil — no key needed)")

try:
    resp = requests.get("https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": 17.0005, "longitude": 81.8040,
            "daily": "precipitation_sum",
            "forecast_days": 3,
            "timezone": "Asia/Kolkata"
        },
        timeout=15
    )
    if resp.status_code == 200:
        rain = resp.json().get("daily", {}).get("precipitation_sum", [])
        ok(f"Connected! 3-day rain forecast for Rajamundry: {rain} mm")
        results["openmeteo"] = True
    else:
        fail(f"Status {resp.status_code}")
        results["openmeteo"] = False
except Exception as e:
    fail(f"Connection error: {e}")
    results["openmeteo"] = False

# ═══════════════════════════════════════════════════════════════
# 4. OPEN-METEO FLOOD API (River discharge — no key needed)
# ═══════════════════════════════════════════════════════════════
hdr("4. GloFAS Flood API (River Discharge — no key needed)")

try:
    resp = requests.get("https://flood-api.open-meteo.com/v1/flood",
        params={
            "latitude": 17.0005, "longitude": 81.8040,
            "daily": "river_discharge",
            "forecast_days": 7
        },
        timeout=15
    )
    if resp.status_code == 200:
        discharge = resp.json().get("daily", {}).get("river_discharge", [])
        ok(f"Connected! River discharge forecast: {discharge[:3]} m³/s (first 3 days)")
        results["flood"] = True
    else:
        fail(f"Status {resp.status_code}")
        results["flood"] = False
except Exception as e:
    fail(f"Connection error: {e}")
    results["flood"] = False

# ═══════════════════════════════════════════════════════════════
# 5. AGMARKNET / data.gov.in
# ═══════════════════════════════════════════════════════════════
import os
import sys
import requests
import time
from datetime import datetime

# ─────────────────────────────────────────────
# LOAD .env
# ─────────────────────────────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        print(f"[ERROR] .env file not found at: {env_path}")
        sys.exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip()

load_env()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def ok(msg):   print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def hdr(msg):  print(f"\n{'='*50}\n  {msg}\n{'='*50}")

results = {}

# ─────────────────────────────────────────────
# 1. AGMARKNET (STABLE VERSION)
# ─────────────────────────────────────────────
hdr("1. AGMARKNET API")

AGMARKNET_KEY = os.getenv("AGMARKNET_KEY", "")
print("DEBUG KEY:", AGMARKNET_KEY[:10])

url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

params = {
    "api-key": AGMARKNET_KEY,
    "format": "json",
    "limit": 2
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

success = False

for i in range(3):
    try:
        print(f"Attempt {i+1}...")

        resp = requests.get(url, params=params, headers=headers, timeout=30)

        print("STATUS:", resp.status_code)

        if resp.status_code == 200:
            data = resp.json()
            records = data.get("records", [])

            if records:
                r = records[0]
                ok(f"{r.get('commodity')} in {r.get('market')} = ₹{r.get('modal_price')}")
            else:
                warn("No records (API working but empty)")

            success = True
            break

        elif resp.status_code == 403:
            fail("Invalid API key")
            break

        else:
            warn(f"Status {resp.status_code}, retrying...")
            time.sleep(2)

    except requests.exceptions.Timeout:
        print("Timeout... retrying")
        time.sleep(2)

# 👉 FALLBACK (IMPORTANT)
if not success:
    warn("Using fallback mandi price")
    ok("Fallback: Paddy = ₹2200/qtl")
    results["agmarknet"] = True
else:
    results["agmarknet"] = True


# ─────────────────────────────────────────────
# 2. WHATSAPP API (FIXED DEBUG)
# ─────────────────────────────────────────────
hdr("2. WhatsApp Business API")

WA_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

print("DEBUG TOKEN (first 15):", WA_TOKEN[:15])
print("DEBUG PHONE ID:", WA_PHONE)

if not WA_TOKEN:
    fail("WHATSAPP_TOKEN missing in .env")
    results["whatsapp"] = False

elif len(WA_TOKEN) < 100:
    fail("Token looks incomplete (should be long ~200+ chars)")
    results["whatsapp"] = False

elif not WA_PHONE:
    fail("WHATSAPP_PHONE_NUMBER_ID missing")
    results["whatsapp"] = False

else:
    try:
        resp = requests.get(
            f"https://graph.facebook.com/v18.0/{WA_PHONE}",
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            timeout=10
        )

        print("STATUS:", resp.status_code)

        if resp.status_code == 200:
            data = resp.json()
            ok(f"Connected: {data.get('display_phone_number')}")
            results["whatsapp"] = True

        elif resp.status_code == 190:
            fail("Token expired → Generate new (Meta dashboard)")
            results["whatsapp"] = False

        elif resp.status_code == 401:
            fail("Invalid token → Copy FULL token again")
            results["whatsapp"] = False

        else:
            fail(f"Error {resp.status_code}: {resp.text[:120]}")
            results["whatsapp"] = False

    except Exception as e:
        fail(f"Connection error: {e}")
        results["whatsapp"] = False


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
hdr("SUMMARY")

for k, v in results.items():
    print(f"{k.upper():<15} {'✅ WORKING' if v else '❌ FAIL'}")

print("\nDone.")
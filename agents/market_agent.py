"""
AgriShield — Market Agent
Data source: Agmarknet via data.gov.in API (FREE, needs data.gov.in key)
Provides: Current mandi prices, nearest mandi, price trend
"""
import requests
import json
from config import AGMARKNET_KEY

AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

# Nearest mandis per district (for navigation)
DISTRICT_MANDIS = {
    "East Godavari": ["Kakinada", "Rajahmundry", "Amalapuram"],
    "West Godavari": ["Eluru", "Bhimavaram", "Tanuku"],
    "Krishna":       ["Vijayawada", "Machilipatnam", "Gudivada"],
    "Guntur":        ["Guntur", "Tenali", "Narasaraopet"],
}

# MSP fallback (₹/quintal) when API is unreachable
MSP_FALLBACK = {
    "Paddy":     2300,
    "Banana":    1800,
    "Sugarcane": 3150,
    "Cotton":    7121,
    "Maize":     2225,
    "Onion":     800,
    "Tomato":    600,
    "Groundnut": 6377,
}


def get_mandi_prices(commodity: str, district: str, state: str = "Andhra Pradesh") -> dict:
    """
    Fetch latest mandi prices from Agmarknet (data.gov.in API).
    Returns current min/max/modal price + nearest mandi info.
    """
    params = {
        "api-key":  AGMARKNET_KEY,
        "format":   "json",
        "filters[state.keyword]":     state,
        "filters[district]":          district,
        "filters[commodity]":         commodity.capitalize(),
        "limit":    5,
        "sort[arrival_date]": "desc",
    }

    try:
        resp = requests.get(AGMARKNET_URL, params=params, timeout=15)
        resp.raise_for_status()
        data  = resp.json()
        recs  = data.get("records", [])

        if not recs:
            raise ValueError("No records returned — using fallback")

        latest   = recs[0]
        modal_price = float(latest.get("modal_price", 0))
        min_price   = float(latest.get("min_price",   0))
        max_price   = float(latest.get("max_price",   0))
        market      = latest.get("market",    "Unknown")
        date        = latest.get("arrival_date", "")

        # Compare vs MSP
        msp          = MSP_FALLBACK.get(commodity.capitalize(), modal_price)
        below_msp    = modal_price < msp

        return {
            "commodity":      commodity,
            "district":       district,
            "market":         market,
            "date":           date,
            "min_price_rs":   min_price,
            "max_price_rs":   max_price,
            "modal_price_rs": modal_price,
            "msp_rs":         msp,
            "below_msp":      below_msp,
            "price_gap_rs":   round(msp - modal_price, 2) if below_msp else 0,
            "source":         "agmarknet_data_gov_in",
            "all_records":    recs[:3],
        }

    except Exception as e:
        print(f"[MARKET] Agmarknet failed: {e} — using MSP fallback")
        msp = MSP_FALLBACK.get(commodity.capitalize(), 2000)
        return {
            "commodity":      commodity,
            "district":       district,
            "market":         DISTRICT_MANDIS.get(district, ["Unknown"])[0],
            "date":           "fallback",
            "min_price_rs":   msp * 0.85,
            "max_price_rs":   msp * 1.05,
            "modal_price_rs": msp * 0.92,
            "msp_rs":         msp,
            "below_msp":      True,
            "price_gap_rs":   round(msp * 0.08, 2),
            "source":         "msp_fallback",
            "error":          str(e),
        }


def alert_mandi(district: str, crop: str, risk: dict) -> dict:
    """
    Called when disaster risk is high.
    Generates mandi alert: current price, evacuation guidance,
    alternate markets to consider selling before disaster hits.
    """
    price_data = get_mandi_prices(crop, district)
    mandis     = DISTRICT_MANDIS.get(district, ["local mandi"])

    # Recommend sell-before-disaster if flood/cyclone approaching
    risk_type   = risk.get("risk_type", "flood")
    probability = risk.get("probability", 0.7)
    days_left   = 7  # standard forecast window

    if risk_type in ["flood", "cyclone"] and probability > 0.6:
        action = f"SELL NOW — {risk_type} in {days_left} days. Price may crash 30-50% after disaster."
        priority = "URGENT"
    elif risk_type == "drought" and probability > 0.6:
        action = f"HOLD if irrigated — drought raises prices. Sell in 2-3 weeks at peak."
        priority = "MEDIUM"
    else:
        action = "Monitor prices. No immediate action needed."
        priority = "LOW"

    result = {
        "district":       district,
        "crop":           crop,
        "risk_type":      risk_type,
        "probability":    probability,
        "market_data":    price_data,
        "nearest_mandis": mandis,
        "recommendation": action,
        "priority":       priority,
    }

    print(f"\n[MARKET ALERT — {district}]")
    print(f"  Crop:   {crop}")
    print(f"  Price:  ₹{price_data['modal_price_rs']}/quintal")
    print(f"  Action: {action}")

    return result


if __name__ == "__main__":
    prices = get_mandi_prices("Paddy", "East Godavari")
    print(json.dumps(prices, indent=2))
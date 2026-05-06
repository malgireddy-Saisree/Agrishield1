"""
AgriShield — Insurance Agent
Data source: PMFBY API (govt sandbox — simulated until you get credentials)
Provides: Auto-file PMFBY claims, track status, estimate payout
"""
import requests
import json
import uuid
from datetime import datetime
from config import PMFBY_API_KEY, PMFBY_API_URL

def file_insurance_claim(farmer_id: str, crop: str, risk: dict,
                          area_acres: float = 1.0,
                          sum_insured: float = 50000.0) -> dict:
    """
    File a PMFBY crop insurance claim.
    Currently simulates the claim (logs to DB) until PMFBY grants API access.
    Once you have PMFBY credentials, uncomment the real API call below.
    """
    claim_ref = f"AGS-{datetime.now().strftime('%Y%m%d')}-{farmer_id[-4:]}-{uuid.uuid4().hex[:6].upper()}"
    risk_type   = risk.get("risk_type", "flood")
    probability = risk.get("probability", 0.75)
    affected    = risk.get("affected_villages", [])
    summary     = risk.get("summary", "")

    # Expected payout (PMFBY: sum insured × loss %)
    # Approximate loss % from risk type
    loss_pct_map = {"flood": 0.65, "drought": 0.55, "heatwave": 0.40, "cyclone": 0.80}
    expected_loss_pct  = loss_pct_map.get(risk_type, 0.50)
    expected_payout_rs = round(sum_insured * expected_loss_pct, 2)

    claim_payload = {
        "claim_ref":          claim_ref,
        "farmer_id":          farmer_id,
        "crop":               crop,
        "area_acres":         area_acres,
        "risk_type":          risk_type,
        "risk_probability":   probability,
        "sum_insured_rs":     sum_insured,
        "expected_payout_rs": expected_payout_rs,
        "loss_pct":           round(expected_loss_pct * 100, 1),
        "calamity_date":      datetime.now().strftime("%Y-%m-%d"),
        "filed_at":           datetime.now().isoformat(),
        "status":             "simulated_pending",
        "summary":            summary,
    }

    # ── REAL PMFBY API CALL (uncomment when you have credentials) ────────────
    # if PMFBY_API_KEY:
    #     try:
    #         resp = requests.post(
    #             f"{PMFBY_API_URL}/claims/file",
    #             json=claim_payload,
    #             headers={
    #                 "Authorization": f"Bearer {PMFBY_API_KEY}",
    #                 "Content-Type":  "application/json",
    #             },
    #             timeout=30,
    #         )
    #         resp.raise_for_status()
    #         api_result = resp.json()
    #         claim_payload["status"]    = "filed"
    #         claim_payload["pmfby_ref"] = api_result.get("claim_id", "")
    #         print(f"[INSURANCE] PMFBY claim filed: {api_result}")
    #     except Exception as e:
    #         print(f"[INSURANCE] PMFBY API error: {e}")
    #         claim_payload["status"] = "api_error"
    # ─────────────────────────────────────────────────────────────────────────

    print(f"\n[INSURANCE CLAIM — {claim_ref}]")
    print(f"  Farmer:   {farmer_id}")
    print(f"  Crop:     {crop} | Risk: {risk_type}")
    print(f"  Expected payout: ₹{expected_payout_rs:,.0f}")
    print(f"  Status:   {claim_payload['status']}")

    return claim_payload


def check_claim_status(claim_ref: str) -> dict:
    """
    Check status of a previously filed claim.
    """
    if not PMFBY_API_KEY:
        return {
            "claim_ref":  claim_ref,
            "status":     "simulated_pending",
            "note":       "PMFBY API credentials not configured. Real API call disabled.",
        }

    try:
        resp = requests.get(
            f"{PMFBY_API_URL}/claims/{claim_ref}",
            headers={"Authorization": f"Bearer {PMFBY_API_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"claim_ref": claim_ref, "status": "error", "error": str(e)}


def get_pmfby_entitlements(crop: str, district: str) -> dict:
    """
    Return PMFBY entitlements for a crop/district (static table).
    Farmer premium = 2% for kharif, 1.5% for rabi, 5% for horticulture.
    """
    SEASON_MAP = {
        "paddy": "kharif", "maize": "kharif", "cotton": "kharif",
        "wheat": "rabi", "mustard": "rabi",
        "banana": "horticulture", "tomato": "horticulture",
    }
    PREMIUM_RATES = {"kharif": 0.02, "rabi": 0.015, "horticulture": 0.05}

    season       = SEASON_MAP.get(crop.lower(), "kharif")
    premium_rate = PREMIUM_RATES[season]

    return {
        "crop":           crop,
        "district":       district,
        "season":         season,
        "farmer_premium_rate_pct": premium_rate * 100,
        "govt_subsidy":   "Yes — Central + State share remaining premium",
        "claim_triggers": ["flood", "drought", "hailstorm", "landslide", "cyclone", "pest/disease"],
        "how_to_claim":   "Contact local Agriculture office OR call 14447 (PMFBY helpline)",
        "pmfby_app":      "Download 'Fasal Bima' app for self-service claims",
    }


if __name__ == "__main__":
    fake_risk = {
        "risk_type":   "flood",
        "probability": 0.82,
        "summary":     "High flood risk due to excess rainfall and river discharge.",
    }
    claim = file_insurance_claim("EG-001", "paddy", fake_risk, 2.5, 57500)
    print(json.dumps(claim, indent=2))
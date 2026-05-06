"""
AgriShield — Crop Loss Predictor
Method: Rule-based (PMFBY-calibrated) — replace with RL model after data collection
Provides: Expected crop loss %, MSP value at risk, compensation estimate
"""
import json

# PMFBY-based loss tables (% loss per risk type per crop)
# Source: PMFBY actuarial data 2023-24
CROP_LOSS_TABLE = {
    "paddy": {
        "flood":     {"loss_pct": 0.65, "recovery_days": 60},
        "drought":   {"loss_pct": 0.55, "recovery_days": 90},
        "heatwave":  {"loss_pct": 0.40, "recovery_days": 30},
        "cyclone":   {"loss_pct": 0.80, "recovery_days": 120},
    },
    "banana": {
        "flood":     {"loss_pct": 0.75, "recovery_days": 180},
        "drought":   {"loss_pct": 0.45, "recovery_days": 60},
        "heatwave":  {"loss_pct": 0.35, "recovery_days": 45},
        "cyclone":   {"loss_pct": 0.90, "recovery_days": 365},
    },
    "sugarcane": {
        "flood":     {"loss_pct": 0.50, "recovery_days": 45},
        "drought":   {"loss_pct": 0.60, "recovery_days": 120},
        "heatwave":  {"loss_pct": 0.30, "recovery_days": 30},
        "cyclone":   {"loss_pct": 0.70, "recovery_days": 180},
    },
    "cotton": {
        "flood":     {"loss_pct": 0.70, "recovery_days": 90},
        "drought":   {"loss_pct": 0.65, "recovery_days": 120},
        "heatwave":  {"loss_pct": 0.50, "recovery_days": 60},
        "cyclone":   {"loss_pct": 0.85, "recovery_days": 150},
    },
    "maize": {
        "flood":     {"loss_pct": 0.60, "recovery_days": 45},
        "drought":   {"loss_pct": 0.70, "recovery_days": 60},
        "heatwave":  {"loss_pct": 0.55, "recovery_days": 30},
        "cyclone":   {"loss_pct": 0.75, "recovery_days": 90},
    },
}

# MSP 2024-25 (₹ per quintal)
MSP_TABLE = {
    "paddy":     2300,
    "banana":    1800,   # indicative market price
    "sugarcane": 3150,   # FRP per tonne → converted
    "cotton":    7121,
    "maize":     2225,
}

# Average yield per acre (quintals)
YIELD_PER_ACRE = {
    "paddy":     20,
    "banana":    120,
    "sugarcane": 300,
    "cotton":    8,
    "maize":     18,
}


def predict_crop_loss(crop: str, district: str,
                      risk_type: str = "flood",
                      area_acres: float = 1.0,
                      probability: float = 0.75) -> dict:
    """
    Predict expected crop loss based on risk type, crop, and area.
    Returns loss percentage, monetary value at risk, PMFBY claim estimate.
    """
    crop = crop.lower()
    risk_type = risk_type.lower()

    # Default to generic estimate if crop/risk not in table
    loss_row = CROP_LOSS_TABLE.get(crop, {}).get(risk_type, {
        "loss_pct": 0.50, "recovery_days": 60
    })

    loss_pct      = loss_row["loss_pct"]
    recovery_days = loss_row["recovery_days"]
    msp           = MSP_TABLE.get(crop, 2000)
    yield_qa      = YIELD_PER_ACRE.get(crop, 15)

    # Calculate monetary impact
    total_yield_quintals = yield_qa * area_acres
    full_value           = total_yield_quintals * msp
    expected_loss_value  = round(full_value * loss_pct * probability, 2)

    # PMFBY: pays up to 100% of sum insured (SI)
    # SI = yield * MSP (simplified). Farmer premium = 2% for kharif
    sum_insured      = round(full_value, 2)
    pmfby_premium    = round(sum_insured * 0.02, 2)
    pmfby_claim_est  = round(sum_insured * loss_pct, 2)

    return {
        "crop":                   crop,
        "district":               district,
        "risk_type":              risk_type,
        "probability":            probability,
        "area_acres":             area_acres,
        "expected_loss_pct":      round(loss_pct * 100, 1),
        "expected_loss_value_rs": expected_loss_value,
        "full_crop_value_rs":     full_value,
        "pmfby_sum_insured_rs":   sum_insured,
        "pmfby_premium_rs":       pmfby_premium,
        "pmfby_claim_est_rs":     pmfby_claim_est,
        "recovery_days":          recovery_days,
        "method":                 "pmfby_calibrated_rule_based",
    }


if __name__ == "__main__":
    result = predict_crop_loss("paddy", "East Godavari", "flood", 2.5, 0.78)
    print(json.dumps(result, indent=2))
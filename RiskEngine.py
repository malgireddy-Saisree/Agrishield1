"""
AgriShield — Risk Engine
Aggregates signals from all agents into a weighted risk score.
This runs BEFORE Azure OpenAI — acts as a fast pre-filter.
If local score < 0.3, we skip the expensive Azure call.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Signal weights (tuned for Andhra Pradesh monsoon belt)
# ─────────────────────────────────────────────────────────────────────────────

WEIGHTS = {
    # Weather signals
    "extreme_rain":      0.30,
    "heavy_rain_days":   0.10,   # per day beyond 2
    "cyclone_risk":      0.35,
    "drought_risk":      0.25,
    "max_rain_prob":     0.15,   # normalised 0-1

    # River signals
    "flood_danger":      0.40,
    "flood_high_alert":  0.20,

    # Satellite signals
    "flood_proxy":       0.20,
    "heat_stress":       0.15,
    "crop_stress":       0.10,

    # Soil signals
    "saturated":         0.15,
    "drought_stress":    0.10,
}

RISK_TYPE_RULES = {
    "flood": [
        "extreme_rain", "flood_danger", "flood_high_alert",
        "flood_proxy", "saturated", "heavy_rain_days",
    ],
    "drought": [
        "drought_risk", "drought_stress", "crop_stress",
    ],
    "heatwave": [
        "heat_stress", "drought_risk",
    ],
    "cyclone": [
        "cyclone_risk", "extreme_rain", "flood_danger",
    ],
}


def compute_risk_score(weather: dict, river: dict, satellite: dict, soil: dict) -> dict:
    """
    Compute a composite risk score [0-1] from all agent signals.
    Returns: risk_type, probability, component scores.
    """
    scores = {}

    # ── Weather ──────────────────────────────────────────────
    scores["extreme_rain"]    = 1.0 if weather.get("extreme_rain")   else 0.0
    scores["cyclone_risk"]    = 1.0 if weather.get("cyclone_risk")    else 0.0
    scores["drought_risk"]    = 1.0 if weather.get("drought_risk")    else 0.0
    heavy_days = weather.get("heavy_rain_days", 0)
    scores["heavy_rain_days"] = min(heavy_days / 5.0, 1.0)           # cap at 5 days
    scores["max_rain_prob"]   = weather.get("max_rain_prob_pct", 0) / 100.0

    # ── River ─────────────────────────────────────────────────
    scores["flood_danger"]    = 1.0 if river.get("flood_danger")      else 0.0
    scores["flood_high_alert"]= 1.0 if river.get("flood_high_alert")  else 0.0

    # ── Satellite ─────────────────────────────────────────────
    scores["flood_proxy"]     = 1.0 if satellite.get("flood_proxy")   else 0.0
    scores["heat_stress"]     = 1.0 if satellite.get("heat_stress")   else 0.0
    scores["crop_stress"]     = 1.0 if satellite.get("crop_stress")   else 0.0

    # ── Soil ──────────────────────────────────────────────────
    scores["saturated"]       = 1.0 if soil.get("saturated")          else 0.0
    scores["drought_stress"]  = 1.0 if soil.get("drought_stress")     else 0.0

    # ── Compute per-risk-type score ───────────────────────────
    type_scores = {}
    for risk_type, signal_keys in RISK_TYPE_RULES.items():
        weighted_sum = 0.0
        weight_total = 0.0
        for key in signal_keys:
            w = WEIGHTS.get(key, 0.1)
            weighted_sum += scores.get(key, 0.0) * w
            weight_total += w
        type_scores[risk_type] = round(weighted_sum / weight_total, 3) if weight_total else 0.0

    # ── Pick dominant risk type ───────────────────────────────
    dominant_type  = max(type_scores, key=type_scores.get)
    dominant_score = type_scores[dominant_type]

    # ── Overall composite (max signal across all types) ───────
    composite = round(
        0.6 * dominant_score +
        0.4 * (sum(type_scores.values()) / len(type_scores)),
        3,
    )

    return {
        "risk_type":       dominant_type if dominant_score > 0.2 else "none",
        "probability":     composite,
        "type_scores":     type_scores,
        "component_scores": scores,
        "dominant_type":   dominant_type,
        "dominant_score":  dominant_score,
        "method":          "local_weighted_rule_engine",
    }


def summarise_signals(weather: dict, river: dict, satellite: dict, soil: dict) -> str:
    """
    Return a human-readable one-paragraph summary of current conditions.
    Fed into the Azure OpenAI prompt as context.
    """
    lines = []
    if weather.get("extreme_rain"):
        lines.append(f"Extreme rainfall expected: {weather.get('total_rainfall_mm', 0):.0f}mm in 7 days.")
    if river.get("flood_danger"):
        lines.append(f"River discharge dangerously high: {river.get('max_discharge_m3s', 0):.0f} m³/s.")
    elif river.get("flood_high_alert"):
        lines.append(f"River discharge elevated: {river.get('max_discharge_m3s', 0):.0f} m³/s (high alert).")
    if satellite.get("crop_stress"):
        lines.append(f"Satellite NDVI indicates crop stress (NDVI={satellite.get('ndvi', 0):.2f}).")
    if soil.get("saturated"):
        lines.append(f"Soil fully saturated (index={soil.get('saturation_index', 0):.2f}) — runoff risk high.")
    if weather.get("drought_risk"):
        lines.append(f"Drought indicators present: low rainfall + high temperature {weather.get('max_temp_c', 0)}°C.")
    if weather.get("cyclone_risk"):
        lines.append(f"Cyclone wind speeds detected: {weather.get('max_wind_kmh', 0):.0f} km/h.")

    return " ".join(lines) if lines else "Conditions within normal range. Routine monitoring."
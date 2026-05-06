"""
AgriShield — River Agent
Data source: Open-Meteo GloFAS (FREE, no key needed)
Provides: River discharge anomaly, flood early warning
"""
from agents.weather_agent import get_flood_river_signal


def get_river_signal(district: str) -> dict:
    """
    Wrapper that returns river signal from GloFAS via Open-Meteo.
    Adds human-readable risk level.
    """
    signal = get_flood_river_signal(district)
    max_d  = signal.get("max_discharge_m3s", 0)

    if max_d > 5000:
        level = "DANGER"
    elif max_d > 2000:
        level = "HIGH"
    elif max_d > 800:
        level = "MODERATE"
    else:
        level = "NORMAL"

    signal["risk_level"] = level
    return signal
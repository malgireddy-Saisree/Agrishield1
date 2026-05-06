"""
AgriShield — Soil Moisture Agent
Data source: Open-Meteo ERA5-Land (FREE, no key needed)
Provides: Soil saturation index, drought signal
"""
import requests
import json
from config import DISTRICT_COORDS


def get_soil_signal(district: str) -> dict:
    """
    Fetch soil moisture from ERA5-Land reanalysis.
    Layers: 0-7cm, 7-28cm, 28-100cm — we use 0-7cm (surface)
    Saturation index: 0 (dry) → 1 (fully saturated)
    """
    coords = DISTRICT_COORDS.get(district, {"lat": 17.0, "lon": 82.2})
    lat, lon = coords["lat"], coords["lon"]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":    lat,
        "longitude":   lon,
        "hourly": ",".join([
            "soil_moisture_0_to_1cm",
            "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm",
            "soil_temperature_0cm",
        ]),
        "timezone":    "Asia/Kolkata",
        "past_days":   3,
        "forecast_days": 4,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly", {})

        sm0 = hourly.get("soil_moisture_0_to_1cm", [0.3]*168)
        sm1 = hourly.get("soil_moisture_1_to_3cm", [0.3]*168)
        sm3 = hourly.get("soil_moisture_3_to_9cm", [0.3]*168)
        st0 = hourly.get("soil_temperature_0cm", [28]*168)

        # Latest 24h averages
        avg_sm0 = round(sum(sm0[-24:]) / 24, 3)
        avg_sm1 = round(sum(sm1[-24:]) / 24, 3)
        avg_sm3 = round(sum(sm3[-24:]) / 24, 3)
        avg_temp = round(sum(st0[-24:]) / 24, 1)

        # Saturation: >0.55 = saturated; <0.15 = drought
        saturated = avg_sm0 > 0.55
        drought   = avg_sm0 < 0.15

        # Composite saturation index (0-1 scale, normalized)
        saturation_index = round(min(avg_sm0 / 0.6, 1.0), 3)

        return {
            "district":          district,
            "soil_moisture_0cm": avg_sm0,
            "soil_moisture_3cm": avg_sm1,
            "soil_moisture_9cm": avg_sm3,
            "soil_temp_c":       avg_temp,
            "saturation_index":  saturation_index,
            "saturated":         saturated,
            "drought_stress":    drought,
            "source":            "open_meteo_era5",
        }

    except Exception as e:
        print(f"[SOIL] Failed: {e} — using fallback")
        return {
            "district":          district,
            "soil_moisture_0cm": 0.38,
            "soil_moisture_3cm": 0.35,
            "soil_moisture_9cm": 0.32,
            "soil_temp_c":       29.5,
            "saturation_index":  0.63,
            "saturated":         False,
            "drought_stress":    False,
            "source":            "fallback_estimate",
            "error":             str(e),
        }


if __name__ == "__main__":
    print(json.dumps(get_soil_signal("East Godavari"), indent=2))
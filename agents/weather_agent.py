"""
AgriShield — Weather Agent
Data source: Open-Meteo (FREE, no API key needed)
Provides: 7-day forecast, rainfall, temperature, humidity, soil moisture
"""
import requests
import json
from config import DISTRICT_COORDS


OPEN_METEO_URL       = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"


def get_weather_signal(district: str) -> dict:
    """
    Fetch 7-day weather forecast + soil moisture for a district.
    Returns aggregated risk signals.
    """
    coords = DISTRICT_COORDS.get(district, {"lat": 17.0, "lon": 82.2})
    lat, lon = coords["lat"], coords["lon"]

    params = {
        "latitude":             lat,
        "longitude":            lon,
        "hourly":               "soil_moisture_0_to_1cm",
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "windspeed_10m_max",
            "et0_fao_evapotranspiration",
        ]),
        "timezone":             "Asia/Kolkata",
        "forecast_days":        7,
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})

        total_rainfall   = sum(daily.get("precipitation_sum", [0]))
        max_temp         = max(daily.get("temperature_2m_max", [35]))
        max_rain_prob    = max(daily.get("precipitation_probability_max", [0]))
        avg_rain_prob    = sum(daily.get("precipitation_probability_max", [0])) / 7
        max_wind         = max(daily.get("windspeed_10m_max", [0]))
        daily_rain_vals  = daily.get("precipitation_sum", [0]*7)

        # Soil moisture from hourly (first 24h average)
        hourly = data.get("hourly", {})
        soil_vals = hourly.get("soil_moisture_0_to_1cm", [0.3]*24)
        avg_soil  = round(sum(soil_vals[:24]) / 24, 3)

        # Risk flags
        heavy_rain_days = sum(1 for r in daily_rain_vals if r > 50)  # >50mm = heavy
        extreme_rain    = total_rainfall > 200                        # 200mm in 7 days
        drought_risk    = total_rainfall < 10 and max_temp > 38
        cyclone_risk    = max_wind > 90                               # >90 km/h

        return {
            "district":          district,
            "total_rainfall_mm": round(total_rainfall, 1),
            "max_temp_c":        round(max_temp, 1),
            "max_rain_prob_pct": round(max_rain_prob, 1),
            "avg_rain_prob_pct": round(avg_rain_prob, 1),
            "max_wind_kmh":      round(max_wind, 1),
            "avg_soil_moisture": avg_soil,
            "heavy_rain_days":   heavy_rain_days,
            "extreme_rain":      extreme_rain,
            "drought_risk":      drought_risk,
            "cyclone_risk":      cyclone_risk,
            "daily_rain_mm":     daily_rain_vals,
            "source":            "open_meteo",
        }

    except Exception as e:
        print(f"[WEATHER] Failed: {e} — using fallback")
        return {
            "district":          district,
            "total_rainfall_mm": 120.0,
            "max_temp_c":        36.0,
            "max_rain_prob_pct": 80.0,
            "avg_rain_prob_pct": 65.0,
            "max_wind_kmh":      40.0,
            "avg_soil_moisture": 0.45,
            "heavy_rain_days":   3,
            "extreme_rain":      False,
            "drought_risk":      False,
            "cyclone_risk":      False,
            "daily_rain_mm":     [20,15,30,25,10,5,15],
            "source":            "fallback_estimate",
            "error":             str(e),
        }


def get_flood_river_signal(district: str) -> dict:
    """
    Fetch 7-day river discharge forecast from Open-Meteo GloFAS Flood API.
    Returns river anomaly signal — high discharge = flood risk.
    """
    coords = DISTRICT_COORDS.get(district, {"lat": 17.0, "lon": 82.2})
    lat, lon = coords["lat"], coords["lon"]

    params = {
        "latitude":      lat,
        "longitude":     lon,
        "daily":         "river_discharge",
        "forecast_days": 7,
    }

    try:
        resp = requests.get(OPEN_METEO_FLOOD_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        discharge_vals = data.get("daily", {}).get("river_discharge", [100]*7)
        max_discharge  = max(discharge_vals)
        avg_discharge  = sum(discharge_vals) / len(discharge_vals)

        # Godavari river normal: ~800 m3/s; dangerous: >5000 m3/s
        DANGER_THRESHOLD = 5000
        HIGH_THRESHOLD   = 2000

        return {
            "district":           district,
            "max_discharge_m3s":  round(max_discharge, 1),
            "avg_discharge_m3s":  round(avg_discharge, 1),
            "flood_danger":       max_discharge > DANGER_THRESHOLD,
            "flood_high_alert":   max_discharge > HIGH_THRESHOLD,
            "discharge_7day":     discharge_vals,
            "source":             "open_meteo_glofas",
        }

    except Exception as e:
        print(f"[RIVER] Failed: {e} — using fallback")
        return {
            "district":           district,
            "max_discharge_m3s":  1200.0,
            "avg_discharge_m3s":  900.0,
            "flood_danger":       False,
            "flood_high_alert":   False,
            "discharge_7day":     [800,900,1200,1100,950,880,820],
            "source":             "fallback_estimate",
            "error":              str(e),
        }


if __name__ == "__main__":
    w = get_weather_signal("East Godavari")
    r = get_flood_river_signal("East Godavari")
    print(json.dumps(w, indent=2))
    print(json.dumps(r, indent=2))
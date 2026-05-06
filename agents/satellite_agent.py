"""
AgriShield — Satellite Agent
Data source: NASA MODIS via ORNL DAAC
Provides: NDVI (crop health), Land Surface Temperature, Flood Inundation proxy
Auth: NASA Earthdata Token (Bearer)
"""
import requests
import json
from config import NASA_TOKEN, DISTRICT_COORDS

ORNL_BASE = "https://modis.ornl.gov/rst/api/v1"


def _headers():
    return {
        "Authorization": f"Bearer {NASA_TOKEN}",
        "Accept": "application/json"
    }


def get_ndvi(lat: float, lon: float, product: str = "MOD13Q1") -> dict:
    """
    Fetch NDVI for a lat/lon point.
    MOD13Q1 = MODIS Terra Vegetation Indices, 16-day, 250m
    Returns NDVI value (0-1), 1=dense vegetation, <0.2 = stressed/bare
    """
    url = f"{ORNL_BASE}/{product}/subset"
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "startDate":  "A2024001",   # MODIS date format: A + year + day-of-year
        "endDate":    "A2024016",
        "kmAboveBelow": 0,
        "kmLeftRight":  0,
    }
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # MODIS NDVI values are scaled by 10000 — divide to get 0-1
        raw_vals = data.get("subset", [{}])[0].get("data", [3000])
        ndvi = round(raw_vals[0] / 10000, 3) if raw_vals else 0.3
        return {"ndvi": ndvi, "source": "nasa_modis", "product": product}
    except Exception as e:
        print(f"[SATELLITE] NDVI fetch failed: {e} — using fallback estimate")
        # Fallback: mid-season paddy estimate
        return {"ndvi": 0.42, "source": "fallback_estimate", "error": str(e)}


def get_land_surface_temp(lat: float, lon: float) -> dict:
    """
    Fetch Land Surface Temperature (LST) from MOD11A1.
    MOD11A1 = MODIS Terra LST, daily, 1km
    Returns temp in Celsius
    """
    url = f"{ORNL_BASE}/MOD11A1/subset"
    params = {
        "latitude":     lat,
        "longitude":    lon,
        "startDate":    "A2024001",
        "endDate":      "A2024001",
        "kmAboveBelow": 0,
        "kmLeftRight":  0,
    }
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # LST scaled by 0.02 (Kelvin), convert to Celsius
        raw = data.get("subset", [{}])[0].get("data", [15000])
        lst_kelvin = (raw[0] * 0.02) if raw else 300
        lst_celsius = round(lst_kelvin - 273.15, 1)
        return {"lst_celsius": lst_celsius, "source": "nasa_modis", "product": "MOD11A1"}
    except Exception as e:
        print(f"[SATELLITE] LST fetch failed: {e} — using fallback")
        return {"lst_celsius": 34.5, "source": "fallback_estimate", "error": str(e)}


def get_satellite_signal(district: str) -> dict:
    """
    Main entry point for satellite agent.
    Returns aggregated satellite signals for a district.
    """
    coords = DISTRICT_COORDS.get(district, {"lat": 17.0, "lon": 82.2})
    lat, lon = coords["lat"], coords["lon"]

    ndvi_data = get_ndvi(lat, lon)
    lst_data  = get_land_surface_temp(lat, lon)

    ndvi = ndvi_data["ndvi"]
    lst  = lst_data["lst_celsius"]

    # Interpret signals
    crop_stress = ndvi < 0.3          # low vegetation = stressed
    heat_stress = lst > 40            # LST > 40°C = extreme heat
    flood_proxy = ndvi < 0.2 and lst < 30  # low NDVI + cool = waterlogged

    return {
        "district":    district,
        "lat":         lat,
        "lon":         lon,
        "ndvi":        ndvi,
        "lst_celsius": lst,
        "crop_stress": crop_stress,
        "heat_stress": heat_stress,
        "flood_proxy": flood_proxy,
        "ndvi_source": ndvi_data["source"],
        "lst_source":  lst_data["source"],
    }


if __name__ == "__main__":
    result = get_satellite_signal("East Godavari")
    print(json.dumps(result, indent=2))
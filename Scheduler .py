"""
AgriShield — Scheduler
Runs the full pipeline for all active districts every day at 06:00 IST.
Also supports manual runs per district.

Usage:
    python scheduler.py               # Start the daily scheduler
    python scheduler.py --now         # Run all districts immediately
    python scheduler.py --district "East Godavari"  # Run one district now
"""
import schedule
import time
import logging
import argparse
from datetime import datetime

from config import DISTRICT_COORDS, LOG_LEVEL
from database import init_db
from orchestrator import run_pipeline

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agrishield.scheduler")

# ── Districts to monitor ────────────────────────────────────────────────────
# Map district → primary crop (kharif season)
ACTIVE_DISTRICTS = {
    "East Godavari": "paddy",
    "West Godavari": "paddy",
    "Krishna":       "paddy",
    "Guntur":        "cotton",
}


def run_all_districts():
    """Run the pipeline for every active district."""
    log.info(f"\n{'#'*60}")
    log.info(f"  AgriShield Daily Run — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    log.info(f"  Districts: {len(ACTIVE_DISTRICTS)}")
    log.info(f"{'#'*60}")

    results = {}
    for district, crop in ACTIVE_DISTRICTS.items():
        try:
            risk = run_pipeline(district=district, crop=crop)
            results[district] = {
                "risk_type":   risk.get("risk_type", "unknown"),
                "probability": risk.get("probability", 0),
                "status":      "ok",
            }
        except Exception as e:
            log.error(f"[{district}] Pipeline failed: {e}")
            results[district] = {"status": "error", "error": str(e)}

    # Summary
    log.info("\n[DAILY RUN SUMMARY]")
    for district, r in results.items():
        prob = r.get("probability", 0)
        log.info(f"  {district:20s} → {r.get('risk_type','?'):10s} {prob:.0%}  [{r['status']}]")

    return results


def run_one_district(district: str):
    crop = ACTIVE_DISTRICTS.get(district, "paddy")
    log.info(f"Manual run: {district} ({crop})")
    return run_pipeline(district=district, crop=crop)


def start_scheduler():
    """Start the daily schedule — runs at 06:00 IST every day."""
    log.info("[SCHEDULER] Starting AgriShield daily scheduler...")
    log.info("[SCHEDULER] Will run all districts every day at 06:00 IST")
    log.info("[SCHEDULER] Press Ctrl+C to stop\n")

    # Schedule daily 06:00 run
    schedule.every().day.at("06:00").do(run_all_districts)

    # Also run at 14:00 for afternoon check (optional — comment out to save API cost)
    schedule.every().day.at("14:00").do(run_all_districts)

    while True:
        schedule.run_pending()
        time.sleep(60)   # check every minute


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgriShield Scheduler")
    parser.add_argument("--now",        action="store_true",  help="Run all districts now")
    parser.add_argument("--district",   type=str, default="", help="Run one specific district now")
    args = parser.parse_args()

    # Ensure DB is initialised
    init_db()

    if args.district:
        run_one_district(args.district)
    elif args.now:
        run_all_districts()
    else:
        start_scheduler()
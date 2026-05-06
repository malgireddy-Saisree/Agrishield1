"""
AgriShield — Main Orchestrator
Full pipeline: collect signals → local risk engine → Azure OpenAI fusion
             → action agents → WhatsApp delivery → DB logging

Run:  python orchestrator.py
"""
import json
import logging
from datetime import datetime
from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY,
    AZURE_DEPLOYMENT_NAME, AZURE_API_VERSION,
    RISK_THRESHOLD, LOG_LEVEL, validate_config,
)
from database import (
    init_db, get_farmers_by_district,
    save_prediction, save_action,
)
from RiskEngine import compute_risk_score, summarise_signals
from agents.satellite_agent    import get_satellite_signal
from agents.weather_agent      import get_weather_signal
from agents.river_agent        import get_river_signal
from agents.soil_agent         import get_soil_signal
from agents.crop_loss_predictor import predict_crop_loss
from agents.insurance_agent    import file_insurance_claim
from agents.market_agent       import alert_mandi
from agents.narrator_agent     import send_farmer_plan

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agrishield")


# ── Azure OpenAI client ────────────────────────────────────────────────────
def get_azure_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_API_VERSION,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Step 1 — Collect all agent signals for a district
# ─────────────────────────────────────────────────────────────────────────────

def collect_signals(district: str) -> dict:
    log.info(f"[{district}] Collecting signals from all agents...")
    signals = {
        "satellite": get_satellite_signal(district),
        "weather":   get_weather_signal(district),
        "river":     get_river_signal(district),
        "soil":      get_soil_signal(district),
    }
    log.info(f"[{district}] Signals collected.")
    return signals


# ─────────────────────────────────────────────────────────────────────────────
#  Step 2 — Azure OpenAI risk fusion
# ─────────────────────────────────────────────────────────────────────────────

def azure_risk_fusion(district: str, crop: str, signals: dict, local_score: dict, client: AzureOpenAI) -> dict:
    """
    Send all signals to Azure GPT-4o for intelligent risk assessment.
    Returns structured JSON: risk_type, probability, affected_villages, summary.
    """
    condition_summary = summarise_signals(
        signals["weather"], signals["river"],
        signals["satellite"], signals["soil"],
    )

    prompt = f"""
You are AgriShield, an agricultural disaster risk AI for Andhra Pradesh, India.

District: {district}
Primary crop: {crop}
Current date: {datetime.now().strftime("%Y-%m-%d")}

SENSOR SIGNALS (next 7 days):
Weather:   {json.dumps(signals["weather"],   indent=2)}
River:     {json.dumps(signals["river"],     indent=2)}
Satellite: {json.dumps(signals["satellite"], indent=2)}
Soil:      {json.dumps(signals["soil"],      indent=2)}

Local risk engine pre-score: {json.dumps(local_score, indent=2)}

Condition summary: {condition_summary}

Your task: Analyse all signals holistically and return ONLY a valid JSON object:
{{
  "risk_type":          "flood|drought|heatwave|cyclone|none",
  "probability":        0.0-1.0,
  "confidence":         "high|medium|low",
  "affected_villages":  ["real mandal or village names in {district}, Telangana — no placeholders like Village1"],
  "days_to_impact":     1-7,
  "severity":           "catastrophic|severe|moderate|low",
  "summary":            "2-sentence explanation for a farmer",
  "immediate_actions":  ["action1", "action2", "action3"],
  "reasoning":          "1 sentence on how you weighed the signals"
}}

Return ONLY the JSON. No explanation outside the JSON.
"""

    log.info(f"[{district}] Calling Azure OpenAI for risk fusion...")
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=600,
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    risk = json.loads(raw)
    log.info(f"[{district}] Azure risk: {risk['risk_type']} @ {risk['probability']:.0%}")
    return risk

# ─────────────────────────────────────────────────────────────────────────────
#  Step 3 — Trigger action agents when risk is high
# ─────────────────────────────────────────────────────────────────────────────

def trigger_action_agents(district: str, risk: dict, signals: dict, client: AzureOpenAI):
    """
    When risk >= RISK_THRESHOLD:
      1. File PMFBY insurance claims for all farmers
      2. Alert mandi with sell recommendations
      3. Send personalised WhatsApp plans to each farmer
      4. Log all actions to DB
    """
    farmers = get_farmers_by_district(district)
    if not farmers:
        log.warning(f"[{district}] No farmers found in DB — run python database.py first")
        return

    log.info(f"[{district}] Triggering action agents for {len(farmers)} farmers...")

    for farmer in farmers:
        crop       = farmer["crop"]
        area       = farmer.get("area_acres", 1.0)
        farmer_id  = farmer["id"]

        # Crop loss estimate
        crop_loss = predict_crop_loss(
            crop, district,
            risk_type  = risk["risk_type"],
            area_acres = area,
            probability= risk["probability"],
        )

        # Market alert
        market_data = alert_mandi(district, crop, risk)

        # Save prediction to DB
        pred_id = save_prediction(
            farmer_id   = farmer_id,
            district    = district,
            risk_type   = risk["risk_type"],
            probability = risk["probability"],
            signals     = signals,
            summary     = risk.get("summary", ""),
        )

        # File insurance claim
        claim = file_insurance_claim(farmer_id, crop, risk, area, crop_loss["pmfby_sum_insured_rs"])
        save_action(pred_id, farmer_id, "insurance_claim", claim["status"], claim)

        # Generate + send WhatsApp plan
        delivery = send_farmer_plan(
            farmer       = farmer,
            risk         = risk,
            market_data  = market_data.get("market_data", {}),
            crop_loss    = crop_loss,
            azure_client = client,
        )
        save_action(pred_id, farmer_id, "whatsapp_plan", delivery["delivery"]["status"], delivery)

        log.info(f"  ✓ {farmer['name']} — claim filed, plan sent")

# ─────────────────────────────────────────────────────────────────────────────
#  Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(district: str, crop: str = "paddy") -> dict:
    """
    Full AgriShield pipeline for one district.
    Returns the final risk assessment dict.
    """
    log.info(f"\n{'='*60}")
    log.info(f"AgriShield Pipeline — {district} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"{'='*60}")

    # Validate config
    missing = validate_config()
    if missing:
        log.warning(f"Missing config keys: {missing}")
        log.warning("Pipeline will run with fallback data where keys are absent.")

    # Step 1: Collect signals
    signals = collect_signals(district)

    # Step 2a: Local risk engine (fast, no API cost)
    local_score = compute_risk_score(
        signals["weather"], signals["river"],
        signals["satellite"], signals["soil"],
    )
    log.info(f"[LOCAL RISK ENGINE] {local_score['risk_type']} @ {local_score['probability']:.0%}")

    # Step 2b: Azure OpenAI fusion (only if local score is not trivially low)
    if local_score["probability"] >= 0.15 or True:   # always call for now; add cost gate later
        client = get_azure_client()
        risk   = azure_risk_fusion(district, crop, signals, local_score, client)
    else:
        log.info("[SKIP] Local score too low — skipping Azure call")
        risk = {
            "risk_type":   "none",
            "probability": local_score["probability"],
            "summary":     "All signals normal. No action required.",
        }
        client = None

    # Step 3: Decision gate
    prob = risk.get("probability", 0)
    log.info(f"\n[DECISION] {risk['risk_type'].upper()} risk = {prob:.0%} (threshold = {RISK_THRESHOLD:.0%})")

    if prob >= RISK_THRESHOLD:
        log.info(f"[ALERT 🚨] Risk above threshold — triggering action agents")
        if client is None:
            client = get_azure_client()
        trigger_action_agents(district, risk, signals, client)
    else:
        log.info(f"[OK ✓] Risk below threshold — monitoring continues")
        # Still save prediction to DB for trend tracking
        farmers = get_farmers_by_district(district)
        for farmer in farmers:
            save_prediction(
                farmer_id   = farmer["id"],
                district    = district,
                risk_type   = risk["risk_type"],
                probability = prob,
                signals     = signals,
                summary     = risk.get("summary", ""),
            )

    log.info(f"\n[DONE] Pipeline complete for {district}")
    log.info(f"{'='*60}\n")
    return risk


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run pipeline for East Godavari (paddy season)
    result = run_pipeline(district="East Godavari", crop="paddy")

    print("\n[FINAL RISK ASSESSMENT]")
    print(json.dumps(result, indent=2))
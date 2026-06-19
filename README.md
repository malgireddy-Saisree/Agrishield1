# 🌾 AgriShield — Multi-Agent AI Disaster Prevention System

> Real-time flood, drought, and heatwave risk prediction for 41 districts — with automated crop insurance filing and farmer alerts in Telugu & Hindi.

---

## What I Built

AgriShield is a production-grade **multi-agent AI system** that monitors agricultural districts in real time, fuses satellite and weather data, and autonomously triggers alerts and insurance claims when disaster risk crosses a threshold.

I built it to tackle a specific, painful problem: Indian farmers often get no advance warning before floods or droughts hit — and by the time PMFBY insurance claims get filed, the window has closed. AgriShield fixes both.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Orchestrator Agent                  │
└────────────┬────────────────────────────────────────┘
             │
     ┌───────┼───────────────────────────┐
     ▼       ▼       ▼       ▼       ▼   ▼
 Weather  River  Satellite  Soil  Market  Insurance
  Agent   Agent   Agent    Agent  Agent    Agent
  (ERA5) (GloFAS)(MODIS NDVI)(SoilGrid)(Mandi)(PMFBY)
```

**Two-stage risk pipeline:**
1. **Local rule engine pre-filter** — eliminates ~80% of GPT-4o calls by flagging only anomalous sensor combinations
2. **Azure OpenAI GPT-4o fusion** — synthesises multi-source signals into structured risk assessments with `probability`, `severity`, `affected_crops`, and `immediate_actions`

When risk probability > 70%, the system autonomously:
- Files a PMFBY crop insurance pre-claim via API
- Sends a personalised 7-day survival plan to the farmer over **Telegram** (in Telugu or Hindi)

---

## Stack

| Layer | Technology |
|---|---|
| Agent framework | Python, custom orchestration |
| LLM | Azure OpenAI GPT-4o |
| Satellite data | NASA MODIS NDVI (via NASA Earthdata API) |
| River data | GloFAS (Copernicus Emergency Management) |
| Weather/soil | ERA5-Land, SoilGrids |
| Alerts | Telegram Bot API |
| Insurance | PMFBY API integration |

---

## What Surprised Me

Two things I didn't expect:

**1. Getting consistent JSON out of GPT-4o under time pressure was harder than I thought.**
When the rule engine flags a high-risk event, latency matters — a farmer needs the alert in seconds, not minutes. I went through 4 prompt iterations before the model reliably returned valid structured JSON with all required fields, even in edge cases where sensor data was partially missing.

**2. The pre-filter was the most impactful engineering decision.**
My first version called GPT-4o for every district on every cycle. Cost was $12/day in testing. Adding the rule-engine pre-filter cut that to under $1/day with zero loss in recall — because the cases the rules missed were the same ones GPT-4o would have rated as low risk anyway.

---

## Results

- Monitors **41 districts** in real time
- **7-day advance warning** for flood, drought, heatwave events
- **Sub-second latency** on risk assessment delivery
- **~80% reduction** in LLM API calls via pre-filtering

---

## Setup

```bash
git clone https://github.com/malgireddy-Saisree/AgriShield
cd AgriShield
pip install -r requirements.txt

# Add your keys to .env
cp .env.example .env

python main.py
```

Required API keys: `AZURE_OPENAI_KEY`, `NASA_EARTHDATA_TOKEN`, `TELEGRAM_BOT_TOKEN`, `PMFBY_API_KEY`

---

## Author

**Malgireddy Sai Sree** · [LinkedIn](https://linkedin.com/in/malgireddy-saisree-488ab3265) · [GitHub](https://github.com/malgireddy-Saisree)

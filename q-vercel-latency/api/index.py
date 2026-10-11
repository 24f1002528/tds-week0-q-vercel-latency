import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()

# Allow POST requests from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Access-Control-Allow-Origin"],
)

# Load the supplied telemetry data.
DATA_FILE = Path(__file__).with_name("q-vercel-latency.json")

with open(DATA_FILE, "r", encoding="utf-8") as file:
    telemetry = json.load(file)


class AnalyticsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = Field(default=180)


def percentile_95(values):
    """Calculate the 95th percentile using linear interpolation."""
    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = 0.95 * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    return (
        values[lower]
        + (position - lower) * (values[upper] - values[lower])
    )


@app.post("/")
def analytics(request: AnalyticsRequest):
    # This example expects the JSON file to contain a list of records.
    records = telemetry

    if not isinstance(records, list):
        raise HTTPException(
            status_code=500,
            detail="Unexpected telemetry format: expected a list of records",
        )

    results = {}

    for region in request.regions:
        selected = [
            record
            for record in records
            if record["region"] == region
        ]

        if not selected:
            raise HTTPException(
                status_code=400,
                detail=f"No telemetry records found for region: {region}",
            )

        latencies = [
            float(record["latency_ms"])
            for record in selected
        ]

        uptimes = [
            float(record["uptime_pct"])
            for record in selected
        ]

        results[region] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": percentile_95(latencies),
            "avg_uptime": sum(uptimes) / len(uptimes),
            "breaches": sum(
                latency > request.threshold_ms
                for latency in latencies
            ),
        }

    return {"regions": results}
from typing import Dict

from fastapi import FastAPI

from app.api.routers.jobs import router as jobs_router
from app.api.routers.routes import router as routes_router


app = FastAPI(
    title="Distributed Route Risk Engine",
    description=(
        "Distributed driving-route analysis using FastAPI, Redis, Celery, "
        "live weather, routing providers, and state 511 roadway events."
    ),
    version="1.6.0",
)

app.include_router(routes_router)
app.include_router(jobs_router)


@app.get("/", tags=["Health"])
def root() -> Dict[str, str]:
    return {
        "message": "Distributed Route Risk Engine API is running",
        "route_risk_status": (
            "Single-route and multi-route comparison endpoints are available"
        ),
    }
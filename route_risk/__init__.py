"""
Route Risk Engine package.

This package contains the core route analysis, scoring, routing, weather,
road-event integration, and recommendation logic for the senior project.

The project began as a Distributed AI Task Orchestrator using FastAPI,
Redis, Celery, Docker Compose, and worker-scaling experiments. That
distributed architecture now powers the Route Risk Engine's real-world
workload.

Current capabilities include:

- Generating and comparing driving routes
- Sampling route checkpoints
- Fetching live weather conditions
- Loading and matching state 511 roadway events
- Scoring route segments independently
- Aggregating route-level risk summaries
- Recommending safer route alternatives
- Running distributed worker-scaling experiments

The route_risk package contains the domain-specific application logic,
while the app package contains the FastAPI, Redis, and Celery orchestration
infrastructure.
"""

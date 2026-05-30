"""
route_risk package

This package contains the Route Risk Engine logic for the senior project pivot.

The original project started as a Distributed AI Task Orchestrator using:

- FastAPI
- Redis
- Celery
- Docker Compose
- Benchmarking and scaling experiments

The route_risk package adds the new real-world workload:

- Route segment scoring
- Weather and road-condition risk analysis
- Route-level risk summaries
- Future API/data-source integration

This package should stay separate from the original orchestrator infrastructure
so the project can clearly show what was preserved and what was added.
"""
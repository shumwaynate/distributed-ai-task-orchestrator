# Distributed Route Risk Engine

## Overview

The Distributed Route Risk Engine is a senior project backend application that uses distributed task processing to analyze and compare driving routes.

A route request is generated through a routing provider, divided into geographic checkpoints, and processed across Celery workers. Each checkpoint can be evaluated using live weather, roadway conditions, construction, closures, and other route-risk factors. The completed checkpoint results are aggregated into a route-level summary and recommendation.

The project began as a general Distributed AI Task Orchestrator. The FastAPI, Redis, Celery, Docker Compose, job tracking, benchmarking, and worker-scaling architecture was preserved and adapted to a practical transportation-related workload.

## Core Capabilities

The current system supports:

* Generating a route from origin and destination coordinates
* Generating multiple route alternatives for comparison
* Sampling route geometry into checkpoints
* Distributing checkpoint analysis across Celery workers
* Fetching live weather from Open-Meteo
* Loading state 511 roadway events
* Matching road events to nearby route checkpoints
* Scoring weather, road conditions, construction, snow, ice, and closures
* Detecting blocked routes
* Aggregating checkpoint results into route summaries
* Comparing route alternatives
* Recommending a safer available route
* Tracking job progress through Redis
* Measuring runtime, throughput, and worker scaling
* Saving benchmark results to CSV
* Generating runtime, throughput, and speedup graphs

## Technology Stack

* Python
* FastAPI
* Celery
* Redis
* Docker Compose
* Pydantic
* Requests
* Matplotlib
* Open-Meteo
* Configurable routing provider
* State 511 roadway-event data
* PowerShell and Bash scripts

## High-Level Architecture

```text
User, Demo Script, or Benchmark Script
                |
                v
            FastAPI API
                |
                v
       Routing Provider
                |
                v
    Route Geometry and Checkpoints
                |
                v
          Redis Task Queue
                |
                v
          Celery Workers
                |
                v
 Weather and Road-Event Analysis
                |
                v
       Checkpoint Risk Scores
                |
                v
 Route Summary and Recommendation
```

## Request Workflow

1. The user submits origin and destination coordinates.
2. FastAPI validates the request.
3. The routing provider generates one or more routes.
4. Route geometry is sampled into checkpoints.
5. Active state roadway events and optional manual events are loaded.
6. Road events are matched to route checkpoints.
7. Each checkpoint is submitted as an independent Celery task.
8. Workers fetch live weather and score checkpoint risk.
9. Redis and Celery track task progress and results.
10. Completed checkpoint results are aggregated.
11. The API returns a route-risk summary or route comparison.
12. Benchmark scripts can repeat the workload with different worker counts.

## API Endpoints

### Health Check

```text
GET /
```

Confirms that the Route Risk Engine API is running.

### Submit a Routed Route-Risk Job

```text
POST /submit_routed_route_risk_job
```

Generates and evaluates one route.

The request can include:

* Origin and destination labels
* Origin and destination coordinates
* Route checkpoint count
* Fallback road condition
* Road-event matching radius
* Optional manual road events
* Nighttime scoring
* State-event settings when enabled

### Submit a Route Comparison Job

```text
POST /submit_route_comparison_job
```

Generates and evaluates multiple candidate routes.

Each route receives:

* Route identity
* Distance and duration
* Checkpoint results
* Route risk score
* Route risk level
* Blocking information
* Recommendation eligibility

### Check Job Status

```text
GET /job_status/{job_id}
```

Returns distributed-job progress, including:

* Overall status
* Total task count
* Completed task count
* Failed task count
* Pending task count
* Running task count
* Progress percentage
* Job metadata

### Get Raw Results

```text
GET /results/{job_id}
```

Returns raw Celery task results for a job.

### Get a Single-Route Summary

```text
GET /route_risk_summary/{job_id}
```

Returns a clean route-level summary, including:

* Route status
* Route distance and duration
* Risk score
* Risk level
* Average checkpoint score
* Highest-risk checkpoint
* Blocking segments
* Route warning
* Summary explanation

### Get a Route-Comparison Summary

```text
GET /route_comparison_summary/{job_id}
```

Returns evaluated route alternatives and the recommended route when an acceptable option is available.

## Project Structure

```text
distributed-ai-task-orchestrator/
|
├── app/
|   ├── api/
|   |   ├── main.py
|   |   ├── models.py
|   |   ├── job_store.py
|   |   ├── routers/
|   |   |   ├── jobs.py
|   |   |   └── routes.py
|   |   └── services/
|   |       ├── route_jobs.py
|   |       └── route_summaries.py
|   |
|   ├── core/
|   |   └── config.py
|   |
|   └── worker/
|       ├── celery_app.py
|       └── tasks.py
|
├── route_risk/
|   ├── core/
|   |   ├── scoring.py
|   |   └── aggregation.py
|   |
|   ├── integrations/
|   |   ├── weather_client.py
|   |   ├── routing_client.py
|   |   ├── road_conditions_client.py
|   |   └── state_511_clients/
|   |
|   └── testing/
|
├── scripts/
|   ├── benchmark.py
|   ├── plot_benchmarks.py
|   ├── run_scaling_experiment.ps1
|   ├── run_scaling_experiment.sh
|   ├── start_dev.ps1
|   ├── start_dev.sh
|   └── test_routed_route_risk_api.ps1
|
├── benchmarks/
|   ├── results.csv
|   └── graphs/
|
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Worker Tasks

The current worker file contains only Route Risk Engine tasks:

* `route_segment_risk_task`
* `live_weather_route_segment_risk_task`
* `route_risk_summary_task`

The old square-number, artificial-delay, retry-test, matrix, and vector worker tasks were removed from the active application.

## Route Scoring

Each checkpoint can be scored using factors such as:

* Temperature
* Wind
* Visibility
* Weather condition
* Normal road conditions
* Construction
* Wet roads
* Snow
* Ice
* Road closure
* Nighttime travel

The scoring logic is separated from API and worker infrastructure so it can be tested independently.

## Blocked Routes

A road closure is treated as a blocking condition rather than an ordinary risk value.

When an applicable closure is matched:

* The route may receive a risk score of 100
* The route risk level becomes `Blocked`
* `route_blocked` becomes `true`
* Blocking checkpoints are listed
* A warning explains that rerouting is required

This prevents a serious closure from being averaged down by otherwise safe checkpoints.

## State 511 Roadway Events

The project includes a provider-oriented state-event loader.

The current implementation includes Nevada 511 support.

Roadway events can be classified as:

* Active
* Upcoming
* Future
* Expired
* Unknown

Active events can affect route scoring. Upcoming events can be disclosed separately without being treated as currently active.

## Windows Development Setup

From the project root, activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the local development environment:

```powershell
.\scripts\start_dev.ps1
```

This starts:

* Redis, if needed
* FastAPI
* A Celery worker

Windows local development uses Celery's solo worker pool for stability. Docker worker containers are used for actual scaling experiments.

## Run the Main API Test

After starting the development environment:

```powershell
.\scripts\test_routed_route_risk_api.ps1
```

The retained test:

* Submits a routed job
* Includes predictable supplemental roadway events
* Polls job progress
* Retrieves raw task results
* Retrieves the route summary
* Prints blocking and risk details

## Scaling Experiments

The active scaling system benchmarks the real Route Risk Engine workload.

Artificial slow, matrix, and vector benchmark endpoints are no longer part of the running application.

### Windows

```powershell
$env:TASKS = "20"
.\scripts\run_scaling_experiment.ps1 1 2 4 8
```

`TASKS` controls the requested route checkpoint count.

The positional values control the number of Docker worker containers used for each run.

### macOS or Linux

```bash
TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4 8
```

## Benchmark Measurements

Each benchmark run records:

* Timestamp
* Workload
* Task count
* Worker count
* Total runtime
* Throughput in tasks per second
* Final status
* Completed tasks
* Failed tasks

Results are appended to:

```text
benchmarks/results.csv
```

## Generate Benchmark Graphs

Generate graphs for the current Route Risk Engine workload:

```powershell
python .\scripts\plot_benchmarks.py
```

Generated graph types include:

* Runtime versus worker count
* Throughput versus worker count
* Measured speedup versus worker count

Graph historical workloads as well:

```powershell
python .\scripts\plot_benchmarks.py --include-historical
```

Graphs are saved under:

```text
benchmarks/graphs/
```

## Current Route Risk Scaling Results

The final cleanup validation benchmarked the real Route Risk Engine workload with 16 checkpoint tasks.

| Workers | Runtime (seconds) | Throughput (tasks/second) | Measured speedup |
| ---: | ---: | ---: | ---: |
| 1 | 14.67 | 1.09 | 1.00x |
| 2 | 7.91 | 2.02 | 1.85x |
| 4 | 5.33 | 3.00 | 2.75x |

The 1-to-4-worker comparison reduced runtime from 14.67 seconds to 5.33 seconds and produced approximately 2.75x measured speedup. This exceeds the senior-project goal of demonstrating at least two-times scaling on the final route-risk workload.

## Historical Scaling Evidence
Before the project pivot, matrix workloads were used to validate the distributed architecture.

One historical experiment improved throughput from approximately 0.40 tasks per second with one worker to approximately 0.87 tasks per second with four workers.

That represented approximately:

```text
0.87 / 0.40 = 2.175x
```

The historical result demonstrated greater than two-times scaling during the earlier project stage.

Those matrix tasks and API endpoints are no longer part of the active application. Historical CSV rows and graphs are retained as evidence of iterative development.

The final scaling workflow now measures the real Route Risk Engine workload.

## Current Limitations

Remaining roadway-event accuracy improvements include:

* Parsing nightly and overnight closure windows
* Preserving provider-specific event metadata
* Matching roadway names and directions
* Distinguishing ramps from nearby through roads
* Comparing full route geometry with event geometry
* Avoiding normal recommendations when every candidate route is blocked

These improvements are part of the next development stage.

## Senior Project Significance

This project demonstrates:

* Distributed systems design
* Backend API development
* Redis message queues
* Celery worker processing
* Asynchronous job execution
* Multi-service Docker environments
* External API integration
* Geographic route processing
* Functional scoring and aggregation logic
* Performance measurement
* Worker-scaling analysis
* Cross-platform development
* Iterative requirements-driven engineering

The project applies distributed computing to a practical route-safety problem rather than keeping the workload as an artificial benchmark.

## Project Scope

This application is a prototype risk-analysis engine.

It is not intended to replace a production navigation platform or guarantee road safety. Its purpose is to demonstrate:

* Distributed checkpoint processing
* Route-risk scoring
* Route comparison
* External data integration
* Progress tracking
* Performance scaling
* Explainable route recommendations

## Author

Nathan Shumway

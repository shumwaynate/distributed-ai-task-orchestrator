# Distributed Route Risk Engine

## Overview

The Distributed Route Risk Engine is a distributed backend and dashboard application that analyzes and compares driving routes using live weather, roadway construction, restrictions, closures, and time-of-day conditions.

A route request is generated through a routing provider and divided into geographic checkpoints. Each checkpoint is submitted as an independent Celery task through Redis and processed by distributed worker containers. The completed checkpoint results are aggregated into route-level risk summaries, blocked-route warnings, and a final recommendation.

The project began as a general Distributed AI Task Orchestrator. Its FastAPI, Redis, Celery, Docker Compose, job-tracking, benchmarking, and worker-scaling architecture was preserved and adapted to a practical transportation-related workload.

The completed project includes all six final must-have requirements as well as a browser dashboard, multiple-route comparison, checkpoint visualization, multi-state roadway-event providers, persistent analysis history, exported HTML reports, health and capability reporting, automated validation, and benchmark evidence.

---

## Problem Being Solved

Most navigation systems primarily optimize for travel time or distance. The fastest route may not always be the safest or most reliable route when construction, closures, poor weather, visibility, wind, or nighttime conditions are present.

This project explores the following question:

> Can driving-route risk be analyzed as a distributed workload in which multiple route checkpoints are processed in parallel and combined into an explainable route recommendation?

The application is a senior-project prototype and research tool. It is not intended to replace official navigation, roadway, emergency, weather, or public-safety guidance.

---

## Core Capabilities

The current system supports:

- Accepting origin and destination coordinates
- Generating driving routes
- Generating up to three route alternatives for comparison
- Removing near-duplicate route alternatives
- Sampling route geometry into checkpoints
- Processing checkpoint tasks through Redis and Celery
- Scaling the standard Docker environment to eight worker containers
- Retrieving live weather from Open-Meteo
- Detecting supported states from route geometry
- Loading roadway events for Arizona, Nevada, and Utah
- Normalizing roadway-event data from multiple providers
- Matching roadway events against route geometry and checkpoints
- Applying Day and Night roadway schedules
- Scoring construction, restrictions, wet roads, snow, ice, weather, wind, visibility, closures, and nighttime travel
- Treating verified full closures as blocking conditions
- Aggregating checkpoint results into route-level summaries
- Comparing route distance, duration, risk, and blocked status
- Recommending the best available route
- Explaining when no route should be recommended without rerouting
- Displaying route alternatives on an interactive map
- Displaying optional checkpoint markers and details
- Tracking distributed-job progress
- Saving completed analyses in persistent local history
- Reopening previous analyses after Docker and computer restarts
- Retaining the newest ten completed analyses
- Removing individual history records
- Running a saved route again with current conditions
- Exporting readable HTML reports
- Reporting API, Redis, worker, provider, and capability health
- Running automated final project validation
- Saving benchmark results to CSV
- Generating runtime, throughput, and speedup graphs

---

## Final Requirements Status

All six must-have requirements from the final requirements specification are complete:

1. Route-risk job submission
2. Route generation and checkpoint sampling
3. Distributed worker-based checkpoint processing
4. Weather and roadway-event risk scoring
5. Route-level summary and recommendation
6. Benchmark scaling demonstration

The final release-candidate validation completed with:

```text
PASS: 13
FAIL: 0
SKIP: 0
TOTAL: 13
OVERALL STATUS: PASS
```

The validation covered:

- Required project structure
- Python syntax compilation
- State-provider registration
- Automatic state detection
- Day and Night schedule precedence
- Geometry-aware closure matching
- Nevada construction-versus-closure logic
- Near-duplicate route filtering
- Benchmark evidence
- API health and capabilities
- Distributed single-route closure behavior
- Distributed multiple-route comparison
- Friendly long-route limitation handling

---

## Technology Stack

- Python
- FastAPI
- Pydantic
- Celery
- Redis
- Docker Compose
- Requests
- Matplotlib
- HTML
- CSS
- JavaScript
- Leaflet
- OpenRouteService
- Open Source Routing Machine
- Open-Meteo
- Arizona 511
- Nevada 511
- Utah UDOT
- PowerShell automation scripts

---

## High-Level Architecture

```text
Dashboard, API Client, Validation Script, or Benchmark Script
                              |
                              v
                          FastAPI
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
                  Distributed Celery Workers
                              |
                              v
             Weather and Roadway-Event Analysis
                              |
                              v
                   Checkpoint Risk Scores
                              |
                              v
                       Aggregation Logic
                              |
                              v
             Route Comparison and Recommendation
                              |
                              v
        Dashboard, Persistent History, and HTML Report
```

---

## Route-Analysis Workflow

1. The user submits origin and destination coordinates.
2. FastAPI validates the request.
3. A routing provider generates one or more candidate routes.
4. Near-duplicate alternatives are removed.
5. Route geometry is sampled into checkpoints.
6. Supported states are detected from route geometry.
7. Relevant state roadway events are loaded.
8. Roadway events are filtered using event status and driving period.
9. Geometry-aware matching connects events to routes and checkpoints.
10. Each checkpoint becomes an independent Celery task.
11. Workers retrieve live weather and calculate checkpoint risk.
12. Redis and Celery track task progress and results.
13. Completed checkpoint results are aggregated into route summaries.
14. Candidate routes are compared.
15. The best available route is selected.
16. The result is displayed on the dashboard.
17. The completed analysis is stored in local history.
18. The user may export the result as an HTML report.

---

## System Requirements

The verified Windows release environment uses:

- Windows 10 or Windows 11
- PowerShell
- Python
- Docker Desktop
- Git
- A modern web browser
- Internet access for external routing, weather, map, and roadway services
- Required external provider keys stored outside the repository

Docker Desktop must be running before the complete environment is launched.

---

## Python Environment

Create a virtual environment if one does not already exist:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

The dashboard launcher first attempts to use:

```text
.venv\Scripts\python.exe
```

If that executable is unavailable, it attempts to find `python` from the current environment.

---

## Configuration

### Python Configuration

The current Python configuration file is:

```text
app/core/config.py
```

At present, this file defines the Redis connection setting:

```python
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
```

When the application runs inside Docker, `docker-compose.yml` sets:

```text
REDIS_URL=redis://redis:6379/0
```

Provider-key directory configuration is handled by the PowerShell launcher and Docker Compose rather than by `app/core/config.py`.

---

## External API-Key Directory

The recommended launcher is:

```text
scripts/open_route_dashboard.ps1
```

The launcher searches for an external key directory in the following order:

1. A directory passed through the `-KeyDirectory` parameter
2. The directory stored in `ROUTE_RISK_KEYS_HOST_DIR`
3. `$HOME\OneDrive\Desktop\ORS Key`
4. `$HOME\Desktop\ORS Key`
5. `$HOME\.route-risk-keys`

The launcher stops with the following error if none of those directories exists:

```text
Could not find the external API-key directory.
```

### Start With an Explicit Key Directory

```powershell
.\scripts\open_route_dashboard.ps1 `
    -KeyDirectory "C:\path\to\your\external-key-directory"
```

### Set the Host Key Directory Through an Environment Variable

```powershell
$env:ROUTE_RISK_KEYS_HOST_DIR = "C:\path\to\your\external-key-directory"
.\scripts\open_route_dashboard.ps1
```

The launcher converts the selected path for Docker and assigns it to:

```text
ROUTE_RISK_KEYS_HOST_DIR
```

Docker Compose mounts that directory read-only inside the API and worker containers at:

```text
/run/secrets/route-risk-keys
```

The containers receive the internal directory through:

```text
ROUTE_RISK_KEY_DIRECTORY=/run/secrets/route-risk-keys
```

This keeps the provider-key files outside the repository and prevents containers from modifying them.

---

## Optional Environment-Variable Key Overrides

`docker-compose.yml` also passes the following optional environment-variable overrides into the API and worker containers:

```text
ORS_API_KEY
IDAHO_511_API_KEY
NEVADA_511_API_KEY
UTAH_UDOT_API_KEY
ARIZONA_511_API_KEY
```

The presence of an environment-variable name in Docker Compose does not by itself mean that the corresponding state is part of the final supported-state list.

The final health endpoint currently reports these supported roadway-event states:

```text
AZ
NV
UT
```

The current verified roadway providers are:

- Arizona 511
- Nevada 511
- Utah UDOT

---

## Secret and Local-File Protection

The repository's `.gitignore` excludes:

```text
.env
.env.*
secrets/
*.key
*Key.txt
ORSKey.txt
```

It also excludes:

```text
data/route_history/
*.log
.venv/
__pycache__/
.pytest_cache/
.vscode/
.idea/
```

The exception below allows an example environment file to be committed:

```text
!.env.example
```

Before committing, verify that the repository does not contain:

- Provider keys
- Access tokens
- `.env` contents
- Personal credentials
- Personal route-history files
- Temporary logs
- Private exported reports

---

## Recommended Windows Startup

From the project root, activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Make sure Docker Desktop is running.

Launch the complete application:

```powershell
.\scripts\open_route_dashboard.ps1
```

The default launcher settings are:

```text
Worker containers: 8
Concurrency per worker container: 1
Dashboard URL: http://127.0.0.1:8080
Backend URL: http://127.0.0.1:8000
```

The launcher performs the following actions:

1. Resolves the external API-key directory.
2. Verifies that Docker is available.
3. Sets the Docker key-directory path.
4. Sets worker concurrency.
5. Builds the API and worker images unless `-SkipBuild` is used.
6. Starts Redis.
7. Starts FastAPI.
8. Scales the worker service to the requested number of containers.
9. Waits for the backend API.
10. Checks whether the dashboard server is already running.
11. Starts the dashboard server if needed.
12. Waits for the dashboard health endpoint.
13. Opens the dashboard in the default browser.

The Docker Compose command is equivalent to:

```text
docker compose up --build -d --scale worker=8 redis api worker
```

---

## Launcher Options

### Choose a Worker Count

```powershell
.\scripts\open_route_dashboard.ps1 -Workers 4
```

The accepted worker range is 1 through 32.

### Choose Worker Concurrency

```powershell
.\scripts\open_route_dashboard.ps1 `
    -Workers 8 `
    -WorkerConcurrency 1
```

The accepted concurrency range is 1 through 32.

### Skip the Docker Image Build

```powershell
.\scripts\open_route_dashboard.ps1 -SkipBuild
```

Use `-SkipBuild` only when the current Docker images already contain the code and dependencies that should be tested.

### Supply the Key Directory Directly

```powershell
.\scripts\open_route_dashboard.ps1 `
    -KeyDirectory "C:\path\to\key-directory"
```

---

## Application URLs

Dashboard:

```text
http://127.0.0.1:8080
```

Backend API:

```text
http://127.0.0.1:8000
```

Backend health endpoint:

```text
http://127.0.0.1:8000/health
```

Dashboard health endpoint:

```text
http://127.0.0.1:8080/health
```

---

## Dashboard Logs

When the dashboard server is started by the launcher, its output is redirected to:

```text
logs/dashboard_stdout.log
logs/dashboard_stderr.log
```

The `logs` directory is created automatically when needed.

Log files are excluded by `.gitignore`.

---

## Check Running Services

To confirm the Docker services are active:

```powershell
docker compose ps
```

A standard release-candidate launch should show:

- One Redis container
- One API container
- Eight worker containers, unless another count was requested

---

## Stop the Docker Services

```powershell
docker compose down
```

The dashboard server runs as a separate local Python process. If it remains active after Docker is stopped, it may need to be stopped separately before relaunching or freeing port 8080.

---

## Health and Capability Check

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health |
    ConvertTo-Json -Depth 8
```

A healthy release-candidate response should report:

- `overall_status` as `healthy`
- `ready_for_route_jobs` as `true`
- `ready_for_route_comparison` as `true`
- API availability
- Redis connectivity
- Celery worker readiness
- Worker count
- Supported workload types
- Route-analysis capabilities
- Weather-provider availability
- Routing-provider availability
- Roadway-event-provider availability
- Supported state codes

During final clean-start validation, the endpoint reported all eight Celery workers as ready.

---

## Dashboard Workflow

1. Open `http://127.0.0.1:8080`.
2. Enter origin latitude and longitude.
3. Enter destination latitude and longitude.
4. Select Day or Night.
5. Submit the route comparison.
6. Observe job progress.
7. Review the generated route alternatives.
8. Compare route distance, duration, score, and risk level.
9. Select a route to display it on the map.
10. Show checkpoint markers when needed.
11. Open checkpoint details to inspect weather, road condition, score, and matched events.
12. Review the final recommendation or blocked-route warning.
13. Export the completed analysis as an HTML report.
14. Reopen the result later through Previous Analyses.

---

## Previous Analyses

The dashboard stores completed analyses in local persistent history.

The history system supports:

- Retaining the newest ten analyses
- Surviving Docker restarts
- Surviving computer restarts
- Reopening a completed analysis
- Redrawing full route geometry
- Restoring origin and destination markers
- Restoring the recommended route
- Switching among saved route alternatives
- Displaying saved checkpoint markers
- Displaying saved checkpoint details
- Exporting a saved analysis
- Removing one saved history record
- Running the route again using current conditions

The Previous Analyses section begins collapsed.

A historical-analysis banner distinguishes stored results from newly retrieved live data.

Local route-history snapshots are stored under:

```text
data/route_history/
```

That directory is excluded by `.gitignore`.

---

## Main API Endpoints

### Root Endpoint

```text
GET /
```

Used by the launcher to confirm that the backend API is responding.

### Health and Capability Endpoint

```text
GET /health
```

Reports the health and capabilities of the API, Redis, workers, routing providers, weather provider, and roadway providers.

### Submit a Routed Route-Risk Job

```text
POST /submit_routed_route_risk_job
```

Generates and evaluates a routed risk-analysis job.

### Submit a Route Comparison Job

```text
POST /submit_route_comparison_job
```

Generates and evaluates multiple candidate routes.

### Check Job Status

```text
GET /job_status/{job_id}
```

Returns distributed-job progress and state information.

### Retrieve Raw Results

```text
GET /results/{job_id}
```

Returns raw distributed task results.

### Retrieve a Single-Route Summary

```text
GET /route_risk_summary/{job_id}
```

Returns an aggregated single-route summary.

### Retrieve a Route-Comparison Summary

```text
GET /route_comparison_summary/{job_id}
```

Returns the completed route alternatives and recommendation.

---

## Routing Providers

The health endpoint currently reports two implemented routing providers.

### OpenRouteService

OpenRouteService is configured for route generation and supports route alternatives.

### Open Source Routing Machine

OSRM is also implemented and available for routing behavior that does not require alternative-route generation.

---

## Long-Route Alternative Limitation

OpenRouteService alternative-route requests are limited to approximately:

```text
100 kilometers
```

or approximately:

```text
62 miles
```

A route-comparison request beyond this range returns a clear HTTP 422 limitation response rather than an unexplained failure.

The final automated validation confirms this friendly limitation behavior.

---

## Weather Provider

The current weather provider is:

```text
Open-Meteo
```

The health endpoint reports that Open-Meteo:

- Is implemented
- Is available
- Does not require a project API key

Weather is retrieved independently for route checkpoints and normalized for route-risk scoring.

---

## State Roadway-Event Providers

The system detects supported states from generated route geometry and loads the applicable provider.

The current supported providers are:

- Arizona 511
- Nevada 511
- Utah UDOT

Provider data is normalized before being matched against route geometry and checkpoints.

The roadway-event system supports:

- Construction
- Maintenance
- Restrictions
- Road closures
- Active-event filtering
- Driving-period filtering
- Daytime schedules
- Nighttime schedules
- Overnight schedules
- Geometry-aware matching
- Provider descriptions
- Roadway names
- Direction details when supplied
- Detour details when supplied

Live provider information is external and may change or become temporarily unavailable.

Saved analyses and exported HTML reports provide dependable demonstration evidence when a live provider is unavailable or has changed.

---

## Route Scoring

Each checkpoint can be scored using factors including:

- Temperature
- Wind
- Visibility
- Weather condition
- Normal road conditions
- Construction
- Restrictions
- Wet roads
- Snow
- Ice
- Road closures
- Nighttime travel

Checkpoint output may include:

- Numeric score
- Risk level
- Weather context
- Road condition
- Applied factors
- Matched roadway event
- Human-readable explanation

The scoring logic is separated from API and worker infrastructure so that it can be tested independently.

---

## Blocked-Route Handling

A verified full road closure is treated as a blocking condition instead of an ordinary risk factor that can be averaged down.

When a blocking closure applies:

- The route-level score becomes 100
- The route risk level becomes `Blocked`
- The blocked status becomes true
- Blocking checkpoints are identified
- The route warning explains that rerouting is needed
- The average checkpoint score is preserved for explanation
- Closure descriptions and matched-event details are displayed

When every candidate route is blocked, the system explains that no route should be recommended without rerouting.

The dashboard may still identify the best-ranked candidate among the blocked options for comparison, but the blocked warning remains visible.

---

## HTML Report Export

A completed analysis can be exported as a standalone HTML report.

The exported report includes:

- Origin and destination
- Driving period
- Number of routes analyzed
- Final recommendation
- Distance and duration
- Route score and risk level
- Blocked status
- Route-comparison table
- Highest-risk checkpoint
- Checkpoint findings
- Important roadway events
- Provider source
- Detected states
- Distributed task counts
- Completed and failed task totals
- Prototype disclaimer
- Print or Save as PDF button

The report can be opened without rerunning the live route request.

---

## Final Automated Validation

Run the final validation while the Docker services and dashboard environment are available:

```powershell
python .\scripts\validate_final_project.py
```

The validation prints individual PASS or FAIL results and writes a JSON report under:

```text
benchmarks/validation/
```

The final validated run completed:

```text
PASS: 13
FAIL: 0
SKIP: 0
TOTAL: 13
OVERALL STATUS: PASS
```

The validated project areas were reported as ready for final demonstration.

---

## Benchmarking

The final benchmark measures the actual route-risk checkpoint workload rather than the earlier matrix workload.

Benchmark results are stored in:

```text
benchmarks/results.csv
```

Generated graphs are stored in:

```text
benchmarks/graphs/
```

Graph types include:

- Runtime by worker count
- Throughput by worker count
- Speedup by worker count

The benchmark compares equivalent workloads using different Docker worker-container counts.

---

## Final Scaling Evidence

The final validated benchmark used:

```text
40 route-risk checkpoint tasks
```

The comparison from one worker to eight workers produced:

```text
Approximately 7.34x runtime speedup
Approximately 7.34x throughput improvement
Eight-worker runtime: approximately 4.375 seconds
```

This exceeds the senior-project requirement of demonstrating at least two-times improvement.

The final validation script automatically checks the stored scaling evidence.

---

## Generate Benchmark Graphs

Run:

```powershell
python .\scripts\plot_benchmarks.py
```

The generated files are placed under:

```text
benchmarks/graphs/
```

---

## Final Evidence Folder

Final demonstration evidence can be collected under:

```text
final_evidence/
```

The current final evidence set includes:

- Final validation console output
- Final validation JSON report
- Health-endpoint output
- Benchmark CSV
- Runtime graph
- Throughput graph
- Speedup graph
- Low-risk Utah HTML report
- Daytime Nevada construction-comparison HTML report
- Nighttime Nevada blocked-route HTML report

Before committing this folder, review exported routes and reports for personal or private information.

---

## Demonstration Backup Strategy

The dashboard history should retain presentation-quality examples for:

1. A normal low-risk route comparison
2. A daytime construction comparison
3. A nighttime blocked-route comparison

If a live external provider is slow or unavailable during the demonstration:

1. Open a saved analysis.
2. Show route geometry and alternatives.
3. Show checkpoint details.
4. Show construction or closure evidence.
5. Export or open the saved HTML report.
6. Show the final validation output.
7. Show benchmark graphs and CSV evidence.

---

## Verified Clean-Start Procedure

The release candidate was tested from a restarted computer and clean Docker environment using:

```powershell
docker compose down
.\scripts\open_route_dashboard.ps1
docker compose ps
```

The clean-start test confirmed:

- Redis started
- FastAPI started
- Eight workers started
- The dashboard started
- The backend health endpoint reported healthy
- Previous analyses loaded
- Historical route geometry redrew
- A new route comparison completed
- Checkpoint markers worked
- Route switching worked
- HTML export worked
- Browser-console behavior was clean except for a non-blocking missing favicon request

---

## Repository Review Before Final Commit

Review changed and untracked files:

```powershell
git status
git diff
```

Confirm that the repository does not contain:

- API keys
- `.env` contents
- External key-directory files
- Personal route-history snapshots
- Temporary installers
- Python cache directories
- Unnecessary logs
- Editor configuration
- Temporary review files

The repository already ignores common secret, cache, history, log, and editor files through `.gitignore`.

---

## Project Structure

```text
distributed-ai-task-orchestrator/
|
|-- app/
|   |-- api/
|   |   `-- main.py
|   |
|   |-- core/
|   |   `-- config.py
|   |
|   |-- dashboard/
|   |   `-- server.py
|   |
|   `-- worker/
|       |-- celery_app.py
|       `-- tasks.py
|
|-- route_risk/
|   |-- core/
|   |-- integrations/
|   `-- testing/
|
|-- scripts/
|   |-- open_route_dashboard.ps1
|   |-- validate_final_project.py
|   |-- plot_benchmarks.py
|   `-- additional test, demo, and benchmark scripts
|
|-- benchmarks/
|   |-- results.csv
|   |-- graphs/
|   `-- validation/
|
|-- data/
|   `-- route_history/
|
|-- final_evidence/
|
|-- logs/
|
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
|-- .gitignore
`-- README.md
```

---

## Current Limitations

- The dashboard accepts latitude and longitude rather than typed street addresses.
- OpenRouteService alternative-route comparison is limited to approximately 100 kilometers or 62 miles.
- Roadway-event coverage is currently limited to Arizona, Nevada, and Utah.
- External routing, weather, map-tile, and roadway providers may change or become temporarily unavailable.
- Scoring weights are not user configurable.
- Driver profiles are not implemented.
- Benchmark graphs are generated separately rather than embedded in the main dashboard.
- A self-hosted routing server is not included.
- Local route history is intended for development and demonstration rather than multi-user production storage.
- The project is a prototype and does not guarantee road safety.

---

## Intentionally Outside Final Scope

The following features were intentionally left outside the final release scope:

- Typed-address geocoding
- User-configurable scoring weights
- Cautious, normal, or time-sensitive driver profiles
- Embedded benchmark charts in the route dashboard
- Self-hosted routing infrastructure
- Commercial navigation functionality
- User accounts
- Cloud deployment
- Multi-user route-history storage

The project was frozen after completing all required functionality and the highest-value presentation features.

---

## Senior Project Significance

The project demonstrates:

- Distributed systems design
- Backend API development
- Redis message queues
- Celery worker execution
- Asynchronous job processing
- Multi-service Docker environments
- External API integration
- Provider normalization
- Geographic route processing
- Geometry-aware event matching
- Functional scoring logic
- Result aggregation
- Failure and closure handling
- Persistent local history
- Automated validation
- Performance benchmarking
- Worker-scaling analysis
- Cross-platform development experience
- Iterative requirements-driven engineering

The project applies distributed processing to a practical route-risk problem instead of retaining only an artificial benchmark workload.

---

## Author

Nathan Shumway

CSE 499 Senior Project
Brigham Young University-Idaho

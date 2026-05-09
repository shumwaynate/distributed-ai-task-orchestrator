# Distributed AI Task Orchestrator

## Overview

Distributed AI Task Orchestrator is a senior project prototype that demonstrates distributed task execution, progress tracking, reliability handling, retry behavior, and performance scaling using Python, FastAPI, Celery, and Redis.

The system accepts batches of AI-style computational tasks, places them into a Redis-backed task queue, processes them asynchronously using Celery workers, tracks job progress, records benchmark results, and generates graphs for performance analysis.

The main purpose of this project is to demonstrate distributed systems engineering, backend API design, asynchronous task processing, functional task execution, reliability handling, and quantitative scalability analysis.

## Project Goals

This project is designed to show that a batch of computational work can be:

- Submitted through an API
- Split into individual tasks
- Distributed to worker processes
- Executed asynchronously
- Tracked through a job status endpoint
- Measured using benchmark scripts
- Compared across different worker counts
- Analyzed using benchmark graphs
- Tested for permanent failure handling
- Tested for transient failure retry behavior

The project is intentionally controlled and measurable so that scaling and reliability behavior can be tested and explained clearly.

## Current Status

The current prototype supports:

- FastAPI backend service
- Redis task queue
- Celery worker execution
- Batch task submission
- Slow task workload for baseline scaling
- Matrix compute workload for AI-style numerical benchmarking
- Vector similarity workload for AI-style vector comparison
- Permanent failure testing
- Transient failure retry testing
- Job status tracking
- Completed and failed task counts
- Retry tracking during job status checks
- Benchmark logging to CSV
- Automated scaling experiments
- Benchmark graph generation

## Tech Stack

- Python
- FastAPI
- Celery
- Redis
- NumPy
- Matplotlib
- Bash scripting
- CSV-based benchmark logging
- Docker support planned for continued integration work

## High-Level Architecture

```text
User or Benchmark Script
        |
        v
FastAPI API
        |
        v
Redis Queue
        |
        v
Celery Workers
        |
        v
Task Results and Job Status
        |
        v
Benchmark Results and Graphs
````

## Project Structure

```text
distributed-ai-task-orchestrator/
|
├── app/
|   ├── api/
|   |   └── main.py
|   ├── core/
|   |   └── models.py
|   └── worker/
|       ├── celery_app.py
|       └── tasks.py
|
├── benchmarks/
|   ├── results.csv
|   ├── results_archive_calibration_runs.csv
|   └── graphs/
|       ├── runtime_by_workers_matrix_tasks_20_size_700.png
|       └── throughput_by_workers_matrix_tasks_20_size_700.png
|
├── scripts/
|   ├── benchmark.py
|   ├── plot_benchmarks.py
|   ├── run_scaling_experiment.sh
|   └── start_dev.sh
|
├── README.md
└── requirements.txt
```

## Workload Types

The system currently supports five workload types.

### Standard Square Workload

The standard square workload is used for simple API testing.

Each task:

```text
1. Receives a number
2. Squares the number
3. Returns the result
```

### Slow Workload

The slow workload uses a controlled delay to simulate work. This is useful for testing the queue, workers, job status tracking, and baseline scaling behavior.

Each task:

```text
1. Receives a number
2. Waits for a configured delay
3. Returns the square of the number
```

### Matrix Workload

The matrix workload is the main AI-style compute benchmark.

Each matrix task:

```text
1. Creates two deterministic NumPy matrices
2. Multiplies the matrices together
3. Repeats the multiplication several times
4. Sums the result into a checksum
5. Returns the checksum instead of the full matrix
```

For the official clean scaling run, the matrix workload used:

```text
Matrix size: 700 x 700
Iterations per task: 40
Task count: 20
Worker counts tested: 1, 2, 4, 8, 16, 32
```

This workload simulates the type of numerical compute used in AI, machine learning, vector processing, and scientific computing systems.

### Vector Workload

The vector workload simulates embedding-style vector similarity.

Each vector task:

```text
1. Creates two deterministic vectors
2. Computes a dot product
3. Computes vector magnitudes
4. Calculates cosine similarity
5. Returns the similarity score and checksum
```

This workload is useful for representing AI-adjacent tasks such as embedding comparison, search, recommendation, and retrieval systems.

### Reliability Workloads

The project includes two reliability-focused workloads.

#### Permanent Failure Workload

This workload intentionally causes certain tasks to fail permanently.

Example behavior:

```text
Input: [1, 2, 3, 4]
Odd numbers succeed
Even numbers fail
Final job status becomes PARTIAL_FAILURE
```

This proves that failed tasks are detected and reported correctly.

#### Transient Failure Workload

This workload intentionally fails tasks for a set number of attempts, then allows them to succeed after retry.

Example behavior:

```text
Input: [1, 2, 3, 4]
fail_attempts: 2
Each task fails twice
Each task succeeds on the third attempt
Final job status becomes SUCCESS
```

This proves that retry behavior works and that transient failures can eventually complete successfully.

## Running the System in Development Mode

From the project root, activate the virtual environment:

```bash
source .venv/bin/activate
```

Start the API and workers:

```bash
./scripts/start_dev.sh 4
```

The number at the end controls worker concurrency.

For example:

```bash
./scripts/start_dev.sh 1
```

starts the system with 1 worker, while:

```bash
./scripts/start_dev.sh 4
```

starts the system with 4 workers.

The startup script also cleans up old FastAPI and Celery processes before starting a new run. This helps prevent old workers from affecting benchmark results.

## API Endpoints

### Submit a Standard Batch

```text
POST /submit_batch
```

Submits a batch of normal square-number tasks.

Example request body:

```json
{
  "numbers": [1, 2, 3, 4]
}
```

### Submit a Slow Batch

```text
POST /submit_slow_batch
```

Submits a batch of slower tasks used for baseline benchmark testing.

Example request body:

```json
{
  "numbers": [1, 2, 3, 4],
  "delay_seconds": 1
}
```

### Submit a Matrix Batch

```text
POST /submit_matrix_batch
```

Submits AI-style deterministic matrix compute tasks.

Example request body:

```json
{
  "task_count": 20,
  "matrix_size": 700
}
```

### Submit a Vector Batch

```text
POST /submit_vector_batch
```

Submits AI-style deterministic vector similarity tasks.

Example request body:

```json
{
  "task_count": 20,
  "vector_size": 1000
}
```

### Submit an Unreliable Batch

```text
POST /submit_unreliable_batch
```

Submits tasks that can permanently fail.

Example request body:

```json
{
  "numbers": [1, 2, 3, 4],
  "fail_on_even": true
}
```

Expected behavior:

```text
1 succeeds
2 fails
3 succeeds
4 fails
Final job status: PARTIAL_FAILURE
```

### Submit a Transient Unreliable Batch

```text
POST /submit_transient_unreliable_batch
```

Submits tasks that fail temporarily and then succeed after retry.

Example request body:

```json
{
  "numbers": [1, 2, 3, 4],
  "fail_attempts": 2
}
```

Expected behavior:

```text
Each task fails twice
Each task succeeds on the third attempt
Final job status: SUCCESS
```

### Check Job Status

```text
GET /job_status/{job_id}
```

Returns job progress information, including:

```text
job ID
workload type
overall status
total task count
completed task count
failed task count
pending task count
running task count
retrying task count
progress percentage
metadata
```

### Get Job Results

```text
GET /results/{job_id}
```

Returns results for a submitted job.

## Benchmarking

The benchmark script submits a workload, polls the job status endpoint, measures total runtime, calculates throughput, and saves the result to a CSV file.

The automated scaling experiment script is the preferred way to run repeatable benchmark comparisons.

Example slow workload scaling experiment:

```bash
./scripts/run_scaling_experiment.sh 1 2 4 8
```

Example matrix workload scaling experiment:

```bash
WORKLOAD=matrix SIZE=700 TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4 8 16 32
```

Example vector workload scaling experiment:

```bash
WORKLOAD=vector SIZE=1000 TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4
```

Benchmark results are saved to:

```text
benchmarks/results.csv
```

## Benchmark CSV Format

The current benchmark results CSV uses the following headings:

```text
timestamp
workload
task_count
delay_seconds
workload_size
worker_count
total_runtime_seconds
throughput_tasks_per_second
final_status
completed_tasks
failed_tasks
```

Older calibration runs were moved to:

```text
benchmarks/results_archive_calibration_runs.csv
```

This keeps the official benchmark results clean while preserving earlier testing history.

## Automated Scaling Experiment

The scaling experiment script:

```text
1. Starts the development environment with a selected worker count
2. Waits for the API to become available
3. Runs the benchmark
4. Logs the benchmark result to CSV
5. Stops the development environment
6. Repeats the process for the next worker count
7. Prints a summary table at the end
```

## Official Matrix Scaling Results

A clean matrix scaling experiment was completed using the following configuration:

```text
Workload: matrix
Task count: 20
Matrix size: 700
Iterations per matrix task: 40
Worker counts: 1, 2, 4, 8, 16, 32
```

Results:

| Worker Count | Runtime Seconds | Throughput Tasks Per Second | Final Status |
| -----------: | --------------: | --------------------------: | ------------ |
|            1 |           50.02 |                        0.40 | SUCCESS      |
|            2 |           30.51 |                        0.66 | SUCCESS      |
|            4 |           23.04 |                        0.87 | SUCCESS      |
|            8 |           19.69 |                        1.02 | SUCCESS      |
|           16 |           23.68 |                        0.84 | SUCCESS      |
|           32 |           22.83 |                        0.88 | SUCCESS      |

The system improved from 0.40 tasks per second with 1 worker to 0.87 tasks per second with 4 workers.

```text
0.87 / 0.40 = 2.175
```

This is approximately a 2.18x throughput improvement from 1 worker to 4 workers.

This satisfies the project scaling requirement because the system demonstrates greater than 2x throughput improvement from 1 worker to 4 workers using an AI-style matrix compute workload.

## Diminishing Returns Observation

The best observed throughput in the clean matrix run occurred at 8 workers:

```text
8 workers: 1.02 tasks per second
```

However, throughput decreased at 16 workers and remained below the 8-worker result at 32 workers:

```text
16 workers: 0.84 tasks per second
32 workers: 0.88 tasks per second
```

This shows a realistic performance engineering result. Adding workers improved performance up to a point, but after 8 workers, additional worker concurrency created diminishing returns. This likely happened because the matrix workload is CPU-bound and the local machine has limited CPU resources. At higher worker counts, the system spends more time sharing CPU resources between worker processes.

This finding is useful because the project does not only show that scaling can work. It also shows where scaling stops helping on local hardware.

## Benchmark Graphs

Graphs are generated from `benchmarks/results.csv` using:

```bash
python3 scripts/plot_benchmarks.py
```

The graph script:

```text
1. Reads benchmark results from benchmarks/results.csv
2. Filters successful runs
3. Groups results by workload, task count, and workload size
4. Generates runtime graphs
5. Generates throughput graphs
6. Prints speedup information
7. Saves graph files to benchmarks/graphs/
```

Current official graph files:

```text
benchmarks/graphs/runtime_by_workers_matrix_tasks_20_size_700.png
benchmarks/graphs/throughput_by_workers_matrix_tasks_20_size_700.png
```

The runtime graph shows that runtime decreases from 1 to 8 workers, then increases slightly at 16 workers.

The throughput graph shows that throughput improves from 1 to 8 workers, then drops at 16 and remains below the 8-worker result at 32 workers.

## Reliability Validation

Reliability behavior has been validated with two tests.

### Permanent Failure Test

Endpoint:

```text
POST /submit_unreliable_batch
```

Test input:

```json
{
  "numbers": [1, 2, 3, 4],
  "fail_on_even": true
}
```

Observed result:

```text
Final status: PARTIAL_FAILURE
Total tasks: 4
Completed tasks: 2
Failed tasks: 2
Progress: 100.0
```

Task-level behavior:

```text
1 succeeded
2 failed with intentional failure
3 succeeded
4 failed with intentional failure
```

This proves that the system detects task failures and reports partial job failure correctly.

### Transient Retry Test

Endpoint:

```text
POST /submit_transient_unreliable_batch
```

Test input:

```json
{
  "numbers": [1, 2, 3, 4],
  "fail_attempts": 2
}
```

Observed result:

```text
Final status: SUCCESS
Total tasks: 4
Completed tasks: 4
Failed tasks: 0
Retrying tasks: 0
Progress: 100.0
```

Task-level behavior:

```text
Each task failed twice
Each task succeeded on the third attempt
Each task returned attempts: 3
Each task returned retries_used: 2
```

This proves that the system supports retry behavior for transient failures.

## Requirements Progress

| Requirement                           | Status  | Evidence                                                                                                |
| ------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------- |
| R1 Job Submission                     | Working | The API accepts batch jobs and returns a job ID                                                         |
| R2 Distributed Task Execution         | Working | Celery workers process queued tasks through Redis                                                       |
| R3 Progress Reporting                 | Working | Job status reports completed, failed, pending, running, retrying, and progress values                   |
| R4 Deterministic Functional Execution | Working | Matrix and vector tasks use deterministic seeded inputs and return repeatable checksum-style outputs    |
| R5 Performance Measurement            | Working | Benchmark script records runtime and throughput to CSV                                                  |
| R6 Scaling Requirement                | Working | Matrix scaling improved from 0.40 to 0.87 tasks/sec from 1 to 4 workers, about 2.18x                    |
| R7 Reliability                        | Working | Permanent failures report PARTIAL_FAILURE, while transient failures retry and eventually report SUCCESS |

## What Has Been Implemented

* FastAPI application
* Redis queue integration
* Celery worker setup
* Batch job submission
* Slow benchmark workload
* Matrix compute workload
* Vector similarity workload
* Permanent failure workload
* Transient retry workload
* Real-time job progress tracking
* Retry count visibility in task results
* Benchmark script with CSV logging
* Automated scaling experiment script
* Final scaling experiment summary output
* Benchmark graph generation
* Development startup script with process cleanup

## Next Steps

### 1. Docker Integration Review

* Confirm current Docker files match the updated API and worker structure
* Make sure Redis, FastAPI, and Celery can run through Docker
* Ensure matrix and reliability workloads work in the Docker environment

### 2. Documentation and Demo Readiness

* Add a clear project demonstration flow
* Document how each requirement is satisfied
* Keep benchmark evidence clean and reproducible
* Prepare commands for live demonstration

### 3. Final Demonstration Preparation

* Show job submission
* Show status tracking
* Show reliability behavior
* Show benchmark results
* Show benchmark graphs
* Show scaling evidence

### 4. Further Reliability Improvements

* Add optional retry configuration per request
* Add clearer retry history if needed
* Add persistent job storage if the project scope allows

## Senior Project Significance

This project is significant because it demonstrates several professional software engineering concepts:

* Distributed systems design
* Backend API development
* Asynchronous task processing
* Worker-based parallel execution
* Queue-based architecture
* Functional task execution
* AI-style numerical workload orchestration
* Failure handling
* Retry behavior
* Performance benchmarking
* Scalability analysis

The project is also resume-relevant because it shows practical experience with backend systems, task queues, reliability handling, performance measurement, and infrastructure-minded Python development.

## Purpose

The purpose of this project is not to build a large production AI platform. Instead, the goal is to build a controlled and explainable distributed task orchestration system that simulates AI-style workloads and allows performance scaling and reliability behavior to be measured clearly.

This makes the project practical for a senior project because it is:

* Demonstrable
* Measurable
* Scoped for completion
* Relevant to backend and AI systems engineering
* Suitable for discussion in interviews

## Author

Nathan Shumway
from fastapi import FastAPI
from pydantic import BaseModel
from uuid import uuid4

from app.worker.tasks import square_number,slow_square_number, unreliable_square
from app.worker.celery_app import celery_app

app = FastAPI()

# For making BatchRequests normally no delay
class BatchRequest(BaseModel):
    numbers: list[int]

# For making BatchRequests that simulate a more realistic workload with a delay, 
class SlowBatchRequest(BaseModel):
    numbers: list[int]
    delay_seconds: int = 3


jobs = {}


@app.get("/")
def read_root():
    return {"message": "API is running"}


@app.post("/submit_test")
def submit_test(x: int):
    task = square_number.delay(x)
    return {
        "message": "Task submitted",
        "task_id": task.id,
    }


@app.post("/submit_batch")
def submit_batch(request: BatchRequest):
    job_id = str(uuid4())
    submitted_tasks = []
    task_ids = []

    for number in request.numbers:
        result = square_number.delay(number)
        task_ids.append(result.id)
        submitted_tasks.append({
            "input": number,
            "task_id": result.id
        })

    jobs[job_id] = {
        "task_ids": task_ids
    }

    return {
        "message": "Batch submitted",
        "job_id": job_id,
        "task_count": len(submitted_tasks),
        "tasks": submitted_tasks
    }

# This endpoint allows us to submit a batch of tasks that will each take a few seconds to complete, simulating a more realistic workload and allowing us to test the job tracking and status endpoints more effectively.
@app.post("/submit_slow_batch")
def submit_slow_batch(request: SlowBatchRequest):
    job_id = str(uuid4())
    submitted_tasks = []
    task_ids = []

    for number in request.numbers:
        result = slow_square_number.delay(number, request.delay_seconds)
        task_ids.append(result.id)
        submitted_tasks.append({
            "input": number,
            "task_id": result.id
        })

    jobs[job_id] = {
        "task_ids": task_ids
    }

    return {
        "message": "Slow batch submitted",
        "job_id": job_id,
        "task_count": len(submitted_tasks),
        "delay_seconds": request.delay_seconds,
        "tasks": submitted_tasks
    }

# This endpoint allows us to submit a batch of tasks that have a chance to fail, which is useful for testing the retry logic and error handling in our system. Each task will attempt to compute the square of a number, but there is a chance that it will raise an exception, simulating an unreliable task. 
@app.post("/submit_unreliable_batch")
def submit_unreliable_batch(request: BatchRequest):
    job_id = str(uuid4())
    submitted_tasks = []
    task_ids = []

    for number in request.numbers:
        result = unreliable_square.delay(number)
        task_ids.append(result.id)
        submitted_tasks.append({
            "input": number,
            "task_id": result.id
        })

    jobs[job_id] = {
        "task_ids": task_ids
    }

    return {
        "message": "Unreliable batch submitted",
        "job_id": job_id,
        "task_count": len(submitted_tasks),
        "tasks": submitted_tasks
    }

@app.get("/task_status/{task_id}")
def task_status(task_id: str):
    task_result = square_number.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None,
    }


@app.get("/job_status/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)

    if not job:
        return {"error": "Job not found"}

    task_ids = job["task_ids"]
    task_statuses = []

    completed = 0
    failed = 0
    pending = 0
    running = 0

    for task_id in task_ids:
        result = celery_app.AsyncResult(task_id)
        status = result.status

        task_info = {
            "task_id": task_id,
            "status": status
        }

        if status == "SUCCESS":
            task_result = result.result

            if isinstance(task_result, dict):
                task_info["result"] = task_result.get("result")
                task_info["retry_count"] = task_result.get("retry_count", 0)
            else:
                task_info["result"] = task_result
                task_info["retry_count"] = 0

            completed += 1

        elif status == "FAILURE":
            task_info["error"] = str(result.result)
            task_info["retry_count"] = 3
            failed += 1
        elif status == "STARTED":
            running += 1
        else:
            pending += 1

        task_statuses.append(task_info)

    total = len(task_ids)
    finished = completed + failed
    remaining = total - finished
    percent_complete = (finished / total) * 100 if total > 0 else 0

    overall_status = "IN_PROGRESS"

    if completed == total:
        overall_status = "SUCCESS"
    elif failed > 0 and finished == total:
        overall_status = "COMPLETED_WITH_FAILURES"
    elif failed > 0:
        overall_status = "PARTIALLY_FAILED"

    return {
        "job_id": job_id,
        "overall_status": overall_status,
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "running_tasks": running,
        "pending_tasks": pending,
        "remaining_tasks": remaining,
        "percent_complete": percent_complete,
        "tasks": task_statuses
    }


@app.get("/results/{job_id}")
def get_results(job_id: str):
    job = jobs.get(job_id)

    if not job:
        return {"error": "Job not found"}

    task_ids = job["task_ids"]
    results = []
    failures = []

    for task_id in task_ids:
        result = celery_app.AsyncResult(task_id)

        if result.status == "SUCCESS":
            task_result = result.result

            if isinstance(task_result, dict):
                results.append({
                    "task_id": task_id,
                    "input": task_result.get("input"),
                    "result": task_result.get("result"),
                    "retry_count": task_result.get("retry_count", 0)
                })
            else:
                results.append({
                    "task_id": task_id,
                    "result": task_result,
                    "retry_count": 0
                })

        elif result.status == "FAILURE":
            failures.append({
                "task_id": task_id,
                "error": str(result.result),
                "retry_count": 3
            })

    return {
        "job_id": job_id,
        "successful_results": results,
        "failures": failures,
        "success_count": len(results),
        "failure_count": len(failures)
    }
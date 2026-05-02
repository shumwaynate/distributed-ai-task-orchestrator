from app.worker.celery_app import celery_app
import time
import random

@celery_app.task
def square_number(x: int) -> int:
    return x * x

@celery_app.task
def slow_square_number(x: int, delay_seconds: int = 3) -> int:
    time.sleep(delay_seconds)
    return x * x

@celery_app.task(bind=True, max_retries=3)
def unreliable_square(self, x: int) -> dict:
    try:
        if random.random() < 0.3:
            raise Exception("Random failure occurred")

        return {
            "input": x,
            "result": x * x,
            "retry_count": self.request.retries
        }

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise Exception(
                f"Random failure occurred after {self.request.retries} retries"
            )

        raise self.retry(exc=exc, countdown=1)
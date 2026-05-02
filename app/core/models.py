from pydantic import BaseModel


class BatchSubmission(BaseModel):
    numbers: list[int]
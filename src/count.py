from pydantic import BaseModel


class Count(BaseModel):
    positive: int = 0
    negative: int = 0
    exceptions: int = 0
    resets: int = 0

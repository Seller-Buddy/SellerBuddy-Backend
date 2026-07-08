from typing import Any
from pydantic import BaseModel


class GeneratePostsRequest(BaseModel):
    products: list[dict[str, Any]]


class PublishThreadRequest(BaseModel):
    content: str


class PublishThreadResponse(BaseModel):
    message: str
    threads_post_id: str
    status: str

from typing import Any
from pydantic import BaseModel


class GeneratePostsRequest(BaseModel):
    products: list[dict[str, Any]]
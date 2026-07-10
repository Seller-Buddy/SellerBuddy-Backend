from typing import Any

from pydantic import BaseModel, Field


class GeneratePostsRequest(BaseModel):
    products: list[dict[str, Any]]


class PublishThreadRequest(BaseModel):
    content: str


class PublishThreadResponse(BaseModel):
    message: str
    threads_post_id: str
    status: str


class PolicyDocument(BaseModel):
    title: str
    content: str
    category: str | None = None
    source: str | None = None


class CsAnalyzeRequest(BaseModel):
    customer_message: str
    order_context: dict[str, Any] = Field(default_factory=dict)


class CsPolicyMatch(BaseModel):
    title: str
    excerpt: str
    score: float
    category: str | None = None
    source: str | None = None


class CsSafetyReview(BaseModel):
    requires_operator_approval: bool
    risk_level: str
    issues: list[str]
    approval_reason: str | None = None


class CsAnalyzeResponse(BaseModel):
    message: str
    inquiry_summary: str
    category: str
    category_label: str
    missing_info: list[str]
    matched_policies: list[CsPolicyMatch]
    decision: str
    decision_label: str
    decision_reason: str
    draft_reply: str
    safety_review: CsSafetyReview
    workflow: list[dict[str, Any]]


class CsPolicyIngestRequest(BaseModel):
    documents: list[PolicyDocument]
    reset_collection: bool = False


class CsPolicyIngestResponse(BaseModel):
    message: str
    collection_name: str
    stored_document_count: int
    stored_chunk_count: int


class CsPolicySearchRequest(BaseModel):
    query: str
    category: str | None = None
    order_context: dict[str, Any] = Field(default_factory=dict)
    top_k: int = 3


class CsPolicySearchResponse(BaseModel):
    message: str
    matches: list[CsPolicyMatch]

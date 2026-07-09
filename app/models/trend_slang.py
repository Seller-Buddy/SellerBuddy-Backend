from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrendSlangSource:
    source_type: str
    source_url: str
    source_title: str | None
    raw_content: str
    cleaned_content: str
    keywords: list[str]
    slang_expressions: list[str]
    hook_patterns: list[str]
    writing_patterns: list[str]
    cta_patterns: list[str]
    tone_features: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None

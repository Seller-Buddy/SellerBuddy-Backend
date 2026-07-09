import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from app.models.trend_slang import TrendSlangSource

logger = logging.getLogger(__name__)

MAX_CONTEXT_ITEMS = 20
MAX_CONTEXT_SUMMARIES = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrendSlangRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv("APP_DB_PATH", "shopbuddy.db")
        logger.info("trend_slang 저장소 초기화: db_path=%s", self.db_path)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_slang_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL UNIQUE,
                    source_title TEXT,
                    raw_content TEXT NOT NULL,
                    cleaned_content TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    slang_expressions TEXT NOT NULL,
                    hook_patterns TEXT NOT NULL,
                    writing_patterns TEXT NOT NULL,
                    cta_patterns TEXT NOT NULL,
                    tone_features TEXT NOT NULL,
                    avoid_expressions TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save_source(self, source: TrendSlangSource) -> None:
        now = _utcnow().isoformat()
        logger.info(
            "trend_slang 소스 저장 시작: source_type=%s url=%s 제목=%s",
            source.source_type,
            source.source_url,
            source.source_title,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trend_slang_sources (
                    source_type,
                    source_url,
                    source_title,
                    raw_content,
                    cleaned_content,
                    keywords,
                    slang_expressions,
                    hook_patterns,
                    writing_patterns,
                    cta_patterns,
                    tone_features,
                    avoid_expressions,
                    summary,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    source_type=excluded.source_type,
                    source_title=excluded.source_title,
                    raw_content=excluded.raw_content,
                    cleaned_content=excluded.cleaned_content,
                    keywords=excluded.keywords,
                    slang_expressions=excluded.slang_expressions,
                    hook_patterns=excluded.hook_patterns,
                    writing_patterns=excluded.writing_patterns,
                    cta_patterns=excluded.cta_patterns,
                    tone_features=excluded.tone_features,
                    avoid_expressions=excluded.avoid_expressions,
                    summary=excluded.summary,
                    updated_at=excluded.updated_at
                """,
                (
                    source.source_type,
                    source.source_url,
                    source.source_title,
                    source.raw_content,
                    source.cleaned_content,
                    json.dumps(source.keywords, ensure_ascii=False),
                    json.dumps(source.slang_expressions, ensure_ascii=False),
                    json.dumps(source.hook_patterns, ensure_ascii=False),
                    json.dumps(source.writing_patterns, ensure_ascii=False),
                    json.dumps(source.cta_patterns, ensure_ascii=False),
                    json.dumps(source.tone_features, ensure_ascii=False),
                    json.dumps(source.avoid_expressions, ensure_ascii=False),
                    source.summary,
                    now,
                    now,
                ),
            )

    def get_recent_trend_slang_sources(self, hours: int = 24) -> list[dict]:
        threshold = (_utcnow() - timedelta(hours=hours)).isoformat()
        logger.info("최근 trend_slang 소스 조회: 기준시간=%s시간 threshold=%s", hours, threshold)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM trend_slang_sources
                WHERE updated_at >= ?
                ORDER BY updated_at DESC
                """,
                (threshold,),
            ).fetchall()
        results = [self._row_to_dict(row) for row in rows]
        logger.info("최근 trend_slang 소스 조회 완료: 개수=%s", len(results))
        return results

    def get_recent_trend_context_for_writer(self, hours: int = 24) -> dict:
        rows = self.get_recent_trend_slang_sources(hours=hours)
        context = {
            "keywords": self._merge_unique(rows, "keywords"),
            "slang_expressions": self._merge_unique(rows, "slang_expressions"),
            "hook_patterns": self._merge_unique(rows, "hook_patterns"),
            "writing_patterns": self._merge_unique(rows, "writing_patterns"),
            "cta_patterns": self._merge_unique(rows, "cta_patterns"),
            "tone_features": self._merge_unique(rows, "tone_features"),
            "avoid_expressions": self._merge_unique(rows, "avoid_expressions"),
            "summaries": [row["summary"] for row in rows if row["summary"]][:MAX_CONTEXT_SUMMARIES],
        }
        logger.info(
            "writer용 트렌드 컨텍스트 생성: 소스수=%s 키워드=%s 유행어=%s 훅=%s 작성패턴=%s CTA=%s 톤=%s 금지표현=%s 요약=%s",
            len(rows),
            len(context["keywords"]),
            len(context["slang_expressions"]),
            len(context["hook_patterns"]),
            len(context["writing_patterns"]),
            len(context["cta_patterns"]),
            len(context["tone_features"]),
            len(context["avoid_expressions"]),
            len(context["summaries"]),
        )
        return context

    def _merge_unique(self, rows: list[dict], key: str) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for item in row.get(key, []):
                if item not in seen:
                    seen.add(item)
                    merged.append(item)
                if len(merged) >= MAX_CONTEXT_ITEMS:
                    return merged
        return merged

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "source_title": row["source_title"],
            "raw_content": row["raw_content"],
            "cleaned_content": row["cleaned_content"],
            "keywords": json.loads(row["keywords"]),
            "slang_expressions": json.loads(row["slang_expressions"]),
            "hook_patterns": json.loads(row["hook_patterns"]),
            "writing_patterns": json.loads(row["writing_patterns"]),
            "cta_patterns": json.loads(row["cta_patterns"]),
            "tone_features": json.loads(row["tone_features"]),
            "avoid_expressions": json.loads(row["avoid_expressions"]),
            "summary": row["summary"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

import unittest
from datetime import datetime, timedelta, timezone
from tempfile import NamedTemporaryFile

from app.agents.trend_slang.agent import CACHE_TTL_HOURS, build_deterministic_route_decision, route_next_step
from app.models.trend_slang import TrendSlangSource
from app.repositories.trend_slang_repository import TrendSlangRepository


class TrendLangGraphWorkflowTests(unittest.TestCase):
    def test_missing_slang_routes_to_slang_search(self):
        state = {
            "target_counts": {"slang": 5, "trend": 5},
            "success_counts": {"slang": 3, "trend": 5},
            "attempt_counts": {"slang": 0, "trend": 0},
            "candidate_urls": [],
            "searched_url_count": 0,
        }

        decision = build_deterministic_route_decision(state)
        state["last_route_decision"] = decision

        self.assertEqual("search_more", decision["next_action"])
        self.assertEqual("slang", decision["target_source_type"])
        self.assertEqual("search_more", route_next_step(state))

    def test_llm_finish_decision_is_respected(self):
        state = {
            "target_counts": {"slang": 5, "trend": 5},
            "success_counts": {"slang": 3, "trend": 5},
            "attempt_counts": {"slang": 0, "trend": 0},
            "candidate_urls": [],
            "searched_url_count": 0,
            "last_route_decision": {
                "next_action": "finish",
                "target_source_type": "none",
                "reason": "현재 결과로 종료",
                "query_hint": None,
            },
        }

        self.assertEqual("finish", route_next_step(state))

    def test_attempt_limit_stops_research(self):
        state = {
            "target_counts": {"slang": 5, "trend": 5},
            "success_counts": {"slang": 3, "trend": 5},
            "attempt_counts": {"slang": 3, "trend": 0},
            "candidate_urls": [],
            "searched_url_count": 0,
        }

        decision = build_deterministic_route_decision(state)
        state["last_route_decision"] = decision

        self.assertEqual("finish", decision["next_action"])
        self.assertEqual("finish", route_next_step(state))

    def test_cache_ttl_is_seven_days(self):
        self.assertEqual(24 * 7, CACHE_TTL_HOURS)

    def test_repository_deletes_sources_older_than_retention_days(self):
        temp_db = NamedTemporaryFile(suffix=".db")
        self.addCleanup(temp_db.close)
        repository = TrendSlangRepository(temp_db.name)
        old_source = build_source("slang", "https://example.com/old")
        recent_source = build_source("trend", "https://example.com/recent")
        repository.save_source(old_source)
        repository.save_source(recent_source)

        now = datetime.now(timezone.utc)
        set_source_updated_at(repository, old_source.source_url, now - timedelta(days=31))
        set_source_updated_at(repository, recent_source.source_url, now - timedelta(days=2))

        deleted_count = repository.delete_sources_older_than(days=30)
        remaining_sources = repository.get_recent_trend_slang_sources(hours=24 * 365)

        self.assertEqual(1, deleted_count)
        self.assertEqual([recent_source.source_url], [source["source_url"] for source in remaining_sources])


def build_source(source_type: str, url: str) -> TrendSlangSource:
    return TrendSlangSource(
        source_type=source_type,
        source_url=url,
        source_title="title",
        raw_content="raw",
        cleaned_content="cleaned",
        keywords=["키워드"],
        slang_expressions=["신조어"],
        hook_patterns=[],
        writing_patterns=[],
        cta_patterns=[],
        tone_features=[],
    )


def set_source_updated_at(repository: TrendSlangRepository, url: str, updated_at: datetime) -> None:
    with repository._connect() as connection:
        connection.execute(
            "UPDATE trend_slang_sources SET updated_at = ? WHERE source_url = ?",
            (updated_at.isoformat(), url),
        )


if __name__ == "__main__":
    unittest.main()

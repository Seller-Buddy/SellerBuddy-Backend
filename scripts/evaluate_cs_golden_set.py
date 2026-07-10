import argparse
import json
import logging
import os
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_POLICIES_PATH = ROOT_DIR / "tests" / "golden" / "cs_eval_policies.json"
DEFAULT_GOLDEN_SET_PATH = ROOT_DIR / "tests" / "golden" / "cs_golden_set.json"
DEFAULT_REPORT_DIR = ROOT_DIR / "reports"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value: str) -> str:
    return " ".join((value or "").split()).lower()


def build_checks(scenario: dict, actual: dict, workflow_agents: list[str], forbidden_phrases: list[str]) -> dict:
    expected = scenario["expected"]
    matched_titles = [item.get("title") for item in actual.get("matched_policies", [])]
    actual_workflow_agents = [item.get("agent") for item in actual.get("workflow", [])]
    draft_reply = normalize_text(actual.get("draft_reply", ""))

    expected_policy_title = expected.get("policy_title")
    if expected_policy_title is None:
        policy_search = len(matched_titles) == 0
    else:
        policy_search = expected_policy_title in matched_titles

    required_group_results = []
    for group in expected.get("reply_required_any_groups", []):
        normalized_group = [normalize_text(term) for term in group]
        required_group_results.append(any(term in draft_reply for term in normalized_group))

    forbidden_matches = [phrase for phrase in forbidden_phrases if normalize_text(phrase) in draft_reply]
    actual_missing = actual.get("missing_info", [])
    expected_missing = expected.get("missing_info", [])
    safety_review = actual.get("safety_review", {})

    return {
        "category": actual.get("category") == expected.get("category"),
        "missing_info": set(actual_missing) == set(expected_missing),
        "policy_search": policy_search,
        "decision": actual.get("decision") == expected.get("decision"),
        "operator_approval": safety_review.get("requires_operator_approval")
        == expected.get("requires_operator_approval"),
        "reply_required_facts": all(required_group_results),
        "reply_forbidden_phrases": not forbidden_matches,
        "workflow_shape": actual_workflow_agents == workflow_agents,
        "details": {
            "matched_policy_titles": matched_titles,
            "missing_required_reply_groups": [
                group
                for group, passed in zip(expected.get("reply_required_any_groups", []), required_group_results)
                if not passed
            ],
            "forbidden_reply_matches": forbidden_matches,
            "actual_workflow_agents": actual_workflow_agents,
        },
    }


def public_checks(checks: dict) -> dict:
    return {key: value for key, value in checks.items() if key != "details"}


def evaluate_scenario(client, scenario: dict, workflow_agents: list[str], forbidden_phrases: list[str]) -> dict:
    response = client.post(
        "/api/cs/analyze",
        json={
            "customer_message": scenario["customer_message"],
            "order_context": scenario.get("order_context", {}),
        },
    )

    if response.status_code != 200:
        return {
            "id": scenario["id"],
            "name": scenario["name"],
            "status_code": response.status_code,
            "passed": False,
            "checks": {},
            "error": response.text,
        }

    actual = response.json()
    checks = build_checks(scenario, actual, workflow_agents, forbidden_phrases)
    passed = all(public_checks(checks).values())
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "status_code": response.status_code,
        "passed": passed,
        "checks": public_checks(checks),
        "check_details": checks["details"],
        "expected": scenario["expected"],
        "actual": {
            "category": actual.get("category"),
            "missing_info": actual.get("missing_info"),
            "matched_policies": actual.get("matched_policies"),
            "decision": actual.get("decision"),
            "decision_reason": actual.get("decision_reason"),
            "draft_reply": actual.get("draft_reply"),
            "safety_review": actual.get("safety_review"),
            "workflow": actual.get("workflow"),
        },
    }


def summarize(results: list[dict]) -> dict:
    check_names = sorted({name for result in results for name in result.get("checks", {})})
    metrics = {}
    for check_name in check_names:
        values = [result["checks"][check_name] for result in results if check_name in result.get("checks", {})]
        passed = sum(1 for value in values if value)
        metrics[check_name] = {
            "passed": passed,
            "total": len(values),
            "rate": round(passed / len(values), 4) if values else 0.0,
        }

    passed_scenarios = sum(1 for result in results if result["passed"])
    return {
        "scenario_passed": passed_scenarios,
        "scenario_total": len(results),
        "scenario_pass_rate": round(passed_scenarios / len(results), 4) if results else 0.0,
        "api_errors": sum(1 for result in results if result.get("status_code") != 200),
        "metrics": metrics,
        "failed_check_counts": dict(
            Counter(
                check_name
                for result in results
                for check_name, passed in result.get("checks", {}).items()
                if not passed
            )
        ),
    }


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# CS 골든 셋 평가 보고서: {report['label']}",
        "",
        f"- 실행 시각(UTC): {report['generated_at']}",
        f"- 정책 버전: {report['policy_version']}",
        f"- 골든 셋 버전: {report['golden_set_version']}",
        f"- 전체 시나리오 통과: {summary['scenario_passed']}/{summary['scenario_total']}",
        f"- API 오류: {summary['api_errors']}",
        "",
        "## 단계별 결과",
        "",
        "| 평가 항목 | 통과 | 전체 | 통과율 |",
        "| --- | ---: | ---: | ---: |",
    ]

    for name, metric in summary["metrics"].items():
        lines.append(f"| {name} | {metric['passed']} | {metric['total']} | {metric['rate']:.0%} |")

    lines.extend(
        [
            "",
            "## 시나리오 결과",
            "",
            "| ID | 시나리오 | 결과 | 실패 항목 |",
            "| --- | --- | --- | --- |",
        ]
    )

    for result in report["results"]:
        failed = [name for name, passed in result.get("checks", {}).items() if not passed]
        lines.append(
            f"| {result['id']} | {result['name']} | {'PASS' if result['passed'] else 'FAIL'} | "
            f"{', '.join(failed) if failed else '-'} |"
        )

    lines.extend(["", "## 실패 상세", ""])
    failed_results = [result for result in report["results"] if not result["passed"]]
    if not failed_results:
        lines.append("모든 시나리오가 통과했습니다.")
    else:
        for result in failed_results:
            lines.extend(
                [
                    f"### {result['id']} {result['name']}",
                    "",
                    f"- 실패 항목: {', '.join(name for name, passed in result.get('checks', {}).items() if not passed)}",
                    f"- 실제 카테고리: {result.get('actual', {}).get('category')}",
                    f"- 실제 누락 정보: {result.get('actual', {}).get('missing_info')}",
                    f"- 실제 판단: {result.get('actual', {}).get('decision')}",
                    f"- 검색 정책: {result.get('check_details', {}).get('matched_policy_titles')}",
                    f"- 실제 답변: {result.get('actual', {}).get('draft_reply')}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CS 골든 셋을 실제 FastAPI 엔드포인트로 평가합니다.")
    parser.add_argument("--policies", type=Path, default=DEFAULT_POLICIES_PATH)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET_PATH)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--label", default="current")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policies = load_json(args.policies)
    golden_set = load_json(args.golden_set)

    chroma_path = ROOT_DIR / "tmp" / "cs_golden_chroma" / args.label
    chroma_path.mkdir(parents=True, exist_ok=True)
    os.environ["CHROMA_DB_PATH"] = str(chroma_path)
    os.environ["CHROMA_POLICY_COLLECTION"] = "shopbuddy_golden_policies"

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated",
    )

    from fastapi.testclient import TestClient
    from app.main import app

    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with TestClient(app) as client:
        ingest_response = client.post(
            "/api/cs/policies/ingest",
            json={"documents": policies["documents"], "reset_collection": True},
        )
        if ingest_response.status_code != 200:
            raise RuntimeError(f"정책 등록 실패: {ingest_response.status_code} {ingest_response.text}")

        results = [
            evaluate_scenario(
                client,
                scenario,
                golden_set["workflow_agents"],
                golden_set["forbidden_reply_phrases"],
            )
            for scenario in golden_set["scenarios"]
        ]

    report = {
        "label": args.label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": policies["version"],
        "golden_set_version": golden_set["version"],
        "policy_ingest": ingest_response.json(),
        "summary": summarize(results),
        "results": results,
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.report_dir / f"cs_golden_set_{args.label}.json"
    markdown_path = args.report_dir / f"cs_golden_set_{args.label}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print(f"CS 골든 셋 평가: {summary['scenario_passed']}/{summary['scenario_total']} 시나리오 통과")
    for name, metric in summary["metrics"].items():
        print(f"- {name}: {metric['passed']}/{metric['total']} ({metric['rate']:.0%})")
    print(f"JSON 보고서: {json_path}")
    print(f"Markdown 보고서: {markdown_path}")
    return 0 if summary["scenario_passed"] == summary["scenario_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

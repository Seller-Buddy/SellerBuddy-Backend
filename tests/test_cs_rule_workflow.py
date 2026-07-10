import unittest

from app.services.cs.decision_service import decide_cs_case
from app.services.cs.inquiry_classifier import classify_inquiry
from app.services.cs.missing_info_checker import check_missing_information
from app.services.cs.response_writer import write_customer_reply
from app.services.cs.safety_review import review_cs_response


EXCHANGE_POLICY = [
    {
        "title": "POL-EXCHANGE-001 | 일반 교환 정책",
        "excerpt": (
            "일반 교환은 상품 수령 후 7일 이내에 신청해야 합니다. "
            "상품이 미사용 상태이고 상품 택 또는 라벨이 제거되지 않은 경우에만 교환할 수 있습니다."
        ),
        "score": 0.9,
        "category": "exchange",
        "source": "test",
    }
]

CANCELLATION_POLICY = [
    {
        "title": "POL-CANCEL-001 | 주문 취소 정책",
        "excerpt": "주문 취소는 상품이 출고되기 전 또는 배송이 시작되기 전에 가능합니다.",
        "score": 0.9,
        "category": "cancellation",
        "source": "test",
    }
]


class CsRuleWorkflowTests(unittest.TestCase):
    def test_received_days_alias_is_not_missing(self):
        missing = check_missing_information(
            "exchange",
            "사이즈 교환을 원합니다.",
            {"received_days_ago": 3, "used": False, "tag_removed": False},
        )
        self.assertEqual([], missing)

    def test_exchange_within_seven_days_is_likely(self):
        decision = decide_cs_case(
            "exchange",
            "사이즈 교환을 원합니다.",
            {"received_days_ago": 3, "used": False, "tag_removed": False},
            [],
            EXCHANGE_POLICY,
        )
        self.assertEqual("likely_possible", decision["decision"])

    def test_exchange_after_seven_days_is_unlikely(self):
        decision = decide_cs_case(
            "exchange",
            "사이즈 교환을 원합니다.",
            {"received_days_ago": 10, "used": False, "tag_removed": False},
            [],
            EXCHANGE_POLICY,
        )
        self.assertEqual("unlikely", decision["decision"])

    def test_cancellation_before_shipping_is_likely(self):
        decision = decide_cs_case(
            "cancellation",
            "주문을 취소하고 싶습니다. 아직 출고 전입니다.",
            {"order_status": "출고 전"},
            [],
            CANCELLATION_POLICY,
        )
        self.assertEqual("likely_possible", decision["decision"])

    def test_cancellation_after_shipping_is_unlikely(self):
        decision = decide_cs_case(
            "cancellation",
            "이미 출고됐고 배송 중입니다.",
            {"order_status": "배송 중"},
            [],
            CANCELLATION_POLICY,
        )
        self.assertEqual("unlikely", decision["decision"])

    def test_compensation_complaint_takes_priority_over_shipping(self):
        classification = classify_inquiry(
            "배송이 지연돼서 화가 납니다. 어떤 보상을 해줄 건가요?",
            {},
        )
        self.assertEqual("complaint", classification["category"])

    def test_cancellation_takes_priority_over_shipping_status_words(self):
        classification = classify_inquiry(
            "상품이 이미 출고됐고 배송 중인데 주문을 취소하고 싶습니다.",
            {},
        )
        self.assertEqual("cancellation", classification["category"])

    def test_rule_based_reply_has_policy_facts_without_risky_phrases(self):
        decision = {
            "decision": "likely_possible",
            "decision_label": "가능성 높음",
            "decision_reason": "7일 이내, 미사용, 택 유지 조건을 충족할 가능성이 높습니다.",
        }
        reply = write_customer_reply("교환", "", {}, [], EXCHANGE_POLICY, decision)
        review = review_cs_response(reply, decision, [], EXCHANGE_POLICY)

        self.assertIn("7일", reply)
        self.assertIn("미사용", reply)
        self.assertIn("택", reply)
        self.assertFalse(review["requires_operator_approval"])


if __name__ == "__main__":
    unittest.main()

# ShopBuddyBack Frontend API Guide

## Base URL

Backend local URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

OpenAPI JSON:

```text
http://127.0.0.1:8000/openapi.json
```

Important:

- Use `127.0.0.1:8000` only when frontend and backend run on the same PC.
- If frontend runs on another PC, replace `127.0.0.1` with the backend PC's LAN IP or deployed backend URL.
- Current CORS allowed origins:
  - `http://localhost:3000`
  - `http://localhost:5173`

## 1. Ingest Policy Documents

Use this when an operator registers policy text into ChromaDB.

```http
POST http://127.0.0.1:8000/api/cs/policies/ingest
Content-Type: application/json
```

Request body:

```json
{
  "reset_collection": false,
  "documents": [
    {
      "title": "교환 정책",
      "category": "exchange",
      "source": "쇼핑몰 정책",
      "content": "상품 수령 후 7일 이내, 미사용, 택 제거 전 상품은 교환 가능합니다."
    }
  ]
}
```

Response example:

```json
{
  "message": "정책 문서 저장 성공",
  "collection_name": "shopbuddy_policies",
  "stored_document_count": 1,
  "stored_chunk_count": 1
}
```

## 2. Search Policies

Use this only when the frontend needs a policy-search test/debug screen.

```http
POST http://127.0.0.1:8000/api/cs/policies/search
Content-Type: application/json
```

Request body:

```json
{
  "query": "어제 받은 상품을 교환하고 싶어요. 미사용이고 택은 그대로입니다.",
  "category": "exchange",
  "order_context": {
    "received_at": "2026-07-09",
    "used": false,
    "tag_removed": false
  },
  "top_k": 3
}
```

Response example:

```json
{
  "message": "정책 검색 성공",
  "matches": [
    {
      "title": "교환 정책",
      "excerpt": "상품 수령 후 7일 이내, 미사용, 택 제거 전 상품은 교환 가능합니다.",
      "score": 0.82,
      "category": "exchange",
      "source": "쇼핑몰 정책"
    }
  ]
}
```

## 3. Analyze Customer Support Inquiry

This is the main API for the CS Agent workflow.

```http
POST http://127.0.0.1:8000/api/cs/analyze
Content-Type: application/json
```

Request body:

```json
{
  "customer_message": "어제 받은 셔츠를 다른 사이즈로 교환하고 싶어요. 미사용이고 택은 그대로입니다.",
  "order_context": {
    "received_at": "2026-07-09",
    "used": false,
    "tag_removed": false,
    "product_name": "셔츠",
    "order_id": "ORDER-1234"
  }
}
```

Response example:

```json
{
  "message": "CS 문의 분석 성공",
  "inquiry_summary": "고객이 수령한 셔츠의 사이즈 교환을 요청함",
  "category": "exchange",
  "category_label": "교환",
  "missing_info": [],
  "matched_policies": [
    {
      "title": "교환 정책",
      "excerpt": "상품 수령 후 7일 이내, 미사용, 택 제거 전 상품은 교환 가능합니다.",
      "score": 0.82,
      "category": "exchange",
      "source": "쇼핑몰 정책"
    }
  ],
  "decision": "likely_possible",
  "decision_label": "가능성 높음",
  "decision_reason": "정책 기준상 수령 후 7일 이내, 미사용, 택 유지 조건을 충족할 가능성이 높습니다.",
  "draft_reply": "고객님, 문의 감사합니다. 전달주신 내용 기준으로는 교환 가능성이 높습니다. 다만 최종 처리를 위해 주문 정보와 상품 상태를 확인 후 안내드리겠습니다.",
  "safety_review": {
    "requires_operator_approval": true,
    "risk_level": "low",
    "issues": [],
    "approval_reason": null
  },
  "workflow": [
    {
      "agent": "inquiry_classifier",
      "label": "문의 접수/분류 Agent",
      "status": "completed",
      "result": "교환"
    },
    {
      "agent": "missing_info_checker",
      "label": "정보 확인 Agent",
      "status": "completed",
      "result": []
    },
    {
      "agent": "policy_search",
      "label": "정책 검색 Agent",
      "status": "completed",
      "result": {
        "matched_count": 1
      }
    },
    {
      "agent": "decision",
      "label": "판단 Agent",
      "status": "completed",
      "result": "가능성 높음"
    },
    {
      "agent": "response_writer",
      "label": "답변 작성 Agent",
      "status": "completed",
      "result": "draft_reply_created"
    },
    {
      "agent": "safety_review",
      "label": "안전 검수 Agent",
      "status": "completed",
      "result": "low"
    },
    {
      "agent": "operator_approval",
      "label": "운영자 승인 Agent",
      "status": "completed",
      "result": {
        "requires_operator_approval": true,
        "approval_reason": null
      }
    }
  ]
}
```

## Frontend Fetch Example

```js
const response = await fetch("http://127.0.0.1:8000/api/cs/analyze", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    customer_message: "어제 받은 셔츠를 교환하고 싶어요. 미사용이고 택은 그대로입니다.",
    order_context: {
      received_at: "2026-07-09",
      used: false,
      tag_removed: false,
      product_name: "셔츠",
      order_id: "ORDER-1234"
    }
  })
});

const data = await response.json();
console.log(data);
```

## Recommended Frontend Flow

1. Policy management screen:
   - Call `POST /api/cs/policies/ingest`
   - Use this when an operator uploads or pastes policy text.

2. CS inquiry analysis screen:
   - Call `POST /api/cs/analyze`
   - Show `category_label`, `missing_info`, `matched_policies`, `decision_label`, `decision_reason`, `draft_reply`, and `safety_review`.

3. Policy search/debug screen, optional:
   - Call `POST /api/cs/policies/search`
   - Use this to verify whether ChromaDB returns the expected policy.

## Category Values

```text
refund
exchange
shipping
cancellation
product_question
defective_item
complaint
other
```

## Decision Values

```text
likely_possible
needs_confirmation
unlikely
```

## Safety Review

If `safety_review.requires_operator_approval` is `true`, the frontend should not send the draft response directly to the customer. Show it to an operator for review, edit, and approval.

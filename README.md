# SellerBuddy

SellerBuddy는 소규모 쇼핑몰 판매자의 마케팅과 고객 응대 업무를 돕는 AI 에이전트 서비스입니다. Upstage Solar Pro 3와 LangGraph를 활용해 Threads 홍보문과 쇼핑몰 정책 기반 CS 답변 초안을 생성하고, 운영자가 결과를 검토할 수 있도록 지원합니다.

## 주요 기능

- 상품 정보를 기반으로 Threads 홍보문 생성
- 최신 트렌드와 유행 표현을 반영한 콘텐츠 작성
- 생성한 Threads 콘텐츠 게시
- 고객 문의 분류 및 누락 정보 확인
- 쇼핑몰 정책 등록과 벡터 검색
- 정책에 근거한 CS 답변 초안 및 안전성 검토
- CSV를 활용한 상품 및 고객 문의 데이터 입력

> AI가 생성한 콘텐츠와 CS 답변은 운영자가 검토한 후 사용해야 합니다.

## 기술 스택

### Backend

- Python 3.12
- FastAPI
- LangGraph
- Upstage Solar Pro 3
- ChromaDB
- SQLite

### Frontend

- TypeScript
- Node.js 22
- Fastify

### Infrastructure

- Docker
- Docker Compose
- Caddy

## 실행 방법

### 1. 저장소 복제

```bash
git clone https://github.com/Seller-Buddy/SellerBuddy-Backend.git
cd SellerBuddy-Backend
```

### 2. 환경변수 설정

예제 파일을 복사해 `.env` 파일을 만듭니다.

```bash
cp .env.example .env
```

생성된 `.env`에 사용할 외부 서비스의 API 키를 입력합니다. 실제 API 키가 들어 있는 `.env` 파일은 Git에 커밋하지 마세요.

```dotenv
UPSTAGE_API_KEY=your_upstage_api_key
SERPER_API_KEY=your_serper_api_key
THREADS_ACCESS_TOKEN=your_threads_access_token
THREADS_USER_ID=your_threads_user_id
```

### 3. Docker Compose 실행

```bash
docker compose up --build
```

백그라운드에서 실행하려면 다음 명령을 사용합니다.

```bash
docker compose up --build -d
```

실행 후 아래 주소로 접속할 수 있습니다.

- 서비스: <http://localhost:3000>
- API 문서: <http://localhost:3000/docs>
- 상태 확인: <http://localhost:3000/health/live>

**이후, 루트 폴더에 있는 csv를 사용하여 진행 가능합니다.**

서비스를 종료하려면 다음 명령을 실행합니다.

```bash
docker compose down
```

## 환경변수

| 변수 | 필수 여부 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `UPSTAGE_API_KEY` | AI 기능 사용 시 필수 | 없음 | Solar 및 Embedding API 인증 키 |
| `UPSTAGE_EMBEDDING_QUERY_MODEL` | 정책 검색 시 필수 | `embedding-query` | 검색어 임베딩 모델 |
| `UPSTAGE_EMBEDDING_PASSAGE_MODEL` | 정책 검색 시 필수 | `embedding-passage` | 정책 문서 임베딩 모델 |
| `SERPER_API_KEY` | 트렌드 검색 시 필수 | 없음 | Serper 검색 API 인증 키 |
| `THREADS_ACCESS_TOKEN` | Threads 게시 시 필수 | 없음 | Threads API 액세스 토큰 |
| `THREADS_USER_ID` | Threads 게시 시 필수 | 없음 | Threads 사용자 ID |
| `CORS_ORIGINS` | 선택 | `http://localhost:3000,http://localhost:5173` | 허용할 프론트엔드 Origin 목록 |
| `FRONTEND_PORT` | 선택 | `3000` | 외부에 노출할 서비스 포트 |
| `LOG_LEVEL` | 선택 | `INFO` | 백엔드 로그 레벨 |
| `SHOPBUDDY_VERSION` | 선택 | `local` | Docker 이미지 태그 |

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `POST` | `/api/threads/generate` | Threads 홍보문 생성 |
| `POST` | `/api/threads/publish` | Threads 콘텐츠 게시 |
| `POST` | `/api/cs/analyze` | 고객 문의 분석 및 답변 초안 생성 |
| `POST` | `/api/cs/policies/ingest` | 쇼핑몰 정책 등록 |
| `POST` | `/api/cs/policies/search` | 관련 쇼핑몰 정책 검색 |
| `GET` | `/health/live` | 서버 생존 상태 확인 |
| `GET` | `/health/ready` | 데이터 저장소 준비 상태 확인 |

요청 및 응답의 상세 형식은 서버 실행 후 [Swagger UI](http://localhost:3000/docs)에서 확인할 수 있습니다.

## 프로젝트 구조

```text
SellerBuddy-Backend/
├── app/
│   ├── agents/          # LangGraph 기반 AI 에이전트
│   ├── core/            # LLM 호출, 로깅 등 공통 기능
│   ├── routers/         # FastAPI 엔드포인트
│   ├── services/        # 마케팅 및 CS 비즈니스 로직
│   └── main.py          # 백엔드 애플리케이션 진입점
├── frontend/            # 프론트엔드와 Node.js 서버
├── tests/               # 백엔드 단위 테스트
├── compose.yaml         # 전체 컨테이너 구성
├── Dockerfile           # 백엔드 이미지 정의
├── requirements.txt     # Python 의존성
└── .env.example         # 환경변수 예시
```

# ShopBuddyBack 도커화 및 실서비스 전환 보고서

## 1. 결론

ShopBuddyBack은 고객사 웹사이트에 프론트엔드와 백엔드를 함께 설치해 사용하는 판매 방식이므로 도커화 효과가 크다. 고객 서버마다 Python, ChromaDB, 실행 경로를 수동으로 맞추는 대신 동일한 이미지와 설정 파일로 설치·업데이트·복구할 수 있기 때문이다.

다만 현재 상태에서 컨테이너만 만들면 "실행 가능한 데모"에는 가깝지만 "고객에게 판매 가능한 설치형 제품"은 아니다. 우선순위는 다음과 같다.

1. 백엔드 이미지와 `docker compose`를 제공한다.
2. SQLite와 ChromaDB 데이터를 하나의 영속 볼륨에 보관한다.
3. CORS, 비밀값, 데이터 경로를 환경변수로 외부화한다.
4. 인증, 고객별 데이터 격리, 작업 큐, 관측성을 보강한다.
5. 이후 프론트엔드와 리버스 프록시까지 하나의 배포 묶음으로 판매한다.

## 2. 현재 프로젝트 파악

### 서비스 역할

FastAPI 기반 단일 백엔드이며 크게 두 업무를 자동화한다.

- 마케팅: 상품 정보를 정규화하고 최신 유행어·카피 패턴을 수집한 뒤 Threads 게시물을 생성하고 게시한다.
- 고객응대: 문의를 분류하고 누락 정보를 확인하며, 쇼핑몰 정책을 벡터 검색해 처리 판단·답변 초안·안전 검수·운영자 승인 필요 여부를 반환한다.

주요 API는 `POST /api/threads/generate`, `POST /api/threads/publish`, `POST /api/cs/policies/ingest`, `POST /api/cs/policies/search`, `POST /api/cs/analyze`이다. `/`는 현재 단순 상태 확인 용도로 쓰인다.

### 실행 및 의존성

- 애플리케이션: FastAPI + Uvicorn
- AI: Upstage의 Solar 및 Embedding API
- 워크플로: LangGraph
- 외부 연동: Serper 검색, 웹 크롤링, Threads Graph API
- 로컬 저장: 트렌드 데이터는 SQLite `shopbuddy.db`, CS 정책 벡터는 ChromaDB `chroma_db/`
- 설정: `.env`의 Upstage, Serper, Threads 인증 정보와 일부 선택 환경변수
- 테스트: 규칙 기반 CS 및 트렌드 워크플로 단위 테스트 13개가 있으며 현재 모두 통과한다.

### 운영 관점의 현재 제약

- CORS 허용 주소가 `localhost:3000`, `localhost:5173`으로 고정되어 고객 도메인 연결이 불가능하다.
- API 인증과 권한 구분이 없다. 공개 배포 시 누구나 정책 등록, AI 호출, Threads 게시를 시도할 수 있다.
- SQLite와 ChromaDB가 상대 경로에 있어 컨테이너 교체 시 볼륨을 잘못 구성하면 데이터가 사라진다.
- 게시물 생성 과정은 검색·크롤링·여러 LLM 호출을 동기식 요청 안에서 수행한다. 응답 지연, 프록시 타임아웃, 중복 실행 위험이 있다.
- 단일 전역 정책 컬렉션과 DB를 사용하므로 여러 사업자가 한 인스턴스를 공유하는 SaaS형 멀티테넌시는 지원하지 않는다.
- `/` 상태 확인은 프로세스 생존만 보여 주고 DB 쓰기 가능 여부나 외부 API 설정 상태는 확인하지 않는다.
- 의존성 버전 지정 방식이 혼재되어 재빌드 시 결과가 달라질 수 있고, 마이그레이션 체계가 없다.

## 3. 권장 도커 구성

### 1단계: 고객사별 단독 설치형

현재 코드에는 고객사마다 독립 스택을 하나씩 배포하는 방식이 가장 안전하다.

```text
인터넷
  -> HTTPS 리버스 프록시(Caddy 또는 Nginx)
      -> 프론트엔드 정적 컨테이너
      -> FastAPI 백엔드 컨테이너
          -> /data/shopbuddy.db
          -> /data/chroma_db
          -> Upstage / Serper / Threads API
```

백엔드는 하나의 이미지로 만들고 `/data`만 named volume 또는 고객 서버의 백업 대상 경로에 연결한다. 프론트엔드는 빌드 결과를 Nginx로 제공한다. 리버스 프록시가 TLS 인증서, 단일 도메인 라우팅, 요청 크기와 타임아웃을 담당하게 한다.

이 구조는 고객별 데이터와 API 키가 스택 단위로 분리되며, 현재 코드를 크게 바꾸지 않고도 배포할 수 있다. 반대로 한 백엔드를 여러 고객이 공유하는 형태는 tenant ID 전파, 인증, DB 스키마, Chroma 컬렉션 격리를 먼저 설계해야 한다.

### 백엔드 이미지 원칙

- Python 3.12 slim 계열처럼 라이브러리 호환성이 검증된 버전을 고정한다.
- 빌드 시 컴파일 도구를 남기지 않는 multi-stage build를 사용한다.
- root가 아닌 전용 사용자로 실행한다.
- 소스와 가상환경만 이미지에 포함하고 `.env`, 로컬 DB, 테스트 결과, IDE 파일은 제외한다.
- `uvicorn app.main:app --host 0.0.0.0 --port 8000`을 기본 명령으로 둔다.
- 처음에는 worker 1개로 운영한다. SQLite와 로컬 ChromaDB에 여러 worker가 동시에 접근하는 구성을 성능 검증 없이 적용하지 않는다.
- 이미지 태그는 `latest` 대신 `1.0.0`과 같은 릴리스 버전 및 커밋 SHA를 함께 발행한다.

권장 파일 구성은 다음과 같다.

```text
Dockerfile
.dockerignore
compose.yaml
compose.production.yaml
.env.example
scripts/backup.sh
scripts/restore.sh
```

`compose.yaml`의 핵심 설정 예시는 아래와 같다.

```yaml
services:
  api:
    image: registry.example.com/shopbuddy/backend:${SHOPBUDDY_VERSION}
    restart: unless-stopped
    env_file: .env
    environment:
      APP_DB_PATH: /data/shopbuddy.db
      CHROMA_DB_PATH: /data/chroma_db
      CORS_ORIGINS: ${CORS_ORIGINS}
    volumes:
      - shopbuddy_data:/data
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health/live"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  shopbuddy_data:
```

실제 이미지에 `curl`을 넣지 않으려면 Python 표준 라이브러리로 healthcheck를 수행할 수 있다. 비밀값은 compose 파일이나 이미지에 직접 쓰지 않고 고객 서버의 `.env`, Docker secret 또는 클라우드 secret manager로 주입한다.

### 환경변수 정리

필수 설정:

- `UPSTAGE_API_KEY`
- `UPSTAGE_EMBEDDING_QUERY_MODEL`
- `UPSTAGE_EMBEDDING_PASSAGE_MODEL`
- `SERPER_API_KEY`
- `THREADS_ACCESS_TOKEN`
- `THREADS_USER_ID`

운영 설정:

- `APP_DB_PATH=/data/shopbuddy.db`
- `CHROMA_DB_PATH=/data/chroma_db`
- `CHROMA_POLICY_COLLECTION=shopbuddy_policies`
- `CORS_ORIGINS=https://customer.example.com`
- `LOG_LEVEL=INFO`
- 향후 추가할 `API_AUTH_SECRET`, 외부 호출 timeout, retry 상한

애플리케이션 시작 시 필수 환경변수를 검증하고 누락된 항목을 명확히 출력해야 한다. 단, Threads를 쓰지 않는 고객처럼 기능별 선택 판매를 고려한다면 전체 시작을 막기보다 해당 기능의 준비 상태를 별도로 표시하는 편이 낫다.

## 4. 도커화가 만드는 사업·운영 이점

- 설치 표준화: 고객 환경 차이를 줄이고 `docker compose up -d` 중심의 설치 절차를 제공할 수 있다.
- 업데이트 상품화: 버전 태그를 바꾸고 재기동하는 방식으로 기능 개선과 보안 패치를 배포할 수 있다.
- 고객 격리: 고객사별 컨테이너, 볼륨, API 키를 분리해 장애와 정보 노출 범위를 제한한다.
- 복구 가능성: 이미지와 데이터 볼륨을 분리하면 애플리케이션 교체와 데이터 복원을 독립적으로 수행할 수 있다.
- 지원 비용 절감: 동일한 로그 형식, 상태 확인, 설정 구조를 사용해 원격 장애 대응 절차를 표준화할 수 있다.
- 배포 선택지 확대: 고객 온프레미스, 단일 VM, AWS/GCP/Naver Cloud 등 Docker 실행 환경에 같은 패키지를 공급할 수 있다.

도커는 데이터 백업, 보안, 무중단 배포를 자동으로 해결하지 않는다. 판매 포인트가 되려면 설치 문서, 진단 명령, 백업·복원, 버전 호환 정책까지 제품에 포함해야 한다.

## 5. 실서비스 전 필수 보강

### 보안과 고객 연결

1. 모든 업무 API에 인증을 적용한다. 최소한 고객사별 API key, 권장 방식은 사용자 로그인과 JWT/OIDC 기반 권한 관리다.
2. 정책 초기화, 정책 등록, Threads 게시는 관리자 권한으로 제한하고 감사 로그를 남긴다.
3. `CORS_ORIGINS`를 환경변수 목록으로 받고 와일드카드와 credential 조합을 금지한다.
4. 로그에 고객 문의 전문, 주문 개인정보, API 토큰, 외부 API 오류 응답이 노출되지 않도록 마스킹한다.
5. 리버스 프록시에서 HTTPS, rate limit, 요청 본문 제한을 적용한다.
6. 이미지 취약점 검사와 SBOM을 CI에 추가하고, 고객에게 지원되는 버전과 보안 업데이트 기간을 명시한다.

### 안정성과 처리 구조

- 게시물 생성과 트렌드 수집은 API 요청에서 분리해 Redis + Celery/RQ/Arq 등의 작업 큐로 실행하고, 작업 ID로 상태를 조회하게 한다.
- Threads 게시 요청에는 idempotency key를 도입해 재시도나 네트워크 단절로 같은 글이 중복 게시되는 것을 막는다.
- 외부 API마다 timeout, 제한된 재시도, 지수 backoff, 실패 원인 코드를 통일한다.
- 상품 여러 개 중 하나가 실패해도 전체가 사라지지 않도록 부분 성공 결과를 보관한다.
- `/health/live`와 `/health/ready`를 분리한다. readiness는 데이터 디렉터리 쓰기 가능 여부와 필수 설정을 확인하되, 외부 API 일시 장애 때문에 컨테이너가 무한 재시작되지는 않게 한다.
- 구조화 JSON 로그에 request ID, job ID, 고객 ID, 처리 시간, 외부 API 호출 결과를 기록한다. Prometheus/Sentry 또는 고객 환경에 맞는 동등 도구를 연결한다.

### 데이터 관리

- `/data` 볼륨을 매일 백업하고 복원 리허설을 정기 수행한다. 백업에는 SQLite와 ChromaDB를 일관된 시점으로 함께 포함해야 한다.
- DB 스키마 버전을 관리하고 컨테이너 시작 전 별도 migration 단계에서 갱신한다.
- 초기 소규모 단독 설치는 SQLite/로컬 ChromaDB로 충분하지만, 다중 인스턴스·고가용성·멀티테넌시가 필요해지면 PostgreSQL과 서버형 벡터 저장소로 이전한다.
- 고객 문의와 주문 정보의 저장 여부, 보존 기간, 삭제 기능을 명시한다. 현재 ChromaDB에는 정책만 저장하지만 로그와 향후 작업 큐가 개인정보를 남길 수 있다.

## 6. 판매 형태별 권장안

### 고객사 설치형: 현재 가장 적합

고객마다 `frontend + api + proxy + volume` 스택을 제공한다. 라이선스 파일 또는 라이선스 서버 검증, 설치 버전, 지원 만료일을 관리한다. 고객이 자체 Threads·Upstage·Serper 키를 넣는 BYOK 방식은 비용 정산과 키 격리가 단순하다.

납품물은 이미지 접근 권한, compose 템플릿, `.env.example`, 설치·업데이트·롤백 문서, 백업·복원 스크립트, 장애 진단 명령으로 구성한다. 소스 자체를 판매하는 계약이라면 빌드 가능한 소스와 이미지 모두에 동일한 버전을 표시한다.

### 중앙 SaaS형: 별도 개발 후 선택

운영사가 하나의 서비스를 여러 고객에게 제공하려면 인증, 과금, 사용량 제한, tenant별 관계형 데이터와 벡터 컬렉션 격리, 비밀값 암호화가 선행되어야 한다. 현재 전역 DB 경로와 컬렉션 구조로는 고객 데이터 혼합 위험이 있어 바로 전환하면 안 된다.

## 7. 단계별 실행안

### P0: 배포 재현성 확보

- `Dockerfile`, `.dockerignore`, compose, `.env.example` 추가
- CORS와 저장 경로 환경변수화
- `/data` 단일 볼륨 및 non-root 권한 검증
- liveness/readiness 추가
- 단위 테스트와 이미지 빌드를 CI에서 수행
- 깨끗한 VM에서 설치, 재기동, 이미지 교체 후 데이터 유지 확인

완료 기준은 새 서버에서 문서만 보고 실행할 수 있고, 컨테이너 삭제·재생성 후 정책과 트렌드 데이터가 유지되는 것이다.

### P1: 판매 가능한 최소 운영 수준

- 인증·권한·rate limit·감사 로그
- 백업/복원 및 버전 롤백 절차
- JSON 로그, 오류 추적, 기본 지표와 알림
- 비밀값 관리와 이미지 보안 검사
- 프론트엔드, HTTPS 프록시를 포함한 고객 도메인 연결
- 고객별 설정 검증과 진단 명령 제공

### P2: 사용량 증가 대응

- 장시간 작업을 큐와 worker로 분리
- 예약 마케팅, 작업 이력, 재시도 및 중복 게시 방지
- PostgreSQL/서버형 벡터 DB 전환 판단
- 멀티테넌시가 사업적으로 필요할 때만 tenant 모델과 과금 체계 도입

## 8. 최종 제안

지금은 Kubernetes나 복잡한 마이크로서비스보다 고객사별 Docker Compose 패키지가 비용 대비 효과가 높다. 백엔드를 하나의 컨테이너로 유지하고 데이터 볼륨, 프론트엔드, HTTPS 프록시를 명확히 분리하면 현재 구조를 보존하면서 설치성과 복구성을 얻을 수 있다.

첫 도커화 작업은 이미지 생성에 그치지 말고 CORS 환경변수화, `/data` 영속화, healthcheck, 비밀값 템플릿, 백업·복원까지 한 묶음으로 진행해야 한다. 이후 인증과 비동기 작업 처리를 추가하면 "개발자 PC에서 동작하는 자동화 백엔드"에서 "고객 서버에 반복 납품하고 운영할 수 있는 제품"으로 전환할 수 있다.

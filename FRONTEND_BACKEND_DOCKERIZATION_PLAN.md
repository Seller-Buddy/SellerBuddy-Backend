# SellerBuddy 프론트엔드·백엔드 MVP 통합 Docker Compose 계획

## 1. 목적

발표용 MVP를 3일 안에 완성하는 것이 이번 작업의 목표다. 개인 쇼핑몰 운영자가 SellerBuddy 소스를 받은 뒤 복잡한 개발 환경을 별도로 구성하지 않고 다음 명령으로 프론트엔드와 백엔드를 함께 실행할 수 있게 한다.

```sh
docker compose up --build
```

이번 작업은 별도 GitHub 저장소의 프론트엔드를 `Seller-Buddy/SellerBuddy-Backend`와 연결하고 하나의 Docker Compose 프로젝트로 실행하는 데 집중한다. 인증·HTTPS 자동화·배포 CI·완전한 백업 체계처럼 실제 판매 전에 필요한 기능은 MVP 발표 후 작업으로 분리한다.

### MVP 범위

- 포함: 프론트엔드 이미지, 백엔드 이미지, 통합 Compose, 프론트와 API 연결, 필수 환경변수, 핵심 기능 smoke test, 발표 실행 안내
- 제외: 로그인과 권한 관리, 자동 HTTPS, 이미지 레지스트리 배포, 무중단 업데이트, 작업 큐, 모니터링, 완전한 백업·복원 자동화
- 시간 제한: 3일
- 최우선 완료 조건: 새 환경에서 `docker compose up --build` 후 프론트 화면에서 핵심 CS 또는 마케팅 API 시연 성공

## 2. 현재 저장소 확인 결과

### 백엔드 기능과 기술 구성

- Python 3.12, FastAPI, Uvicorn 기반 API 서버이다.
- LangGraph와 Upstage 모델을 이용해 상품 기반 Threads 마케팅 글을 생성한다.
- Serper 검색·웹 수집 결과를 SQLite에 저장해 트렌드와 신조어를 콘텐츠 생성에 활용한다.
- Threads Graph API를 통해 생성한 글을 게시한다.
- 쇼핑몰 CS 정책을 ChromaDB에 저장·검색하고, 문의 분류·정보 확인·처리 판단·답변 초안·안전 검수를 수행한다.
- 주요 API는 `POST /api/threads/generate`, `POST /api/threads/publish`, `POST /api/cs/policies/ingest`, `POST /api/cs/policies/search`, `POST /api/cs/analyze`이다.
- 상태 확인 API는 `/health/live`, `/health/ready`로 분리되어 있다.

### 현재 Docker 구성

- `Dockerfile`은 Python 가상환경을 분리하는 multi-stage build와 non-root 실행을 적용했다.
- `compose.yaml`에는 현재 `api` 서비스 하나만 있으며 호스트의 기본 `8000` 포트로 노출한다.
- SQLite와 ChromaDB는 `shopbuddy_data` named volume의 `/data`에 함께 영속화한다.
- `.env`를 선택적으로 읽으며 API 키, 포트, 로그 레벨과 CORS 설정을 주입한다.
- API 컨테이너 healthcheck가 설정되어 있다.
- 현재 저장소에는 프론트엔드 소스, 프론트엔드 Dockerfile, 정적 서버 설정이 없다.

### 확인된 제약과 위험

- 현재 로컬 디렉터리명은 `ShopBuddyBack`이지만 실제 GitHub 저장소명은 `Seller-Buddy/SellerBuddy-Backend`이다. 문서와 사용자 노출 명칭은 실제 저장소명을 기준으로 한다.
- 현재 환경에는 GitHub CLI가 없고 공개 검색에서도 조직의 프론트엔드 저장소가 확인되지 않았다. 프론트 저장소가 비공개라면 구현 전에 저장소 접근 권한 또는 로컬 소스가 필요하다.
- 프론트엔드 기술 스택, 패키지 매니저, 빌드 명령, 출력 디렉터리, 현재 API base URL 환경변수 이름을 아직 확인할 수 없다.
- 기존 문서에는 운영용 `frontend + api + proxy` 구성이 언급되지만 관련 Compose 파일과 프록시·백업 스크립트는 현재 추적 파일에 없다.
- 백엔드 업무 API에는 인증이 없다. 발표용 로컬 실행에서는 허용하되 인터넷 공개 배포는 하지 않는다.
- 장시간 걸리는 검색·크롤링·LLM 호출이 동기 요청으로 실행되므로 프록시 timeout을 실제 처리 시간에 맞춰야 한다.

## 3. 목표 구조

개발 및 기본 고객 설치에서는 프론트 정적 서버가 단일 진입점이 되고 `/api` 요청을 Docker 내부 네트워크의 백엔드로 전달하도록 구성한다.

```text
사용자 브라우저
  -> http://고객서버:${FRONTEND_PORT}
      -> frontend (Nginx 또는 프론트 빌드에 적합한 정적 서버)
          -> 정적 프론트 파일
          -> /api/*  -> http://api:8000/api/*
          -> /health/* -> http://api:8000/health/* (운영 진단용 선택 경로)

api
  -> /data/shopbuddy.db
  -> /data/chroma_db
  -> Upstage / Serper / Threads 외부 API
```

이 구조의 원칙은 다음과 같다.

- 브라우저의 API base URL은 컨테이너 이름이 아니라 동일 origin의 상대 경로 `/api`를 사용한다. `api:8000`은 Docker 네트워크 안에서만 유효하므로 프론트 JavaScript에 포함하지 않는다.
- 기본 Compose에서는 `frontend`만 호스트에 공개하고 `api`는 `expose: 8000`으로 내부에만 연다. 개발·진단 시에만 별도 override를 사용해 API 포트를 공개한다.
- 동일 origin 프록시를 사용해 일반 실행 시 CORS 의존성을 없앤다. CORS 환경변수는 분리 개발이나 외부 API 연동을 위해 유지한다.
- `frontend`는 `api` healthcheck 통과 후 시작하도록 `depends_on.condition: service_healthy`를 적용한다.
- 고객 데이터와 비밀값은 이미지에 넣지 않고 named volume과 `.env`로 분리한다.

## 4. MVP 저장소 구조

### 권장안: 현재 저장소 아래에 프론트엔드 포함

3일 안에 통합 실행을 만들려면 현재 백엔드 저장소 아래에 프론트 소스를 포함하는 구조가 가장 단순하다.

```text
SellerBuddy-Backend/
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── 프론트엔드 소스
├── backend/ 또는 현재 app 중심 백엔드 파일
├── compose.yaml
├── .env.example
└── DEPLOYMENT.md
```

프론트 소스를 `frontend/`에 포함하고 백엔드 build context는 현재 루트로 유지한다. 발표 시에는 이 저장소 하나만 준비하면 되므로 설치 실수를 줄일 수 있다.

### MVP 이후 대안: Git submodule 또는 배포 전용 저장소

프론트와 백 저장소를 계속 분리해야 한다면 submodule이나 별도 배포 저장소를 검토한다. 하지만 인증과 버전 관리 작업이 추가되므로 이번 3일 MVP에는 적용하지 않는다.

### 버전 원칙

- 프론트와 백을 각각 임의의 최신 브랜치로 받지 않고 호환성이 검증된 태그 또는 커밋으로 묶는다.
- 전체 제품 버전 `SHOPBUDDY_VERSION`과 프론트·백 커밋을 릴리스 기록에 남긴다.
- 이미지 이름은 `shopbuddy-frontend:${SHOPBUDDY_VERSION}`과 `shopbuddy-backend:${SHOPBUDDY_VERSION}`으로 통일한다.

## 5. 단계별 구현 계획

### 1단계: 프론트엔드 저장소 분석 및 API 계약 확인

1. `Seller-Buddy` 조직의 프론트 저장소 접근 권한을 확보하고 소스를 로컬 `frontend/`에 준비한다.
2. `package.json`과 lockfile을 확인해 Node 버전, npm/yarn/pnpm 여부, 설치 명령과 production build 명령을 확정한다.
3. React/Vite, Next.js 등 프레임워크와 정적 export 가능 여부를 확인한다. 서버 사이드 렌더링이 필요하면 Nginx 정적 이미지 대신 Node runtime 컨테이너를 사용한다.
4. 현재 API base URL, 프록시 설정, 환경변수 접두사(`VITE_`, `NEXT_PUBLIC_` 등), 라우팅 fallback 요구사항을 조사한다.
5. 프론트가 실제로 사용하는 endpoint와 백엔드 OpenAPI를 대조해 경로, 요청·응답 스키마, timeout, 오류 처리 차이를 목록화한다.
6. 운영자 승인 전 CS 답변을 자동 발송하지 않는지와 정책 초기화·Threads 게시 같은 위험 기능의 UI 흐름을 확인한다.

완료 기준: 프론트의 깨끗한 로컬 빌드가 성공하고 모든 API 호출 지점과 production build 산출 위치가 확인되어야 한다.

### 2단계: 프론트엔드 Docker 이미지 작성

1. 프론트 프레임워크와 lockfile에 맞는 고정 Node 버전을 사용한다.
2. 의존성 설치와 production build를 builder stage에서 실행한다.
3. 정적 앱이면 build 결과만 Nginx 등의 경량 runtime stage로 복사한다. SSR 앱이면 production dependency만 포함한 non-root Node runtime stage를 구성한다.
4. SPA라면 새로고침 시 404가 나지 않도록 `try_files ... /index.html` fallback을 설정한다.
5. `/api/`를 `http://api:8000`으로 전달하고 `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, request ID 관련 헤더를 보존한다.
6. LLM 처리 endpoint에는 충분한 proxy read timeout을 적용하되 무제한 timeout은 피한다.
7. 정적 자산에는 해시 기반 장기 cache를, `index.html`에는 짧은 cache 또는 no-cache를 설정해 업데이트 후 구버전 자산 참조를 방지한다.
8. 프론트 healthcheck를 추가하고 root가 아닌 사용자로 실행 가능한지 검증한다.
9. 프론트 `.dockerignore`에 `node_modules`, build 결과, `.git`, 로컬 환경파일, 로그를 제외한다.

완료 기준: 로컬 Node 설치 없이 `docker build`만으로 프론트 이미지가 만들어지고, 컨테이너에서 화면과 SPA route가 정상 제공되어야 한다.

### 3단계: 프론트 API 연결 방식 정리

1. production에서 하드코딩된 `localhost:8000` 또는 `127.0.0.1:8000` 호출을 제거한다.
2. 기본 API base URL을 상대 경로 `/api`로 설정한다.
3. 개발 서버에서는 프론트 프레임워크의 proxy 설정으로 `/api`를 로컬 백엔드에 전달하거나 개발 전용 환경변수로 override한다.
4. build-time 환경변수가 필요한 프레임워크라면 Compose `build.args`를 사용하되 API 키나 토큰은 절대 프론트 빌드 인자에 넣지 않는다.
5. 고객마다 실행 시점에 API 주소를 바꿔야 한다면 `config.js` 같은 runtime 공개 설정 파일을 entrypoint에서 생성하는 방식을 검토한다. 동일 origin 기본 구성에서는 불필요한 복잡성을 추가하지 않는다.
6. 연결 오류, 4xx 입력 오류, 502 외부 API 오류, 긴 작업 timeout을 프론트에서 구분해 처리한다.

완료 기준: 브라우저 네트워크 요청이 동일 origin의 `/api/...`로 발생하고 실제 응답이 `api` 컨테이너에서 반환되어야 한다.

### 4단계: 통합 `compose.yaml` 구성

1. 기존 `api` 서비스에 `frontend` 서비스를 추가한다.
2. 서비스 이름, 이미지 이름, build context, restart 정책을 제품 명칭에 맞게 통일한다.
3. `frontend`는 `${FRONTEND_PORT:-3000}:80`만 공개하고 `api`는 Docker 내부 네트워크에만 노출한다.
4. `frontend`가 `api` healthcheck 성공 이후 시작되도록 의존 조건을 설정한다.
5. `shopbuddy_data:/data` 볼륨과 백엔드의 worker 1개 원칙을 유지한다.
6. 환경변수는 `.env`에서 읽되 비밀값에 Compose 기본값을 제공하지 않는다.
7. 개발용 API 직접 노출, 소스 bind mount, hot reload가 필요하면 기본 파일을 복잡하게 만들지 않고 `compose.dev.yaml`로 분리한다.
8. 실제 도메인과 HTTPS가 필요한 운영 환경은 `compose.production.yaml` 또는 고객 인프라의 기존 리버스 프록시 연결 방식으로 분리한다. Caddy를 포함할 경우 도메인·인증서 볼륨·80/443 포트를 명시한다.

예상 기본 서비스 골격은 다음과 같다. 실제 프론트 경로와 컨테이너 포트는 1단계 분석 후 확정한다.

```yaml
services:
  api:
    build:
      context: .
    image: shopbuddy-backend:${SHOPBUDDY_VERSION:-local}
    env_file:
      - path: .env
        required: false
    environment:
      APP_DB_PATH: /data/shopbuddy.db
      CHROMA_DB_PATH: /data/chroma_db
    expose:
      - "8000"
    volumes:
      - shopbuddy_data:/data

  frontend:
    build:
      context: ./frontend
    image: shopbuddy-frontend:${SHOPBUDDY_VERSION:-local}
    depends_on:
      api:
        condition: service_healthy
    ports:
      - "${FRONTEND_PORT:-3000}:80"

volumes:
  shopbuddy_data:
```

완료 기준: 새 환경에서 `.env` 작성 후 `docker compose up --build` 한 번으로 두 서비스가 기동되고 프론트 화면에서 백엔드 기능을 호출할 수 있어야 한다.

### 5단계: 환경변수와 비밀값 정리

`.env.example`을 다음 범주로 재정리한다.

- 제품 실행: `SHOPBUDDY_VERSION`, `FRONTEND_PORT`, 선택적인 개발용 `BACKEND_PORT`, `LOG_LEVEL`
- AI·검색: `UPSTAGE_API_KEY`, `UPSTAGE_EMBEDDING_QUERY_MODEL`, `UPSTAGE_EMBEDDING_PASSAGE_MODEL`, `SERPER_API_KEY`
- Threads: `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`
- 저장소: `APP_DB_PATH`, `CHROMA_DB_PATH`, `CHROMA_POLICY_COLLECTION`
- 웹 보안: 개발 분리 실행이나 외부 origin이 필요한 경우의 `CORS_ORIGINS`
- 향후 필수 보강: API 인증 secret, 외부 API timeout·retry 상한

추가 원칙은 다음과 같다.

- 실제 `.env`와 DB는 Git 및 Docker build context에서 제외한다.
- 브라우저에 포함되는 프론트 환경변수에는 공개 가능한 값만 넣는다.
- 시작 시 기능별 필수값 누락을 명확히 진단한다. 사용하지 않는 Threads 기능의 키 누락 때문에 전체 앱을 중단할지는 판매 옵션 정책에 맞춰 결정한다.
- 예제 파일에는 실제 키와 고객 도메인을 넣지 않는다.

### 6단계: 발표 환경 안전장치

이번 MVP에서는 다음 최소 안전장치만 적용한다.

1. 기본 구성에서 백엔드 포트를 외부에 직접 공개하지 않는다.
2. `.env`와 실제 API 키가 이미지나 Git에 포함되지 않는지 확인한다.
3. 발표는 로컬 또는 신뢰할 수 있는 내부망에서 진행하고 인터넷에 공개 배포하지 않는다.
4. 데모용 Threads 계정을 사용하며 실제 게시 직전에 운영자가 확인한다.
5. 인증, HTTPS, rate limit, 백업 자동화는 발표 후 판매 준비 단계로 넘긴다.

### 7단계: 문서와 고객 설치 경험 정리

1. 루트 `README.md` 또는 `DEPLOYMENT.md`에 필수 Docker/Compose 버전, 초기 설치, 접속 주소, 중지와 재시작 명령을 작성한다.
2. `.env.example` 복사 후 반드시 채워야 하는 값과 선택 기능별 값을 구분한다.
3. `docker compose ps`, `docker compose logs`, health endpoint를 이용한 진단 절차를 제공한다.
4. 업데이트 전 백업, 새 버전 pull/build, 재기동, 상태 확인, 롤백 순서를 제공한다.
5. 데이터 삭제를 동반하는 `down -v`의 위험을 명확히 표시한다.
6. 프론트·백 소스의 라이선스, 고객 수정 범위, 재배포 제한, 보안 업데이트 지원 기간은 기술 문서와 별도로 계약에 반영한다.

## 6. 검증 계획

### 자동 검증

- 기존 Python 단위 테스트를 실행한다.
- 백엔드 Docker 이미지를 깨끗한 cache 조건에서도 빌드한다.
- 프론트 lint, type check, 단위 테스트와 production build를 실행한다.
- `docker compose config`로 환경변수 치환과 Compose 문법을 검증한다.
- CI에서 프론트와 백 이미지를 모두 빌드하고 가능하면 취약점 검사와 SBOM 생성을 추가한다.

### 통합 smoke test

1. 기존 이미지·컨테이너가 없는 환경에서 `.env.example`로 시작한다.
2. `docker compose up --build -d` 후 두 서비스의 healthy 상태를 확인한다.
3. 프론트 첫 화면, 정적 자산, SPA 직접 경로 접속을 확인한다.
4. 프론트에서 CS 정책 등록·검색·문의 분석을 순서대로 확인한다.
5. 상품 기반 Threads 글 생성과, 별도 테스트 계정에서 게시 기능을 확인한다.
6. 브라우저 요청이 `/api`를 사용하며 CORS·mixed content 오류가 없는지 확인한다.
7. API 컨테이너 재시작 및 전체 `down`/`up` 후 SQLite와 ChromaDB 데이터가 유지되는지 확인한다.
8. API 키 누락, 외부 API 실패, 4xx 요청 오류, proxy timeout 상황에서 사용자에게 적절한 오류가 표시되는지 확인한다.

### 발표 환경 검증

- 실제 발표용 컴퓨터에서 Docker Compose build와 실행 시간을 확인한다.
- 발표 직전 사용할 네트워크에서 Upstage·Serper·Threads 외부 API 통신을 확인한다.
- 네트워크 또는 외부 API 장애에 대비해 미리 준비한 입력과 시연 순서를 문서화한다.
- Linux 서버, 멀티 아키텍처, 고객 도메인, HTTPS, 복원 테스트는 발표 후 검증한다.

## 7. 예상 변경 파일

프론트 분석 결과에 따라 이름은 달라질 수 있지만 다음 변경을 예상한다.

```text
.gitignore
.dockerignore
.env.example
compose.yaml
DEPLOYMENT.md 또는 README.md
frontend/
├── Dockerfile
├── .dockerignore
├── nginx.conf                   # 정적 프론트인 경우
└── 프론트 소스 및 API 설정 변경
```

백엔드 애플리케이션 코드는 통합에 필요한 최소 범위만 수정한다. 기존 healthcheck와 환경변수 구성을 활용하고 프론트 연결만을 위해 API 스키마를 임의로 바꾸지 않는다.

## 8. 3일 작업 일정

### 1일 차: 프론트 분석과 이미지 빌드

- 프론트 저장소 접근 및 소스를 `frontend/`에 준비
- 기술 스택, 패키지 매니저, build 명령, API 호출부 확인
- 프론트 Dockerfile 작성 및 단독 이미지 build 성공
- API base URL을 `/api`로 변경

### 2일 차: Compose 통합과 기능 연결

- `api + frontend` 통합 `compose.yaml` 작성
- 프론트 reverse proxy와 backend health dependency 설정
- 필수 `.env.example` 정리
- CS 정책 등록·검색·문의 분석 또는 마케팅 글 생성 흐름 연결
- 컨테이너 재시작 후 데이터 유지 확인

### 3일 차: 발표 시나리오 검증과 문서화

- 깨끗한 환경에서 `docker compose up --build` 재현
- 핵심 발표 시나리오 end-to-end 반복 검증
- API 키 누락과 외부 API 실패 시 오류 화면 확인
- 발표용 시작·종료·로그 확인 명령 문서화
- 시연 데이터와 예비 시나리오 준비

### 발표 후 판매 준비 작업

- API 인증과 관리자 권한
- HTTPS와 도메인 연결
- 백업·복원, 업데이트·롤백, 릴리스 CI
- rate limit, 로그 마스킹, 취약점 검사
- 장시간 작업용 queue/worker와 모니터링

## 9. 최종 완료 기준

다음 조건을 만족하면 3일 MVP 통합 작업이 완료된 것으로 본다.

- 고객이 제공된 소스와 `.env`만으로 `docker compose up --build`를 실행할 수 있다.
- 프론트와 백엔드가 같은 제품 버전으로 함께 빌드되고 시작된다.
- 사용자는 프론트 접속 주소 하나만 사용하며 주요 마케팅·CS 흐름이 정상 동작한다.
- 브라우저에는 Docker 내부 주소나 비밀값이 노출되지 않는다.
- 기본 구성에서 백엔드 API 포트가 인터넷에 직접 공개되지 않는다.
- 컨테이너를 삭제·재생성해도 SQLite와 ChromaDB 데이터가 유지된다.
- API와 프론트 healthcheck 및 기본 로그 확인이 가능하다.
- 발표용 컴퓨터의 깨끗한 Docker 환경에서 실행 절차가 재현된다.

## 10. 구현 시작 전 필요한 입력

실제 구현을 시작하려면 다음 정보가 필요하다.

1. 프론트엔드 GitHub 저장소의 정확한 이름과 읽기 권한 또는 로컬 소스 경로
2. 발표에서 반드시 보여 줄 핵심 사용자 흐름: CS 자동화, 마케팅 글 생성·게시 중 우선순위
3. 발표 컴퓨터에서 사용할 실제 또는 데모용 Upstage·Serper·Threads 환경변수

MVP 기본 결정은 `프론트 소스를 frontend/에 포함 + 동일 origin /api 프록시 + 기본 API 포트 비공개 + 로컬 발표 환경`이다.

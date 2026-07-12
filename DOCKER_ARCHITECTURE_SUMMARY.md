# SellerBuddy Docker 통합 구조 요약

## 1. 구성 목적

SellerBuddy는 프론트엔드와 AI 에이전트 백엔드를 하나의 저장소로 통합하고, 사용자가 별도의 Node.js·Python 개발 환경을 구성하지 않아도 Docker Compose로 전체 서비스를 실행할 수 있도록 구성했다.

```sh
cp .env.example .env
docker compose up --build
```

실행 후 사용자는 브라우저에서 `http://localhost:3000`에 접속해 UI를 이용한다.

## 2. 저장소 구조

```text
SellerBuddy/
├── frontend/       # React UI, CSV 입력, 프론트 WebSocket 서버
├── app/            # FastAPI 기반 AI 에이전트 백엔드
├── Dockerfile      # 백엔드 이미지 빌드
├── Caddyfile       # 요청 경로에 따른 프록시 설정
├── compose.yaml    # 전체 컨테이너 통합 실행
└── .env.example    # 실행에 필요한 환경변수 예시
```

프론트엔드와 백엔드 개발자는 같은 저장소에서 각각 `frontend/`와 `app/`을 수정한다. 이를 통해 API 변경과 UI 변경을 하나의 프로젝트에서 함께 검증할 수 있다.

## 3. Docker 아키텍처

현재 Docker Compose는 총 3개의 컨테이너를 실행한다.

```text
사용자 브라우저
       │
       │ http://localhost:3000
       ▼
┌───────────────────────────┐
│ proxy (Caddy)             │
│ 단일 접속 주소와 요청 분배 │
└─────────────┬─────────────┘
              │
       ┌──────┴──────────────┐
       │                     │
       ▼                     ▼
┌─────────────────┐   ┌──────────────────┐
│ frontend        │   │ api              │
│ React UI        │   │ FastAPI          │
│ WebSocket 서버  │   │ AI 에이전트      │
│ CSV 입력·결과 UI│   │ CS·마케팅 처리   │
└─────────────────┘   └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │ Docker Volume    │
                      │ SQLite·ChromaDB  │
                      └──────────────────┘
```

### 컨테이너 역할

- `proxy`: 외부에 `3000` 포트를 공개하고 요청을 적절한 서비스로 전달한다.
- `frontend`: React 화면과 에이전트 UI에 필요한 WebSocket 서버를 실행한다.
- `api`: FastAPI 기반 CS·마케팅 AI 에이전트와 외부 API 연동을 담당한다.

### 요청 흐름

- 화면과 정적 파일 요청 → `proxy` → `frontend`
- WebSocket 요청 `/ws` → `proxy` → `frontend`
- 백엔드 요청 `/api/*` → `proxy` → `api`
- 상태 확인 `/health/*` → `proxy` → `api`

브라우저는 Docker 내부 주소를 알 필요 없이 같은 주소의 `/api`만 호출한다.

## 4. 데이터와 환경변수

- SQLite와 ChromaDB 데이터는 `/data` Docker named volume에 저장한다.
- 컨테이너를 교체하거나 다시 빌드해도 데이터 볼륨은 유지된다.
- AI·검색·Threads API 키는 소스나 이미지에 넣지 않고 `.env`로 전달한다.
- 백엔드 포트는 호스트에 직접 공개하지 않고 Docker 내부 네트워크에서만 사용한다.

## 5. Docker 적용의 장점

### 사용자 측면

- 명령어 하나로 프론트엔드와 백엔드를 함께 실행할 수 있다.
- Python, Node.js와 개별 라이브러리를 직접 설치할 필요가 없다.
- 사용자는 `localhost:3000` 하나의 주소만 알면 된다.

### 개발 측면

- 팀원마다 동일한 버전과 실행 환경을 사용할 수 있다.
- 프론트엔드와 백엔드의 호환 상태를 한 번에 검증할 수 있다.
- 서비스별 컨테이너를 독립적으로 빌드하고 수정할 수 있다.
- healthcheck를 통해 서비스가 정상 준비된 후 다음 컨테이너를 시작한다.

### 배포·관리 측면

- 운영체제 차이로 발생하는 실행 오류를 줄일 수 있다.
- 애플리케이션과 데이터를 분리해 이미지 교체와 데이터 보존이 쉽다.
- 프록시가 단일 진입점을 제공하므로 API 주소와 CORS 관리가 단순해진다.
- 향후 도메인과 HTTPS 설정을 프록시 계층에 추가하기 쉽다.

## 6. 최종 사용 흐름

```text
저장소 다운로드
  → .env에 API 키 설정
  → docker compose up --build
  → localhost:3000 접속
  → CSV 파일 입력
  → 프론트에서 백엔드 AI 에이전트 호출
  → CS 분석 또는 마케팅 결과 확인
```

현재 구조의 핵심은 **프론트엔드와 백엔드를 하나의 실행 가능한 AI 에이전트 데모로 패키징하고, Docker Compose를 통해 실행 환경을 표준화한 것**이다.

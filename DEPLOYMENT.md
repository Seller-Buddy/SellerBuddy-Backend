# SellerBuddy Docker 실행 안내

## 통합 실행

```sh
cp .env.example .env
docker compose up --build -d
```

브라우저에서 `http://localhost:3000`으로 접속한다. 포트는 `.env`의
`FRONTEND_PORT`로 변경할 수 있다.

기본 구성은 다음 세 컨테이너를 실행한다.

- `proxy`: 브라우저의 단일 진입점
- `frontend`: SellerBuddy 에이전트 UI와 WebSocket 서버
- `api`: FastAPI 백엔드

브라우저의 `/api/*`와 `/health/*` 요청은 proxy가 API 컨테이너로 전달한다.
백엔드는 호스트에 직접 공개하지 않는다.

Useful checks:

```sh
docker compose ps
curl http://localhost:3000/health/live
curl http://localhost:3000/health/ready
docker compose logs -f
```

종료와 재시작:

```sh
docker compose down
docker compose up -d
```

소스 변경 후 이미지를 다시 만들려면 다음 명령을 사용한다.

```sh
docker compose up --build -d
```

`docker compose down -v`는 SQLite와 ChromaDB가 저장된 볼륨까지 삭제하므로
데이터를 제거하려는 경우가 아니면 사용하지 않는다.

## Data backup

The backend stores SQLite and ChromaDB data in the `shopbuddy_data` Docker volume.

Create a backup:

```sh
COMPOSE_PROJECT_NAME=shopbuddy ./scripts/backup.sh
```

Restore a backup:

```sh
COMPOSE_PROJECT_NAME=shopbuddy CONFIRM_RESTORE=yes ./scripts/restore.sh ./backups/shopbuddy-data-YYYYMMDDTHHMMSSZ.tar.gz
```

Restore replaces the full contents of the data volume. Stop the stack before restoring if the API container is running.

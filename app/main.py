import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import configure_logging
from app.routers.cs_router import router as cs_router
from app.routers.threads_router import router as threads_router

configure_logging()

app = FastAPI(title="ShopBuddyBack API")


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )
    return [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]


origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads_router, prefix="/api/threads", tags=["threads"])
app.include_router(cs_router, prefix="/api/cs", tags=["cs"])


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/health/live", include_in_schema=False)
def liveness_check():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def readiness_check():
    paths = [
        Path(os.getenv("APP_DB_PATH", "shopbuddy.db")),
        Path(os.getenv("CHROMA_DB_PATH", "chroma_db")),
    ]
    for path in paths:
        directory = path if path.suffix == "" else path.parent
        directory.mkdir(parents=True, exist_ok=True)
        if not os.access(directory, os.W_OK):
            return {"status": "not_ready", "reason": "data_directory_not_writable"}
    return {"status": "ready"}

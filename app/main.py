from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import configure_logging
from app.routers.cs_router import router as cs_router
from app.routers.threads_router import router as threads_router

configure_logging()

app = FastAPI(title="ShopBuddyBack API")

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

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

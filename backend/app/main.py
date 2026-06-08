from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.routers import (
    admin,
    auth,
    billing,
    images,
    license,
    naver_accounts,
    places,
    tasks,
)

settings = get_settings()

# Scaffold convenience: create tables on startup. Use Alembic in production.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SmartPlace Cloud — 통합 이미지 관리 자동화",
    version="1.0.0",
    description="다계정 네이버 스마트플레이스 이미지 일괄 배포 (Cloud + Redis Worker + S3).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(naver_accounts.router)
app.include_router(places.router)
app.include_router(images.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(license.router)
app.include_router(billing.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}

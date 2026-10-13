import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError
from config import settings
from database import Base, engine
from security import limiter
from routers import auth, donors, requests, admin

logging.basicConfig(level=logging.INFO)
app = FastAPI(
    title="BloodLink API",
    version="0.1.0",
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS.split(","),
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth, donors, requests, admin):
    app.include_router(r.router)
app.include_router(admin.public)

@app.on_event("startup")
def init_db():
    if settings.CREATE_TABLES:
        Base.metadata.create_all(engine)  # migrations are preferred outside local development

@app.exception_handler(SQLAlchemyError)
async def db_error(request: Request, exc: SQLAlchemyError):
    logging.exception("DB error")
    return JSONResponse(status_code=503, content={"success": False, "detail": "Service temporarily unavailable"})

@app.get("/api/locations/config")
def maps_config():
    # Maps JS keys are browser-visible by design: restrict this key by HTTP referrer in Google Cloud.
    return {"success": True, "data": {"google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
                                      "default_radius_km": settings.DEFAULT_RADIUS_KM}}

@app.get("/api/health")
def health():
    return {"status": "ok"}

from pathlib import Path
from fastapi.staticfiles import StaticFiles

_FRONT = Path(__file__).resolve().parent.parent / "frontend"
if _FRONT.exists():
    app.mount("/", StaticFiles(directory=_FRONT, html=True), name="site")  # must stay last

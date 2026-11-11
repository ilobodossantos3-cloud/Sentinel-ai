import logging

from fastapi import FastAPI

from app.core.database import Base, engine

from app.models.incident import Incident
from app.models.incident_analysis import IncidentAnalysis
from app.models.asset import Asset
from app.models.job import Job

from app.api.incidents import router as incidents_router
from app.api.incident_analysis import router as analysis_router
from app.api.assets import router as assets_router
from app.api.dashboard import router as dashboard_router

from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SentinelAI API",
    description="AI-powered cybersecurity detection and incident analysis platform",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)    



app.include_router(incidents_router)
app.include_router(analysis_router)
app.include_router(assets_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "name": "SentinelAI",
        "status": "online",
        "version": "0.1.0"
    }


@app.get("/health")
def health():
    db_status = "connected"

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception:
        db_status = "unavailable"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status
    }
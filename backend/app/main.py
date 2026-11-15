import logging

from fastapi import FastAPI

from app.core.database import Base, engine

from app.models.incident import Incident
from app.models.incident_analysis import IncidentAnalysis
from app.models.asset import Asset
from app.models.job import Job
from app.models.audit import AuditTarget, Audit, AuditFinding
from app.models.threat_intel import ThreatIntelEntry

from app.api.incidents import router as incidents_router
from app.api.incident_analysis import router as analysis_router
from app.api.assets import router as assets_router
from app.api.dashboard import router as dashboard_router
from app.api.ingest import router as ingest_router
from app.api.audits import router as audits_router
from app.api.vulnerabilities import router as vulnerabilities_router
from app.api.intel import router as intel_router, incident_intel_router

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

from app.services.scheduler_service import start_scheduler

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
app.include_router(ingest_router)
app.include_router(audits_router)
app.include_router(vulnerabilities_router)
app.include_router(intel_router)
app.include_router(incident_intel_router)


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


@app.on_event("startup")
def startup_scheduler():
    """Start the periodic security sweep thread (if enabled)."""
    if settings.AUDIT_SCHEDULE_ENABLED:
        start_scheduler()
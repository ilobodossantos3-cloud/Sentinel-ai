"""Shared fixtures for the SentinelAI test suite.

Uses the real app engine pointing at a disposable SQLite file
(DATABASE_URL set here, before any app import, so pydantic-settings
gives the env var precedence over .env).
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["OPENROUTER_API_KEY"] = "test-key"

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

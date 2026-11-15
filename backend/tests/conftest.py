"""Shared fixtures for the SentinelAI test suite.

Uses the real app engine pointing at a disposable SQLite file
(DATABASE_URL set here, before any app import, so pydantic-settings
gives the env var precedence over .env).
"""
import os  # noqa: E402

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["OPENROUTER_API_KEY"] = "test-key"
os.environ["AUDIT_SCHEDULE_ENABLED"] = "false"

import http.server  # noqa: E402
import socketserver  # noqa: E402
import threading  # noqa: E402

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


class _LocalHandler(http.server.BaseHTTPRequestHandler):
    """Static local HTTP server for offline audit tests."""

    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Server", "nginx/1.24.0")
            self.send_header("Content-Type", "text/plain")
            body = b"User-agent: *\nDisallow: /admin\n"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Server", "nginx/1.24.0")
        self.send_header("Content-Type", "text/html")
        body = b"<html>ok</html>"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    with socketserver.TCPServer(("127.0.0.1", 0), _LocalHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()

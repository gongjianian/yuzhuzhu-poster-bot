import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test-password"
os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ALLOWED_ORIGINS"] = "http://localhost:5173"

from fastapi.testclient import TestClient

from dashboard.app import create_app


def test_app_starts():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/docs")
    assert response.status_code == 200


def test_cors_headers():
    app = create_app()
    client = TestClient(app)
    response = client.options(
        "/api/docs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers

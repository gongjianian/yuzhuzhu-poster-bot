import pytest


@pytest.fixture(autouse=True)
def default_dashboard_auth_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ADMIN_USER", "admin")
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD", "test123")
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key-with-32-bytes-min")
    monkeypatch.setenv("DASHBOARD_ALLOWED_ORIGINS", "http://localhost:5173")

import os
import pytest

os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "password"

from dashboard.config import DashboardSettings


def test_settings_require_long_secret_key():
    with pytest.raises(ValueError, match="DASHBOARD_SECRET_KEY"):
        DashboardSettings(
            secret_key="short",
            admin_user="admin",
            admin_password="password",
        )


def test_settings_require_admin_user():
    with pytest.raises(ValueError, match="admin_user"):
        DashboardSettings(
            secret_key="test-secret-key-with-32-bytes-min",
            admin_user="",
            admin_password="password",
        )


def test_settings_require_admin_password():
    with pytest.raises(ValueError, match="admin_password"):
        DashboardSettings(
            secret_key="test-secret-key-with-32-bytes-min",
            admin_user="admin",
            admin_password="",
        )


def test_settings_accept_valid_dashboard_credentials():
    settings = DashboardSettings(
        secret_key="test-secret-key-with-32-bytes-min",
        admin_user="admin",
        admin_password="password",
    )

    assert settings.secret_key == "test-secret-key-with-32-bytes-min"
    assert settings.admin_user == "admin"
    assert settings.admin_password == "password"

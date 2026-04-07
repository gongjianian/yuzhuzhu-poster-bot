from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dashboard.services.health_service import check_feishu, check_gemini


@patch("feishu_reader.build_client")
def test_check_feishu_runs_authenticated_probe(mock_build_client):
    mock_client = MagicMock()
    mock_client.bitable.v1.app_table.list.return_value = SimpleNamespace(
        success=lambda: True
    )
    mock_build_client.return_value = mock_client

    result = check_feishu()

    assert result["status"] == "ok"
    mock_client.bitable.v1.app_table.list.assert_called_once()


@patch("dashboard.services.health_service.requests.get")
def test_check_gemini_treats_401_as_error(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=401)

    result = check_gemini()

    assert result["status"] == "error"
    assert result["detail"] == "HTTP 401"

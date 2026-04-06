import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from models import QCResult
from qc_checker import check_poster_quality


FAKE_B64 = base64.b64encode(b"fake").decode()


def _mock_qc_response(passed: bool, issues: list, confidence: float = 0.9):
    msg = MagicMock()
    msg.content = json.dumps({"passed": passed, "issues": issues, "confidence": confidence})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("qc_checker._build_client")
def test_qc_passes(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_qc_response(True, [])

    result = check_poster_quality(FAKE_B64, FAKE_B64)
    assert result.passed is True
    assert result.issues == []


@patch("qc_checker._build_client")
def test_qc_fails_with_issues(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_qc_response(
        False, ["product distorted", "logo missing"]
    )

    result = check_poster_quality(FAKE_B64, FAKE_B64)
    assert result.passed is False
    assert len(result.issues) == 2


@patch("qc_checker._build_client")
def test_qc_handles_invalid_json(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client

    msg = MagicMock()
    msg.content = "This is not valid JSON at all."
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    mock_client.chat.completions.create.return_value = resp

    result = check_poster_quality(FAKE_B64, FAKE_B64)
    # Defaults to passed=True to avoid blocking pipeline
    assert result.passed is True
    assert len(result.issues) > 0

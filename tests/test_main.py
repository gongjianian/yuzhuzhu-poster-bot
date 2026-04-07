from unittest.mock import Mock, patch

import main


def test_setup_logging_creates_logs_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    main.setup_logging()

    assert (tmp_path / "logs").exists()


def test_main_starts_uvicorn(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_PORT", "9001")

    with patch("dashboard.app.create_app", return_value="app") as mock_create_app, patch(
        "uvicorn.run"
    ) as mock_uvicorn_run:
        main.main()

    mock_create_app.assert_called_once()
    mock_uvicorn_run.assert_called_once_with("app", host="0.0.0.0", port=9001)

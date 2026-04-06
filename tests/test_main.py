from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

import main
from models import ProductRecord, QCResult


def test_setup_logging_creates_logs_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    main.setup_logging()

    assert (tmp_path / "logs").exists()


def test_acquire_and_release_lock(tmp_path) -> None:
    with patch.object(main, "LOCK_PATH", tmp_path / "poster_bot.lock"):
        lock_fd = main.acquire_lock()
        assert lock_fd is not None
        assert (tmp_path / "poster_bot.lock").exists()

        second_lock = main.acquire_lock()
        assert second_lock is None

        main.release_lock(lock_fd)
        assert not (tmp_path / "poster_bot.lock").exists()


@patch("main.requests.post")
def test_send_feishu_alert(mock_post: Mock, monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")
    response = Mock()
    response.raise_for_status = Mock()
    mock_post.return_value = response

    main.send_feishu_alert("pipeline failed")

    assert mock_post.call_args.args[0] == "https://example.com/webhook"
    assert mock_post.call_args.kwargs["json"]["content"]["text"] == "pipeline failed"


@pytest.mark.asyncio
@patch("main.send_feishu_alert")
@patch("main.update_record_status")
@patch("main.upload_image", return_value="cloud://file-id")
@patch("main.build_cloud_path", return_value="images/泡澡球/产品_20260406.jpg")
@patch("main.check_poster_quality", return_value=QCResult(passed=True))
@patch("main.generate_poster_image", return_value=b"poster-bytes")
@patch("main.generate_poster_content")
@patch("main.process_product_image", return_value="product-b64")
async def test_process_product_success(
    mock_process_product_image: Mock,
    mock_generate_poster_content: Mock,
    mock_generate_poster_image: Mock,
    mock_check_poster_quality: Mock,
    mock_build_cloud_path: Mock,
    mock_upload_image: Mock,
    mock_update_record_status: Mock,
    mock_send_feishu_alert: Mock,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASSETS_DIR", "./assets/products")
    mock_generate_poster_content.return_value = Mock(image_prompt="make poster")
    record = ProductRecord(
        record_id="rec_1",
        product_name="浴小主泡澡球",
        category="泡澡球",
        asset_filename="product.png",
    )

    result = await main.process_product(record)

    assert result == "cloud://file-id"
    mock_process_product_image.assert_called_once()
    mock_generate_poster_content.assert_called_once_with(record)
    mock_generate_poster_image.assert_called_once_with("make poster", "product-b64")
    mock_check_poster_quality.assert_called_once()
    mock_upload_image.assert_called_once_with(b"poster-bytes", "images/泡澡球/产品_20260406.jpg")
    mock_update_record_status.assert_called_once_with("rec_1", "DONE", file_id="cloud://file-id")
    mock_send_feishu_alert.assert_not_called()


@pytest.mark.asyncio
@patch("main.send_feishu_alert")
@patch("main.update_record_status")
@patch("main.check_poster_quality", return_value=QCResult(passed=False, issues=["Logo mismatch"]))
@patch("main.generate_poster_image", return_value=b"poster-bytes")
@patch("main.generate_poster_content")
@patch("main.process_product_image", return_value="product-b64")
async def test_process_product_qc_failed(
    mock_process_product_image: Mock,
    mock_generate_poster_content: Mock,
    mock_generate_poster_image: Mock,
    mock_check_poster_quality: Mock,
    mock_update_record_status: Mock,
    mock_send_feishu_alert: Mock,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ASSETS_DIR", "./assets/products")
    mock_generate_poster_content.return_value = Mock(image_prompt="make poster")
    record = ProductRecord(
        record_id="rec_2",
        product_name="浴小主泡澡球",
        category="泡澡球",
        asset_filename="product.png",
    )

    result = await main.process_product(record)

    assert result is None
    mock_update_record_status.assert_called_once_with(
        "rec_2",
        "FAILED_MANUAL",
        error_msg="Logo mismatch",
    )
    mock_send_feishu_alert.assert_called_once()


@pytest.mark.asyncio
async def test_run_pipeline_processes_records() -> None:
    records = [
        ProductRecord(record_id="rec_1", product_name="A"),
        ProductRecord(record_id="rec_2", product_name="B"),
    ]
    expected = ["file-1", "file-2"]

    with patch("main.fetch_pending_records", return_value=records), patch(
        "main.process_product",
        new=AsyncMock(side_effect=expected),
    ) as mock_process_product:
        result = await main.run_pipeline()

    assert result == expected
    assert mock_process_product.await_count == 2


def test_main_releases_lock() -> None:
    with patch("main.setup_logging"), patch(
        "main.acquire_lock",
        return_value=123,
    ), patch("main.run_pipeline", new=Mock(return_value="pipeline")), patch(
        "main.release_lock"
    ) as mock_release_lock, patch(
        "main.asyncio.run"
    ) as mock_asyncio_run:
        main.main()

    mock_asyncio_run.assert_called_once_with("pipeline")
    mock_release_lock.assert_called_once_with(123)

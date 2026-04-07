from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import feishu_reader


def _mock_response(*, items=None, has_more=False, page_token=None, ok=True):
    return SimpleNamespace(
        success=lambda: ok,
        code=0 if ok else 500,
        msg="ok" if ok else "error",
        data=SimpleNamespace(
            items=items or [],
            has_more=has_more,
            page_token=page_token,
        ),
    )


def test_extract_text_handles_nested_values() -> None:
    assert feishu_reader._extract_text(None) == ""
    assert feishu_reader._extract_text("plain") == "plain"
    assert feishu_reader._extract_text([{"text": "A"}, {"text": "B"}]) == "A B"
    assert feishu_reader._extract_text({"value": [{"text": "nested"}]}) == "nested"


@patch("feishu_reader.build_client")
def test_fetch_pending_records(mock_build_client: Mock) -> None:
    item_one = SimpleNamespace(
        record_id="rec_1",
        fields={
            feishu_reader.FIELD_PRODUCT_NAME: [{"text": "Product One"}],
            feishu_reader.FIELD_INGREDIENTS: "Mint",
            feishu_reader.FIELD_BENEFITS: "Calming",
            feishu_reader.FIELD_TOPICS: [{"text": "#bath"}],
            feishu_reader.FIELD_CATEGORY: "Bath Care",
            feishu_reader.FIELD_VISUAL_STYLE: "Minimal",
            feishu_reader.FIELD_BRAND_COLORS: "#ABCDEF",
            feishu_reader.FIELD_ASSET_FILENAME: "prod-1.png",
            feishu_reader.FIELD_STATUS: "PENDING",
            feishu_reader.FIELD_IDEMPOTENCY_KEY: "idem-1",
        },
    )
    item_two = SimpleNamespace(
        record_id="rec_2",
        fields={
            feishu_reader.FIELD_PRODUCT_NAME: "Product Two",
            feishu_reader.FIELD_STATUS: "FAILED_RETRYABLE",
        },
    )
    search = Mock(
        side_effect=[
            _mock_response(items=[item_one], has_more=True, page_token="next"),
            _mock_response(items=[item_two]),
        ]
    )
    mock_client = SimpleNamespace(
        bitable=SimpleNamespace(
            v1=SimpleNamespace(app_table_record=SimpleNamespace(search=search))
        )
    )
    mock_build_client.return_value = mock_client

    records = feishu_reader.fetch_pending_records()

    assert [record.record_id for record in records] == ["rec_1", "rec_2"]
    assert records[0].product_name == "Product One"
    assert records[1].category == feishu_reader.DEFAULT_CATEGORY
    assert search.call_count == 2


@patch("feishu_reader.build_client")
def test_fetch_pending_records_raises_on_error(mock_build_client: Mock) -> None:
    search = Mock(return_value=_mock_response(ok=False))
    mock_client = SimpleNamespace(
        bitable=SimpleNamespace(
            v1=SimpleNamespace(app_table_record=SimpleNamespace(search=search))
        )
    )
    mock_build_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        feishu_reader.fetch_pending_records()


@patch("feishu_reader.build_client")
def test_fetch_all_records_keeps_empty_status(mock_build_client: Mock) -> None:
    item = SimpleNamespace(
        record_id="rec_3",
        fields={
            feishu_reader.FIELD_PRODUCT_NAME: "Product Three",
        },
    )
    search = Mock(return_value=_mock_response(items=[item]))
    mock_client = SimpleNamespace(
        bitable=SimpleNamespace(
            v1=SimpleNamespace(app_table_record=SimpleNamespace(search=search))
        )
    )
    mock_build_client.return_value = mock_client

    records = feishu_reader.fetch_all_records()

    assert len(records) == 1
    assert records[0].status == ""
    request = search.call_args.args[0]
    assert getattr(request, "request_body", None) is None


@patch("feishu_reader.build_client")
def test_update_record_status(mock_build_client: Mock) -> None:
    update = Mock(return_value=_mock_response())
    mock_client = SimpleNamespace(
        bitable=SimpleNamespace(
            v1=SimpleNamespace(app_table_record=SimpleNamespace(update=update))
        )
    )
    mock_build_client.return_value = mock_client

    feishu_reader.update_record_status(
        record_id="rec_1",
        status="DONE",
        file_id="cloud://file-id",
        error_msg="",
    )

    request = update.call_args.args[0]
    assert request.record_id == "rec_1"
    assert request.request_body.fields[feishu_reader.FIELD_STATUS] == "DONE"
    assert (
        request.request_body.fields[feishu_reader.FIELD_CLOUD_FILE_ID]
        == "cloud://file-id"
    )
    assert feishu_reader.FIELD_LAST_GENERATED_AT in request.request_body.fields


@patch("feishu_reader.build_client")
def test_update_record_status_raises_on_error(mock_build_client: Mock) -> None:
    update = Mock(return_value=_mock_response(ok=False))
    mock_client = SimpleNamespace(
        bitable=SimpleNamespace(
            v1=SimpleNamespace(app_table_record=SimpleNamespace(update=update))
        )
    )
    mock_build_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        feishu_reader.update_record_status("rec_1", "FAILED_MANUAL", error_msg="bad")

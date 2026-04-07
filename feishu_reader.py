from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import lark_oapi as lark
from dotenv import load_dotenv
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    Condition,
    FilterInfo,
    SearchAppTableRecordRequest,
    SearchAppTableRecordRequestBody,
    UpdateAppTableRecordRequest,
)

from models import ProductRecord

load_dotenv()

FIELD_PRODUCT_NAME = "\u4ea7\u54c1\u540d\u79f0"
FIELD_INGREDIENTS = "\u6210\u5206"
FIELD_BENEFITS = "\u529f\u6548"
FIELD_TOPICS = "\u5c0f\u7ea2\u4e66\u8bdd\u9898"
FIELD_CATEGORY = "\u5206\u7c7b"
FIELD_VISUAL_STYLE = "\u6d77\u62a5\u98ce\u683c"
FIELD_BRAND_COLORS = "\u54c1\u724c\u8272"
FIELD_ASSET_FILENAME = "\u4ea7\u54c1\u7d20\u6750\u56fe\u7247\u6587\u4ef6\u540d"
FIELD_STATUS = "\u72b6\u6001"
FIELD_IDEMPOTENCY_KEY = "\u5e42\u7b49\u952e"
FIELD_CLOUD_FILE_ID = "\u4e91\u5b58\u50a8FileID"
FIELD_LAST_GENERATED_AT = "\u6700\u540e\u751f\u6210\u65f6\u95f4"
FIELD_ERROR_MESSAGE = "\u9519\u8bef\u4fe1\u606f"

DEFAULT_CATEGORY = "\u672a\u5206\u7c7b"
DEFAULT_VISUAL_STYLE = "\u6781\u7b80\u6241\u5e73"


def build_client() -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(os.getenv("FEISHU_APP_ID", ""))
        .app_secret(os.getenv("FEISHU_APP_SECRET", ""))
        .build()
    )


def _extract_text(field_value: Any) -> str:
    if field_value is None:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, (int, float, bool)):
        return str(field_value)
    if isinstance(field_value, dict):
        for key in ("text", "name", "value"):
            value = field_value.get(key)
            if value not in (None, ""):
                return _extract_text(value)
        return ""
    if isinstance(field_value, list):
        parts = []
        for item in field_value:
            text = _extract_text(item)
            if text:
                parts.append(text)
        return " ".join(parts)
    return str(field_value)


def _parse_product_record(item: Any, *, default_status: str) -> ProductRecord:
    fields = getattr(item, "fields", {}) or {}
    status = _extract_text(fields.get(FIELD_STATUS))
    return ProductRecord(
        record_id=getattr(item, "record_id", ""),
        product_name=_extract_text(fields.get(FIELD_PRODUCT_NAME)),
        ingredients=_extract_text(fields.get(FIELD_INGREDIENTS)),
        benefits=_extract_text(fields.get(FIELD_BENEFITS)),
        xiaohongshu_topics=_extract_text(fields.get(FIELD_TOPICS)),
        category=_extract_text(fields.get(FIELD_CATEGORY)) or DEFAULT_CATEGORY,
        visual_style=_extract_text(fields.get(FIELD_VISUAL_STYLE)) or DEFAULT_VISUAL_STYLE,
        brand_colors=_extract_text(fields.get(FIELD_BRAND_COLORS)) or "#FFFFFF",
        asset_filename=_extract_text(fields.get(FIELD_ASSET_FILENAME)),
        status=status or default_status,
        idempotency_key=_extract_text(fields.get(FIELD_IDEMPOTENCY_KEY)),
        cloud_file_id=_extract_text(fields.get(FIELD_CLOUD_FILE_ID)),
    )


def _build_search_request(
    *,
    app_token: str,
    table_id: str,
    page_token: str | None,
    statuses: list[str] | None,
):
    builder = (
        SearchAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .page_size(100)
    )
    if statuses:
        filter_info = (
            FilterInfo.builder()
            .conjunction("or")
            .conditions(
                [
                    Condition.builder()
                    .field_name(FIELD_STATUS)
                    .operator("is")
                    .value([status])
                    .build()
                    for status in statuses
                ]
            )
            .build()
        )
        request_body = (
            SearchAppTableRecordRequestBody.builder()
            .filter(filter_info)
            .build()
        )
        builder = builder.request_body(request_body)
    if page_token:
        builder = builder.page_token(page_token)
    return builder.build()


def _fetch_records(
    *,
    statuses: list[str] | None,
    default_status: str,
) -> list[ProductRecord]:
    client = build_client()
    app_token = os.getenv("FEISHU_APP_TOKEN", "")
    table_id = os.getenv("FEISHU_TABLE_ID", "")
    records: list[ProductRecord] = []
    page_token = None

    while True:
        request = _build_search_request(
            app_token=app_token,
            table_id=table_id,
            page_token=page_token,
            statuses=statuses,
        )
        response = client.bitable.v1.app_table_record.search(request)
        if hasattr(response, "success") and not response.success():
            code = getattr(response, "code", "unknown")
            msg = getattr(response, "msg", "unknown error")
            raise RuntimeError(f"Failed to fetch Feishu records: {code} {msg}")

        data = getattr(response, "data", None)
        items = getattr(data, "items", []) or []
        for item in items:
            records.append(_parse_product_record(item, default_status=default_status))

        has_more = bool(getattr(data, "has_more", False))
        page_token = getattr(data, "page_token", None)
        if not has_more:
            break

    return records


def fetch_pending_records() -> list[ProductRecord]:
    return _fetch_records(
        statuses=["PENDING", "FAILED_RETRYABLE"],
        default_status="PENDING",
    )


def fetch_all_records() -> list[ProductRecord]:
    return _fetch_records(
        statuses=None,
        default_status="",
    )


def update_record_status(
    record_id: str,
    status: str,
    file_id: str = "",
    error_msg: str = "",
) -> None:
    client = build_client()
    app_token = os.getenv("FEISHU_APP_TOKEN", "")
    table_id = os.getenv("FEISHU_TABLE_ID", "")

    fields: dict[str, Any] = {
        FIELD_STATUS: status,
        FIELD_LAST_GENERATED_AT: datetime.now().isoformat(timespec="seconds"),
    }
    if file_id:
        fields[FIELD_CLOUD_FILE_ID] = file_id
    if error_msg:
        fields[FIELD_ERROR_MESSAGE] = error_msg

    request = (
        UpdateAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .record_id(record_id)
        .request_body(AppTableRecord.builder().fields(fields).build())
        .build()
    )

    response = client.bitable.v1.app_table_record.update(request)
    if hasattr(response, "success") and not response.success():
        code = getattr(response, "code", "unknown")
        msg = getattr(response, "msg", "unknown error")
        raise RuntimeError(f"Failed to update Feishu record: {code} {msg}")

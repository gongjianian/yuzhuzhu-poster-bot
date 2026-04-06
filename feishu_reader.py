from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
import lark_oapi as lark
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


def fetch_pending_records() -> list[ProductRecord]:
    client = build_client()
    app_token = os.getenv("FEISHU_APP_TOKEN", "")
    table_id = os.getenv("FEISHU_TABLE_ID", "")
    statuses = ["PENDING", "FAILED_RETRYABLE"]
    records: list[ProductRecord] = []
    page_token = None

    while True:
        filter_info = (
            FilterInfo.builder()
            .conjunction("or")
            .conditions(
                [
                    Condition.builder()
                    .field_name("状态")
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
        builder = (
            SearchAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .page_size(100)
            .request_body(request_body)
        )
        if page_token:
            builder = builder.page_token(page_token)
        request = builder.build()

        response = client.bitable.v1.app_table_record.search(request)
        if hasattr(response, "success") and not response.success():
            code = getattr(response, "code", "unknown")
            msg = getattr(response, "msg", "unknown error")
            raise RuntimeError(f"Failed to fetch Feishu records: {code} {msg}")

        data = getattr(response, "data", None)
        items = getattr(data, "items", []) or []
        for item in items:
            fields = getattr(item, "fields", {}) or {}
            record_id = getattr(item, "record_id", "")
            record = ProductRecord(
                record_id=record_id,
                product_name=_extract_text(fields.get("产品名称")),
                ingredients=_extract_text(fields.get("成分")),
                benefits=_extract_text(fields.get("功效")),
                xiaohongshu_topics=_extract_text(fields.get("小红书话题")),
                category=_extract_text(fields.get("分类")) or "未分类",
                visual_style=_extract_text(fields.get("海报风格")) or "极简扁平",
                brand_colors=_extract_text(fields.get("品牌色")) or "#FFFFFF",
                asset_filename=_extract_text(fields.get("产品素材图文件名")),
                status=_extract_text(fields.get("状态")) or "PENDING",
                idempotency_key=_extract_text(fields.get("幂等键")),
            )
            records.append(record)

        has_more = bool(getattr(data, "has_more", False))
        page_token = getattr(data, "page_token", None)
        if not has_more:
            break

    return records


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
        "状态": status,
        "最后生成时间": datetime.now().isoformat(timespec="seconds"),
    }
    if file_id:
        fields["云存储fileID"] = file_id
    if error_msg:
        fields["错误信息"] = error_msg

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

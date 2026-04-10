"""
一键给飞书产品表添加「产品线」字段并自动分类。

分类规则：
  - 产品名含「元气灸」→ 百草元气灸
  - 产品名含「泡浴」   → 五行泡浴
  - 其他               → 未知产品线（手动确认）
"""
from __future__ import annotations

import os
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    AppTableField,
    AppTableFieldProperty,
    AppTableFieldPropertyOption,
    AppTableRecord,
    CreateAppTableFieldRequest,
    ListAppTableFieldRequest,
    UpdateAppTableRecordRequest,
)

APP_ID     = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
APP_TOKEN  = os.getenv("FEISHU_APP_TOKEN", "")
TABLE_ID   = os.getenv("FEISHU_TABLE_ID", "")

FIELD_NAME = "产品线"


def _classify(product_name: str) -> str:
    if "元气灸" in product_name:
        return "百草元气灸"
    if "泡浴" in product_name:
        return "五行泡浴"
    if "敷贴" in product_name or "贴" in product_name:
        return "靶向敷贴"
    if "精油" in product_name:
        return "精油系列"
    return "未知产品线"


def build_client() -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(APP_ID)
        .app_secret(APP_SECRET)
        .build()
    )


def field_exists(client: lark.Client) -> bool:
    """Check whether the 产品线 field already exists in the table."""
    request = (
        ListAppTableFieldRequest.builder()
        .app_token(APP_TOKEN)
        .table_id(TABLE_ID)
        .build()
    )
    resp = client.bitable.v1.app_table_field.list(request)
    if hasattr(resp, "success") and not resp.success():
        raise RuntimeError(f"ListFields error: {resp.code} {resp.msg}")
    data = getattr(resp, "data", None)
    items = getattr(data, "items", []) or []
    return any(getattr(f, "field_name", "") == FIELD_NAME for f in items)


def create_product_line_field(client: lark.Client) -> None:
    """Create a single-select 产品线 field with preset options."""
    options = [
        AppTableFieldPropertyOption.builder().name("五行泡浴").color(0).build(),
        AppTableFieldPropertyOption.builder().name("百草元气灸").color(1).build(),
        AppTableFieldPropertyOption.builder().name("靶向敷贴").color(2).build(),
        AppTableFieldPropertyOption.builder().name("精油系列").color(3).build(),
        AppTableFieldPropertyOption.builder().name("未知产品线").color(4).build(),
    ]
    field = (
        AppTableField.builder()
        .field_name(FIELD_NAME)
        .type(3)  # 3 = single select
        .property(
            AppTableFieldProperty.builder()
            .options(options)
            .build()
        )
        .build()
    )
    request = (
        CreateAppTableFieldRequest.builder()
        .app_token(APP_TOKEN)
        .table_id(TABLE_ID)
        .request_body(field)
        .build()
    )
    resp = client.bitable.v1.app_table_field.create(request)
    if hasattr(resp, "success") and not resp.success():
        raise RuntimeError(f"CreateField error: {resp.code} {resp.msg}")
    print(f"   ✅ 字段「{FIELD_NAME}」创建成功")


def fetch_all_products(client: lark.Client) -> list[dict]:
    """Fetch all records, return list of {record_id, product_name}."""
    from lark_oapi.api.bitable.v1 import (
        SearchAppTableRecordRequest,
        SearchAppTableRecordRequestBody,
    )
    records = []
    page_token = None

    while True:
        builder = (
            SearchAppTableRecordRequest.builder()
            .app_token(APP_TOKEN)
            .table_id(TABLE_ID)
            .page_size(100)
            .request_body(SearchAppTableRecordRequestBody.builder().build())
        )
        if page_token:
            builder = builder.page_token(page_token)

        resp = client.bitable.v1.app_table_record.search(builder.build())
        if hasattr(resp, "success") and not resp.success():
            raise RuntimeError(f"Feishu search error: {resp.code} {resp.msg}")

        data = getattr(resp, "data", None)
        items = getattr(data, "items", []) or []
        for item in items:
            fields = getattr(item, "fields", {}) or {}
            name_field = fields.get("产品名称", "")
            # Extract text from Feishu rich text field
            if isinstance(name_field, list):
                name = "".join(
                    seg.get("text", "") if isinstance(seg, dict) else str(seg)
                    for seg in name_field
                )
            elif isinstance(name_field, dict):
                name = name_field.get("text", str(name_field))
            else:
                name = str(name_field)

            records.append({
                "record_id": getattr(item, "record_id", ""),
                "product_name": name,
            })

        has_more = bool(getattr(data, "has_more", False))
        page_token = getattr(data, "page_token", None)
        if not has_more:
            break

    return records


def update_product_line(client: lark.Client, record_id: str, product_line: str) -> None:
    request = (
        UpdateAppTableRecordRequest.builder()
        .app_token(APP_TOKEN)
        .table_id(TABLE_ID)
        .record_id(record_id)
        .request_body(
            AppTableRecord.builder()
            .fields({FIELD_NAME: product_line})
            .build()
        )
        .build()
    )
    resp = client.bitable.v1.app_table_record.update(request)
    if hasattr(resp, "success") and not resp.success():
        raise RuntimeError(f"Update failed: {resp.code} {resp.msg}")


def main() -> None:
    client = build_client()

    print(f"🔍 检查飞书字段「{FIELD_NAME}」是否存在...")
    if field_exists(client):
        print(f"   字段已存在，跳过创建")
    else:
        print(f"   字段不存在，正在创建...")
        create_product_line_field(client)

    print("\n📦 读取飞书产品列表...")
    products = fetch_all_products(client)
    print(f"   共 {len(products)} 个产品\n")

    # Preview classification
    print("📋 分类预览：")
    unknown = []
    for p in products:
        line = _classify(p["product_name"])
        print(f"   {p['product_name']} → {line}")
        if line == "未知产品线":
            unknown.append(p["product_name"])

    if unknown:
        print(f"\n⚠️  {len(unknown)} 个产品无法自动分类：{unknown}")
        answer = input("继续写入飞书？(y/n): ").strip().lower()
        if answer != "y":
            print("已取消。")
            return
    else:
        print(f"\n✅ 所有产品均已自动分类")
        answer = input("确认写入飞书「产品线」字段？(y/n): ").strip().lower()
        if answer != "y":
            print("已取消。")
            return

    print("\n✏️  正在写入飞书...")
    ok = 0
    fail = 0
    for p in products:
        line = _classify(p["product_name"])
        try:
            update_product_line(client, p["record_id"], line)
            print(f"   ✓ {p['product_name']} → {line}")
            ok += 1
        except Exception as e:
            print(f"   ✗ {p['product_name']}: {e}")
            fail += 1

    print(f"\n🎉 完成！成功 {ok} 个，失败 {fail} 个")


if __name__ == "__main__":
    main()

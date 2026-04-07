"""
自动创建飞书多维表格 + 字段配置。

使用方法：
    1. 确保 .env 中填好 FEISHU_APP_ID 和 FEISHU_APP_SECRET
    2. python scripts/setup_feishu_table.py
    3. 执行完成后会打印 App Token 和 Table ID，手动填入 .env

前置条件：
    - 飞书应用需要有 bitable:app 权限并已发布版本
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

FEISHU_API = "https://open.feishu.cn/open-apis"
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

if not APP_ID or not APP_SECRET:
    print("ERROR: FEISHU_APP_ID and FEISHU_APP_SECRET must be set in .env")
    sys.exit(1)


def get_tenant_access_token() -> str:
    """Fetch tenant access token using app credentials."""
    resp = requests.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get token: {data}")
    return data["tenant_access_token"]


def create_bitable_app(token: str, name: str) -> str:
    """Create a new multi-dimensional spreadsheet and return its app_token."""
    resp = requests.post(
        f"{FEISHU_API}/bitable/v1/apps",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json={"name": name, "folder_token": ""},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to create bitable: {data}")
    app = data["data"]["app"]
    print(f"  [OK] Bitable app created: {app['name']}")
    print(f"       URL: {app.get('url', 'N/A')}")
    return app["app_token"]


def get_default_table_id(token: str, app_token: str) -> str:
    """Get the ID of the default table in a newly-created bitable."""
    resp = requests.get(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to list tables: {data}")
    tables = data["data"].get("items", [])
    if not tables:
        raise RuntimeError("No default table found in new bitable app")
    return tables[0]["table_id"]


def rename_table(token: str, app_token: str, table_id: str, new_name: str) -> None:
    """Rename the default table."""
    resp = requests.patch(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json={"name": new_name},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"  [WARN] Could not rename table (non-fatal): {data.get('msg')}")
    else:
        print(f"  [OK] Table renamed to: {new_name}")


def list_existing_fields(token: str, app_token: str, table_id: str) -> list[dict]:
    """List fields already present in the table (default table has one)."""
    resp = requests.get(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to list fields: {data}")
    return data["data"].get("items", [])


def create_field(token: str, app_token: str, table_id: str, field_spec: dict) -> None:
    """Create a single field in the table."""
    resp = requests.post(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json=field_spec,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"  [FAIL] {field_spec['field_name']}: {data.get('msg')}")
    else:
        print(f"  [OK] Field created: {field_spec['field_name']}")


def update_field(token: str, app_token: str, table_id: str, field_id: str, field_spec: dict) -> None:
    """Update an existing field (used for the default 'first' field)."""
    resp = requests.put(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json=field_spec,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"  [FAIL] Update {field_spec['field_name']}: {data.get('msg')}")
    else:
        print(f"  [OK] Field updated: {field_spec['field_name']}")


def delete_empty_records(token: str, app_token: str, table_id: str) -> None:
    """Delete the default empty placeholder rows that Feishu auto-creates."""
    resp = requests.get(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=100",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"  [WARN] Could not list records: {data.get('msg')}")
        return

    items = data["data"].get("items", [])
    empty_ids = [item["record_id"] for item in items if not item.get("fields")]

    if not empty_ids:
        print("  [OK] No empty records to clean up")
        return

    resp = requests.post(
        f"{FEISHU_API}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json={"records": empty_ids},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"  [FAIL] Could not delete empty records: {data.get('msg')}")
    else:
        print(f"  [OK] Deleted {len(empty_ids)} default empty rows")


# Field type constants (from Feishu bitable docs)
FIELD_TYPE_TEXT = 1
FIELD_TYPE_SINGLE_SELECT = 3
FIELD_TYPE_DATETIME = 5


# Field specifications following README.md schema
FIELD_SPECS = [
    {"field_name": "产品名称", "type": FIELD_TYPE_TEXT},
    {"field_name": "成分", "type": FIELD_TYPE_TEXT},
    {"field_name": "功效", "type": FIELD_TYPE_TEXT},
    {"field_name": "小红书话题", "type": FIELD_TYPE_TEXT},
    {
        "field_name": "分类",
        "type": FIELD_TYPE_SINGLE_SELECT,
        "property": {
            "options": [
                {"name": "沐浴"},
                {"name": "洗发"},
                {"name": "护肤"},
                {"name": "未分类"},
            ]
        },
    },
    {
        "field_name": "海报风格",
        "type": FIELD_TYPE_SINGLE_SELECT,
        "property": {
            "options": [
                {"name": "极简扁平"},
                {"name": "3D C4D"},
                {"name": "新中式插画"},
                {"name": "日系清新"},
            ]
        },
    },
    {"field_name": "品牌色", "type": FIELD_TYPE_TEXT},
    {"field_name": "产品素材图文件名", "type": FIELD_TYPE_TEXT},
    {
        "field_name": "状态",
        "type": FIELD_TYPE_SINGLE_SELECT,
        "property": {
            "options": [
                {"name": "PENDING"},
                {"name": "COPY_OK"},
                {"name": "IMAGE_OK"},
                {"name": "UPLOAD_OK"},
                {"name": "DONE"},
                {"name": "FAILED_RETRYABLE"},
                {"name": "FAILED_MANUAL"},
            ]
        },
    },
    {"field_name": "幂等键", "type": FIELD_TYPE_TEXT},
    {"field_name": "云存储fileID", "type": FIELD_TYPE_TEXT},
    {
        "field_name": "最后生成时间",
        "type": FIELD_TYPE_DATETIME,
        "property": {"date_formatter": "yyyy-MM-dd HH:mm", "auto_fill": False},
    },
    {"field_name": "错误信息", "type": FIELD_TYPE_TEXT},
]


def main() -> None:
    print("=" * 60)
    print("浴小主多维表格自动化创建脚本")
    print("=" * 60)

    print("\n[1/5] Getting tenant access token...")
    token = get_tenant_access_token()
    print(f"  [OK] Token obtained")

    print("\n[2/5] Creating bitable app '浴小主产品池'...")
    app_token = create_bitable_app(token, "浴小主产品池")

    print("\n[3/5] Getting default table ID...")
    table_id = get_default_table_id(token, app_token)
    print(f"  [OK] Default table_id: {table_id}")

    rename_table(token, app_token, table_id, "产品库")

    print("\n[4/5] Creating fields...")
    existing_fields = list_existing_fields(token, app_token, table_id)
    existing_names = {f["field_name"] for f in existing_fields}

    # The default table has one auto-created text field. Update it to '产品名称'.
    default_field = existing_fields[0] if existing_fields else None
    if default_field and default_field["field_name"] not in {spec["field_name"] for spec in FIELD_SPECS}:
        update_field(
            token, app_token, table_id, default_field["field_id"],
            {"field_name": "产品名称", "type": FIELD_TYPE_TEXT},
        )
        existing_names.add("产品名称")

    for spec in FIELD_SPECS:
        if spec["field_name"] in existing_names:
            continue
        create_field(token, app_token, table_id, spec)

    print("\n[5/5] Cleaning up default empty rows...")
    delete_empty_records(token, app_token, table_id)

    print("\n" + "=" * 60)
    print("[OK] SUCCESS! Bitable setup complete.")
    print("=" * 60)
    print(f"\nApp Token: {app_token}")
    print(f"Table ID:  {table_id}")
    print("\nNext steps:")
    print("  1. Add the following to your .env file:")
    print(f"     FEISHU_APP_TOKEN={app_token}")
    print(f"     FEISHU_TABLE_ID={table_id}")
    print("  2. Open the bitable in Feishu to verify all fields")
    print("  3. Add test product data to the table")
    print("=" * 60)


if __name__ == "__main__":
    main()

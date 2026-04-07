"""
解析产品介绍 doc/docx 文件，批量导入到飞书多维表格。

使用方法：
    python scripts/import_products.py

流程：
    1. 解析 18款元气灸介绍卡.docx（python-docx）
    2. 解析 26款泡浴介绍卡.doc（Word COM）
    3. 更新分类字段，添加「元气灸」「泡浴」选项
    4. 批量写入产品数据到飞书表格
    5. 状态字段留空（用户后续上传素材图后改为 PENDING 才会被 cron 处理）
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests
from docx import Document
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

FEISHU_API = "https://open.feishu.cn/open-apis"
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")
TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")

if not all([APP_ID, APP_SECRET, APP_TOKEN, TABLE_ID]):
    print("ERROR: FEISHU_APP_ID/SECRET/APP_TOKEN/TABLE_ID must all be set in .env")
    sys.exit(1)


def get_token() -> str:
    resp = requests.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


# ---------------- 18款元气灸 ---------------- #

def parse_yuanqijiu(path: str) -> list[dict]:
    """Parse the 18款元气灸 docx file into product dicts."""
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs]

    products = []
    current: dict | None = None
    section: str | None = None  # 'ingredients' | 'benefits'

    product_header_re = re.compile(r"^(\d+)号脐灸粉（针对(.+?)）$")

    for text in paragraphs:
        if not text:
            continue

        header_match = product_header_re.match(text)
        if header_match:
            if current:
                products.append(current)
            number = header_match.group(1)
            target = header_match.group(2)
            current = {
                "product_name": f"{number}号元气灸（{target}）",
                "raw_ingredients": "",
                "benefits_lines": [],
            }
            section = None
            continue

        if current is None:
            continue

        if text.startswith("成分："):
            current["raw_ingredients"] = text.replace("成分：", "").strip()
            section = None
            continue

        if text.startswith("成分解析"):
            section = "ingredients_detail"
            continue

        if text.startswith("适用人群"):
            section = "benefits"
            continue

        if section == "benefits":
            current["benefits_lines"].append(text)

    if current:
        products.append(current)

    return products


# ---------------- 26款泡浴 ---------------- #

def read_doc_via_word(path: str) -> list[str]:
    """Use Word COM to extract paragraphs from legacy .doc file."""
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(os.path.abspath(path))
        paragraphs = [p.Range.Text.strip() for p in doc.Paragraphs]
        doc.Close()
    finally:
        try:
            word.Quit()
        except Exception:
            pass
    return [p for p in paragraphs if p]


def parse_paoyu(path: str) -> list[dict]:
    """Parse 26款泡浴 .doc file. Structure is less uniform than the docx."""
    lines = read_doc_via_word(path)
    products: list[dict] = []
    current: dict | None = None
    section: str | None = None

    name_re = re.compile(r"^泡浴名称[：:]\s*(.+?)(?:成分[：:])?$")

    for raw in lines:
        text = raw.strip()
        if not text:
            continue

        m = name_re.match(text)
        if m:
            if current:
                products.append(current)
            name = m.group(1).strip()
            # Handle edge case: "泡浴名称：鸡内金成分：" — "成分：" already stripped
            current = {
                "product_name": f"{name}泡浴",
                "raw_ingredients": "",
                "ingredient_lines": [],
                "benefits_lines": [],
            }
            section = "ingredients"
            continue

        if current is None:
            continue

        if text.startswith("成分："):
            # Some entries have standalone "成分：" after the name line
            section = "ingredients"
            # May contain inline list
            after = text.replace("成分：", "").strip()
            if after:
                current["ingredient_lines"].append(after)
            continue

        if text.startswith("适用人群"):
            section = "benefits"
            continue

        if section == "ingredients":
            current["ingredient_lines"].append(text)
        elif section == "benefits":
            current["benefits_lines"].append(text)

    if current:
        products.append(current)

    # Derive raw_ingredients summary from ingredient_lines
    for p in products:
        names = []
        for line in p.get("ingredient_lines", []):
            # Format: "1.药名：说明..." or "药名：说明..."
            clean = re.sub(r"^\d+[\.\s、]\s*", "", line)
            name_match = re.match(r"^(.+?)[：:]", clean)
            if name_match:
                names.append(name_match.group(1).strip())
        p["raw_ingredients"] = "、".join(dict.fromkeys(names))  # dedupe preserve order
        p.pop("ingredient_lines", None)

    return products


# ---------------- 分类字段扩展 ---------------- #

def ensure_category_options(token: str) -> None:
    """Add 元气灸 and 泡浴 to the category field options."""
    resp = requests.get(
        f"{FEISHU_API}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    fields = resp.json()["data"]["items"]
    category_field = next((f for f in fields if f["field_name"] == "分类"), None)
    if not category_field:
        print("[WARN] '分类' field not found")
        return

    existing = {opt["name"] for opt in category_field.get("property", {}).get("options", [])}
    new_options = list(category_field.get("property", {}).get("options", []))

    for cat in ["元气灸", "泡浴"]:
        if cat not in existing:
            new_options.append({"name": cat})

    resp = requests.put(
        f"{FEISHU_API}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields/{category_field['field_id']}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        json={
            "field_name": "分类",
            "type": 3,
            "property": {"options": new_options},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"[WARN] Failed to update category options: {data}")
    else:
        print("[OK] Category field options updated (元气灸, 泡浴 added)")


# ---------------- 批量写入 ---------------- #

def batch_insert_records(token: str, records: list[dict]) -> None:
    """Batch create records via bitable API (100 per call max)."""
    batch_size = 100
    total = len(records)
    for start in range(0, total, batch_size):
        chunk = records[start : start + batch_size]
        resp = requests.post(
            f"{FEISHU_API}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/batch_create",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
            json={"records": [{"fields": r} for r in chunk]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            print(f"[FAIL] Batch {start}: {data}")
        else:
            print(f"[OK] Inserted {len(chunk)} records (batch {start // batch_size + 1})")


def build_record(product: dict, category: str) -> dict:
    """Convert parsed product into a bitable record."""
    benefits_text = "\n".join(product.get("benefits_lines", [])).strip()
    return {
        "产品名称": product["product_name"],
        "成分": product["raw_ingredients"],
        "功效": benefits_text,
        "小红书话题": "",
        "分类": category,
        "海报风格": "极简扁平",
        "品牌色": "#7FA650",
        "产品素材图文件名": "",
        # 状态留空，避免立刻被 cron 拾取
        "幂等键": "",
    }


def main() -> None:
    print("=" * 60)
    print("浴小主产品数据导入")
    print("=" * 60)

    print("\n[1/5] Getting tenant access token...")
    token = get_token()
    print("  [OK]")

    print("\n[2/5] Parsing 18款元气灸介绍卡.docx...")
    yuanqijiu = parse_yuanqijiu("18款元气灸介绍卡.docx")
    print(f"  [OK] Found {len(yuanqijiu)} products")

    print("\n[3/5] Parsing 26款泡浴介绍卡.doc...")
    paoyu = parse_paoyu("26款泡浴介绍卡.doc")
    print(f"  [OK] Found {len(paoyu)} products")

    print("\n[4/5] Updating category field options...")
    ensure_category_options(token)

    print("\n[5/5] Inserting records into bitable...")
    records = []
    for p in yuanqijiu:
        records.append(build_record(p, "元气灸"))
    for p in paoyu:
        records.append(build_record(p, "泡浴"))

    print(f"  Total records to insert: {len(records)}")
    batch_insert_records(token, records)

    print("\n" + "=" * 60)
    print("[OK] Import complete!")
    print("=" * 60)
    print(f"  元气灸: {len(yuanqijiu)} products")
    print(f"  泡浴:    {len(paoyu)} products")
    print(f"  总计:    {len(records)} records")
    print("\nNote: '状态' field is left empty on purpose.")
    print("      Fill in '产品素材图文件名' + set 状态=PENDING when ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()

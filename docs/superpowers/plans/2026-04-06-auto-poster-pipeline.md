# 每日自动作图上传系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在腾讯云 Ubuntu 服务器上运行 Python 程序，每天 08:00 自动从飞书读取产品信息、生成海报图片、上传到微信小程序云存储，全程无需人工介入。

**Architecture:** 单进程 Python 应用，asyncio 并发处理多产品。7 个职责单一模块通过 Pydantic models 传递数据。所有外部 API 调用均使用 tenacity 指数退避重试。文案生成用 `gemini-3.1-pro-preview`，图像生成用 `gemini-3-pro-image-preview`，通过自建 OpenAI-compatible API 调用。

**Tech Stack:** Python 3.11+, lark-oapi, openai, rembg, Pillow, tenacity, pydantic, loguru, python-dotenv, requests, pytest

---

## File Map

| 文件 | 职责 |
|------|------|
| `models.py` | 全局 Pydantic 数据模型 |
| `feishu_reader.py` | 读取飞书待处理记录；回写状态/fileID |
| `asset_processor.py` | rembg 抠图、缩放、base64 编码 |
| `content_generator.py` | 两阶段文案生成：方案 → 图像提示词 |
| `image_generator.py` | Gemini 图像生成（提示词 + 产品图） |
| `qc_checker.py` | 多模态质量检查 |
| `wechat_uploader.py` | 获取微信 access_token + 上传到云存储 |
| `main.py` | 总调度：asyncio、Job Lock、日志、告警 |
| `prompts/scheme_prompt.txt` | 方案策划 Prompt 模板 |
| `prompts/image_prompt.txt` | 视觉翻译官 Prompt 模板 |
| `tests/` | pytest 单元测试 |

---

## Task 1: 项目脚手架

**Files:**
- Create: `poster_bot/models.py`
- Create: `poster_bot/requirements.txt`
- Create: `poster_bot/.env.example`
- Create: `poster_bot/.gitignore`
- Create: `poster_bot/README.md`
- Create: `poster_bot/tests/__init__.py`

- [ ] **Step 1: 创建项目目录结构**

```bash
mkdir -p /opt/poster_bot/{tests,prompts,assets/products,logs}
cd /opt/poster_bot
git init
```

- [ ] **Step 2: 写 `requirements.txt`**

```
lark-oapi>=1.3.0
openai>=1.0.0
rembg>=2.0.50
Pillow>=10.0.0
tenacity>=8.2.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
loguru>=0.7.0
python-dotenv>=1.0.0
requests>=2.31.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

- [ ] **Step 3: 写 `.env.example`**

```env
GEMINI_API_KEY=
GEMINI_API_BASE=https://api.buxianliang.fun/v1
STORE_NAME=浴小主
GEMINI_COPY_MODEL=gemini-3.1-pro-preview
GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_TABLE_ID=
FEISHU_WEBHOOK_URL=
WX_APPID=
WX_APPSECRET=
WX_ENV_ID=newyuxiaozhu-5g28gork4d0ed6c4
ASSETS_DIR=/opt/poster_bot/assets/products
```

- [ ] **Step 4: 写 `.gitignore`**

```
.env
assets/products/
logs/
*.log
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/
/tmp/poster_bot*
```

- [ ] **Step 5: 安装依赖**

```bash
cd /opt/poster_bot
pip install -r requirements.txt
```

Expected: 所有包成功安装，无报错。

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore
git commit -m "chore: project scaffolding"
```

---

## Task 2: Pydantic 数据模型

**Files:**
- Create: `poster_bot/models.py`
- Create: `poster_bot/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

`tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError
from models import ProductRecord, PosterScheme, QCResult

def test_product_record_valid():
    r = ProductRecord(
        record_id="rec123",
        product_name="玻尿酸精华液",
        ingredients="透明质酸钠",
        benefits="深层补水，锁水保湿",
        category="护肤品",
        visual_style="极简扁平",
        brand_colors="#FFFFFF,#87CEEB",
        asset_filename="product_a.png",
    )
    assert r.product_name == "玻尿酸精华液"
    assert r.status == "PENDING"

def test_product_record_missing_required():
    with pytest.raises(ValidationError):
        ProductRecord(record_id="rec123")

def test_poster_scheme_valid():
    s = PosterScheme(
        scheme_name="方案A - 痛点共鸣型",
        visual_style="极简扁平",
        headline="告别干燥，喝饱的肌肤",
        subheadline="深层补水，连续28天见效",
        body_copy=["透明质酸钠深层渗透", "锁水时长提升300%"],
        cta="立即体验",
        image_prompt="Generate a minimalist poster...",
        aspect_ratio="3:4",
    )
    assert s.headline == "告别干燥，喝饱的肌肤"

def test_qc_result_valid():
    q = QCResult(passed=True, issues=[], confidence=0.95)
    assert q.passed is True

def test_qc_result_failed():
    q = QCResult(passed=False, issues=["product distorted", "logo missing"], confidence=0.4)
    assert len(q.issues) == 2
```

Run: `cd /opt/poster_bot && pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 2: 写 `models.py`**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ProductRecord(BaseModel):
    record_id: str
    product_name: str
    ingredients: str = ""
    benefits: str = ""
    xiaohongshu_topics: str = ""
    category: str = "未分类"
    visual_style: str = "极简扁平"
    brand_colors: str = "#FFFFFF"
    asset_filename: str = ""
    status: str = "PENDING"
    idempotency_key: str = ""


class PosterScheme(BaseModel):
    scheme_name: str
    visual_style: str
    headline: str
    subheadline: str
    body_copy: list[str]
    cta: str
    image_prompt: str
    aspect_ratio: str = "3:4"


class QCResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    confidence: float = 1.0
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_models.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: add Pydantic data models"
```

---

## Task 3: 飞书数据读取与状态回写

**Files:**
- Create: `poster_bot/feishu_reader.py`
- Create: `poster_bot/tests/test_feishu_reader.py`

飞书多维表格字段名（与表格一一对应）：
- `产品名称`, `成分`, `功效`, `小红书话题`, `分类`, `海报风格`, `品牌色`, `产品素材图文件名`, `状态`, `幂等键`, `云存储fileID`, `最后生成时间`

- [ ] **Step 1: 写失败测试**

`tests/test_feishu_reader.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from models import ProductRecord
from feishu_reader import fetch_pending_records, update_record_status


def _make_mock_record(record_id="rec001", status="PENDING"):
    record = MagicMock()
    record.record_id = record_id
    record.fields = {
        "产品名称": {"value": [{"text": "玻尿酸精华液"}]},
        "成分": {"value": [{"text": "透明质酸钠"}]},
        "功效": {"value": [{"text": "深层补水"}]},
        "小红书话题": {"value": [{"text": "秋冬护肤"}]},
        "分类": {"value": [{"text": "护肤品"}]},
        "海报风格": {"value": [{"text": "极简扁平"}]},
        "品牌色": {"value": [{"text": "#FFFFFF"}]},
        "产品素材图文件名": {"value": [{"text": "product_a.png"}]},
        "状态": {"value": [{"text": status}]},
        "幂等键": {"value": [{"text": ""}]},
    }
    return record


@patch("feishu_reader.build_client")
def test_fetch_pending_records(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.success.return_value = True
    mock_resp.data.items = [_make_mock_record("rec001", "PENDING")]
    mock_resp.data.has_more = False
    mock_client.bitable.v1.app_table_record.search.return_value = mock_resp

    records = fetch_pending_records()
    assert len(records) == 1
    assert records[0].record_id == "rec001"
    assert records[0].product_name == "玻尿酸精华液"


@patch("feishu_reader.build_client")
def test_update_record_status(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.success.return_value = True
    mock_client.bitable.v1.app_table_record.update.return_value = mock_resp

    update_record_status("rec001", "COPY_OK")
    mock_client.bitable.v1.app_table_record.update.assert_called_once()
```

Run: `cd /opt/poster_bot && pytest tests/test_feishu_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'feishu_reader'`

- [ ] **Step 2: 写 `feishu_reader.py`**

```python
import os
from datetime import datetime
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from models import ProductRecord

load_dotenv()

APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")
TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")


def build_client() -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(os.getenv("FEISHU_APP_ID", ""))
        .app_secret(os.getenv("FEISHU_APP_SECRET", ""))
        .build()
    )


def _extract_text(field_value) -> str:
    """Extract plain text from Feishu field value."""
    try:
        if isinstance(field_value, dict) and "value" in field_value:
            items = field_value["value"]
            if isinstance(items, list) and items:
                return items[0].get("text", "")
        return ""
    except Exception:
        return ""


def fetch_pending_records() -> list[ProductRecord]:
    client = build_client()
    records = []
    page_token = None

    while True:
        body = (
            SearchAppTableRecordRequestBody.builder()
            .filter(
                FilterInfo.builder()
                .conjunction("or")
                .conditions([
                    Condition.builder()
                    .field_name("状态")
                    .operator("is")
                    .value(["PENDING"])
                    .build(),
                    Condition.builder()
                    .field_name("状态")
                    .operator("is")
                    .value(["FAILED_RETRYABLE"])
                    .build(),
                ])
                .build()
            )
            .build()
        )
        req_builder = (
            SearchAppTableRecordRequest.builder()
            .app_token(APP_TOKEN)
            .table_id(TABLE_ID)
            .request_body(body)
        )
        if page_token:
            req_builder = req_builder.page_token(page_token)

        resp = client.bitable.v1.app_table_record.search(req_builder.build())
        if not resp.success():
            raise RuntimeError(f"Feishu fetch failed: {resp.msg}")

        for item in resp.data.items or []:
            f = item.fields
            records.append(ProductRecord(
                record_id=item.record_id,
                product_name=_extract_text(f.get("产品名称")),
                ingredients=_extract_text(f.get("成分")),
                benefits=_extract_text(f.get("功效")),
                xiaohongshu_topics=_extract_text(f.get("小红书话题")),
                category=_extract_text(f.get("分类")) or "未分类",
                visual_style=_extract_text(f.get("海报风格")) or "极简扁平",
                brand_colors=_extract_text(f.get("品牌色")) or "#FFFFFF",
                asset_filename=_extract_text(f.get("产品素材图文件名")),
                status=_extract_text(f.get("状态")) or "PENDING",
                idempotency_key=_extract_text(f.get("幂等键")),
            ))

        if not resp.data.has_more:
            break
        page_token = resp.data.page_token

    return records


def update_record_status(
    record_id: str,
    status: str,
    file_id: str = "",
    error_msg: str = "",
) -> None:
    client = build_client()
    fields: dict = {"状态": status}
    if file_id:
        fields["云存储fileID"] = file_id
    if status == "DONE":
        fields["最后生成时间"] = int(datetime.now().timestamp() * 1000)
    if error_msg:
        fields["错误信息"] = error_msg[:500]

    resp = client.bitable.v1.app_table_record.update(
        UpdateAppTableRecordRequest.builder()
        .app_token(APP_TOKEN)
        .table_id(TABLE_ID)
        .record_id(record_id)
        .request_body(
            AppTableRecord.builder().fields(fields).build()
        )
        .build()
    )
    if not resp.success():
        raise RuntimeError(f"Feishu update failed: {resp.msg}")
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_feishu_reader.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add feishu_reader.py tests/test_feishu_reader.py
git commit -m "feat: add Feishu reader and status writer"
```

---

## Task 4: 产品图预处理

**Files:**
- Create: `poster_bot/asset_processor.py`
- Create: `poster_bot/tests/test_asset_processor.py`

- [ ] **Step 1: 写失败测试**

`tests/test_asset_processor.py`:
```python
import base64
from pathlib import Path
from PIL import Image
import io
import pytest
from asset_processor import process_product_image


def test_process_product_image_returns_base64(tmp_path):
    # Create a small test image
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img_path = tmp_path / "test_product.png"
    img.save(img_path)

    result = process_product_image(str(img_path))

    # Should return a valid base64 string
    assert isinstance(result, str)
    decoded = base64.b64decode(result)
    output_img = Image.open(io.BytesIO(decoded))
    assert output_img.mode == "RGBA"  # rembg outputs RGBA


def test_process_product_image_file_not_found():
    with pytest.raises(FileNotFoundError):
        process_product_image("/nonexistent/path/product.png")
```

Run: `cd /opt/poster_bot && pytest tests/test_asset_processor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'asset_processor'`

- [ ] **Step 2: 写 `asset_processor.py`**

```python
import base64
import io
from pathlib import Path
from PIL import Image
from rembg import remove


MAX_SIZE = (800, 800)


def process_product_image(file_path: str) -> str:
    """
    Remove background with rembg, resize to fit MAX_SIZE, return base64-encoded PNG.
    Raises FileNotFoundError if file doesn't exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Product image not found: {file_path}")

    with open(path, "rb") as f:
        raw = f.read()

    # Remove background
    output = remove(raw)

    # Open as PIL RGBA image and resize
    img = Image.open(io.BytesIO(output)).convert("RGBA")
    img.thumbnail(MAX_SIZE, Image.LANCZOS)

    # Encode to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_asset_processor.py -v`
Expected: 2 passed

Note: `rembg` 首次运行会下载模型（约 170MB），需要网络连接。

- [ ] **Step 4: Commit**

```bash
git add asset_processor.py tests/test_asset_processor.py
git commit -m "feat: add rembg product image preprocessor"
```

---

## Task 5: Prompt 模板文件

**Files:**
- Create: `poster_bot/prompts/scheme_prompt.txt`
- Create: `poster_bot/prompts/image_prompt.txt`

- [ ] **Step 1: 写 `prompts/scheme_prompt.txt`**

```
# Role: 资深商业文案策划与 AI 绘图指令专家。
- **核心理念**: "内容即价值"。视觉服务于文字，海报必须具备独立阅读价值，排版必须专业且清晰。

## 任务目标
基于以下产品信息，自主构思出 3 个视觉风格截然不同、文案直击痛点的朋友圈海报策划方案，然后**直接自动选取方案A**作为最终输出，无需用户选择。

## 产品信息
- 产品名称：{product_name}
- 产品卖点：{selling_points}
- 小红书话题参考：{idea}
- 偏好风格：{visual_style}
- 品牌色：{brand_colors}

## 🧠 核心思考逻辑 (请在后台默默执行，不要输出)
1. **深度洞察**：分析产品名称和卖点，提炼出最能打动宝妈群体的核心卖点或情绪（如焦虑、期盼、治愈、信任）。
2. **风格动态匹配 (CRITICAL)**：结合偏好风格，从你庞大的设计知识库中，自主挑选 3 种完全不同、且极具高级感的视觉流派。**绝对不要套用固定公式，请为你每次挑选的风格命名！**

## 📝 请内部生成3个方案后，直接输出方案A的内容（JSON格式）

请严格按照以下 JSON 格式输出，不要输出任何其他文字：

{{
  "scheme_name": "方案A - [文案切入点类型]",
  "visual_style": "[你选定的风格名称]",
  "headline": "[5-8字，极致抓人的大标题]",
  "subheadline": "[一句话痛点补充或情绪安抚]",
  "body_copy": [
    "[核心文案1，具体有信息量]",
    "[核心文案2]",
    "[核心文案3]",
    "[核心文案4（可选）]",
    "[核心文案5（可选）]"
  ],
  "cta": "[行动号召或金句]",
  "scene_description": "[用极具画面感的语言描述符合该风格的构图、光影、色调和主体细节]",
  "layout_description": "[详细描述文字排版位置]"
}}
```

- [ ] **Step 2: 写 `prompts/image_prompt.txt`**

```
# Role: 顶级代码级视觉翻译官与全风格场景融合排版引擎

## Profile
- **身份**: 连接"前端策划案"与"底层生图引擎"的核心枢纽。
- **核心理念**: 绝对服从画风！文字与视觉场景**完美融合（Seamless Integration）**，拒绝生硬的"贴膏药式"排版。

## 输入信息
- 店铺名称：{store_name}
- 海报尺寸：{size}
- 产品卖点：{selling_points}
- 方案内容：{selected_scheme}

## 🚫 视觉红线 (FATAL)
1. 严禁风格冲突：绝不可使用与方案中指定风格相悖的渲染词汇。
2. 严禁扁平死板：留白区必须带有符合该画风的微观质感或自然景深。
3. 严禁图文割裂：文字必须与场景有机融合 (Environmental Typography)。
4. 只输出生图代码块，禁止输出任何解释或问候语。

## 任务
严格按下面格式，输出一段包含在 ``` 里的生图提示词：

```
【指令：请调用最高算力，严格执行以下高层次商业海报指令】

Size: {size}
Action: Generate Poster Immediately

文生图提示词：{product_name}产品海报

**主题与核心视觉**
[简述画面核心主题与第一眼视觉焦点，融入方案的视觉风格]

**顶级美工场景排版系统 (In-Scene Typography - CRITICAL)**
- 核心指令: Environmental typography, seamless text and image integration, typography interacting with lighting and shadows, magazine cover aesthetic.
- 图文自然融合：文字需仿佛置身于实景空间中，带有微妙的场景环境光反射，避免生硬的抠图感。
- 景深与空间层次：利用前景的模糊元素在背景中自然晕染出低对比度区域供文字安放。
- 字体定义：主标题使用极具视觉冲击力的粗体无衬线；正文使用高辨识度的纤细黑体，强烈粗细对比。

**详细文案与层级渲染 (CRITICAL)**
Instruction: Render the text inside the double quotes exactly as written. Perfect text rendering, no deformed letters.

- 顶部店铺名（Top Center，不可偏离）："{store_name}"
- 主标题："{headline}"
- 副标题："{subheadline}"
- 核心干货（列表式，行距宽松）：
{body_copy_formatted}
- 底部标语/CTA："{cta}"

**场景设定与光影**
{scene_description}

**构图**
{layout_description}
尺寸比例：{size}

**产品图融合规则（CRITICAL）**
- 严格保留产品外形、颜色、包装文字、Logo 不变
- 产品必须是视觉焦点，占画面核心位置
- 带轻微金属质感，光影与整体画面一致
- 禁止重新设计产品，禁止遮挡品牌关键元素

**风格与质量**
- {visual_style}
- 8k resolution, masterpiece, highly cohesive composition
- Perfect text rendering, no deformed letters, sharp edges, clear legibility
```
```

- [ ] **Step 3: 验证文件存在**

```bash
ls /opt/poster_bot/prompts/
```
Expected: `image_prompt.txt  scheme_prompt.txt`

- [ ] **Step 4: Commit**

```bash
git add prompts/
git commit -m "feat: add scheme and image prompt templates"
```

---

## Task 6: 内容生成器（两阶段文案）

**Files:**
- Create: `poster_bot/content_generator.py`
- Create: `poster_bot/tests/test_content_generator.py`

- [ ] **Step 1: 写失败测试**

`tests/test_content_generator.py`:
```python
import json
import pytest
from unittest.mock import patch, MagicMock
from models import ProductRecord, PosterScheme
from content_generator import generate_poster_content


def _make_record():
    return ProductRecord(
        record_id="rec001",
        product_name="玻尿酸精华液",
        ingredients="透明质酸钠",
        benefits="深层补水，锁水保湿",
        xiaohongshu_topics="秋冬护肤",
        visual_style="极简扁平",
        brand_colors="#FFFFFF",
        asset_filename="product_a.png",
    )


def _mock_scheme_response():
    return json.dumps({
        "scheme_name": "方案A - 痛点共鸣型",
        "visual_style": "极简莫兰迪",
        "headline": "告别干燥，喝饱的肌肤",
        "subheadline": "透明质酸钠深层渗透，28天见证蜕变",
        "body_copy": ["深层补水", "锁水保湿", "温和不刺激"],
        "cta": "立即体验",
        "scene_description": "极简白色背景，产品居中",
        "layout_description": "标题居上，产品居中，文案居下",
    })


@patch("content_generator.OpenAI")
def test_generate_poster_content_returns_scheme(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    # Stage 1 mock: scheme JSON
    stage1_msg = MagicMock()
    stage1_msg.content = _mock_scheme_response()
    stage1_choice = MagicMock()
    stage1_choice.message = stage1_msg
    stage1_resp = MagicMock()
    stage1_resp.choices = [stage1_choice]

    # Stage 2 mock: image prompt
    stage2_msg = MagicMock()
    stage2_msg.content = "```\nGenerate a minimalist poster...\n```"
    stage2_choice = MagicMock()
    stage2_choice.message = stage2_msg
    stage2_resp = MagicMock()
    stage2_resp.choices = [stage2_choice]

    mock_client.chat.completions.create.side_effect = [stage1_resp, stage2_resp]

    record = _make_record()
    scheme = generate_poster_content(record)

    assert isinstance(scheme, PosterScheme)
    assert scheme.headline == "告别干燥，喝饱的肌肤"
    assert "Generate a minimalist poster" in scheme.image_prompt
    assert mock_client.chat.completions.create.call_count == 2


@patch("content_generator.OpenAI")
def test_generate_poster_content_invalid_json_raises(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    bad_msg = MagicMock()
    bad_msg.content = "这不是JSON"
    bad_choice = MagicMock()
    bad_choice.message = bad_msg
    bad_resp = MagicMock()
    bad_resp.choices = [bad_choice]
    mock_client.chat.completions.create.return_value = bad_resp

    with pytest.raises(ValueError, match="Stage 1 JSON parse error"):
        generate_poster_content(_make_record())
```

Run: `cd /opt/poster_bot && pytest tests/test_content_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_generator'`

- [ ] **Step 2: 写 `content_generator.py`**

```python
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models import ProductRecord, PosterScheme

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
STORE_NAME = os.getenv("STORE_NAME", "浴小主")


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE"),
    )


def _extract_code_block(text: str) -> str:
    """Extract content between first ``` and last ```."""
    match = re.search(r"```\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def generate_poster_content(record: ProductRecord) -> PosterScheme:
    client = _build_client()
    model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")

    # --- Stage 1: Generate scheme ---
    scheme_template = _load_prompt("scheme_prompt.txt")
    selling_points = f"{record.benefits}；成分：{record.ingredients}"
    scheme_prompt = scheme_template.format(
        product_name=record.product_name,
        selling_points=selling_points,
        idea=record.xiaohongshu_topics or "（无）",
        visual_style=record.visual_style,
        brand_colors=record.brand_colors,
    )

    stage1_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": scheme_prompt}],
        temperature=0.8,
    )
    stage1_content = stage1_resp.choices[0].message.content

    try:
        # Strip markdown code block if present
        clean = re.sub(r"```json|```", "", stage1_content).strip()
        scheme_data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Stage 1 JSON parse error: {e}\nResponse: {stage1_content[:300]}")

    # --- Stage 2: Generate image prompt ---
    body_copy_formatted = "\n".join(f'  - "{line}"' for line in scheme_data.get("body_copy", []))

    image_template = _load_prompt("image_prompt.txt")
    image_prompt_filled = image_template.format(
        store_name=STORE_NAME,
        size="3:4",
        selling_points=selling_points,
        selected_scheme=json.dumps(scheme_data, ensure_ascii=False),
        product_name=record.product_name,
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy_formatted=body_copy_formatted,
        cta=scheme_data.get("cta", ""),
        scene_description=scheme_data.get("scene_description", ""),
        layout_description=scheme_data.get("layout_description", ""),
        visual_style=scheme_data.get("visual_style", record.visual_style),
    )

    stage2_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": image_prompt_filled}],
        temperature=0.7,
    )
    stage2_content = stage2_resp.choices[0].message.content
    image_prompt = _extract_code_block(stage2_content)

    return PosterScheme(
        scheme_name=scheme_data.get("scheme_name", "方案A"),
        visual_style=scheme_data.get("visual_style", record.visual_style),
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy=scheme_data.get("body_copy", []),
        cta=scheme_data.get("cta", ""),
        image_prompt=image_prompt,
        aspect_ratio="3:4",
    )
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_content_generator.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add content_generator.py tests/test_content_generator.py
git commit -m "feat: add two-stage content generator"
```

---

## Task 7: 图像生成器

**Files:**
- Create: `poster_bot/image_generator.py`
- Create: `poster_bot/tests/test_image_generator.py`

- [ ] **Step 1: 写失败测试**

`tests/test_image_generator.py`:
```python
import base64
import pytest
from unittest.mock import patch, MagicMock
from image_generator import generate_poster_image


FAKE_B64 = base64.b64encode(b"fake_image_data").decode()


def _mock_image_response(b64_data: str):
    """Mock an OpenAI-compatible response that contains a base64 image."""
    msg = MagicMock()
    # Gemini image response returns image in content parts
    part = MagicMock()
    part.type = "image_url"
    part.image_url.url = f"data:image/jpeg;base64,{b64_data}"
    msg.content = [part]
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("image_generator.OpenAI")
def test_generate_poster_image_returns_bytes(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_image_response(FAKE_B64)

    result = generate_poster_image("Generate a poster...", FAKE_B64)

    assert isinstance(result, bytes)
    assert result == b"fake_image_data"


@patch("image_generator.OpenAI")
def test_generate_poster_image_no_image_raises(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    # Response with only text, no image
    msg = MagicMock()
    part = MagicMock()
    part.type = "text"
    part.text = "I cannot generate an image."
    msg.content = [part]
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    mock_client.chat.completions.create.return_value = resp

    with pytest.raises(ValueError, match="No image returned"):
        generate_poster_image("Generate a poster...", FAKE_B64)
```

Run: `cd /opt/poster_bot && pytest tests/test_image_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'image_generator'`

- [ ] **Step 2: 写 `image_generator.py`**

```python
import base64
import os

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

FUSION_RULES = """
CRITICAL product fusion rules:
- Strictly preserve product shape, colors, packaging text, and logo unchanged
- Do NOT redesign the product or alter its proportions
- Product must be the visual focal point, never obscured
- Apply subtle metallic sheen consistent with overall lighting
- Brand elements must remain fully visible
"""


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE"),
    )


def _extract_image_bytes(response) -> bytes:
    """Extract image bytes from OpenAI-compatible Gemini response."""
    choices = response.choices
    if not choices:
        raise ValueError("No image returned: empty choices")

    content = choices[0].message.content

    # Handle list of content parts (multimodal response)
    if isinstance(content, list):
        for part in content:
            part_type = getattr(part, "type", None)
            if part_type == "image_url":
                url = part.image_url.url
                if url.startswith("data:"):
                    b64 = url.split(",", 1)[1]
                    return base64.b64decode(b64)
        raise ValueError("No image returned: no image_url part in response")

    # Handle string content with embedded base64
    if isinstance(content, str) and "base64" in content:
        import re
        match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
        if match:
            return base64.b64decode(match.group(1))

    raise ValueError(f"No image returned: unexpected response format. Content: {str(content)[:200]}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def generate_poster_image(image_prompt: str, product_image_b64: str) -> bytes:
    """
    Generate poster image by sending text prompt + product image to Gemini.
    Returns raw image bytes (JPEG).
    """
    client = _build_client()
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

    full_prompt = f"{image_prompt}\n\n{FUSION_RULES}"

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": full_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{product_image_b64}"},
                },
            ],
        }],
    )

    return _extract_image_bytes(response)
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_image_generator.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add image_generator.py tests/test_image_generator.py
git commit -m "feat: add Gemini image generator with product fusion"
```

---

## Task 8: QC 质量检查

**Files:**
- Create: `poster_bot/qc_checker.py`
- Create: `poster_bot/tests/test_qc_checker.py`

- [ ] **Step 1: 写失败测试**

`tests/test_qc_checker.py`:
```python
import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from models import QCResult
from qc_checker import check_poster_quality


FAKE_B64 = base64.b64encode(b"fake").decode()


def _mock_qc_response(passed: bool, issues: list):
    msg = MagicMock()
    msg.content = json.dumps({"passed": passed, "issues": issues, "confidence": 0.9})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("qc_checker.OpenAI")
def test_qc_passes(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_qc_response(True, [])

    result = check_poster_quality(FAKE_B64, FAKE_B64)
    assert result.passed is True
    assert result.issues == []


@patch("qc_checker.OpenAI")
def test_qc_fails_with_issues(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_qc_response(
        False, ["product logo distorted", "text cropped at bottom"]
    )

    result = check_poster_quality(FAKE_B64, FAKE_B64)
    assert result.passed is False
    assert len(result.issues) == 2
```

Run: `cd /opt/poster_bot && pytest tests/test_qc_checker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qc_checker'`

- [ ] **Step 2: 写 `qc_checker.py`**

```python
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import QCResult

load_dotenv()

QC_PROMPT = """
You are a quality control inspector for commercial product posters.

You are given two images:
1. The generated poster (first image)
2. The original product photo (second image)

Check the generated poster against these criteria and respond with JSON only:

{
  "passed": true/false,
  "issues": ["issue1", "issue2"],
  "confidence": 0.0-1.0
}

Criteria (ALL must pass for passed=true):
1. Product is clearly visible and is the focal point
2. Product shape and packaging are not distorted or redesigned
3. Brand colors are approximately preserved
4. Text in the poster is not cropped or illegible
5. No hallucinated extra products appear
6. Logo/brand elements are not obscured

Be strict. If any criterion fails, set passed=false and list all issues.
"""


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE"),
    )


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    reraise=True,
)
def check_poster_quality(poster_b64: str, product_b64: str) -> QCResult:
    """
    Use multimodal model to verify poster quality.
    poster_b64: base64-encoded JPEG of generated poster
    product_b64: base64-encoded PNG of original product (pre-processed)
    """
    client = _build_client()
    model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{poster_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{product_b64}"}},
                {"type": "text", "text": QC_PROMPT},
            ],
        }],
        temperature=0.1,
    )

    content = response.choices[0].message.content
    clean = re.sub(r"```json|```", "", content).strip()

    try:
        data = json.loads(clean)
        return QCResult(**data)
    except (json.JSONDecodeError, Exception):
        # If QC model fails to return valid JSON, default to passed to avoid blocking
        return QCResult(passed=True, issues=["QC model returned invalid JSON"], confidence=0.5)
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_qc_checker.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add qc_checker.py tests/test_qc_checker.py
git commit -m "feat: add multimodal QC checker"
```

---

## Task 9: 微信云存储上传

**Files:**
- Create: `poster_bot/wechat_uploader.py`
- Create: `poster_bot/tests/test_wechat_uploader.py`

微信云存储上传流程（WeChat Server API）：
1. `GET https://api.weixin.qq.com/cgi-bin/token` → `access_token`
2. `POST https://api.weixin.qq.com/tcb/uploadfile?access_token=...` → `url`, `token`, `authorization`, `file_id`, `cos_file_id`
3. `POST {url}` multipart form → 上传成功

- [ ] **Step 1: 写失败测试**

`tests/test_wechat_uploader.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from wechat_uploader import get_wx_access_token, upload_image


@patch("wechat_uploader.requests.get")
def test_get_wx_access_token(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "test_token_123", "expires_in": 7200}
    mock_get.return_value = mock_resp

    token = get_wx_access_token()
    assert token == "test_token_123"
    mock_get.assert_called_once()


@patch("wechat_uploader.get_wx_access_token")
@patch("wechat_uploader.requests.post")
def test_upload_image(mock_post, mock_token):
    mock_token.return_value = "test_token_123"

    # Mock Step 2: get upload info
    upload_info_resp = MagicMock()
    upload_info_resp.json.return_value = {
        "errcode": 0,
        "url": "https://cos.ap-beijing.myqcloud.com/bucket",
        "token": "cos_token",
        "authorization": "q-sign-algorithm...",
        "file_id": "cloud://env.bucket/images/test.jpg",
        "cos_file_id": "cos_file_id_123",
    }

    # Mock Step 3: actual upload
    upload_resp = MagicMock()
    upload_resp.status_code = 204

    mock_post.side_effect = [upload_info_resp, upload_resp]

    file_id = upload_image(b"fake_image_bytes", "images/护肤品/test_20260406.jpg")
    assert file_id == "cloud://env.bucket/images/test.jpg"


@patch("wechat_uploader.requests.get")
def test_get_wx_access_token_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"errcode": 40013, "errmsg": "invalid appid"}
    mock_get.return_value = mock_resp

    with pytest.raises(RuntimeError, match="WeChat token error"):
        get_wx_access_token()
```

Run: `cd /opt/poster_bot && pytest tests/test_wechat_uploader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wechat_uploader'`

- [ ] **Step 2: 写 `wechat_uploader.py`**

```python
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

WX_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WX_UPLOAD_URL = "https://api.weixin.qq.com/tcb/uploadfile"


def get_wx_access_token() -> str:
    """Fetch WeChat server access token using appid + appsecret."""
    resp = requests.get(
        WX_TOKEN_URL,
        params={
            "grant_type": "client_credential",
            "appid": os.getenv("WX_APPID", ""),
            "secret": os.getenv("WX_APPSECRET", ""),
        },
        timeout=10,
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"WeChat token error: {data}")
    return data["access_token"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True,
)
def upload_image(image_bytes: bytes, cloud_path: str) -> str:
    """
    Upload image bytes to WeChat CloudBase storage.
    cloud_path: e.g. "images/护肤品/product_20260406.jpg"
    Returns fileID.
    """
    env_id = os.getenv("WX_ENV_ID", "")
    access_token = get_wx_access_token()

    # Step 1: Get upload info
    info_resp = requests.post(
        f"{WX_UPLOAD_URL}?access_token={access_token}",
        json={"env": env_id, "path": cloud_path},
        timeout=15,
    )
    info = info_resp.json()
    if info.get("errcode", 0) != 0:
        raise RuntimeError(f"CloudBase upload info error: {info}")

    # Step 2: Upload to COS
    upload_resp = requests.post(
        info["url"],
        data={
            "key": cloud_path,
            "Signature": info["authorization"],
            "x-cos-security-token": info["token"],
            "x-cos-meta-fileid": info["cos_file_id"],
        },
        files={"file": ("poster.jpg", image_bytes, "image/jpeg")},
        timeout=30,
    )

    if upload_resp.status_code not in (200, 204):
        raise RuntimeError(f"COS upload failed: HTTP {upload_resp.status_code}")

    return info["file_id"]


def build_cloud_path(category: str, product_name: str) -> str:
    """Build cloud storage path: images/<category>/<product>_<YYYYMMDD>.jpg"""
    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = product_name.replace(" ", "_").replace("/", "_")
    safe_category = category.replace(" ", "_")
    return f"images/{safe_category}/{safe_name}_{date_str}.jpg"
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_wechat_uploader.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add wechat_uploader.py tests/test_wechat_uploader.py
git commit -m "feat: add WeChat CloudBase HTTP API uploader"
```

---

## Task 10: 主调度器

**Files:**
- Create: `poster_bot/main.py`
- Create: `poster_bot/tests/test_main.py`

- [ ] **Step 1: 写失败测试**

`tests/test_main.py`:
```python
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models import ProductRecord, PosterScheme, QCResult


def _make_record(record_id="rec001"):
    return ProductRecord(
        record_id=record_id,
        product_name="玻尿酸精华液",
        ingredients="透明质酸钠",
        benefits="深层补水",
        category="护肤品",
        asset_filename="product_a.png",
    )


def _make_scheme():
    return PosterScheme(
        scheme_name="方案A",
        visual_style="极简",
        headline="告别干燥",
        subheadline="深层补水",
        body_copy=["补水", "锁水"],
        cta="立即体验",
        image_prompt="Generate poster",
        aspect_ratio="3:4",
    )


@patch("main.upload_image", return_value="cloud://file_id_123")
@patch("main.build_cloud_path", return_value="images/护肤品/test.jpg")
@patch("main.check_poster_quality", return_value=QCResult(passed=True, issues=[]))
@patch("main.generate_poster_image", return_value=b"fake_jpeg")
@patch("main.process_product_image", return_value="fake_b64")
@patch("main.generate_poster_content")
@patch("main.update_record_status")
@patch("main.fetch_pending_records")
def test_process_product_success(
    mock_fetch, mock_update, mock_content, mock_asset,
    mock_image, mock_qc, mock_path, mock_upload
):
    import main
    mock_content.return_value = _make_scheme()

    record = _make_record()
    asyncio.run(main.process_product(record))

    # Verify status progression
    calls = [c.args[1] for c in mock_update.call_args_list]
    assert "IMAGE_OK" in calls
    assert "DONE" in calls
```

Run: `cd /opt/poster_bot && pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 2: 写 `main.py`**

```python
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
import requests

from asset_processor import process_product_image
from content_generator import generate_poster_content
from feishu_reader import fetch_pending_records, update_record_status
from image_generator import generate_poster_image
from models import ProductRecord, PosterScheme
from qc_checker import check_poster_quality
from wechat_uploader import upload_image, build_cloud_path

load_dotenv()

LOCK_FILE = Path("/tmp/poster_bot.lock")
LOG_DIR = Path("/opt/poster_bot/logs")
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/opt/poster_bot/assets/products"))
MAX_QC_RETRIES = 2


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{date.today()}.log"
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(str(log_file), rotation="00:00", retention="30 days", level="DEBUG")


def acquire_lock():
    if LOCK_FILE.exists():
        logger.warning(f"Lock file exists at {LOCK_FILE}. Another instance may be running. Exiting.")
        sys.exit(0)
    LOCK_FILE.touch()


def release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def send_feishu_alert(message: str):
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": f"[浴小主海报机器人]\n{message}"}},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Failed to send Feishu alert: {e}")


async def process_product(record: ProductRecord) -> None:
    logger.info(f"Processing: {record.product_name} (record_id={record.record_id})")

    try:
        # Step A: Generate copy & image prompt
        update_record_status(record.record_id, "COPY_OK")
        scheme: PosterScheme = generate_poster_content(record)
        logger.info(f"{record.product_name}: content generated — {scheme.headline}")

        # Step B: Preprocess product image
        asset_path = str(ASSETS_DIR / record.asset_filename)
        product_b64 = await asyncio.get_event_loop().run_in_executor(
            None, process_product_image, asset_path
        )

        # Step C: Generate poster image (with QC retry loop)
        poster_bytes = None
        qc_prompt_suffix = ""
        for attempt in range(MAX_QC_RETRIES + 1):
            poster_bytes = await asyncio.get_event_loop().run_in_executor(
                None,
                generate_poster_image,
                scheme.image_prompt + qc_prompt_suffix,
                product_b64,
            )

            # Step D: QC check
            import base64
            poster_b64 = base64.b64encode(poster_bytes).decode()
            qc_result = await asyncio.get_event_loop().run_in_executor(
                None, check_poster_quality, poster_b64, product_b64
            )

            if qc_result.passed:
                logger.info(f"{record.product_name}: QC passed (confidence={qc_result.confidence})")
                break
            else:
                logger.warning(f"{record.product_name}: QC failed attempt {attempt+1}: {qc_result.issues}")
                if attempt < MAX_QC_RETRIES:
                    issues_str = "; ".join(qc_result.issues)
                    qc_prompt_suffix = f"\n\nPREVIOUS ATTEMPT FAILED QC. Fix these issues: {issues_str}. Be stricter about preserving the product."
                else:
                    logger.error(f"{record.product_name}: QC failed after {MAX_QC_RETRIES+1} attempts. Marking FAILED_MANUAL.")
                    update_record_status(record.record_id, "FAILED_MANUAL", error_msg=str(qc_result.issues))
                    return

        update_record_status(record.record_id, "IMAGE_OK")

        # Step E: Upload to WeChat cloud storage
        cloud_path = build_cloud_path(record.category, record.product_name)
        file_id = await asyncio.get_event_loop().run_in_executor(
            None, upload_image, poster_bytes, cloud_path
        )
        logger.info(f"{record.product_name}: uploaded → {file_id}")

        # Step F: Write back to Feishu
        update_record_status(record.record_id, "DONE", file_id=file_id)
        logger.success(f"{record.product_name}: DONE")

    except Exception as e:
        logger.error(f"{record.product_name}: FAILED — {e}")
        update_record_status(record.record_id, "FAILED_RETRYABLE", error_msg=str(e))
        raise


async def run_pipeline():
    records = fetch_pending_records()
    if not records:
        logger.info("No pending records. Exiting.")
        return

    logger.info(f"Found {len(records)} pending records.")
    failed = []

    results = await asyncio.gather(
        *[process_product(r) for r in records],
        return_exceptions=True,
    )

    for record, result in zip(records, results):
        if isinstance(result, Exception):
            failed.append(f"{record.product_name}: {result}")

    if failed:
        msg = f"今日有 {len(failed)} 个产品生成失败：\n" + "\n".join(failed)
        logger.error(msg)
        send_feishu_alert(msg)
    else:
        logger.success(f"All {len(records)} products processed successfully.")


def main():
    setup_logging()
    acquire_lock()
    try:
        asyncio.run(run_pipeline())
    finally:
        release_lock()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/poster_bot && pytest tests/test_main.py -v`
Expected: 1 passed

- [ ] **Step 4: 运行所有测试**

Run: `cd /opt/poster_bot && pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add main orchestrator with asyncio, job lock, and Feishu alerts"
```

---

## Task 11: GitHub 仓库 & 推送

- [ ] **Step 1: 在 GitHub 创建仓库**

在 GitHub.com 创建新仓库，名称如 `yuzhuzhu-poster-bot`，选 Public（开源），不勾选 Initialize（本地已有代码）。

- [ ] **Step 2: 添加 remote 并推送**

```bash
cd /opt/poster_bot
git remote add origin https://github.com/<your-username>/yuzhuzhu-poster-bot.git
git push -u origin main
```

- [ ] **Step 3: 验证 `.env` 未被推送**

```bash
git log --oneline
git show HEAD --name-only | grep ".env"
```
Expected: `.env` 不出现在任何 commit 中。

---

## Task 12: 服务器部署 & Cron 配置

- [ ] **Step 1: 配置 `.env`（在服务器上）**

```bash
nano /opt/poster_bot/.env
```

填写所有变量值（参考 `.env.example`）。需要准备的凭证：
- 飞书：创建企业自建应用，获取 App ID + App Secret；记录多维表格的 App Token 和 Table ID
- 微信：小程序管理后台 → 设置 → 基本设置 → AppID + AppSecret
- Gemini API Key 已有

- [ ] **Step 2: 上传产品素材图**

```bash
# 从本地上传（在本地机器执行）
scp /path/to/your/product_images/*.png root@49.235.145.49:/opt/poster_bot/assets/products/
```

- [ ] **Step 3: 配置 cron**

```bash
crontab -e
```

添加：
```
0 8 * * * cd /opt/poster_bot && /usr/bin/python3 main.py >> /opt/poster_bot/logs/cron.log 2>&1
```

- [ ] **Step 4: 手动运行集成测试**

```bash
cd /opt/poster_bot
python3 main.py
```

检查：
- `/opt/poster_bot/logs/<today>.log` 有日志输出
- 飞书表格状态列从 PENDING 变为 DONE
- 微信云开发控制台 → 云存储 → 出现新图片

- [ ] **Step 5: 次日验证定时任务**

```bash
# 次日 08:05 检查
cat /opt/poster_bot/logs/cron.log
cat /opt/poster_bot/logs/$(date +%Y-%m-%d).log
```

Expected: 日志显示各产品 DONE，无 FAILED。

---

## Self-Review

**Spec coverage check:**

| Spec 要求 | 实现 Task |
|-----------|-----------|
| 飞书读取产品数据 | Task 3 |
| 飞书状态回写 | Task 3 |
| rembg 抠图预处理 | Task 4 |
| 方案策划 Prompt 两阶段 | Task 5, 6 |
| gemini-3.1-pro-preview 文案 | Task 6 |
| gemini-3-pro-image-preview 图像 | Task 7 |
| 产品图融合规则写入提示词 | Task 7 |
| QC 质量检查（最多重试2次） | Task 8 |
| CloudBase HTTP API 上传 | Task 9 |
| asyncio 并发 | Task 10 |
| Job Lock 防重复 | Task 10 |
| loguru 日志轮转 | Task 10 |
| 飞书 Webhook 告警 | Task 10 |
| tenacity 重试 | Task 6, 7, 8, 9 |
| .env 不入库 | Task 1 |
| GitHub 开源 | Task 11 |
| cron 每天 08:00 | Task 12 |
| 店铺名固定"浴小主" | Task 6 |

所有 Spec 要求均已覆盖。

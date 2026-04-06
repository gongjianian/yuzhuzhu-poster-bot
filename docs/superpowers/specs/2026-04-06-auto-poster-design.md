# 设计文档：每日自动作图上传系统（v2）

**日期**: 2026-04-06  
**状态**: 待实现  
**版本说明**: 整合了 Gemini 和 Codex 的审阅建议

---

## 背景与目标

用户每天需要手动完成：输入产品信息 → 生成海报提示词 → 生成图片 → 上传微信小程序云存储。

目标：部署在腾讯云 Ubuntu 服务器，每天由 cron 全自动完成，无需人工介入。

---

## 系统架构（更新后）

```
cron (每天 08:00)
└── main.py
    ├── 1. 飞书多维表格 → 读取"待处理/失败可重试"产品行
    ├── 2. 对每个产品（可并发）：
    │   ├── Step A: gemini-2.5-flash → 生成结构化 JSON 文案计划（Pydantic 校验）
    │   ├── Step B: rembg 产品图抠图预处理
    │   ├── Step C: gemini-3-pro-image-preview → 传入 JSON+产品切图 → 生成海报
    │   ├── Step D: 多模态 QC 检查（验证产品主体、品牌色、Logo 未变形）
    │   ├── Step E: CloudBase HTTP API → 上传到微信云存储
    │   └── Step F: 回写飞书状态 + fileID
    └── 3. loguru 日志轮转 + 飞书 Webhook 告警（失败时）
```

---

## 模块设计

### 模块 1：飞书数据读取 (`feishu_reader.py`)

- **SDK**: `lark-oapi`
- **飞书多维表格字段**：

  | 字段名 | 类型 | 说明 |
  |--------|------|------|
  | 产品名称 | 文本 | 如：玻尿酸精华液 |
  | 成分 | 文本 | 核心成分 |
  | 功效 | 文本 | 产品卖点 |
  | 小红书话题 | 文本 | 可选热点话题 |
  | 分类 | 单选 | 对应云存储目录 |
  | 海报风格 | 单选 | 3D C4D / 极简扁平 / 新中式插画 等 |
  | 品牌色 | 文本 | 如：#FF6B6B, #FFFFFF |
  | 产品素材图文件名 | 文本 | 服务器上的文件名，如 product_a.png |
  | 状态 | 单选 | PENDING / COPY_OK / IMAGE_OK / UPLOAD_OK / DONE / FAILED_RETRYABLE / FAILED_MANUAL |
  | 幂等键 | 文本 | date+record_id+prompt_version+asset_hash，防止重复生成 |
  | 云存储 fileID | 文本 | 上传成功后写入 |
  | 最后生成时间 | 日期 | 完成后写入 |

- **读取逻辑**: 只拉取状态为 `PENDING` 或 `FAILED_RETRYABLE` 的行
- **Job Lock**: 脚本启动时写锁文件 `/tmp/poster_bot.lock`，防止 cron 重复触发

---

### 模块 2：文案与提示词生成（两阶段，`content_generator.py`）

**模型**: `gemini-3.1-pro-preview`（顶级模型，负责全部文案和提示词创作）

#### 第一阶段：自动生成海报方案

- **Prompt 来源**: 用户现有的"方案策划 Prompt"，变量替换为：
  - `{{productName}}` ← 飞书表格「产品名称」
  - `{{sellingPoints}}` ← 飞书表格「功效」+「成分」
  - `{{idea}}` ← 飞书表格「小红书话题」（可为空）
- **自动化改造**: 去掉 A/B/C 用户选择交互，改为**自动选取方案 A**（或按飞书表格「海报风格」字段匹配最接近的方案）
- **输出**: 结构化的方案文本（主标题、副标题、核心文案、画面脑补、排版描述）

#### 第二阶段：生成图像提示词

- **Prompt 来源**: 用户现有的"视觉翻译官 Prompt"，变量替换为：
  - `{{storeName}}` ← 固定值 `"浴小主"`（硬编码在配置中，无需飞书维护）
  - `{{size}}` ← 固定值 `3:4`（或飞书表格中配置）
  - `{{sellingPoints}}` ← 同上
  - `{{selectedScheme}}` ← 第一阶段输出的方案内容
- **输出**: 完整的图像生成提示词（Markdown 代码块格式）

#### Pydantic 校验结构

```json
{
  "scheme_name": "方案A - 痛点共鸣型",
  "visual_style": "极简新中式",
  "headline": "主标题",
  "subheadline": "副标题",
  "body_copy": ["文案1", "文案2", "文案3"],
  "cta": "行动号召",
  "image_prompt": "完整图像提示词字符串",
  "aspect_ratio": "3:4"
}
```

- 两阶段均用同一个 API 调用（`gemini-3.1-pro-preview`），第二阶段将第一阶段输出作为上下文传入
- Pydantic 校验通过后才进入图像生成，否则标记 `FAILED_RETRYABLE`

---

### 模块 3：产品图预处理 (`asset_processor.py`)

- **库**: `rembg`（深度学习轻量化抠图）
- **输入**: `/opt/poster_bot/assets/products/<文件名>`
- **处理步骤**:
  1. `rembg` 移除背景，输出透明 PNG
  2. 等比缩放到标准尺寸，放置在纯色画布上
  3. base64 编码，传给图像模型
- **目的**: 去除杂乱背景，让模型融合效果更稳定

---

### 模块 4：图像生成 (`image_generator.py`)

- **API**: `https://api.buxianliang.fun`（Key 从环境变量读取）
- **模型**: `gemini-3-pro-image-preview`（高质量图像生成）；备用 `gemini-3.1-flash-image-preview`
- **输入**:
  - 上一步生成的 `image_prompt`（来自 Pydantic JSON）
  - 预处理后的产品切图（base64）
- **产品图融合 Prompt 规则**（硬性约束，写入提示词）:
  - 严格保留产品外形、颜色、包装文字、Logo 不变
  - 不重新设计产品，比例不变
  - 产品必须是视觉焦点，不可被遮挡
  - 品牌关键元素不可被覆盖
- **重试**: `tenacity` 指数退避，处理 429 / 5xx / 超时；非重试类（资产无效、Schema 错误）直接标记 `FAILED_MANUAL`

---

### 模块 5：质量控制 (`qc_checker.py`)

- **模型**: `gemini-2.5-flash`（多模态文本模型）
- **输入**: 生成的海报图 + 原始产品图
- **检查项**:
  - 产品主体是否存在
  - 品牌色是否大致保留
  - Logo / 包装是否变形
  - 文字是否被裁切
  - 是否出现幻觉产品
- **结果**: 通过 → 进入上传；失败 → 用更严格的 prompt 重新生成（最多重试 2 次）；2 次仍失败 → 标记 `FAILED_MANUAL`

---

### 模块 6：微信云存储上传 (`wechat_uploader.py`)

- **方式**: CloudBase HTTP API（不依赖 Python SDK，直接 HTTP 调用，官方支持所有语言）
- **流程**:
  1. 调用 CloudBase HTTP API 获取上传凭证（`POST /storage/upload`）
  2. 用凭证直接上传图片文件
  3. 获取返回的 fileID
- **上传路径规则**: `images/<分类>/<产品名>_<YYYYMMDD>.jpg`
- **环境 ID**: `newyuxiaozhu-5g28gork4d0ed6c4`（从环境变量读取）
- **注意**: 云存储默认公开可读，如需访问控制请在云开发控制台调整安全规则

---

### 模块 7：调度、日志与告警 (`main.py`)

- **调度**: cron `0 8 * * * /usr/bin/python3 /opt/poster_bot/main.py`
- **并发**: `asyncio` 并发处理多个产品，缩短总执行时间
- **日志**: `loguru`，按天轮转，写入 `/opt/poster_bot/logs/YYYY-MM-DD.log`
- **告警**: 有任何产品最终失败，通过飞书机器人 Webhook 发送告警到工作群
- **Job Lock**: 脚本结束后删除锁文件，异常退出时锁文件保留（下次启动检测到锁则跳过或告警）

---

## 配置文件

### `.env`（严禁入库）

```env
GEMINI_API_KEY=
GEMINI_API_BASE=https://api.buxianliang.fun
STORE_NAME=浴小主
GEMINI_COPY_MODEL=gemini-3.1-pro-preview
GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_TABLE_ID=
FEISHU_WEBHOOK_URL=
WX_ENV_ID=newyuxiaozhu-5g28gork4d0ed6c4
WX_SECRET_ID=
WX_SECRET_KEY=
```

### `.env.example`（入库，值为空）

与上方相同，所有值留空，作为配置模板。

---

## 目录结构

```
poster_bot/
├── main.py                   # 入口，并发调度
├── feishu_reader.py          # 飞书读取与状态回写
├── content_generator.py      # gemini-2.5-flash 生成结构化 JSON
├── asset_processor.py        # rembg 抠图预处理
├── image_generator.py        # 图像生成（提示词 + 产品切图）
├── qc_checker.py             # 多模态质量检查
├── wechat_uploader.py        # CloudBase HTTP API 上传
├── models.py                 # Pydantic 数据模型
├── prompts/
│   ├── scheme_prompt.txt     # 方案策划 Prompt（自动生成3方案取其一）
│   └── image_prompt.txt      # 视觉翻译官 Prompt（生成图像提示词）
├── assets/
│   └── products/             # 产品素材图（不入 git）
├── .env                      # 环境变量（不入 git）
├── .env.example              # 配置模板（入库）
├── .gitignore
├── requirements.txt
├── README.md
└── logs/                     # 运行日志（不入 git）
```

---

## .gitignore 关键内容

```
.env
assets/products/
logs/
*.log
__pycache__/
*.pyc
/tmp/
```

---

## GitHub 开源

- 所有 API Key、密码、环境 ID 只从 `os.environ` 读取，代码中零硬编码
- 提供 `.env.example` 和 `README.md`（含飞书表格结构、配置步骤、cron 配置说明）
- 服务器上 `.env` 单独维护，不参与 git

---

## 部署步骤

1. GitHub 建立仓库，推送代码
2. SSH 进入服务器，`git clone <repo>` 到 `/opt/poster_bot/`
3. `pip install -r requirements.txt`
4. 配置 `/opt/poster_bot/.env`
5. 上传产品素材图到 `/opt/poster_bot/assets/products/`
6. 配置 cron：`0 8 * * * /usr/bin/python3 /opt/poster_bot/main.py`
7. 在飞书建立多维表格，填入产品数据

---

## 验证方式

- **分步测试**: 每个模块可单独运行并打印结果
- **集成测试**: 手动 `python main.py`，检查日志、飞书状态列、云存储新增图片
- **定时验证**: 次日 08:00 后检查日志与飞书表格
- **QC 验证**: 检查 `qc_checker` 的通过/重试记录，确认产品主体保留正确

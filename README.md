# 浴小主 - 每日自动海报生成系统

自动从飞书多维表格读取产品信息，利用 Gemini AI 生成文案与海报图片，上传至微信小程序云存储。全流程无需人工介入，每天定时自动运行。

## 系统架构

```
cron (每天 08:00)
└── main.py
    ├── 飞书多维表格 → 读取待处理产品
    ├── gemini-3.1-pro-preview → 生成文案方案 + 图像提示词
    ├── rembg → 产品图抠图预处理
    ├── gemini-3-pro-image-preview → 生成海报（提示词 + 产品图融合）
    ├── 多模态 QC → 验证产品主体/品牌色/Logo 完整性
    ├── 微信云存储 → 上传至对应分类
    └── 飞书回写状态 + 失败告警
```

## 状态流转

```
PENDING → COPY_OK → IMAGE_OK → UPLOAD_OK → DONE
                                          → FAILED_RETRYABLE（自动重试）
                                          → FAILED_MANUAL（需人工处理）
```

## 项目结构

```
├── main.py                   # 入口，asyncio 并发调度
├── models.py                 # Pydantic 数据模型
├── feishu_reader.py          # 飞书多维表格读取与状态回写
├── content_generator.py      # 两阶段文案生成（方案策划 → 图像提示词）
├── asset_processor.py        # rembg 抠图 + 缩放 + base64 编码
├── image_generator.py        # Gemini 图像生成（产品图融合）
├── qc_checker.py             # 多模态质量检查
├── wechat_uploader.py        # 微信云存储 HTTP API 上传
├── prompts/
│   ├── scheme_prompt.txt     # 方案策划 Prompt 模板
│   └── image_prompt.txt      # 视觉翻译官 Prompt 模板
├── assets/products/          # 产品素材图（不入 git）
├── logs/                     # 运行日志（不入 git）
├── tests/                    # pytest 单元测试
├── .env.example              # 环境变量模板
└── requirements.txt
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/gongjianian/yuzhuzhu-poster-bot.git
cd yuzhuzhu-poster-bot
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 填入以下凭证：

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `GEMINI_API_KEY` | Gemini API 密钥 | 自建 API 服务 |
| `GEMINI_API_BASE` | API 地址 | 如 `https://api.example.com/v1` |
| `FEISHU_APP_ID` | 飞书应用 ID | 飞书开放平台 → 创建企业自建应用 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 同上 |
| `FEISHU_APP_TOKEN` | 多维表格 App Token | 飞书多维表格 URL 中获取 |
| `FEISHU_TABLE_ID` | 数据表 ID | 飞书多维表格 URL 中获取 |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook | 飞书群设置 → 群机器人 → 自定义机器人 |
| `WX_APPID` | 微信小程序 AppID | 微信公众平台 → 设置 → 基本设置 |
| `WX_APPSECRET` | 微信小程序 AppSecret | 同上 |
| `WX_ENV_ID` | 云开发环境 ID | 微信云开发控制台 |

### 4. 配置飞书多维表格

创建多维表格，字段如下：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 产品名称 | 文本 | 产品名 |
| 成分 | 文本 | 核心成分 |
| 功效 | 文本 | 产品卖点 |
| 小红书话题 | 文本 | 可选，创意灵感 |
| 分类 | 单选 | 对应云存储目录 |
| 海报风格 | 单选 | 如：极简扁平 / 3D C4D / 新中式插画 |
| 品牌色 | 文本 | 如：#FF6B6B |
| 产品素材图文件名 | 文本 | 服务器上的文件名 |
| 状态 | 单选 | PENDING / COPY_OK / IMAGE_OK / UPLOAD_OK / DONE / FAILED_RETRYABLE / FAILED_MANUAL |
| 幂等键 | 文本 | 防重复生成 |
| 云存储fileID | 文本 | 上传成功后自动写入 |
| 最后生成时间 | 日期 | 自动写入 |

### 5. 上传产品素材图

```bash
mkdir -p assets/products
# 将产品图片放入 assets/products/ 目录
# 文件名需与飞书表格中「产品素材图文件名」字段一致
```

### 6. 手动运行测试

```bash
# 运行单元测试
python -m pytest tests/ -v

# 手动执行一次完整流程
python main.py
```

### 7. 配置定时任务

```bash
crontab -e
# 添加以下行：
0 8 * * * cd /opt/poster_bot && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

## 运行机制

- **并发处理**：asyncio 并发处理多个产品，缩短总执行时间
- **QC 质量检查**：生成后自动用多模态模型验证产品主体、品牌色、Logo 是否完整，失败最多重试 2 次
- **智能重试**：所有外部 API 调用使用 tenacity 指数退避重试
- **Job Lock**：防止 cron 重复触发
- **日志轮转**：loguru 按天轮转，保留 30 天
- **失败告警**：通过飞书机器人 Webhook 实时通知

## 安全说明

- 所有密钥仅通过 `.env` 配置，代码中零硬编码
- `.env` 和 `assets/products/` 已被 `.gitignore` 排除
- 仓库中仅提供 `.env.example` 作为配置模板

## 技术栈

- Python 3.11+
- Gemini API (gemini-3.1-pro-preview / gemini-3-pro-image-preview)
- 飞书多维表格 (lark-oapi)
- 微信云存储 (CloudBase HTTP API)
- rembg (深度学习抠图)
- Pydantic / tenacity / loguru / asyncio

## License

MIT

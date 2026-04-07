# 浴小主 - 每日自动海报生成系统

自动从飞书多维表格读取产品信息，利用 Gemini AI 生成文案与海报图片，上传至微信小程序云存储。配备完整的 Web 控制面板用于任务管理、实时监控和日志查询。全流程支持定时自动运行与手动触发。

## 核心功能

- **全自动管线**：飞书 → Gemini 文案+图像 → QC 质检 → 微信云存储
- **Web 控制面板**：FastAPI + Vue 3 后台，任务管理、实时日志、健康监测、统计仪表盘
- **双入口触发**：cron 定时执行 + 面板手动触发（共享 asyncio.Lock 防竞态）
- **JWT 鉴权**：登录保护，WebSocket 实时日志流
- **执行历史**：SQLite 持久化每次执行的详情、耗时、QC 结果

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│            FastAPI (uvicorn, 常驻进程)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  /api/*  REST endpoints + WebSocket              │   │
│  │  /       Vue 3 SPA (Element Plus)                │   │
│  └──────────────────────────────────────────────────┘   │
│                         ↓                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  pipeline.py (asyncio.Lock 统一管线入口)          │   │
│  │    1. 飞书 → fetch_pending_records               │   │
│  │    2. gemini-3.1-pro-preview → 文案+图像prompt   │   │
│  │    3. rembg → 产品图抠图                          │   │
│  │    4. gemini-3-pro-image-preview → 海报生成     │   │
│  │    5. 多模态 QC → 主体/品牌色/Logo 验证           │   │
│  │    6. 微信云存储上传                              │   │
│  │    7. 飞书状态回写 + SQLite 记录 + 飞书告警       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ↑                                    ↑
         │                                    │
   cron (每天 08:00)                   用户手动点击
   curl HTTP POST                        (浏览器)
```

## 状态流转

```
PENDING → COPY_OK → IMAGE_OK → UPLOAD_OK → DONE
                                          → FAILED_RETRYABLE（自动重试）
                                          → FAILED_MANUAL（需人工处理）
```

## 项目结构

```
├── main.py                       # uvicorn 启动入口
├── pipeline.py                   # 核心管线（asyncio.Lock）
├── models.py                     # Pydantic 数据模型
├── feishu_reader.py              # 飞书多维表格读取与状态回写
├── content_generator.py          # 两阶段文案生成
├── asset_processor.py            # rembg 抠图 + base64
├── image_generator.py            # Gemini 图像生成
├── qc_checker.py                 # 多模态质量检查
├── wechat_uploader.py            # 微信云存储 HTTP API
├── prompts/                      # Gemini Prompt 模板
│
├── dashboard/                    # Web 控制面板后端
│   ├── app.py                    # FastAPI 应用工厂
│   ├── config.py                 # pydantic-settings 配置
│   ├── auth.py                   # JWT 认证
│   ├── database.py               # SQLAlchemy ORM
│   ├── db_models.py              # RunRecord / DailyStats
│   ├── schemas.py                # API 响应 schemas
│   ├── websocket_manager.py      # WebSocket 日志广播
│   ├── routers/
│   │   ├── auth_router.py        # 登录/刷新
│   │   ├── tasks_router.py       # 任务列表/触发
│   │   ├── runs_router.py        # 执行记录查询
│   │   ├── stats_router.py       # 统计聚合
│   │   ├── logs_router.py        # 日志查询 + WebSocket
│   │   ├── health_router.py      # 健康检查
│   │   └── pipeline_router.py    # 管线触发
│   └── services/                 # 业务逻辑层
│
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── views/                # 5 个业务页面
│   │   ├── components/           # StatsCard/TrendChart/LogStream/...
│   │   ├── api/                  # Axios 客户端
│   │   ├── stores/               # Pinia
│   │   ├── router/               # 路由守卫
│   │   └── layouts/              # 后台布局
│   └── vite.config.ts
│
├── static/                       # 前端构建产物（FastAPI 托管）
├── deploy/                       # 部署配置
│   ├── nginx.conf                # Nginx 反向代理
│   ├── poster-dashboard.service  # systemd
│   ├── setup.sh                  # 一键部署脚本
│   └── cron_trigger.sh           # cron HTTP 触发
│
├── tests/                        # 63 个单元+集成测试
├── docs/superpowers/             # 设计文档和实现计划
└── requirements.txt
```

## Web 控制面板

访问 `http://<服务器>/` 登录后可使用以下功能：

| 页面 | 功能 |
|------|------|
| **概览仪表盘** | 今日总数/成功/失败/成功率 + 7 天趋势图 + 最近 5 条执行记录 |
| **任务管理** | 飞书产品列表、状态筛选、海报预览、单个/批量重新生成 |
| **执行记录** | 历史执行详情（耗时、QC 结果、错误信息）、分页、筛选、drawer 详情 |
| **系统日志** | WebSocket 实时日志流 + 历史日志按日期/关键词/级别查询 |
| **健康监测** | 飞书 / Gemini / 微信 API 状态灯 + 磁盘空间，60 秒自动刷新 |

### API 端点

```
POST   /api/auth/login              登录
POST   /api/auth/refresh            刷新 token
GET    /api/stats/summary           今日统计
GET    /api/stats/trend              N 天趋势
GET    /api/tasks                   任务列表（来自飞书）
POST   /api/tasks/{id}/trigger      手动触发单个
POST   /api/tasks/batch-trigger     批量触发
GET    /api/runs                   执行记录分页
GET    /api/runs/{run_id}          执行详情
GET    /api/logs                   历史日志
WS     /api/logs/stream            实时日志流（?token=xxx）
GET    /api/health                 健康检查
POST   /api/pipeline/run            触发完整批处理（cron 调这个）
GET    /api/docs                   Swagger UI
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/gongjianian/yuzhuzhu-poster-bot.git
cd yuzhuzhu-poster-bot
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 构建前端（首次部署）

```bash
cd frontend
npm install
npm run build   # 输出到 ../static/
cd ..
```

### 4. 配置环境变量

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
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook | 飞书群设置 → 自定义机器人 |
| `WX_APPID` | 微信小程序 AppID | 微信公众平台 |
| `WX_APPSECRET` | 微信小程序 AppSecret | 同上 |
| `WX_ENV_ID` | 云开发环境 ID | 微信云开发控制台 |
| `DASHBOARD_SECRET_KEY` | JWT 签名密钥 | 随机字符串（建议 openssl rand -hex 32）|
| `DASHBOARD_ADMIN_USER` | 管理员用户名 | 自定义 |
| `DASHBOARD_ADMIN_PASSWORD` | 管理员密码 | 自定义强密码 |

### 5. 配置飞书多维表格

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

### 6. 上传产品素材图

```bash
mkdir -p assets/products
# 将产品图片放入 assets/products/ 目录
# 文件名需与飞书表格中「产品素材图文件名」字段一致
```

### 7. 启动服务

```bash
# 开发模式（前端 dev server 独立）
cd frontend && npm run dev      # 端口 5173
# 另开终端
python main.py                  # 端口 8000

# 生产模式（前端打包后由 FastAPI 托管）
cd frontend && npm run build
cd .. && python main.py
# 访问 http://localhost:8000
```

### 8. 服务器部署（Ubuntu）

```bash
sudo bash deploy/setup.sh
```

该脚本会：
- 安装 Python venv、pip、Nginx
- 创建虚拟环境并安装依赖
- 初始化数据目录
- 配置 Nginx 反向代理（含 WebSocket 升级）
- 注册 systemd 守护进程并启动

### 9. 配置定时任务

```bash
crontab -e
# 添加以下行（通过 HTTP 触发，共享 FastAPI 进程的锁）：
0 8 * * * /opt/poster_bot/deploy/cron_trigger.sh >> /opt/poster_bot/logs/cron.log 2>&1
```

## 测试

```bash
pytest tests/ -v
# 63 tests passed
```

## 运行机制

- **统一管线入口**：cron 和 Web 手动触发共享 `asyncio.Lock`，彻底消除竞态
- **QC 质量检查**：生成后自动用多模态模型验证产品主体、品牌色、Logo 是否完整，失败最多重试 2 次
- **智能重试**：所有外部 API 调用使用 tenacity 指数退避重试
- **日志轮转**：loguru 按天轮转，保留 30 天
- **失败告警**：飞书群机器人 Webhook 实时通知
- **执行历史**：SQLite 持久化每次执行的完整详情，供面板查询和统计
- **WebSocket 实时日志**：loguru sink 广播到所有已鉴权的 WebSocket 连接

## 安全说明

- 所有密钥仅通过 `.env` 配置，代码中零硬编码
- JWT 鉴权所有 API + WebSocket 端点
- 路径穿越防护（日志文件按严格日期格式校验）
- CORS 白名单配置
- `.env` / `assets/products/` / `data/` 已被 `.gitignore` 排除
- 建议生产环境配合腾讯云安全组限 IP 访问

## 技术栈

### 后端
- Python 3.11+ / FastAPI / uvicorn
- SQLAlchemy 2.0 + SQLite
- PyJWT + passlib (pbkdf2_sha256)
- loguru / pydantic / tenacity / asyncio
- Gemini API (gemini-3.1-pro-preview / gemini-3-pro-image-preview)
- 飞书多维表格 (lark-oapi)
- 微信云存储 (CloudBase HTTP API)
- rembg (深度学习抠图)

### 前端
- Vue 3 + TypeScript + Vite
- Element Plus（中文语言包）
- Pinia + Vue Router 4
- Axios（JWT 拦截器）
- ECharts / vue-echarts
- WebSocket

## 开发流程

本项目由 Claude + Codex + Gemini 协作开发：

- **Claude**：架构设计、代码审核、多 AI 协调
- **Codex**：后端基础设施（FastAPI、SQLite、JWT、管线重构、部署）
- **Gemini**：前端 UI（Vue 3、Element Plus、所有业务页面）

详细实现计划见 [`docs/superpowers/plans/`](docs/superpowers/plans/)。

## License

MIT

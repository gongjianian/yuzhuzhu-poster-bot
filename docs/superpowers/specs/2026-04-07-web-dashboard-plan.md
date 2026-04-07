# Web 控制面板规划书 (Web Dashboard Plan)

## 1. 架构与技术选型
- **后端架构**: FastAPI
  - **原因**: 系统现有的核心逻辑基于 Python `asyncio`。FastAPI 原生支持异步，能无缝复用 `models.py` 的 Pydantic 模型以及 `feishu_reader`、`content_generator` 等各个业务模块，学习成本低且性能极佳。
- **前端架构**: Vue 3 + Vite + Element Plus (或 React + Tailwind CSS)
  - **原因**: 极其适合快速搭建后台管理系统，提供丰富的表格、图表、和日志弹窗组件。
  - **备选方案**: 若缺乏前端资源，可采用纯 Python 方案 **NiceGUI** 或 **Streamlit**，直接在后端构建并渲染交互式 Web UI。
- **数据存储**: 
  - **核心业务数据**：继续以**飞书多维表格**为主（SSOT）。
  - **缓存/配置数据**：引入 **SQLite**，用于缓存前端所需的飞书列表状态以提升加载速度，同时存储面板自身的操作日志。

## 2. 页面结构设计 (UI/UX)
控制面板采用标准的中后台管理布局（左侧导航栏 + 右侧内容展示区）：

1. **📊 概览仪表盘 (Dashboard)**
   - **核心指标**: 今日任务总数、成功数、失败数、成功率。
   - **图表展示**: 近 7 天海报生成数量与 API 耗时的趋势图。
   - **快捷状态**: 当前系统时间、下一个 Cron 任务执行时间倒计时。
2. **📋 任务与海报管理 (Task Management)**
   - **数据列表**: 分页展示从飞书拉取的产品列表。字段包括：产品 ID、产品名称、生成状态（成功/进行中/失败）、更新时间。
   - **海报预览**: 支持点击某行弹窗展示已生成的图片预览（直接调用 `wechat_uploader` 传回的云存储链接，或读取 `assets/` 下的本地缓存图）。
   - **操作区**: 针对失败任务提供单个“重新生成”的触发按钮；支持批量选中执行重试。
3. **📝 系统日志查询 (Log Viewer)**
   - **实时日志流**: 使用 WebSocket 实时尾随（Tail）输出当天的 `loguru` 运行日志。
   - **历史查询**: 支持通过日期选择器加载过去 30 天轮转的日志文件，提供全文本搜索和日志级别（INFO/ERROR/WARNING）高亮与过滤功能。
4. **🩺 系统健康监测 (Health Check)**
   - **状态指示灯**: 
     - 飞书 API 鉴权与连通性检测
     - Gemini API 连通性检测
     - 微信小程序云环境访问状态检测
     - 腾讯云 Ubuntu 服务器磁盘剩余空间监控（防止日志或图片堆积打满磁盘）。

## 3. API 接口设计 (FastAPI)

### 核心 REST API 与 WebSocket 端点
- `GET /api/stats/daily` -> 获取当日生成的统计数据和成功率。
- `GET /api/tasks` -> 读取飞书产品列表（带服务端缓存），支持基于状态的快速过滤。
- `POST /api/tasks/{product_id}/trigger` -> 手动触发单个海报生成管线。
  - **实现逻辑**：调用现有系统抽象出的 `process_single_product` 函数，并复用全局的 Job Lock，防止与 Cron 任务发生冲突。
- `GET /api/logs` -> 接收 `date` 参数，读取并返回对应的 `loguru` 文件文本内容。
- `WS /api/logs/stream` -> 建立 WebSocket 连接，持续下发最新的系统日志。
- `GET /api/health` -> 并发检查飞书、Gemini 和微信云组件的存活状态并返回诊断报告。

## 4. 实施与开发计划

- **第一阶段：后端基础设施与日志系统 (1-2 天)**
  - 引入 FastAPI 依赖，搭建基本的路由结构。
  - 编写 `/api/logs` 接口，直接解析已存在的 `logs/` 目录下的按天轮转日志。
  - 编写 `/api/health` 接口，复用现有组件的测试凭证逻辑。
- **第二阶段：核心调度与现有系统整合 (2 天)**
  - 改造 `main.py`，将批处理调度解耦，暴露出可供 HTTP 请求调用的 `process_single_product(product_id)` 方法。
  - 实现 `/api/tasks/{product_id}/trigger`，确保手动触发和定时 Cron 触发使用同一套分布式锁/文件锁（避免竞态条件）。
- **第三阶段：前端界面开发 (3 天)**
  - 初始化 Vue 3 基础工程，集成 Element Plus UI 框架。
  - 依次开发 Dashboard（仪表盘）、任务列表页（含图片预览组件）和日志浏览器。
  - 对接后端所有的 REST API 和 WebSocket 流。
- **第四阶段：生产部署与上线 (1 天)**
  - 使用 `uvicorn` 或 `gunicorn` 在腾讯云服务器上守护进程运行 FastAPI 服务。
  - 配置 Nginx 反向代理，绑定域名与 SSL 证书。
  - 进行全面测试，确保面板操作正常且未对原本每天 08:00 的自动化任务造成副作用。
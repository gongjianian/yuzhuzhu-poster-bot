# 分类海报仪表板 - 设计文档

## 目标

在控制面板新增「分类海报」页面，让用户：
1. 实时看到正在执行的流水线走到了哪一步
2. 按日期浏览每个分类生成了哪些海报

## 数据层

### 新表 `category_run_records`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | 自增主键 |
| batch_id | String(64) index | 批次 ID（同一次触发共享，格式 `20260410_203744`） |
| category_id | String(64) | 症状分类 ID，如 `cat_pw_jstl` |
| category_name | String(100) | 如 `积食停滞类` |
| level1_name | String(100) | 一级分类，如 `脾胃系列` |
| product_line | String(50) | 如 `五行泡浴` |
| products_json | Text | JSON 数组，产品名列表 |
| status | String(20) index | PENDING / MATCHING / RUNNING / DONE / FAILED |
| step | String(20) | 当前步骤：matching / content / image / uploading / registering / done |
| headline | String(500) | 生成的主标题 |
| cloud_file_id | String(500) | 微信云文件 ID |
| material_id | String(200) | 小程序 materials 集合 doc ID |
| error_msg | Text | 失败原因 |
| duration_seconds | Float nullable | 耗时秒 |
| started_at | DateTime | 开始时间 |
| finished_at | DateTime nullable | 结束时间 |

### Pipeline 改造

`category_pipeline.py` 现有逻辑不变，在关键节点插入 DB 写入：
- 触发时：生成 `batch_id`，为每个 category 创建 PENDING 行（step 和 products 暂未知）
- `match_products_to_symptom` 返回后：更新 products_json、product_line，创建具体任务行（RUNNING）
- 每个步骤开始前：更新 `step` 字段（content → image → uploading → registering）
- 步骤完成/失败：更新 `status`、`headline`、`material_id`、`error_msg`、`finished_at`

为了不让 pipeline 直接依赖 dashboard 的 DB 模块，定义一个轻量回调接口 `PipelineProgressWriter`，pipeline 调用它上报进度，dashboard 侧实现写入。

## 后端 API

### 新路由 `dashboard/routers/category_runs_router.py`

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/api/category-runs` | 查询批次列表（支持 `?date=YYYY-MM-DD`） |
| GET | `/api/category-runs/current` | 获取正在运行的批次所有任务（供前端轮询） |
| GET | `/api/category-runs/{batch_id}` | 获取指定批次所有任务详情 |
| POST | `/api/category-runs/trigger` | 触发分类流水线（替代原 tasks_router 里的 trigger） |
| POST | `/api/category-runs/stop` | 终止当前运行（设置取消标志 + 重启不需要） |

### 响应格式

**批次列表**（GET /api/category-runs）：
```json
{
  "items": [
    {
      "batch_id": "20260410_203744",
      "started_at": "2026-04-10T20:37:44",
      "total": 15,
      "done": 12,
      "failed": 1,
      "running": 2
    }
  ]
}
```

**批次详情**（GET /api/category-runs/{batch_id} 或 /current）：
```json
{
  "batch_id": "20260410_203744",
  "status": "running",
  "tasks": [
    {
      "category_name": "积食停滞类",
      "product_line": "五行泡浴",
      "products": ["鸡内金泡浴", "金银花泡浴"],
      "status": "RUNNING",
      "step": "image",
      "headline": "我家崽吃不下，肚子总鼓鼓的",
      "material_id": "",
      "duration_seconds": null,
      "started_at": "2026-04-10T20:38:00"
    }
  ]
}
```

## 前端

### 新页面 `CategoryRunsView.vue`

导航位置：侧边栏「分类海报」图标，放在「产品任务」和「执行记录」之间。

**页面布局（从上到下）：**

1. **操作栏**：「立即触发」按钮 + 「终止」按钮（仅运行时可点）+ 自动刷新开关
2. **当前进度面板**（仅运行时显示）：
   - 顶部进度条：X/Y 完成
   - 表格：每行一个任务（分类名 | 产品线 | 步骤指示器 | 状态标签 | 标题 | 耗时）
   - 步骤指示器：5 个圆点 + 连线（匹配 → 文案 → 生图 → 上传 → 注册），当前步骤高亮
   - 3 秒轮询 `/api/category-runs/current`
3. **历史记录**（始终显示）：
   - 日期选择器（默认今天）
   - 批次卡片列表，每个批次展开后是同样的表格

### 新 API 模块 `frontend/src/api/categoryRuns.ts`

封装上述 5 个 API 调用。

### 路由

`/category-runs` → `CategoryRunsView.vue`

## 技术要点

- **轮询而非 WebSocket**：3 秒 setInterval，页面不可见时暂停（`document.hidden`）
- **Pipeline 取消**：用 `asyncio.Event` 标志位，pipeline 每个任务前检查，设置后当前任务完成即停止
- **DB 写入非阻塞**：pipeline 里用 `asyncio.to_thread` 包裹 DB 操作
- **现有 tasks_router 里的 category-pipeline/trigger 保留**，新 API 并行存在，后续可废弃旧的

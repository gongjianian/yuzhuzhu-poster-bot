# 浴小主 - 每日自动海报生成系统

## 项目概述
自动从飞书多维表格读取产品信息 → Gemini 生成文案+图像 → 上传微信小程序云存储。部署在腾讯云 Ubuntu 服务器，cron 每天 08:00 自动执行。

## 关键配置
- API 地址：https://api.buxianliang.fun/v1
- 文案模型：gemini-3.1-pro-preview
- 图像模型：gemini-3-pro-image-preview
- 品牌名：浴小主
- 微信云开发环境：newyuxiaozhu-5g28gork4d0ed6c4
- 服务器：49.235.145.49 (Ubuntu)
- GitHub：https://github.com/gongjianian/yuzhuzhu-poster-bot

## 已完成 (2026-04-06)

### 设计阶段
- [x] 需求分析与方案讨论
- [x] 设计文档 v2（整合 Gemini + Codex 审阅建议）→ docs/superpowers/specs/
- [x] 详细实现计划（12 个 Task）→ docs/superpowers/plans/

### 开发阶段
- [x] Task 1: 项目脚手架（requirements.txt, .env.example, .gitignore）
- [x] Task 2: Pydantic 数据模型（models.py）
- [x] Task 3: 飞书数据读取与状态回写（feishu_reader.py）
- [x] Task 4: 产品图预处理 rembg 抠图（asset_processor.py）
- [x] Task 5: Prompt 模板文件（scheme_prompt.txt, image_prompt.txt）
- [x] Task 6: 两阶段内容生成器（content_generator.py）
- [x] Task 7: 图像生成器（image_generator.py）
- [x] Task 8: 多模态 QC 质量检查（qc_checker.py）
- [x] Task 9: 微信云存储上传（wechat_uploader.py）
- [x] Task 10: 主调度器 asyncio + Job Lock + 日志 + 告警（main.py）

### 审核阶段
- [x] Claude 审核全部代码，修复 Gemini 的 8 个问题（环境变量、函数名、Prompt 重写等）
- [x] Codex 审查代码，修复 4 个问题（UPLOAD_OK 状态、告警容错、上传校验、.gitignore）
- [x] 全部 32 个单元测试通过
- [x] 推送到 GitHub

### 分工记录
- Codex：基础设施层（models, feishu, asset, image_gen, uploader, main）
- Gemini：创意内容层（prompts, content_generator, qc_checker）
- Claude：架构设计 + 代码审核 + 修复 + 协调

## 未完成

### Task 11: 服务器部署
- [ ] SSH 进入服务器，git clone 到 /opt/poster_bot/
- [ ] pip install -r requirements.txt
- [ ] 配置 /opt/poster_bot/.env（填入真实密钥）
- [ ] 上传产品素材图到 /opt/poster_bot/assets/products/

### Task 12: 集成测试与定时任务
- [ ] 手动运行 python main.py 验证完整流程
- [ ] 检查飞书状态列、云存储新增图片
- [ ] 配置 cron：0 8 * * * cd /opt/poster_bot && python3 main.py
- [ ] 次日验证定时任务

### 待用户准备的凭证
- [ ] 飞书：创建企业自建应用 → App ID + App Secret
- [ ] 飞书：多维表格 App Token + Table ID
- [ ] 飞书：群机器人 Webhook URL
- [ ] 微信：小程序 AppID + AppSecret（管理后台获取）
- [ ] 在飞书创建多维表格并填入产品数据

## 开发规范
- 所有密钥只通过 .env 读取，代码中零硬编码
- .env 严禁入 git
- 测试：pytest tests/ -v
- 日志：loguru 按天轮转

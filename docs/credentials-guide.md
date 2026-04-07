# 凭证准备指南

部署前需要准备以下凭证，填入服务器 `/opt/poster_bot/.env` 文件。

## 检查清单

- [ ] **飞书应用** — App ID + App Secret
- [ ] **飞书多维表格** — App Token + Table ID
- [ ] **飞书群机器人** — Webhook URL
- [ ] **微信小程序** — AppID + AppSecret
- [ ] **Gemini API** — API Key（已有 api.buxianliang.fun 代理）
- [ ] **控制面板** — SECRET_KEY + 管理员密码

---

## 1. 飞书企业自建应用

### 1.1 创建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)
2. 登录后点击 **「创建企业自建应用」**
3. 填写：
   - **应用名称**：浴小主海报机器人
   - **应用描述**：自动化海报生成系统
   - **应用图标**：随便传一个
4. 创建成功后进入应用详情页

### 1.2 获取 App ID / App Secret

- 在 **「凭证与基础信息」** 页面看到：
  - `App ID` → 填入 `.env` 的 `FEISHU_APP_ID`
  - `App Secret` → 填入 `.env` 的 `FEISHU_APP_SECRET`

⚠️ **注意**：App Secret 只显示一次，记得保存。

### 1.3 开通权限

在 **「权限管理」** 页面，搜索并添加以下权限：

| 权限 | 说明 |
|------|------|
| `bitable:app` | 查看、编辑多维表格 |
| `bitable:app:readonly` | 查看多维表格 |
| `im:message` | 发送群消息（告警用） |

添加后点击 **「创建版本并发布」**，提交审核（自建应用一般秒审）。

### 1.4 应用发布

**「版本管理与发布」** → 创建版本 → 填写版本说明 → 发布 → 管理员审批。

发布成功后应用才能实际调用 API。

---

## 2. 飞书多维表格

### 2.1 创建多维表格

1. 打开飞书 → 新建 → **「多维表格」**
2. 表格命名：浴小主产品池

### 2.2 配置字段

按以下字段创建（必须严格命名）：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| 产品名称 | 文本 | ✅ | 如「舒缓植萃沐浴露」 |
| 成分 | 文本 | ✅ | 核心成分，如「积雪草、洋甘菊」 |
| 功效 | 文本 | ✅ | 卖点描述 |
| 小红书话题 | 文本 | ❌ | 可选创意灵感 |
| 分类 | 单选 | ✅ | 沐浴 / 洗发 / 护肤 / ... |
| 海报风格 | 单选 | ✅ | 极简扁平 / 3D C4D / 新中式插画 / ... |
| 品牌色 | 文本 | ✅ | 如 `#FF6B6B` |
| 产品素材图文件名 | 文本 | ✅ | 服务器上的文件名，如 `shuhuan.png` |
| 状态 | 单选 | ✅ | **选项：** PENDING / COPY_OK / IMAGE_OK / UPLOAD_OK / DONE / FAILED_RETRYABLE / FAILED_MANUAL |
| 幂等键 | 文本 | ❌ | 防重复生成 |
| 云存储fileID | 文本 | ❌ | 自动回写 |
| 最后生成时间 | 日期 | ❌ | 自动回写 |
| 错误信息 | 文本 | ❌ | 自动回写 |

### 2.3 获取 App Token 和 Table ID

打开多维表格后，看浏览器地址栏：

```
https://xxx.feishu.cn/base/【App Token】?table=【Table ID】&view=xxx
```

举例：
```
https://yuxiaozhu.feishu.cn/base/bascnCMaa5t4yZxK8V1Qsqi6j1g?table=tblYj3rLNKq8WxN2&view=vewK9Bcz3F
                                  └─────── App Token ───────┘        └── Table ID ──┘
```

- `App Token`（`base/` 后面那一串）→ 填 `FEISHU_APP_TOKEN`
- `Table ID`（`table=` 后面那一串）→ 填 `FEISHU_TABLE_ID`

### 2.4 给应用授权表格

在多维表格页面点击右上角 **「...」** → **「高级权限」** → 添加应用：搜索你刚才创建的应用名称 → 授予「可编辑」权限。

⚠️ **这一步非常关键**，否则应用读不到表格数据。

---

## 3. 飞书群机器人 Webhook

用于发送失败告警通知。

### 3.1 创建群

1. 飞书 → 新建群 → 命名「浴小主海报告警群」
2. 拉入相关人员

### 3.2 添加自定义机器人

1. 群设置（右上角齿轮）→ **「群机器人」** → **「添加机器人」**
2. 选择 **「自定义机器人」**
3. 填写：
   - **机器人名称**：海报告警助手
   - **描述**：海报生成失败时自动通知
4. 点击 **「添加」** → 复制生成的 Webhook 地址
5. 填入 `.env` 的 `FEISHU_WEBHOOK_URL`

Webhook 格式示例：
```
https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## 4. 微信小程序凭证

### 4.1 获取 AppID / AppSecret

1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 选择你的小程序
3. **「开发」 → 「开发管理」 → 「开发设置」**
4. 复制：
   - **AppID** → 填 `WX_APPID`
   - **AppSecret** → 点击「重置」→ 管理员扫码确认 → 复制 → 填 `WX_APPSECRET`

⚠️ AppSecret 只在重置时显示一次，务必保存好。

### 4.2 配置 IP 白名单（重要！）

微信云存储 API 默认不允许任意 IP 调用，需要加白名单：

1. 同一页面找到 **「IP 白名单」**
2. 点击 **「修改」**
3. 添加服务器 IP：`49.235.145.49`
4. 保存

### 4.3 云开发环境 ID

已有：`newyuxiaozhu-5g28gork4d0ed6c4`

如果需要确认：微信云开发控制台 → 环境 → 环境 ID。

---

## 5. Gemini API Key

浴小主项目使用第三方代理 `https://api.buxianliang.fun/v1`。

1. 联系代理服务提供方获取 API Key
2. 填入 `.env`：
   ```
   GEMINI_API_KEY=sk-xxxxxxxxxxxxxxxx
   GEMINI_API_BASE=https://api.buxianliang.fun/v1
   GEMINI_COPY_MODEL=gemini-3.1-pro-preview
   GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview
   ```

---

## 6. 控制面板凭证（自己生成）

### 6.1 SECRET_KEY（JWT 签名密钥）

用于加密登录 token，**必须是强随机字符串**。

**生成方式**：
```bash
# Linux/Mac
openssl rand -hex 32

# 或 Python
python -c "import secrets; print(secrets.token_hex(32))"
```

输出类似：
```
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

填入 `.env`：
```
DASHBOARD_SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

⚠️ **不要使用默认值 `dev-secret-change-me`**，否则任何人都能伪造登录。

### 6.2 管理员账号密码

```
DASHBOARD_ADMIN_USER=admin
DASHBOARD_ADMIN_PASSWORD=你的强密码
```

**密码建议：**
- 至少 12 位
- 包含大小写字母 + 数字 + 符号
- 不要用生日/姓名拼音

---

## 7. 完整 .env 示例

填写完成后，`.env` 应该长这样：

```bash
# Gemini API
GEMINI_API_KEY=sk-xxxxxxxxxxxxxxxx
GEMINI_API_BASE=https://api.buxianliang.fun/v1
GEMINI_COPY_MODEL=gemini-3.1-pro-preview
GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview
STORE_NAME=浴小主

# 飞书
FEISHU_APP_ID=cli_a1b2c3d4e5f6g7h8
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_APP_TOKEN=bascnCMaa5t4yZxK8V1Qsqi6j1g
FEISHU_TABLE_ID=tblYj3rLNKq8WxN2
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 微信云开发
WX_APPID=wxa1b2c3d4e5f6
WX_APPSECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WX_ENV_ID=newyuxiaozhu-5g28gork4d0ed6c4

# 素材
ASSETS_DIR=/opt/poster_bot/assets/products

# 控制面板
DASHBOARD_SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
DASHBOARD_ADMIN_USER=admin
DASHBOARD_ADMIN_PASSWORD=YourStrongPasswordHere!
DASHBOARD_DB_PATH=/opt/poster_bot/data/dashboard.db
DASHBOARD_PORT=8000
DASHBOARD_ALLOWED_ORIGINS=http://49.235.145.49,http://localhost:5173
```

---

## 8. 凭证安全守则

⚠️ **绝对不要**：
- ❌ 把 `.env` 文件提交到 git
- ❌ 把密钥贴到聊天群、截图、微信
- ❌ 在代码里硬编码密钥
- ❌ 使用默认的 `DASHBOARD_SECRET_KEY`
- ❌ 用弱密码（如 `admin123`）

✅ **正确做法**：
- 所有密钥只放在服务器的 `/opt/poster_bot/.env` 文件中
- 文件权限设为 `600`：`chmod 600 /opt/poster_bot/.env`
- 定期轮换密钥（至少每 6 个月）
- 密钥泄露时立即在各平台重置

---

## 9. 准备完成后的检查

填完 `.env` 后，在服务器上手动验证连通性：

```bash
cd /opt/poster_bot
source venv/bin/activate

# 测试飞书连接
python -c "from feishu_reader import fetch_pending_records; print(fetch_pending_records())"

# 测试微信连接
python -c "from wechat_uploader import get_wx_access_token; print(get_wx_access_token())"

# 测试 Gemini 连接
python -c "import os; from openai import OpenAI; c = OpenAI(api_key=os.getenv('GEMINI_API_KEY'), base_url=os.getenv('GEMINI_API_BASE')); print(c.models.list())"
```

如果都没报错就说明凭证都配好了。

然后访问控制面板 `http://49.235.145.49/` → 健康监测页面，应该看到 4 个绿灯。

---

## 遇到问题？

| 问题 | 原因 | 解决 |
|------|------|------|
| 飞书 API 401 | 权限未发布 / 未授权表格 | 检查应用是否已发布版本 + 多维表格高级权限 |
| 飞书表格读取为空 | 字段名不匹配 | 严格按表格字段名，特别是「状态」单选 |
| 微信云存储 403 | IP 白名单没加 | 公众平台添加服务器 IP |
| Gemini 401 | API Key 错 | 联系代理商确认 key |
| 面板 401 | SECRET_KEY 改了但 token 还在缓存 | 浏览器清 localStorage 重新登录 |

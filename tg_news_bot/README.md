# Telegram 新闻播报机器人

一个自动化的 Telegram 新闻播报机器人，可以从指定频道采集消息，使用 AI 进行分类和摘要，并推送到目标频道。

## 功能特点

- \U0001f4e1 **自动采集**：使用 Telethon 从指定频道/群组读取最新消息
- \U0001f916 **智能分类**：结合规则引擎和 AI 对消息进行自动分类（政治/科技/游戏/财经/社会/其他）
- \U0001f4dd **智能摘要**：AI 自动生成一句话摘要
- \u26a1 **实时推送**：高置信度消息即时推送为快讯
- \U0001f4f0 **每日日报**：每天固定时间生成分类汇总日报
- \U0001f4be **去重存储**：SQLite 数据库存储，自动去重
- \U0001f504 **工程化**：完整的错误处理、日志记录、定时任务

## 项目结构

```
tg_news_bot/
├── app.py              # 程序入口
├── config.py           # 配置管理
├── db.py               # 数据库封装
├── collector.py        # Telethon 采集模块
├── classifier.py       # 规则 + AI 分类模块
├── publisher.py        # Bot 发布模块
├── scheduler.py        # 定时任务调度
├── templates.py        # 消息模板
├── requirements.txt    # 依赖列表
├── .env.example        # 配置示例
├── README.md           # 说明文档
├── logs/               # 日志目录
└── news.db             # SQLite 数据库（运行后生成）
```

## 快速开始

### 1. 环境要求

- Python 3.9+（推荐 3.11+）
- Telegram 账号
- AI 分类 Key（可选，二选一）：
  - Cursor API Key（使用 Cursor 订阅的模型，从 [Cursor Dashboard](https://cursor.com/dashboard/api) 获取）
  - OpenAI 或任何 OpenAI 兼容 API 的 Key（OpenAI / DeepSeek / OpenRouter / 本地 Ollama 等）

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

#### 快速配置（推荐）

使用配置向导自动生成 `.env` 文件：

```bash
python3 setup_guide.py
```

按照提示输入配置信息，向导会自动生成 `.env` 文件。

#### 手动配置

#### 3.1 获取 Telethon API 凭证

1. 访问 https://my.telegram.org/apps
2. 使用你的 Telegram 账号登录
3. 创建一个新的应用
4. 记录 `api_id` 和 `api_hash`

#### 3.2 创建 Telegram Bot

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新 bot
3. 按提示设置 bot 名称和 username
4. 记录 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

#### 3.3 获取目标频道 ID

**方法一：使用 @userinfobot**

1. 在 Telegram 中搜索 `@userinfobot`
2. 将 bot 添加到你的目标频道
3. 在频道中发送任意消息
4. @userinfobot 会回复频道 ID（格式：`-1001234567890`）

**方法二：使用代码获取**

```python
# 创建一个临时脚本 get_chat_id.py
from telegram import Bot
import asyncio

async def get_chat_id():
    bot = Bot(token='YOUR_BOT_TOKEN')
    updates = await bot.get_updates()
    for update in updates:
        print(update)

asyncio.run(get_chat_id())
```

**重要提示：**
- 频道 ID 必须是负数（如 `-1001234567890`）
- 必须将 bot 添加为频道管理员
- bot 需要有发送消息的权限

#### 3.4 配置文件

```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 文件
nano .env  # 或使用你喜欢的编辑器
```

必填配置项：

```env
# Telethon 配置
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_PHONE=+886912345678  # 首次登录需要

# 采集源（逗号分隔）
SOURCE_CHANNELS=@channel1,@channel2

# Bot 配置
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TARGET_CHAT_ID=-1001234567890

# AI 配置（可选，两种后端二选一）
# 方式一：Cursor SDK（优先级更高）
CURSOR_API_KEY=your-cursor-api-key
CURSOR_MODEL=composer-2.5

# 方式二：OpenAI 兼容 API
# OPENAI_API_KEY=sk-your-key
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4o-mini
```

### 4. 验证配置

在首次运行前，建议使用配置验证工具检查配置是否正确：

```bash
python3 verify_config.py
```

验证工具会检查：
- Telethon API 配置
- Bot Token 和连接
- 目标频道访问权限
- AI 配置（如果启用）

如果验证失败，工具会提供详细的错误信息和解决方法。

### 5. 运行

#### 首次运行

首次运行需要登录 Telethon：

```bash
python app.py
```

系统会提示：
1. 输入手机号（如已在 .env 中配置则跳过）
2. 输入验证码（Telegram 会发送到你的手机）
3. 如果启用了两步验证，输入密码

登录成功后会生成 session 文件，之后运行不再需要验证。

#### 日常运行

```bash
python app.py
```

程序会：
1. 立即执行一次采集和发布
2. 启动定时任务（默认每 10 分钟采集一次）
3. 每天固定时间发布日报

#### 后台运行（Linux）

使用 `screen` 或 `tmux`：

```bash
# 使用 screen
screen -S tg_news_bot
python app.py
# 按 Ctrl+A 然后按 D 离开

# 重新连接
screen -r tg_news_bot

# 或使用 tmux
tmux new -s tg_news_bot
python app.py
# 按 Ctrl+B 然后按 D 离开

# 重新连接
tmux attach -t tg_news_bot
```

使用 `systemd`（推荐用于生产环境）：

```bash
# 创建服务文件
sudo nano /etc/systemd/system/tg-news-bot.service
```

内容：

```ini
[Unit]
Description=Telegram News Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/tg_news_bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start tg-news-bot
sudo systemctl enable tg-news-bot  # 开机自启

# 查看状态
sudo systemctl status tg-news-bot

# 查看日志
sudo journalctl -u tg-news-bot -f
```

## 常见问题

### Q1: 运行时报错 `Error 401: Unauthorized`

**原因：** Bot Token 无效或已过期

**解决方法：**
1. 检查 `.env` 中的 `TELEGRAM_BOT_TOKEN` 是否正确
2. 确认 token 没有多余的空格
3. 向 @BotFather 确认 bot 是否还存在

### Q2: 运行时报错 `Chat not found` 或 `403 Forbidden`

**原因：** Bot 无法访问目标频道

**解决方法：**
1. 确认 `TARGET_CHAT_ID` 格式正确（必须是负数）
2. 将 bot 添加到目标频道
3. 确保 bot 有管理员权限（至少需要发送消息权限）

### Q3: Session 登录失败或过期

**原因：** Telethon session 文件损坏或过期

**解决方法：**
1. 删除 `*.session` 文件
2. 重新运行 `python app.py`
3. 按提示重新登录

### Q4: 无法读取某些频道

**原因：** 频道是私有的或未加入

**解决方法：**
1. 确保你的 Telegram 账号已加入该频道/群组
2. 确认频道 username 正确（带 `@` 符号）
3. 如果是私有频道，使用频道 ID 而不是 username

### Q5: AI 分类不工作

**原因：** 未配置或 API Key 无效

**解决方法：**
1. 检查 `.env` 中的 `CURSOR_API_KEY` 或 `OPENAI_API_KEY` 是否正确
2. 确认 API Key 有足够的额度
3. 如果使用 OpenAI 兼容的第三方 API，检查 `OPENAI_BASE_URL` 配置
4. 同时配置了两个 Key 时，优先使用 Cursor SDK
5. 如果 AI 分类失败，系统会自动回退到规则分类，不影响基本功能
6. 查看日志文件 `logs/app.log` 获取详细错误信息

### Q6: 消息格式显示异常

**原因：** HTML 格式解析错误

**解决方法：**
- 消息使用 HTML 解析模式，动态内容已自动转义；如果仍然解析失败，会自动降级为纯文本发送
- 在 `templates.py` 中可以调整格式化逻辑
- 或在 `publisher.py` 中将 `parse_mode` 改为 `None`

### Q7: 触发 Telegram 限制（FloodWait）

**原因：** 请求过于频繁

**解决方法：**
1. 增加 `FETCH_INTERVAL_MINUTES` 的值（如改为 15 或 30）
2. 减少 `FETCH_LIMIT` 的值
3. 等待限制时间过后再运行
4. 采集器已内置自动重试机制，会自动等待

### Q8: 日志文件太大

**解决方法：**

使用 logrotate（Linux）：

```bash
sudo nano /etc/logrotate.d/tg-news-bot
```

内容：

```
/path/to/tg_news_bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 your_username your_username
}
```

### Q9: 数据库损坏

**原因：** 程序异常终止或磁盘问题

**解决方法：**
1. 备份 `news.db` 文件
2. 尝试使用 SQLite 工具修复：
   ```bash
   sqlite3 news.db "PRAGMA integrity_check;"
   ```
3. 如无法修复，删除 `news.db` 并重新运行（会丢失历史数据）

## 高级配置

### 自定义分类规则

编辑 `classifier.py` 中的 `RULE_KEYWORDS` 字典：

```python
RULE_KEYWORDS = {
    'politics': ['政府', '国务院', ...],
    'tech': ['AI', '人工智能', ...],
    'custom_category': ['关键词1', '关键词2'],  # 自定义分类
}
```

### 自定义消息模板

编辑 `templates.py` 中的 `format_breaking_news()` 和 `format_daily_report()` 函数。

### 调整采集和发布频率

在 `.env` 中：

```env
# 每 5 分钟采集一次
FETCH_INTERVAL_MINUTES=5

# 每天早上 8:00 发布日报
DAILY_REPORT_TIME=08:00
```

## 安全建议

1. **不要将 `.env` 文件提交到 git**（仓库根目录已附带 `.gitignore`，覆盖 `.env` / `*.session` / `news.db`）

2. **定期备份数据库**
   ```bash
   cp news.db news.db.backup.$(date +%Y%m%d)
   ```

3. **限制服务器访问权限**
   ```bash
   chmod 600 .env
   chmod 600 *.session
   ```

4. **使用专用 Bot 和频道**
   - 不要在生产环境使用个人账号
   - 为不同用途创建不同的 Bot

## 开发调试

启用 DEBUG 日志：

```env
LOG_LEVEL=DEBUG
```

单独测试各个模块：

```python
# 测试采集
from collector import collector
import asyncio

async def test():
    await collector.init_client()
    await collector.fetch_channel_messages('@channel_name', limit=10)

asyncio.run(test())
```

## 许可证

本项目仅供学习和个人使用。

- 仅通过官方 Telegram API 采集内容
- 仅用于已加入的公开或已授权的频道/群组
- 不得用于非法采集、滥用或侵犯他人隐私

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请在 GitHub 上提交 Issue。

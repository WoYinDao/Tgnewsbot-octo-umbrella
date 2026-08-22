# Tgnewsbot · Telegram 新闻播报机器人

自动从指定 Telegram 频道采集消息，用 AI 分类并生成摘要，再推送到你自己的频道：高置信度消息实时发快讯，每天定时发分类汇总日报。

## 工作流程

```
源频道 ──Telethon 采集──▶ 去重 ──▶ 规则 + AI 分类/摘要 ──▶ SQLite 存储
                                                              │
                    目标频道 ◀──Bot 发布（快讯 + 每日日报）──┘
```

- **采集**：Telethon 每 10 分钟（可配置）从多个源频道拉取最新消息，自动去重
- **分类**：先走关键词规则，拿不准的交给 AI（支持两种后端，二选一）：
  - **Cursor SDK**：用 Cursor 订阅的模型，配置 `CURSOR_API_KEY`
  - **OpenAI 兼容 API**：OpenAI / DeepSeek / OpenRouter / 本地 Ollama 等，配置 `OPENAI_API_KEY`
  - 都不配则只用规则分类，程序照常运行
- **发布**：置信度达标的消息即时推送为快讯；每天固定时间（默认 21:00）按分类汇总发日报

分类类目：政治 / 科技 / 游戏 / 财经 / 社会 / 其他

## 仓库结构

```
.
├── RUN_SETUP.sh        # 交互式快速启动脚本（配置/验证/启动三合一）
└── tg_news_bot/        # 机器人主体代码
    ├── app.py          # 程序入口
    ├── collector.py    # Telethon 采集
    ├── classifier.py   # 规则 + AI 分类（Cursor / OpenAI 双后端）
    ├── publisher.py    # Bot 发布
    ├── scheduler.py    # 定时任务
    ├── db.py           # SQLite 存储与去重
    ├── templates.py    # 快讯/日报排版模板
    ├── setup_guide.py  # 交互式配置向导（生成 .env）
    ├── verify_config.py# 配置验证工具
    └── README.md       # 详细文档（配置说明、部署、常见问题）
```

## 快速开始

环境要求：Python 3.9+（推荐 3.11+）、一个 Telegram 账号、一个 Bot Token。

```bash
git clone https://github.com/WoYinDao/Tgnewsbot-octo-umbrella.git
cd Tgnewsbot-octo-umbrella/tg_news_bot

# 安装依赖
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 生成配置（交互式向导）
python3 setup_guide.py

# 验证配置
python3 verify_config.py

# 启动（首次运行需输入 Telegram 验证码登录）
python3 app.py
```

或者在仓库根目录直接运行一键脚本：

```bash
./RUN_SETUP.sh
```

## 需要准备的凭证

| 配置项 | 获取方式 | 必需 |
|--------|----------|------|
| `TELETHON_API_ID` / `TELETHON_API_HASH` | [my.telegram.org/apps](https://my.telegram.org/apps) | 是 |
| `TELEGRAM_BOT_TOKEN` | Telegram 内搜索 [@BotFather](https://t.me/BotFather) | 是 |
| `TARGET_CHAT_ID` | 目标频道 ID（负数，如 `-1001234567890`） | 是 |
| `SOURCE_CHANNELS` | 要采集的频道，逗号分隔 | 是 |
| `CURSOR_API_KEY` | [Cursor Dashboard → API Keys](https://cursor.com/dashboard/api) | 可选（AI 分类） |
| `OPENAI_API_KEY` | OpenAI 或任何兼容服务 | 可选（AI 分类） |

完整配置项见 [`tg_news_bot/.env.example`](tg_news_bot/.env.example)。

## 更多文档

详细的配置说明、systemd 部署、常见问题排查，见 [`tg_news_bot/README.md`](tg_news_bot/README.md)。

## 安全提醒

- `.env`、`*.session`（Telegram 登录凭证）、`news.db` 已在 `.gitignore` 中，**绝对不要提交到 git**
- 建议 `chmod 600 .env *.session`

## 使用声明

本项目仅供学习和个人使用：仅通过官方 Telegram API 采集已加入的公开或已授权频道，不得用于非法采集、滥用或侵犯他人隐私。

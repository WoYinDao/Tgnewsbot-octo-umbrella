# 快速启动指南

## ✅ 已修复的问题

### 1. 程序卡死 - 已彻底解决
- ✅ 双重 Ctrl+C 机制：第一次优雅退出，第二次强制退出
- ✅ 所有网络操作添加超时保护（消息发送 10 秒，断开连接 5 秒）
- ✅ 连续失败 3 次自动停止发布（避免配置错误时无限重试）

### 2. Chat not found - 需要你配置

**问题原因**：`TARGET_CHAT_ID=3567119801` 是你的用户 ID，不是频道 ID

**快速解决（选一种）**：

---

## 🚀 立即运行（最简单）

### 方法 1：私聊模式（5 秒搞定）

```bash
# 第 1 步：在 Telegram 中搜索你的 Bot
@CloudTeamwatch_bot

# 第 2 步：发送 /start 命令
/start

# 第 3 步：运行程序
cd /home/user/Tgnewsbot-octo-umbrella/tg_news_bot
python3 app.py
```

**就这样！** Bot 会发消息到你的私聊。

---

### 方法 2：频道模式（推荐）

**详细步骤请查看**: `FIX_CHAT_ID.md`

简要步骤：
1. 使用 @userinfobot 获取频道 ID（负数）
2. 将 @CloudTeamwatch_bot 添加为频道管理员
3. 修改 `.env` 中的 `TARGET_CHAT_ID`
4. 运行程序

---

## 🎮 如何退出程序

### 正常退出
```
按一次 Ctrl+C
```
程序会优雅地停止，关闭所有连接。

### 强制退出（如果卡住）
```
按两次 Ctrl+C
```
程序会立即强制退出。

---

## 📊 运行测试

```bash
cd /home/user/Tgnewsbot-octo-umbrella/tg_news_bot

# 验证配置（可选）
python3 verify_config.py

# 启动机器人
python3 app.py
```

---

## 🔍 预期输出

### 成功运行的标志

```
============================================================
Telegram 新闻播报机器人
============================================================
INFO - 正在初始化应用...
INFO - 数据库初始化完成: news.db
INFO - Telethon 客户端初始化成功
INFO - Bot 初始化成功: @CloudTeamwatch_bot
INFO - 应用初始化完成
INFO - 调度器已启动
INFO - 首次启动，执行一次完整流程...
INFO - ===== 开始执行采集任务 =====
INFO - 从 @DNSPODT 采集到 10 条新消息
INFO - ===== 采集任务完成 =====
INFO - ===== 开始发布快讯 =====
INFO - 找到 3 条待发布快讯
INFO - 消息已发送到目标频道          ← 看到这行就成功了！
INFO - 快讯已发布: tech - xxx
INFO - ===== 快讯发布完成，共发布 3 条 =====
```

### 如果还是 Chat not found

说明你还没完成配置：
- **方法 1 用户**：需要先给 @CloudTeamwatch_bot 发送 `/start`
- **方法 2 用户**：需要修改 `.env` 中的 `TARGET_CHAT_ID` 为频道 ID

---

## 🛠️ 改进说明

现在程序具有以下特性：

1. **不会卡死**
   - 所有操作都有超时保护
   - 双重 Ctrl+C 保证能退出
   - 连续失败 3 次自动停止

2. **快速响应**
   - 退出信号响应时间 < 0.1 秒
   - 第一次 Ctrl+C 在 10 秒内退出
   - 第二次 Ctrl+C 立即退出

3. **智能容错**
   - 发送失败不会无限重试
   - 超时自动跳过
   - 错误详细记录在日志中

---

## 📝 下一步

运行成功后，你可以：

1. **后台运行**
   ```bash
   screen -S tg_bot
   python3 app.py
   # 按 Ctrl+A 然后 D 离开
   ```

2. **查看日志**
   ```bash
   tail -f logs/app.log
   ```

3. **定制配置**
   - 修改 `.env` 文件
   - 调整采集间隔 `FETCH_INTERVAL_MINUTES`
   - 调整日报时间 `DAILY_REPORT_TIME`

---

**现在就试试吧！选择方法 1 或方法 2，然后运行 `python3 app.py`**

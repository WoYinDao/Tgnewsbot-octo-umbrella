"""
Bot 管理命令 - 通过 Telegram 私聊管理机器人，无需登录服务器

需要在 .env 中配置 ADMIN_USER_IDS（你的 Telegram 用户 ID，逗号分隔），
未配置时命令功能不启动。获取自己的用户 ID：给 @userinfobot 发条消息即可。

可用命令：
/help                     命令列表
/stats                    数据库统计
/sources                  查看源频道列表
/addsource @channel       添加源频道
/delsource @channel       删除源频道
/threshold 0.8            设置快讯置信度阈值（0-1）
/minscore 6               设置快讯价值分门槛（0-10）
/pause                    暂停采集
/resume                   恢复采集
/report                   立即生成并发布今天的日报
/reload                   重新加载过滤规则文件
"""
import logging
from datetime import datetime
from functools import wraps

import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_USER_IDS,
    DAILY_REPORT_TIMEZONE,
    DAILY_REPORT_TOP_N,
)
from db import db
from filters import message_filter
from runtime import runtime

logger = logging.getLogger(__name__)

HELP_TEXT = """可用命令：

/stats - 数据库统计
/sources - 查看源频道列表
/addsource @channel - 添加源频道
/delsource @channel - 删除源频道
/threshold 0.8 - 设置快讯置信度阈值（0-1）
/minscore 6 - 设置快讯价值分门槛（0-10）
/pause - 暂停采集
/resume - 恢复采集
/report - 立即发布今天的日报
/reload - 重新加载过滤规则文件

配置修改立即生效并持久化，重启后保留。"""


def admin_only(func):
    """只响应管理员的命令，其他人静默忽略"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id not in ADMIN_USER_IDS:
            if user:
                logger.warning(f'忽略非管理员的命令: user_id={user.id}')
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await db.get_stats()
    lines = [
        '数据库统计',
        f"总消息数：{stats['total']}",
        f"已发布数：{stats['published']}",
        '',
        '分类统计：',
    ]
    for category, count in stats['by_category'].items():
        lines.append(f'  {category}: {count}')
    lines.append('')
    lines.append(f'采集状态：{"已暂停" if runtime.paused else "运行中"}')
    lines.append(f'置信度阈值：{runtime.confidence_threshold}')
    lines.append(f'价值分门槛：{runtime.min_score}')
    await update.message.reply_text('\n'.join(lines))


@admin_only
async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not runtime.sources:
        await update.message.reply_text('当前没有配置源频道，用 /addsource @channel 添加')
        return
    lines = [f'源频道（{len(runtime.sources)} 个）：'] + [f'  {s}' for s in runtime.sources]
    await update.message.reply_text('\n'.join(lines))


@admin_only
async def cmd_addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('用法：/addsource @channel')
        return
    channel = context.args[0]
    if await runtime.add_source(channel):
        await update.message.reply_text(f'已添加源频道 {channel}，下一轮采集生效')
    else:
        await update.message.reply_text(f'{channel} 已在源频道列表中')


@admin_only
async def cmd_delsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('用法：/delsource @channel')
        return
    channel = context.args[0]
    if await runtime.remove_source(channel):
        await update.message.reply_text(f'已删除源频道 {channel}')
    else:
        await update.message.reply_text(f'{channel} 不在源频道列表中，用 /sources 查看当前列表')


@admin_only
async def cmd_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f'当前置信度阈值：{runtime.confidence_threshold}\n用法：/threshold 0.8')
        return
    try:
        value = float(context.args[0])
        if not 0 <= value <= 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text('阈值必须是 0-1 之间的数字，例如 /threshold 0.8')
        return
    await runtime.set_confidence_threshold(value)
    await update.message.reply_text(f'置信度阈值已设为 {runtime.confidence_threshold}')


@admin_only
async def cmd_minscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f'当前价值分门槛：{runtime.min_score}\n用法：/minscore 6')
        return
    try:
        value = float(context.args[0])
        if not 0 <= value <= 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text('门槛必须是 0-10 之间的数字，例如 /minscore 6')
        return
    await runtime.set_min_score(value)
    await update.message.reply_text(f'价值分门槛已设为 {runtime.min_score}（0 = 不限制）')


@admin_only
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await runtime.set_paused(True)
    await update.message.reply_text('采集已暂停，用 /resume 恢复')


@admin_only
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await runtime.set_paused(False)
    await update.message.reply_text('采集已恢复')


@admin_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 延迟导入避免循环依赖（publisher 不依赖本模块）
    from publisher import publisher

    today = datetime.now(pytz.timezone(DAILY_REPORT_TIMEZONE)).date().isoformat()
    await update.message.reply_text(f'正在生成 {today} 的日报...')
    success = await publisher.publish_daily_report(date=today, top_n=DAILY_REPORT_TOP_N)
    if success:
        await update.message.reply_text('日报已发布到目标频道')
    else:
        await update.message.reply_text('日报发布失败（可能今天还没有数据），详见日志')


@admin_only
async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    block_count, white_count = message_filter.reload()
    await update.message.reply_text(f'过滤规则已重新加载：屏蔽规则 {block_count} 条，关注规则 {white_count} 条')


class CommandBot:
    """管理命令服务：独立的 PTB Application，只负责收命令（发消息仍走 publisher）"""

    def __init__(self):
        self.app: Application = None

    @property
    def enabled(self) -> bool:
        return bool(ADMIN_USER_IDS)

    async def start(self):
        """启动命令轮询；未配置 ADMIN_USER_IDS 时跳过"""
        if not self.enabled:
            logger.info('未配置 ADMIN_USER_IDS，Bot 管理命令未启用')
            return

        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        handlers = {
            'start': cmd_help,
            'help': cmd_help,
            'stats': cmd_stats,
            'sources': cmd_sources,
            'addsource': cmd_addsource,
            'delsource': cmd_delsource,
            'threshold': cmd_threshold,
            'minscore': cmd_minscore,
            'pause': cmd_pause,
            'resume': cmd_resume,
            'report': cmd_report,
            'reload': cmd_reload,
        }
        for command, handler in handlers.items():
            self.app.add_handler(CommandHandler(command, handler))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=['message'])
        logger.info(f'Bot 管理命令已启用，管理员: {ADMIN_USER_IDS}')

    async def stop(self):
        if self.app is None:
            return
        try:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info('Bot 管理命令已停止')
        except Exception as e:
            logger.warning(f'停止命令服务失败: {e}')
        self.app = None


# 全局命令服务实例
command_bot = CommandBot()

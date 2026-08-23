"""
发布模块 - 使用 Telegram Bot API 发布消息（python-telegram-bot 21+，原生 async）
"""
import logging
import asyncio
import re

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError

from config import (
    TELEGRAM_BOT_TOKEN,
    TARGET_CHAT_ID,
    MESSAGE_MAX_LENGTH,
    BREAKING_MAX_PER_ROUND,
    BREAKING_MAX_AGE_HOURS
)
from db import db
from runtime import runtime
from templates import format_breaking_news, format_daily_report, truncate_message

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """去掉 HTML 标签，用于解析失败时的纯文本降级发送"""
    return re.sub(r'<[^>]+>', '', text)


class Publisher:
    """消息发布器"""

    def __init__(self):
        self.bot = None

    async def init_bot(self):
        """初始化 Bot"""
        try:
            self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await self.bot.initialize()
            bot_info = await self.bot.get_me()
            logger.info(f'Bot 已初始化: @{bot_info.username}')
        except Exception as e:
            logger.error(f'Bot 初始化失败: {e}')
            raise

    async def close(self):
        """关闭 Bot"""
        if self.bot:
            try:
                await asyncio.wait_for(self.bot.shutdown(), timeout=5.0)
                logger.info('Bot 已关闭')
            except asyncio.TimeoutError:
                logger.warning('关闭 Bot 超时，强制继续')
            except Exception as e:
                logger.error(f'关闭 Bot 失败: {e}')

    async def send_message(self, text: str, parse_mode: str = ParseMode.HTML) -> bool:
        """
        发送消息到目标频道

        Args:
            text: 消息内容（HTML 格式）
            parse_mode: 解析模式

        Returns:
            是否发送成功
        """
        if not self.bot:
            logger.error('Bot 未初始化')
            return False

        # 截断过长消息
        text = truncate_message(text, MESSAGE_MAX_LENGTH)

        try:
            await asyncio.wait_for(
                self.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=text,
                    parse_mode=parse_mode,
                ),
                timeout=15.0
            )
            logger.info('消息已发送到目标频道')
            return True

        except asyncio.TimeoutError:
            logger.error('发送消息超时 (15秒)')
            return False
        except BadRequest as e:
            if 'parse' in str(e).lower() or 'entit' in str(e).lower():
                # HTML 解析失败（如截断破坏了标签），降级为纯文本重发
                logger.warning(f'HTML 解析失败，降级为纯文本发送: {e}')
                try:
                    await asyncio.wait_for(
                        self.bot.send_message(
                            chat_id=TARGET_CHAT_ID,
                            text=_strip_html(text),
                        ),
                        timeout=15.0
                    )
                    logger.info('消息已以纯文本发送')
                    return True
                except Exception as e2:
                    logger.error(f'纯文本降级发送也失败: {e2}')
                    return False
            logger.error(f'发送消息失败 (BadRequest): {e}')
            return False
        except TelegramError as e:
            error_msg = str(e)
            if 'chat not found' in error_msg.lower():
                logger.error(f'发送消息失败: 找不到目标频道 (TARGET_CHAT_ID={TARGET_CHAT_ID})')
                logger.error('请确认：1) TARGET_CHAT_ID 配置正确  2) Bot 已被添加到频道  3) Bot 有发送消息权限')
            else:
                logger.error(f'发送消息失败: {e}')
            return False
        except Exception as e:
            logger.error(f'发送消息时发生未知错误: {e}', exc_info=True)
            return False

    async def publish_breaking_news(self) -> int:
        """
        发布快讯（未发布的高置信度消息）

        Returns:
            发布的消息数量
        """
        try:
            # 先把超龄的未发布消息标记为跳过，防止首次运行/长时间停机后
            # 把积压的历史旧闻当快讯轰炸目标频道（它们仍会进入日报）
            await db.mark_stale_as_skipped(BREAKING_MAX_AGE_HOURS)

            # 获取未发布的高置信度消息（限制数量 + 新鲜度 + 价值分门槛，防刷屏）
            # 阈值来自运行时配置，可用 /threshold 和 /minscore 命令调整
            messages = await db.get_unpublished_messages(
                min_confidence=runtime.confidence_threshold,
                max_age_hours=BREAKING_MAX_AGE_HOURS,
                limit=BREAKING_MAX_PER_ROUND,
                min_score=runtime.min_score if runtime.min_score > 0 else None
            )

            if not messages:
                logger.info('没有待发布的快讯')
                return 0

            # 按时间正序发送，读者在频道里看到的顺序更自然
            messages.reverse()

            logger.info(f'找到 {len(messages)} 条待发布快讯（本轮上限 {BREAKING_MAX_PER_ROUND} 条）')

            published_count = 0
            consecutive_failures = 0  # 连续失败计数器
            max_consecutive_failures = 3  # 最多连续失败次数

            for msg in messages:
                # 如果连续失败太多次，停止尝试
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(f'连续失败 {consecutive_failures} 次，停止发布剩余消息')
                    break

                try:
                    # 格式化消息
                    formatted_text = format_breaking_news(msg)

                    # 发送消息
                    success = await self.send_message(formatted_text)

                    if success:
                        # 标记为已发布
                        await db.mark_as_published(msg['id'])
                        published_count += 1
                        consecutive_failures = 0  # 重置失败计数
                        logger.info(f"快讯已发布: {msg['category']} - {msg['summary'][:50]}")

                        # 限速：避免触发 Telegram 限制
                        await asyncio.sleep(1)
                    else:
                        consecutive_failures += 1
                        logger.warning(f"快讯发布失败 (连续失败: {consecutive_failures}/{max_consecutive_failures}): {msg['id']}")

                except Exception as e:
                    logger.error(f"发布消息 {msg['id']} 失败: {e}", exc_info=True)
                    continue

            logger.info(f'快讯发布完成，共发布 {published_count} 条')
            return published_count

        except Exception as e:
            logger.error(f'发布快讯失败: {e}', exc_info=True)
            return 0

    async def publish_daily_report(self, date: str, top_n: int = 10) -> bool:
        """
        发布日报

        Args:
            date: 日期 (YYYY-MM-DD)
            top_n: 每个分类取 top N

        Returns:
            是否发布成功
        """
        try:
            logger.info(f'开始生成日报: {date}')

            # 获取日报数据
            data = await db.get_daily_summary(date, top_n)

            if not data:
                logger.warning(f'日期 {date} 没有数据，跳过日报')
                return False

            # 格式化日报
            report_text = format_daily_report(date, data)

            # 发送日报
            success = await self.send_message(report_text)

            if success:
                logger.info(f'日报发布成功: {date}')
            else:
                logger.error(f'日报发布失败: {date}')

            return success

        except Exception as e:
            logger.error(f'发布日报失败: {e}', exc_info=True)
            return False


# 全局发布器实例
publisher = Publisher()

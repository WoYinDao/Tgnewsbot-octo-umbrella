"""
发布模块 - 使用 Telegram Bot API 发布消息
"""
import logging
import asyncio
from telegram import Bot, ParseMode
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TARGET_CHAT_ID, MESSAGE_MAX_LENGTH, AI_CONFIDENCE_THRESHOLD
from db import db
from templates import format_breaking_news, format_daily_report, truncate_message

logger = logging.getLogger(__name__)


class Publisher:
    """消息发布器"""

    def __init__(self):
        self.bot = None

    async def init_bot(self):
        """初始化 Bot"""
        try:
            self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
            # python-telegram-bot 13.x 是同步的，在线程池中运行（Python 3.8 兼容）
            loop = asyncio.get_event_loop()
            bot_info = await loop.run_in_executor(None, self.bot.get_me)
            logger.info(f'Bot 已初始化: @{bot_info.username}')
        except Exception as e:
            logger.error(f'Bot 初始化失败: {e}')
            raise

    async def send_message(self, text: str, parse_mode: str = ParseMode.MARKDOWN) -> bool:
        """
        发送消息到目标频道

        Args:
            text: 消息内容
            parse_mode: 解析模式（Markdown/HTML）

        Returns:
            是否发送成功
        """
        if not self.bot:
            logger.error('Bot 未初始化')
            return False

        try:
            # 截断过长消息
            text = truncate_message(text, MESSAGE_MAX_LENGTH)

            # 发送消息（python-telegram-bot 13.x 是同步的，在线程池中运行）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )
            )
            logger.info('消息已发送到目标频道')
            return True

        except TelegramError as e:
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
            # 获取未发布的高置信度消息
            messages = await db.get_unpublished_messages(min_confidence=AI_CONFIDENCE_THRESHOLD)

            if not messages:
                logger.info('没有待发布的快讯')
                return 0

            logger.info(f'找到 {len(messages)} 条待发布快讯')

            published_count = 0

            for msg in messages:
                try:
                    # 格式化消息
                    formatted_text = format_breaking_news(msg)

                    # 发送消息
                    success = await self.send_message(formatted_text)

                    if success:
                        # 标记为已发布
                        await db.mark_as_published(msg['id'])
                        published_count += 1
                        logger.info(f"快讯已发布: {msg['category']} - {msg['summary'][:50]}")

                        # 限速：避免触发 Telegram 限制
                        await asyncio.sleep(1)
                    else:
                        logger.warning(f"快讯发布失败: {msg['id']}")

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

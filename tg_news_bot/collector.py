"""
采集模块 - 使用 Telethon 从指定频道采集消息
"""
import asyncio
import logging
import pytz
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
from config import (
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELETHON_SESSION,
    SOURCE_CHANNELS,
    FETCH_LIMIT,
    BASE_DIR,
    DAILY_REPORT_TIMEZONE
)
from db import db
from classifier import classifier

logger = logging.getLogger(__name__)


class Collector:
    """消息采集器"""

    def __init__(self):
        self.client = None
        self.session_file = BASE_DIR / f'{TELETHON_SESSION}.session'

    async def init_client(self):
        """初始化 Telethon 客户端"""
        try:
            self.client = TelegramClient(
                str(self.session_file),
                int(TELETHON_API_ID),
                TELETHON_API_HASH
            )
            await self.client.start()
            logger.info('Telethon 客户端已启动')

            # 获取当前用户信息
            me = await self.client.get_me()
            logger.info(f'已登录用户: {me.first_name} (@{me.username})')

        except Exception as e:
            logger.error(f'Telethon 客户端初始化失败: {e}')
            raise

    async def close(self):
        """关闭客户端"""
        if self.client:
            try:
                # 添加超时保护防止卡死
                await asyncio.wait_for(self.client.disconnect(), timeout=5.0)
                logger.info('Telethon 客户端已关闭')
            except asyncio.TimeoutError:
                logger.warning('关闭 Telethon 客户端超时，强制继续')
            except Exception as e:
                logger.error(f'关闭 Telethon 客户端失败: {e}')

    @staticmethod
    def clean_text(text: str) -> str:
        """
        清洗文本
        - 去除多余空白字符
        - 去除特殊字符
        """
        if not text:
            return ''

        # 去除首尾空白
        text = text.strip()

        # 替换多个连续空白为单个空格
        text = ' '.join(text.split())

        return text

    async def fetch_channel_messages(self, channel: str, limit: int = FETCH_LIMIT) -> int:
        """
        从指定频道采集消息

        Args:
            channel: 频道 username 或 ID
            limit: 采集数量限制

        Returns:
            采集到的新消息数量
        """
        try:
            logger.info(f'开始采集频道: {channel}, 限制 {limit} 条')

            # 获取频道实体
            try:
                entity = await self.client.get_entity(channel)
            except ValueError as e:
                logger.error(f'无法找到频道 {channel}: {e}')
                return 0
            except ChannelPrivateError:
                logger.error(f'频道 {channel} 是私有的或未加入')
                return 0

            # 获取消息
            messages = []
            async for message in self.client.iter_messages(entity, limit=limit):
                if message.text:  # 只处理文本消息
                    messages.append(message)

            logger.info(f'从 {channel} 获取到 {len(messages)} 条消息')

            # 处理消息
            report_tz = pytz.timezone(DAILY_REPORT_TIMEZONE)
            new_count = 0
            for msg in messages:
                try:
                    # 清洗文本
                    text = self.clean_text(msg.text)

                    if not text or len(text) < 10:
                        logger.debug(f'跳过过短的消息: {msg.id}')
                        continue

                    # 先查重，避免对已入库的旧消息重复调用 AI 分类（浪费费用）
                    if await db.message_exists(channel, msg.id, text):
                        logger.debug(f'消息已存在，跳过: {channel}/{msg.id}')
                        continue

                    # 使用分类器
                    classification = await classifier.classify(text)

                    # 消息时间转换为日报时区存储，保证日报按本地日期聚合正确
                    local_date = msg.date.astimezone(report_tz)

                    # 插入数据库
                    msg_id = await db.insert_message(
                        source=channel,
                        msg_id=msg.id,
                        date=local_date,
                        text=text,
                        category=classification['category'],
                        confidence=classification['confidence'],
                        summary=classification['summary']
                    )

                    if msg_id:
                        new_count += 1
                        logger.info(
                            f'新消息已入库: {channel}/{msg.id} -> '
                            f'{classification["category"]} ({classification["confidence"]:.2f})'
                        )

                    # 限速：只对真正处理的新消息间隔 0.5 秒
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f'处理消息 {msg.id} 失败: {e}', exc_info=True)
                    continue

            logger.info(f'频道 {channel} 采集完成，新增 {new_count} 条')
            return new_count

        except FloodWaitError as e:
            logger.warning(f'触发频率限制，需等待 {e.seconds} 秒')
            await asyncio.sleep(e.seconds)
            return 0
        except ChatAdminRequiredError:
            logger.error(f'频道 {channel} 需要管理员权限')
            return 0
        except Exception as e:
            logger.error(f'采集频道 {channel} 失败: {e}', exc_info=True)
            return 0

    async def collect_all(self):
        """采集所有配置的频道"""
        if not SOURCE_CHANNELS:
            logger.warning('未配置采集源（SOURCE_CHANNELS）')
            return

        total_new = 0

        for channel in SOURCE_CHANNELS:
            try:
                new_count = await self.fetch_channel_messages(channel)
                total_new += new_count

                # 频道间隔：避免触发风控
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f'采集频道 {channel} 时发生异常: {e}', exc_info=True)
                continue

        logger.info(f'本轮采集完成，共新增 {total_new} 条消息')
        return total_new


# 全局采集器实例
collector = Collector()

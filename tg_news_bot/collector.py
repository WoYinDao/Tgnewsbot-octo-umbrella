"""
采集模块 - 使用 Telethon 从指定频道采集消息
"""
import asyncio
import logging
import time
import pytz
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
from config import (
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELETHON_SESSION,
    FETCH_LIMIT,
    BASE_DIR,
    DAILY_REPORT_TIMEZONE,
    SEMANTIC_DEDUP_WINDOW_HOURS
)
from db import db
from classifier import classifier
from filters import message_filter
from dedup import deduper
from runtime import runtime

logger = logging.getLogger(__name__)


class Collector:
    """消息采集器"""

    def __init__(self):
        self.client = None
        self.session_file = BASE_DIR / f'{TELETHON_SESSION}.session'
        # 频道实体缓存：get_entity 会消耗 Telegram API 配额，只在首次解析
        self._entities = {}
        # FloodWait 冷却表：channel -> 解禁时间（time.monotonic 时间戳）
        self._flood_until = {}

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
            # 获取频道实体（带缓存，避免每轮都消耗解析配额）
            entity = self._entities.get(channel)
            if entity is None:
                try:
                    entity = await self.client.get_entity(channel)
                    self._entities[channel] = entity
                except ValueError as e:
                    logger.error(f'无法找到频道 {channel}: {e}')
                    return 0
                except ChannelPrivateError:
                    logger.error(f'频道 {channel} 是私有的或未加入')
                    return 0

            # 增量采集：只拉取上次进度之后的新消息
            last_msg_id = await db.get_last_msg_id(channel)
            logger.info(f'开始采集频道: {channel}（上次进度 msg_id={last_msg_id}，限制 {limit} 条）')

            # 获取消息（min_id 只返回 ID 大于该值的消息，首次运行 min_id=0 即拉最新 N 条）
            messages = []
            max_seen_id = last_msg_id
            async for message in self.client.iter_messages(entity, limit=limit, min_id=last_msg_id):
                max_seen_id = max(max_seen_id, message.id)
                if message.text:  # 只处理文本消息
                    messages.append(message)

            logger.info(f'从 {channel} 获取到 {len(messages)} 条新消息')

            # 近期消息缓存，供语义去重比对（含本批已入库的，防止同批内重复）
            recent_for_dedup = []
            if messages and deduper.enabled:
                recent_for_dedup = await db.get_recent_for_dedup(SEMANTIC_DEDUP_WINDOW_HOURS)

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

                    # 广告黑名单 / 关注白名单过滤
                    allowed, reason = message_filter.check(text)
                    if not allowed:
                        logger.info(f'消息被过滤: {channel}/{msg.id}（{reason}）')
                        continue

                    # 精确查重（含跨频道内容查重），避免重复调用 AI 分类浪费费用
                    if await db.message_exists(channel, msg.id, text):
                        logger.debug(f'消息已存在，跳过: {channel}/{msg.id}')
                        continue

                    # 语义去重：识别同一事件的相似报道
                    is_dup, similarity, embedding_json = await deduper.check(text, recent_for_dedup)
                    if is_dup:
                        logger.info(f'消息与近期报道语义重复（{similarity:.2f}），跳过: {channel}/{msg.id}')
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
                        summary=classification['summary'],
                        score=classification.get('score'),
                        embedding=embedding_json
                    )

                    if msg_id:
                        new_count += 1
                        # 加入去重缓存，同一批内的相似消息也能被拦截
                        recent_for_dedup.append({'id': msg_id, 'text': text, 'embedding': embedding_json})
                        logger.info(
                            f'新消息已入库: {channel}/{msg.id} -> '
                            f'{classification["category"]} ({classification["confidence"]:.2f})'
                        )

                    # 限速：只对真正处理的新消息间隔 0.5 秒
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f'处理消息 {msg.id} 失败: {e}', exc_info=True)
                    continue

            # 保存采集进度（含被跳过的短消息/媒体消息，避免下轮重复拉取）
            if max_seen_id > last_msg_id:
                await db.set_last_msg_id(channel, max_seen_id)

            logger.info(f'频道 {channel} 采集完成，新增 {new_count} 条')
            return new_count

        except FloodWaitError as e:
            # 不在原地等待（可能长达数小时，会卡死整轮采集）：
            # 记录解禁时间，本轮跳过该频道，之后的轮次自动恢复
            self._flood_until[channel] = time.monotonic() + e.seconds
            logger.warning(f'频道 {channel} 触发频率限制，冷却 {e.seconds} 秒后自动恢复')
            return 0
        except ChatAdminRequiredError:
            logger.error(f'频道 {channel} 需要管理员权限')
            return 0
        except Exception as e:
            logger.error(f'采集频道 {channel} 失败: {e}', exc_info=True)
            return 0

    async def collect_all(self):
        """采集所有配置的频道（源列表来自运行时配置，可用 Bot 命令增删）"""
        if runtime.paused:
            logger.info('采集已暂停（用 /resume 命令恢复），本轮跳过')
            return 0

        if not runtime.sources:
            logger.warning('未配置采集源（SOURCE_CHANNELS 或 /addsource 命令）')
            return

        total_new = 0

        for channel in runtime.sources:
            # 跳过仍在 FloodWait 冷却期的频道
            flood_until = self._flood_until.get(channel, 0)
            if flood_until > time.monotonic():
                remaining = int(flood_until - time.monotonic())
                logger.info(f'频道 {channel} 仍在限流冷却中（剩余 {remaining} 秒），本轮跳过')
                continue

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

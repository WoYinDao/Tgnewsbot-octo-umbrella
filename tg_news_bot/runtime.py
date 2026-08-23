"""
运行时配置 - Bot 命令可修改的设置

启动时从数据库 settings 表加载（Bot 命令改过的值），
没改过的项回退到 .env / config.py 的默认值。
修改会立即生效并持久化，重启后保留。
"""
import logging
from typing import List

from config import (
    SOURCE_CHANNELS,
    AI_CONFIDENCE_THRESHOLD,
    BREAKING_MIN_SCORE,
)
from db import db

logger = logging.getLogger(__name__)


class RuntimeConfig:
    """可在运行时被 Bot 命令修改的配置"""

    def __init__(self):
        self.sources: List[str] = list(SOURCE_CHANNELS)
        self.confidence_threshold: float = AI_CONFIDENCE_THRESHOLD
        self.min_score: float = BREAKING_MIN_SCORE
        self.paused: bool = False

    async def load(self):
        """从数据库加载持久化的运行时设置（覆盖 .env 默认值）"""
        sources = await db.get_setting('sources')
        if sources is not None:
            self.sources = [s.strip() for s in sources.split(',') if s.strip()]

        threshold = await db.get_setting('confidence_threshold')
        if threshold is not None:
            self.confidence_threshold = float(threshold)

        min_score = await db.get_setting('min_score')
        if min_score is not None:
            self.min_score = float(min_score)

        paused = await db.get_setting('paused')
        if paused is not None:
            self.paused = paused == '1'

        logger.info(
            f'运行时配置：源频道 {len(self.sources)} 个，'
            f'置信度阈值 {self.confidence_threshold}，价值分门槛 {self.min_score}，'
            f'采集{"已暂停" if self.paused else "运行中"}'
        )

    async def add_source(self, channel: str) -> bool:
        """添加源频道，已存在返回 False"""
        channel = channel.strip()
        if channel in self.sources:
            return False
        self.sources.append(channel)
        await db.set_setting('sources', ','.join(self.sources))
        return True

    async def remove_source(self, channel: str) -> bool:
        """删除源频道，不存在返回 False"""
        channel = channel.strip()
        if channel not in self.sources:
            return False
        self.sources.remove(channel)
        await db.set_setting('sources', ','.join(self.sources))
        return True

    async def set_confidence_threshold(self, value: float):
        self.confidence_threshold = max(0.0, min(1.0, value))
        await db.set_setting('confidence_threshold', str(self.confidence_threshold))

    async def set_min_score(self, value: float):
        self.min_score = max(0.0, min(10.0, value))
        await db.set_setting('min_score', str(self.min_score))

    async def set_paused(self, paused: bool):
        self.paused = paused
        await db.set_setting('paused', '1' if paused else '0')


# 全局运行时配置实例
runtime = RuntimeConfig()

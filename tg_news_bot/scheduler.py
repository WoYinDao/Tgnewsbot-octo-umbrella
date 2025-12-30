"""
调度模块 - 定时任务管理
"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from config import (
    FETCH_INTERVAL_MINUTES,
    DAILY_REPORT_TIME,
    DAILY_REPORT_TIMEZONE,
    DAILY_REPORT_TOP_N
)
from collector import collector
from publisher import publisher

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        # APScheduler 3.6.3 需要 pytz 时区对象
        tz = pytz.timezone(DAILY_REPORT_TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=tz)
        self.running = False

    async def collect_task(self):
        """采集任务"""
        try:
            logger.info('===== 开始执行采集任务 =====')
            await collector.collect_all()
            logger.info('===== 采集任务完成 =====')
        except Exception as e:
            logger.error(f'采集任务执行失败: {e}', exc_info=True)

    async def publish_breaking_news_task(self):
        """发布快讯任务"""
        try:
            logger.info('===== 开始发布快讯 =====')
            count = await publisher.publish_breaking_news()
            logger.info(f'===== 快讯发布完成，共 {count} 条 =====')
        except Exception as e:
            logger.error(f'快讯发布任务执行失败: {e}', exc_info=True)

    async def publish_daily_report_task(self):
        """发布日报任务"""
        try:
            logger.info('===== 开始生成并发布日报 =====')

            # 获取昨天的日期
            now = datetime.now(pytz.timezone(DAILY_REPORT_TIMEZONE))
            yesterday = now.date().isoformat()

            success = await publisher.publish_daily_report(
                date=yesterday,
                top_n=DAILY_REPORT_TOP_N
            )

            if success:
                logger.info(f'===== 日报发布成功: {yesterday} =====')
            else:
                logger.warning(f'===== 日报发布失败: {yesterday} =====')

        except Exception as e:
            logger.error(f'日报发布任务执行失败: {e}', exc_info=True)

    async def collect_and_publish_task(self):
        """
        组合任务：采集 -> 发布快讯
        在每个采集周期后立即尝试发布新消息
        """
        try:
            # 先采集
            await self.collect_task()

            # 等待 2 秒，确保数据库写入完成
            await asyncio.sleep(2)

            # 再发布
            await self.publish_breaking_news_task()

        except Exception as e:
            logger.error(f'组合任务执行失败: {e}', exc_info=True)

    def setup_jobs(self):
        """设置定时任务"""

        # 获取 pytz 时区对象
        tz = pytz.timezone(DAILY_REPORT_TIMEZONE)

        # 1. 采集 + 发布快讯任务（每 N 分钟执行一次）
        self.scheduler.add_job(
            self.collect_and_publish_task,
            trigger=IntervalTrigger(minutes=FETCH_INTERVAL_MINUTES, timezone=tz),
            id='collect_and_publish',
            name='采集并发布快讯',
            replace_existing=True
        )
        logger.info(f'已添加任务: 采集并发布快讯（每 {FETCH_INTERVAL_MINUTES} 分钟）')

        # 2. 日报任务（每天固定时间）
        hour, minute = map(int, DAILY_REPORT_TIME.split(':'))
        self.scheduler.add_job(
            self.publish_daily_report_task,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id='daily_report',
            name='发布日报',
            replace_existing=True
        )
        logger.info(f'已添加任务: 发布日报（每天 {DAILY_REPORT_TIME} {DAILY_REPORT_TIMEZONE}）')

    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning('调度器已在运行中')
            return

        self.setup_jobs()
        self.scheduler.start()
        self.running = True
        logger.info('调度器已启动')

        # 打印所有任务
        self.print_jobs()

    def stop(self):
        """停止调度器"""
        if not self.running:
            return

        self.scheduler.shutdown(wait=False)
        self.running = False
        logger.info('调度器已停止')

    def print_jobs(self):
        """打印所有已调度的任务"""
        jobs = self.scheduler.get_jobs()
        if jobs:
            logger.info('当前调度任务:')
            for job in jobs:
                logger.info(f'  - {job.name} (ID: {job.id}), 下次执行: {job.next_run_time}')
        else:
            logger.warning('没有已调度的任务')

    async def run_once(self):
        """
        手动执行一次完整流程（用于测试）
        """
        logger.info('===== 手动执行一次完整流程 =====')

        try:
            # 1. 采集
            await self.collect_task()

            # 2. 等待
            await asyncio.sleep(2)

            # 3. 发布快讯
            await self.publish_breaking_news_task()

            logger.info('===== 手动执行完成 =====')

        except Exception as e:
            logger.error(f'手动执行失败: {e}', exc_info=True)


# 全局调度器实例
scheduler = TaskScheduler()

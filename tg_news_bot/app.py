"""
主程序入口
"""
import asyncio
import logging
import signal
import sys

from config import setup_logging, validate_config
from db import db
from collector import collector
from classifier import classifier
from publisher import publisher
from scheduler import scheduler

logger = logging.getLogger(__name__)


class Application:
    """应用主类"""

    def __init__(self):
        self.running = False
        self._stop_event = asyncio.Event()

    async def init(self):
        """初始化应用"""
        logger.info('正在初始化应用...')

        try:
            # 验证配置
            validate_config()

            # 初始化数据库
            await db.init_db()

            # 初始化采集器
            await collector.init_client()

            # 初始化发布器
            await publisher.init_bot()

            logger.info('应用初始化完成')

        except Exception as e:
            logger.error(f'应用初始化失败: {e}', exc_info=True)
            raise

    async def start(self):
        """启动应用"""
        if self.running:
            logger.warning('应用已在运行中')
            return

        try:
            # 初始化
            await self.init()

            # 启动调度器
            scheduler.start()

            # 首次运行：立即执行一次采集和发布
            logger.info('首次启动，执行一次完整流程...')
            await scheduler.run_once()

            self.running = True
            logger.info('应用已启动，进入运行状态')

            # 打印统计信息
            await self.print_stats()

            # 保持运行，直到收到退出信号
            await self._stop_event.wait()

        except KeyboardInterrupt:
            logger.info('收到退出信号 (Ctrl+C)')
            await self.stop()
        except Exception as e:
            logger.error(f'应用运行异常: {e}', exc_info=True)
            await self.stop()

    async def stop(self):
        """停止应用"""
        # 使用标志防止重复停止
        if hasattr(self, '_stopping') and self._stopping:
            return

        self._stopping = True
        self.running = False
        self._stop_event.set()

        logger.info('正在停止应用...')

        try:
            # 停止调度器
            scheduler.stop()

            # 关闭采集器
            await collector.close()

            # 关闭发布器
            await publisher.close()

            # 关闭分类器（释放 AI 客户端）
            await classifier.close()

            # 关闭数据库
            await db.close()

            logger.info('应用已停止')

        except Exception as e:
            logger.error(f'停止应用时发生错误: {e}', exc_info=True)

    async def print_stats(self):
        """打印统计信息"""
        try:
            stats = await db.get_stats()
            logger.info('=' * 50)
            logger.info('数据库统计:')
            logger.info(f'  总消息数: {stats["total"]}')
            logger.info(f'  已发布数: {stats["published"]}')
            logger.info('  分类统计:')
            for category, count in stats['by_category'].items():
                logger.info(f'    - {category}: {count}')
            logger.info('=' * 50)
        except Exception as e:
            logger.error(f'获取统计信息失败: {e}')


def setup_signal_handlers(app: Application, loop):
    """设置信号处理器"""

    # 记录按了几次 Ctrl+C
    signal_count = {'count': 0}

    def signal_handler(signum):
        signal_count['count'] += 1

        if signal_count['count'] == 1:
            logger.info(f'收到信号 {signum}，准备退出... (再次按 Ctrl+C 强制退出)')
            app.running = False
            # 创建一个任务来执行清理
            asyncio.create_task(app.stop())
        else:
            logger.warning(f'收到第 {signal_count["count"]} 次退出信号，强制退出')
            # 强制退出，不等待清理
            import os
            os._exit(0)

    # 在 asyncio 事件循环中正确设置信号处理
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))


async def main():
    """主函数"""
    # 设置日志
    setup_logging()

    logger.info('=' * 60)
    logger.info('Telegram 新闻播报机器人')
    logger.info('=' * 60)

    # 创建应用实例
    app = Application()

    # 获取当前事件循环并设置信号处理
    loop = asyncio.get_running_loop()
    setup_signal_handlers(app, loop)

    # 启动应用
    try:
        await app.start()
    except Exception as e:
        logger.error(f'应用启动失败: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n程序已退出')
        sys.exit(0)
    except Exception as e:
        logger.error(f'程序异常退出: {e}', exc_info=True)
        sys.exit(1)

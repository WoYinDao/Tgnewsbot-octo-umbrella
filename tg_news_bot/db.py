"""
数据库模块 - SQLite 封装
"""
import asyncio
import aiosqlite
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from config import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None

    async def init_db(self):
        """初始化数据库，创建表"""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                msg_id INTEGER,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                category TEXT,
                confidence REAL,
                summary TEXT,
                published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(source, msg_id)
            )
        ''')

        # 频道采集进度表：记录每个频道最后处理到的消息 ID，实现增量采集
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS channel_state (
                channel TEXT PRIMARY KEY,
                last_msg_id INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        ''')

        # 创建索引
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_text_hash ON messages(text_hash)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_published ON messages(published)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON messages(category)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON messages(date)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON messages(created_at)')

        await self.conn.commit()
        logger.info(f'数据库初始化完成: {self.db_path}')

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                await asyncio.wait_for(self.conn.close(), timeout=3.0)
                logger.info('数据库连接已关闭')
            except asyncio.TimeoutError:
                logger.warning('关闭数据库连接超时，强制继续')
            except Exception as e:
                logger.error(f'关闭数据库连接失败: {e}')

    @staticmethod
    def calculate_hash(text: str) -> str:
        """计算文本的哈希值用于去重"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    async def message_exists(self, source: str, msg_id: Optional[int], text: str) -> bool:
        """
        检查消息是否已存在

        同时检查两个维度：
        1. source + msg_id：同一频道的同一条消息
        2. text_hash：其他频道转发的相同内容（跨频道去重，
           避免同一条新闻被多个源频道重复分类和推送）
        """
        text_hash = self.calculate_hash(text)

        if msg_id:
            async with self.conn.execute(
                'SELECT 1 FROM messages WHERE (source = ? AND msg_id = ?) OR text_hash = ? LIMIT 1',
                (source, msg_id, text_hash)
            ) as cursor:
                return await cursor.fetchone() is not None

        async with self.conn.execute(
            'SELECT 1 FROM messages WHERE text_hash = ? LIMIT 1',
            (text_hash,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def insert_message(
        self,
        source: str,
        msg_id: Optional[int],
        date: datetime,
        text: str,
        category: str = 'other',
        confidence: float = 0.0,
        summary: str = ''
    ) -> Optional[int]:
        """
        插入新消息
        返回插入的 ID，如果已存在则返回 None

        依赖 UNIQUE(source, msg_id) 约束 + INSERT OR IGNORE 去重，
        调用方（collector）在 AI 分类前已用 message_exists 做过内容级查重，
        这里不再重复查询。
        """
        text_hash = self.calculate_hash(text)
        created_at = datetime.now().isoformat()

        cursor = await self.conn.execute(
            '''INSERT OR IGNORE INTO messages
            (source, msg_id, date, text, text_hash, category, confidence, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (source, msg_id, date.isoformat(), text, text_hash, category, confidence, summary, created_at)
        )
        await self.conn.commit()

        if cursor.rowcount == 0:
            logger.debug(f'消息已存在（唯一约束），跳过: source={source}, msg_id={msg_id}')
            return None

        logger.info(f'新消息已插入: id={cursor.lastrowid}, source={source}, category={category}')
        return cursor.lastrowid

    async def get_unpublished_messages(
        self,
        min_confidence: float = 0.7,
        max_age_hours: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        获取未发布的高置信度消息

        Args:
            min_confidence: 最低置信度
            max_age_hours: 只取入库时间在最近 N 小时内的消息（防止旧闻轰炸）
            limit: 最多返回 N 条（防止单轮刷屏）
        """
        sql = '''SELECT id, source, msg_id, date, text, category, confidence, summary
            FROM messages
            WHERE published = 0 AND confidence >= ?'''
        params: list = [min_confidence]

        if max_age_hours is not None:
            cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            sql += ' AND created_at >= ?'
            params.append(cutoff)

        sql += ' ORDER BY date DESC'

        if limit is not None:
            sql += ' LIMIT ?'
            params.append(limit)

        async with self.conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'source': row[1],
                    'msg_id': row[2],
                    'date': row[3],
                    'text': row[4],
                    'category': row[5],
                    'confidence': row[6],
                    'summary': row[7]
                }
                for row in rows
            ]

    async def mark_as_published(self, message_id: int):
        """标记消息为已发布"""
        await self.conn.execute(
            'UPDATE messages SET published = 1 WHERE id = ?',
            (message_id,)
        )
        await self.conn.commit()
        logger.info(f'消息已标记为已发布: id={message_id}')

    async def mark_stale_as_skipped(self, max_age_hours: float) -> int:
        """
        把超龄的未发布消息标记为跳过（published = 2）

        用于防止旧闻轰炸：首次运行或长时间停机后，采集到的历史消息
        不应该再当快讯推送，只保留在库里供日报使用。

        Returns:
            被标记的消息数量
        """
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        cursor = await self.conn.execute(
            'UPDATE messages SET published = 2 WHERE published = 0 AND created_at < ?',
            (cutoff,)
        )
        await self.conn.commit()
        if cursor.rowcount:
            logger.info(f'{cursor.rowcount} 条超龄消息已跳过快讯（仅保留供日报）')
        return cursor.rowcount

    async def get_last_msg_id(self, channel: str) -> int:
        """获取频道最后处理到的消息 ID（用于增量采集），无记录返回 0"""
        async with self.conn.execute(
            'SELECT last_msg_id FROM channel_state WHERE channel = ?',
            (channel,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def set_last_msg_id(self, channel: str, msg_id: int):
        """更新频道采集进度（只前进不后退）"""
        await self.conn.execute(
            '''INSERT INTO channel_state (channel, last_msg_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(channel) DO UPDATE SET
                last_msg_id = MAX(last_msg_id, excluded.last_msg_id),
                updated_at = excluded.updated_at''',
            (channel, msg_id, datetime.now().isoformat())
        )
        await self.conn.commit()

    async def cleanup_old_messages(self, retention_days: int) -> int:
        """
        删除超过保留期的旧消息，防止数据库无限膨胀

        Returns:
            删除的消息数量
        """
        if retention_days <= 0:
            return 0

        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        cursor = await self.conn.execute(
            'DELETE FROM messages WHERE created_at < ?',
            (cutoff,)
        )
        await self.conn.commit()

        if cursor.rowcount:
            logger.info(f'数据清理完成：删除 {cursor.rowcount} 条超过 {retention_days} 天的旧消息')
        return cursor.rowcount

    async def get_daily_summary(self, date: str, top_n: int = 10) -> Dict[str, List[Dict]]:
        """
        获取指定日期的日报数据
        按分类聚合，每个分类取 top N（按置信度排序）
        """
        result = {}

        for category in ['politics', 'tech', 'game', 'finance', 'society', 'other']:
            async with self.conn.execute(
                '''SELECT id, source, msg_id, date, text, category, confidence, summary
                FROM messages
                WHERE date LIKE ? AND category = ?
                ORDER BY confidence DESC, date DESC
                LIMIT ?''',
                (f'{date}%', category, top_n)
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    result[category] = [
                        {
                            'id': row[0],
                            'source': row[1],
                            'msg_id': row[2],
                            'date': row[3],
                            'text': row[4],
                            'category': row[5],
                            'confidence': row[6],
                            'summary': row[7]
                        }
                        for row in rows
                    ]

        return result

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {}

        # 总消息数
        async with self.conn.execute('SELECT COUNT(*) FROM messages') as cursor:
            stats['total'] = (await cursor.fetchone())[0]

        # 已发布数
        async with self.conn.execute('SELECT COUNT(*) FROM messages WHERE published = 1') as cursor:
            stats['published'] = (await cursor.fetchone())[0]

        # 各分类数量
        stats['by_category'] = {}
        for category in ['politics', 'tech', 'game', 'finance', 'society', 'other']:
            async with self.conn.execute(
                'SELECT COUNT(*) FROM messages WHERE category = ?',
                (category,)
            ) as cursor:
                stats['by_category'][category] = (await cursor.fetchone())[0]

        return stats


# 全局数据库实例
db = Database()

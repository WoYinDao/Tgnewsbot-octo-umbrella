"""
数据库模块 - SQLite 封装
"""
import aiosqlite
import hashlib
import logging
from datetime import datetime
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

        # 创建索引
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_text_hash ON messages(text_hash)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_published ON messages(published)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON messages(category)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON messages(date)')

        await self.conn.commit()
        logger.info(f'数据库初始化完成: {self.db_path}')

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            await self.conn.close()
            logger.info('数据库连接已关闭')

    @staticmethod
    def calculate_hash(text: str) -> str:
        """计算文本的哈希值用于去重"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    async def message_exists(self, source: str, msg_id: Optional[int], text: str) -> bool:
        """
        检查消息是否已存在
        优先使用 source + msg_id，若 msg_id 为空则使用 text_hash
        """
        if msg_id:
            async with self.conn.execute(
                'SELECT 1 FROM messages WHERE source = ? AND msg_id = ?',
                (source, msg_id)
            ) as cursor:
                result = await cursor.fetchone()
                return result is not None
        else:
            text_hash = self.calculate_hash(text)
            async with self.conn.execute(
                'SELECT 1 FROM messages WHERE text_hash = ?',
                (text_hash,)
            ) as cursor:
                result = await cursor.fetchone()
                return result is not None

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
        """
        # 检查是否已存在
        if await self.message_exists(source, msg_id, text):
            logger.debug(f'消息已存在，跳过: source={source}, msg_id={msg_id}')
            return None

        text_hash = self.calculate_hash(text)
        created_at = datetime.now().isoformat()

        try:
            cursor = await self.conn.execute(
                '''INSERT INTO messages
                (source, msg_id, date, text, text_hash, category, confidence, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (source, msg_id, date.isoformat(), text, text_hash, category, confidence, summary, created_at)
            )
            await self.conn.commit()
            logger.info(f'新消息已插入: id={cursor.lastrowid}, source={source}, category={category}')
            return cursor.lastrowid
        except aiosqlite.IntegrityError as e:
            logger.warning(f'消息插入失败（可能重复）: {e}')
            return None

    async def get_unpublished_messages(self, min_confidence: float = 0.7) -> List[Dict]:
        """获取未发布的高置信度消息"""
        async with self.conn.execute(
            '''SELECT id, source, msg_id, date, text, category, confidence, summary
            FROM messages
            WHERE published = 0 AND confidence >= ?
            ORDER BY date DESC''',
            (min_confidence,)
        ) as cursor:
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

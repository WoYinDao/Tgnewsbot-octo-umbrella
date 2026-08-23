"""
语义去重模块 - 识别不同频道对同一事件的相似报道

两种后端（SEMANTIC_DEDUP_BACKEND 配置）：
- ngram（默认）：本地字符 3-gram Jaccard 相似度，零依赖零费用，
  能识别“同一篇稿子被各频道小幅编辑/删减后转发”的情况
- embedding：OpenAI 兼容向量接口（需 OPENAI_API_KEY），
  能识别“同一事件、完全不同措辞”的报道，向量存库避免重复计算

精确重复（逐字相同）由 db.message_exists 的 text_hash 负责，
本模块只处理“相似但不相同”的情况。
"""
import json
import logging
import math
import re
from typing import Dict, List, Optional, Set, Tuple

from config import (
    SEMANTIC_DEDUP_ENABLED,
    SEMANTIC_DEDUP_BACKEND,
    SEMANTIC_DEDUP_THRESHOLD,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)

# 各后端的默认判重阈值
DEFAULT_THRESHOLDS = {'ngram': 0.55, 'embedding': 0.90}

# 去掉 URL 和空白后再比对，避免“同一新闻但附了不同链接”漏判
_URL_RE = re.compile(r'https?://\S+|t\.me/\S+')
_SPACE_RE = re.compile(r'\s+')


def _normalize(text: str) -> str:
    text = _URL_RE.sub('', text)
    text = _SPACE_RE.sub('', text)
    return text.lower()


def ngram_set(text: str, n: int = 3) -> Set[str]:
    """字符 n-gram 集合"""
    text = _normalize(text)
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard 相似度"""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class SemanticDeduper:
    """语义去重器"""

    def __init__(self):
        self.enabled = SEMANTIC_DEDUP_ENABLED
        self.backend = SEMANTIC_DEDUP_BACKEND if SEMANTIC_DEDUP_BACKEND in ('ngram', 'embedding') else 'ngram'

        if self.backend == 'embedding' and not OPENAI_API_KEY:
            logger.warning('SEMANTIC_DEDUP_BACKEND=embedding 但未配置 OPENAI_API_KEY，回退到 ngram 后端')
            self.backend = 'ngram'

        self.threshold = (
            SEMANTIC_DEDUP_THRESHOLD
            if SEMANTIC_DEDUP_THRESHOLD is not None
            else DEFAULT_THRESHOLDS[self.backend]
        )
        self._openai_client = None

        if self.enabled:
            logger.info(f'语义去重已启用：后端 {self.backend}，阈值 {self.threshold}')
        else:
            logger.info('语义去重已禁用（SEMANTIC_DEDUP_ENABLED=false）')

    async def _embed(self, text: str) -> Optional[List[float]]:
        """调用 OpenAI 兼容接口计算向量，失败返回 None"""
        from openai import AsyncOpenAI

        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

        try:
            response = await self._openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text[:2000],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f'计算向量失败（本条按 ngram 回退比对）: {e}')
            return None

    async def check(self, text: str, recent: List[Dict]) -> Tuple[bool, float, Optional[str]]:
        """
        检查新消息是否与近期消息语义重复

        Args:
            text: 新消息文本
            recent: 近期消息列表，元素为 {'id', 'text', 'embedding'}

        Returns:
            (是否重复, 最高相似度, 本条消息的向量 JSON（供入库，ngram 后端为 None）)
        """
        if not self.enabled or not recent:
            return False, 0.0, None

        embedding_json = None

        if self.backend == 'embedding':
            vector = await self._embed(text)
            if vector is not None:
                embedding_json = json.dumps(vector)
                best = 0.0
                for row in recent:
                    if not row.get('embedding'):
                        continue
                    try:
                        other = json.loads(row['embedding'])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    sim = cosine(vector, other)
                    if sim > best:
                        best = sim
                    if sim >= self.threshold:
                        logger.info(f"语义重复（embedding {sim:.2f}）：与已入库消息 id={row['id']} 相似，跳过")
                        return True, sim, embedding_json
                return False, best, embedding_json
            # 向量计算失败，本条回退 ngram 比对（用 ngram 默认阈值）
            return self._ngram_check(text, recent, DEFAULT_THRESHOLDS['ngram']) + (None,)

        return self._ngram_check(text, recent, self.threshold) + (None,)

    @staticmethod
    def _ngram_check(text: str, recent: List[Dict], threshold: float) -> Tuple[bool, float]:
        grams = ngram_set(text)
        best = 0.0
        for row in recent:
            sim = jaccard(grams, ngram_set(row['text']))
            if sim > best:
                best = sim
            if sim >= threshold:
                logger.info(f"语义重复（ngram {sim:.2f}）：与已入库消息 id={row['id']} 相似，跳过")
                return True, sim
        return False, best

    async def close(self):
        if self._openai_client is not None:
            try:
                await self._openai_client.close()
            except Exception:
                pass
            self._openai_client = None


# 全局去重器实例
deduper = SemanticDeduper()

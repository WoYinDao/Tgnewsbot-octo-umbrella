"""
分类模块 - 规则 + AI 对消息进行分类

AI 后端（按优先级）：
1. Cursor SDK（配置 CURSOR_API_KEY 后启用，使用 Cursor 订阅的模型）
2. OpenAI 或任何 OpenAI 兼容 API（配置 OPENAI_API_KEY）
两者都未配置时只使用规则分类。
"""
import re
import json
import logging
from typing import Dict, Optional, Tuple

from config import (
    BASE_DIR,
    CURSOR_API_KEY,
    CURSOR_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)

logger = logging.getLogger(__name__)


# 规则分类关键词库
RULE_KEYWORDS = {
    'politics': [
        '政府', '国务院', '总统', '主席', '外交', '军事', '国防', '议会', '选举',
        '法律', '法规', '政策', '官员', '部长', '省长', '市长', '议员'
    ],
    'tech': [
        'AI', '人工智能', '机器学习', '深度学习', 'ChatGPT', 'OpenAI', 'Google',
        '苹果', 'iPhone', 'Android', '芯片', '半导体', '5G', '6G', '互联网',
        '区块链', '加密货币', '比特币', '以太坊', '编程', '开源', 'GitHub',
        '科技公司', '软件', '硬件', '云计算', '数据中心'
    ],
    'game': [
        '游戏', '电竞', 'Steam', 'PlayStation', 'Xbox', 'Nintendo', 'Switch',
        '手游', 'PC游戏', '主机游戏', '网游', 'MOBA', 'FPS', 'RPG', 'MMO',
        '游戏开发', '游戏公司', '暴雪', '腾讯游戏', '米哈游', '原神', '王者荣耀'
    ],
    'finance': [
        '股市', '股票', '证券', '基金', '债券', '期货', '外汇', '美联储', '央行',
        '通胀', '利率', '经济', 'GDP', '财报', '上市', 'IPO', '投资', '融资',
        '银行', '金融', '房地产', '楼市', '房价', '贷款', '理财'
    ],
    'society': [
        '社会', '民生', '教育', '医疗', '健康', '疫情', '病毒', '医院', '学校',
        '交通', '事故', '灾害', '地震', '台风', '洪水', '火灾', '环境', '污染',
        '文化', '艺术', '电影', '音乐', '体育', '足球', '篮球', '奥运'
    ]
}

VALID_CATEGORIES = ['politics', 'tech', 'game', 'finance', 'society', 'other']

CLASSIFY_PROMPT = """你是一个专业的新闻编辑。请对以下新闻文本进行分类、生成一句话摘要，并给出新闻价值分。

分类必须是以下之一：politics（政治）、tech（科技）、game（游戏）、finance（财经）、society（社会）、other（其他）

新闻价值分 score 为 0-10 的数字，衡量这条消息值不值得实时推送给读者：
- 8-10：重大突发、影响广泛（重要政策发布、重大事故、行业巨变）
- 4-7：一般新闻，有信息量但非紧急
- 0-3：琐碎内容、旧闻回顾、软文推广、无实质信息

请严格按照以下 JSON 格式返回（不要添加任何其他文字）：
{{"category": "分类", "confidence": 0.85, "summary": "一句话摘要", "score": 7}}

新闻文本：
{text}"""


def _compile_keyword_pattern(keyword: str):
    """英文/数字关键词用词边界匹配，避免 'AI' 误匹配 said/email 等；中文关键词用子串匹配"""
    if re.fullmatch(r'[A-Za-z0-9]+', keyword):
        return re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
    return None


# 预编译英文关键词的词边界正则
_KEYWORD_PATTERNS = {
    category: [(kw, _compile_keyword_pattern(kw)) for kw in keywords]
    for category, keywords in RULE_KEYWORDS.items()
}


def _extract_json(content: str) -> Dict:
    """从模型回复中提取 JSON（容忍代码块标记和前后缀文字）"""
    content = re.sub(r'```(?:json)?\s*|\s*```', '', content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 回复中夹杂了其他文字时，取第一个 {...} 块
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class Classifier:
    """消息分类器"""

    def __init__(self):
        self._cursor_client = None
        self._openai_client = None

        if CURSOR_API_KEY:
            self.backend = 'cursor'
            logger.info(f'AI 分类后端: Cursor SDK (模型: {CURSOR_MODEL})')
        elif OPENAI_API_KEY:
            self.backend = 'openai'
            logger.info(f'AI 分类后端: OpenAI 兼容 API (模型: {OPENAI_MODEL})')
        else:
            self.backend = None
            logger.warning('未配置 CURSOR_API_KEY 或 OPENAI_API_KEY，AI 分类不可用，将只使用规则分类')

    @property
    def enabled(self) -> bool:
        return self.backend is not None

    def rule_classify(self, text: str) -> Tuple[str, float]:
        """
        基于规则的分类

        Returns:
            (category, confidence) 元组
        """
        scores = {category: 0 for category in RULE_KEYWORDS.keys()}

        for category, patterns in _KEYWORD_PATTERNS.items():
            for keyword, pattern in patterns:
                if pattern is not None:
                    if pattern.search(text):
                        scores[category] += 1
                elif keyword in text:
                    scores[category] += 1

        max_score = max(scores.values())

        if max_score == 0:
            return 'other', 0.0

        max_category = max(scores.items(), key=lambda x: x[1])[0]

        # 计算置信度（简单归一化）
        total_score = sum(scores.values())
        confidence = scores[max_category] / total_score if total_score > 0 else 0

        if confidence < 0.5:
            return 'other', confidence

        return max_category, confidence

    async def _ai_call_cursor(self, prompt: str) -> str:
        """通过 Cursor SDK 调用模型，返回文本回复"""
        from cursor_sdk import AsyncClient, LocalAgentOptions

        if self._cursor_client is None:
            self._cursor_client = await AsyncClient.launch_bridge(workspace=str(BASE_DIR))

        # 每次分类创建独立 agent（tools=[] 表示纯文本回答，不给任何工具），
        # 避免复用同一 agent 导致上下文越积越长、费用上涨
        agent = await self._cursor_client.agents.create(
            model=CURSOR_MODEL,
            api_key=CURSOR_API_KEY,
            tools=[],
            local=LocalAgentOptions(cwd=str(BASE_DIR)),
        )
        try:
            run = await agent.send(prompt)
            return await run.text()
        finally:
            await agent.close()

    async def _ai_call_openai(self, prompt: str) -> str:
        """通过 OpenAI 兼容 API 调用模型，返回文本回复"""
        from openai import AsyncOpenAI

        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
            )

        response = await self._openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content or ''

    async def ai_classify(self, text: str) -> Dict:
        """
        使用 AI 进行分类和摘要生成

        Returns:
            {"category": str, "confidence": float, "summary": str, "score": float | None}

        score 是 0-10 的新闻价值分（发布端用它做快讯门槛）；
        AI 不可用或解析失败时为 None，表示未打分，不参与门槛过滤。
        """
        fallback = {
            'category': 'other',
            'confidence': 0.0,
            'summary': text[:100] + ('...' if len(text) > 100 else ''),
            'score': None
        }

        if not self.enabled:
            logger.warning('AI 分类器未初始化，返回默认值')
            return fallback

        prompt = CLASSIFY_PROMPT.format(text=text[:1000])

        try:
            if self.backend == 'cursor':
                content = await self._ai_call_cursor(prompt)
            else:
                content = await self._ai_call_openai(prompt)

            logger.debug(f'AI 返回: {content}')
            result = _extract_json(content)

            if 'category' not in result or 'summary' not in result:
                raise ValueError('返回的 JSON 缺少必要字段')

            if result['category'] not in VALID_CATEGORIES:
                logger.warning(f"无效的分类: {result['category']}，使用默认值 'other'")
                result['category'] = 'other'

            result['confidence'] = max(0.0, min(1.0, float(result.get('confidence', 0.5))))
            result['summary'] = str(result['summary'])

            # 新闻价值分：钐制到 0-10 范围，缺失或非法时视为未打分
            try:
                result['score'] = max(0.0, min(10.0, float(result['score'])))
            except (KeyError, TypeError, ValueError):
                result['score'] = None

            score_text = f"{result['score']:.0f}" if result['score'] is not None else '未打分'
            logger.info(
                f"AI 分类成功: {result['category']} "
                f"(confidence: {result['confidence']:.2f}, score: {score_text})"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f'AI 返回的内容不是有效 JSON: {e}')
        except Exception as e:
            logger.error(f'AI 分类失败: {e}', exc_info=True)

        return fallback

    async def classify(self, text: str) -> Dict:
        """
        综合分类流程：先规则后 AI

        Returns:
            {"category": str, "confidence": float, "summary": str, "score": float | None}

        规则分类不打分（score 为 None），发布端对未打分的消息只看置信度门槛。
        """
        text = text.strip()

        if not text:
            return {
                'category': 'other',
                'confidence': 0.0,
                'summary': '',
                'score': None
            }

        # 1. 先尝试规则分类
        rule_category, rule_confidence = self.rule_classify(text)

        # 2. 如果规则分类置信度高，直接使用
        if rule_confidence >= 0.7:
            logger.info(f'规则分类成功: {rule_category} (confidence: {rule_confidence:.2f})')
            return {
                'category': rule_category,
                'confidence': rule_confidence,
                'summary': text[:100] + ('...' if len(text) > 100 else ''),
                'score': None
            }

        # 3. 否则使用 AI 分类
        logger.info('规则分类置信度较低，使用 AI 分类')
        ai_result = await self.ai_classify(text)

        # 4. 如果 AI 也失败，使用规则分类结果（即使置信度低）
        if ai_result['confidence'] == 0.0 and rule_confidence > 0:
            logger.warning('AI 分类失败，回退到规则分类')
            return {
                'category': rule_category,
                'confidence': rule_confidence,
                'summary': text[:100] + ('...' if len(text) > 100 else ''),
                'score': None
            }

        return ai_result

    async def close(self):
        """释放 AI 客户端资源"""
        if self._cursor_client is not None:
            try:
                await self._cursor_client.aclose()
            except Exception as e:
                logger.warning(f'关闭 Cursor 客户端失败: {e}')
            self._cursor_client = None

        if self._openai_client is not None:
            try:
                await self._openai_client.close()
            except Exception as e:
                logger.warning(f'关闭 OpenAI 客户端失败: {e}')
            self._openai_client = None


# 全局分类器实例
classifier = Classifier()

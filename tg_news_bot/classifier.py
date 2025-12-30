"""
分类模块 - 规则 + AI 对消息进行分类
"""
import re
import json
import logging
from typing import Dict, Tuple
import openai
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

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


class Classifier:
    """消息分类器"""

    def __init__(self):
        self.enabled = False
        if OPENAI_API_KEY:
            openai.api_key = OPENAI_API_KEY
            if OPENAI_BASE_URL and OPENAI_BASE_URL != 'https://api.openai.com/v1':
                openai.api_base = OPENAI_BASE_URL
            self.enabled = True
            logger.info('AI 分类器已初始化')
        else:
            logger.warning('未配置 OPENAI_API_KEY，AI 分类功能将不可用')

    def rule_classify(self, text: str) -> Tuple[str, float]:
        """
        基于规则的分类

        Returns:
            (category, confidence) 元组
        """
        text_lower = text.lower()
        scores = {category: 0 for category in RULE_KEYWORDS.keys()}

        # 计算每个分类的关键词匹配分数
        for category, keywords in RULE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[category] += 1

        # 找出最高分的分类
        max_score = max(scores.values())

        if max_score == 0:
            # 没有匹配任何关键词
            return 'other', 0.0

        max_category = max(scores.items(), key=lambda x: x[1])[0]

        # 计算置信度（简单归一化）
        total_score = sum(scores.values())
        confidence = scores[max_category] / total_score if total_score > 0 else 0

        # 如果置信度太低，标记为不确定
        if confidence < 0.5:
            return 'other', confidence

        return max_category, confidence

    async def ai_classify(self, text: str) -> Dict:
        """
        使用 AI 进行分类和摘要生成

        Returns:
            {"category": str, "confidence": float, "summary": str}
        """
        if not self.enabled:
            logger.warning('AI 分类器未初始化，返回默认值')
            return {
                'category': 'other',
                'confidence': 0.0,
                'summary': text[:100] + ('...' if len(text) > 100 else '')
            }

        # 构建 prompt（适配 openai 0.10.5 的 Completion API）
        prompt = f"""你是一个专业的新闻分类助手。请对以下新闻文本进行分类，并生成一句话摘要。

分类必须是以下之一：politics（政治）、tech（科技）、game（游戏）、finance（财经）、society（社会）、other（其他）

请严格按照以下 JSON 格式返回（不要添加任何其他文字）：
{{"category": "分类", "confidence": 0.85, "summary": "一句话摘要"}}

新闻文本：
{text[:1000]}

JSON返回："""

        try:
            # openai 0.10.5 没有 ChatCompletion 和异步方法，使用 Completion + run_in_executor
            import asyncio
            loop = asyncio.get_event_loop()

            # 使用旧式 Completion API
            response = await loop.run_in_executor(
                None,
                lambda: openai.Completion.create(
                    engine=OPENAI_MODEL if OPENAI_MODEL.startswith('text-') else 'text-davinci-003',
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=200,
                    stop=["\n\n"]
                )
            )

            content = response.choices[0].text.strip()
            logger.debug(f'AI 返回: {content}')

            # 尝试解析 JSON
            # 去除可能的 markdown 代码块标记
            content = re.sub(r'```json\s*|\s*```', '', content)

            result = json.loads(content)

            # 验证字段
            if 'category' not in result or 'summary' not in result:
                raise ValueError('返回的 JSON 缺少必要字段')

            # 验证分类
            valid_categories = ['politics', 'tech', 'game', 'finance', 'society', 'other']
            if result['category'] not in valid_categories:
                logger.warning(f"无效的分类: {result['category']}，使用默认值 'other'")
                result['category'] = 'other'

            # 确保 confidence 字段存在
            if 'confidence' not in result:
                result['confidence'] = 0.5

            # 确保 confidence 在 0-1 之间
            result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))

            logger.info(f"AI 分类成功: {result['category']} (confidence: {result['confidence']:.2f})")
            return result

        except json.JSONDecodeError as e:
            logger.error(f'AI 返回的内容不是有效 JSON: {e}')
        except Exception as e:
            logger.error(f'AI 分类失败: {e}', exc_info=True)

        # 失败回退
        return {
            'category': 'other',
            'confidence': 0.0,
            'summary': text[:100] + ('...' if len(text) > 100 else '')
        }

    async def classify(self, text: str) -> Dict:
        """
        综合分类流程：先规则后 AI

        Returns:
            {"category": str, "confidence": float, "summary": str}
        """
        # 文本清洗
        text = text.strip()

        if not text:
            return {
                'category': 'other',
                'confidence': 0.0,
                'summary': ''
            }

        # 1. 先尝试规则分类
        rule_category, rule_confidence = self.rule_classify(text)

        # 2. 如果规则分类置信度高，直接使用
        if rule_confidence >= 0.7:
            logger.info(f'规则分类成功: {rule_category} (confidence: {rule_confidence:.2f})')
            return {
                'category': rule_category,
                'confidence': rule_confidence,
                'summary': text[:100] + ('...' if len(text) > 100 else '')
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
                'summary': text[:100] + ('...' if len(text) > 100 else '')
            }

        return ai_result


# 全局分类器实例
classifier = Classifier()

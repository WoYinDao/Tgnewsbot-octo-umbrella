"""
模板模块 - 日报/快讯排版模板
"""
from datetime import datetime
from typing import Dict, List


# 分类中英文映射
CATEGORY_NAMES = {
    'politics': '政治',
    'tech': '科技',
    'game': '游戏',
    'finance': '财经',
    'society': '社会',
    'other': '其他'
}


def format_breaking_news(message: Dict) -> str:
    """
    格式化快讯消息

    Args:
        message: 消息字典，包含 category, summary, text, source, msg_id 等字段

    Returns:
        格式化后的 Markdown 文本
    """
    category_name = CATEGORY_NAMES.get(message['category'], '未分类')
    confidence = message.get('confidence', 0)
    summary = message.get('summary', '').strip()
    text = message.get('text', '').strip()
    source = message.get('source', '')
    msg_id = message.get('msg_id')

    # 构建消息链接（如果有 msg_id）
    link = ''
    if msg_id and source:
        # 移除 @ 符号（如果有）
        source_clean = source.lstrip('@')
        if source_clean.startswith('-100'):
            # 私有频道 ID，无法直接构造链接
            link = ''
        else:
            # 公开频道可以构造链接
            link = f'https://t.me/{source_clean}/{msg_id}'

    # 格式化
    lines = [
        f'🔔 **快讯 - {category_name}**',
        '',
        f'**摘要：** {summary}' if summary else '',
        '',
        f'置信度：{confidence:.2f}',
        '',
        '---',
        '',
        text[:500] + ('...' if len(text) > 500 else ''),  # 限制长度
    ]

    if link:
        lines.append('')
        lines.append(f'[查看原文]({link})')

    return '\n'.join([line for line in lines if line is not None])


def format_daily_report(date: str, data: Dict[str, List[Dict]]) -> str:
    """
    格式化日报

    Args:
        date: 日期字符串 (YYYY-MM-DD)
        data: 按分类聚合的消息字典

    Returns:
        格式化后的 Markdown 文本
    """
    lines = [
        f'📰 **每日新闻日报 - {date}**',
        '',
        f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '=' * 40,
        ''
    ]

    # 统计
    total_count = sum(len(messages) for messages in data.values())
    lines.append(f'今日共收录 **{total_count}** 条新闻')
    lines.append('')

    # 按分类输出
    for category in ['politics', 'tech', 'game', 'finance', 'society', 'other']:
        if category not in data or not data[category]:
            continue

        messages = data[category]
        category_name = CATEGORY_NAMES[category]

        lines.append('')
        lines.append(f'## 📌 {category_name} ({len(messages)} 条)')
        lines.append('')

        for idx, msg in enumerate(messages, 1):
            summary = msg.get('summary', '').strip()
            text = msg.get('text', '').strip()
            confidence = msg.get('confidence', 0)
            source = msg.get('source', '')
            msg_id = msg.get('msg_id')

            # 构建链接
            link = ''
            if msg_id and source:
                source_clean = source.lstrip('@')
                if not source_clean.startswith('-100'):
                    link = f'https://t.me/{source_clean}/{msg_id}'

            lines.append(f'**{idx}. {summary}**' if summary else f'**{idx}. {text[:50]}...**')
            lines.append(f'   置信度：{confidence:.2f}')

            if link:
                lines.append(f'   [原文链接]({link})')

            lines.append('')

    lines.append('')
    lines.append('=' * 40)
    lines.append('')
    lines.append('_本日报由 AI 自动生成_')

    return '\n'.join(lines)


def truncate_message(text: str, max_length: int = 4000) -> str:
    """
    截断过长的消息

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    # 预留空间给提示信息
    footer = '\n\n...(消息过长已截断)'
    available_length = max_length - len(footer)

    return text[:available_length] + footer

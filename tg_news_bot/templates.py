"""
模板模块 - 日报/快讯排版模板

使用 Telegram HTML 解析模式。所有动态内容（正文、摘要）都经过
html.escape 转义，避免消息中的特殊字符导致 Telegram 解析失败。
"""
import html
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


def _build_link(source: str, msg_id) -> str:
    """构建消息原文链接，私有频道（-100 开头）无法构造链接"""
    if not msg_id or not source:
        return ''
    source_clean = source.lstrip('@')
    if source_clean.startswith('-100') or source_clean.lstrip('-').isdigit():
        return ''
    return f'https://t.me/{source_clean}/{msg_id}'


def format_breaking_news(message: Dict) -> str:
    """
    格式化快讯消息

    Args:
        message: 消息字典，包含 category, summary, text, source, msg_id 等字段

    Returns:
        格式化后的 HTML 文本
    """
    category_name = CATEGORY_NAMES.get(message['category'], '未分类')
    confidence = message.get('confidence', 0)
    summary = html.escape(message.get('summary', '').strip())
    text = message.get('text', '').strip()
    text = html.escape(text[:500] + ('...' if len(text) > 500 else ''))
    link = _build_link(message.get('source', ''), message.get('msg_id'))

    lines = [
        f'\U0001f514 <b>快讯 - {category_name}</b>',
        '',
    ]

    if summary:
        lines.append(f'<b>摘要：</b> {summary}')
        lines.append('')

    lines.extend([
        f'置信度：{confidence:.2f}',
        '',
        '—————',
        '',
        text,
    ])

    if link:
        lines.append('')
        lines.append(f'<a href="{link}">查看原文</a>')

    return '\n'.join(lines)


def format_daily_report(date: str, data: Dict[str, List[Dict]]) -> str:
    """
    格式化日报

    Args:
        date: 日期字符串 (YYYY-MM-DD)
        data: 按分类聚合的消息字典

    Returns:
        格式化后的 HTML 文本
    """
    lines = [
        f'\U0001f4f0 <b>每日新闻日报 - {date}</b>',
        '',
        f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '=' * 30,
        ''
    ]

    # 统计
    total_count = sum(len(messages) for messages in data.values())
    lines.append(f'今日共收录 <b>{total_count}</b> 条新闻')
    lines.append('')

    # 按分类输出
    for category in ['politics', 'tech', 'game', 'finance', 'society', 'other']:
        if category not in data or not data[category]:
            continue

        messages = data[category]
        category_name = CATEGORY_NAMES[category]

        lines.append('')
        lines.append(f'\U0001f4cc <b>{category_name}</b> ({len(messages)} 条)')
        lines.append('')

        for idx, msg in enumerate(messages, 1):
            summary = html.escape(msg.get('summary', '').strip())
            text = html.escape(msg.get('text', '').strip()[:50])
            confidence = msg.get('confidence', 0)
            link = _build_link(msg.get('source', ''), msg.get('msg_id'))

            title = summary if summary else f'{text}...'
            lines.append(f'<b>{idx}. {title}</b>')
            lines.append(f'   置信度：{confidence:.2f}')

            if link:
                lines.append(f'   <a href="{link}">原文链接</a>')

            lines.append('')

    lines.append('')
    lines.append('=' * 30)
    lines.append('')
    lines.append('<i>本日报由 AI 自动生成</i>')

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

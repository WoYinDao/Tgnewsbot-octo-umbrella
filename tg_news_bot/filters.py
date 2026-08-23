"""
过滤引擎 - 广告屏蔽 + 关注规则

规则文件（可直接编辑，无需改代码）：
- config/blocklist.txt   屏蔽规则：命中任意一行的消息直接丢弃（去广告）
- config/whitelist.txt   关注规则：非空时，只保留命中至少一行的消息（留空 = 全部保留）

每行是一个规则组，词之间用空格分隔，支持三种记号（借鉴 TrendRadar 的语法）：
- 普通词         组内多个普通词是“或”关系，出现任意一个即可
- +必须词        必须同时出现
- !排除词        出现则该组不匹配

示例（blocklist.txt）：
    优惠码 邀请码 +注册     -> 消息同时含“注册”且含“优惠码”或“邀请码”时屏蔽
    博彩                    -> 消息含“博彩”即屏蔽

纯英文/数字的词按整词匹配（不区分大小写），中文按子串匹配。
"""
import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from config import BASE_DIR

logger = logging.getLogger(__name__)

RULES_DIR = BASE_DIR / 'config'
BLOCKLIST_FILE = RULES_DIR / 'blocklist.txt'
WHITELIST_FILE = RULES_DIR / 'whitelist.txt'


def _token_matches(token: str, text: str) -> bool:
    """纯英文/数字整词匹配（不区分大小写），其余子串匹配"""
    if re.fullmatch(r'[A-Za-z0-9]+', token):
        return re.search(r'\b' + re.escape(token) + r'\b', text, re.IGNORECASE) is not None
    return token in text


class RuleGroup:
    """一行规则：普通词（或）+ 必须词（与）+ 排除词（非）"""

    def __init__(self, line: str):
        self.raw = line
        self.any_words: List[str] = []
        self.must_words: List[str] = []
        self.not_words: List[str] = []

        for token in line.split():
            if token.startswith('+') and len(token) > 1:
                self.must_words.append(token[1:])
            elif token.startswith('!') and len(token) > 1:
                self.not_words.append(token[1:])
            else:
                self.any_words.append(token)

    @property
    def valid(self) -> bool:
        # 只有排除词的规则组无意义（会匹配一切），视为无效
        return bool(self.any_words or self.must_words)

    def matches(self, text: str) -> bool:
        for w in self.not_words:
            if _token_matches(w, text):
                return False
        for w in self.must_words:
            if not _token_matches(w, text):
                return False
        if self.any_words:
            return any(_token_matches(w, text) for w in self.any_words)
        return True  # 只有必须词的组，必须词全命中即匹配


def _load_rules(path: Path) -> List[RuleGroup]:
    """读取规则文件，忽略空行和 # 注释"""
    if not path.exists():
        return []

    groups = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        group = RuleGroup(line)
        if group.valid:
            groups.append(group)
        else:
            logger.warning(f'忽略无效规则（只有排除词）: {line}')
    return groups


class MessageFilter:
    """消息过滤器：先查屏蔽规则，再查关注规则"""

    def __init__(self):
        self.blocklist: List[RuleGroup] = []
        self.whitelist: List[RuleGroup] = []
        self.reload()

    def reload(self) -> Tuple[int, int]:
        """重新加载规则文件，返回 (屏蔽规则数, 关注规则数)"""
        self.blocklist = _load_rules(BLOCKLIST_FILE)
        self.whitelist = _load_rules(WHITELIST_FILE)
        logger.info(f'过滤规则已加载：屏蔽 {len(self.blocklist)} 条，关注 {len(self.whitelist)} 条')
        return len(self.blocklist), len(self.whitelist)

    def check(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        检查消息是否放行

        Returns:
            (是否放行, 拦截原因或 None)
        """
        for group in self.blocklist:
            if group.matches(text):
                return False, f'命中屏蔽规则: {group.raw}'

        if self.whitelist:
            if not any(group.matches(text) for group in self.whitelist):
                return False, '未命中任何关注规则'

        return True, None


# 全局过滤器实例
message_filter = MessageFilter()

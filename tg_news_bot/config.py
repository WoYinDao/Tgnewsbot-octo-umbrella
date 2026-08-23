"""
配置模块 - 读取环境变量与配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# 加载 .env 文件
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent

# 日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = BASE_DIR / 'logs' / 'app.log'

# Telethon 采集端配置
TELETHON_API_ID = os.getenv('TELETHON_API_ID')
TELETHON_API_HASH = os.getenv('TELETHON_API_HASH')
TELETHON_SESSION = os.getenv('TELETHON_SESSION', 'tg_news_session')
TELETHON_PHONE = os.getenv('TELETHON_PHONE', '')  # 首次登录需要

# 采集源配置（逗号分隔）
SOURCE_CHANNELS = os.getenv('SOURCE_CHANNELS', '').split(',')
SOURCE_CHANNELS = [s.strip() for s in SOURCE_CHANNELS if s.strip()]

# 采集配置
FETCH_LIMIT = int(os.getenv('FETCH_LIMIT', '50'))  # 每次采集最多 N 条
FETCH_INTERVAL_MINUTES = int(os.getenv('FETCH_INTERVAL_MINUTES', '10'))  # 采集间隔

# 发布端配置
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TARGET_CHAT_ID = os.getenv('TARGET_CHAT_ID')  # 目标频道 ID（如 -1001234567890）

# AI 分类配置
# 后端一：Cursor SDK（优先，配置 CURSOR_API_KEY 后启用）
CURSOR_API_KEY = os.getenv('CURSOR_API_KEY')
CURSOR_MODEL = os.getenv('CURSOR_MODEL', 'composer-2.5')

# 后端二：OpenAI 或任何 OpenAI 兼容 API
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

AI_CONFIDENCE_THRESHOLD = float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7'))

# 分类配置
CATEGORIES = ['politics', 'tech', 'game', 'finance', 'society', 'other']

# 数据库配置
DB_PATH = BASE_DIR / 'news.db'

# 日报配置
DAILY_REPORT_TIME = os.getenv('DAILY_REPORT_TIME', '21:00')  # 每天日报时间
DAILY_REPORT_TIMEZONE = os.getenv('DAILY_REPORT_TIMEZONE', 'Asia/Taipei')
DAILY_REPORT_TOP_N = int(os.getenv('DAILY_REPORT_TOP_N', '10'))  # 每个分类取 top N

# 快讯限流配置（防止刷屏 / 旧闻轰炸）
BREAKING_MAX_PER_ROUND = int(os.getenv('BREAKING_MAX_PER_ROUND', '5'))  # 每轮最多发几条快讯
BREAKING_MAX_AGE_HOURS = float(os.getenv('BREAKING_MAX_AGE_HOURS', '6'))  # 只推送入库不超过 N 小时的消息
BREAKING_MIN_SCORE = float(os.getenv('BREAKING_MIN_SCORE', '6'))  # AI 新闻价值分门槛（0-10，未打分的消息不受此限制）

# 语义去重配置（识别不同频道对同一事件的相似报道）
SEMANTIC_DEDUP_ENABLED = os.getenv('SEMANTIC_DEDUP_ENABLED', 'true').lower() in ('1', 'true', 'yes')
# 后端：ngram = 本地字符 n-gram 相似度（免费，默认）；embedding = OpenAI 兼容向量接口（需 OPENAI_API_KEY）
SEMANTIC_DEDUP_BACKEND = os.getenv('SEMANTIC_DEDUP_BACKEND', 'ngram')
# 判重阈值：留空则按后端取默认（ngram 0.55 / embedding 0.90）
_dedup_threshold = os.getenv('SEMANTIC_DEDUP_THRESHOLD', '').strip()
SEMANTIC_DEDUP_THRESHOLD = float(_dedup_threshold) if _dedup_threshold else None
SEMANTIC_DEDUP_WINDOW_HOURS = float(os.getenv('SEMANTIC_DEDUP_WINDOW_HOURS', '48'))  # 只和最近 N 小时的消息比对
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')

# Bot 管理命令：允许使用命令的 Telegram 用户 ID（逗号分隔，留空则禁用命令功能）
ADMIN_USER_IDS = [
    int(x.strip()) for x in os.getenv('ADMIN_USER_IDS', '').split(',') if x.strip().lstrip('-').isdigit()
]

# 数据保留配置
DB_RETENTION_DAYS = int(os.getenv('DB_RETENTION_DAYS', '30'))  # 消息保留天数，0 = 永久保留

# 消息配置
MESSAGE_MAX_LENGTH = int(os.getenv('MESSAGE_MAX_LENGTH', '4000'))  # Telegram 限制 4096


def validate_config():
    """验证必要的配置项"""
    errors = []

    if not TELETHON_API_ID:
        errors.append('缺少 TELETHON_API_ID')
    if not TELETHON_API_HASH:
        errors.append('缺少 TELETHON_API_HASH')
    if not TELEGRAM_BOT_TOKEN:
        errors.append('缺少 TELEGRAM_BOT_TOKEN')
    if not TARGET_CHAT_ID:
        errors.append('缺少 TARGET_CHAT_ID')
    if not SOURCE_CHANNELS:
        errors.append('缺少 SOURCE_CHANNELS（采集源）')

    if errors:
        raise ValueError(f"配置错误：{', '.join(errors)}")

    logging.info('配置验证通过')
    return True


def setup_logging():
    """设置日志"""
    # 确保日志目录存在
    LOG_FILE.parent.mkdir(exist_ok=True)

    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 配置根日志器
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 控制台输出
            logging.StreamHandler(),
            # 文件输出（追加模式）
            logging.FileHandler(LOG_FILE, encoding='utf-8')
        ]
    )

    # 设置第三方库日志级别（减少噪音）
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.INFO)

    logging.info('日志系统初始化完成')

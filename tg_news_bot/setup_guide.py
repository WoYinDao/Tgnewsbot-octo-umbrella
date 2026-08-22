#!/usr/bin/env python3
"""
配置向导 - 帮助用户创建 .env 文件
"""
import os
import sys
from pathlib import Path


def print_header(text):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step, text):
    """打印步骤"""
    print(f"\n[步骤 {step}] {text}")
    print("-" * 60)


def get_input(prompt, default='', required=True):
    """获取用户输入"""
    if default:
        prompt = f"{prompt} [{default}]"
    prompt += ": "

    while True:
        value = input(prompt).strip()
        if not value and default:
            return default
        if not value and required:
            print("\u274c 这是必填项，请输入！")
            continue
        return value


def main():
    print_header("Telegram 新闻播报机器人 - 配置向导")

    env_file = Path(__file__).parent / '.env'

    if env_file.exists():
        print(f"\u26a0\ufe0f  检测到已存在的 .env 文件")
        overwrite = input("是否覆盖？(y/N): ").strip().lower()
        if overwrite != 'y':
            print("已取消配置")
            sys.exit(0)

    config = {}

    # 1. Telethon 配置
    print_step(1, "Telethon 配置")
    print("请访问 https://my.telegram.org/apps 获取 API 凭证")
    config['TELETHON_API_ID'] = get_input("API ID")
    config['TELETHON_API_HASH'] = get_input("API Hash")
    config['TELETHON_PHONE'] = get_input("手机号（带国家码，如 +8613800138000）")
    config['TELETHON_SESSION'] = get_input("Session 名称", default='tg_news_session', required=False)

    # 2. 采集源配置
    print_step(2, "采集源配置")
    print("请输入要采集的频道（用逗号分隔，如：@channel1,@channel2）")
    config['SOURCE_CHANNELS'] = get_input("频道列表")
    config['FETCH_LIMIT'] = get_input("每次采集条数", default='50', required=False)
    config['FETCH_INTERVAL_MINUTES'] = get_input("采集间隔（分钟）", default='10', required=False)

    # 3. Bot 配置
    print_step(3, "Telegram Bot 配置")
    print("请访问 @BotFather 创建 Bot 并获取 Token")
    config['TELEGRAM_BOT_TOKEN'] = get_input("Bot Token")

    print("\n如何获取目标频道 ID：")
    print("方法 1: 使用 @userinfobot，将其添加到频道后会显示 ID")
    print("方法 2: 使用 @raw_data_bot，转发频道消息给它会显示 ID")
    print("注意：频道 ID 必须是负数（如 -1001234567890）")
    config['TARGET_CHAT_ID'] = get_input("目标频道 ID")

    # 4. AI 配置
    print_step(4, "AI 配置（可选）")
    print("支持两种 AI 后端：")
    print("  1) Cursor SDK - 使用 Cursor 订阅的模型（https://cursor.com/dashboard/api 获取 Key）")
    print("  2) OpenAI 兼容 API - OpenAI / DeepSeek / OpenRouter / Ollama 等")
    use_ai = input("是否使用 AI 分类？(Y/n): ").strip().lower()
    if use_ai != 'n':
        backend = get_input("选择后端 (1=Cursor, 2=OpenAI 兼容)", default='1', required=False)
        if backend == '1':
            config['CURSOR_API_KEY'] = get_input("Cursor API Key", required=False)
            if config.get('CURSOR_API_KEY'):
                config['CURSOR_MODEL'] = get_input("模型名称",
                                                    default='composer-2.5',
                                                    required=False)
        else:
            config['OPENAI_API_KEY'] = get_input("API Key", required=False)
            if config.get('OPENAI_API_KEY'):
                config['OPENAI_BASE_URL'] = get_input("API Base URL",
                                                       default='https://api.openai.com/v1',
                                                       required=False)
                config['OPENAI_MODEL'] = get_input("模型名称",
                                                    default='gpt-4o-mini',
                                                    required=False)
        config['AI_CONFIDENCE_THRESHOLD'] = get_input("置信度阈值 (0-1)",
                                                       default='0.7',
                                                       required=False)

    # 5. 日报配置
    print_step(5, "日报配置")
    config['DAILY_REPORT_TIME'] = get_input("日报发布时间（HH:MM）", default='21:00', required=False)
    config['DAILY_REPORT_TIMEZONE'] = get_input("时区", default='Asia/Shanghai', required=False)
    config['DAILY_REPORT_TOP_N'] = get_input("每个分类取 top N", default='10', required=False)

    # 6. 其他配置
    print_step(6, "其他配置")
    config['LOG_LEVEL'] = get_input("日志级别 (DEBUG/INFO/WARNING/ERROR)",
                                     default='INFO',
                                     required=False)
    config['MESSAGE_MAX_LENGTH'] = get_input("消息最大长度", default='4000', required=False)

    # 生成 .env 文件
    print_header("生成配置文件")

    with open(env_file, 'w', encoding='utf-8') as f:
        f.write("# Telegram 新闻播报机器人配置\n")
        f.write(f"# 生成时间: {__import__('datetime').datetime.now()}\n\n")

        for key, value in config.items():
            if value:
                f.write(f"{key}={value}\n")

    print(f"\u2705 配置文件已生成: {env_file}")
    print("\n下一步：")
    print("1. 检查并编辑 .env 文件（如有需要）")
    print("2. 运行 python app.py 启动机器人")
    print("3. 首次运行需要输入 Telegram 验证码")
    print("\n\u26a0\ufe0f  重要提醒：")
    print("1. 请将 Bot 添加到目标频道，并授予管理员权限")
    print("2. 确保 Bot 有发送消息的权限")
    print("3. 不要将 .env 文件提交到 git")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消配置")
        sys.exit(1)
    except Exception as e:
        print(f"\n\u274c 配置失败: {e}")
        sys.exit(1)

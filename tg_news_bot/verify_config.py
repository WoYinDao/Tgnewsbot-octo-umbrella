#!/usr/bin/env python3
"""
配置验证工具 - 检查 Bot 配置是否正确
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


async def verify_bot_config():
    """验证 Bot 配置"""
    print("=" * 60)
    print("  Telegram Bot 配置验证")
    print("=" * 60)

    try:
        from config import TELEGRAM_BOT_TOKEN, TARGET_CHAT_ID
        from telegram import Bot
        from telegram.error import TelegramError

        if not TELEGRAM_BOT_TOKEN:
            print("\n\u274c TELEGRAM_BOT_TOKEN 未配置")
            return False

        if not TARGET_CHAT_ID:
            print("\n\u274c TARGET_CHAT_ID 未配置")
            return False

        print(f"\n\u2713 TELEGRAM_BOT_TOKEN: {'*' * 10}{TELEGRAM_BOT_TOKEN[-10:]}")
        print(f"\u2713 TARGET_CHAT_ID: {TARGET_CHAT_ID}")

        # 测试 Bot 连接
        print("\n[1/3] 测试 Bot 连接...")
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.initialize()
            bot_info = await bot.get_me()
            print(f"\u2705 Bot 连接成功: @{bot_info.username}")
            print(f"    Bot ID: {bot_info.id}")
            print(f"    Bot 名称: {bot_info.first_name}")
        except TelegramError as e:
            print(f"\u274c Bot 连接失败: {e}")
            print("   请检查 TELEGRAM_BOT_TOKEN 是否正确")
            return False

        # 测试目标频道访问
        print(f"\n[2/3] 测试目标频道访问 (ID: {TARGET_CHAT_ID})...")
        try:
            chat = await bot.get_chat(chat_id=TARGET_CHAT_ID)
            print(f"\u2705 目标频道访问成功")
            print(f"    频道标题: {chat.title if hasattr(chat, 'title') else 'N/A'}")
            print(f"    频道类型: {chat.type}")
            if hasattr(chat, 'username') and chat.username:
                print(f"    频道 @{chat.username}")
        except TelegramError as e:
            print(f"\u274c 目标频道访问失败: {e}")
            print("\n   可能的原因：")
            print("   1. TARGET_CHAT_ID 配置错误")
            print("   2. Bot 未被添加到该频道")
            print("   3. Bot 不是频道管理员")
            print("\n   解决方法：")
            print("   1. 确认 TARGET_CHAT_ID 格式正确（必须是负数，如 -1001234567890）")
            print(f"   2. 将 @{bot_info.username} 添加到目标频道")
            print("   3. 授予 Bot 管理员权限（至少需要发送消息权限）")
            return False

        # 测试发送消息
        print(f"\n[3/3] 测试发送消息...")
        test_message = "\U0001f916 配置验证测试消息\n\n这是一条测试消息，用于验证 Bot 配置是否正确。如果你看到这条消息，说明配置成功！"

        send_test = input("是否发送测试消息到目标频道？(Y/n): ").strip().lower()
        if send_test != 'n':
            try:
                message = await bot.send_message(
                    chat_id=TARGET_CHAT_ID,
                    text=test_message
                )
                print(f"\u2705 测试消息发送成功")
                print(f"    消息 ID: {message.message_id}")
                print(f"    发送时间: {message.date}")
            except TelegramError as e:
                print(f"\u274c 测试消息发送失败: {e}")
                print("\n   可能的原因：")
                print("   1. Bot 没有发送消息的权限")
                print("   2. 频道设置限制了消息发送")
                print("\n   解决方法：")
                print("   1. 确保 Bot 是频道管理员")
                print("   2. 在频道设置中授予 Bot 发送消息权限")
                return False
        else:
            print("\u26a0\ufe0f  跳过发送测试")

        print("\n" + "=" * 60)
        print("\u2705 所有验证通过！Bot 配置正确")
        print("=" * 60)
        return True

    except ImportError as e:
        print(f"\n\u274c 导入失败: {e}")
        print("   请确保已安装所有依赖：pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"\n\u274c 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_telethon_config():
    """验证 Telethon 配置"""
    print("\n" + "=" * 60)
    print("  Telethon 配置验证")
    print("=" * 60)

    try:
        from config import TELETHON_API_ID, TELETHON_API_HASH, SOURCE_CHANNELS

        if not TELETHON_API_ID:
            print("\n\u274c TELETHON_API_ID 未配置")
            return False

        if not TELETHON_API_HASH:
            print("\n\u274c TELETHON_API_HASH 未配置")
            return False

        print(f"\n\u2713 TELETHON_API_ID: {TELETHON_API_ID}")
        print(f"\u2713 TELETHON_API_HASH: {'*' * 10}{TELETHON_API_HASH[-10:]}")
        print(f"\u2713 SOURCE_CHANNELS: {', '.join(SOURCE_CHANNELS) if SOURCE_CHANNELS else '未配置'}")

        if not SOURCE_CHANNELS:
            print("\n\u26a0\ufe0f  SOURCE_CHANNELS 未配置，将无法采集消息")

        print("\n\u2705 Telethon 配置正确")
        print("   首次运行需要登录 Telegram 账号")

        return True

    except ImportError as e:
        print(f"\n\u274c 导入失败: {e}")
        return False
    except Exception as e:
        print(f"\n\u274c 验证失败: {e}")
        return False


async def verify_ai_config():
    """验证 AI 配置"""
    print("\n" + "=" * 60)
    print("  AI 配置验证")
    print("=" * 60)

    try:
        from config import (
            CURSOR_API_KEY, CURSOR_MODEL,
            OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
        )

        if CURSOR_API_KEY:
            print(f"\n\u2713 CURSOR_API_KEY: {'*' * 10}{CURSOR_API_KEY[-6:]}")
            print(f"\u2713 CURSOR_MODEL: {CURSOR_MODEL}")
            print("\n\u2705 AI 分类后端: Cursor SDK")
            return True

        if OPENAI_API_KEY:
            print(f"\n\u2713 OPENAI_API_KEY: {'*' * 10}{OPENAI_API_KEY[-6:]}")
            print(f"\u2713 OPENAI_BASE_URL: {OPENAI_BASE_URL}")
            print(f"\u2713 OPENAI_MODEL: {OPENAI_MODEL}")
            print("\n\u2705 AI 分类后端: OpenAI 兼容 API")
            return True

        print("\n\u26a0\ufe0f  未配置 CURSOR_API_KEY 或 OPENAI_API_KEY")
        print("   AI 分类功能将不可用，将只使用规则分类")
        return True

    except Exception as e:
        print(f"\n\u274c 验证失败: {e}")
        return False


async def main():
    """主函数"""
    print("\n\U0001f50d 开始验证配置...\n")

    results = []

    # 验证 Telethon 配置
    results.append(await verify_telethon_config())

    # 验证 Bot 配置
    results.append(await verify_bot_config())

    # 验证 AI 配置
    results.append(await verify_ai_config())

    # 总结
    print("\n" + "=" * 60)
    if all(results):
        print("\U0001f389 所有配置验证通过！可以运行 python app.py 启动机器人")
    else:
        print("\u26a0\ufe0f  部分配置验证失败，请根据上述提示修正")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n已取消验证")
        sys.exit(1)
    except Exception as e:
        print(f"\n\u274c 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

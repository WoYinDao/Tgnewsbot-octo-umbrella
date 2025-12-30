#!/bin/bash
# 快速启动脚本

cd "$(dirname "$0")/tg_news_bot" || exit 1

echo "=========================================="
echo "  Telegram 新闻机器人 - 快速配置"
echo "=========================================="
echo ""
echo "当前目录: $(pwd)"
echo ""
echo "请选择操作："
echo "  1) 创建配置文件 (.env)"
echo "  2) 验证配置"
echo "  3) 启动机器人"
echo "  4) 退出"
echo ""
read -p "请输入选项 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "运行配置向导..."
        python3 setup_guide.py
        ;;
    2)
        echo ""
        echo "验证配置..."
        python3 verify_config.py
        ;;
    3)
        echo ""
        echo "启动机器人..."
        python3 app.py
        ;;
    4)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac

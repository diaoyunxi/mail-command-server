#!/bin/bash
# MailCommandBot 服务管理脚本

SERVICE_NAME="mail-command-server"
PROJECT_DIR="/root/mail-command-server"

case "$1" in
    start)
        systemctl start $SERVICE_NAME
        echo "服务已启动"
        ;;
    stop)
        systemctl stop $SERVICE_NAME
        echo "服务已停止"
        ;;
    restart)
        systemctl restart $SERVICE_NAME
        echo "服务已重启"
        ;;
    status)
        systemctl status $SERVICE_NAME --no-pager
        ;;
    logs)
        journalctl -u $SERVICE_NAME -f --no-pager
        ;;
    enable)
        systemctl enable $SERVICE_NAME
        echo "已启用开机自启动"
        ;;
    disable)
        systemctl disable $SERVICE_NAME
        echo "已禁用开机自启动"
        ;;
    test)
        cd $PROJECT_DIR && source venv/bin/activate && python -m pytest tests/ -v
        ;;
    update)
        cd $PROJECT_DIR && git pull origin main
        systemctl restart $SERVICE_NAME
        echo "已更新并重启服务"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs|enable|disable|test|update}"
        exit 1
        ;;
esac

exit 0

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件命令执行服务器主入口

功能：
    支持两种运行模式：
    1. 自建 SMTP 服务器模式：在本地端口监听邮件（默认 9930）
    2. POP3/IMAP 拉取模式：从已有邮件服务器主动拉取邮件

    自动解析收到的邮件，提取以 @ 开头的命令并执行，
    将执行结果通过邮件回复给发件人。

使用方法：
    python main.py

环境变量配置（可选）：
    RECEIVE_MODE        接收模式: smtp / pop3 / imap，默认 smtp

    --- SMTP 自建服务器模式 ---
    SMTP_BIND_HOST      接收服务器绑定地址，默认 0.0.0.0
    SMTP_BIND_PORT      接收服务器端口，默认 9930

    --- POP3/IMAP 拉取模式 ---
    MAIL_IN_HOST        收件服务器地址（如 pop.qq.com / imap.qq.com）
    MAIL_IN_PORT        收件服务器端口（默认根据协议自动选择）
    MAIL_IN_USER        收件邮箱账号
    MAIL_IN_PASS        收件邮箱密码/授权码
    MAIL_IN_PROTOCOL    收件协议: pop3 / imap，默认 pop3
    MAIL_IN_TLS         是否启用TLS，默认 true
    MAIL_POLL_INTERVAL  轮询间隔（秒），默认 10
    MAIL_INBOX_FOLDER   IMAP收件箱文件夹，默认 INBOX

    --- 邮件发送配置（所有模式共用） ---
    SMTP_OUT_HOST       外发SMTP服务器，默认 smtp.qq.com
    SMTP_OUT_PORT       外发SMTP端口，默认 587
    SMTP_OUT_TIMEOUT    外发SMTP超时时间（秒），默认 30
    SMTP_OUT_USER       发件邮箱账号
    SMTP_OUT_PASS       发件邮箱授权码/密码
    SMTP_OUT_TLS        是否启用TLS，默认 true
    SENDER_NAME         发件人显示名称

    --- 安全配置 ---
    ALLOWED_SENDERS     允许的发件人邮箱，逗号分隔
    ALLOWED_DOMAINS     允许的邮箱域名，逗号分隔
    CMD_TIMEOUT         命令执行超时（秒），默认 30
    CMD_MAX_OUTPUT      命令输出最大长度，默认 50000
    MAX_EMAIL_SIZE      单封邮件最大字节数，默认 1MB
    GITHUB_REPO         GitHub仓库（用于自动更新）
    GITHUB_TOKEN        GitHub Token（用于API认证）
    UPDATE_BRANCH       更新分支，默认 main
    CHECK_UPDATE_ON_START 启动时检查更新，默认 true
    MAX_RESTART_COUNT   最大自动重启次数，默认 5
    LOG_LEVEL           日志级别，默认 INFO
    LOG_FILE            日志文件路径，默认 mail_command_bot.log
    LOG_MAX_BYTES       日志文件最大大小，默认 10MB
    LOG_BACKUP_COUNT    日志备份文件数量，默认 5
"""

import logging
import logging.handlers
import sys

import config
from smtp_receiver import SmtpReceiver
from mail_receiver import MailReceiver
from auto_updater import check_update_on_start


def setup_logging():
    """
    配置日志输出：同时输出到标准输出和文件（RotatingFileHandler）
    日志文件按大小轮转，避免磁盘占满
    """
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    log_format = config.LOG_FORMAT
    handlers = []

    # 标准输出 handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(stdout_handler)

    # 文件持久化 handler（RotatingFileHandler，按大小轮转）
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except (IOError, PermissionError) as e:
        # 文件日志创建失败时仅打印警告，不阻断服务启动
        stdout_err = logging.StreamHandler(sys.stderr)
        stdout_err.setLevel(logging.WARNING)
        sys.stderr.write(f"警告：无法创建日志文件 {config.LOG_FILE}: {e}\n")
        sys.stderr.write("将仅使用标准输出日志\n")

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("MailCommandBot 启动")
    logger.info("=" * 50)

    # 启动前自动更新检查
    check_update_on_start()

    # 根据接收模式启动对应服务
    mode = config.RECEIVE_MODE.lower().strip()
    if mode == "smtp":
        logger.info("运行模式: 自建 SMTP 服务器 (%s:%d)", config.SMTP_BIND_HOST, config.SMTP_BIND_PORT)
        receiver = SmtpReceiver()
        receiver.run_forever()
    elif mode in ("pop3", "imap"):
        logger.info("运行模式: %s 拉取模式 (服务器=%s:%d, 轮询间隔=%ds)",
                    mode.upper(), config.MAIL_IN_HOST, config.MAIL_IN_PORT, config.MAIL_POLL_INTERVAL)
        receiver = MailReceiver()
        receiver.run_forever()
    else:
        logger.error("未知的接收模式: %s，请设置 RECEIVE_MODE 为 smtp/pop3/imap", mode)
        raise SystemExit(1)

    logger.info("MailCommandBot 已停止")


if __name__ == "__main__":
    main()

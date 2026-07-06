#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件命令执行服务器主入口

功能：
    在本地端口（默认9930）启动SMTP接收服务器，
    自动解析收到的邮件，提取以 @ 开头的命令并执行，
    将执行结果通过邮件回复给发件人。

使用方法：
    python main.py

环境变量配置（可选）：
    SMTP_BIND_HOST      接收服务器绑定地址，默认 0.0.0.0
    SMTP_BIND_PORT      接收服务器端口，默认 9930
    SMTP_OUT_HOST       外发SMTP服务器，默认 smtp.qq.com
    SMTP_OUT_PORT       外发SMTP端口，默认 587
    SMTP_OUT_USER       发件邮箱账号
    SMTP_OUT_PASS       发件邮箱授权码/密码
    SMTP_OUT_TLS        是否启用TLS，默认 true
    SENDER_NAME         发件人显示名称
    ALLOWED_SENDERS     允许的发件人邮箱，逗号分隔
    ALLOWED_DOMAINS     允许的邮箱域名，逗号分隔
    CMD_TIMEOUT         命令执行超时（秒），默认 30
    CMD_MAX_OUTPUT      命令输出最大长度，默认 50000
    GITHUB_REPO         GitHub仓库（用于自动更新）
    UPDATE_BRANCH       更新分支，默认 main
    CHECK_UPDATE_ON_START 启动时检查更新，默认 true
    LOG_LEVEL           日志级别，默认 INFO
"""

import logging
import sys

import config
from smtp_receiver import SmtpReceiver
from auto_updater import check_update_on_start


def setup_logging():
    """配置日志输出"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("MailCommandBot 启动")
    logger.info("=" * 50)

    # 启动前自动更新检查
    check_update_on_start()

    # 启动SMTP接收服务器
    receiver = SmtpReceiver()
    receiver.run_forever()

    logger.info("MailCommandBot 已停止")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送模块
负责将命令执行结果通过邮件回复给发件人
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import config

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器：通过外部SMTP发送回复邮件"""

    def __init__(self):
        self.host = config.SMTP_OUT_HOST
        self.port = config.SMTP_OUT_PORT
        self.user = config.SMTP_OUT_USER
        self.password = config.SMTP_OUT_PASS
        self.use_tls = config.SMTP_OUT_TLS
        self.sender_name = config.SENDER_NAME

    def send_reply(self, to_addr: str, subject: str, body: str, original_subject: str = "") -> bool:
        """
        发送回复邮件
        Args:
            to_addr: 收件人地址
            subject: 回复主题
            body: 邮件正文
            original_subject: 原邮件主题（用于构造回复主题）
        Returns:
            发送是否成功
        """
        if not self.user or not self.password:
            logger.error("邮件发送配置不完整: 未设置 SMTP_OUT_USER 或 SMTP_OUT_PASS")
            return False

        if not to_addr:
            logger.error("收件人地址为空，无法发送邮件")
            return False

        reply_subject = subject
        if original_subject and not original_subject.startswith("Re:"):
            reply_subject = f"Re: {original_subject}"

        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = formataddr((Header(self.sender_name, "utf-8").encode(), self.user))
        msg["To"] = to_addr
        msg["Subject"] = Header(reply_subject, "utf-8")

        try:
            logger.info("发送邮件至 %s, 主题: %s", to_addr, reply_subject)
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, [to_addr], msg.as_string())
            logger.info("邮件发送成功: %s", to_addr)
            return True
        except Exception as e:
            logger.error("邮件发送失败: %s", e)
            return False

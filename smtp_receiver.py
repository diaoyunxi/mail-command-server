#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMTP接收服务器模块
使用 aiosmtpd 在本地端口接收邮件，解析后执行命令并回复
"""

import time
import logging
from aiosmtpd.controller import Controller
from email_parser import EmailParser
from command_executor import CommandExecutor
from email_sender import EmailSender
import config

logger = logging.getLogger(__name__)


class MailCommandHandler:
    """
    邮件命令处理器
    实现 aiosmtpd 的 handle_DATA 接口，在收到完整邮件后触发处理
    """

    def __init__(self):
        self.sender = EmailSender()

    async def handle_DATA(self, server, session, envelope):
        """
        处理接收到的邮件数据
        aiosmtpd 在收到 DATA 命令结束后调用此方法
        """
        raw_data = envelope.content
        mail_from = envelope.mail_from
        rcpt_tos = envelope.rcpt_tos

        logger.info("收到邮件 from=%s to=%s size=%d", mail_from, rcpt_tos, len(raw_data))

        try:
            # 解析邮件
            from_addr, to_addr, subject, cleaned_body = EmailParser.parse(raw_data)

            # 提取命令和密码
            cmd, password = EmailParser.extract_command_and_password(cleaned_body)

            if not cmd:
                logger.info("邮件正文中未找到以 @ 开头的命令")
                self.sender.send_reply(
                    from_addr,
                    "未检测到命令",
                    f"收到您的邮件，但未在正文中找到以 '@' 开头的命令行。\n\n"
                    f"请在邮件正文单独一行输入命令，例如：\n@ls -la\n\n"
                    f"如需 sudo，请在第二行提供密码：\n@sudo ls /root\nmy_password\n\n"
                    f"您的原始正文:\n{cleaned_body[:500]}",
                    subject,
                )
                return "250 Message accepted for delivery"

            logger.info("提取到命令: %s, sudo密码: %s", cmd, "已提供" if password else "未提供")

            # 执行命令
            rc, stdout, stderr = CommandExecutor.execute(cmd, password)
            result = CommandExecutor.format_result(rc, stdout, stderr, cmd, bool(password))

            # 发送回复
            reply_body = (
                f"您好，\n\n"
                f"已收到您的命令请求，执行结果如下：\n\n"
                f"{result}\n\n"
                f"---\n"
                f"本邮件由 MailCommandBot 自动发送\n"
            )
            success = self.sender.send_reply(from_addr, "命令执行结果", reply_body, subject)

            if not success:
                logger.error("回复邮件发送失败: %s", from_addr)

        except Exception as e:
            logger.exception("处理邮件时发生异常: %s", e)
            try:
                if mail_from:
                    self.sender.send_reply(
                        mail_from,
                        "处理异常",
                        f"处理您的邮件时发生内部错误:\n{str(e)}\n",
                        subject if "subject" in dir() else "",
                    )
            except Exception:
                pass

        return "250 Message accepted for delivery"


class SmtpReceiver:
    """SMTP 接收服务器包装类"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.SMTP_BIND_HOST
        self.port = port or config.SMTP_BIND_PORT
        self.controller = None

    def start(self):
        """启动SMTP接收服务器"""
        handler = MailCommandHandler()
        self.controller = Controller(
            handler,
            hostname=self.host,
            port=self.port,
        )
        self.controller.start()
        logger.info("SMTP接收服务器已启动: %s:%d", self.host, self.port)

    def stop(self):
        """停止SMTP接收服务器"""
        if self.controller:
            self.controller.stop()
            logger.info("SMTP接收服务器已停止")

    def run_forever(self):
        """阻塞运行，直到手动停止"""
        self.start()
        logger.info("服务器运行中，按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop()

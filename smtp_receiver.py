#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMTP接收服务器模块
使用 aiosmtpd 在本地端口接收邮件，解析后执行命令并回复
"""

import asyncio
import time
import logging
from aiosmtpd.controller import Controller
from email_parser import EmailParser
from command_executor import CommandExecutor
from email_sender import EmailSender
import config

logger = logging.getLogger(__name__)


def _is_sender_allowed(from_addr: str) -> bool:
    """
    校验发件人是否在白名单中
    当 ALLOWED_SENDERS 和 ALLOWED_DOMAINS 均为空时，不限制发件人
    当任一白名单已配置时，仅允许匹配白名单的发件人
    Args:
        from_addr: 发件人邮箱地址
    Returns:
        是否允许该发件人触发命令执行
    """
    if not from_addr:
        return False

    allowed_senders = config.ALLOWED_SENDERS.strip()
    allowed_domains = config.ALLOWED_DOMAINS.strip()

    # 均未配置白名单，不限制
    if not allowed_senders and not allowed_domains:
        return True

    from_lower = from_addr.lower()

    # 检查完整邮箱白名单
    if allowed_senders:
        sender_list = [s.strip().lower() for s in allowed_senders.split(",") if s.strip()]
        if from_lower in sender_list:
            return True

    # 检查域名白名单
    if allowed_domains:
        domain_list = [d.strip().lower() for d in allowed_domains.split(",") if d.strip()]
        for domain in domain_list:
            if from_lower.endswith("@" + domain) or from_lower == domain:
                return True

    return False


class MailCommandHandler:
    """
    邮件命令处理器
    实现 aiosmtpd 的 handle_DATA 接口，在收到完整邮件后触发处理
    """

    def __init__(self):
        self.sender = EmailSender()

    async def handle_DATA(self, server, session, envelope):
        """
        处理接收到的邮件数据（async 协程）
        aiosmtpd 在收到 DATA 命令结束后调用此方法
        所有同步阻塞 I/O（邮件发送）均通过 run_in_executor 交由线程池执行
        """
        raw_data = envelope.content
        mail_from = envelope.mail_from
        rcpt_tos = envelope.rcpt_tos
        subject = ""  # 在 try 顶部初始化，避免后续引用未定义

        logger.info("收到邮件 from=%s to=%s size=%d", mail_from, rcpt_tos, len(raw_data))

        # 邮件大小限制检查（防止超大附件导致 OOM）
        if len(raw_data) > config.MAX_EMAIL_SIZE:
            logger.warning(
                "邮件过大 (%d 字节，限制 %d 字节)，来自 %s",
                len(raw_data), config.MAX_EMAIL_SIZE, mail_from
            )
            return "552 Message too large"

        # 发件人白名单校验
        if not _is_sender_allowed(mail_from):
            logger.warning("发件人 %s 不在白名单中，拒绝处理", mail_from)
            return "550 Sender not allowed"

        loop = asyncio.get_event_loop()

        try:
            # 解析邮件
            from_addr, to_addr, subject, cleaned_body = EmailParser.parse(raw_data)

            # 提取命令和密码
            cmd, password = EmailParser.extract_command_and_password(cleaned_body)

            if not cmd:
                logger.info("邮件正文中未找到以 @ 开头的命令")
                await loop.run_in_executor(
                    None,
                    self.sender.send_reply,
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

            # 构造回复内容
            reply_body = (
                f"您好，\n\n"
                f"已收到您的命令请求，执行结果如下：\n\n"
                f"{result}\n\n"
                f"---\n"
                f"本邮件由 MailCommandBot 自动发送\n"
            )

            # 通过线程池发送邮件，避免阻塞事件循环
            success = await loop.run_in_executor(
                None,
                self.sender.send_reply,
                from_addr,
                "命令执行结果",
                reply_body,
                subject,
            )

            if not success:
                logger.error("回复邮件发送失败: %s", from_addr)

        except Exception as e:
            logger.exception("处理邮件时发生异常: %s", e)
            try:
                if mail_from:
                    await loop.run_in_executor(
                        None,
                        self.sender.send_reply,
                        mail_from,
                        "处理异常",
                        f"处理您的邮件时发生内部错误:\n{str(e)}\n",
                        subject,
                    )
            except Exception:
                logger.exception("发送异常通知邮件失败")

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

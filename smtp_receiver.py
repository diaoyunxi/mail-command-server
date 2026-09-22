#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMTP接收服务器模块
使用 aiosmtpd 在本地端口接收邮件，解析后执行命令并回复
包含发件人白名单、客户端IP白名单、频率限制等安全机制
"""

import asyncio
import time
import logging
import collections
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


def _is_client_ip_allowed(client_ip: str) -> bool:
    """
    校验客户端IP是否在白名单中
    当 ALLOWED_CLIENT_IPS 未配置时，不限制
    Args:
        client_ip: 客户端IP地址
    Returns:
        是否允许该客户端连接
    """
    allowed_ips = config.ALLOWED_CLIENT_IPS.strip()
    if not allowed_ips:
        return True

    ip_list = [ip.strip() for ip in allowed_ips.split(",") if ip.strip()]
    return client_ip in ip_list


class RateLimiter:
    """
    频率限制器：按发件人进行速率限制
    每个发件人在指定时间窗口内最多发送指定数量的邮件
    """

    def __init__(self, max_count: int, window_seconds: int = 60):
        """
        Args:
            max_count: 时间窗口内允许的最大请求数
            window_seconds: 时间窗口大小（秒），默认60秒
        """
        self.max_count = max_count
        self.window_seconds = window_seconds
        # 使用 defaultdict 存储每个发件人的请求时间戳列表
        self._timestamps = collections.defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """
        检查指定 key（发件人）是否允许通过
        Args:
            key: 发件人邮箱地址
        Returns:
            是否允许（True=允许，False=超出限制）
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # 清理过期的记录
        self._timestamps[key] = [ts for ts in self._timestamps[key] if ts > cutoff]

        if len(self._timestamps[key]) >= self.max_count:
            return False

        self._timestamps[key].append(now)
        return True


class MailCommandHandler:
    """
    邮件命令处理器
    实现 aiosmtpd 的 handle_DATA 接口，在收到完整邮件后触发处理
    """

    def __init__(self):
        self.sender = EmailSender()
        # 初始化频率限制器
        self.rate_limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)

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

        # 获取客户端IP（用于IP白名单校验）
        client_ip = ""
        if session and hasattr(session, "peer"):
            try:
                client_ip = session.peer[0] if session.peer else ""
            except (IndexError, TypeError):
                pass

        logger.info("收到邮件 from=%s to=%s size=%d client_ip=%s", mail_from, rcpt_tos, len(raw_data), client_ip)

        # 邮件大小限制检查（防止超大附件导致 OOM）
        if len(raw_data) > config.MAX_EMAIL_SIZE:
            logger.warning(
                "邮件过大 (%d 字节，限制 %d 字节)，来自 %s",
                len(raw_data), config.MAX_EMAIL_SIZE, mail_from
            )
            return "552 Message too large"

        # 客户端IP白名单校验（防止外部未授权主机伪造 MAIL FROM）
        if not _is_client_ip_allowed(client_ip):
            logger.warning("客户端IP %s 不在白名单中，拒绝处理", client_ip)
            return "550 Access denied"

        # 发件人白名单校验
        if not _is_sender_allowed(mail_from):
            logger.warning("发件人 %s 不在白名单中，拒绝处理", mail_from)
            return "550 Sender not allowed"

        # 频率限制校验（每分钟最多 RATE_LIMIT_PER_MINUTE 封）
        if not self.rate_limiter.is_allowed(mail_from or client_ip):
            logger.warning("发件人 %s 触发频率限制，拒绝处理", mail_from)
            return "450 Too many requests, please try again later"

        # 使用 get_running_loop() 替代已废弃的 get_event_loop()
        loop = asyncio.get_running_loop()

        try:
            # 解析邮件
            from_addr, _to_addr, subject, cleaned_body = EmailParser.parse(raw_data)

            # 提取所有命令（列表格式）
            commands = EmailParser.extract_commands(cleaned_body)

            if not commands:
                # 没有有效命令，不回复任何邮件
                logger.info("邮件正文未以 @ 开头，不执行任何命令")
                return "250 Message accepted for delivery"

            # NOPASSWD 模式：忽略邮件中的所有密码
            if config.SUDO_NOPASSWD:
                logger.info("已启用 sudoers NOPASSWD 模式，忽略邮件中提供的密码")
                commands = [(cmd, "") for cmd, _ in commands]

            # 依次执行所有命令
            all_results = []
            executed_count = 0
            for idx, (cmd, password) in enumerate(commands, 1):
                logger.info("执行命令 [%d/%d]: %s", idx, len(commands), cmd)
                rc, stdout, stderr = await loop.run_in_executor(
                    None, CommandExecutor.execute, cmd, password
                )
                result = CommandExecutor.format_result(rc, stdout, stderr, cmd, bool(password))
                all_results.append(f"--- 命令 {idx}: {cmd} ---\n{result}")
                executed_count += 1

            # 构造回复内容
            reply_body = (
                f"您好，\n\n"
                f"已收到您的命令请求，共执行 {executed_count} 条命令，结果如下：\n\n"
                + "\n".join(all_results) +
                f"\n\n---\n"
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
            # 仅记录详细异常到日志，不向发件人泄露系统信息
            logger.exception("处理邮件时发生异常: %s", e)
            try:
                if mail_from:
                    await loop.run_in_executor(
                        None,
                        self.sender.send_reply,
                        mail_from,
                        "处理异常",
                        # 仅回复通用错误信息，不泄露异常详情
                        "处理您的邮件时发生内部错误，请联系管理员排查。\n",
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

    def _check_whitelist_config(self):
        """
        启动时检查白名单配置
        若 REQUIRE_WHITELIST 为 true 且未配置任何白名单，则强制绑定 127.0.0.1
        """
        if not config.REQUIRE_WHITELIST:
            return

        allowed_senders = config.ALLOWED_SENDERS.strip()
        allowed_domains = config.ALLOWED_DOMAINS.strip()

        if not allowed_senders and not allowed_domains:
            if self.host not in ("127.0.0.1", "localhost", "::1"):
                logger.warning(
                    "安全警告：未配置 ALLOWED_SENDERS 或 ALLOWED_DOMAINS 白名单，"
                    "强制绑定 127.0.0.1 以防止未授权访问。"
                    "如需对外提供服务，请配置白名单后设置 SMTP_BIND_HOST。"
                )
                self.host = "127.0.0.1"

    def start(self):
        """启动SMTP接收服务器"""
        # 启动前检查白名单配置
        self._check_whitelist_config()

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

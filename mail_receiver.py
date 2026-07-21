#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件接收模块（POP3/IMAP 模式）
通过已有邮件服务器的 POP3 或 IMAP 协议主动拉取邮件，
解析命令并执行，将结果通过 SMTP 回复给发件人。

支持：
    - POP3 / POP3_SSL：使用 UIDL 去重，处理完成后删除邮件
    - IMAP / IMAP_SSL：搜索未读邮件(UNSEEN)，处理完成后标记已读

此模式无需自建 SMTP 接收服务器，适合无法开放端口或不想配置 MX 记录的场景。
"""

import os
import time
import logging
import threading
import collections
import poplib
import imaplib
import email
import email.policy
from typing import List, Optional

import config
from email_parser import EmailParser
from command_executor import CommandExecutor
from email_sender import EmailSender

logger = logging.getLogger(__name__)


# =====================================================================
# 公共工具函数
# =====================================================================
def _is_sender_allowed(from_addr: str) -> bool:
    """
    校验发件人是否在白名单中
    与 smtp_receiver 中逻辑保持一致
    """
    if not from_addr:
        return False

    allowed_senders = config.ALLOWED_SENDERS.strip()
    allowed_domains = config.ALLOWED_DOMAINS.strip()

    if not allowed_senders and not allowed_domains:
        return True

    from_lower = from_addr.lower()

    if allowed_senders:
        sender_list = [s.strip().lower() for s in allowed_senders.split(",") if s.strip()]
        if from_lower in sender_list:
            return True

    if allowed_domains:
        domain_list = [d.strip().lower() for d in allowed_domains.split(",") if d.strip()]
        for domain in domain_list:
            if from_lower.endswith("@" + domain) or from_lower == domain:
                return True

    return False


class RateLimiter:
    """
    频率限制器：按发件人进行速率限制
    与 smtp_receiver 中实现保持一致
    """

    def __init__(self, max_count: int, window_seconds: int = 60):
        self.max_count = max_count
        self.window_seconds = window_seconds
        self._timestamps = collections.defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self._timestamps[key] = [ts for ts in self._timestamps[key] if ts > cutoff]
        if len(self._timestamps[key]) >= self.max_count:
            return False
        self._timestamps[key].append(now)
        return True


# =====================================================================
# 邮件处理器（同步版本，复用 smtp_receiver 核心逻辑）
# =====================================================================
class MailProcessor:
    """
    邮件处理器：解析邮件、提取命令、执行、发送回复
    此实现为同步版本，适用于后台线程轮询场景
    """

    def __init__(self):
        self.sender = EmailSender()
        self.rate_limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)

    def process(self, raw_data: bytes, mail_from: str, rcpt_tos: List[str]) -> bool:
        """
        处理单封邮件

        Args:
            raw_data: 原始邮件字节数据
            mail_from: 发件人地址
            rcpt_tos: 收件人地址列表
        Returns:
            是否成功处理
        """
        # 邮件大小限制
        if len(raw_data) > config.MAX_EMAIL_SIZE:
            logger.warning(
                "邮件过大 (%d 字节，限制 %d 字节)，来自 %s",
                len(raw_data), config.MAX_EMAIL_SIZE, mail_from
            )
            return False

        # 发件人白名单校验（POP3/IMAP 模式下不校验客户端 IP）
        if not _is_sender_allowed(mail_from):
            logger.warning("发件人 %s 不在白名单中，拒绝处理", mail_from)
            return False

        # 频率限制校验
        if not self.rate_limiter.is_allowed(mail_from or "unknown"):
            logger.warning("发件人 %s 触发频率限制，拒绝处理", mail_from)
            return False

        subject = ""
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
                    f"也可使用命令模板：\n@template:disk\n\n"
                    f"您的原始正文:\n{cleaned_body[:500]}",
                    subject,
                )
                return True

            # NOPASSWD 模式：忽略邮件中的密码
            if config.SUDO_NOPASSWD and password:
                logger.info("已启用 sudoers NOPASSWD 模式，忽略邮件中提供的密码")
                password = ""

            # 执行命令
            rc, stdout, stderr = CommandExecutor.execute(cmd, password)
            result = CommandExecutor.format_result(rc, stdout, stderr, cmd, bool(password))

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
            return success

        except Exception as e:
            logger.exception("处理邮件时发生异常: %s", e)
            try:
                if mail_from:
                    self.sender.send_reply(
                        mail_from,
                        "处理异常",
                        "处理您的邮件时发生内部错误，请联系管理员排查。\n",
                        subject,
                    )
            except Exception:
                logger.exception("发送异常通知邮件失败")
            return False


# =====================================================================
# POP3 接收器
# =====================================================================
class Pop3Receiver:
    """
    POP3 邮件接收器
    通过 UIDL 识别新邮件，处理完成后使用 DELE 删除，避免重复执行
    """

    def __init__(self):
        self.host = config.MAIL_IN_HOST
        self.port = config.MAIL_IN_PORT
        self.user = config.MAIL_IN_USER
        self.password = config.MAIL_IN_PASS
        self.use_tls = config.MAIL_IN_TLS
        self.poll_interval = config.MAIL_POLL_INTERVAL
        self.processor = MailProcessor()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动后台轮询线程"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "POP3 接收器已启动: %s:%d, 轮询间隔 %d 秒",
            self.host, self.port, self.poll_interval
        )

    def stop(self) -> None:
        """停止轮询线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("POP3 接收器已停止")

    def _run(self) -> None:
        """主循环"""
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                logger.exception("POP3 轮询异常: %s", e)
            self._stop_event.wait(self.poll_interval)

    def _poll(self) -> None:
        """单次轮询：连接、获取、处理、删除"""
        if not self.user or not self.password:
            logger.error("POP3 账号或密码未配置")
            return

        server: Optional[poplib.POP3] = None
        try:
            if self.use_tls:
                server = poplib.POP3_SSL(self.host, self.port, timeout=30)
            else:
                server = poplib.POP3(self.host, self.port, timeout=30)

            server.user(self.user)
            server.pass_(self.password)

            num_messages, total_size = server.stat()
            logger.debug("POP3 状态: %d 封邮件, 总大小 %d 字节", num_messages, total_size)

            if num_messages == 0:
                server.quit()
                return

            # 获取 UIDL 列表
            try:
                resp = server.uidl()
                uidl_lines = resp[1] if len(resp) > 1 else []
            except poplib.error_proto as e:
                logger.warning("POP3 UIDL 命令失败: %s", e)
                server.quit()
                return

            # 解析 UIDL 响应: 每行格式 "序号 UID"
            uid_map = {}  # uid -> 1-based index
            for line in uidl_lines:
                try:
                    line_str = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line)
                    parts = line_str.strip().split()
                    if len(parts) >= 2:
                        idx = parts[0]
                        uid = parts[1]
                        uid_map[uid] = idx
                except Exception as e:
                    logger.warning("解析 UIDL 行失败: %s", e)

            if not uid_map:
                server.quit()
                return

            logger.info("POP3 发现 %d 封邮件", len(uid_map))

            processed_count = 0
            for uid, idx in uid_map.items():
                if self._stop_event.is_set():
                    break
                try:
                    resp = server.retr(int(idx))
                    raw_data = b"\r\n".join(resp[1])

                    # 解析发件人
                    msg = email.message_from_bytes(raw_data, policy=email.policy.default)
                    mail_from = msg.get("From", "")
                    rcpt_tos = [msg.get("To", "")]

                    logger.info("处理 POP3 邮件: uid=%s, from=%s", uid, mail_from)
                    self.processor.process(raw_data, mail_from, rcpt_tos)
                    processed_count += 1

                    # 处理完成后删除邮件（避免下次重复执行）
                    server.dele(int(idx))

                except Exception as e:
                    logger.exception("处理 POP3 邮件 uid=%s 失败: %s", uid, e)

            if processed_count:
                logger.info("POP3 本次处理 %d 封邮件", processed_count)

            server.quit()

        except Exception as e:
            logger.exception("POP3 连接失败: %s", e)
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


# =====================================================================
# IMAP 接收器
# =====================================================================
class ImapReceiver:
    """
    IMAP 邮件接收器
    搜索未读邮件(UNSEEN)，处理完成后标记为已读，避免重复执行
    """

    def __init__(self):
        self.host = config.MAIL_IN_HOST
        self.port = config.MAIL_IN_PORT
        self.user = config.MAIL_IN_USER
        self.password = config.MAIL_IN_PASS
        self.use_tls = config.MAIL_IN_TLS
        self.poll_interval = config.MAIL_POLL_INTERVAL
        self.inbox_folder = config.MAIL_INBOX_FOLDER
        self.processor = MailProcessor()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动后台轮询线程"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "IMAP 接收器已启动: %s:%d, 文件夹=%s, 轮询间隔 %d 秒",
            self.host, self.port, self.inbox_folder, self.poll_interval
        )

    def stop(self) -> None:
        """停止轮询线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("IMAP 接收器已停止")

    def _run(self) -> None:
        """主循环"""
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                logger.exception("IMAP 轮询异常: %s", e)
            self._stop_event.wait(self.poll_interval)

    def _poll(self) -> None:
        """单次轮询：连接、搜索未读、获取、处理、标记已读"""
        if not self.user or not self.password:
            logger.error("IMAP 账号或密码未配置")
            return

        server: Optional[imaplib.IMAP4] = None
        try:
            if self.use_tls:
                server = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                server = imaplib.IMAP4(self.host, self.port)

            server.login(self.user, self.password)
            status, _ = server.select(self.inbox_folder)
            if status != "OK":
                logger.error("IMAP 选择文件夹 %s 失败: %s", self.inbox_folder, status)
                server.logout()
                return

            # 搜索未读邮件
            status, msg_ids = server.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("IMAP 搜索邮件失败: %s", status)
                server.close()
                server.logout()
                return

            msg_id_list = msg_ids[0].split()
            if not msg_id_list:
                logger.debug("IMAP 没有新邮件")
                server.close()
                server.logout()
                return

            logger.info("IMAP 发现 %d 封未读邮件", len(msg_id_list))

            processed_count = 0
            for msg_id in msg_id_list:
                if self._stop_event.is_set():
                    break
                try:
                    status, msg_data = server.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data:
                        logger.warning("IMAP 获取邮件 %s 失败", msg_id)
                        continue

                    raw_data = None
                    for part in msg_data:
                        if isinstance(part, tuple) and len(part) >= 2:
                            raw_data = part[1]
                            break

                    if not raw_data:
                        continue

                    msg = email.message_from_bytes(raw_data, policy=email.policy.default)
                    mail_from = msg.get("From", "")
                    rcpt_tos = [msg.get("To", "")]

                    msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                    logger.info("处理 IMAP 邮件: id=%s, from=%s", msg_id_str, mail_from)
                    self.processor.process(raw_data, mail_from, rcpt_tos)
                    processed_count += 1

                    # 标记为已读（避免下次重复处理）
                    server.store(msg_id, "+FLAGS", "\\Seen")

                except Exception as e:
                    logger.exception("处理 IMAP 邮件 id=%s 失败: %s", msg_id, e)

            if processed_count:
                logger.info("IMAP 本次处理 %d 封邮件", processed_count)

            server.close()
            server.logout()

        except Exception as e:
            logger.exception("IMAP 连接失败: %s", e)
        finally:
            if server:
                try:
                    server.close()
                    server.logout()
                except Exception:
                    pass


# =====================================================================
# 统一入口
# =====================================================================
class MailReceiver:
    """
    邮件接收器统一入口
    根据 config.MAIL_IN_PROTOCOL 自动选择 POP3 或 IMAP 实现
    """

    def __init__(self):
        protocol = config.MAIL_IN_PROTOCOL.lower().strip()
        if protocol == "pop3":
            self._receiver = Pop3Receiver()
        elif protocol == "imap":
            self._receiver = ImapReceiver()
        else:
            raise ValueError(
                f"不支持的邮件接收协议: {protocol}，"
                f"请设置 MAIL_IN_PROTOCOL 为 pop3 或 imap"
            )

    def start(self) -> None:
        self._receiver.start()

    def stop(self) -> None:
        self._receiver.stop()

    def run_forever(self) -> None:
        """阻塞运行，直到收到 Ctrl+C"""
        self.start()
        logger.info("邮件接收器运行中，按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop()

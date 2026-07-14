#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送模块
负责将命令执行结果通过邮件回复给发件人
支持 SMTP 连接复用、分类异常捕获、大小写不敏感的 Re: 匹配
"""

import smtplib
import socket
import re
import logging
import threading
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import config

logger = logging.getLogger(__name__)


class EmailSender:
    """
    邮件发送器：通过外部SMTP发送回复邮件
    支持连接复用，自动重连和异常分类处理
    """

    def __init__(self):
        self.host = config.SMTP_OUT_HOST
        self.port = config.SMTP_OUT_PORT
        self.timeout = config.SMTP_OUT_TIMEOUT
        self.user = config.SMTP_OUT_USER
        self.password = config.SMTP_OUT_PASS
        self.use_tls = config.SMTP_OUT_TLS
        self.sender_name = config.SENDER_NAME
        # 连接复用：缓存 SMTP 连接
        self._server = None
        # 线程安全锁：保护 _get_connection 和 _close_connection 的并发访问
        self._lock = threading.Lock()
        # 心跳保活间隔（秒），0 表示禁用
        self._keepalive_interval = config.SMTP_KEEPALIVE_INTERVAL

    def _get_connection(self) -> smtplib.SMTP:
        """
        获取 SMTP 连接（复用已有连接或创建新连接）
        使用 threading.Lock 保证线程安全
        Returns:
            可用的 SMTP 连接对象
        """
        with self._lock:
            # 尝试复用已有连接
            if self._server is not None:
                try:
                    # 发送 NOOP 命令检查连接是否存活（同时起到心跳保活作用）
                    code, msg = self._server.noop()
                    if code == 250:
                        return self._server
                except Exception:
                    pass
                # 连接已失效，关闭并重建
                self._close_connection_locked()

            # 创建新连接
            self._server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            if self.use_tls:
                self._server.starttls()
            if self.user and self.password:
                self._server.login(self.user, self.password)
            return self._server

    def _close_connection_locked(self) -> None:
        """
        安全关闭 SMTP 连接（内部方法，调用方需已持有锁）
        """
        if self._server is not None:
            try:
                self._server.quit()
            except Exception:
                try:
                    self._server.close()
                except Exception:
                    pass
            finally:
                self._server = None

    def _close_connection(self) -> None:
        """安全关闭 SMTP 连接（线程安全）"""
        with self._lock:
            self._close_connection_locked()

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

        # 构造回复主题：大小写不敏感匹配 Re:
        reply_subject = subject
        if original_subject and not re.match(r"(?i)^re:\s*", original_subject):
            reply_subject = f"Re: {original_subject}"

        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = formataddr((Header(self.sender_name, "utf-8").encode(), self.user))
        msg["To"] = to_addr
        msg["Subject"] = Header(reply_subject, "utf-8")

        try:
            logger.info("发送邮件至 %s, 主题: %s", to_addr, reply_subject)
            server = self._get_connection()
            server.sendmail(self.user, [to_addr], msg.as_string())
            logger.info("邮件发送成功: %s", to_addr)
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error("SMTP 认证失败: %s (请检查 SMTP_OUT_USER 和 SMTP_OUT_PASS)", e)
            self._close_connection()
            return False

        except smtplib.SMTPConnectError as e:
            logger.error("SMTP 连接失败: %s", e)
            self._close_connection()
            return False

        except smtplib.SMTPRecipientsRefused as e:
            logger.error("收件人被拒绝: %s", e.recipients)
            return False

        except smtplib.SMTPDataError as e:
            logger.error("SMTP 数据错误: %s", e)
            return False

        except smtplib.SMTPException as e:
            logger.error("SMTP 协议错误: %s", e)
            self._close_connection()
            return False

        except socket.timeout:
            logger.error("邮件发送超时 (>%d秒): %s", self.timeout, to_addr)
            self._close_connection()
            return False

        except ConnectionError as e:
            logger.error("邮件发送网络连接错误: %s", e)
            self._close_connection()
            return False

        except OSError as e:
            logger.error("邮件发送系统错误: %s", e)
            self._close_connection()
            return False

        except Exception as e:
            logger.error("邮件发送未知错误: %s", e)
            self._close_connection()
            return False

    def close(self) -> None:
        """关闭邮件发送器，释放 SMTP 连接"""
        self._close_connection()

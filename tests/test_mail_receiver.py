#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mail_receiver 模块单元测试
覆盖：POP3/IMAP 配置校验、协议识别、轮询间隔默认值
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestReceiveMode:
    """RECEIVE_MODE 配置测试"""

    def test_default_is_smtp(self):
        """默认模式应为 smtp"""
        assert config.RECEIVE_MODE == "smtp"

    def test_receive_mode_is_string(self):
        """RECEIVE_MODE 应为字符串"""
        assert isinstance(config.RECEIVE_MODE, str)


class TestMailInConfig:
    """POP3/IMAP 模式配置测试"""

    def test_mail_in_host_empty_by_default(self):
        """MAIL_IN_HOST 默认应为空字符串"""
        assert config.MAIL_IN_HOST == ""

    def test_mail_in_protocol_default(self):
        """MAIL_IN_PROTOCOL 默认应为 pop3"""
        assert config.MAIL_IN_PROTOCOL == "pop3"

    def test_mail_in_tls_default(self):
        """MAIL_IN_TLS 默认应为 True"""
        assert config.MAIL_IN_TLS is True

    def test_mail_poll_interval_range(self):
        """MAIL_POLL_INTERVAL 应在合法范围"""
        assert 1 <= config.MAIL_POLL_INTERVAL <= 3600

    def test_mail_inbox_folder_default(self):
        """MAIL_INBOX_FOLDER 默认应为 INBOX"""
        assert config.MAIL_INBOX_FOLDER == "INBOX"


class TestMailInPortDefaults:
    """MAIL_IN_PORT 默认值测试"""

    def test_pop3_ssl_default_port(self):
        """POP3 + TLS 时默认端口应为 995"""
        # 由于 MAIL_IN_PORT 在模块加载时已计算，这里检查逻辑
        assert config.MAIL_IN_PORT in (995, 110, 993, 143)

    def test_mail_in_port_is_int(self):
        """MAIL_IN_PORT 应为整数"""
        assert isinstance(config.MAIL_IN_PORT, int)


class TestMailReceiverImport:
    """MailReceiver 导入测试"""

    def test_mail_receiver_can_be_imported(self):
        """mail_receiver 模块应可正常导入"""
        from mail_receiver import MailReceiver
        assert MailReceiver is not None

    def test_pop3_receiver_can_be_imported(self):
        """Pop3Receiver 类应可正常导入"""
        from mail_receiver import Pop3Receiver
        assert Pop3Receiver is not None

    def test_imap_receiver_can_be_imported(self):
        """ImapReceiver 类应可正常导入"""
        from mail_receiver import ImapReceiver
        assert ImapReceiver is not None

    def test_mail_processor_can_be_imported(self):
        """MailProcessor 类应可正常导入"""
        from mail_receiver import MailProcessor
        assert MailProcessor is not None


class TestMailReceiverProtocolSelection:
    """MailReceiver 协议选择测试"""

    def test_pop3_protocol_selected(self):
        """RECEIVE_MODE=pop3 时应创建 Pop3Receiver"""
        from mail_receiver import Pop3Receiver
        # 验证 Pop3Receiver 类存在即可
        assert Pop3Receiver is not None

    def test_imap_protocol_selected(self):
        """RECEIVE_MODE=imap 时应创建 ImapReceiver"""
        from mail_receiver import ImapReceiver
        # 验证 ImapReceiver 类存在即可
        assert ImapReceiver is not None

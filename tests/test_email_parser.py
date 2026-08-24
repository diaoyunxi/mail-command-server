#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmailParser 单元测试
覆盖：邮件解析、正文清洗、命令提取、密码提取
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_parser import EmailParser


class TestExtractCommands:
    """EmailParser.extract_commands() 测试"""

    def test_simple_command(self):
        """提取简单命令"""
        commands = EmailParser.extract_commands("@ls -la")
        assert commands == [("ls -la", "")]

    def test_first_line_must_be_at(self):
        """第一行必须是以 @ 开头的命令"""
        commands = EmailParser.extract_commands("你好\n@df -h\n再见")
        assert commands == []

    def test_multiple_commands(self):
        """多个 @ 命令应全部提取"""
        commands = EmailParser.extract_commands("@ls -la\n@df -h\n@whoami")
        assert commands == [("ls -la", ""), ("df -h", ""), ("whoami", "")]

    def test_sudo_command_with_password(self):
        """sudo 命令应提取下一行的密码"""
        commands = EmailParser.extract_commands("@sudo ls /root\nmy_secret_password")
        assert commands == [("sudo ls /root", "my_secret_password")]

    def test_sudo_command_password_with_blank_line(self):
        """密码前有空行时应跳过空行"""
        commands = EmailParser.extract_commands("@sudo cat /etc/passwd\n\nmy_password")
        assert commands == [("sudo cat /etc/passwd", "my_password")]

    def test_no_command(self):
        """无 @ 前缀时返回空列表"""
        commands = EmailParser.extract_commands("这是一封普通邮件\n没有命令")
        assert commands == []

    def test_empty_body(self):
        """空正文返回空列表"""
        commands = EmailParser.extract_commands("")
        assert commands == []

    def test_non_sudo_command_no_password(self):
        """非 sudo 命令不提取密码"""
        commands = EmailParser.extract_commands("@whoami\nsome_text")
        assert commands == [("whoami", "")]

    def test_only_at_sign(self):
        """只有 @ 无后续内容"""
        commands = EmailParser.extract_commands("@")
        assert commands == []

    def test_at_with_spaces_only(self):
        """@ 后只有空格"""
        commands = EmailParser.extract_commands("@   ")
        assert commands == []

    def test_multiple_sudo_commands(self):
        """多个 sudo 命令各自提取密码"""
        commands = EmailParser.extract_commands("@sudo ls /root\npass1\n@sudo cat /etc/hosts\npass2")
        assert commands == [("sudo ls /root", "pass1"), ("sudo cat /etc/hosts", "pass2")]


class TestCleanBody:
    """EmailParser._clean_body() 测试"""

    def test_strip_signature(self):
        """应去除 -- 签名后的内容"""
        body = "正文内容\n--\n签名内容\n更多签名"
        cleaned = EmailParser._clean_body(body)
        assert "正文内容" in cleaned
        assert "签名内容" not in cleaned

    def test_strip_quoted_lines(self):
        """应去除 > 引用行"""
        body = "回复内容\n> 原始内容\n> 更多引用"
        cleaned = EmailParser._clean_body(body)
        assert "回复内容" in cleaned
        assert "原始内容" not in cleaned

    def test_strip_email_headers(self):
        """应去除邮件头残留"""
        body = "From: sender@example.com\n正文内容\nDate: 2024-01-01"
        cleaned = EmailParser._clean_body(body)
        assert "正文内容" in cleaned
        assert "From: sender@example.com" not in cleaned

    def test_strip_original_message_marker(self):
        """应去除引用原文标记后的内容"""
        body = "回复\nOn Mon wrote:\n> 原文"
        cleaned = EmailParser._clean_body(body)
        assert "回复" in cleaned
        assert "On Mon wrote:" not in cleaned

    def test_preserve_normal_text(self):
        """应保留正常文本"""
        body = "第一行\n第二行\n第三行"
        cleaned = EmailParser._clean_body(body)
        assert cleaned == "第一行\n第二行\n第三行"

    def test_strip_html_to_text(self):
        """HTML 标签应被去除"""
        html = "<p>段落1</p><p>段落2</p>"
        text = EmailParser._html_to_text(html)
        assert "段落1" in text
        assert "段落2" in text
        assert "<p>" not in text


class TestParseEmail:
    """EmailParser.parse() 集成测试"""

    def test_parse_simple_email(self):
        """解析简单邮件"""
        raw = (
            b"From: sender@example.com\r\n"
            b"To: bot@example.com\r\n"
            b"Subject: Test\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"@echo hello world\r\n"
        )
        from_addr, to_addr, subject, body = EmailParser.parse(raw)
        assert from_addr == "sender@example.com"
        assert to_addr == "bot@example.com"
        assert subject == "Test"
        assert "echo hello world" in body

    def test_parse_email_with_command_and_password(self):
        """解析含命令和密码的邮件"""
        raw = (
            b"From: admin@example.com\r\n"
            b"To: bot@example.com\r\n"
            b"Subject: Run Command\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"@sudo ls /root\r\n"
            b"my_sudo_password\r\n"
        )
        from_addr, to_addr, subject, body = EmailParser.parse(raw)
        commands = EmailParser.extract_commands(body)
        assert commands == [("sudo ls /root", "my_sudo_password")]

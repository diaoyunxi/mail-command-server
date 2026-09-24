#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件内容解析模块
负责从原始邮件中提取发件人、主题、以及纯文本正文内容
"""

import email
import email.policy
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import List, Tuple
import re
import html as html_module
import logging

logger = logging.getLogger(__name__)


# ==================== 预编译正则表达式 ====================
# 签名分隔线
_RE_SIGNATURE_SEPARATOR = re.compile(r"^--\s*$")
# 邮件头残留
_RE_MAIL_HEADER = re.compile(
    r"^(From|To|Subject|Date|Message-ID|Received|Mime-Version|Content-Type|Content-Transfer-Encoding|DKIM-Signature|X-[^:]+):\s",
    re.IGNORECASE
)
# 引用原文标记
_RE_QUOTED_ORIGINAL = re.compile(
    r"^(On .+ wrote:|在 .+ 写道：|-----Original Message-----|Sent from my )",
    re.IGNORECASE
)


class _HTMLToTextParser(HTMLParser):
    """
    HTML 转文本解析器（基于标准库 html.parser）
    将 HTML 标签转换为纯文本，处理换行、列表等常见元素
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._result = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        """处理开始标签"""
        if tag in ("script", "style", "head"):
            self._skip = True
        elif tag == "br":
            self._result.append("\n")
        elif tag == "li":
            self._result.append("\n- ")
        elif tag in ("p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.append("\n")

    def handle_endtag(self, tag):
        """处理结束标签"""
        if tag in ("script", "style", "head"):
            self._skip = False
        elif tag in ("p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.append("\n")

    def handle_data(self, data):
        """处理文本内容"""
        if not self._skip:
            self._result.append(data)

    def get_text(self) -> str:
        """获取转换后的纯文本"""
        text = "".join(self._result)
        # 对 HTML 实体进行反转义
        text = html_module.unescape(text)
        return text


class EmailParser:
    """邮件解析器：提取邮件关键信息并清洗正文"""

    @staticmethod
    def parse(raw_data: bytes) -> Tuple[str, str, str, str]:
        """
        解析原始邮件数据
        Args:
            raw_data: 原始邮件字节数据
        Returns:
            (from_addr, to_addr, subject, cleaned_body)
        """
        msg = email.message_from_bytes(raw_data, policy=email.policy.default)

        from_addr = msg.get("From", "")
        to_addr = msg.get("To", "")
        subject = msg.get("Subject", "")

        body = EmailParser._extract_body(msg)
        cleaned_body = EmailParser._clean_body(body)

        logger.info("解析邮件: from=%s, to=%s, subject=%s", from_addr, to_addr, subject)
        return from_addr, to_addr, subject, cleaned_body

    @staticmethod
    def _extract_body(msg: EmailMessage) -> str:
        """从邮件对象中提取纯文本正文，优先 text/plain"""
        body_parts = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = part.get("Content-Disposition", "")
                if "attachment" in disposition:
                    continue
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception as e:
                        logger.warning("解析 text/plain 失败: %s", e)
                elif content_type == "text/html" and not body_parts:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html = payload.decode(charset, errors="replace")
                            body_parts.append(EmailParser._html_to_text(html))
                    except Exception as e:
                        logger.warning("解析 text/html 失败: %s", e)
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        text = EmailParser._html_to_text(text)
                    body_parts.append(text)
            except Exception as e:
                logger.warning("解析单部分邮件失败: %s", e)

        return "\n".join(body_parts)

    @staticmethod
    def _html_to_text(html: str) -> str:
        """
        将 HTML 转换为纯文本（基于标准库 html.parser，替代正则表达式）
        处理换行、列表、段落等常见 HTML 元素，跳过 script/style/head 标签
        Args:
            html: HTML 字符串
        Returns:
            转换后的纯文本
        """
        parser = _HTMLToTextParser()
        parser.feed(html)
        parser.close()
        return parser.get_text()

    @staticmethod
    def _clean_body(body: str) -> str:
        """
        清洗邮件正文：去除签名、引用、邮件头残留等
        """
        lines = body.splitlines()
        cleaned_lines = []
        in_signature = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue

            # 签名分隔线
            if _RE_SIGNATURE_SEPARATOR.match(stripped):
                in_signature = True
                continue
            if in_signature:
                continue

            # 引用行
            if stripped.startswith(">"):
                continue

            # 邮件头残留
            if _RE_MAIL_HEADER.match(stripped):
                continue

            # 引用原文标记
            if _RE_QUOTED_ORIGINAL.match(stripped):
                break

            cleaned_lines.append(line)

        # 去除首尾多余空行
        while cleaned_lines and cleaned_lines[0] == "":
            cleaned_lines.pop(0)
        while cleaned_lines and cleaned_lines[-1] == "":
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    @staticmethod
    def extract_commands(body: str) -> List[Tuple[str, str]]:
        """
        从清洗后的正文中提取所有以 @ 开头的命令及其后的密码

        规则：
        - 正文必须第一行以 @ 开头，否则不执行任何命令
        - 允许多个 @ 命令，依次执行
        - 返回命令列表：[(cmd1, password1), (cmd2, password2), ...]

        Args:
            body: 清洗后的邮件正文

        Returns:
            命令列表，格式为 [(命令, 密码), ...]
            如果正文不以 @ 开头或没有有效命令，返回空列表
        """
        lines = body.splitlines()
        if not lines:
            return []

        # 第一行必须是以 @ 开头的命令
        first_line = lines[0].strip()
        if not first_line.startswith("@"):
            return []

        commands = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 找到以 @ 开头的命令行
            if line.startswith("@"):
                cmd = line[1:].strip()
                if not cmd:  # @ 后无内容，跳过
                    i += 1
                    continue

                # 提取命令
                commands.append((cmd, ""))

                # 如果命令以 sudo 开头，提取下一行的密码
                if cmd.lower().startswith("sudo "):
                    i += 1
                    while i < len(lines) and not lines[i].strip().startswith("@"):
                        pwd = lines[i].strip()
                        if pwd:
                            commands[-1] = (commands[-1][0], pwd)
                            break
                        i += 1
                    else:
                        # 内层循环因条件不满足退出（遇到下一个 @ 行），
                        # 不递增 i，让外层循环处理该 @ 命令
                        continue
                i += 1
            else:
                i += 1

        return commands

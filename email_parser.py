#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件内容解析模块
负责从原始邮件中提取发件人、主题、以及纯文本正文内容
"""

import email
import email.policy
from email.message import EmailMessage
from typing import Tuple
import re
import html as html_module
import logging

logger = logging.getLogger(__name__)


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
        """简单HTML转文本"""
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html_module.unescape(text)
        return text

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
            if re.match(r"^--\s*$", stripped):
                in_signature = True
                continue
            if in_signature:
                continue

            # 引用行
            if stripped.startswith(">"):
                continue

            # 邮件头残留
            if re.match(r"^(From|To|Subject|Date|Message-ID|Received|Mime-Version|Content-Type|Content-Transfer-Encoding|DKIM-Signature|X-[^:]+):\s", stripped, re.IGNORECASE):
                continue

            # 引用原文标记
            if re.match(r"^(On .+ wrote:|在 .+ 写道：|-----Original Message-----|Sent from my )", stripped, re.IGNORECASE):
                break

            cleaned_lines.append(line)

        # 去除首尾多余空行
        while cleaned_lines and cleaned_lines[0] == "":
            cleaned_lines.pop(0)
        while cleaned_lines and cleaned_lines[-1] == "":
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    @staticmethod
    def extract_command_and_password(body: str) -> Tuple[str, str]:
        """
        从清洗后的正文中提取以 @ 开头的命令及其后的密码
        返回 (cmd, password)
        - cmd: 去掉 @ 后的命令行
        - password: 如果命令以 'sudo ' 开头，取命令行之后的第一个非空行作为密码；否则为空
        """
        lines = body.splitlines()
        cmd = ""
        password = ""
        cmd_index = -1

        # 找到第一个以 @ 开头的行
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("@"):
                cmd = stripped[1:].strip()
                cmd_index = i
                break

        if not cmd:
            return "", ""

        # 如果命令以 sudo 开头，提取后面的密码行
        if cmd.lower().startswith("sudo "):
            for j in range(cmd_index + 1, len(lines)):
                pwd = lines[j].strip()
                if pwd:
                    password = pwd
                    break

        return cmd, password

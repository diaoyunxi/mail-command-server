#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件模块
存储服务器运行所需的配置项，提供安全的环境变量类型转换
"""

import os
import logging

logger = logging.getLogger(__name__)


def _get_int_env(key: str, default: int, min_val: int = None, max_val: int = None) -> int:
    """
    安全地从环境变量读取整数
    Args:
        key: 环境变量名
        default: 默认值（当变量未设置或非法时使用）
        min_val: 允许的最小值（None 表示不限制）
        max_val: 允许的最大值（None 表示不限制）
    Returns:
        合法的整数值
    """
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        val = int(raw)
    except (ValueError, TypeError):
        logger.warning("环境变量 %s 值 '%s' 不是合法整数，使用默认值 %s", key, raw, default)
        return default
    if min_val is not None and val < min_val:
        logger.warning("环境变量 %s 值 %s 低于最小值 %s，使用默认值 %s", key, val, min_val, default)
        return default
    if max_val is not None and val > max_val:
        logger.warning("环境变量 %s 值 %s 超过最大值 %s，使用默认值 %s", key, val, max_val, default)
        return default
    return val


def _get_str_env(key: str, default: str) -> str:
    """
    安全地从环境变量读取字符串，确保非 None
    """
    return os.getenv(key, default) or default


# ==================== 服务器配置 ====================
# 本地SMTP接收服务器监听地址和端口
SMTP_BIND_HOST = _get_str_env("SMTP_BIND_HOST", "0.0.0.0")
SMTP_BIND_PORT = _get_int_env("SMTP_BIND_PORT", 9930, min_val=1, max_val=65535)

# ==================== 邮件发送配置 ====================
# 用于回复邮件的SMTP服务器（需配置为实际可用的外发SMTP）
SMTP_OUT_HOST = _get_str_env("SMTP_OUT_HOST", "smtp.qq.com")
SMTP_OUT_PORT = _get_int_env("SMTP_OUT_PORT", 587, min_val=1, max_val=65535)
SMTP_OUT_TIMEOUT = _get_int_env("SMTP_OUT_TIMEOUT", 30, min_val=1, max_val=300)
SMTP_OUT_USER = _get_str_env("SMTP_OUT_USER", "")          # 发件邮箱账号
SMTP_OUT_PASS = _get_str_env("SMTP_OUT_PASS", "")          # 发件邮箱授权码/密码
SMTP_OUT_TLS = os.getenv("SMTP_OUT_TLS", "true").lower() == "true"

# 发件人显示名称
SENDER_NAME = _get_str_env("SENDER_NAME", "MailCommandBot")

# ==================== 安全白名单配置 ====================
# 允许触发命令执行的发件人邮箱（逗号分隔，留空表示不限制）
ALLOWED_SENDERS = _get_str_env("ALLOWED_SENDERS", "")
# 允许触发命令执行的邮箱域名（逗号分隔，留空表示不限制）
ALLOWED_DOMAINS = _get_str_env("ALLOWED_DOMAINS", "")

# ==================== 命令执行配置 ====================
# 命令执行超时时间（秒）
CMD_TIMEOUT = _get_int_env("CMD_TIMEOUT", 30, min_val=1, max_val=3600)
# 命令输出最大长度（字符）
CMD_MAX_OUTPUT = _get_int_env("CMD_MAX_OUTPUT", 50000, min_val=1024)
# 命令输出截取后追加的提示
CMD_TRUNCATE_HINT = "\n... [输出已截断，超出最大长度限制]"

# ==================== 邮件大小限制 ====================
# 单封邮件最大字节数（超过则拒绝处理，防止OOM）
MAX_EMAIL_SIZE = _get_int_env("MAX_EMAIL_SIZE", 10 * 1024 * 1024, min_val=1024, max_val=50 * 1024 * 1024)

# ==================== 自动更新配置 ====================
# GitHub仓库地址（用于自动更新）
GITHUB_REPO = _get_str_env("GITHUB_REPO", "")
# GitHub Token（用于访问私有仓库和提升API速率限制）
GITHUB_TOKEN = _get_str_env("GITHUB_TOKEN", "")
# 更新检查分支
UPDATE_BRANCH = _get_str_env("UPDATE_BRANCH", "main")
# 启动时是否检查更新
CHECK_UPDATE_ON_START = os.getenv("CHECK_UPDATE_ON_START", "true").lower() == "true"
# 最大重启次数（防止无限重启循环）
MAX_RESTART_COUNT = _get_int_env("MAX_RESTART_COUNT", 5, min_val=1, max_val=100)

# ==================== 日志配置 ====================
LOG_LEVEL = _get_str_env("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = _get_str_env("LOG_FILE", "mail_command_bot.log")
LOG_MAX_BYTES = _get_int_env("LOG_MAX_BYTES", 10 * 1024 * 1024, min_val=1024)  # 默认 10MB
LOG_BACKUP_COUNT = _get_int_env("LOG_BACKUP_COUNT", 5, min_val=1, max_val=100)

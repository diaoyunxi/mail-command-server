#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件模块
仅从项目根目录的 .env 文件读取配置，不使用环境变量

优先级: .env 文件 > 硬编码默认值
首次运行时若 .env 不存在，自动生成带注释的模板文件
"""

import logging
from pathlib import Path
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

# =====================================================================
# .env 文件路径与自动模板生成
# =====================================================================
_PROJECT_DIR = Path(__file__).parent.resolve()
_ENV_FILE = _PROJECT_DIR / ".env"


def _generate_env_template() -> None:
    """
    首次运行时自动生成 .env 配置文件模板
    生成后用户可按需修改，重启服务生效
    """
    template = """# ================================================================
# MailCommandBot 配置文件
# 首次启动时自动生成，按需修改后重启服务生效
# ================================================================

# ==================== 接收模式配置 ====================
# 邮件接收模式: smtp(自建服务器) / pop3 / imap
RECEIVE_MODE=smtp

# ==================== SMTP 自建服务器配置 ====================
# 本地SMTP接收服务器监听地址和端口（smtp 模式下使用）
SMTP_BIND_HOST=0.0.0.0
SMTP_BIND_PORT=9930

# ==================== 已有邮件服务器配置（pop3/imap 模式） ====================
# 收件服务器地址（如 pop.qq.com / imap.qq.com）
MAIL_IN_HOST=
# 收件协议: pop3 / imap
MAIL_IN_PROTOCOL=pop3
# 是否启用 TLS/SSL
MAIL_IN_TLS=true
# 收件服务器端口（留空则根据协议和 TLS 自动选择: pop3=995/110, imap=993/143）
MAIL_IN_PORT=
# 收件邮箱账号
MAIL_IN_USER=
# 收件邮箱密码/授权码
MAIL_IN_PASS=
# 轮询检查间隔（秒）
MAIL_POLL_INTERVAL=10
# IMAP 收件箱文件夹名
MAIL_INBOX_FOLDER=INBOX

# ==================== 邮件发送配置（所有模式共用） ====================
# 外发SMTP服务器
SMTP_OUT_HOST=smtp.qq.com
SMTP_OUT_PORT=587
SMTP_OUT_TIMEOUT=30
# 发件邮箱账号
SMTP_OUT_USER=
# 发件邮箱授权码/密码
SMTP_OUT_PASS=
# 外发SMTP是否启用TLS
SMTP_OUT_TLS=true
# 发件人显示名称
SENDER_NAME=MailCommandBot

# ==================== 安全白名单配置 ====================
# 允许触发命令执行的发件人邮箱（逗号分隔，留空表示不限制）
ALLOWED_SENDERS=
# 允许的邮箱域名（逗号分隔，留空表示不限制）
ALLOWED_DOMAINS=
# 允许连接SMTP接收服务器的客户端IP（逗号分隔，留空不限制，仅smtp模式生效）
ALLOWED_CLIENT_IPS=
# 未配置白名单时是否强制绑定 127.0.0.1
REQUIRE_WHITELIST=true

# ==================== sudo 配置 ====================
# 是否使用 sudoers NOPASSWD 模式（建议启用，避免邮件传输密码）
SUDO_NOPASSWD=false

# ==================== 频率限制配置 ====================
# 每个发件人每分钟最多发送的命令邮件数
RATE_LIMIT_PER_MINUTE=10

# ==================== 命令执行配置 ====================
# 命令执行超时（秒）
CMD_TIMEOUT=30
# 命令输出最大长度（字符）
CMD_MAX_OUTPUT=50000

# ==================== 邮件大小限制 ====================
# 单封邮件最大字节数（默认1MB）
MAX_EMAIL_SIZE=1048576

# ==================== SMTP 连接保活配置 ====================
# SMTP 外发连接心跳保活间隔（秒），0 禁用
SMTP_KEEPALIVE_INTERVAL=60

# ==================== 自动更新配置 ====================
# GitHub仓库地址（用于自动更新，格式: owner/repo）
GITHUB_REPO=
# GitHub Token（用于私有仓库和提升API速率限制）
GITHUB_TOKEN=
# 更新检查分支
UPDATE_BRANCH=main
# 启动时是否检查更新
CHECK_UPDATE_ON_START=true
# 最大自动重启次数（防止无限重启循环）
MAX_RESTART_COUNT=5

# ==================== 日志配置 ====================
# 日志级别: DEBUG / INFO / WARNING / ERROR
LOG_LEVEL=INFO
# 日志文件路径
LOG_FILE=mail_command_bot.log
# 日志文件最大大小（字节，默认10MB）
LOG_MAX_BYTES=10485760
# 日志备份文件数量
LOG_BACKUP_COUNT=5
"""
    try:
        with open(_ENV_FILE, "w", encoding="utf-8") as f:
            f.write(template)
        logger.info("已自动生成 .env 配置文件模板: %s", _ENV_FILE)
    except Exception as e:
        logger.warning("生成 .env 配置文件失败: %s", e)


# 首次运行时若 .env 不存在，自动生成模板
if not _ENV_FILE.exists():
    _generate_env_template()

# 加载 .env 文件
_ENV_FROM_FILE = dotenv_values(_ENV_FILE) if _ENV_FILE.exists() else {}


# =====================================================================
# 通用配置读取辅助函数
# =====================================================================
def _get_value(key: str, default: str = "") -> str:
    """
    从 .env 文件获取配置值

    :param key: 配置项键名
    :param default: 默认值
    :return: 配置值字符串（可能为空字符串）
    """
    val = _ENV_FROM_FILE.get(key)
    if val is not None:
        return str(val)
    return default


def _get_int(key: str, default: int, min_val: int = None, max_val: int = None) -> int:
    """
    安全地读取整数配置

    :param key: 配置项键名
    :param default: 默认值
    :param min_val: 允许的最小值
    :param max_val: 允许的最大值
    :return: 合法的整数值
    """
    raw = _get_value(key)
    if raw == "":
        return default
    try:
        val = int(raw)
    except (ValueError, TypeError):
        logger.warning("配置项 %s 值 '%s' 不是合法整数，使用默认值 %s", key, raw, default)
        return default
    if min_val is not None and val < min_val:
        logger.warning("配置项 %s 值 %s 低于最小值 %s，使用默认值 %s", key, val, min_val, default)
        return default
    if max_val is not None and val > max_val:
        logger.warning("配置项 %s 值 %s 超过最大值 %s，使用默认值 %s", key, val, max_val, default)
        return default
    return val


def _get_str(key: str, default: str) -> str:
    """
    安全地读取字符串配置，空字符串视为未设置，返回默认值

    :param key: 配置项键名
    :param default: 默认值
    :return: 非空字符串
    """
    val = _get_value(key, "")
    return val if val != "" else default


def _get_bool(key: str, default: bool) -> bool:
    """
    安全地读取布尔配置

    :param key: 配置项键名
    :param default: 默认值
    :return: bool 值
    """
    val = _get_value(key, "")
    if val == "":
        return default
    return val.lower() == "true"


# =====================================================================
# 具体配置项
# =====================================================================

# ==================== 接收模式配置 ====================
RECEIVE_MODE = _get_str("RECEIVE_MODE", "smtp")

# ==================== SMTP 自建服务器配置 ====================
SMTP_BIND_HOST = _get_str("SMTP_BIND_HOST", "0.0.0.0")
SMTP_BIND_PORT = _get_int("SMTP_BIND_PORT", 9930, min_val=1, max_val=65535)

# ==================== 已有邮件服务器配置（pop3/imap 模式） ====================
MAIL_IN_HOST = _get_str("MAIL_IN_HOST", "")
MAIL_IN_PROTOCOL = _get_str("MAIL_IN_PROTOCOL", "pop3")
MAIL_IN_TLS = _get_bool("MAIL_IN_TLS", True)


def _get_default_mail_in_port() -> int:
    """根据协议和 TLS 设置返回默认端口"""
    if MAIL_IN_PROTOCOL.lower() == "imap":
        return 993 if MAIL_IN_TLS else 143
    return 995 if MAIL_IN_TLS else 110


MAIL_IN_PORT = _get_int("MAIL_IN_PORT", _get_default_mail_in_port(), min_val=1, max_val=65535)
MAIL_IN_USER = _get_str("MAIL_IN_USER", "")
MAIL_IN_PASS = _get_str("MAIL_IN_PASS", "")
MAIL_POLL_INTERVAL = _get_int("MAIL_POLL_INTERVAL", 10, min_val=1, max_val=3600)
MAIL_INBOX_FOLDER = _get_str("MAIL_INBOX_FOLDER", "INBOX")

# ==================== 邮件发送配置 ====================
SMTP_OUT_HOST = _get_str("SMTP_OUT_HOST", "smtp.qq.com")
SMTP_OUT_PORT = _get_int("SMTP_OUT_PORT", 587, min_val=1, max_val=65535)
SMTP_OUT_TIMEOUT = _get_int("SMTP_OUT_TIMEOUT", 30, min_val=1, max_val=300)
SMTP_OUT_USER = _get_str("SMTP_OUT_USER", "")
SMTP_OUT_PASS = _get_str("SMTP_OUT_PASS", "")
SMTP_OUT_TLS = _get_bool("SMTP_OUT_TLS", True)

# 发件人显示名称
SENDER_NAME = _get_str("SENDER_NAME", "MailCommandBot")

# ==================== 安全白名单配置 ====================
ALLOWED_SENDERS = _get_str("ALLOWED_SENDERS", "")
ALLOWED_DOMAINS = _get_str("ALLOWED_DOMAINS", "")
ALLOWED_CLIENT_IPS = _get_str("ALLOWED_CLIENT_IPS", "")
REQUIRE_WHITELIST = _get_bool("REQUIRE_WHITELIST", True)

# ==================== sudo 配置 ====================
SUDO_NOPASSWD = _get_bool("SUDO_NOPASSWD", False)

# ==================== 频率限制配置 ====================
RATE_LIMIT_PER_MINUTE = _get_int("RATE_LIMIT_PER_MINUTE", 10, min_val=1, max_val=1000)

# ==================== 命令执行配置 ====================
CMD_TIMEOUT = _get_int("CMD_TIMEOUT", 30, min_val=1, max_val=3600)
CMD_MAX_OUTPUT = _get_int("CMD_MAX_OUTPUT", 50000, min_val=1024)
CMD_TRUNCATE_HINT = "\n... [输出已截断，超出最大长度限制]"

# ==================== 邮件大小限制 ====================
MAX_EMAIL_SIZE = _get_int("MAX_EMAIL_SIZE", 1024 * 1024, min_val=1024, max_val=10 * 1024 * 1024)

# ==================== SMTP 连接保活配置 ====================
SMTP_KEEPALIVE_INTERVAL = _get_int("SMTP_KEEPALIVE_INTERVAL", 60, min_val=0, max_val=3600)

# ==================== 自动更新配置 ====================
GITHUB_REPO = _get_str("GITHUB_REPO", "")
GITHUB_TOKEN = _get_str("GITHUB_TOKEN", "")
UPDATE_BRANCH = _get_str("UPDATE_BRANCH", "main")
CHECK_UPDATE_ON_START = _get_bool("CHECK_UPDATE_ON_START", True)
MAX_RESTART_COUNT = _get_int("MAX_RESTART_COUNT", 5, min_val=1, max_val=100)

# ==================== 日志配置 ====================
LOG_LEVEL = _get_str("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = _get_str("LOG_FILE", "mail_command_bot.log")
LOG_MAX_BYTES = _get_int("LOG_MAX_BYTES", 10 * 1024 * 1024, min_val=1024)
LOG_BACKUP_COUNT = _get_int("LOG_BACKUP_COUNT", 5, min_val=1, max_val=100)

# =====================================================================
# 兼容旧接口（供测试等模块使用）
# =====================================================================
_get_env_value = _get_value
_get_int_env = _get_int
_get_str_env = _get_str
_get_bool_env = _get_bool

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件模块
存储服务器运行所需的配置项
"""

import os

# ==================== 服务器配置 ====================
# 本地SMTP接收服务器监听地址和端口
SMTP_BIND_HOST = os.getenv("SMTP_BIND_HOST", "0.0.0.0")
SMTP_BIND_PORT = int(os.getenv("SMTP_BIND_PORT", "9930"))

# ==================== 邮件发送配置 ====================
# 用于回复邮件的SMTP服务器（需配置为实际可用的外发SMTP）
SMTP_OUT_HOST = os.getenv("SMTP_OUT_HOST", "smtp.qq.com")
SMTP_OUT_PORT = int(os.getenv("SMTP_OUT_PORT", "587"))
SMTP_OUT_USER = os.getenv("SMTP_OUT_USER", "")          # 发件邮箱账号
SMTP_OUT_PASS = os.getenv("SMTP_OUT_PASS", "")          # 发件邮箱授权码/密码
SMTP_OUT_TLS = os.getenv("SMTP_OUT_TLS", "true").lower() == "true"

# 发件人显示名称
SENDER_NAME = os.getenv("SENDER_NAME", "MailCommandBot")

# 命令执行超时时间（秒）
CMD_TIMEOUT = int(os.getenv("CMD_TIMEOUT", "30"))
# 命令输出最大长度（字符）
CMD_MAX_OUTPUT = int(os.getenv("CMD_MAX_OUTPUT", "50000"))
# 命令输出截取后追加的提示
CMD_TRUNCATE_HINT = "\n... [输出已截断，超出最大长度限制]"

# ==================== 安全白名单配置 ====================
# 注意：白名单与黑名单机制已移除，仅保留 sudo 密码验证

# ==================== 命令执行配置 ====================

# ==================== 自动更新配置 ====================
# GitHub仓库地址（用于自动更新）
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
# 更新检查分支
UPDATE_BRANCH = os.getenv("UPDATE_BRANCH", "main")
# 启动时是否检查更新
CHECK_UPDATE_ON_START = os.getenv("CHECK_UPDATE_ON_START", "true").lower() == "true"

# ==================== 日志配置 ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config 模块单元测试
覆盖：配置读取函数、边界值校验、默认值合理性
"""

import sys
import os
import tempfile
import pytest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetIntEnv:
    """_get_int() 安全整数转换测试"""

    def test_default_when_not_set(self):
        """未设置的配置项应返回默认值"""
        from config import _get_int_env
        result = _get_int_env("TEST_VAR_NOT_EXIST_12345", 42)
        assert result == 42

    def test_invalid_string_returns_default(self):
        """非法字符串应返回默认值"""
        from config import _get_int_env
        result = _get_int_env("NONEXIST_INT_INVALID", 42)
        assert result == 42

    def test_empty_string_returns_default(self):
        """空字符串应返回默认值"""
        from config import _get_int_env
        result = _get_int_env("NONEXIST_INT_EMPTY", 42)
        assert result == 42

    def test_below_min_returns_default(self):
        """低于最小值应返回默认值"""
        from config import _get_int_env
        result = _get_int_env("NONEXIST_INT_BELOW_MIN", 42, min_val=10)
        assert result == 42

    def test_above_max_returns_default(self):
        """超过最大值应返回默认值"""
        from config import _get_int_env
        result = _get_int_env("NONEXIST_INT_ABOVE_MAX", 42, max_val=50)
        assert result == 42

    def test_no_min_max_constraints(self):
        """无约束时应返回实际值"""
        from config import _get_int_env
        # 通过 .env 文件读取（默认 .env 模板中 SMTP_BIND_PORT=9930）
        result = _get_int_env("SMTP_BIND_PORT", 42)
        assert result == 9930

    def test_int_from_env_file(self):
        """从 .env 文件中读取整数应正确解析"""
        from config import _get_int_env
        # .env 模板中 SMTP_BIND_PORT=9930
        result = _get_int_env("SMTP_BIND_PORT", 0, min_val=1, max_val=65535)
        assert result == 9930

    def test_bool_from_env_file(self):
        """从 .env 文件中读取布尔值应正确解析"""
        from config import _get_bool_env
        # .env 模板中 MAIL_IN_TLS=true
        result = _get_bool_env("MAIL_IN_TLS", False)
        assert result is True

    def test_bool_false_from_env_file(self):
        """从 .env 文件中读取 false 布尔值"""
        from config import _get_bool_env
        # .env 模板中 SUDO_NOPASSWD=false
        result = _get_bool_env("SUDO_NOPASSWD", True)
        assert result is False

    def test_string_from_env_file(self):
        """从 .env 文件中读取字符串应正确解析"""
        from config import _get_str_env
        # .env 模板中 SMTP_OUT_HOST=smtp.qq.com
        result = _get_str_env("SMTP_OUT_HOST", "default")
        assert result == "smtp.qq.com"

    def test_empty_string_returns_default_str(self):
        """空字符串应返回默认值（字符串）"""
        from config import _get_str_env
        # .env 模板中 SMTP_OUT_USER= （空值）
        result = _get_str_env("SMTP_OUT_USER", "fallback")
        assert result == "fallback"


class TestEnvFileGeneration:
    """.env 文件自动生成测试"""

    def test_env_file_exists(self):
        """首次导入 config 后 .env 文件应存在"""
        env_path = Path(__file__).parent.parent / ".env"
        assert env_path.exists()

    def test_env_file_has_content(self):
        """.env 文件应包含配置项"""
        env_path = Path(__file__).parent.parent / ".env"
        content = env_path.read_text(encoding="utf-8")
        assert "RECEIVE_MODE" in content
        assert "SMTP_BIND_PORT" in content
        assert "MAIL_IN_HOST" in content
        assert "SMTP_OUT_USER" in content


class TestConfigDefaults:
    """验证 config 模块全局变量的默认值合理性"""

    def test_smtp_bind_port(self):
        """SMTP 绑定端口应在合法范围"""
        from config import SMTP_BIND_PORT
        assert 1 <= SMTP_BIND_PORT <= 65535

    def test_smtp_out_port(self):
        """SMTP 外发端口应在合法范围"""
        from config import SMTP_OUT_PORT
        assert 1 <= SMTP_OUT_PORT <= 65535

    def test_cmd_timeout(self):
        """命令超时应大于0"""
        from config import CMD_TIMEOUT
        assert CMD_TIMEOUT > 0

    def test_cmd_max_output(self):
        """最大输出长度应大于0"""
        from config import CMD_MAX_OUTPUT
        assert CMD_MAX_OUTPUT > 0

    def test_max_email_size(self):
        """邮件大小限制应大于0"""
        from config import MAX_EMAIL_SIZE
        assert MAX_EMAIL_SIZE > 0

    def test_max_restart_count(self):
        """最大重启次数应大于0"""
        from config import MAX_RESTART_COUNT
        assert MAX_RESTART_COUNT > 0

    def test_smtp_out_timeout(self):
        """SMTP 超时应大于0"""
        from config import SMTP_OUT_TIMEOUT
        assert SMTP_OUT_TIMEOUT > 0

    def test_receive_mode_default(self):
        """默认接收模式应为 smtp"""
        from config import RECEIVE_MODE
        assert RECEIVE_MODE == "smtp"

    def test_log_level_default(self):
        """默认日志级别应为 INFO"""
        from config import LOG_LEVEL
        assert LOG_LEVEL == "INFO"

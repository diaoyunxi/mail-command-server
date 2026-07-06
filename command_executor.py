#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令执行模块
执行以 @ 开头的 Linux 命令，支持 sudo 密码传入
"""

import subprocess
import logging
from typing import Tuple
import config

logger = logging.getLogger(__name__)


class CommandExecutor:
    """命令执行器：执行 shell 命令并返回输出"""

    @staticmethod
    def validate(cmd: str) -> Tuple[bool, str]:
        """
        校验命令是否允许执行
        Returns: (是否允许, 拒绝原因)
        """
        if not cmd or not cmd.strip():
            return False, "命令为空"
        return True, ""

    @staticmethod
    def execute(cmd: str, password: str = "") -> Tuple[int, str, str]:
        """
        执行命令并返回结果
        Args:
            cmd: 要执行的 shell 命令字符串
            password: 若命令包含 sudo，此处传入密码
        Returns:
            (returncode, stdout, stderr)
        """
        allowed, reason = CommandExecutor.validate(cmd)
        if not allowed:
            logger.warning("命令被拦截: %s, 原因: %s", cmd, reason)
            return -1, "", f"[命令被拒绝] {reason}"

        # 构造实际执行的命令
        actual_cmd = cmd
        if cmd.lower().startswith("sudo "):
            if password:
                # 使用 sudo -S 从 stdin 读取密码
                actual_cmd = f"echo '{password}' | sudo -S {cmd[5:].strip()}"
                logger.info("执行 sudo 命令（已提供密码）: %s", cmd)
            else:
                logger.info("执行 sudo 命令（无密码）: %s", cmd)
        else:
            logger.info("执行命令: %s", cmd)

        try:
            proc = subprocess.Popen(
                actual_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd="/",
            )
            stdout, stderr = proc.communicate(timeout=config.CMD_TIMEOUT)
            rc = proc.returncode

        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            logger.warning("命令执行超时: %s", cmd)
            return -1, stdout, f"[命令执行超时，已超过 {config.CMD_TIMEOUT} 秒]\n{stderr}"
        except Exception as e:
            logger.error("命令执行异常: %s, 错误: %s", cmd, e)
            return -1, "", f"[命令执行异常] {str(e)}"

        # 截断过长输出
        stdout = CommandExecutor._truncate(stdout)
        stderr = CommandExecutor._truncate(stderr)

        return rc, stdout, stderr

    @staticmethod
    def _truncate(text: str) -> str:
        """截断超过最大长度的输出"""
        if len(text) > config.CMD_MAX_OUTPUT:
            return text[:config.CMD_MAX_OUTPUT] + config.CMD_TRUNCATE_HINT
        return text

    @staticmethod
    def format_result(rc: int, stdout: str, stderr: str, cmd: str, has_password: bool = False) -> str:
        """格式化命令执行结果为邮件正文"""
        lines = [
            f"执行命令: {cmd}",
        ]
        if cmd.lower().startswith("sudo "):
            lines.append(f"sudo 密码: {'已提供' if has_password else '未提供'}")
        lines.append(f"返回码: {rc}")
        lines.append("=" * 40)
        if stdout:
            lines.append("[标准输出]")
            lines.append(stdout)
        if stderr:
            lines.append("[标准错误]")
            lines.append(stderr)
        if not stdout and not stderr:
            lines.append("(无输出)")
        return "\n".join(lines)

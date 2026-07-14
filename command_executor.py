#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令执行模块
执行以 @ 开头的 Linux 命令，支持 sudo 密码传入
包含命令黑名单校验，防止危险命令执行
"""

import os
import re
import shlex
import signal
import subprocess
import logging
from typing import Tuple
import config

logger = logging.getLogger(__name__)

# ==================== 危险命令黑名单 ====================
# 匹配高危命令模式，防止通过邮件执行破坏性操作
BLOCKED_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*rf\b",          # rm -rf（强制递归删除）
    r"\brm\s+-[a-zA-Z]*fr\b",          # rm -fr
    r"\bmkfs\b",                        # 格式化文件系统
    r"\bshutdown\b",                    # 关机
    r"\breboot\b",                      # 重启
    r"\binit\s+[06]\b",                 # 切换运行级别（关机/重启）
    r"\bhalt\b",                        # 停机
    r"\bpoweroff\b",                    # 关闭电源
    r"\bdd\s+if=",                      # dd 磁盘写入（可能覆盖整个磁盘）
    r"\b>\s*/dev/",                     # 重定向到设备文件
    r"\bchmod\s+-R\s+[0-7]*[7]\s+/",   # 递归 chmod 到根目录
    r"\bchown\s+-R\b",                  # 递归 chown
    r"\bpasswd\b",                      # 修改密码
    r"\buseradd\b.*\s+/bin/bash",       # 添加可登录用户
    r"\buserdel\b",                     # 删除用户
    r"\bcrontab\b",                     # 修改定时任务
    r"\biptables\s+-F\b",              # 清空防火墙规则
    r"\b>\s*/dev/sd[a-z]",             # 覆盖磁盘设备
    r"\bcurl\b.*\|\s*(ba)?sh\b",       # curl 管道到 shell（远程脚本执行）
    r"\bwget\b.*\|\s*(ba)?sh\b",       # wget 管道到 shell
    r"\beval\b",                        # eval 命令执行
    r"\bexec\b",                        # exec 替换进程
    r"\bsource\b",                      # source 执行脚本
    r"\b\.\s+/",                         # 点号执行脚本（如 . /tmp/malicious.sh）
    r"\bnc\b.*-[elp]",                  # netcat 监听/反向 shell
    r"\bpython[23]?\s+-c\b",            # python -c 执行任意代码
    r"\bperl\s+-e\b",                   # perl -e 执行任意代码
    r"\bruby\s+-e\b",                   # ruby -e 执行任意代码
    r"\bphp\s+-r\b",                    # php -r 执行任意代码
]


class CommandExecutor:
    """命令执行器：执行 shell 命令并返回输出，内置安全校验"""

    @staticmethod
    def validate(cmd: str) -> Tuple[bool, str]:
        """
        校验命令是否允许执行（黑名单 + 空值检查）
        Args:
            cmd: 待校验的命令字符串
        Returns:
            (是否允许, 拒绝原因) - 允许时原因为空字符串
        """
        if not cmd or not cmd.strip():
            return False, "命令为空"

        cmd_stripped = cmd.strip()

        # 检查危险命令黑名单
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, cmd_stripped, re.IGNORECASE):
                return False, f"命令包含被禁止的危险操作（匹配规则: {pattern}）"

        # 检查命令长度，防止超长命令
        if len(cmd_stripped) > 4096:
            return False, f"命令过长（{len(cmd_stripped)} 字符），最大允许 4096 字符"

        return True, ""

    @staticmethod
    def execute(cmd: str, password: str = "") -> Tuple[int, str, str]:
        """
        安全执行命令并返回结果
        使用 shlex.split + subprocess.Popen(shell=False) 杜绝命令注入
        密码通过 stdin 传入，不暴露在命令行中
        Args:
            cmd: 要执行的 shell 命令字符串
            password: 若命令包含 sudo，此处传入密码
        Returns:
            (returncode, stdout, stderr)
        """
        # 安全校验
        allowed, reason = CommandExecutor.validate(cmd)
        if not allowed:
            logger.warning("命令被拦截: %s, 原因: %s", cmd, reason)
            return -1, "", f"[命令被拒绝] {reason}"

        # 解析命令：使用 shlex.split 安全拆分参数
        is_sudo = cmd.lower().startswith("sudo ")
        if is_sudo:
            real_cmd = cmd[5:].strip()
            if not real_cmd:
                return -1, "", "[命令被拒绝] sudo 后缺少实际命令"
            # 二次校验：sudo 后的子命令也需要通过黑名单
            sub_allowed, sub_reason = CommandExecutor.validate(real_cmd)
            if not sub_allowed:
                logger.warning("sudo 子命令被拦截: %s, 原因: %s", real_cmd, sub_reason)
                return -1, "", f"[命令被拒绝] {sub_reason}"
            try:
                cmd_parts = ["sudo", "-S"] + shlex.split(real_cmd)
            except ValueError as e:
                return -1, "", f"[命令解析失败] {e}"
            logger.info("执行 sudo 命令: %s", cmd)
        else:
            try:
                cmd_parts = shlex.split(cmd)
            except ValueError as e:
                return -1, "", f"[命令解析失败] {e}"
            logger.info("执行命令: %s", cmd)

        # 执行命令：shell=False 彻底杜绝注入
        try:
            proc = subprocess.Popen(
                cmd_parts,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                cwd="/",
                start_new_session=True,  # 创建新进程组，便于整体 kill
            )
            # 通过 stdin 传入 sudo 密码（不暴露在命令行）
            if is_sudo and password:
                stdout, stderr = proc.communicate(
                    input=password + "\n",
                    timeout=config.CMD_TIMEOUT
                )
            else:
                stdout, stderr = proc.communicate(
                    timeout=config.CMD_TIMEOUT
                )
            rc = proc.returncode

        except subprocess.TimeoutExpired:
            # 超时时杀死整个进程组（包括子进程），防止残留
            CommandExecutor._kill_process_group(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            logger.warning("命令执行超时: %s", cmd)
            return -1, stdout or "", f"[命令执行超时，已超过 {config.CMD_TIMEOUT} 秒]\n{stderr or ''}"
        except FileNotFoundError:
            logger.error("命令不存在: %s", cmd_parts[0] if cmd_parts else cmd)
            return -1, "", f"[命令执行失败] 找不到命令: {cmd_parts[0] if cmd_parts else cmd}"
        except PermissionError:
            logger.error("权限不足: %s", cmd)
            return -1, "", f"[命令执行失败] 权限不足，请使用 sudo"
        except OSError as e:
            logger.error("命令执行系统错误: %s, 错误: %s", cmd, e)
            return -1, "", f"[命令执行系统错误] {str(e)}"
        except Exception as e:
            logger.error("命令执行异常: %s, 错误: %s", cmd, e)
            return -1, "", f"[命令执行异常] {str(e)}"

        # 截断过长输出
        stdout = CommandExecutor._truncate(stdout)
        stderr = CommandExecutor._truncate(stderr)

        return rc, stdout, stderr

    @staticmethod
    def _kill_process_group(proc: subprocess.Popen) -> None:
        """
        杀死进程及其所有子进程（通过进程组）
        Args:
            proc: subprocess.Popen 对象
        """
        try:
            pgid = os.getpgid(proc.pid)
            if pgid > 0:
                os.killpg(pgid, signal.SIGKILL)
            else:
                proc.kill()
        except (ProcessLookupError, OSError):
            # 进程可能已结束
            proc.kill()

    @staticmethod
    def _truncate(text: str) -> str:
        """截断超过最大长度的输出"""
        if len(text) > config.CMD_MAX_OUTPUT:
            return text[:config.CMD_MAX_OUTPUT] + config.CMD_TRUNCATE_HINT
        return text

    @staticmethod
    def format_result(rc: int, stdout: str, stderr: str, cmd: str, has_password: bool = False) -> str:
        """
        格式化命令执行结果为邮件正文
        Args:
            rc: 返回码
            stdout: 标准输出
            stderr: 标准错误
            cmd: 原始命令
            has_password: 是否提供了 sudo 密码
        Returns:
            格式化后的结果文本
        """
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

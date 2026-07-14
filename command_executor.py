#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令执行模块
执行以 @ 开头的 Linux 命令，支持 sudo 密码传入
使用命令白名单模式，仅允许预定义的安全命令执行
包含敏感信息脱敏、命令模板、输出大小限制等安全机制
"""

import os
import re
import shlex
import signal
import subprocess
import logging
from typing import Tuple, Optional
import config

logger = logging.getLogger(__name__)

# ==================== 命令白名单 ====================
# 仅允许以下安全命令执行，其他命令一律拒绝
ALLOWED_COMMANDS = frozenset({
    "ls", "cat", "df", "ps", "uptime", "free", "head", "tail",
    "grep", "wc", "date", "whoami", "id", "uname", "ifconfig",
    "ip", "netstat", "ss", "top", "du", "find",
})

# find 命令的危险参数（禁止使用，防止删除文件或执行任意命令）
FIND_DANGEROUS_ARGS = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir"})

# 禁止的 shell 元字符（管道、重定向、命令替换等），防止命令注入
# 注意：不禁止 [ ] ! { } 等在正则表达式参数中常见的字符
_BLOCKED_META_PATTERN = re.compile(r'[|;`$()>&<]')

# 敏感参数脱敏正则（匹配 -p / --password / --pass 后跟的值）
_SENSITIVE_PARAM_PATTERN = re.compile(
    r'(-p\s+|--password\s+|--pass\s+)\S+',
    re.IGNORECASE
)

# ==================== 命令模板 ====================
# 预定义安全命令模板，用户可在邮件中通过 @template:名称 引用
COMMAND_TEMPLATES = {
    "disk": "df -h",
    "memory": "free -h",
    "process": "ps aux",
    "uptime": "uptime",
    "network": "ss -tlnp",
    "ports": "netstat -tlnp",
    "disk_usage": "du -sh /",
    "system": "uname -a",
    "identity": "id",
    "date": "date",
    "whoami": "whoami",
}


def _sanitize_cmd(cmd: str) -> str:
    """
    对命令中的敏感信息进行脱敏处理
    将 -p / --password 后面的值替换为 ***
    Args:
        cmd: 原始命令字符串
    Returns:
        脱敏后的命令字符串
    """
    return _SENSITIVE_PARAM_PATTERN.sub(r'\1***', cmd)


class CommandExecutor:
    """命令执行器：执行 shell 命令并返回输出，内置白名单安全校验"""

    @staticmethod
    def validate(cmd: str) -> Tuple[bool, str]:
        """
        校验命令是否允许执行（白名单 + 空值检查 + 长度检查 + 元字符检查）
        Args:
            cmd: 待校验的命令字符串
        Returns:
            (是否允许, 拒绝原因) - 允许时原因为空字符串
        """
        if not cmd or not cmd.strip():
            return False, "命令为空"

        cmd_stripped = cmd.strip()

        # 检查命令长度，防止超长命令
        if len(cmd_stripped) > 4096:
            return False, f"命令过长（{len(cmd_stripped)} 字符），最大允许 4096 字符"

        # 禁止 shell 元字符（管道、重定向、命令替换等），防止命令注入
        if _BLOCKED_META_PATTERN.search(cmd_stripped):
            return False, "命令包含危险的特殊字符（管道/重定向/命令替换等），拒绝执行"

        # 使用 shlex 解析命令
        try:
            parts = shlex.split(cmd_stripped)
        except ValueError as e:
            return False, f"命令解析失败: {e}"

        if not parts:
            return False, "命令为空"

        # 检查是否是 sudo 命令，如是则跳过 sudo 本身校验后续命令
        is_sudo = parts[0].lower() == "sudo"
        if is_sudo:
            # sudo 命令：跳过 sudo 及其标志参数，找到实际命令
            cmd_idx = 1
            while cmd_idx < len(parts) and parts[cmd_idx].startswith("-"):
                # 跳过 -u username 等带参数的选项
                if parts[cmd_idx] in ("-u", "--user") and cmd_idx + 1 < len(parts):
                    cmd_idx += 2
                else:
                    cmd_idx += 1
            if cmd_idx >= len(parts):
                return False, "sudo 后缺少实际命令"
            cmd_name = os.path.basename(parts[cmd_idx])
            check_start = cmd_idx + 1
        else:
            cmd_name = os.path.basename(parts[0])
            check_start = 1

        # 检查命令是否在白名单中
        if cmd_name not in ALLOWED_COMMANDS:
            return False, f"命令 '{cmd_name}' 不在安全白名单中，拒绝执行（危险操作）"

        # 对 find 命令检查危险参数
        if cmd_name == "find":
            for arg in parts[check_start:]:
                if arg in FIND_DANGEROUS_ARGS:
                    return False, f"find 命令不允许使用危险参数 {arg}（-delete/-exec 等）"

        return True, ""

    @staticmethod
    def resolve_template(cmd: str) -> Optional[str]:
        """
        解析命令模板引用，格式为 template:名称
        Args:
            cmd: 原始命令字符串
        Returns:
            模板对应的命令字符串，若不是模板或模板不存在则返回 None
        """
        if not cmd:
            return None
        stripped = cmd.strip()
        if stripped.startswith("template:"):
            template_name = stripped[len("template:"):].strip()
            return COMMAND_TEMPLATES.get(template_name)
        return None

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
        # 命令模板解析
        resolved = CommandExecutor.resolve_template(cmd)
        if resolved is not None:
            cmd = resolved

        # 安全校验
        allowed, reason = CommandExecutor.validate(cmd)
        if not allowed:
            # 日志记录脱敏后的命令
            logger.warning("命令被拦截: %s, 原因: %s", _sanitize_cmd(cmd), reason)
            return -1, "", f"[命令被拒绝] {reason}"

        # 解析命令：使用 shlex.split 安全拆分参数
        is_sudo = cmd.lower().startswith("sudo ")
        if is_sudo:
            real_cmd = cmd[5:].strip()
            if not real_cmd:
                return -1, "", "[命令被拒绝] sudo 后缺少实际命令"
            # 二次校验：sudo 后的子命令也需要通过白名单
            sub_allowed, sub_reason = CommandExecutor.validate(real_cmd)
            if not sub_allowed:
                logger.warning("sudo 子命令被拦截: %s, 原因: %s", _sanitize_cmd(real_cmd), sub_reason)
                return -1, "", f"[命令被拒绝] {sub_reason}"
            try:
                cmd_parts = ["sudo", "-S"] + shlex.split(real_cmd)
            except ValueError as e:
                return -1, "", f"[命令解析失败] {e}"
            # 日志记录脱敏后的命令
            logger.info("执行 sudo 命令: %s", _sanitize_cmd(cmd))
        else:
            try:
                cmd_parts = shlex.split(cmd)
            except ValueError as e:
                return -1, "", f"[命令解析失败] {e}"
            # 日志记录脱敏后的命令
            logger.info("执行命令: %s", _sanitize_cmd(cmd))

        # 执行命令：shell=False 彻底杜绝注入
        proc = None
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
            # 日志记录脱敏后的命令
            logger.warning("命令执行超时: %s", _sanitize_cmd(cmd))
            return -1, stdout or "", f"[命令执行超时，已超过 {config.CMD_TIMEOUT} 秒]\n{stderr or ''}"
        except FileNotFoundError:
            logger.error("命令不存在: %s", cmd_parts[0] if cmd_parts else cmd)
            return -1, "", f"[命令执行失败] 找不到命令: {cmd_parts[0] if cmd_parts else cmd}"
        except PermissionError:
            logger.error("权限不足: %s", _sanitize_cmd(cmd))
            return -1, "", f"[命令执行失败] 权限不足，请使用 sudo"
        except ValueError as e:
            # 更具体的异常捕获：参数值错误
            logger.error("命令参数错误: %s, 错误: %s", _sanitize_cmd(cmd), e)
            return -1, "", f"[命令执行失败] 参数错误: {str(e)}"
        except OSError as e:
            logger.error("命令执行系统错误: %s, 错误: %s", _sanitize_cmd(cmd), e)
            return -1, "", f"[命令执行系统错误] {str(e)}"
        except Exception as e:
            logger.error("命令执行异常: %s, 错误: %s", _sanitize_cmd(cmd), e)
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
        对命令做脱敏处理后再格式化，避免敏感信息泄露
        Args:
            rc: 返回码
            stdout: 标准输出
            stderr: 标准错误
            cmd: 原始命令
            has_password: 是否提供了 sudo 密码
        Returns:
            格式化后的结果文本
        """
        # 对命令做脱敏处理，防止敏感信息出现在回复邮件中
        safe_cmd = _sanitize_cmd(cmd)
        lines = [
            f"执行命令: {safe_cmd}",
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

    @staticmethod
    def get_allowed_commands() -> frozenset:
        """获取允许执行的命令白名单"""
        return ALLOWED_COMMANDS

    @staticmethod
    def get_command_templates() -> dict:
        """获取预定义命令模板"""
        return dict(COMMAND_TEMPLATES)

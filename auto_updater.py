#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新模块
启动时检查GitHub仓库是否有新版本，如有则拉取更新并重启
包含分支名校验、GitHub Token认证、健康检查和重启次数限制
"""

import os
import re
import sys
import glob
import subprocess
import logging
import json
import urllib.request
import urllib.error
import time

import config

logger = logging.getLogger(__name__)

# 合法分支名字符集：仅允许字母、数字、下划线、连字符、点号、斜杠
SAFE_BRANCH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\./]+$")

# 重启计数文件路径（用于防止无限重启循环）
_RESTART_COUNT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".restart_count"
)


class AutoUpdater:
    """自动更新器：检查GitHub远程仓库更新并应用"""

    def __init__(self, repo: str = None, branch: str = None):
        self.repo = repo or config.GITHUB_REPO
        self.branch = branch or config.UPDATE_BRANCH
        self.project_dir = os.path.dirname(os.path.abspath(__file__))

    def check_and_update(self) -> bool:
        """
        检查并执行更新
        Returns:
            如果执行了更新返回True，否则返回False
        """
        if not self.repo:
            logger.info("未配置GitHub仓库，跳过自动更新检查")
            return False

        logger.info("检查更新: %s/%s", self.repo, self.branch)

        remote_commit = self._get_remote_commit()
        if not remote_commit:
            logger.warning("获取远程版本失败，跳过更新")
            return False

        local_commit = self._get_local_commit()
        if not local_commit:
            logger.warning("获取本地版本失败，跳过更新")
            return False

        if remote_commit == local_commit:
            logger.info("当前已是最新版本: %s", local_commit[:8])
            return False

        logger.info("发现新版本: 本地 %s -> 远程 %s", local_commit[:8], remote_commit[:8])
        return self._apply_update()

    def _get_remote_commit(self) -> str:
        """
        通过GitHub API获取远程最新commit hash
        支持通过 GITHUB_TOKEN 环境变量认证，访问私有仓库并提升速率限制
        Returns:
            commit SHA 字符串，失败返回空字符串
        """
        try:
            api_url = f"https://api.github.com/repos/{self.repo}/commits/{self.branch}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MailCommandBot-Updater/1.0",
            }
            # 如果配置了 GitHub Token，添加认证头
            token = config.GITHUB_TOKEN.strip()
            if token:
                headers["Authorization"] = f"token {token}"
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("sha", "")
        except urllib.error.HTTPError as e:
            logger.warning("GitHub API HTTP 错误 %d: %s", e.code, e.reason)
            return ""
        except urllib.error.URLError as e:
            logger.warning("GitHub API 网络错误: %s", e.reason)
            return ""
        except Exception as e:
            logger.warning("获取远程commit失败: %s", e)
            return ""

    def _get_local_commit(self) -> str:
        """获取本地git仓库当前commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.warning("获取本地commit失败 (返回码 %d): %s", e.returncode, e.stderr.strip())
            return ""
        except FileNotFoundError:
            logger.warning("git 命令不存在")
            return ""
        except Exception as e:
            logger.warning("获取本地commit失败: %s", e)
            return ""

    def _apply_update(self) -> bool:
        """
        执行git pull更新
        包含分支名校验，防止参数注入
        Returns:
            是否更新成功
        """
        # 分支名校验：限制为合法字符集，防止参数注入
        if not self.branch or not SAFE_BRANCH_PATTERN.match(self.branch):
            logger.error("非法分支名，拒绝更新: %s", self.branch)
            return False

        try:
            logger.info("开始执行更新 (分支: %s)...", self.branch)
            # 设置 git 安全环境变量，防止读取系统级配置和终端交互提示
            os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
            os.environ["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(
                ["git", "pull", "origin", self.branch],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.error("git pull 失败 (返回码 %d): %s", result.returncode, result.stderr.strip())
                return False

            logger.info("更新成功: %s", result.stdout.strip())

            # 更新后健康检查：编译所有 Python 文件确认语法无误
            if not self._health_check():
                logger.error("更新后健康检查失败，回滚更新")
                self._rollback()
                return False

            return True

        except FileNotFoundError:
            logger.error("git 命令不存在，无法执行更新")
            return False
        except Exception as e:
            logger.error("执行更新失败: %s", e)
            return False

    def _health_check(self) -> bool:
        """
        更新后健康检查：编译所有 Python 文件确认语法无误
        Returns:
            所有文件语法检查是否通过
        """
        try:
            py_files = glob.glob(os.path.join(self.project_dir, "*.py"))
            if not py_files:
                logger.warning("未找到 Python 文件，跳过健康检查")
                return True

            for py_file in py_files:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", py_file],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    logger.error(
                        "文件 %s 语法检查失败: %s",
                        os.path.basename(py_file),
                        result.stderr.strip(),
                    )
                    return False

            logger.info("健康检查通过 (%d 个文件)", len(py_files))
            return True

        except Exception as e:
            logger.error("健康检查过程异常: %s", e)
            return False

    def _rollback(self) -> None:
        """回滚到更新前的版本"""
        try:
            logger.info("正在回滚更新...")
            subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            logger.info("回滚完成")
        except Exception as e:
            logger.error("回滚失败: %s", e)

    def restart(self) -> bool:
        """
        重启当前进程（含重启次数限制）
        Returns:
            是否允许重启（超过最大重启次数时返回 False）
        """
        # 读取并检查重启次数
        count = self._read_restart_count()
        if count >= config.MAX_RESTART_COUNT:
            logger.error(
                "重启次数已达上限 (%d/%d)，拒绝重启，请人工排查",
                count, config.MAX_RESTART_COUNT,
            )
            return False

        # 增加重启计数
        self._increment_restart_count()

        logger.info("正在重启服务... (第 %d/%d 次)", count + 1, config.MAX_RESTART_COUNT)
        time.sleep(1)

        python = sys.executable
        args = [python] + sys.argv
        os.execv(python, args)
        # execv 不会返回，如果到达这里说明重启失败
        return False

    @staticmethod
    def _read_restart_count() -> int:
        """读取重启计数"""
        try:
            if os.path.exists(_RESTART_COUNT_FILE):
                with open(_RESTART_COUNT_FILE, "r") as f:
                    return int(f.read().strip())
        except (ValueError, IOError):
            pass
        return 0

    @staticmethod
    def _increment_restart_count() -> None:
        """增加重启计数（使用临时文件 + os.rename 实现原子写入）"""
        try:
            count = AutoUpdater._read_restart_count() + 1
            # 写入临时文件，然后原子性重命名，防止写入过程中崩溃导致文件损坏
            tmp_file = _RESTART_COUNT_FILE + ".tmp"
            with open(tmp_file, "w") as f:
                f.write(str(count))
            os.rename(tmp_file, _RESTART_COUNT_FILE)
        except IOError as e:
            logger.warning("无法写入重启计数文件: %s", e)
            # 清理可能残留的临时文件
            try:
                if os.path.exists(_RESTART_COUNT_FILE + ".tmp"):
                    os.remove(_RESTART_COUNT_FILE + ".tmp")
            except OSError:
                pass

    @staticmethod
    def reset_restart_count() -> None:
        """重置重启计数（服务正常运行超过一定时间后调用）"""
        try:
            if os.path.exists(_RESTART_COUNT_FILE):
                os.remove(_RESTART_COUNT_FILE)
                logger.info("重启计数已重置")
        except IOError as e:
            logger.warning("无法删除重启计数文件: %s", e)


def check_update_on_start():
    """启动时检查更新的便捷函数"""
    if not config.CHECK_UPDATE_ON_START:
        return

    updater = AutoUpdater()
    updated = updater.check_and_update()
    if updated:
        logger.info("代码已更新，即将重启以应用新版本")
        if not updater.restart():
            logger.error("自动重启失败，服务将以更新后的代码继续运行")

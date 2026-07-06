#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新模块
启动时检查GitHub仓库是否有新版本，如有则拉取更新并重启
"""

import os
import sys
import subprocess
import logging
import json
import urllib.request
import urllib.error
import time
import shutil

import config

logger = logging.getLogger(__name__)


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
        """通过GitHub API获取远程最新commit hash"""
        try:
            api_url = f"https://api.github.com/repos/{self.repo}/commits/{self.branch}"
            req = urllib.request.Request(
                api_url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "MailCommandBot-Updater/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("sha", "")
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
        except Exception as e:
            logger.warning("获取本地commit失败: %s", e)
            return ""

    def _apply_update(self) -> bool:
        """执行git pull更新"""
        try:
            logger.info("开始执行更新...")
            result = subprocess.run(
                ["git", "pull", "origin", self.branch],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.error("git pull 失败: %s", result.stderr)
                return False

            logger.info("更新成功: %s", result.stdout.strip())
            return True
        except Exception as e:
            logger.error("执行更新失败: %s", e)
            return False

    def restart(self):
        """重启当前进程"""
        logger.info("正在重启服务...")
        time.sleep(1)
        python = sys.executable
        args = [python] + sys.argv
        os.execv(python, args)


def check_update_on_start():
    """启动时检查更新的便捷函数"""
    if not config.CHECK_UPDATE_ON_START:
        return

    updater = AutoUpdater()
    updated = updater.check_and_update()
    if updated:
        logger.info("代码已更新，即将重启以应用新版本")
        updater.restart()

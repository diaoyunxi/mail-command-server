# MailCommandBot - 邮件命令执行服务器

## 功能简介

在本地启动SMTP接收服务器（默认端口9930），可被设置为MX记录指向的目标服务器。收到邮件后自动解析内容，如果正文中有以 `@` 开头的行，则提取其后的Linux命令并执行，将执行结果通过邮件回复给发件人。

## 项目架构

```
mail-command-server/
├── main.py              # 程序入口（日志配置、服务启动）
├── config.py            # 配置文件（安全环境变量转换）
├── smtp_receiver.py     # SMTP接收服务器（aiosmtpd，含发件人白名单）
├── email_parser.py      # 邮件内容解析器（正文清洗、命令提取）
├── command_executor.py  # 命令执行器（含危险命令黑名单、防注入）
├── email_sender.py      # 邮件发送器（smtplib，含连接复用）
├── auto_updater.py      # 自动更新模块（含健康检查、重启限制）
├── tests/               # 单元测试
│   ├── __init__.py
│   ├── test_command_executor.py
│   ├── test_email_parser.py
│   └── test_config.py
├── requirements.txt     # 依赖
└── README.md            # 说明文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 必须配置
export SMTP_OUT_USER="your_email@qq.com"
export SMTP_OUT_PASS="your_auth_code"

# 安全配置（强烈建议）
export ALLOWED_SENDERS="trusted@example.com,admin@example.com"
# 或按域名白名单
export ALLOWED_DOMAINS="example.com,company.org"
```

### 3. 启动服务

```bash
python main.py
```

服务将在 `0.0.0.0:9930` 监听邮件。日志同时输出到标准输出和 `mail_command_bot.log` 文件。

## MX记录配置

在你的域名DNS管理面板中添加MX记录：

| 类型 | 主机记录 | 记录值 | 优先级 |
|------|---------|--------|--------|
| MX   | @       | your-server-ip 或域名 | 10 |

**注意**：标准SMTP使用25端口，但本服务默认在9930端口运行。若需MX解析，建议使用反向代理（如nginx/haproxy）将25端口转发到本机9930端口，或在防火墙开放9930端口并配置发件方直连。

## 使用方式

发送一封邮件到运行此服务的邮箱地址，正文包含：

```
@ls -la
```

服务器将执行 `ls -la`，并将输出通过邮件回复给你。

如需 sudo 命令，在命令的下一行提供密码：

```
@sudo ls /root
your_sudo_password
```

## 安全机制

本服务实现了以下多层安全防护：

1. **发件人白名单**：通过 `ALLOWED_SENDERS`（完整邮箱）或 `ALLOWED_DOMAINS`（域名）限制可触发命令的发件人。未配置时默认不限制（首次部署建议立即配置）。

2. **命令黑名单**：内置 30+ 种危险命令模式匹配，包括但不限于：
   - 破坏性命令：`rm -rf`、`mkfs`、`shutdown`、`dd if=`、`format`
   - 权限操作：`passwd`、`useradd`、`chown -R`、`iptables -F`
   - 远程执行：`curl | sh`、`wget | sh`、`nc -e`
   - 代码执行：`python -c`、`perl -e`、`eval`、`source`、`. /path/to/script`

3. **防命令注入**：使用 `subprocess.Popen(shell=False)` + `shlex.split()` 执行命令，用户输入不经过 shell 解释，彻底杜绝命令注入。sudo 密码通过 stdin 安全传入。

4. **执行超时**：默认 30 秒超时，防止命令挂死；超时后通过进程组 kill 确保无残留子进程。

5. **输出截断**：默认最大 50000 字符，防止过大输出占用资源。

6. **邮件大小限制**：默认 10MB，超大邮件直接拒绝，防止 OOM。

7. **重启保护**：自动更新后最多重启 5 次，防止代码错误导致无限重启循环。

8. **健康检查**：自动更新后编译检查所有 Python 文件，语法错误时自动回滚。

## 环境变量配置表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| SMTP_BIND_HOST | 0.0.0.0 | 接收服务器绑定地址 |
| SMTP_BIND_PORT | 9930 | 接收服务器端口 |
| SMTP_OUT_HOST | smtp.qq.com | 外发SMTP服务器 |
| SMTP_OUT_PORT | 587 | 外发SMTP端口 |
| SMTP_OUT_TIMEOUT | 30 | 外发SMTP超时时间（秒） |
| SMTP_OUT_USER | - | 发件邮箱账号 |
| SMTP_OUT_PASS | - | 发件邮箱授权码 |
| SMTP_OUT_TLS | true | 是否启用TLS |
| SENDER_NAME | MailCommandBot | 发件人显示名称 |
| ALLOWED_SENDERS | - | 允许的发件人邮箱（逗号分隔，留空不限制） |
| ALLOWED_DOMAINS | - | 允许的邮箱域名（逗号分隔，留空不限制） |
| CMD_TIMEOUT | 30 | 命令执行超时（秒） |
| CMD_MAX_OUTPUT | 50000 | 命令输出最大长度（字符） |
| MAX_EMAIL_SIZE | 10485760 | 单封邮件最大字节数（默认10MB） |
| GITHUB_REPO | - | GitHub仓库（用于自动更新） |
| GITHUB_TOKEN | - | GitHub Token（用于API认证） |
| UPDATE_BRANCH | main | 更新分支 |
| CHECK_UPDATE_ON_START | true | 启动时检查更新 |
| MAX_RESTART_COUNT | 5 | 最大自动重启次数 |
| LOG_LEVEL | INFO | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| LOG_FILE | mail_command_bot.log | 日志文件路径 |
| LOG_MAX_BYTES | 10485760 | 日志文件最大大小（字节，默认10MB） |
| LOG_BACKUP_COUNT | 5 | 日志备份文件数量 |

## 自动更新

如果配置了 `GITHUB_REPO`，服务启动时会自动检查GitHub仓库是否有新版本：
1. 对比本地和远程 commit hash
2. 有更新时执行 `git pull`
3. 更新后编译检查所有 Python 文件（健康检查）
4. 健康检查通过后重启服务
5. 语法错误时自动回滚
6. 连续重启超过 `MAX_RESTART_COUNT` 次后停止重启并报警

## 单元测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行指定模块测试
python -m pytest tests/test_command_executor.py -v
python -m pytest tests/test_email_parser.py -v
```

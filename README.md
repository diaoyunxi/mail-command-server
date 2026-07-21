# MailCommandBot - 邮件命令执行服务器

## 功能简介

支持两种运行模式，满足不同网络环境需求：

1. **自建 SMTP 服务器模式**：在本地启动 SMTP 接收服务器（默认端口 9930），可被设置为 MX 记录指向的目标服务器。
2. **已有邮件服务器模式（POP3/IMAP）**：不自建服务器，直接通过 POP3 或 IMAP 协议从已有邮箱（如 QQ邮箱、163邮箱、Gmail 等）拉取邮件。

收到邮件后自动解析内容，如果正文中有以 `@` 开头的行，则提取其后的 Linux 命令并执行，将执行结果通过邮件回复给发件人。

## 项目架构

```
mail-command-server/
├── main.py              # 程序入口（日志配置、模式选择、服务启动）
├── config.py            # 配置文件（安全环境变量转换）
├── smtp_receiver.py     # SMTP接收服务器（aiosmtpd，含发件人白名单）
├── mail_receiver.py     # POP3/IMAP邮件接收器（轮询拉取、处理、删除/标记已读）
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

**公共配置（所有模式必须）**

```bash
# 外发SMTP配置（用于发送回复邮件）
export SMTP_OUT_USER="your_email@qq.com"
export SMTP_OUT_PASS="your_auth_code"

# 安全配置（强烈建议）
export ALLOWED_SENDERS="trusted@example.com,admin@example.com"
# 或按域名白名单
export ALLOWED_DOMAINS="example.com,company.org"
```

**模式一：自建 SMTP 服务器（默认）**

无需额外配置，直接启动即可在 `0.0.0.0:9930` 监听邮件。

**模式二：使用已有邮件服务器（POP3/IMAP）**

```bash
# 切换到 POP3 或 IMAP 模式
export RECEIVE_MODE="imap"          # 或 pop3

# 配置收件服务器
export MAIL_IN_HOST="imap.qq.com"   # POP3示例: pop.qq.com
export MAIL_IN_USER="your_email@qq.com"
export MAIL_IN_PASS="your_auth_code"
# MAIL_IN_PORT 会根据协议和 TLS 自动选择默认值（IMAP:993, POP3:995）
```

### 3. 启动服务

```bash
python main.py
```

- **SMTP 模式**：服务将在 `0.0.0.0:9930` 监听邮件。
- **POP3/IMAP 模式**：服务将按 `MAIL_POLL_INTERVAL`（默认 10 秒）轮询检查新邮件。

日志同时输出到标准输出和 `mail_command_bot.log` 文件。

## MX记录配置（仅SMTP模式）

在你的域名DNS管理面板中添加MX记录：

| 类型 | 主机记录 | 记录值 | 优先级 |
|------|---------|--------|--------|
| MX   | @       | your-server-ip 或域名 | 10 |

**注意**：标准SMTP使用25端口，但本服务默认在9930端口运行。若需MX解析，建议使用反向代理（如nginx/haproxy）将25端口转发到本机9930端口，或在防火墙开放9930端口并配置发件方直连。

## 已有邮件服务器模式（POP3/IMAP）

如果你不想自建 SMTP 服务器，或运行环境无法开放端口，可使用 POP3/IMAP 模式：

1. 准备一个有 POP3/IMAP 访问权限的邮箱（如 QQ邮箱、163邮箱、Gmail、Outlook 等）。
2. 开启邮箱的 POP3/IMAP 服务，获取授权码/应用密码。
3. 设置 `RECEIVE_MODE=pop3` 或 `RECEIVE_MODE=imap`。
4. 配置 `MAIL_IN_HOST`、`MAIL_IN_USER`、`MAIL_IN_PASS`。

**工作原理**：
- **POP3 模式**：每次轮询连接服务器，获取所有邮件 UID，下载处理后用 `DELE` 删除，避免重复执行。
- **IMAP 模式**：每次轮询搜索 `UNSEEN`（未读）邮件，处理后用 `+FLAGS \\Seen` 标记为已读，原邮件保留在服务器。

**优势**：
- 无需公网IP或开放端口
- 无需配置 MX 记录
- 可在 NAT/防火墙后运行
- 适合家庭宽带、云服务器内网等场景

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

1. **发件人白名单**：通过 `ALLOWED_SENDERS`（完整邮箱）或 `ALLOWED_DOMAINS`（域名）限制可触发命令的发件人。未配置白名单时，若 `REQUIRE_WHITELIST=true`（默认），服务将强制绑定 `127.0.0.1` 以防止未授权访问。

2. **客户端IP白名单**：通过 `ALLOWED_CLIENT_IPS` 限制可连接SMTP服务器的客户端IP，防止外部主机伪造 `MAIL FROM` 发送命令邮件。**强烈建议**在对外提供服务时配置此项，并结合 SPF/DKIM/DMARC 邮件认证机制使用。

3. **命令白名单**：采用白名单模式，仅允许以下安全命令执行：`ls, cat, df, ps, uptime, free, head, tail, grep, wc, date, whoami, id, uname, ifconfig, ip, netstat, ss, top, du, find`。其他命令一律拒绝。`find` 命令禁止使用 `-delete`、`-exec` 等危险参数。禁止管道符（`|`）、重定向（`>`/`<`）、命令替换（`` ` ``/`$()`）等 shell 元字符。

4. **命令模板**：支持通过 `@template:名称` 引用预定义安全命令，如 `@template:disk` 执行 `df -h`。

5. **防命令注入**：使用 `subprocess.Popen(shell=False)` + `shlex.split()` 执行命令，用户输入不经过 shell 解释，彻底杜绝命令注入。sudo 密码通过 stdin 安全传入。

6. **sudo 密码安全**：通过邮件传输 sudo 密码存在安全风险。建议启用 `SUDO_NOPASSWD=true` 并在 `/etc/sudoers` 中配置 NOPASSWD 规则（如 `mailbot ALL=(ALL) NOPASSWD: /bin/ls, /bin/cat`），启用后服务将忽略邮件中的密码。

7. **频率限制**：每个发件人每分钟最多发送 `RATE_LIMIT_PER_MINUTE`（默认10）封命令邮件，超出限制将返回 450 错误。

8. **执行超时**：默认 30 秒超时，防止命令挂死；超时后通过进程组 kill 确保无残留子进程。

9. **输出截断**：默认最大 50000 字符，防止过大输出占用资源。

10. **敏感信息脱敏**：日志和回复邮件中对命令中的 `-p`/`--password` 参数值进行脱敏（替换为 `***`），异常详情仅记录日志不回复给发件人。

11. **邮件大小限制**：默认 1MB，超大邮件直接拒绝，防止 OOM。

12. **重启保护**：自动更新后最多重启 5 次，防止代码错误导致无限重启循环。重启计数使用原子写入。

13. **健康检查**：自动更新后编译检查所有 Python 文件，语法错误时自动回滚。

14. **SMTP 线程安全**：邮件发送器使用 `threading.Lock` 保护连接管理，支持并发安全。

## 环境变量配置表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| RECEIVE_MODE | smtp | 接收模式: smtp(自建服务器) / pop3 / imap |
| SMTP_BIND_HOST | 0.0.0.0 | 接收服务器绑定地址（smtp模式） |
| SMTP_BIND_PORT | 9930 | 接收服务器端口（smtp模式） |
| MAIL_IN_HOST | - | 收件服务器地址（pop3/imap模式，如 pop.qq.com） |
| MAIL_IN_PORT | 自动 | 收件服务器端口（pop3默认995/110，imap默认993/143） |
| MAIL_IN_USER | - | 收件邮箱账号（pop3/imap模式） |
| MAIL_IN_PASS | - | 收件邮箱密码/授权码（pop3/imap模式） |
| MAIL_IN_PROTOCOL | pop3 | 收件协议: pop3 / imap |
| MAIL_IN_TLS | true | 收件是否启用TLS |
| MAIL_POLL_INTERVAL | 10 | 轮询检查间隔（秒，pop3/imap模式） |
| MAIL_INBOX_FOLDER | INBOX | IMAP收件箱文件夹名 |
| SMTP_OUT_HOST | smtp.qq.com | 外发SMTP服务器 |
| SMTP_OUT_PORT | 587 | 外发SMTP端口 |
| SMTP_OUT_TIMEOUT | 30 | 外发SMTP超时时间（秒） |
| SMTP_OUT_USER | - | 发件邮箱账号 |
| SMTP_OUT_PASS | - | 发件邮箱授权码 |
| SMTP_OUT_TLS | true | 是否启用TLS |
| SENDER_NAME | MailCommandBot | 发件人显示名称 |
| ALLOWED_SENDERS | - | 允许的发件人邮箱（逗号分隔，留空时强制绑定127.0.0.1） |
| ALLOWED_DOMAINS | - | 允许的邮箱域名（逗号分隔，留空时强制绑定127.0.0.1） |
| ALLOWED_CLIENT_IPS | - | 允许连接的客户端IP（逗号分隔，留空不限制，仅smtp模式） |
| REQUIRE_WHITELIST | true | 未配置白名单时是否强制绑定127.0.0.1 |
| SUDO_NOPASSWD | false | 是否使用sudoers NOPASSWD模式（建议启用，避免邮件传输密码） |
| RATE_LIMIT_PER_MINUTE | 10 | 每个发件人每分钟最多命令邮件数 |
| CMD_TIMEOUT | 30 | 命令执行超时（秒） |
| CMD_MAX_OUTPUT | 50000 | 命令输出最大长度（字符） |
| MAX_EMAIL_SIZE | 1048576 | 单封邮件最大字节数（默认1MB） |
| SMTP_KEEPALIVE_INTERVAL | 60 | SMTP连接心跳保活间隔（秒，0禁用） |
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

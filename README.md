# MailCommandBot - 邮件命令执行服务器

## 功能简介

在本地启动SMTP接收服务器（默认端口9930），可被设置为MX记录指向的目标服务器。收到邮件后自动解析内容，如果正文中有以 `@` 开头的行，则提取其后的Linux命令并执行，将执行结果通过邮件回复给发件人。

## 项目架构

```
mail_command_server/
├── main.py              # 程序入口
├── config.py            # 配置文件（支持环境变量）
├── smtp_receiver.py     # SMTP接收服务器（aiosmtpd）
├── email_parser.py      # 邮件内容解析器
├── command_executor.py  # 命令执行器（含安全校验）
├── email_sender.py      # 邮件发送器（smtplib）
├── auto_updater.py      # 自动更新模块（GitHub）
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
export SMTP_OUT_USER="your_email@qq.com"
export SMTP_OUT_PASS="your_auth_code"
export ALLOWED_SENDERS="trusted@example.com,admin@example.com"
```

### 3. 启动服务

```bash
python main.py
```

服务将在 `0.0.0.0:9930` 监听邮件。

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

## 安全机制

- 发件人白名单：可通过 `ALLOWED_SENDERS` 或 `ALLOWED_DOMAINS` 限制可触发命令的邮箱
- 命令黑名单：内置危险命令关键词过滤（如 `rm -rf /`, `shutdown` 等）
- 执行超时：默认30秒超时，防止命令挂死
- 输出截断：默认最大50000字符，防止过大输出

## 环境变量配置表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| SMTP_BIND_HOST | 0.0.0.0 | 接收服务器绑定地址 |
| SMTP_BIND_PORT | 9930 | 接收服务器端口 |
| SMTP_OUT_HOST | smtp.qq.com | 外发SMTP服务器 |
| SMTP_OUT_PORT | 587 | 外发SMTP端口 |
| SMTP_OUT_USER | - | 发件邮箱账号 |
| SMTP_OUT_PASS | - | 发件邮箱授权码 |
| SMTP_OUT_TLS | true | 是否启用TLS |
| ALLOWED_SENDERS | - | 允许的发件人邮箱（逗号分隔） |
| ALLOWED_DOMAINS | - | 允许的邮箱域名（逗号分隔） |
| CMD_TIMEOUT | 30 | 命令执行超时（秒） |
| CMD_MAX_OUTPUT | 50000 | 命令输出最大长度 |
| GITHUB_REPO | - | GitHub仓库（用于自动更新） |
| UPDATE_BRANCH | main | 更新分支 |
| CHECK_UPDATE_ON_START | true | 启动时检查更新 |
| LOG_LEVEL | INFO | 日志级别 |

## 自动更新

如果配置了 `GITHUB_REPO`，服务启动时会自动检查GitHub仓库是否有新版本，如有更新则自动拉取并重启。

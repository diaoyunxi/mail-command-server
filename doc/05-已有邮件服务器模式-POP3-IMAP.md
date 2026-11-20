> [← 返回文档目录](../README.md) ｜ 本分册由 `README.md` 的「已有邮件服务器模式（POP3/IMAP）」章节拆分而来。

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

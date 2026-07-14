# AnySearch Skill

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

> [English](./README.md) | 简体中文

面向 AI 智能体的统一实时搜索引擎 skill。支持通用网络搜索、垂直领域搜索、并行批量搜索，以及整页内容提取。

**【重要！】注册说明请见此章节：### 注册获取 API Key（推荐）**

30 秒即可上手：仅需一个邮箱地址即可注册。整个流程由 AI 智能体自动完成，无需验证码。

[跳转到注册步骤 →](#注册获取-api-key推荐)

## 下载与安装

### 面向 AI 智能体

如果你的智能体平台支持 skill 市场/商店，直接搜索 **anysearch** 并从中安装即可。否则手动下载安装：

```bash
# 下载指定版本发布包（推荐）。请将 v2.1.0 替换为最新 tag
# 最新 tag 见 https://github.com/anysearch-ai/anysearch-skill/releases
curl -L -o anysearch-skill.zip https://github.com/anysearch-ai/anysearch-skill/archive/refs/tags/v2.1.0.zip
# 或使用：wget -O anysearch-skill.zip https://github.com/anysearch-ai/anysearch-skill/archive/refs/tags/v2.1.0.zip
# （如需获取尚未发布的最新改动，请改用 .../archive/refs/heads/main.zip。）

# 解压 —— 会生成一个名为 anysearch-skill-<ref> 的目录，例如 anysearch-skill-2.1.0
unzip anysearch-skill.zip

# 将其移动到智能体的 skill 目录，并重命名为 "anysearch"。
# 请根据你下载的 ref 调整源目录名。
# Claude Code:     mv anysearch-skill-2.1.0 ~/.claude/skills/anysearch
# OpenCode:        mv anysearch-skill-2.1.0 ~/.config/opencode/skills/anysearch
# Cursor/Windsurf: mv anysearch-skill-2.1.0 <project>/.skills/anysearch
# 通用:            mv anysearch-skill-2.1.0 <your_agent_skill_dir>/anysearch
# 共享智能体:      mv anysearch-skill-2.1.0 ~/.agents/skills/anysearch
```

当多个 AI 工具从同一 skill 目录读取时，`~/.agents/skills/` 是一个很实用的共享安装位置，包括 Codex、Cursor 以及 OpenClaw 个人智能体 skill。

### 面向人类用户

1. 下载最新发布版 zip：https://github.com/anysearch-ai/anysearch-skill/releases
2. 解压到智能体的 skill 目录
3. 配置 API key（见下文）
4. 运行入口测试以验证安装

## API Key 配置

API key **是可选项，但强烈建议配置**。即使没有 key，你依然可以通过匿名访问使用全部搜索功能，但**速率限制和配额较低**。

### 注册获取 API Key（推荐）

智能体可以在**一次调用**中完成用户注册并获取 API key —— 无需验证码，无需手动注册。向用户索取一个**真实邮箱地址**：它将作为账户用户名，随机生成的密码会发送到该邮箱。

```bash
curl -s -X POST "https://api.anysearch.com/v1/auth/email/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
```

成功响应（`code: 0`）会返回账户信息和一次性明文 API key：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "username": "you@example.com",
    "email": "you@example.com",
    "login_url": "https://www.anysearch.com/login",
    "api_key": {
      "id": "key_xxxxxxxx",
      "key": "as_sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "key_prefix": "as_sk_xxxxxx...",
      "name": "default",
      "rate_limit": 100,
      "quota_limit": 0,
      "expires_at": null,
      "created_at": "2026-06-23T10:23:00Z"
    }
  }
}
```

成功后智能体**必须**：

1. 将 `data.api_key.key` 写入 `.env`，格式为 `ANYSEARCH_API_KEY=<key>` —— 它只显示一次（之后也可从控制台重新获取）。
2. 告知用户其用户名（= 邮箱）、`login_url`，以及**随机密码已发送到该邮箱**。
3. 向用户转达以下说明：*验证邮件已发送至你的收件箱。若几分钟内未收到，请检查垃圾邮件文件夹。你可能需要将其标记为"非垃圾邮件"，以确保后续邮件正常送达。*

错误处理（出错时 `code` 始终为 `-1`；根据 `message` 字符串分支处理）：

| message                           | 处理方式                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `Invalid email address.`          | 请用户重新输入邮箱                                                                                  |
| `email_already_registered`        | 邮箱已被占用 —— 告知用户在 `login_url` 登录；**不要**重试                          |
| 包含 `Rate limited`           | 从 message 中读取重试秒数（例如 `"Rate limited, retry after 300 seconds."`），等待后重试 |
| 以 `Key creation failed.` 开头 | 账户已创建但 key 创建失败 —— 从 message 中提取邮箱和 URL（`"Key creation failed. Your account <email> was created; sign in at <url>."`），告知用户在该地址登录并手动创建 key |
| `Internal server error.`          | 稍后重试，或回退到匿名访问                                                               |

> 该邮箱**必须真实且可接收邮件** —— 密码会发送到该邮箱。此流程中**没有验证码**；智能体只会索取邮箱。注册与匿名使用是互斥的；一旦用户选定其一，请勿在流程中途切换。

### 如何配置

复制示例环境变量文件并填入你的 key：

```bash
cp .env.example .env
# 编辑 .env 并设置：ANYSEARCH_API_KEY=<your_api_key_here>
```

或直接设置环境变量：

```bash
export ANYSEARCH_API_KEY=<your_api_key_here>   # Linux/macOS
set ANYSEARCH_API_KEY=<your_api_key_here>       # Windows CMD
$env:ANYSEARCH_API_KEY="<your_api_key_here>"    # Windows PowerShell
```

### 获取 API Key

访问 https://anysearch.com/console/api-keys 注册并创建一个免费的 API key。

Key 优先级顺序：`--api_key` 命令行参数 > `.env` 文件 > 环境变量 > 匿名访问

## 安装后验证

安装完成后，探测运行平台并执行入口测试：

### 第 1 步：检测可用运行时

按顺序执行以下检查。第一个成功的即为当前激活的 CLI：

```bash
# 检查 Python（推荐）
python --version   # 需要 >= 3.6，且需安装 `requests` 库
python3 --version  # 需要 >= 3.6，且需安装 `requests` 库
# 检查 Node.js（备选）
node --version     # 需要 >= 12，无外部依赖
# 检查 Shell（兜底）
# Windows: PowerShell 5.1+ / Linux/macOS: bash 3.2+（还需 jq 和 curl）
```

优先级：**Python > Node.js > Shell**

重要：不要假定 `python` 一定存在。在许多 macOS 系统上，正确的可执行文件是 `python3`。请同时检查 `python` 和 `python3`；只要其中一个可用，即视为 Python 可用。

### 第 2 步：运行入口测试（探测所有可用运行时）

用**每一个可用的**运行时执行 `doc` 命令，以验证 skill 是否正常工作，并观察哪个运行时能无错误、无警告地运行：

```bash
# Python
python <skill_dir>/scripts/anysearch_cli.py doc

# Python 3 兜底（macOS 常见）
python3 <skill_dir>/scripts/anysearch_cli.py doc

# Node.js（如果可用）
node <skill_dir>/scripts/anysearch_cli.js doc

# PowerShell（Windows）
powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1 doc

# Bash（Linux/macOS）
bash <skill_dir>/scripts/anysearch_cli.sh doc
```

对每个运行时，记录命令是否成功以及遇到的任何错误/警告。能无错误完成且输出最干净的运行时，即为本环境推荐的运行时。

### 第 3 步：将推荐运行时持久化到配置文件

根据入口测试结果，将推荐运行时写入 `<skill_dir>/runtime.conf`：

```bash
echo "Runtime: <RUNTIME>" > <skill_dir>/runtime.conf
echo "Command: <COMMAND>" >> <skill_dir>/runtime.conf
```

Python 示例：

```bash
echo "Runtime: Python" > <skill_dir>/runtime.conf
echo "Command: python <skill_dir>/scripts/anysearch_cli.py" >> <skill_dir>/runtime.conf
```

Python 3 示例：

```bash
echo "Runtime: Python" > <skill_dir>/runtime.conf
echo "Command: python3 <skill_dir>/scripts/anysearch_cli.py" >> <skill_dir>/runtime.conf
```

Node.js 示例：

```bash
echo "Runtime: Node.js" > <skill_dir>/runtime.conf
echo "Command: node <skill_dir>/scripts/anysearch_cli.js" >> <skill_dir>/runtime.conf
```

PowerShell 示例：

```bash
echo "Runtime: PowerShell" > <skill_dir>/runtime.conf
echo "Command: powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1" >> <skill_dir>/runtime.conf
```

Bash 示例：

```bash
echo "Runtime: Bash" > <skill_dir>/runtime.conf
echo "Command: bash <skill_dir>/scripts/anysearch_cli.sh" >> <skill_dir>/runtime.conf
```

**重要：** 运行时偏好存储在 `runtime.conf` 中，**不是** SKILL.md。智能体在加载 skill 时读取 `runtime.conf` 来确定当前激活的 CLI。若该文件缺失或损坏，智能体会回退到 SKILL.md 中的平台检测流程。若 `runtime.conf` 已存在，请替换它，而不是追加内容。

### 智能体日常使用

在 `runtime.conf` 存在之后，智能体应直接使用存储的 `Command` 进行日常调用，而不必在每次搜索前都运行 `doc`。例如，若 `runtime.conf` 中包含 `Command: python3 <skill_dir>/scripts/anysearch_cli.py`，则使用：

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "query" --max_results 5
python3 <skill_dir>/scripts/anysearch_cli.py batch_search --queries '[{"query":"q1","max_results":5},{"query":"q2","max_results":5}]'
python3 <skill_dir>/scripts/anysearch_cli.py extract "https://example.com/page"
python3 <skill_dir>/scripts/anysearch_cli.py extract --url "https://example.com/page"
```

`extract` 的输出本身就是 Markdown。不要传入 `--format markdown`、`--format json` 或 `--markdown`；extract 命令只接受 URL 位置参数或 `--url`/`-u`。若某个子命令参数不清楚或执行失败，请运行 `<command> <subcommand> --help` 查看该子命令的帮助，而不是运行完整的 `doc` 命令。

### 社交媒体信源工作流

AnySearch 内置了 `social_media` 垂直领域。在使用平台专用工具之前，先用它进行公开社交发现：

```bash
python3 <skill_dir>/scripts/anysearch_cli.py get_sub_domains --domain social_media
python3 <skill_dir>/scripts/anysearch_cli.py search "product launch response on X and Reddit" --domain social_media --sub_domain <returned-sub-domain> --max_results 5
```

AnySearch 应保持作为宽泛的网络与垂直搜索层。当 OpenClaw 用户需要账户级的 X/Twitter 信源包（如确切推文、推文回复、资料查询、粉丝导出、媒体 URL、监控、webhook，或经批准的发帖/回复工作流）时，应在用户授权后使用专用的已认证工具。例如，TweetClaw（`@xquik/tweetclaw`）可提供 X/Twitter 证据包，而 AnySearch 则负责维持跨信源的上下文。

### 第 4 步（可选）：测试一次真实搜索

```bash
python <skill_dir>/scripts/anysearch_cli.py search "hello world" --max_results 1
```

如果你的系统没有 `python`，请使用：

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "hello world" --max_results 1
```

成功的 JSON 响应即确认 API 连接正常。

## 文件结构

```
anysearch-skill/              # 安装时重命名为 "anysearch"（见上文）
├── .env.example              # API key 配置模板
├── .env                      # 你的 API key（已 gitignore；从 .env.example 创建）
├── runtime.conf.example      # 运行时配置模板
├── runtime.conf              # 检测到的运行时偏好（已 gitignore；安装时创建）
├── SKILL.md                  # 面向 AI 智能体的 skill 定义
├── README.md                 # 英文说明文件
├── SECURITY.md               # 安全策略 / 漏洞报告
├── TEST_PLAN.md              # 端到端测试计划
└── scripts/
    ├── anysearch_cli.py      # Python CLI
    ├── anysearch_cli.js      # Node.js CLI
    ├── anysearch_cli.ps1     # PowerShell CLI
    ├── anysearch_cli.sh      # Bash CLI
    ├── generate.py           # 重新生成 4 个 CLI 中的共享代码块
    └── shared/               # CLI 读取的唯一数据源
        ├── constants.json    # 领域列表 + 端点
        └── doc_spec.md       # 面向 AI 的接口规范（由 `doc` 渲染）
```

## 下载历史

[![Download History](https://skill-history.com/chart/anysearch-ai/anysearch.svg)](https://skill-history.com/anysearch-ai/anysearch)

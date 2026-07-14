# AnySearch Skill

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

> English | [简体中文](./README_zh.md)

Unified real-time search engine skill for AI agents. Supports general web search, vertical domain search, parallel batch search, and full-page content extraction.

**[IMPORTANT!] Registration instructions can be found in this section: ### Register for an API Key (Recommended)**

Get started in 30 seconds: Register with just an email address. The AI agent will complete the whole process automatically, no verification code required.

[Jump to registration steps →](#register-for-an-api-key-recommended)

## Download & Install

### For AI Agents

If your agent platform supports a skill marketplace/store, search for **anysearch** and install from there. Otherwise, download and install manually:

```bash
# Download a pinned release (recommended). Replace v2.1.0 with the latest tag
# from https://github.com/anysearch-ai/anysearch-skill/releases
curl -L -o anysearch-skill.zip https://github.com/anysearch-ai/anysearch-skill/archive/refs/tags/v2.1.0.zip
# or: wget -O anysearch-skill.zip https://github.com/anysearch-ai/anysearch-skill/archive/refs/tags/v2.1.0.zip
# (For the latest unreleased changes, use .../archive/refs/heads/main.zip instead.)

# Unzip — creates a directory named anysearch-skill-<ref>, e.g. anysearch-skill-2.1.0
unzip anysearch-skill.zip

# Move it to your agent's skill directory, renaming it to "anysearch".
# Adjust the source directory name to match the ref you downloaded.
# Claude Code:     mv anysearch-skill-2.1.0 ~/.claude/skills/anysearch
# OpenCode:        mv anysearch-skill-2.1.0 ~/.config/opencode/skills/anysearch
# Cursor/Windsurf: mv anysearch-skill-2.1.0 <project>/.skills/anysearch
# Generic:         mv anysearch-skill-2.1.0 <your_agent_skill_dir>/anysearch
# Shared agents:   mv anysearch-skill-2.1.0 ~/.agents/skills/anysearch
```

`~/.agents/skills/` is a useful shared install location when multiple AI tools read from the same skill directory, including Codex, Cursor, and OpenClaw personal agent skills.

### For Humans

1. Download the latest release zip: https://github.com/anysearch-ai/anysearch-skill/releases
2. Unzip to your agent's skill directory
3. Configure API key (see below)
4. Run the entry test to verify installation

## API Key Configuration

An API key is **optional but strongly recommended**. Without a key, you can still use all search features via anonymous access, but with **lower rate limits and quota**.

### Register for an API Key (Recommended)

The agent can register the user and obtain an API key in a **single call** — no verification code, no manual signup. Ask the user for a **real email address**: it becomes the account username, and a randomly generated password is emailed to it.

```bash
curl -s -X POST "https://api.anysearch.com/v1/auth/email/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
```

Success response (`code: 0`) returns the account info and a one-time plaintext API key:

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

On success the agent MUST:

1. Write `data.api_key.key` to `.env` as `ANYSEARCH_API_KEY=<key>` — it is shown only once (it can also be retrieved later from the dashboard).
2. Tell the user their username (= email), the `login_url`, and that a **random password has been emailed to that address**.
3. Relay this note to the user: *A verification email has been sent to your inbox. If you don't see it within a few minutes, please check your spam or junk folder. You may need to mark it as "Not Spam" to ensure future emails arrive correctly.*

Error handling (always `code: -1` on error; branch on the `message` string):

| message                           | what to do                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `Invalid email address.`          | ask the user to re-enter the email                                                                  |
| `email_already_registered`        | email is taken — tell the user to sign in at `login_url`; do **not** retry                          |
| contains `Rate limited`           | read retry seconds from message (e.g. `"Rate limited, retry after 300 seconds."`), wait, then retry |
| starts with `Key creation failed.` | account created but key failed — extract the email and URL from the message (`"Key creation failed. Your account <email> was created; sign in at <url>."`) and tell the user to sign in there to create a key manually |
| `Internal server error.`          | retry later or fall back to anonymous                                                               |

> The email **must be real and reachable** — the password is delivered there. There is **no verification code** in this flow; the agent only ever asks for an email. Registration and anonymous use are mutually exclusive; once the user picks one, don't switch mid-flow.

### How to configure

Copy the example env file and fill in your key:

```bash
cp .env.example .env
# Edit .env and set: ANYSEARCH_API_KEY=<your_api_key_here>
```

Or set the environment variable directly:

```bash
export ANYSEARCH_API_KEY=<your_api_key_here>   # Linux/macOS
set ANYSEARCH_API_KEY=<your_api_key_here>       # Windows CMD
$env:ANYSEARCH_API_KEY="<your_api_key_here>"    # Windows PowerShell
```

### Get an API Key

Visit https://anysearch.com/console/api-keys to sign up and create a free API key.

Key priority order: `--api_key` CLI flag > `.env` file > environment variable > anonymous

## Post-Install Verification

After installation, probe the platform and run the entry test:

### Step 1: Detect available runtime

Run these checks in order. The first success determines the active CLI:

```bash
# Check Python (recommended)
python --version   # Need >= 3.6, requires `requests` library
python3 --version  # Need >= 3.6, requires `requests` library
# Check Node.js (alternative)
node --version     # Need >= 12, no external dependencies
# Check Shell (fallback)
# Windows: PowerShell 5.1+ / Linux/macOS: bash 3.2+ (also requires jq and curl)
```

Priority: **Python > Node.js > Shell**

Important: do not assume `python` exists. On many macOS systems, the correct executable is `python3`. Check both `python` and `python3`; if either works, Python is available.

### Step 2: Run entry test (probe all available runtimes)

Run the `doc` command with **each available** runtime to verify the skill works, and observe which runs without errors or warnings:

```bash
# Python
python <skill_dir>/scripts/anysearch_cli.py doc

# Python 3 fallback (common on macOS)
python3 <skill_dir>/scripts/anysearch_cli.py doc

# Node.js (if available)
node <skill_dir>/scripts/anysearch_cli.js doc

# PowerShell (Windows)
powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1 doc

# Bash (Linux/macOS)
bash <skill_dir>/scripts/anysearch_cli.sh doc
```

For each runtime, record whether the command succeeded and any errors/warnings encountered. The runtime that completes without errors and produces the cleanest output is the recommended runtime for this environment.

### Step 3: Persist recommended runtime to configuration file

Based on the entry test results, write the recommended runtime to `<skill_dir>/runtime.conf`:

```bash
echo "Runtime: <RUNTIME>" > <skill_dir>/runtime.conf
echo "Command: <COMMAND>" >> <skill_dir>/runtime.conf
```

Example for Python:

```bash
echo "Runtime: Python" > <skill_dir>/runtime.conf
echo "Command: python <skill_dir>/scripts/anysearch_cli.py" >> <skill_dir>/runtime.conf
```

Example for Python 3:

```bash
echo "Runtime: Python" > <skill_dir>/runtime.conf
echo "Command: python3 <skill_dir>/scripts/anysearch_cli.py" >> <skill_dir>/runtime.conf
```

Example for Node.js:

```bash
echo "Runtime: Node.js" > <skill_dir>/runtime.conf
echo "Command: node <skill_dir>/scripts/anysearch_cli.js" >> <skill_dir>/runtime.conf
```

Example for PowerShell:

```bash
echo "Runtime: PowerShell" > <skill_dir>/runtime.conf
echo "Command: powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1" >> <skill_dir>/runtime.conf
```

Example for Bash:

```bash
echo "Runtime: Bash" > <skill_dir>/runtime.conf
echo "Command: bash <skill_dir>/scripts/anysearch_cli.sh" >> <skill_dir>/runtime.conf
```

**Important:** Runtime preferences are stored in `runtime.conf`, NOT in SKILL.md. The agent reads `runtime.conf` on skill load to determine the active CLI. If the file is missing or corrupted, the agent falls back to the Platform Detection procedure in SKILL.md. If `runtime.conf` already exists, replace it instead of appending.

### Routine agent usage

After `runtime.conf` exists, agents should use the stored `Command` directly for routine calls instead of running `doc` before every search. For example, if `runtime.conf` contains `Command: python3 <skill_dir>/scripts/anysearch_cli.py`, use:

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "query" --max_results 5
python3 <skill_dir>/scripts/anysearch_cli.py batch_search --queries '[{"query":"q1","max_results":5},{"query":"q2","max_results":5}]'
python3 <skill_dir>/scripts/anysearch_cli.py extract "https://example.com/page"
python3 <skill_dir>/scripts/anysearch_cli.py extract --url "https://example.com/page"
```

`extract` output is already Markdown. Do not pass `--format markdown`, `--format json`, or `--markdown`; the extract command only accepts the URL positional argument or `--url`/`-u`. If a subcommand argument is unclear or fails, run `<command> <subcommand> --help` for that subcommand rather than the full `doc` command.

### Social media source workflows

AnySearch includes a `social_media` vertical domain. Use it for public social discovery before reaching for platform-specific tools:

```bash
python3 <skill_dir>/scripts/anysearch_cli.py get_sub_domains --domain social_media
python3 <skill_dir>/scripts/anysearch_cli.py search "product launch response on X and Reddit" --domain social_media --sub_domain <returned-sub-domain> --max_results 5
```

AnySearch should stay the broad web and vertical search layer. When an OpenClaw user needs account-scoped X/Twitter source packets such as exact tweets, tweet replies, profile lookup, follower export, media URLs, monitors, webhooks, or approved post/reply workflows, use a dedicated authenticated tool after user approval. For example, TweetClaw (`@xquik/tweetclaw`) can provide the X/Twitter evidence packet while AnySearch keeps the cross-source context.

### Step 4 (optional): Test a real search

```bash
python <skill_dir>/scripts/anysearch_cli.py search "hello world" --max_results 1
```

If your system does not provide `python`, use:

```bash
python3 <skill_dir>/scripts/anysearch_cli.py search "hello world" --max_results 1
```

A successful JSON response confirms the API connection is working.

## File Structure

```
anysearch-skill/              # renamed to "anysearch" on install (see above)
├── .env.example              # API key configuration template
├── .env                      # Your API key (gitignored; create from .env.example)
├── runtime.conf.example      # Runtime configuration template
├── runtime.conf              # Detected runtime preferences (gitignored; created at install)
├── SKILL.md                  # Skill definition for AI agents
├── README.md                 # This file
├── SECURITY.md               # Security policy / vulnerability reporting
├── TEST_PLAN.md              # End-to-end test plan
└── scripts/
    ├── anysearch_cli.py      # Python CLI
    ├── anysearch_cli.js      # Node.js CLI
    ├── anysearch_cli.ps1     # PowerShell CLI
    ├── anysearch_cli.sh      # Bash CLI
    ├── generate.py           # Regenerates the shared blocks in the 4 CLIs
    └── shared/               # Single source of truth read by the CLIs
        ├── constants.json    # Domain list + endpoint
        └── doc_spec.md       # AI-facing interface spec (rendered by `doc`)
```

## Download History

[![Download History](https://skill-history.com/chart/anysearch-ai/anysearch.svg)](https://skill-history.com/anysearch-ai/anysearch)

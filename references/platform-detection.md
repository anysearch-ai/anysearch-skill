# Platform Detection & CLI Routing

## Pre-detected Runtime (fast path)

If `<skill_dir>/runtime.conf` exists, read the `Runtime` and `Command` values from it and skip the detection procedure below. Treat this as the normal fast path for routine searches. If the file is absent or the specified command fails, fall back to the full detection procedure.

`runtime.conf` format (auto-generated during installation; stored per machine, gitignored):

```
Runtime: Python
Command: python3 /path/to/skill/scripts/anysearch_cli.py
```

The agent MUST use the stored `Command` directly for routine calls instead of running `doc` before every search.

## Priority Order

```
Python  >  Node.js  >  Shell (powershell on Windows, bash on Linux/macOS)
```

## Detection Procedure

Run the following checks in order. The first success determines the active CLI.

### Step 1 — Check Python

```
python --version 2>&1
python3 --version 2>&1
```

- If either `python` or `python3` exists with version >= 3.6 → use `anysearch_cli.py`
- On many macOS systems, `python` is absent while `python3` is available. Treat both names as valid probes.
- Dependency: the `requests` library (not part of the standard library). It is commonly already available; if importing it fails, install with `pip install requests` (or `pip install -r requirements.txt`), or fall through to the Node.js CLI, which has no dependencies.

### Step 2 — Check Node.js (if Python failed)

```
node --version 2>&1
```

- If exit code 0 → use `anysearch_cli.js`
- No external dependencies required (uses built-in `https` module)

### Step 3 — Check Shell (if both Python and Node.js failed)

| Platform | Shell | CLI |
|----------|-------|-----|
| Windows | PowerShell 5.1+ | `anysearch_cli.ps1` |
| Linux / macOS | bash 3.2+ (with `jq` and `curl`) | `anysearch_cli.sh` |

- Windows: `powershell -Command "$PSVersionTable.PSVersion"` to verify
- Linux/macOS: `bash --version`, and `jq --version` / `curl --version` (the Bash CLI requires both)

> Note: `anysearch_cli.sh` is a Bash script (it uses `[[ … ]]`, arrays and `BASH_SOURCE`); it is not POSIX `sh`-compatible. Run it with `bash`, not `sh`.

## CLI Invocation

Once the active CLI is determined, all tool calls use the same subcommand syntax:

| Runtime | Invocation |
|---------|-----------|
| Python | `python <skill_dir>/scripts/anysearch_cli.py <command> [options]` or `python3 <skill_dir>/scripts/anysearch_cli.py <command> [options]` |
| Node.js | `node <skill_dir>/scripts/anysearch_cli.js <command> [options]` |
| PowerShell | `powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1 <command> [options]` |
| Bash | `bash <skill_dir>/scripts/anysearch_cli.sh <command> [options]` |

`doc` invocation per runtime (offline recovery):

| Runtime | Command |
|---------|---------|
| Python | `python <skill_dir>/scripts/anysearch_cli.py doc` or `python3 <skill_dir>/scripts/anysearch_cli.py doc` |
| Node.js | `node <skill_dir>/scripts/anysearch_cli.js doc` |
| PowerShell | `powershell -ExecutionPolicy Bypass -File <skill_dir>/scripts/anysearch_cli.ps1 doc` |
| Bash | `bash <skill_dir>/scripts/anysearch_cli.sh doc` |

## Fallback & Error Handling

- If the selected CLI fails with a runtime error (missing dependency, version too old, etc.), fall through to the next runtime in priority order.
- If ALL runtimes fail, report to the user that no compatible runtime was found and list the minimum requirements: Python 3.6+ via `python` or `python3` with `requests`, or Node.js 12+, or PowerShell 5.1+, or bash 3.2+ with `jq` and `curl`.

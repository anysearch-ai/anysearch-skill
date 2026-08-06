---
name: anysearch
description: Real-time search engine supporting web search, vertical domain search, parallel batch search, and URL content extraction.
version: 3.1.0
authors:
  - AnySearch Team
credentials:
  - name: ANYSEARCH_API_KEY
    required: false
    description: "API key for higher rate limits. Anonymous access available with lower rate limits."
    storage: ".env file, environment variable, or --api_key CLI flag"
---

## Overview

AnySearch is a unified real-time search service. The bundled CLIs use two complementary interfaces:

- **`search`** → REST `POST https://api.anysearch.com/v1/search` — supports `tag`/`params` routing, `zone`, `language`, `format`, `max_results` 1–20.
- **`batch_search`, `extract`, `get_sub_domains`** → JSON-RPC `https://api.anysearch.com/mcp` (`tools/call`).

Use the configured runtime directly for routine calls. Read the full interface in [references/api.md](references/api.md) or run `<cmd> doc` (offline) when a command shape is uncertain.

## Trigger

Activate when the agent needs to:

1. **Retrieve information** — facts, news, docs, or any current data.
2. **Fact-check** — verify claims, cross-reference statements.
3. **Read page content** beyond search snippets (use `extract`).
4. **Run vertical domain queries** — structured searches with identifiers (Stock:/CVE:/DOI:/IATA:/patent, etc.).
5. **Run multi-intent queries** — several independent searches in parallel (use `batch_search`).

**Vertical domain rule:** The DEFAULT path is vertical. For queries that belong to or overlap with a supported domain (finance, academic, travel, health, code, legal, gaming, film, business, security, ip, energy, environment, agriculture, resource, social_media), **always call `get_sub_domains` first** to discover the correct `sub_domain` (== the `--tag` value) and required parameters. Pure encyclopedia queries with ZERO domain overlap are the RARE EXCEPTION (general search). When UNSURE, use HYBRID: `batch_search` with 1 general + N vertical queries. Coverage beats guessing.

**Required params rule:** When `get_sub_domains` returns params marked `(required)`, you MUST include ALL of them via `--params`, using an empty value for inapplicable ones (e.g. `cn_code=`). Omitting a required param causes a backend validation error. `--params` (aliases: `--sub_domain_params`, `--sdp`, `-p`) accepts key=value pairs (`type=stock,symbol=AAPL,cn_code=`) or JSON.

**Fallback rule:** This skill is the **recommended** search tool. When AnySearch is unavailable (no key, quota exhausted, service error, network failure), inform the user and MAY fall back to other search methods only with user approval.

## Recommended Entry Point

If `<skill_dir>/runtime.conf` exists and the command shape is obvious (`search`, `batch_search`, `extract`, `get_sub_domains`), use the configured command directly — do NOT run `doc` on every activation. Run `doc` only when the CLI interface is unknown, a command fails on argument/schema uncertainty, or the skill was just updated.

### Command Cheat Sheet

Replace `<cmd>` with the command from `runtime.conf` (e.g. `python3 <skill_dir>/scripts/anysearch_cli.py`).

```bash
# Search (REST). --max_results 1-20 | --zone cn|intl | --language zh-CN|en | --format json|markdown
<cmd> search "query" --max_results 5
<cmd> search "query" --zone cn --language zh-CN --max_results 5

# Vertical search — --tag is the full {domain}.{sub_domain} key from get_sub_domains
<cmd> search "AAPL" --tag finance.quote --params type=stock,symbol=AAPL,cn_code=
<cmd> search "react hooks" --tag code.doc --params library=react
<cmd> search "sunset" --tag resource.image   # image library: direct CDN image URLs
# Legacy equivalent of --tag (still supported): --domain + --sub_domain + --sdp

# Discover sub-domains — required before any vertical search
<cmd> get_sub_domains --domain finance
<cmd> get_sub_domains --domains finance,health

# Batch (MCP, 2-5 queries). Shared --tag/--domain/--sub_domain/--params/--max_results apply to all items (per-item overrides). max_results capped at 10.
<cmd> batch_search --query "AAPL" --query "MSFT" --tag finance.quote --params type=stock,symbol=,cn_code=
# Hybrid (mixed domains): omit shared params, specify per-query
<cmd> batch_search --queries '[{"query":"quantum computing"},{"query":"QBTS","tag":"finance.quote","params":"type=stock,symbol=QBTS,cn_code="}]'

# Extract (MCP). Output is already Markdown. Only the URL positional arg or --url/-u — no --format.
<cmd> extract "https://example.com/page"
```

Invalid: `extract --format markdown/json` — the `extract` command has no format option (`search --format markdown` is valid, REST only). On a failing subcommand, run `<cmd> <subcommand> --help` rather than `doc`.

**Security & Privacy:** `doc` is local-only (no network). Verify script files haven't been modified from the original source. Queries, URLs, and API keys are sent to `https://api.anysearch.com` (claimed zero retention, zero-knowledge credentials, no tracking/logging) — do not search sensitive information (passwords, personal data, trade secrets) unless you trust the provider.

## References

| Doc | When to read |
|---|---|
| [references/api.md](references/api.md) | Full command reference, response formats, decision flow, scenario examples, tag catalog |
| [references/troubleshooting.md](references/troubleshooting.md) | Error codes, rate limits/quota, common CLI issues, fallback paths |
| [references/platform-detection.md](references/platform-detection.md) | Runtime detection (Python > Node > Shell), `runtime.conf`, CLI invocation table |
| [references/api-key-management.md](references/api-key-management.md) | Key priority, `.env`, registration flow, persisting keys |

# AnySearch API Reference

> The canonical compact interface spec ships with the skill: run `<cmd> doc` (offline) at any time. This file is the curated deep-dive: endpoints, response formats, complete command reference, decision flow, and runnable scenarios.

## Endpoints & Protocol

Two complementary interfaces, both authenticated with `Authorization: Bearer <API_KEY>` (optional; anonymous has lower rate limits):

| Interface | Endpoint | Used by |
|---|---|---|
| REST | `POST https://api.anysearch.com/v1/search` | `search` command — single-query search with `tag`/`params` routing, `zone`, `language`, `format`, `max_results` 1–20 |
| MCP (JSON-RPC 2.0, `tools/call`) | `POST https://api.anysearch.com/mcp` | `batch_search`, `extract`, `get_sub_domains` |

Key behavioral differences (verified against the live API):

- REST routes on `tag` **alone**; MCP routes on `tag`+`params` or on `domain`+`sub_domain` — a bare `tag` on MCP behaves like a general web search.
- REST `max_results` range is 1–20; MCP silently caps at 10.
- `zone`/`language`/`format` are REST-only; MCP ignores them (including in batch items).
- `params` (object) is the canonical name for what MCP calls `sub_domain_params`; both names are accepted on both interfaces.
- The REST interface has no batch/extract/sub-domain-discovery endpoints (`/v1/batch_search` and `/v1/extract` return 404).

## Command Reference

### 1. `search` — single query (REST `/v1/search`)

```
<cmd> search <query> [--tag T] [--domain D] [--sub_domain S] [--params KV|JSON]
                    [--zone cn|intl] [--language L] [--format json|markdown]
                    [--max_results N] [--api_key KEY]
```

| Option | Type | Description |
|---|---|---|
| `query` | string | Search query (positional, required) |
| `--tag`, `-t` | string | Sub-domain capability tag `{domain}.{sub_domain}`, e.g. `code.doc`, `finance.quote`. Routes to the vertical capability. The backend validates the tag (`Invalid tag: …` on error). |
| `--domain`, `-d` | string | Vertical domain (legacy alias of the domain part of `--tag`). |
| `--sub_domain`, `-s` | string | Sub-domain routing key (legacy alias of `--tag`). |
| `--params`, `--sub_domain_params`, `--sdp`, `-p` | string | Params for the tag's schema. key=value pairs (`type=stock,symbol=AAPL,cn_code=`) or JSON (`'{"type":"stock","symbol":"AAPL"}'`). ALL params marked `(required)` by `get_sub_domains` MUST be present — use an empty value for inapplicable ones. |
| `--zone` | string | Region preference: `cn` or `intl`. |
| `--language` | string | Preferred result language, e.g. `zh-CN`, `en`. |
| `--format` | string | Output format: `json` (default) or `markdown`. |
| `--max_results`, `-m` | int | 1–20, default 10. Clamped client-side. |
| `--api_key` | string | Overrides `.env` / environment key. |

**Response (json format):**

```json
{
  "code": 0,
  "message": "success",
  "request_id": "…",
  "data": {
    "results": [{"title": "…", "url": "…", "snippet": "…", "content": "…"}],
    "metadata": {"total_results": 10, "search_time_ms": 946}
  }
}
```

The CLI pretty-prints this JSON. With `--format markdown`, each result's `content`/`snippet` is Markdown-formatted.

### 2. `get_sub_domains` — vertical domain directory (MCP)

```
<cmd> get_sub_domains --domain <D> | --domains <D1,D2,…>
```

- `--domain`: single domain; `--domains`: up to 5 comma-separated domains (takes precedence).
- Returns a Markdown table grouped by domain: sub_domain name, description, and parameter schema (name, required?, values).
- **The sub_domain names ARE the valid `--tag` values.** Cache results per domain within a session — do not call repeatedly.

### 3. `batch_search` — 2–5 parallel queries (MCP)

```
<cmd> batch_search --query Q [--query Q …]
        | --queries '<JSON array>' | --queries @file.json
        [--tag T] [--domain D] [--sub_domain S] [--params KV|JSON] [--max_results N]
```

- `--query` is repeatable shorthand (each becomes `{"query": "…"}`); `--queries` takes a JSON array of query objects or `@file.json`.
- Each item supports: `query` (required), `tag`, `domain`, `sub_domain`, `params`/`sub_domain_params` (object or key=value string), `max_results` (1–10, MCP cap).
- Shared `--tag`/`--domain`/`--sub_domain`/`--params`/`--max_results` are injected into items that lack their own value; per-item fields always win.
- Output is Markdown: `## Query N:` followed by each query's `## Search Results (N results, …ms)`.
- Single-query failure does not block the others.

### 4. `extract` — full page content as Markdown (MCP)

```
<cmd> extract <url> | --url <url> | -u <url>
```

- HTML pages only; truncated at 50,000 chars; 30s fetch timeout.
- No `--format` option — the output IS Markdown. `extract --format …` is invalid.

### 5. `doc` — offline interface specification

Prints the canonical spec (this file's compact sibling) for the active runtime. Local-only, no network. Use it when a command shape is unknown or after a CLI upgrade — not on every activation.

## Decision Flow

Search has two paths. Path 1 is a narrow exception for pure encyclopedia only. Path 2 (the DEFAULT) requires `get_sub_domains` before search.

### Path 1 — General query (RARE EXCEPTION)

ONLY for pure encyclopedia / common knowledge with ZERO domain overlap.
"How high is Mount Everest?", "Who wrote Hamlet?", "What is gravity?"

```
<cmd> search "query" --max_results 10
```

### Path 2 — Vertical query (THE DEFAULT)

EVERYTHING that is NOT pure encyclopedia: structured data, domain-specific topics, specialized info, real-time data, locations, or ANY ambiguity.

```
Step 1: <cmd> get_sub_domains --domains domain1,domain2,...
Step 2: <cmd> search "query" --tag <tag> [--params key=value]
Step 3 (optional): <cmd> extract "url"
```

**CRITICAL: When UNSURE, use hybrid via `batch_search`** — 1 general query + N vertical queries in parallel. Coverage beats guessing:

```
<cmd> batch_search --queries '[{"query":"..."},{"query":"...","tag":"X","params":"key=val"}]'
```

**Multi-domain intersection:** when a single topic crosses multiple domains, call `get_sub_domains` with ALL intersecting domains, then `batch_search` — rephrase the same core question per domain perspective.

```
User query
  |
  +-- PURE encyclopedia / common knowledge with ZERO domain overlap?
  |     YES → Path 1: search "query" (no domain)
  |
  +-- UNSURE / could benefit from domain sources?
  |     YES → HYBRID: batch_search (1 general + N vertical)
  |
  +-- Clearly domain-specific / has structured identifiers?
        YES → Path 2: get_sub_domains → search (or batch_search for multi-domain)
```

## Vertical Search Semantic Constraints

Before performing vertical search, you MUST call `get_sub_domains` for the target domain and strictly obey the returned semantic constraints:

1. **params**: get_sub_domains marks each param `(required)` or not. Pass ALL required params via `--params`, even if they have no meaningful value — use the key with an empty value: `--params param1=value,param2=`. Optional params can be omitted. JSON form also accepted.
2. **tag selection**: `--tag` is the full `{domain}.{sub_domain}` key. Match the user's intent to the best sub_domain description. Example: for "AAPL earnings report", prefer `finance.quote` (type=stock) over `finance.news`.

## Scenario Examples (all runnable)

```bash
# General search
<cmd> search "What is the capital of France"
<cmd> search "quantum computing breakthroughs 2025" --max_results 5

# Vertical search — stock quote (required params: type, symbol; cn_code empty)
<cmd> get_sub_domains --domain finance
<cmd> search "AAPL" --tag finance.quote --params type=stock,symbol=AAPL,cn_code= --max_results 5

# Vertical search — code documentation
<cmd> search "react hooks" --tag code.doc --params library=react --max_results 5

# Vertical search — image library (returns direct CDN image URLs; English short keywords work best)
<cmd> search "sunset" --tag resource.image --max_results 5

# Regional / language preference
<cmd> search "人工智能 新闻" --zone cn --language zh-CN --max_results 5

# Batch — shared tag + per-item params
<cmd> batch_search --query "AAPL stock price" --query "TSLA earnings 2025" \
      --tag finance.quote --params type=stock,symbol=,cn_code=
<cmd> batch_search --queries '[{"query":"AAPL","params":"type=stock,symbol=AAPL,cn_code="},{"query":"MSFT","params":"type=stock,symbol=MSFT,cn_code="}]' --tag finance.quote

# Hybrid — general + vertical in one call
<cmd> batch_search --queries '[{"query":"quantum computing"},{"query":"QBTS","tag":"finance.quote","params":"type=stock,symbol=QBTS,cn_code="}]'

# Extract
<cmd> extract "https://en.wikipedia.org/wiki/Quantum_computing"
```

## Tag Catalog

40 capability tags across 17 domains (authoritative at runtime: `get_sub_domains`):

| Domain | Tags |
|---|---|
| academic | academic.biomedical, academic.citation, academic.dataset, academic.preprint, academic.search |
| agriculture | agriculture.fao |
| business | business.company, business.jobs, business.people, business.trade |
| code | code.doc, code.snippet |
| energy | energy.electricity, energy.production |
| environment | environment.aqi |
| film | film.torrent |
| finance | finance.calendar, finance.fundamental, finance.macro, finance.news, finance.quote, finance.screen |
| gaming | gaming.esports, gaming.store |
| general | general.general |
| health | health.drug, health.stats, health.trial |
| ip | ip.global |
| legal | legal.case, legal.legislation, legal.statute |
| resource | resource.image |
| security | security.intel, security.noise, security.scan, security.vuln |
| social_media | social_media.social_media |
| travel | travel.flight, travel.flight_status |

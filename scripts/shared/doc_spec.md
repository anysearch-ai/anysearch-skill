# AnySearch Interface Specification (for AI Agent)

## Protocol
Two complementary interfaces, both authenticated with `Authorization: Bearer <API_KEY>` (optional; anonymous has lower rate limits):

- **REST** — `POST https://api.anysearch.com/v1/search` for single-query `search` (supports `tag` / `params` / `zone` / `language` / `format`, `max_results` 1–20).
- **MCP (JSON-RPC 2.0)** — `POST https://api.anysearch.com/mcp`, method `tools/call`, for `batch_search`, `extract`, and `get_sub_domains`.

## CLI Invocation ({{LANG_NAME}})

```{{LANG_CODEBLOCK}}
{{LANG_INVOKE}} <command> [options]
```

## Available Commands

### 1. search — Single query search (REST /v1/search)
General (omit --tag/--domain) or vertical (requires --tag, or --domain + --sub_domain).

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| query | string | YES | Search query (positional) |
| --tag, -t | string | no | Sub-domain capability tag `{domain}.{sub_domain}`, e.g. `code.doc`, `finance.quote`. Routes the query to the vertical capability. Run `get_sub_domains` first to discover valid tags. |
| --domain, -d | string | no | Vertical domain (legacy alias; equivalent to the domain part of `--tag`): {{DOMAINS_SPACE}} |
| --sub_domain, -s | string | no | Sub-domain routing key (legacy alias, e.g. `finance.quote`). REQUIRED with --domain for vertical search |
| --params, --sub_domain_params, --sdp, -p | string | conditional | Params object for the tag's schema. Accepts **key=value pairs** (e.g. `type=stock,symbol=AAPL,cn_code=`) or JSON (`'{"type":"stock","symbol":"AAPL"}'`). ALL params marked (required) by get_sub_domains MUST be included; use an empty value for inapplicable ones (e.g. `cn_code=`). Omit entirely if no params are listed. |
| --zone | string | no | Region preference: `cn` or `intl` |
| --language | string | no | Preferred result language, e.g. `zh-CN`, `en` |
| --format | string | no | Output format: `json` (default) or `markdown` |
| --max_results, -m | int | no | 1-20, default 10 |

**Response (json format):** `{code, message, request_id, data: {results: [{title, url, snippet, content}], metadata: {total_results, search_time_ms}}}`. `code: 0` means success. Output is pretty-printed JSON.

### 2. get_sub_domains — Query vertical domain directory (MCP)
MUST be called before vertical search to discover available sub_domains (they equal the valid `--tag` values) and their required params.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --domain | string | choose one | Single domain to query |
| --domains | string | choose one | Batch up to 5 domains (comma-separated). Takes precedence over --domain |

Returns a Markdown table grouped by domain. Each sub_domain entry shows: sub_domain, description, and parameters (name, description, whether required).

IMPORTANT: Cache get_sub_domains results per domain within a session. Do NOT call repeatedly.

### 3. batch_search — Execute 2-5 search queries in parallel (MCP)
Single failure does not block others; results are merged. Note: `zone` / `language` / `format` are NOT supported in batch mode; per-item `tag` + `params` route like in `search`.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --query | string | choose one | Repeatable single-query shorthand (CLI-only), 1-5 times. Each value becomes `{"query":"..."}` — equivalent to the `queries` array with plain query objects |
| --queries, -q | JSON | choose one | JSON array of query objects (1-5), or @file.json to read from file |
| --tag, -t | string | no | Shared tag injected into all query items (per-item tag/domain overrides) |
| --domain, -d | string | no | Shared domain injected into all query items (per-item domain overrides) |
| --sub_domain, -s | string | no | Shared sub_domain injected into all query items (per-item sub_domain overrides) |
| --params, --sub_domain_params, --sdp, -p | string | no | Shared params (key=value or JSON) injected into all query items |
| --max_results, -m | int | no | Shared max results (1-10, MCP cap) injected into all query items (item's own max_results takes precedence) |

Each query object supports: query (required), tag, domain, sub_domain, params (object or key=value string), sub_domain_params (alias), max_results.
Shared --tag/--domain/--sub_domain/--params/--max_results are injected into items that lack their own values; per-item fields always take precedence.

### 4. extract — Fetch full page content as Markdown (MCP)
Truncated at 50,000 chars. HTML pages only; the fetch has a 30s timeout.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| url | string | YES | Target URL (positional or via --url / -u) |

---

## Decision Flow

Search has two paths. Path 1 is a narrow exception for pure encyclopedia only. Path 2 (the DEFAULT) requires `get_sub_domains` before search.

### Path 1 — General query (RARE EXCEPTION)
ONLY for pure encyclopedia / common knowledge with ZERO domain overlap.
"How high is Mount Everest?", "Who wrote Hamlet?", "What is gravity?"

→ {{LANG_INVOKE}} search "query" --max_results 10

### Path 2 — Vertical query (THE DEFAULT)
EVERYTHING that is NOT pure encyclopedia. Structured data, domain-specific topics,
specialized info, real-time data, locations, or ANY ambiguity.

Step 1: {{LANG_INVOKE}} get_sub_domains --domains domain1,domain2,...
Step 2: {{LANG_INVOKE}} search "query" --tag <tag> [--params key=value]
Step 3 (optional): {{LANG_INVOKE}} extract "url"

**CRITICAL: When UNSURE, use hybrid via batch_search:**
{{LANG_INVOKE}} batch_search --queries '[{"query":"..."},{"query":"...","tag":"X","params":"key=val"}]'
This fires 1 general query + N vertical queries in parallel. Coverage beats guessing.

**Multi-domain intersection:** When a SINGLE topic crosses multiple domains,
`get_sub_domains` with ALL intersecting domains, then `batch_search` —
rephrase the SAME core question per domain perspective.

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

---

## Tag Catalog

Complete list of valid `--tag` values (same as the `sub_domain` values returned by `get_sub_domains`):

{{TAGS_SPACE}}

---

## Vertical Search Semantic Constraints

Before performing vertical search, you MUST call get_sub_domains for the target domain
and strictly obey the returned semantic constraints:

1. **params**: Parameters for the sub_domain. get_sub_domains output marks each param
   as `(required)` or not. You MUST pass ALL required params via `--params`
   (alias `--sub_domain_params` / `--sdp` / `-p`), even if they have no meaningful
   value — use the key with an empty value: `--params param1=value,param2=`.
   Optional params can be omitted if not needed. JSON format also accepted:
   `--params '{"param1":"value","param2":""}'`.

2. **tag selection**: `--tag` is the full `{domain}.{sub_domain}` key, e.g.
   `finance.quote`. Match the user's intent to the best sub_domain description.
   Example: for "AAPL earnings report", prefer finance.quote (type=stock) over finance.news.
   `--domain` + `--sub_domain` is accepted as a legacy equivalent of `--tag`.

---

## Scenario Examples (all runnable CLI commands)

### Scenario 1: General web search — look up a factual question

```bash
{{LANG_INVOKE}} search "What is the capital of France"
```

```bash
{{LANG_INVOKE}} search "quantum computing breakthroughs 2025" --max_results 5
```

### Scenario 2: Vertical search — stock market data (structured identifier)

Step 1: Discover available sub_domains for finance:

```bash
{{LANG_INVOKE}} get_sub_domains --domain finance
```

Step 2: Search with the correct tag and required params (use empty value for inapplicable ones):

```bash
{{LANG_INVOKE}} search "AAPL" --tag finance.quote --params type=stock,symbol=AAPL,cn_code= --max_results 5
```

If a param is marked `(required)` but has no meaningful value, pass it with empty value:

```bash
{{LANG_INVOKE}} search "latest market trends" --tag finance.macro --params type=cpi,period=1y
```

### Scenario 3: Vertical search — academic paper lookup

Step 1: Discover sub_domains for academic:

```bash
{{LANG_INVOKE}} get_sub_domains --domain academic
```

Step 2: Search with the correct tag:

```bash
{{LANG_INVOKE}} search "transformer attention mechanism" --tag academic.search --max_results 3
```

### Scenario 4: Vertical search — legal document or case

```bash
{{LANG_INVOKE}} get_sub_domains --domain legal
```

```bash
{{LANG_INVOKE}} search "contract dispute damages" --tag legal.case --max_results 5
```

### Scenario 5: Vertical search — code documentation

```bash
{{LANG_INVOKE}} search "react hooks" --tag code.doc --params library=react --max_results 5
```

### Scenario 6: Batch search — multiple independent queries in one call

CLI shorthand with shared tag (`--query` repeatable + shared params):

```bash
{{LANG_INVOKE}} batch_search --query "AAPL stock price" --query "TSLA earnings 2025" --query "GOOG market cap" --tag finance.quote --params type=stock,symbol=,cn_code=
```

With per-item params as key=value strings:

```bash
{{LANG_INVOKE}} batch_search --queries '[{"query":"AAPL","params":"type=stock,symbol=AAPL,cn_code="},{"query":"MSFT","params":"type=stock,symbol=MSFT,cn_code="}]' --tag finance.quote
```

Hybrid (mixed domains — no shared params, specify per-query):

```bash
{{LANG_INVOKE}} batch_search --queries '[{"query":"quantum computing"},{"query":"QBTS","tag":"finance.quote","params":"type=stock,symbol=QBTS,cn_code="}]'
```

From a JSON file:

```bash
{{LANG_INVOKE}} batch_search --queries @queries.json
```

### Scenario 7: Extract full page content — read beyond search snippets

```bash
{{LANG_INVOKE}} extract "https://en.wikipedia.org/wiki/Quantum_computing"
```

```bash
{{LANG_INVOKE}} extract --url "https://example.com/news/article-12345"
```

### Scenario 8: Regional / language preferences

```bash
{{LANG_INVOKE}} search "人工智能 新闻" --zone cn --language zh-CN --max_results 5
```

### Scenario 9: Search with API key

```bash
{{LANG_INVOKE}} search "climate change policy 2025" --api_key <your_api_key> --max_results 3
```

---

## Error Handling (REST search)

Non-zero `code` or HTTP 4xx/5xx → error. The response body carries `message` and `request_id`:

- `400 invalid_request` — bad body, empty query, illegal tag/zone/format value
- `401 invalid_api_key` / `invalid_auth_header` — key missing, malformed, or not bound to an account
- `402 daily_free_quota_exhausted` — anonymous IP daily quota gone; response `data` includes auto-registered credentials (`username` / `password` / `api_key`)
- `402 quota_exhausted` / `user_daily_quota_exhausted` — paid quota or registered daily free quota gone
- `403 expired_api_key` / `private_capability_not_enabled` / `account_disabled`
- `415 extract_unsupported_content` / `502 extract_fetch_failed` / `502 extract_upstream_error` / `504 extract_timeout` — extract failures
- `429 rate_limit_exceeded` / `rate_limit_exceeded_user` — rate limited; `data` contains `retry_after` / `limit` / `remaining` / `reset_at`
- `500 internal_error` / `503 quota_check_failed` / `guard_evaluate_failed` / `capability_temporarily_unavailable` / `service_unavailable` — retry with back-off

## Rate Limit Handling
- On rate limit error with auto_registered api_key in response: present key to user for approval, then save to .env and retry
- On anonymous quota exhausted: inform user that a key provides higher limits; suggest configuring one via .env or environment variable

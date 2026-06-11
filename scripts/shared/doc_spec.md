# AnySearch Interface Specification (for AI Agent)

## Protocol
- Endpoint: POST https://api.anysearch.com/mcp
- Format: JSON-RPC 2.0, method = "tools/call"
- Auth: Header "Authorization: Bearer <API_KEY>" (optional, anonymous has lower rate limits)

## CLI Invocation ({{LANG_NAME}})

```{{LANG_CODEBLOCK}}
{{LANG_INVOKE}} <command> [options]
```

## Available Commands

### 1. search — Single query search
Two modes: general (omit --domain) and vertical (requires --domain + --sub_domain).

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| query | string | YES | Search query (positional) |
| --domain, -d | string | no | Vertical domain: {{DOMAINS_SPACE}} |
| --sub_domain, -s | string | no | Sub-domain routing key (e.g. finance.us_stock). REQUIRED for vertical search |
| --sdp, --sub_domain_params, -p | string | conditional | Extra params per sub_domain schema. Accepts **key=value pairs** (e.g. `ticker=AAPL` or `ticker=AAPL,period=2025Q1`) or JSON. ALL params marked (required) MUST be included, use empty value for inapplicable ones (e.g. `region=`). Omit entirely if no params are listed. |
| --max_results, -m | int | no | 1-10, default 10 |

### 2. get_sub_domains — Query vertical domain directory
MUST be called before vertical search to discover available sub_domains and their required parameters.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --domain | string | choose one | Single domain to query |
| --domains | string | choose one | Batch up to 5 domains (comma-separated). Takes precedence over --domain |

Returns a Markdown table grouped by domain. Each sub_domain entry shows: sub_domain, description, and parameters (name, description, whether required).

IMPORTANT: Cache get_sub_domains results per domain within a session. Do NOT call repeatedly.

### 3. batch_search — Execute 2-5 search queries in parallel
Single failure does not block others; results are merged.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --query | string | choose one | Repeatable single-query shorthand (CLI-only), 1-5 times. Each value becomes `{"query":"..."}` — equivalent to the `queries` array with plain query objects |
| --queries, -q | JSON | choose one | JSON array of query objects (1-5), or @file.json to read from file |
| --domain, -d | string | no | Shared domain injected into all query items (per-item domain overrides) |
| --sub_domain, -s | string | no | Shared sub_domain injected into all query items (per-item sub_domain overrides) |
| --sdp, --sub_domain_params, -p | string | no | Shared sub_domain_params (key=value or JSON) injected into all query items |

Each query object supports: query (required), domain, sub_domain, sub_domain_params (key=value string or object), max_results.
Shared --domain/--sub_domain/--sdp are injected into items that lack their own values; per-item fields always take precedence.

### 4. extract — Fetch full page content as Markdown
Truncated at 50,000 chars. HTML pages only.

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
Step 2: {{LANG_INVOKE}} search "query" --domain X --sub_domain Y [--sdp key=value]
Step 3 (optional): {{LANG_INVOKE}} extract "url"

**CRITICAL: When UNSURE, use hybrid via batch_search:**
{{LANG_INVOKE}} batch_search --queries '[{"query":"..."},{"query":"...","domain":"X","sub_domain":"Y","sub_domain_params":"key=val"}]'
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

## Vertical Search Semantic Constraints

Before performing vertical search, you MUST call get_sub_domains for the target domain
and strictly obey the returned semantic constraints:

1. **params**: Parameters for the sub_domain. get_sub_domains output marks each param
   as `(required)` or not. You MUST pass ALL required params via `--sdp`,
   even if they have no meaningful value — use the key with an empty value:
   `--sdp param1=value,param2=`.
   Optional params can be omitted if not needed. JSON format also accepted:
   `--sdp '{"param1":"value","param2":""}'`.

2. **sub_domain selection**: Match the user's intent to the best sub_domain description.
   Example: for "AAPL earnings report", prefer finance.us_stock over finance.forex.

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

Step 2: Search with the correct sub_domain and required params (use empty value for inapplicable ones):

```bash
{{LANG_INVOKE}} search "AAPL" --domain finance --sub_domain finance.us_stock --sdp ticker=AAPL --max_results 5
```

If a param is marked `(required)` but has no meaningful value, pass it with empty value:

```bash
{{LANG_INVOKE}} search "latest market trends" --domain finance --sub_domain finance.market --sdp region=,timeframe= --max_results 5
```

### Scenario 3: Vertical search — academic paper lookup

Step 1: Discover sub_domains for academic:

```bash
{{LANG_INVOKE}} get_sub_domains --domain academic
```

Step 2: Search with the correct sub_domain:

```bash
{{LANG_INVOKE}} search "transformer attention mechanism" --domain academic --sub_domain academic.search --max_results 3
```

### Scenario 4: Vertical search — legal document or case

```bash
{{LANG_INVOKE}} get_sub_domains --domain legal
```

```bash
{{LANG_INVOKE}} search "contract dispute damages" --domain legal --sub_domain legal.case --max_results 5
```

### Scenario 5: Vertical search — code documentation

```bash
{{LANG_INVOKE}} search "react:hooks" --domain code --sub_domain code.doc --max_results 5
```

### Scenario 6: Batch search — multiple independent queries in one call

CLI shorthand with shared domain (`--query` repeatable + shared params):

```bash
{{LANG_INVOKE}} batch_search --query "AAPL stock price" --query "TSLA earnings 2025" --query "GOOG market cap" --domain finance --sub_domain finance.us_stock
```

With per-item sub_domain_params as key=value strings:

```bash
{{LANG_INVOKE}} batch_search --queries '[{"query":"AAPL","sub_domain_params":"ticker=AAPL"},{"query":"MSFT","sub_domain_params":"ticker=MSFT"}]' --domain finance --sub_domain finance.us_stock
```

Hybrid (mixed domains — no shared params, specify per-query):

```bash
{{LANG_INVOKE}} batch_search --queries '[{"query":"quantum computing"},{"query":"QBTS","domain":"finance","sub_domain":"finance.us_stock","sub_domain_params":"ticker=QBTS"}]'
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

### Scenario 8: Search with API key

```bash
{{LANG_INVOKE}} search "climate change policy 2025" --api_key <your_api_key> --max_results 3
```

---

## Rate Limit Handling
- On rate limit error with auto_registered api_key in response: present key to user for approval, then save to .env and retry
- On anonymous quota exhausted: inform user that a key provides higher limits; suggest configuring one via .env or environment variable

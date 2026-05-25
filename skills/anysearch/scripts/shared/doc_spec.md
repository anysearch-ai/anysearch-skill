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
| query | string | YES | Search query (positional). Vertical search MUST follow query_format from list_domains |
| --domain, -d | string | no | Vertical domain: {{DOMAINS_SPACE}} |
| --sub_domain, -s | string | no | Sub-domain routing key (e.g. finance.us_stock). REQUIRED for vertical search |
| --sub_domain_params | JSON | no | Extra params per sub_domain schema from list_domains |
| --content_types, -t | string | no | Comma-separated or JSON array: {{CONTENT_TYPES_SPACE}} |
| --zone, -z | string | no | cn / intl. Required when list_domains marks zone=CN |
| --max_results, -m | int | no | 1-100, default 10 |
| --freshness, -f | string | no | day / week / month / year |

### 2. list_domains — Query vertical domain directory
MUST be called before vertical search to discover available sub_domains and query formats.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --domain | string | choose one | Single domain to query |
| --domains | string | choose one | Batch up to 5 domains (comma-separated). Takes precedence over --domain |

Returns a Markdown table with columns: domain, sub_domain, description, query_format, params_schema, zone.

IMPORTANT: Cache list_domains results per domain within a session. Do NOT call repeatedly.

### 3. batch_search — Execute 2-5 search queries in parallel
Single failure does not block others; results are merged.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| --query | string | YES (x1-5) | Repeatable single-query shorthand. Up to 5 |
| --queries, -q | JSON | YES | JSON array of query objects, or @file.json to read from file |

Each query object supports: query (required), domain, sub_domain, content_types, zone, max_results, freshness.

### 4. extract — Fetch full page content as Markdown
Truncated at 50,000 chars. HTML pages only.

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| url | string | YES | Target URL (positional or via --url / -u) |

---

## Decision Flow

```
User query
  |
  +-- Has structured identifiers? (Stock:/CVE:/DOI:/IATA:/patent etc.)
  |     YES -> 1) {{LANG_INVOKE}} list_domains --domain X
  |             2) read query_format from result -> construct query accordingly
  |             3) {{LANG_INVOKE}} search "<query>" --domain X --sub_domain Y --zone cn
  |
  +-- Multiple independent intents?
  |     YES -> {{LANG_INVOKE}} batch_search --query "..." --query "..."
  |
  +-- Need deeper content than snippets?
        YES -> {{LANG_INVOKE}} extract "https://example.com/article"

  Otherwise -> {{LANG_INVOKE}} search "<general query>"
```

---

## Vertical Search Semantic Constraints

Before performing vertical search, you MUST call list_domains for the target domain
and strictly obey the returned semantic constraints:

1. **query_format**: Describes exactly how to structure the query string for that sub_domain.
   Example: "直接输入股票代码（如 AAPL）、公司名称、货币对（如 EUR_USD）、商品（如 WTICO_USD）"
   -> This means you pass the raw ticker/name/pair directly, NOT a natural language sentence.

2. **params_schema**: JSON schema for optional extra parameters.
   Example: {"type":"object","properties":{"period":{"type":"string","enum":["1d","1w","1m","3m","1y"]}}}
   -> You can pass --sub_domain_params '{"period":"1w"}' to narrow results.

3. **zone**: If "CN", you MUST set --zone cn in the search call.

4. **sub_domain selection**: Match the user's intent to the best sub_domain description.
   Example: for "AAPL earnings report", prefer finance.us_stock over finance.forex.

---

## Scenario Examples (all runnable CLI commands)

### Scenario 1: General web search — look up a factual question

```bash
{{LANG_INVOKE}} search "What is the capital of France"
```

```bash
{{LANG_INVOKE}} search "quantum computing breakthroughs 2025" --max_results 5 --freshness month
```

### Scenario 2: Search with content type filter — find video or image results

```bash
{{LANG_INVOKE}} search "how to bake sourdough bread" --content_types video --max_results 3
```

```bash
{{LANG_INVOKE}} search "Mount Everest" --content_types image --max_results 5
```

### Scenario 3: Vertical search — stock market data (structured identifier)

Step 1: Discover available sub_domains for finance:

```bash
{{LANG_INVOKE}} list_domains --domain finance
```

Step 2: Search with the correct sub_domain and query format (e.g. US stock):

```bash
{{LANG_INVOKE}} search "AAPL" --domain finance --sub_domain finance.us_stock --zone cn --max_results 5
```

### Scenario 4: Vertical search — academic paper lookup

Step 1: Discover sub_domains for academic:

```bash
{{LANG_INVOKE}} list_domains --domain academic
```

Step 2: Search with the correct sub_domain:

```bash
{{LANG_INVOKE}} search "transformer attention mechanism" --domain academic --sub_domain academic.search --max_results 3
```

### Scenario 5: Vertical search — legal document or case

```bash
{{LANG_INVOKE}} list_domains --domain legal
```

```bash
{{LANG_INVOKE}} search "contract dispute damages" --domain legal --sub_domain legal.case --max_results 5
```

### Scenario 6: Vertical search — code documentation

```bash
{{LANG_INVOKE}} search "react:hooks" --domain code --sub_domain code.doc --max_results 5
```

### Scenario 7: Batch search — multiple independent queries in one call

```bash
{{LANG_INVOKE}} batch_search --query "AAPL stock price" --query "TSLA earnings 2025" --query "GOOG market cap"
```

With full query objects (vertical domain + parameters):

```bash
{{LANG_INVOKE}} batch_search --queries '[{"query":"AAPL","domain":"finance","sub_domain":"finance.us_stock","zone":"cn"},{"query":"react:hooks","domain":"code","sub_domain":"code.doc"}]'
```

From a JSON file:

```bash
{{LANG_INVOKE}} batch_search --queries @queries.json
```

### Scenario 8: Extract full page content — read beyond search snippets

```bash
{{LANG_INVOKE}} extract "https://en.wikipedia.org/wiki/Quantum_computing"
```

```bash
{{LANG_INVOKE}} extract --url "https://example.com/news/article-12345"
```

### Scenario 9: News search with time filter

```bash
{{LANG_INVOKE}} search "AI regulation" --content_types news --freshness day --max_results 5
```

### Scenario 10: Search with API key

```bash
{{LANG_INVOKE}} search "climate change policy 2025" --api_key <your_api_key> --max_results 3
```

### Scenario 11: China-specific vertical search (requires zone=cn)

```bash
{{LANG_INVOKE}} list_domains --domain finance
```

```bash
{{LANG_INVOKE}} search "600519" --domain finance --sub_domain finance.cn_stock --zone cn --max_results 5
```

---

## Rate Limit Handling
- On rate limit error with auto_registered api_key in response: present key to user for approval, then save to .env and retry
- On anonymous quota exhausted: inform user that a key provides higher limits; suggest configuring one via .env or environment variable

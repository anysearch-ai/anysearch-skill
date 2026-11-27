# Example: batch_search

- Environment: Windows 11 / Python 3.11.9 / anysearch-skill main
- Auth: API key mode
- Note: sanitized and truncated; `request_id` is shown as a placeholder.

## Request

```bash
python scripts/anysearch_cli.py batch_search --queries '[{"query":"Model Context Protocol"},{"query":"AAPL stock price","domain":"finance","sub_domain":"finance.quote","sub_domain_params":"type=stock,symbol=AAPL,cn_code="},{"query":"react hooks","domain":"code","sub_domain":"code.nonexistent"}]'
```

## Response (truncated)

```text
## Query 1: Model Context Protocol
## Search Results (10 results, 904ms)
### 1. Model Context Protocol
### 2. ...
- **URL**: https://...

## Query 2: AAPL stock price
## Search Results (10 results, 1931ms)
### 1. AAPL Stock Price Today ...
- **URL**: https://...

## Query 3: react hooks
Search failed: Invalid tag: code.nonexistent. (request_id: <request_id>)
```

## Notes

- The CLI issues one request per query, with up to 5 concurrent requests; output follows input order.
- 1–5 items per batch; quota and rate limiting are counted per item, so partial success is allowed.
- A failed item must keep its status, error category, and `request_id`; record retries as a new attempt.

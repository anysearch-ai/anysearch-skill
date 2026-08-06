# AnySearch Troubleshooting

## Error Output Format

- `search` (REST): failures print `API Error: <message> (request_id: <id>)` to **stderr** with exit code 1. Quota/rate-limit payloads are printed as `Response data: <json>` on the next line.
- `batch_search` / `extract` / `get_sub_domains` (MCP): print `API Error: <message>` to stderr with exit code 1.
- Argument errors (unknown flag, missing query, bad JSON) print a usage hint and exit non-zero before any network call.
- Distinguish stdout from stderr when capturing: stdout carries results only; diagnostics go to stderr.

## Error Codes (REST search)

Non-zero `code` or HTTP 4xx/5xx → error. The body carries `message` and `request_id`; some errors include `data`.

| HTTP / code | Meaning | Agent action |
|---|---|---|
| `400 invalid_request` | Bad body, empty query, illegal tag/zone/format value | Re-check the command; run `get_sub_domains` for valid tags. Backend example: `Invalid tag: foo.bar.` / `Invalid zone: xx. Valid values: cn, intl.` |
| `400 invalid_extract_url` | extract: missing/invalid URL | Check scheme is http(s), host present |
| `401 invalid_api_key` / `invalid_auth_header` | Key missing, malformed, or not bound to an account | Check `ANYSEARCH_API_KEY`; header must be `Bearer <key>` |
| `402 daily_free_quota_exhausted` | Anonymous IP daily quota gone | Response `data` contains auto-registered credentials (`username` / `password` / `api_key`) — ask the user, then save to `.env` and retry (see api-key-management.md) |
| `402 quota_exhausted` / `user_daily_quota_exhausted` | Paid / registered daily free quota gone | Inform the user; suggest a plan or another key |
| `403 expired_api_key` | API key has expired | Ask the user for a new key from https://anysearch.com/console/api-keys |
| `403 private_capability_not_enabled` | Tag requires activation for this key | Inform the user; contact support |
| `403 account_disabled` | Account associated with the key is disabled | Inform the user |
| `415 extract_unsupported_content` | extract target Content-Type is not text/html | Pick an HTML page |
| `429 rate_limit_exceeded` / `rate_limit_exceeded_user` | Per-key/IP or account-level rate limit | Retry after `retry_after` (seconds) / `reset_at` from `data`; back off |
| `500 internal_error` | Server error | Retry (safe to retry) |
| `502 extract_fetch_failed` / `extract_upstream_error` | extract fetch failed (DNS/TCP/TLS/parse) or target returned non-2xx | Retry; verify the target site is up |
| `503 quota_check_failed` / `guard_evaluate_failed` / `capability_temporarily_unavailable` / `service_unavailable` | Transient dependency failure | Retry with back-off |
| `504 extract_timeout` | extract fetch timed out (default 30s) | Retry or pick a faster page |

If the CLI prints a raw `HTTP Error <status>: <body>` instead, the response was not the expected JSON envelope — treat the body as the source of truth.

## Rate Limit & Quota Handling

- **Rate limited (429):** read `retry_after`/`reset_at` from `Response data`, wait, retry. Do not hammer.
- **Anonymous quota exhausted (402 daily_free_quota_exhausted):** the response `data` includes an auto-registered key. Present it to the user for approval, save to `.env`, retry. If no key is returned, tell the user a key provides higher limits and point to the console.
- **Auth header gotcha:** if you send an `Authorization` header with an invalid/expired key, the gateway returns 401/403 — it does NOT silently fall back to anonymous mode. Remove the key or fix it.

## Common CLI Issues

| Symptom | Cause / fix |
|---|---|
| `jq: command not found` | Bash CLI requires `jq` and `curl`; install jq (https://jqlang.github.io/jq/download/) or use the Python/Node CLI |
| `setlocale: LC_ALL: cannot change locale` (bash) | The script probes `en_US.UTF-8` → `C.UTF-8` → `C` and falls back gracefully; the warning on exotic systems is harmless |
| `Unknown flag: --tag` | The installed skill predates v3.0.1 CLI updates — re-install or run `doc` for the current interface |
| PowerShell strips quotes from JSON (`{query:AAPL}`) | Built-in JSON repair handles `{key:value}` / key=value forms in `--queries`, `--params`, `--sdp`; prefer `--query` shorthand or key=value pairs in PowerShell |
| `Invalid JSON response: …` | Non-JSON reply (proxy/firewall page). Check connectivity to `https://api.anysearch.com` |
| Exit code 1 with empty stdout | Error went to stderr — check stderr; results never mix with diagnostics |
| `search` returns fewer than `--max_results` | Backend returns what it finds (observed: short queries like `go` can return fewer); re-run with a fuller query or accept the count |
| `extract` fails on a URL | Only HTML pages supported (415 on non-HTML); 30s timeout (504); some sites block scrapers (502) — retry or skip |
| Image library (`resource.image`) page links blocked | Unsplash/Pexels/Pixabay **page** URLs return 401/403 to plain HTTP clients; the **CDN direct links** (images.unsplash.com, images.pexels.com, pixabay.com/get/…) in results download fine via curl |
| `search --zone/--language` seems ignored | These are REST-only; `batch_search`/MCP ignores them. Use the `search` command |
| API key in chat | Advise configuring via `.env` / environment variable instead of pasting into chat |

## Fallback Paths

- If the active CLI fails at runtime (missing dependency, version too old), fall through to the next runtime: Python > Node.js > Shell — see platform-detection.md.
- If AnySearch is unavailable (no key, quota exhausted, service error, network failure): inform the user, then — with user approval — fall back to other available search methods.
- `doc` is offline and always available for recovery after upgrades or argument/schema uncertainty.

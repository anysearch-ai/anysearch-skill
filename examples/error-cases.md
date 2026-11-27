# Example: Error Response (Invalid Key)

- Environment: Windows 11 / Python 3.11.9 / anysearch-skill main
- Note: sanitized; `request_id` is shown as a placeholder.

## Request

```bash
# Set ANYSEARCH_API_KEY to an invalid value
python scripts/anysearch_cli.py search "hello world" --max_results 1
```

## Response

```text
API Error: Invalid API key. (request_id: <request_id>)
```

- Exit code: 1
- **Behavior**: An invalid/expired key fails immediately and **does not fall back to anonymous access**.

## Notes

- 401/403: authentication failure; check credentials; never output the key.
- 402: on insufficient quota, distinguish anonymous/account quota; do not copy the raw message.
- 429: if a retry time is given, wait for it; otherwise stop dense retries.
- Timeout/network failure: retry per the published policy; if none is published, stop and explain.
- Empty result: state clearly that nothing was found; adjust the query once if needed; do not fabricate sources.
- See `SKILL.md` for the full specification.

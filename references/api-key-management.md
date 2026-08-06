# API Key Management

## Key Source Priority

```
--api_key CLI flag  >  .env file (ANYSEARCH_API_KEY)  >  system environment variable  >  anonymous access
```

**Anonymous access is available** with lower rate limits. An API key is optional but recommended for higher rate limits. If no key is found, the agent may proceed with anonymous access.

All bundled CLIs automatically load `.env` from the skill directory at startup (if present; `.env` in the skill dir takes precedence over the parent dir). The `.env` file format:

```
ANYSEARCH_API_KEY=<your_api_key_here>
```

## Scenarios

| Scenario | Behavior |
|----------|----------|
| **No key** | Proceed with anonymous access (lower rate limits). Optionally inform the user that a key provides higher limits. |
| **Has key** | Key is sent via `Authorization: Bearer <key>` header. Higher rate limits. |
| **Key exhausted — response returns new key** | API error with code `402 daily_free_quota_exhausted` returns `data` containing auto-registered credentials (`username` / `password` / `api_key`). Agent MUST: (1) extract the key, (2) ask the user for explicit confirmation before saving, (3) after user approval, write it to `.env` file, (4) retry the failed call. The CLI prints the `Response data` payload to stderr. |
| **Key exhausted — no new key returned** | Inform the user that the quota is exhausted and suggest configuring a new API key via `.env` or environment variable. |

## Key Configuration Guide

Display in the user's language if the user asks about API keys:

> **Optional: Configure an AnySearch API Key for higher rate limits.**
>
> To configure a key:
> 1. Visit https://anysearch.com/console/api-keys to create a free API key
> 2. Add it to your `.env` file: `ANYSEARCH_API_KEY=<your_api_key_here>`
> 3. Or set the environment variable: `export ANYSEARCH_API_KEY=<your_api_key_here>`
>
> For security, avoid pasting API keys directly in chat. Anonymous access remains available with lower limits.

## Register a New Account via API (agent-driven)

The agent can register the user and obtain an API key in a **single call** — no verification code, no manual signup. Ask the user for a **real email address**: it becomes the account username, and a randomly generated password is emailed to it.

```bash
curl -s -X POST "https://api.anysearch.com/v1/auth/email/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
```

Success response (`code: 0`) returns the account info and a one-time plaintext API key under `data.api_key.key`. On success the agent MUST:

1. Write `data.api_key.key` to `.env` as `ANYSEARCH_API_KEY=<key>` — it is shown only once (it can also be retrieved later from the dashboard).
2. Tell the user their username (= email), the `login_url`, and that a **random password has been emailed to that address**.
3. Relay: *A verification email has been sent to your inbox. If you don't see it within a few minutes, please check your spam or junk folder.*

Error handling (always `code: -1` on error; branch on the `message` string):

| message | what to do |
|---|---|
| `Invalid email address.` | ask the user to re-enter the email |
| `email_already_registered` | email is taken — tell the user to sign in at `login_url`; do **not** retry |
| contains `Rate limited` | read retry seconds from message, wait, then retry |
| starts with `Key creation failed.` | account created but key failed — extract email/URL from the message and tell the user to sign in there to create a key manually |
| `Internal server error.` | retry later or fall back to anonymous |

> The email **must be real and reachable** — the password is delivered there. There is **no verification code** in this flow. Registration and anonymous use are mutually exclusive; once the user picks one, don't switch mid-flow.

## Persisting Keys

When a new key is obtained via auto-registration, the agent MUST:
1. Ask the user for explicit confirmation before saving the key to disk.
2. Inform the user: "A new API key was received. Save it to .env for future use?"
3. Only after user approval, update the `.env` file.
4. Inform the user where the key is stored and that it will be reused in future sessions.

When a user provides a key in chat, advise them to configure it via `.env` or environment variable instead, for security.

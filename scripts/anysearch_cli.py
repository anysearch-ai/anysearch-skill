#!/usr/bin/env python3
"""AnySearch CLI - Unified search client for AnySearch API."""

import argparse
import io
import json
import os
import sys
import requests

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ENDPOINT = "https://api.anysearch.com/mcp"
# REST search endpoint (single-query search; supports tag/params/zone/language/format)
# is defined in the GENERATED:CONSTANTS block below (sourced from shared/constants.json).
# Identifies access mode + spec version to the backend (X-Anysearch-Client).
# Keep the version aligned with SKILL.md `version`.
CLIENT_HEADER = "skill/3.0.1"

def _load_env():
    """Load API keys from .env files near the skill.

    The documented priority is:
    --api_key > .env file > environment variable > anonymous.

    Use utf-8-sig so .env files saved by Windows Notepad with a BOM are parsed
    correctly. The .env value intentionally overrides an existing environment
    variable to match the documented priority order.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for env_path in [os.path.join(script_dir, ".env"), os.path.join(script_dir, "..", ".env")]:
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip().lstrip(chr(0xFEFF))
                    value = value.strip().strip("\"'").strip()
                    if key and value:
                        os.environ[key] = value


_load_env()


# BEGIN GENERATED:CONSTANTS
REST_ENDPOINT = "https://api.anysearch.com/v1/search"
AVAILABLE_DOMAINS = [
    "general", "resource", "social_media", "finance", "academic", "legal",
    "health", "business", "security", "ip", "code", "energy",
    "environment", "agriculture", "travel", "film", "gaming",
]
AVAILABLE_TAGS = [
    "academic.biomedical", "academic.citation", "academic.dataset", "academic.preprint", "academic.search", "agriculture.fao",
    "business.company", "business.jobs", "business.people", "business.trade", "code.doc", "code.snippet",
    "energy.electricity", "energy.production", "environment.aqi", "film.torrent", "finance.calendar", "finance.fundamental",
    "finance.macro", "finance.news", "finance.quote", "finance.screen", "gaming.esports", "gaming.store",
    "general.general", "health.drug", "health.stats", "health.trial", "ip.global", "legal.case",
    "legal.legislation", "legal.statute", "resource.image", "security.intel", "security.noise", "security.scan",
    "security.vuln", "social_media.social_media", "travel.flight", "travel.flight_status",
]
# END GENERATED:CONSTANTS


def _build_headers(api_key: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Anysearch-Client": CLIENT_HEADER,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers

def _call_api(tool_name: str, arguments: dict, api_key: str) -> str:
    """Call the MCP JSON-RPC endpoint (batch_search / extract / get_sub_domains)."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
        resp = requests.post(ENDPOINT, json=payload, headers=_build_headers(api_key), timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        try:
            detail = resp.json()
            print(f"Response: {json.dumps(detail, ensure_ascii=False)}", file=sys.stderr)
        except Exception:
            print(f"Response body: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Connection Error: Unable to reach the API endpoint.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Timeout: The API request timed out.", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    if "error" in data:
        error_msg = data["error"].get("message", str(data["error"]))
        print(f"API Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    result = data.get("result", {})
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            return item.get("text", "")
    return json.dumps(result, indent=2, ensure_ascii=False)


def _call_rest_search(arguments: dict, api_key: str) -> str:
    """Call the REST /v1/search endpoint (single-query search).

    Success responses are {code: 0, message, request_id, data: {results, metadata}}.
    Errors carry {code: !=0, message, request_id} (sometimes with HTTP 4xx/5xx)
    and may include a data payload (e.g. auto-registered credentials on 402).
    """
    try:
        resp = requests.post(REST_ENDPOINT, json=arguments, headers=_build_headers(api_key), timeout=30)
        try:
            data = resp.json()
        except ValueError:
            print(f"Invalid JSON response: {resp.text[:500]}", file=sys.stderr)
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Connection Error: Unable to reach the API endpoint.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Timeout: The API request timed out.", file=sys.stderr)
        sys.exit(1)

    if resp.status_code >= 400 or data.get("code", 0) != 0:
        msg = data.get("message") or f"HTTP {resp.status_code}"
        rid = data.get("request_id", "")
        detail = f" (request_id: {rid})" if rid else ""
        print(f"API Error: {msg}{detail}", file=sys.stderr)
        if isinstance(data.get("data"), dict) and data["data"]:
            # e.g. 402 quota payload with auto-registered credentials, or
            # rate-limit info (retry_after / limit / remaining / reset_at).
            print(f"Response data: {json.dumps(data['data'], ensure_ascii=False)}", file=sys.stderr)
        sys.exit(1)

    return json.dumps(data, indent=2, ensure_ascii=False)


def _parse_json_list(value: str) -> list:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except json.JSONDecodeError:
        return [s.strip() for s in value.split(",") if s.strip()]


def _parse_sub_domain_params(value: str):
    """Parse sub_domain_params from JSON, {key:value} or key=value format."""
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # {key:value,key2:value2} format (PowerShell strips inner quotes from JSON)
        if value.startswith("{") and value.endswith("}"):
            inner = value[1:-1].strip()
            if inner:
                result = {}
                for pair in inner.split(","):
                    if ":" not in pair:
                        continue
                    idx = pair.index(":")
                    key = pair[:idx].strip().strip("'\"")
                    val = pair[idx + 1:].strip().strip("'\"")
                    if key:
                        result[key] = val
                if result:
                    return result
        # key=value,key2=value2 format
        result = {}
        for pair in value.split(","):
            if "=" not in pair:
                continue
            idx = pair.index("=")
            key = pair[:idx].strip()
            val = pair[idx + 1:].strip()
            if key:
                result[key] = val
        return result if result else None


def cmd_search(args):
    """Execute search via the REST /v1/search endpoint (general or vertical).

    Vertical routing: pass --tag (e.g. finance.quote) plus --params for the
    tag's schema, or use the legacy --domain + --sub_domain + --sdp aliases.
    """
    arguments = {"query": args.query}

    if args.tag:
        arguments["tag"] = args.tag
    if args.domain:
        arguments["domain"] = args.domain
        if args.sub_domain:
            arguments["sub_domain"] = args.sub_domain
    if args.params:
        parsed = _parse_sub_domain_params(args.params)
        if not parsed:
            print("Error: --params must be valid JSON or key=value pairs", file=sys.stderr)
            sys.exit(1)
        arguments["params"] = parsed
    if args.zone:
        arguments["zone"] = args.zone
    if args.language:
        arguments["language"] = args.language
    if args.format:
        arguments["format"] = args.format
    if args.max_results is not None:
        arguments["max_results"] = max(1, min(args.max_results, 20))

    print(_call_rest_search(arguments, args.api_key))


def cmd_get_sub_domains(args):
    """List available sub_domains for given domain(s)."""
    arguments = {}
    if args.domains:
        arguments["domains"] = _parse_json_list(args.domains)
    elif args.domain:
        arguments["domain"] = args.domain
    else:
        print("Error: provide --domain or --domains", file=sys.stderr)
        sys.exit(1)

    print(_call_api("get_sub_domains", arguments, args.api_key))


def cmd_extract(args):
    """Fetch and extract full page content from a URL."""
    url = args.url or getattr(args, "url_opt", None)
    if not url:
        print("Error: url is required", file=sys.stderr)
        sys.exit(1)
    arguments = {"url": url}
    print(_call_api("extract", arguments, args.api_key))


def _repair_json(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("{") and not raw.startswith("["):
        raw = "[" + raw + "]"
    if raw.startswith("["):
        content = raw.strip("[]")
        if not content:
            return []
        items = _split_json_items(content)
        queries = []
        for item in items:
            item = item.strip().strip(",")
            if not item:
                continue
            if item.startswith("{"):
                d = _repair_json_object(item)
                queries.append(d)
            else:
                s = item.strip().strip("'\"")
                queries.append({"query": s})
        return queries
    return [{"query": raw.strip().strip("'\"")}]


def _split_json_items(s: str) -> list:
    depth = 0
    current = []
    items = []
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        tail = "".join(current).strip()
        if tail:
            items.append(tail)
    return items


def _repair_json_object(s: str) -> dict:
    inner = s.strip().strip("{}").strip()
    if not inner:
        return {}
    pairs = _split_json_items(inner)
    result = {}
    for pair in pairs:
        pair = pair.strip().strip(",")
        if not pair:
            continue
        if ":" not in pair:
            continue
        colon = pair.index(":")
        key = pair[:colon].strip().strip("'\"")
        val = pair[colon + 1:].strip()
        if val.startswith("{"):
            try:
                result[key] = json.loads(val)
            except json.JSONDecodeError:
                result[key] = _repair_json_object(val)
        elif val.startswith("["):
            try:
                result[key] = json.loads(val)
            except json.JSONDecodeError:
                result[key] = val.strip("[]").split(",")
        elif val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"
        elif val.lower() == "null":
            result[key] = None
        else:
            try:
                result[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                result[key] = val.strip("'\"")
    return result


def cmd_batch_search(args):
    """Execute multiple search queries in parallel (2-5 queries)."""
    query_items = getattr(args, "query_items", None) or []
    raw = args.queries or getattr(args, "queries_opt", None)

    if query_items:
        queries = [{"query": q} for q in query_items]
        if len(queries) > 5:
            print("Error: batch_search supports a maximum of 5 queries", file=sys.stderr)
            sys.exit(1)
    elif raw:
        if raw.startswith("@"):
            file_path = raw[1:]
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = f.read()
            except FileNotFoundError:
                print(f"Error: file not found: {file_path}", file=sys.stderr)
                sys.exit(1)
        try:
            queries = json.loads(raw)
            if not isinstance(queries, list):
                queries = [queries]
        except json.JSONDecodeError:
            queries = _repair_json(raw)
        if len(queries) < 1:
            print("Error: queries must contain at least 1 item", file=sys.stderr)
            sys.exit(1)
        if len(queries) > 5:
            print("Error: batch_search supports a maximum of 5 queries", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: provide --queries or --query", file=sys.stderr)
        sys.exit(1)

    # Inject shared params into each query item (item's own fields take precedence)
    shared_tag = getattr(args, "batch_tag", None)
    shared_domain = getattr(args, "batch_domain", None)
    shared_sub_domain = getattr(args, "batch_sub_domain", None)
    shared_sdp_raw = getattr(args, "batch_sdp", None)
    shared_sdp = _parse_sub_domain_params(shared_sdp_raw) if shared_sdp_raw else None
    shared_max_results = getattr(args, "batch_max_results", None)

    for item in queries:
        if shared_tag and not item.get("tag"):
            item["tag"] = shared_tag
        if shared_domain and not item.get("domain"):
            item["domain"] = shared_domain
        if shared_sub_domain and not item.get("sub_domain"):
            item["sub_domain"] = shared_sub_domain
        if shared_sdp and not item.get("sub_domain_params"):
            item["sub_domain_params"] = shared_sdp
        if shared_max_results is not None and item.get("max_results") is None:
            item["max_results"] = max(1, min(shared_max_results, 10))
        # Parse KV string params / sub_domain_params inside query items
        for key in ("params", "sub_domain_params"):
            if isinstance(item.get(key), str):
                item[key] = _parse_sub_domain_params(item[key])

    arguments = {"queries": queries}
    print(_call_api("batch_search", arguments, args.api_key))


# BEGIN GENERATED:DOC_SPEC
def _render_doc():
    import json as _json
    _dir = os.path.dirname(os.path.abspath(__file__))
    _shared = os.path.join(_dir, "shared")
    with open(os.path.join(_shared, "doc_spec.md"), "r", encoding="utf-8") as _f:
        _tpl = _f.read()
    with open(os.path.join(_shared, "constants.json"), "r", encoding="utf-8") as _f:
        _c = _json.load(_f)
    _tpl = _tpl.replace("{{LANG_NAME}}", "Python")
    _tpl = _tpl.replace("{{LANG_CODEBLOCK}}", "")
    _tpl = _tpl.replace("{{LANG_INVOKE}}", "python scripts/anysearch_cli.py")
    _tpl = _tpl.replace("{{DOMAINS_SPACE}}", " ".join(_c["available_domains"]))
    _tags = "\n".join("- " + _d + ": " + ", ".join(_c["available_tags"][_d]) for _d in _c["available_tags"])
    _tpl = _tpl.replace("{{TAGS_SPACE}}", _tags)
    return _tpl
# END GENERATED:DOC_SPEC


def cmd_doc(args):
    print(_render_doc())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anysearch",
        description=(
            "AnySearch CLI - Unified real-time search client.\n\n"
            "Supports general search, vertical domain search, batch search,\n"
            "domain directory lookup, and URL content extraction via the\n"
            "AnySearch JSON-RPC API."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  anysearch search "quantum computing"\n'
            '  anysearch search "AAPL" --tag finance.quote --params type=stock,symbol=AAPL,cn_code=\n'
            '  anysearch search "react hooks" --tag code.doc --params library=react\n'
            '  anysearch search "\u4eba\u5de5\u667a\u80fd \u65b0\u95fb" --zone cn --language zh-CN\n'
            '  anysearch get_sub_domains --domain finance\n'
            '  anysearch extract --url https://example.com\n'
            '  anysearch batch_search --queries \'[{"query":"AAPL"},{"query":"GOOG"}]\'\n'
        ),
    )

    parser.add_argument(
        "--api_key",
        default=os.environ.get("ANYSEARCH_API_KEY", ""),
        help="API key for authentication. Read from: --api_key > .env ANYSEARCH_API_KEY > env ANYSEARCH_API_KEY. "
        "Without a key, anonymous access is used with lower rate limits.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    search_p = subparsers.add_parser(
        "search",
        help="Search the web (general or vertical domain search)",
        description=(
            "Execute a search query via the REST /v1/search endpoint.\n\n"
            "Two modes:\n"
            "  General search:   omit --tag/--domain (open-ended natural language queries)\n"
            "  Vertical search:  specify --tag (e.g. finance.quote) with --params, or the\n"
            "                    legacy --domain + --sub_domain for structured queries\n\n"
            "For vertical search, run 'get_sub_domains' first to discover available\n"
            "sub_domains (they equal the valid --tag values) and their required params."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    search_p.add_argument("query", help="Search query string. For vertical search, follow the format returned by get_sub_domains.")
    search_p.add_argument(
        "--tag", "-t",
        help=(
            "Sub-domain capability tag '{domain}.{sub_domain}', e.g. code.doc, finance.quote. "
            "Routes the query to the vertical capability. "
            "Obtain valid tags via get_sub_domains (the backend validates the tag)."
        ),
    )
    search_p.add_argument(
        "--domain", "-d",
        choices=AVAILABLE_DOMAINS,
        help=(
            "Vertical domain for structured search (legacy alias of the domain part of --tag). "
            f"Available: {', '.join(AVAILABLE_DOMAINS)}"
        ),
    )
    search_p.add_argument(
        "--sub_domain", "-s",
        help="Sub-domain routing key (e.g. finance.quote). Legacy alias of --tag; obtain via get_sub_domains.",
    )
    search_p.add_argument(
        "--params", "--sub_domain_params", "--sdp", "-p",
        dest="params",
        help="Params for the tag schema as JSON or key=value pairs (e.g. type=stock,symbol=AAPL,cn_code=). Schema depends on the sub_domain (see get_sub_domains output).",
    )
    search_p.add_argument(
        "--zone",
        choices=["cn", "intl"],
        help="Region preference: cn or intl.",
    )
    search_p.add_argument(
        "--language",
        help="Preferred result language, e.g. zh-CN, en.",
    )
    search_p.add_argument(
        "--format",
        choices=["json", "markdown"],
        help="Output format: json (default) or markdown.",
    )
    search_p.add_argument(
        "--max_results", "-m",
        type=int,
        help="Maximum number of results to return (1-20, default 10).",
    )
    search_p.set_defaults(func=cmd_search)

    ld_p = subparsers.add_parser(
        "get_sub_domains",
        help="Query domain directory for available sub_domains",
        description=(
            "List available sub_domains, query formats, and parameter schemas\n"
            "for one or more vertical domains.\n\n"
            "MUST be called before performing vertical search to obtain\n"
            "the correct sub_domain value and query_format.\n\n"
            "Results are returned as a Markdown table with columns:\n"
            "domain, sub_domain, description, query_format, params_schema, zone."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ld_p.add_argument(
        "--domain",
        choices=AVAILABLE_DOMAINS,
        help="Single domain to query.",
    )
    ld_p.add_argument(
        "--domains",
        help=(
            "Batch query up to 5 domains. Comma-separated or JSON array.\n"
            f"Available: {', '.join(AVAILABLE_DOMAINS)}\n"
            "Takes precedence over --domain."
        ),
    )
    ld_p.set_defaults(func=cmd_get_sub_domains)

    ext_p = subparsers.add_parser(
        "extract",
        help="Fetch full page content from a URL",
        description=(
            "Extract the full content of a web page and return it as Markdown.\n\n"
            "Use this when search snippets are insufficient, you need to verify\n"
            "data, or want to extract structured content (tables, code, etc.).\n\n"
            "Note: Output is truncated at 50,000 characters. Only HTML pages\n"
            "are supported (not PDFs, images, etc.)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ext_p.add_argument("url", nargs="?", help="Target URL to extract content from (http(s)://).")
    ext_p.add_argument("--url", "-u", dest="url_opt", help="Target URL to extract content from (alternative to positional arg).")
    ext_p.set_defaults(func=cmd_extract)

    batch_p = subparsers.add_parser(
        "batch_search",
        help="Execute 2-5 search queries in parallel",
        description=(
            "Run multiple independent search queries in a single API call.\n"
            "Each query follows the same parameter structure as the 'search' command.\n"
            "A single query failure does not block others; results are merged.\n\n"
            "Queries are provided as a JSON array of objects. Each object supports\n"
            "the same fields as 'search': query, domain, sub_domain, max_results."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  anysearch batch_search --query AAPL --query GOOG\n'
            '  anysearch batch_search --queries \'[{\"query\":\"AAPL\"},{\"query\":\"GOOG\"}]\'\n'
            '  anysearch batch_search \'[{\"query\":\"AAPL\"},{\"query\":\"GOOG\"}]\'\n'
            '  anysearch batch_search --queries @queries.json\n'
        ),
    )
    batch_p.add_argument(
        "queries",
        nargs="?",
        help=(
            'JSON array of search query objects (1-5 items). '
            'Tolerates PowerShell quote-stripping automatically.\n'
            'Each object supports: query (required), domain, sub_domain, sub_domain_params, max_results.\n'
            'Example: \'[{"query":"AAPL"},{"query":"GOOG"}]\''
        ),
    )
    batch_p.add_argument(
        "--queries", "-q", dest="queries_opt",
        help="JSON array of search query objects (alternative to positional arg). Prefix @ to read from file.",
    )
    batch_p.add_argument(
        "--query",
        action="append",
        dest="query_items",
        help="Shorthand: repeatable single-query string. Easier for PowerShell. Up to 5.",
    )
    batch_p.add_argument(
        "--tag", "-t",
        dest="batch_tag",
        help="Shared tag injected into all query items (item's own tag/domain takes precedence).",
    )
    batch_p.add_argument(
        "--domain", "-d",
        dest="batch_domain",
        choices=AVAILABLE_DOMAINS,
        help="Shared domain injected into all query items (item's own domain takes precedence).",
    )
    batch_p.add_argument(
        "--sub_domain", "-s",
        dest="batch_sub_domain",
        help="Shared sub_domain injected into all query items (item's own sub_domain takes precedence).",
    )
    batch_p.add_argument(
        "--params", "--sub_domain_params", "--sdp", "-p",
        dest="batch_sdp",
        help="Shared params as JSON or key=value pairs, injected into all query items.",
    )
    batch_p.add_argument(
        "--max_results", "-m",
        dest="batch_max_results",
        type=int,
        help="Shared max results (1-10) injected into all query items (item's own max_results takes precedence).",
    )
    batch_p.set_defaults(func=cmd_batch_search)

    doc_p = subparsers.add_parser(
        "doc",
        help="Print AI-facing interface specification",
    )
    doc_p.set_defaults(func=cmd_doc)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        print(_render_doc())
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()

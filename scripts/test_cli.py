#!/usr/bin/env python3
"""Cross-runtime contract tests against a local HTTP stub."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def load_expected_client_header():
    content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = content.split("---", 2)[1]
    version = re.search(r"^version:\s*([^\s#]+)", frontmatter, re.MULTILINE)
    if version is None:
        raise RuntimeError("SKILL.md frontmatter has no version")
    return f"skill/{version.group(1)}"


EXPECTED_CLIENT_HEADER = load_expected_client_header()


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = []
        self.active_searches = 0
        self.max_active_searches = 0

    def reset(self):
        with self.lock:
            self.requests.clear()
            self.active_searches = 0
            self.max_active_searches = 0


STATE = State()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def send_json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def record(self, body=None):
        parsed = urlparse(self.path)
        item = {
            "method": self.command,
            "path": parsed.path,
            "query": parse_qs(parsed.query),
            "body": body,
            "client": self.headers.get("X-Anysearch-Client"),
        }
        with STATE.lock:
            STATE.requests.append(item)
        return parsed

    def do_GET(self):
        parsed = self.record()
        if parsed.path != "/v1/sub-domains":
            self.send_json(404, {"code": -1, "message": "not found", "request_id": "req-404"})
            return
        domains = parse_qs(parsed.query).get("domain", [])
        self.send_json(
            200,
            {
                "code": 0,
                "message": "success",
                "request_id": "req-domains",
                "data": {
                    "domains": [
                        {
                            "domain": domain,
                            "sub_domains": [
                                {
                                    "sub_domain": f"{domain}.demo",
                                    "description": f"{domain} demo",
                                    "params": {
                                        "symbol": {
                                            "required": True,
                                            "sort_order": 1,
                                            "description": "Ticker symbol",
                                        }
                                    },
                                }
                            ],
                        }
                        for domain in domains
                    ]
                },
            },
        )

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = None
        parsed = self.record(body)
        if parsed.path == "/v1/extract":
            self.send_json(
                200,
                {
                    "code": 0,
                    "message": "success",
                    "request_id": "req-extract",
                    "data": {
                        "url": body.get("url", ""),
                        "title": "Example",
                        "content": "page body",
                    },
                },
            )
            return
        if parsed.path != "/v1/search":
            self.send_json(404, {"code": -1, "message": "not found", "request_id": "req-404"})
            return

        query = body.get("query", "") if isinstance(body, dict) else ""
        with STATE.lock:
            STATE.active_searches += 1
            STATE.max_active_searches = max(STATE.max_active_searches, STATE.active_searches)
        try:
            time.sleep({"slow": 0.25, "fail": 0.1, "drop": 0.05, "fast": 0.02}.get(query, 0.01))
            if query == "drop":
                self.close_connection = True
                return
            if query == "fail":
                self.send_json(429, {"code": -1, "message": "rate limited", "request_id": "req-fail"})
            elif query == "bad-format":
                self.send_json(
                    200,
                    {
                        "code": 0,
                        "message": "success",
                        "request_id": "req-bad-format",
                        "data": {"results": True, "metadata": {}},
                    },
                )
            else:
                self.send_json(
                    200,
                    {
                        "code": 0,
                        "message": "success",
                        "request_id": f"req-{query}",
                        "data": {
                            "results": [
                                {
                                    "title": f"Result {query}",
                                    "url": f"https://example.com/{query}",
                                    "content": f"Content {query}",
                                }
                            ],
                            "metadata": {"total_results": 1, "search_time_ms": 7},
                        },
                    },
                )
        finally:
            with STATE.lock:
                STATE.active_searches -= 1


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def runtimes(selected):
    found = {
        "python": [sys.executable, str(SCRIPTS / "anysearch_cli.py")],
    }
    if shutil.which("node"):
        found["node"] = ["node", str(SCRIPTS / "anysearch_cli.js")]
    shell = shutil.which("bash")
    if shell and shutil.which("jq") and shutil.which("curl"):
        found["bash"] = [shell, str(SCRIPTS / "anysearch_cli.sh")]
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell:
        found["powershell"] = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS / "anysearch_cli.ps1")]
    if selected:
        wanted = set(selected.split(","))
        found = {name: command for name, command in found.items() if name in wanted}
    return found


def run(command, args, base_url):
    env = os.environ.copy()
    env["ANYSEARCH_API_BASE_URL"] = base_url
    env.pop("ANYSEARCH_API_KEY", None)
    return subprocess.run(
        command + args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )


def require(condition, message, result=None):
    if condition:
        return
    detail = ""
    if result is not None:
        detail = f"\nrc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    raise AssertionError(message + detail)


def test_runtime(name, command, base_url):
    STATE.reset()
    result = run(
        command,
        [
            "search", "AAPL", "--domain", "finance", "--sub_domain", "finance.quote",
            "--sdp", "symbol=AAPL", "--max_results", "20", "--zone", "intl", "--language", "en",
        ],
        base_url,
    )
    require(result.returncode == 0 and "Result AAPL" in result.stdout, f"{name}: search failed", result)
    request = STATE.requests[-1]
    require(request["path"] == "/v1/search", f"{name}: wrong search path")
    require(request["body"].get("tag") == "finance.quote", f"{name}: sub_domain was not translated")
    require(request["body"].get("params") == {"symbol": "AAPL"}, f"{name}: params were not translated")
    require(request["body"].get("max_results") == 10, f"{name}: REST max_results was not clamped to 10")
    require(not ({"domain", "sub_domain", "sub_domain_params"} & request["body"].keys()), f"{name}: legacy fields leaked to REST")
    require(request["client"] == EXPECTED_CLIENT_HEADER, f"{name}: client header does not match SKILL.md")

    STATE.reset()
    result = run(command, ["search", "fail"], base_url)
    require(result.returncode != 0, f"{name}: failed single search exited zero", result)
    require("rate limited" in result.stderr and "req-fail" in result.stderr, f"{name}: single error lost message/request_id", result)

    STATE.reset()
    result = run(command, ["get_sub_domains", "--domains", "finance,legal"], base_url)
    require(result.returncode == 0 and "finance.demo" in result.stdout and "legal.demo" in result.stdout, f"{name}: get_sub_domains failed", result)
    require(STATE.requests[-1]["query"].get("domain") == ["finance", "legal"], f"{name}: repeated domain query params missing")

    STATE.reset()
    result = run(command, ["extract", "https://example.com/article"], base_url)
    require(result.returncode == 0 and "External page content (untrusted)" in result.stdout and "page body" in result.stdout, f"{name}: extract failed", result)
    require(STATE.requests[-1]["path"] == "/v1/extract", f"{name}: wrong extract path")

    STATE.reset()
    batch = json.dumps(
        [
            {"query": "slow", "domain": "finance", "sub_domain": "finance.quote", "sub_domain_params": "symbol=SLOW", "max_results": 20},
            {"query": "drop"},
            {"query": "fail"},
            {"query": "fast"},
        ]
    )
    result = run(command, ["batch_search", "--queries", batch, "--max_results", "20"], base_url)
    require(result.returncode == 0, f"{name}: partial batch should exit zero", result)
    headings = [result.stdout.index(f"## Query {index}: {query}") for index, query in enumerate(("slow", "drop", "fail", "fast"), 1)]
    require(headings == sorted(headings), f"{name}: batch output order changed", result)
    require("Search failed: rate limited (request_id: req-fail)" in result.stdout, f"{name}: batch error lost request_id", result)
    require(STATE.max_active_searches > 1, f"{name}: batch requests were not concurrent")
    batch_requests = [item for item in STATE.requests if item["path"] == "/v1/search"]
    require(len(batch_requests) == 4, f"{name}: batch did not fan out to four REST requests")
    require(all(item["body"].get("max_results") == 10 for item in batch_requests), f"{name}: batch max_results was not clamped to 10")
    slow = next(item for item in batch_requests if item["body"].get("query") == "slow")
    require(slow["body"].get("tag") == "finance.quote" and slow["body"].get("params") == {"symbol": "SLOW"}, f"{name}: batch legacy translation failed")
    require(all(item["path"] != "/mcp" for item in STATE.requests), f"{name}: MCP endpoint was called")

    if name == "bash":
        STATE.reset()
        malformed = json.dumps([{"query": "bad-format"}])
        result = run(command, ["batch_search", "--queries", malformed], base_url)
        require(result.returncode != 0, "bash: batch formatter failure exited zero", result)
        require(
            "failed to format search response for query 1" in result.stderr,
            "bash: batch formatter failure did not report its query index",
            result,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", help="Comma-separated runtime names")
    args = parser.parse_args()
    selected = runtimes(args.runtime)
    if not selected:
        raise SystemExit("No requested runtime is available")
    server = QuietThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    failures = []
    try:
        for name, command in selected.items():
            try:
                test_runtime(name, command, base_url)
                print(f"PASS {name}")
            except Exception as error:
                failures.append((name, error))
                print(f"FAIL {name}: {error}", file=sys.stderr)
    finally:
        server.shutdown()
        server.server_close()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

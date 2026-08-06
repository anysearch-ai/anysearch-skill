#!/usr/bin/env python3
"""Integration and regression tests for the AnySearch CLI scripts.

Covers all four bundled runtimes (Python / Node.js / Bash, plus Windows
PowerShell when reachable) against both the REST /v1/search endpoint
(`search` command) and the MCP /mcp endpoint (batch_search / extract /
get_sub_domains).

Usage:
    python3 scripts/test_cli.py            # full suite (needs network)
    python3 scripts/test_cli.py --offline  # only offline checks (doc/help/args)
    python3 scripts/test_cli.py --runtime python,node   # pick runtimes

Exit code 0 when every enabled check passes; 1 otherwise.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(SKILL_DIR, "scripts")

RESULTS = []  # (runtime, check, ok, detail)


def build_runtimes():
    """Detect available CLIs in the documented priority order."""
    runtimes = {}

    if shutil.which("node"):
        runtimes["node"] = ["node", os.path.join(SCRIPT_DIR, "anysearch_cli.js")]
    if shutil.which("bash") and shutil.which("jq") and shutil.which("curl"):
        runtimes["bash"] = ["bash", os.path.join(SCRIPT_DIR, "anysearch_cli.sh")]
    # Windows PowerShell via WSL interop
    for cand in ("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",):
        if os.path.isfile(cand):
            runtimes["powershell"] = [
                cand, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", os.path.join(SCRIPT_DIR, "anysearch_cli.ps1"),
            ]
    # Python last so it can be the default even when other probes exist;
    # detection priority is Python > Node > Shell, so the suite tests Python first.
    runtimes["python"] = [sys.executable, os.path.join(SCRIPT_DIR, "anysearch_cli.py")]

    # Reorder: python first (reference implementation), then node, bash, powershell
    ordered = {k: runtimes[k] for k in ("python", "node", "bash", "powershell") if k in runtimes}
    return ordered


def run_cli(cmd, args, timeout=90):
    """Run a CLI command; return (exit_code, stdout, stderr)."""
    env = dict(os.environ)
    try:
        proc = subprocess.run(
            cmd + args, capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except OSError as e:
        return -1, "", f"OSError: {e}"


def parse_json_stdout(stdout):
    """Best-effort JSON parse of CLI stdout (skips leading non-JSON lines)."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def check(runtime, name, ok, detail=""):
    RESULTS.append((runtime, name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {runtime:10s} {name}{'  -- ' + detail if detail and not ok else ''}")


# ---------------------------------------------------------------------------
# Offline checks
# ---------------------------------------------------------------------------

def test_doc(cmd, runtime):
    rc, out, err = run_cli(cmd, ["doc"])
    check(runtime, "doc exits 0", rc == 0, f"rc={rc} err={err[:200]}")
    if rc == 0:
        check(runtime, "doc has no {{ placeholders", "{{" not in out)
        check(runtime, "doc documents REST /v1/search", "REST" in out and "/v1/search" in out)
        check(runtime, "doc documents --tag", "--tag" in out)
        check(runtime, "doc documents --zone/--language/--format",
              "--zone" in out and "--language" in out and "--format" in out)
        check(runtime, "doc lists domains", "finance" in out and "general" in out)


def test_arg_errors(cmd, runtime):
    rc, out, err = run_cli(cmd, ["search", "--max_results", "3"])  # missing query
    check(runtime, "search without query fails", rc != 0, f"rc={rc}")
    rc, out, err = run_cli(cmd, ["search", "x", "--bogus_flag", "1"])
    check(runtime, "unknown flag fails", rc != 0, f"rc={rc}")
    rc, out, err = run_cli(cmd, ["frobnicate"])
    check(runtime, "unknown command fails", rc != 0, f"rc={rc}")


# ---------------------------------------------------------------------------
# Online checks (REST /v1/search)
# ---------------------------------------------------------------------------

def test_search_general(cmd, runtime):
    rc, out, err = run_cli(cmd, ["search", "quantum computing", "--max_results", "3"])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0 and data.get("data", {}).get("results")
    check(runtime, "search general", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")
    if ok:
        check(runtime, "search general has metadata",
              "metadata" in data["data"] and "total_results" in data["data"]["metadata"])


def test_search_tag_params(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "search", "AAPL", "--tag", "finance.quote",
        "--params", "type=stock,symbol=AAPL,cn_code=", "--max_results", "2",
    ])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0 and data.get("data", {}).get("results")
    check(runtime, "search --tag + --params", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")
    if ok:
        titles = " ".join(r["title"] for r in data["data"]["results"]).upper()
        check(runtime, "search tag routes to vertical (AAPL)", "AAPL" in titles,
              titles[:120])


def test_search_tag_params_json(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "search", "react hooks", "--tag", "code.doc",
        "--params", '{"library":"react"}', "--max_results", "1",
    ])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0 and data.get("data", {}).get("results")
    check(runtime, "search --params as JSON", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_search_legacy_style(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "search", "MSFT", "--domain", "finance", "--sub_domain", "finance.quote",
        "--sdp", "type=stock,symbol=MSFT,cn_code=", "--max_results", "1",
    ])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0
    check(runtime, "search legacy --domain/--sub_domain/--sdp", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_search_zone_language(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "search", "人工智能 新闻", "--zone", "cn", "--language", "zh-CN",
        "--max_results", "1",
    ])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0
    check(runtime, "search --zone + --language", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_search_format_markdown(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "search", "go 1.26", "--format", "markdown", "--max_results", "1",
    ])
    data = parse_json_stdout(out)
    ok = rc == 0 and data and data.get("code") == 0
    md = ""
    if ok and data.get("data", {}).get("results"):
        md = data["data"]["results"][0].get("content", "")
    check(runtime, "search --format markdown", bool(ok) and ("#" in md or "**" in md),
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_search_max_results_20(cmd, runtime):
    total = 0
    err = ""
    # Short queries occasionally return fewer results from the backend; retry
    # with a fuller query. The point is to prove the CLI does NOT clamp to the
    # old MCP cap of 10 (REST accepts up to 20).
    for _ in range(2):
        rc, out, err = run_cli(cmd, ["search", "go programming language", "--max_results", "20"])
        data = parse_json_stdout(out)
        total = 0
        if rc == 0 and data and data.get("code") == 0:
            total = data.get("data", {}).get("metadata", {}).get("total_results", 0)
        if total > 10:
            break
    check(runtime, "search --max_results 20 (no 10-cap)", total > 10, f"total={total} rc={rc} err={err[:150]}")


def test_search_error_missing_param(cmd, runtime):
    rc, out, err = run_cli(cmd, ["search", "go", "--tag", "code.doc"])
    ok = rc != 0 and "Missing required params" in err
    check(runtime, "missing required param errors", ok,
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_search_error_invalid_tag(cmd, runtime):
    rc, out, err = run_cli(cmd, ["search", "go", "--tag", "not.a.tag"])
    ok = rc != 0 and ("invalid choice" in err or "Invalid tag" in err)
    check(runtime, "invalid tag errors", ok, f"rc={rc} err={err[:150]}" if not ok else "")


# ---------------------------------------------------------------------------
# Online checks (MCP /mcp)
# ---------------------------------------------------------------------------

def test_get_sub_domains(cmd, runtime):
    rc, out, err = run_cli(cmd, ["get_sub_domains", "--domain", "finance"])
    ok = rc == 0 and "finance.quote" in out and "Parameters" in out
    check(runtime, "get_sub_domains --domain", ok, f"rc={rc} err={err[:150]}" if not ok else "")
    rc, out, err = run_cli(cmd, ["get_sub_domains", "--domains", "finance,code"])
    check(runtime, "get_sub_domains --domains", rc == 0 and "code.doc" in out,
          f"rc={rc} err={err[:150]}" if rc != 0 else "")


def test_batch_search(cmd, runtime):
    rc, out, err = run_cli(cmd, [
        "batch_search", "--query", "AAPL", "--query", "MSFT",
        "--tag", "finance.quote", "--params", "type=stock,symbol=,cn_code=",
        "--max_results", "1",
    ])
    ok = rc == 0 and "Query 1" in out and "Query 2" in out and "AAPL" in out.upper() or "APPLE" in out.upper()
    check(runtime, "batch_search shared --tag/--params", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")

    rc, out, err = run_cli(cmd, [
        "batch_search",
        "--queries", '[{"query":"react hooks","tag":"code.doc","params":"library=react"}]',
        "--max_results", "1",
    ])
    ok = rc == 0 and "### 1" in out and ("React" in out or "react" in out)
    check(runtime, "batch_search per-item tag+params", bool(ok),
          f"rc={rc} err={err[:150]}" if not ok else "")


def test_extract(cmd, runtime):
    rc, out, err = run_cli(cmd, ["extract", "https://example.com"])
    check(runtime, "extract page", rc == 0 and "Example Domain" in out,
          f"rc={rc} err={err[:150]}" if rc != 0 else "")


# ---------------------------------------------------------------------------
# Offline-only: generated scripts in sync
# ---------------------------------------------------------------------------

def test_generated_sync():
    rc, out, err = run_cli([sys.executable, os.path.join(SCRIPT_DIR, "generate.py")], ["--check"])
    check("generate", "generate.py --check (no drift)", rc == 0, out + err)


def main():
    ap = argparse.ArgumentParser(description="AnySearch CLI test suite")
    ap.add_argument("--offline", action="store_true", help="only offline checks")
    ap.add_argument("--runtime", default="", help="comma-separated runtimes to test")
    args = ap.parse_args()

    runtimes = build_runtimes()
    selected = [r.strip() for r in args.runtime.split(",") if r.strip()]
    if selected:
        runtimes = {k: v for k, v in runtimes.items() if k in selected}

    print(f"Runtimes under test: {', '.join(runtimes) or '(none)'}")
    print(f"Skill dir: {SKILL_DIR}")
    print(f"API key present: {'YES' if os.environ.get('ANYSEARCH_API_KEY') else 'no (anonymous)'}\n")

    for name, cmd in runtimes.items():
        print(f"--- {name} ---")
        test_doc(cmd, name)
        test_arg_errors(cmd, name)
        if not args.offline:
            test_search_general(cmd, name)
            test_search_tag_params(cmd, name)
            test_search_tag_params_json(cmd, name)
            test_search_legacy_style(cmd, name)
            test_search_zone_language(cmd, name)
            test_search_format_markdown(cmd, name)
            test_search_max_results_20(cmd, name)
            test_search_error_missing_param(cmd, name)
            test_search_error_invalid_tag(cmd, name)
            test_get_sub_domains(cmd, name)
            test_batch_search(cmd, name)
            test_extract(cmd, name)

    test_generated_sync()

    failed = [r for r in RESULTS if not r[2]]
    print(f"\n===== {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed =====")
    if failed:
        print("Failed checks:")
        for runtime, name, ok, detail in failed:
            print(f"  - {runtime}: {name}  ({detail})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

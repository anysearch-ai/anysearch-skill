#!/usr/bin/env python3
"""Code generator for AnySearch CLI scripts.

Reads shared data from scripts/shared/ and injects it into each CLI script,
replacing content between marker comments. This eliminates duplication of
constants (domains, content_types, etc.) and the doc spec across all 4
language implementations.

Usage:
    python scripts/generate.py          # Generate all scripts
    python scripts/generate.py --check  # Verify scripts are up-to-date (for CI)
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(SCRIPT_DIR, "shared")

# --- Marker format per language ---
# Each script uses paired comments to delimit generated sections:
#   BEGIN GENERATED:<section_name>
#   ... generated content ...
#   END GENERATED:<section_name>

MARKERS = {
    ".py": ("# BEGIN GENERATED:{name}", "# END GENERATED:{name}"),
    ".js": ("// BEGIN GENERATED:{name}", "// END GENERATED:{name}"),
    ".ps1": ("# BEGIN GENERATED:{name}", "# END GENERATED:{name}"),
    ".sh": ("# BEGIN GENERATED:{name}", "# END GENERATED:{name}"),
}

# --- Language-specific config for doc_spec template ---
LANG_CONFIG = {
    ".py": {
        "LANG_NAME": "Python",
        "LANG_CODEBLOCK": "",
        "LANG_INVOKE": "python scripts/anysearch_cli.py",
    },
    ".js": {
        "LANG_NAME": "Node.js",
        "LANG_CODEBLOCK": "",
        "LANG_INVOKE": "node scripts/anysearch_cli.js",
    },
    ".ps1": {
        "LANG_NAME": "PowerShell",
        "LANG_CODEBLOCK": "powershell",
        "LANG_INVOKE": "powershell -ExecutionPolicy Bypass -File scripts/anysearch_cli.ps1",
    },
    ".sh": {
        "LANG_NAME": "Bash",
        "LANG_CODEBLOCK": "bash",
        "LANG_INVOKE": "bash scripts/anysearch_cli.sh",
    },
}


def load_constants():
    with open(os.path.join(SHARED_DIR, "constants.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_doc_template():
    with open(os.path.join(SHARED_DIR, "doc_spec.md"), "r", encoding="utf-8") as f:
        return f.read()


def render_doc_spec(template, ext, constants):
    """Render doc_spec.md template with language-specific and constant values."""
    config = LANG_CONFIG[ext]
    result = template
    for key, val in config.items():
        result = result.replace("{{" + key + "}}", val)
    result = result.replace("{{DOMAINS_SPACE}}", " ".join(constants["available_domains"]))
    result = result.replace("{{CONTENT_TYPES_SPACE}}", " ".join(constants["content_types"]))
    return result


def render_constants(ext, constants):
    """Render constants block in the target language syntax."""
    domains = constants["available_domains"]
    content_types = constants["content_types"]
    freshness = constants["freshness_values"]
    zones = constants["zones"]

    if ext == ".py":
        lines = []
        lines.append("AVAILABLE_DOMAINS = [")
        # Format in rows of ~6 items
        for i in range(0, len(domains), 6):
            chunk = domains[i:i+6]
            lines.append("    " + ", ".join(f'"{d}"' for d in chunk) + ",")
        lines.append("]")
        lines.append("")
        lines.append("CONTENT_TYPES = [")
        lines.append("    " + ", ".join(f'"{c}"' for c in content_types) + ",")
        lines.append("]")
        lines.append("")
        lines.append("FRESHNESS_VALUES = [" + ", ".join(f'"{f}"' for f in freshness) + "]")
        lines.append("ZONES = [" + ", ".join(f'"{z}"' for z in zones) + "]")
        return "\n".join(lines)

    elif ext == ".js":
        lines = []
        lines.append("const AVAILABLE_DOMAINS = [")
        for i in range(0, len(domains), 6):
            chunk = domains[i:i+6]
            lines.append("  " + ",".join(f'"{d}"' for d in chunk) + ",")
        lines.append("];")
        lines.append("")
        lines.append("const CONTENT_TYPES = [")
        lines.append("  " + ",".join(f'"{c}"' for c in content_types) + ",")
        lines.append("];")
        lines.append("")
        lines.append("const FRESHNESS_VALUES = [" + ",".join(f'"{f}"' for f in freshness) + "];")
        lines.append("const ZONES = [" + ",".join(f'"{z}"' for z in zones) + "];")
        return "\n".join(lines)

    elif ext == ".ps1":
        lines = []
        lines.append("$AVAILABLE_DOMAINS = @(")
        chunks = [domains[i:i+6] for i in range(0, len(domains), 6)]
        for idx, chunk in enumerate(chunks):
            suffix = "," if idx < len(chunks) - 1 else ""
            lines.append("    " + ", ".join(f'"{d}"' for d in chunk) + suffix)
        lines.append(")")
        lines.append("")
        lines.append("$CONTENT_TYPES = @(" + ", ".join(f'"{c}"' for c in content_types) + ")")
        lines.append("$FRESHNESS_VALUES = @(" + ", ".join(f'"{f}"' for f in freshness) + ")")
        lines.append("$ZONES = @(" + ", ".join(f'"{z}"' for z in zones) + ")")
        return "\n".join(lines)

    elif ext == ".sh":
        lines = []
        lines.append("AVAILABLE_DOMAINS=(" + " ".join(f'"{d}"' for d in domains) + ")")
        lines.append("CONTENT_TYPES=(" + " ".join(f'"{c}"' for c in content_types) + ")")
        lines.append("FRESHNESS_VALUES=(" + " ".join(f'"{f}"' for f in freshness) + ")")
        lines.append("ZONES=(" + " ".join(f'"{z}"' for z in zones) + ")")
        return "\n".join(lines)


def render_doc_block(ext, _doc_text=None):
    """Generate code that reads and renders doc_spec.md at runtime."""
    if ext == ".py":
        return '''def _render_doc():
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
    _tpl = _tpl.replace("{{CONTENT_TYPES_SPACE}}", " ".join(_c["content_types"]))
    return _tpl'''

    elif ext == ".js":
        return '''function renderDoc() {
  const shared = path.join(__dirname, "shared");
  let tpl = fs.readFileSync(path.join(shared, "doc_spec.md"), "utf-8");
  const c = JSON.parse(fs.readFileSync(path.join(shared, "constants.json"), "utf-8"));
  tpl = tpl.replace(/\\{\\{LANG_NAME\\}\\}/g, "Node.js");
  tpl = tpl.replace(/\\{\\{LANG_CODEBLOCK\\}\\}/g, "");
  tpl = tpl.replace(/\\{\\{LANG_INVOKE\\}\\}/g, "node scripts/anysearch_cli.js");
  tpl = tpl.replace(/\\{\\{DOMAINS_SPACE\\}\\}/g, c.available_domains.join(" "));
  tpl = tpl.replace(/\\{\\{CONTENT_TYPES_SPACE\\}\\}/g, c.content_types.join(" "));
  return tpl;
}'''

    elif ext == ".ps1":
        return '''function Render-Doc {
    $shared = Join-Path (Split-Path -Parent $MyInvocation.ScriptName) "shared"
    $tpl = Get-Content (Join-Path $shared "doc_spec.md") -Raw -Encoding UTF8
    $c = Get-Content (Join-Path $shared "constants.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $tpl = $tpl.Replace("{{LANG_NAME}}", "PowerShell")
    $tpl = $tpl.Replace("{{LANG_CODEBLOCK}}", "powershell")
    $tpl = $tpl.Replace("{{LANG_INVOKE}}", "powershell -ExecutionPolicy Bypass -File scripts/anysearch_cli.ps1")
    $tpl = $tpl.Replace("{{DOMAINS_SPACE}}", ($c.available_domains -join " "))
    $tpl = $tpl.Replace("{{CONTENT_TYPES_SPACE}}", ($c.content_types -join " "))
    return $tpl
}'''

    elif ext == ".sh":
        return '''_cmd_doc() {
  local shared="$SCRIPT_DIR/shared"
  local tpl
  tpl=$(cat "$shared/doc_spec.md")
  local domains
  domains=$(jq -r '.available_domains | join(" ")' "$shared/constants.json")
  local ctypes
  ctypes=$(jq -r '.content_types | join(" ")' "$shared/constants.json")
  tpl="${tpl//\\{\\{LANG_NAME\\}\\}/Bash}"
  tpl="${tpl//\\{\\{LANG_CODEBLOCK\\}\\}/bash}"
  tpl="${tpl//\\{\\{LANG_INVOKE\\}\\}/bash scripts/anysearch_cli.sh}"
  tpl="${tpl//\\{\\{DOMAINS_SPACE\\}\\}/$domains}"
  tpl="${tpl//\\{\\{CONTENT_TYPES_SPACE\\}\\}/$ctypes}"
  printf '%s\\n' "$tpl"
}'''


def inject_generated(source, ext, section_name, content):
    """Replace content between markers in source file."""
    begin_marker = MARKERS[ext][0].format(name=section_name)
    end_marker = MARKERS[ext][1].format(name=section_name)

    begin_idx = source.find(begin_marker)
    end_idx = source.find(end_marker)

    if begin_idx == -1 or end_idx == -1:
        return None  # Markers not found

    # Preserve the line with the begin marker and the line with the end marker
    after_begin = source.index("\n", begin_idx) + 1
    return source[:after_begin] + content + "\n" + source[end_idx:]


def process_file(filepath, constants, doc_template, check_only=False):
    """Process a single CLI script file."""
    ext = os.path.splitext(filepath)[1]
    if ext not in MARKERS:
        return True

    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    source = original

    # Inject constants
    constants_content = render_constants(ext, constants)
    result = inject_generated(source, ext, "CONSTANTS", constants_content)
    if result is not None:
        source = result

    # Inject doc spec (runtime reader code)
    doc_block = render_doc_block(ext, None)
    result = inject_generated(source, ext, "DOC_SPEC", doc_block)
    if result is not None:
        source = result

    if source == original:
        print(f"  {os.path.basename(filepath)}: up to date")
        return True

    if check_only:
        if source != original:
            print(f"  {os.path.basename(filepath)}: OUT OF DATE")
            return False
        print(f"  {os.path.basename(filepath)}: up to date")
        return True

    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(source)
    print(f"  {os.path.basename(filepath)}: updated")
    return True


def main():
    check_only = "--check" in sys.argv

    print("Loading shared data...")
    constants = load_constants()
    doc_template = load_doc_template()

    print(f"  Domains: {len(constants['available_domains'])}")
    print(f"  Content types: {len(constants['content_types'])}")

    scripts = [
        os.path.join(SCRIPT_DIR, "anysearch_cli.py"),
        os.path.join(SCRIPT_DIR, "anysearch_cli.js"),
        os.path.join(SCRIPT_DIR, "anysearch_cli.ps1"),
        os.path.join(SCRIPT_DIR, "anysearch_cli.sh"),
    ]

    print("\nProcessing scripts...")
    all_ok = True
    for script in scripts:
        if not os.path.isfile(script):
            print(f"  {os.path.basename(script)}: NOT FOUND")
            all_ok = False
            continue
        if not process_file(script, constants, doc_template, check_only):
            all_ok = False

    if check_only and not all_ok:
        print("\nFAILED: Generated files are out of date. Run: python scripts/generate.py")
        sys.exit(1)
    elif check_only:
        print("\nOK: All generated files are up to date.")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()

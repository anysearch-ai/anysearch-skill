#!/usr/bin/env python3
"""Code generator for AnySearch CLI scripts.

Reads the skill version from SKILL.md and shared data from scripts/shared/, then
injects the client header, API base URL, domain list, and doc command
implementation into each CLI script. It also keeps the pinned version references
in README.md / README_zh.md in sync and regenerates SHA256SUMS.txt, so the skill
version only has to be edited in one place.

Usage:
    python scripts/generate.py                 # Regenerate all generated files
    python scripts/generate.py --check         # Verify generated files are up-to-date (for CI)
    python scripts/generate.py --bump 3.2.0    # Update SKILL.md, then regenerate everything
"""

import hashlib
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(SCRIPT_DIR, "shared")
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
SKILL_PATH = os.path.join(ROOT_DIR, "SKILL.md")
README_FILES = ("README.md", "README_zh.md")
SUMS_FILENAME = "SHA256SUMS.txt"

SEMVER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"

# Version references in the READMEs are pinned release examples. Rewrite the
# version only in these known contexts so unrelated semver-looking strings
# (Python 3.11.9, Node v24.14.0, JSON payload versions) are left alone.
README_VERSION_PATTERNS = (
    # https://github.com/.../archive/refs/tags/vX.Y.Z.zip
    (r"(refs/tags/v)" + SEMVER, r"\g<1>{version}"),
    # anysearch-skill-X.Y.Z (unzip output and mv source directory names)
    (r"(anysearch-skill-)" + SEMVER, r"\g<1>{version}"),
    # `vX.Y.Z` (backticked hand-off mentions, e.g. "replace `v3.1.1`")
    (r"(`v)" + SEMVER + r"(`)", r"\g<1>{version}\g<2>"),
    # "Replace vX.Y.Z with the latest tag" (English README)
    (r"((?:R|r)eplace v)" + SEMVER, r"\g<1>{version}"),
    # "请将 vX.Y.Z 替换为最新 tag" (Chinese README)
    (r"((?:请将|将) v)" + SEMVER, r"\g<1>{version}"),
)

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


def load_constants():
    with open(os.path.join(SHARED_DIR, "constants.json"), "r", encoding="utf-8") as f:
        constants = json.load(f)
    constants["skill_version"] = load_skill_version()
    return constants


def load_skill_version():
    """Read and validate the version from the SKILL.md frontmatter."""
    with open(SKILL_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("SKILL.md must start with YAML frontmatter")

    matches = re.findall(r"^version:\s*([^\s#]+)\s*(?:#.*)?$", parts[1], re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("SKILL.md frontmatter must contain exactly one version")

    version = matches[0]
    if not re.fullmatch(SEMVER, version):
        raise ValueError(f"Invalid SKILL.md version: {version}")
    return version


def bump_skill_version(version):
    """Rewrite the SKILL.md frontmatter version."""
    if not re.fullmatch(SEMVER, version):
        raise ValueError(f"Invalid version: {version}")

    with open(SKILL_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("SKILL.md must start with YAML frontmatter")

    new_frontmatter, count = re.subn(
        r"^version:\s*[^\s#]+\s*$", f"version: {version}", parts[1], flags=re.MULTILINE
    )
    if count != 1:
        raise ValueError("SKILL.md frontmatter must contain exactly one version")

    content = "---".join((parts[0], new_frontmatter, parts[2]))
    with open(SKILL_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def render_readme(content, version, name):
    """Rewrite pinned version references in a README without touching other semver."""
    total = 0
    for pattern, replacement in README_VERSION_PATTERNS:
        content, count = re.subn(pattern, replacement.format(version=version), content)
        total += count
    if total == 0:
        raise ValueError(f"{name} has no recognized pinned version references")
    return content


def render_sha256sums(script_contents):
    """Render SHA256SUMS.txt from the generated (LF-normalized) script contents."""
    lines = []
    for name, content in script_contents.items():
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        lines.append(f"{digest}  scripts/{name}")
    return "\n".join(lines) + "\n"


def render_constants(ext, constants):
    """Render constants block in the target language syntax."""
    client_header = f'skill/{constants["skill_version"]}'
    base_url = constants["api_base_url"]
    domains = constants["available_domains"]

    if ext == ".py":
        lines = [f'CLIENT_HEADER = "{client_header}"']
        lines.append(f'API_BASE_URL = os.environ.get("ANYSEARCH_API_BASE_URL", "{base_url}").rstrip("/")')
        lines.append("AVAILABLE_DOMAINS = [")
        for i in range(0, len(domains), 6):
            chunk = domains[i:i+6]
            lines.append("    " + ", ".join(f'"{d}"' for d in chunk) + ",")
        lines.append("]")
        return "\n".join(lines)

    elif ext == ".js":
        lines = [f'const CLIENT_HEADER = "{client_header}";']
        lines.append(f'const API_BASE_URL = (process.env.ANYSEARCH_API_BASE_URL || "{base_url}").replace(/\\/$/, "");')
        lines.append("const AVAILABLE_DOMAINS = [")
        for i in range(0, len(domains), 6):
            chunk = domains[i:i+6]
            lines.append("  " + ",".join(f'"{d}"' for d in chunk) + ",")
        lines.append("];")
        return "\n".join(lines)

    elif ext == ".ps1":
        lines = [f'$CLIENT_HEADER = "{client_header}"']
        lines.append(f'$API_BASE_URL = if ($env:ANYSEARCH_API_BASE_URL) {{ $env:ANYSEARCH_API_BASE_URL.TrimEnd("/") }} else {{ "{base_url}" }}')
        lines.append("$AVAILABLE_DOMAINS = @(")
        chunks = [domains[i:i+6] for i in range(0, len(domains), 6)]
        for idx, chunk in enumerate(chunks):
            suffix = "," if idx < len(chunks) - 1 else ""
            lines.append("    " + ", ".join(f'"{d}"' for d in chunk) + suffix)
        lines.append(")")
        return "\n".join(lines)

    elif ext == ".sh":
        lines = [f'CLIENT_HEADER="{client_header}"']
        lines.extend([f'API_BASE_URL="${{ANYSEARCH_API_BASE_URL:-{base_url}}}"', 'API_BASE_URL="${API_BASE_URL%/}"'])
        lines.append("AVAILABLE_DOMAINS=(" + " ".join(f'"{d}"' for d in domains) + ")")
        return "\n".join(lines)

    raise ValueError(f"Unsupported extension: {ext}")


def render_doc_block(ext, constants):
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
    return $tpl
}'''

    elif ext == ".sh":
        return r'''_cmd_doc() {
  local shared="$SCRIPT_DIR/shared"
  local tpl
  tpl=$(cat "$shared/doc_spec.md")
  local domains
  domains=$(jq -r '.available_domains | join(" ")' "$shared/constants.json")
  tpl="${tpl//\{\{LANG_NAME\}\}/Bash}"
  tpl="${tpl//\{\{LANG_CODEBLOCK\}\}/bash}"
  tpl="${tpl//\{\{LANG_INVOKE\}\}/bash scripts/anysearch_cli.sh}"
  tpl="${tpl//\{\{DOMAINS_SPACE\}\}/$domains}"
  printf '%s\n' "$tpl"
}'''

    raise ValueError(f"Unsupported extension: {ext}")


def replace_marker_section(content, ext, section_name, new_text):
    """Replace everything between marker comments for section_name with new_text."""
    begin_tag, end_tag = MARKERS[ext]
    begin = begin_tag.format(name=section_name)
    end = end_tag.format(name=section_name)

    if begin not in content:
        raise ValueError(f"BEGIN marker '{begin_tag.format(name=section_name)}' not found")
    if end not in content:
        raise ValueError(f"END marker '{end_tag.format(name=section_name)}' not found")

    before, rest = content.split(begin, 1)
    _, after = rest.split(end, 1)
    return before + begin + "\n" + new_text + "\n" + end + after


def generate_script(script_path, constants):
    """Regenerate the constants and doc blocks in a CLI script."""
    ext = os.path.splitext(script_path)[1]
    if ext not in MARKERS:
        raise ValueError(f"Unsupported extension: {ext}")

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    constants_text = render_constants(ext, constants)
    content = replace_marker_section(content, ext, "CONSTANTS", constants_text)

    doc_block = render_doc_block(ext, constants)
    content = replace_marker_section(content, ext, "DOC_SPEC", doc_block)

    return content


def sync_file(path, label, new_content, check_only):
    """Write new_content if it differs, or report drift in check mode."""
    with open(path, "r", encoding="utf-8") as f:
        old_content = f.read()

    if new_content == old_content:
        print(f"OK: {label}")
        return False

    if check_only:
        print(f"CHANGED: {label} (run generate.py to update)")
        return True

    # Keep Bash runnable from Windows worktrees with core.autocrlf=true.
    # The repository also pins *.sh to LF in .gitattributes.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print(f"Generated: {label}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate AnySearch CLI scripts and version metadata")
    parser.add_argument("--check", action="store_true", help="Verify generated files are up-to-date (for CI)")
    parser.add_argument("--bump", metavar="VERSION", help="Update the SKILL.md version, then regenerate")
    args = parser.parse_args()

    if args.bump and args.check:
        parser.error("--bump cannot be combined with --check")

    if args.bump:
        try:
            bump_skill_version(args.bump)
            print(f"Bumped SKILL.md to {args.bump}")
        except Exception as e:
            print(f"ERROR bumping SKILL.md: {e}", file=sys.stderr)
            sys.exit(1)

    constants = load_constants()
    version = constants["skill_version"]

    changed = False
    script_contents = {}

    for ext in [".py", ".js", ".ps1", ".sh"]:
        script_name = f"anysearch_cli{ext}"
        script_path = os.path.join(SCRIPT_DIR, script_name)

        try:
            new_content = generate_script(script_path, constants)
            script_contents[script_name] = new_content
            changed = sync_file(script_path, script_name, new_content, args.check) or changed
        except Exception as e:
            print(f"ERROR in {script_name}: {e}", file=sys.stderr)
            sys.exit(1)

    sums_path = os.path.join(ROOT_DIR, SUMS_FILENAME)
    sums_content = render_sha256sums(script_contents)
    changed = sync_file(sums_path, SUMS_FILENAME, sums_content, args.check) or changed

    for readme_name in README_FILES:
        readme_path = os.path.join(ROOT_DIR, readme_name)
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = render_readme(f.read(), version, readme_name)
            changed = sync_file(readme_path, readme_name, readme_content, args.check) or changed
        except Exception as e:
            print(f"ERROR in {readme_name}: {e}", file=sys.stderr)
            sys.exit(1)

    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()

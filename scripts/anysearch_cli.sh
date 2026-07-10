#!/usr/bin/env bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

ENDPOINT="https://api.anysearch.com/mcp"
# Identifies access mode + spec version to the backend (X-Anysearch-Client).
# Keep the version aligned with SKILL.md `version`.
CLIENT_HEADER="skill/2.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not found. Install it: https://jqlang.github.io/jq/download/" >&2
  exit 1
fi

_trim() {
  # Strip leading/trailing whitespace (pure bash, no subprocess). Unlike
  # `echo "$x" | xargs` this preserves internal whitespace, backslashes and
  # quotes in the value.
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

_load_env() {
  for env_path in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/../.env"; do
    if [[ -f "$env_path" ]]; then
      while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#$'\xEF\xBB\xBF'}"   # strip a leading UTF-8 BOM (first line)
        line="$(_trim "$line")"
        # '#' is a comment only at the start of a line, not inline, so a value
        # that legitimately contains '#' (e.g. an API key) is preserved. Matches
        # the Python CLI.
        [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
        local key val
        key="$(_trim "${line%%=*}")"
        val="$(_trim "${line#*=}")"
        # Strip surrounding quotes (any number, either kind) and re-trim, to
        # match the Python reference: value.strip().strip("\"'").strip().
        val="${val#"${val%%[!\"\']*}"}"
        val="${val%"${val##*[!\"\']}"}"
        val="$(_trim "$val")"
        # Skip empty values so an empty .env entry does not clobber a real
        # environment variable.
        [[ -n "$key" && -n "$val" ]] && export "$key=$val"
      done < "$env_path"
    fi
  done
}

_load_env

API_KEY="${ANYSEARCH_API_KEY:-}"

# Abort with a clear message when a value-taking flag has no value. Call as
# `_need_val "$@"` from inside an arg loop ($1 = flag, $2 = its value). This is
# required because on bash 3.2 `shift 2` past the end of the positional list
# fails WITHOUT decrementing $#, which would otherwise spin a `while [[ $# -gt 0 ]]`
# arg loop forever (100% CPU) on a trailing value-flag such as `search q --domain`.
_need_val() {
  if [[ $# -lt 2 ]]; then
    echo "Error: missing value for $1" >&2
    exit 1
  fi
}

_parse_sub_domain_params() {
  local value="$1"
  if [[ -z "$value" ]]; then
    echo ""
    return
  fi
  # Try JSON parse first
  if printf '%s' "$value" | jq empty 2>/dev/null; then
    printf '%s' "$value"
    return
  fi
  # {key:value,key2:value2} format (PowerShell strips inner quotes from JSON)
  if [[ "$value" == \{* && "$value" == *\} ]]; then
    local inner="${value#\{}"
    inner="${inner%\}}"
    inner="$(echo "$inner" | xargs 2>/dev/null || echo "$inner")"
    if [[ -n "$inner" ]]; then
      local result="{}"
      IFS=',' read -ra pairs <<< "$inner"
      for pair in "${pairs[@]}"; do
        if [[ "$pair" == *:* ]]; then
          local key="${pair%%:*}"
          local val="${pair#*:}"
          key="$(echo "$key" | xargs 2>/dev/null || echo "$key")"
          val="$(echo "$val" | xargs 2>/dev/null || echo "$val")"
          key="${key//\"/}"
          key="${key//\'/}"
          val="${val//\"/}"
          val="${val//\'/}"
          if [[ -n "$key" ]]; then
            result=$(printf '%s' "$result" | jq --arg k "$key" --arg v "$val" '. + {($k):$v}')
          fi
        fi
      done
      if [[ "$result" != "{}" ]]; then
        printf '%s' "$result"
        return
      fi
    fi
  fi
  # key=value,key2=value2 format
  local result="{}"
  IFS=',' read -ra pairs <<< "$value"
  for pair in "${pairs[@]}"; do
    local key="${pair%%=*}"
    local val="${pair#*=}"
    key="$(echo "$key" | xargs 2>/dev/null || echo "$key")"
    val="$(echo "$val" | xargs 2>/dev/null || echo "$val")"
    if [[ -n "$key" ]]; then
      result=$(printf '%s' "$result" | jq --arg k "$key" --arg v "$val" '. + {($k):$v}')
    fi
  done
  printf '%s' "$result"
}

# BEGIN GENERATED:CONSTANTS
AVAILABLE_DOMAINS=("general" "resource" "social_media" "finance" "academic" "legal" "health" "business" "security" "ip" "code" "energy" "environment" "agriculture" "travel" "film" "gaming")
# END GENERATED:CONSTANTS

_call_api() {
  local tool_name="$1"
  local arguments="$2"
  local auth_args=()
  if [[ -n "$API_KEY" ]]; then
    auth_args+=(-H "Authorization: Bearer $API_KEY")
  fi

  local payload
  payload=$(jq -n --arg name "$tool_name" --argjson args "$arguments" \
    '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":$name,"arguments":$args}}')

  # Capture the response body and the HTTP status together: curl -w appends
  # "\n<http_code>" after the body, which we split apart below.
  local response http_code body
  response=$(curl -s -w '\n%{http_code}' -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "X-Anysearch-Client: $CLIENT_HEADER" \
    "${auth_args[@]}" \
    -d "$payload" \
    --max-time 30 2>/dev/null)

  http_code="${response##*$'\n'}"
  body="${response%$'\n'*}"

  # A non-numeric or 000 status means the request never completed
  # (connection failure, DNS error, or timeout — curl reports 000).
  if [[ ! "$http_code" =~ ^[0-9]+$ || "$http_code" == "000" ]]; then
    echo "Error: No response from API" >&2
    exit 1
  fi

  # Surface HTTP-level failures (4xx/5xx) instead of printing the error body
  # to stdout and exiting 0, which is indistinguishable from a real result.
  if (( 10#$http_code >= 400 )); then
    local http_err
    http_err=$(printf '%s' "$body" | jq -r '.error.message // empty' 2>/dev/null)
    if [[ -n "$http_err" ]]; then
      echo "API Error (HTTP $http_code): $http_err" >&2
    else
      echo "HTTP Error $http_code: $body" >&2
    fi
    exit 1
  fi

  # JSON-RPC-level error returned with HTTP 200.
  local error_msg
  error_msg=$(printf '%s' "$body" | jq -r '.error.message // empty' 2>/dev/null)
  if [[ -n "$error_msg" ]]; then
    echo "API Error: $error_msg" >&2
    exit 1
  fi

  local text_block
  text_block=$(printf '%s' "$body" | jq -r '.result.content[0].text // empty' 2>/dev/null)
  if [[ -n "$text_block" ]]; then
    printf '%s\n' "$text_block"
  else
    printf '%s\n' "$body"
  fi
}

_cmd_search() {
  local query=""
  local domain=""
  local sub_domain=""
  local sub_domain_params=""
  local max_results=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domain|-d)     _need_val "$@"; domain="$2"; shift 2 ;;
      --sub_domain|-s) _need_val "$@"; sub_domain="$2"; shift 2 ;;
      --sub_domain_params|--sdp|-p) _need_val "$@"; sub_domain_params="$2"; shift 2 ;;
      --max_results|-m) _need_val "$@"; max_results="$2"; shift 2 ;;
      --api_key)       _need_val "$@"; API_KEY="$2"; shift 2 ;;
      -*)              echo "Unknown flag: $1" >&2; _usage; exit 1 ;;
      *)               query="$1"; shift ;;
    esac
  done

  if [[ -z "$query" ]]; then
    echo "Error: query is required" >&2
    exit 1
  fi

  local args
  args=$(jq -n --arg q "$query" '{"query":$q}')

  if [[ -n "$domain" ]]; then
    args=$(printf '%s' "$args" | jq --arg d "$domain" '. + {"domain":$d}')
    if [[ -n "$sub_domain" ]]; then
      args=$(printf '%s' "$args" | jq --arg s "$sub_domain" '. + {"sub_domain":$s}')
    fi
    if [[ -n "$sub_domain_params" ]]; then
      local parsed_sdp
      parsed_sdp=$(_parse_sub_domain_params "$sub_domain_params")
      if [[ -n "$parsed_sdp" && "$parsed_sdp" != "{}" ]]; then
        args=$(printf '%s' "$args" | jq --argjson p "$parsed_sdp" '. + {"sub_domain_params":$p}')
      fi
    fi
  fi

  if [[ -n "$max_results" ]]; then
    if [[ "$max_results" -gt 10 ]]; then
      max_results=10
    fi
    args=$(printf '%s' "$args" | jq --argjson m "$max_results" '. + {"max_results":$m}')
  fi

  _call_api "search" "$args"
}

_cmd_get_sub_domains() {
  local domain=""
  local domains=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domains)       _need_val "$@"; domains="$2"; shift 2 ;;
      --domain)        _need_val "$@"; domain="$2"; shift 2 ;;
      --api_key)       _need_val "$@"; API_KEY="$2"; shift 2 ;;
      -*)              echo "Unknown flag: $1" >&2; exit 1 ;;
      *)               domain="$1"; shift ;;
    esac
  done

  local args
  if [[ -n "$domains" ]]; then
    local d_json
    if [[ "$domains" == \[* ]]; then
      d_json="$domains"
    else
      d_json=$(printf '%s' "$domains" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length > 0))')
    fi
    args=$(jq -n --argjson d "$d_json" '{"domains":$d}')
  elif [[ -n "$domain" ]]; then
    args=$(jq -n --arg d "$domain" '{"domain":$d}')
  else
    echo "Error: provide --domain or --domains" >&2
    exit 1
  fi

  _call_api "get_sub_domains" "$args"
}

_cmd_extract() {
  local url=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url|-u)        _need_val "$@"; url="$2"; shift 2 ;;
      --api_key)       _need_val "$@"; API_KEY="$2"; shift 2 ;;
      -*)              echo "Unknown flag: $1" >&2; exit 1 ;;
      *)               url="$1"; shift ;;
    esac
  done

  if [[ -z "$url" ]]; then
    echo "Error: url is required" >&2
    exit 1
  fi

  local args
  args=$(jq -n --arg u "$url" '{"url":$u}')
  _call_api "extract" "$args"
}

_cmd_batch_search() {
  local queries=""
  local query_items=()
  local shared_domain=""
  local shared_sub_domain=""
  local shared_sdp=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queries|-q)    _need_val "$@"; queries="$2"; shift 2 ;;
      --query)         _need_val "$@"; query_items+=("$2"); shift 2 ;;
      --domain|-d)     _need_val "$@"; shared_domain="$2"; shift 2 ;;
      --sub_domain|-s) _need_val "$@"; shared_sub_domain="$2"; shift 2 ;;
      --sub_domain_params|--sdp|-p) _need_val "$@"; shared_sdp="$2"; shift 2 ;;
      --api_key)       _need_val "$@"; API_KEY="$2"; shift 2 ;;
      -*)              echo "Unknown flag: $1" >&2; exit 1 ;;
      *)               queries="$1"; shift ;;
    esac
  done

  local args
  if [[ ${#query_items[@]} -gt 0 ]]; then
    if [[ ${#query_items[@]} -gt 5 ]]; then
      echo "Error: batch_search supports a maximum of 5 queries" >&2
      exit 1
    fi
    local items_json="[]"
    for q in "${query_items[@]}"; do
      items_json=$(printf '%s' "$items_json" | jq --arg q "$q" '. + [{"query":$q}]')
    done
    args=$(jq -n --argjson q "$items_json" '{"queries":$q}')
  elif [[ -n "$queries" ]]; then
    local raw="$queries"
    if [[ "$raw" == @* ]]; then
      local fpath="${raw:1}"
      if [[ ! -f "$fpath" ]]; then
        echo "Error: file not found: $fpath" >&2
        exit 1
      fi
      raw=$(cat "$fpath")
    fi
    if [[ "$raw" == \[* || "$raw" == \{* ]]; then
      local json_input="$raw"
      [[ "$raw" == \{* ]] && json_input="[$raw]"
      if printf '%s' "$json_input" | jq empty 2>/dev/null; then
        args=$(jq -n --argjson q "$json_input" '{"queries":$q}')
      else
        # Repair mangled JSON (e.g. PowerShell strips inner quotes: {query:AAPL} )
        # Use jq to parse the repaired structure
        args=$(printf '%s' "$json_input" | jq -R '
          # Simple repair: split top-level array items by "},{" then parse each
          gsub("^\\[|\\]$";"") |
          split("},{") |
          map(gsub("^\\{|\\}$";"")) |
          map(
            split(",") |
            map(
              (index(":") // index("=")) as $idx |
              if $idx then
                { (.[0:$idx] | gsub("^\\s+|\\s+$|[\"'"'"']";"")): (.[$idx+1:] | gsub("^\\s+|\\s+$|[\"'"'"']";"")) }
              else empty end
            ) | add // {}
          )
        ' 2>/dev/null) || true
        if [[ -z "$args" || "$args" == "null" ]]; then
          echo "Error: failed to parse queries JSON" >&2
          exit 1
        fi
        args=$(jq -n --argjson q "$args" '{"queries":$q}')
      fi
    else
      local items_json
      items_json=$(printf '%s' "$raw" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length > 0)) | map({"query":.})')
      args=$(jq -n --argjson q "$items_json" '{"queries":$q}')
    fi
  else
    echo "Error: provide --queries or --query" >&2
    exit 1
  fi

  local count
  count=$(printf '%s' "$args" | jq '.queries | length')
  if [[ "$count" -lt 1 ]]; then
    echo "Error: queries must contain at least 1 item" >&2
    exit 1
  fi
  if [[ "$count" -gt 5 ]]; then
    echo "Error: batch_search supports a maximum of 5 queries" >&2
    exit 1
  fi

  # Inject shared params into each query item (item's own fields take precedence)
  local parsed_shared_sdp=""
  if [[ -n "$shared_sdp" ]]; then
    parsed_shared_sdp=$(_parse_sub_domain_params "$shared_sdp")
  fi

  if [[ -n "$shared_domain" || -n "$shared_sub_domain" || -n "$parsed_shared_sdp" ]]; then
    args=$(printf '%s' "$args" | jq \
      --arg sd "$shared_domain" \
      --arg ss "$shared_sub_domain" \
      --argjson sp "${parsed_shared_sdp:-null}" \
      '.queries = [.queries[] | 
        (if ($sd != "" and (.domain == null or .domain == "")) then .domain = $sd else . end) |
        (if ($ss != "" and (.sub_domain == null or .sub_domain == "")) then .sub_domain = $ss else . end) |
        (if ($sp != null and (.sub_domain_params == null)) then .sub_domain_params = $sp else . end)
      ]')
  fi

  # Parse string sub_domain_params inside query items to objects
  args=$(printf '%s' "$args" | jq '
    .queries = [.queries[] |
      if (.sub_domain_params | type) == "string" then
        if (.sub_domain_params | startswith("{")) then
          # {key:value} format (PowerShell-mangled JSON)
          .sub_domain_params = (.sub_domain_params | ltrimstr("{") | rtrimstr("}") | split(",") | map(split(":") | {(.[0] | gsub("^\\s+|\\s+$|[\"'"'"']";"")): (.[1:] | join(":") | gsub("^\\s+|\\s+$|[\"'"'"']";""))}) | add // {})
        else
          # key=value format
          .sub_domain_params = (.sub_domain_params | split(",") | map(split("=") | {(.[0] | gsub("^\\s+|\\s+$";"")): (.[1:] | join("=") | gsub("^\\s+|\\s+$";""))}) | add // {})
        end
      else . end
    ]')

  _call_api "batch_search" "$args"
}

# BEGIN GENERATED:DOC_SPEC
_cmd_doc() {
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
}
# END GENERATED:DOC_SPEC

_usage() {
  _cmd_doc
}

main() {
  local command="${1:-}"
  shift || true

  case "$command" in
    search)         _cmd_search "$@" ;;
    get_sub_domains)   _cmd_get_sub_domains "$@" ;;
    extract)        _cmd_extract "$@" ;;
    batch_search)   _cmd_batch_search "$@" ;;
    doc)            _cmd_doc ;;
    -h|--help|help) _usage ;;
    "")             _usage ;;
    *)              echo "Unknown command: $command" >&2; _usage; exit 1 ;;
  esac
}

main "$@"

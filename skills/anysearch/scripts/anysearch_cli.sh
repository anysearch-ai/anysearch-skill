#!/usr/bin/env bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

ENDPOINT="https://api.anysearch.com/mcp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not found. Install it: https://jqlang.github.io/jq/download/" >&2
  exit 1
fi

_load_env() {
  for env_path in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/../.env"; do
    if [[ -f "$env_path" ]]; then
      while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%%#*}"
        line="$(echo "$line" | xargs 2>/dev/null || true)"
        [[ -z "$line" || "$line" != *=* ]] && continue
        local key="${line%%=*}"
        local val="${line#*=}"
        val="$(echo "$val" | sed 's/^["\x27]\|["\x27]$//g')"
        export "$key=$val"
      done < "$env_path"
    fi
  done
}

_load_env

API_KEY="${ANYSEARCH_API_KEY:-}"

# BEGIN GENERATED:CONSTANTS
AVAILABLE_DOMAINS=("code" "travel" "home" "ecommerce" "gaming" "film" "music" "finance" "academic" "legal" "business" "ip" "health" "geo" "environment" "energy")
CONTENT_TYPES=("web" "news" "code" "doc" "academic" "data" "image" "video" "audio")
FRESHNESS_VALUES=("day" "week" "month" "year")
ZONES=("cn" "intl")
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

  local response
  response=$(curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    "${auth_args[@]}" \
    -d "$payload" \
    --max-time 30 2>/dev/null)

  if [[ -z "$response" ]]; then
    echo "Error: No response from API" >&2
    exit 1
  fi

  local error_msg
  error_msg=$(printf '%s' "$response" | jq -r '.error.message // empty' 2>/dev/null)
  if [[ -n "$error_msg" ]]; then
    echo "API Error: $error_msg" >&2
    exit 1
  fi

  local text_block
  text_block=$(printf '%s' "$response" | jq -r '.result.content[0].text // empty' 2>/dev/null)
  if [[ -n "$text_block" ]]; then
    printf '%s\n' "$text_block"
  else
    printf '%s\n' "$response"
  fi
}

_cmd_search() {
  local query=""
  local domain=""
  local sub_domain=""
  local sub_domain_params=""
  local content_types=""
  local zone=""
  local max_results=""
  local freshness=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domain|-d)     domain="$2"; shift 2 ;;
      --sub_domain|-s) sub_domain="$2"; shift 2 ;;
      --sub_domain_params) sub_domain_params="$2"; shift 2 ;;
      --content_types|-t) content_types="$2"; shift 2 ;;
      --zone|-z)       zone="$2"; shift 2 ;;
      --max_results|-m) max_results="$2"; shift 2 ;;
      --freshness|-f)  freshness="$2"; shift 2 ;;
      --api_key)       API_KEY="$2"; shift 2 ;;
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
      args=$(printf '%s' "$args" | jq --argjson p "$sub_domain_params" '. + {"sub_domain_params":$p}')
    fi
  fi

  if [[ -n "$content_types" ]]; then
    local ct_json
    if [[ "$content_types" == \[* ]]; then
      ct_json="$content_types"
    else
      ct_json=$(printf '%s' "$content_types" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length > 0))')
    fi
    args=$(printf '%s' "$args" | jq --argjson ct "$ct_json" '. + {"content_types":$ct}')
  fi

  if [[ -n "$zone" ]]; then
    args=$(printf '%s' "$args" | jq --arg z "$zone" '. + {"zone":$z}')
  fi
  if [[ -n "$max_results" ]]; then
    args=$(printf '%s' "$args" | jq --argjson m "$max_results" '. + {"max_results":$m}')
  fi
  if [[ -n "$freshness" ]]; then
    args=$(printf '%s' "$args" | jq --arg f "$freshness" '. + {"freshness":$f}')
  fi

  _call_api "search" "$args"
}

_cmd_list_domains() {
  local domain=""
  local domains=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domains)       domains="$2"; shift 2 ;;
      --domain)        domain="$2"; shift 2 ;;
      --api_key)       API_KEY="$2"; shift 2 ;;
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

  _call_api "list_domains" "$args"
}

_cmd_extract() {
  local url=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url|-u)        url="$2"; shift 2 ;;
      --api_key)       API_KEY="$2"; shift 2 ;;
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

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --queries|-q)    queries="$2"; shift 2 ;;
      --query)         query_items+=("$2"); shift 2 ;;
      --api_key)       API_KEY="$2"; shift 2 ;;
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
      if [[ "$raw" == \[* ]]; then
        args=$(jq -n --argjson q "$raw" '{"queries":$q}')
      else
        args=$(jq -n --argjson q "[$raw]" '{"queries":$q}')
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

  _call_api "batch_search" "$args"
}

# BEGIN GENERATED:DOC_SPEC
_cmd_doc() {
  local shared="$SCRIPT_DIR/shared"
  if [[ ! -f "$shared/doc_spec.md" || ! -f "$shared/constants.json" ]]; then
    echo "Error: could not load help template from $shared" >&2
    echo "Usage: bash scripts/anysearch_cli.sh <search|list_domains|extract|batch_search|doc>" >&2
    return 1
  fi
  local tpl
  tpl=$(cat "$shared/doc_spec.md")
  local domains
  domains=$(jq -r '.available_domains | join(" ")' "$shared/constants.json")
  local ctypes
  ctypes=$(jq -r '.content_types | join(" ")' "$shared/constants.json")
  tpl="${tpl//\{\{LANG_NAME\}\}/Bash}"
  tpl="${tpl//\{\{LANG_CODEBLOCK\}\}/bash}"
  tpl="${tpl//\{\{LANG_INVOKE\}\}/bash scripts/anysearch_cli.sh}"
  tpl="${tpl//\{\{DOMAINS_SPACE\}\}/$domains}"
  tpl="${tpl//\{\{CONTENT_TYPES_SPACE\}\}/$ctypes}"
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
    list_domains)   _cmd_list_domains "$@" ;;
    extract)        _cmd_extract "$@" ;;
    batch_search)   _cmd_batch_search "$@" ;;
    doc)            _cmd_doc ;;
    -h|--help|help) _usage ;;
    "")             _usage ;;
    *)              echo "Unknown command: $command" >&2; _usage; exit 1 ;;
  esac
}

main "$@"

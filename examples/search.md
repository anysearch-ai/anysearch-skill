# Example: search (General Search)

- Environment: Windows 11 / Python 3.11.9 / anysearch-skill main
- Auth: API key mode

## Request

```bash
python scripts/anysearch_cli.py search "Model Context Protocol official documentation" --max_results 3
```

## Response (truncated)

```text
## Search Results (3 results, 1380ms)

### 1. Specification - Model Context Protocol
- **URL**: https://modelcontextprotocol.io/specification/draft
- （Main text summary, truncated）Model Context Protocol (MCP) 是连接 LLM 应用与外部数据源/工具的开放协议……

### 2. Specification (Draft) — Model Context Protocol (MCP)
- **URL**: https://modelcontextprotocol.info/specification/draft/

### 3. Model Context Protocol (MCP) Evaluation - CAMARA Project
- **URL**: https://lf-camaraproject.atlassian.net/wiki/spaces/CAM/pages/108134638/...
```

## Notes

- The response is Markdown, emitted in result order, with title, URL, and body summary.

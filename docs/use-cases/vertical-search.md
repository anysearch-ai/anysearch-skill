# Use Case: Structured Vertical Information

> Measured record. First CLI call on 2026-11-23; re-collected via MCP `search` on 2026-11-24 to fill in real `request_id` values. Not a fabricated example.

`````text
Input example: **Look up AAPL's stock quote and include the data time and source; explicitly state when timeliness cannot be confirmed.**

Calls: **get_sub_domains → search**

**1. `get_sub_domains` — get finance's valid sub-domains and parameters**

```json
{
  "domain": "finance"
}
```

````text
## finance Domain Capabilities (6 available)

### finance.calendar
### finance.fundamental
### finance.macro
### finance.news
### finance.quote
Real-time and historical price, volume and market-cap data ...
  - type (required): stock / forex / crypto / commodity / index / etf
  - symbol / cn_code / period ...
### finance.screen
````

```yaml
request_id: 890241efbe0145cba207ddd9551c3fbe
```

| sub_domain | Purpose |
| --- | --- |
| `finance.calendar` | Earnings, dividends, IPO, and economic data calendars |
| `finance.fundamental` | Financial statements, valuation, analyst ratings, ownership, SEC filings |
| `finance.macro` | Macro indicators such as GDP, CPI, interest rates, and money supply |
| `finance.news` | Financial news, company announcements, and broker summaries |
| `finance.quote` | Quotes for stocks, forex, crypto, commodities, indices, and ETFs |
| `finance.screen` | Screen stocks by industry and country |

The actual key names for `sub_domain` and `params` follow the current response.

**2. `search` (vertical) — get the AAPL quote by schema**

```json
{
  "query": "AAPL stock quote",
  "domain": "finance",
  "sub_domain": "finance.quote",
  "sub_domain_params": { "type": "stock", "symbol": "AAPL", "cn_code": "" },
  "max_results": 3
}
```

````text
## Search Results (3 results, 927ms)

### 1. Apple Inc. (AAPL)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL
- Symbol: AAPL | Name: Apple Inc. | Exchange: NASDAQ | Price: 349.08 | Open: 347.78 | PrevClose: 342.56 | Change: +6.52 | Change%: +1.90% | DayHigh: 352.60 | DayLow: 345.44 | YearHigh: 360.83 | YearLow: 243.42 | Volume: 56997299 | MarketCap: 5072900376000 | Avg50: 341.81 | Avg200: 303.24

### 2. LS 1x Apple Tracker ETC (AAPL.L)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL.L
- Symbol: AAPL.L | Name: LS 1x Apple Tracker ETC | Exchange: LSE | Price: 672.65 | Open: 0.00 | PrevClose: 637.67 | Change: +34.98 | Change%: +5.48% | DayHigh: 672.65 | DayLow: 672.65 | YearHigh: 672.65 | YearLow: 672.65 | Volume: 49 | MarketCap: 0 | Avg50: 0.00 | Avg200: 0.00

### 3. Apple Inc. (AAPL.DE)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL.DE
- Symbol: AAPL.DE | Name: Apple Inc. | Exchange: XETRA | Price: 0.00 | Open: 0.00 | PrevClose: 0.00 | Change: +0.00 | Change%: +0.00% | DayHigh: 0.00 | DayLow: 0.00 | YearHigh: 0.00 | YearLow: 0.00 | Volume: 0 | MarketCap: 0 | Avg50: 0.00 | Avg200: 0.00
````

```yaml
request_id: b29c00a1013b4f4692b87394f7438c3e
```

All three are quotes for the same company Apple on different exchanges: `AAPL` (NASDAQ primary), `AAPL.L` (LSE London, actually the LS 1x Apple Tracker ETC), and `AAPL.DE` (XETRA Frankfurt; all fields were 0 in this run and there was no valid quote). The response contains only `data.metadata.search_time_ms` (927ms this time, which is search latency) and **no quote as-of timestamp**, so it is treated as "timeliness unverified" rather than a live quote.

This example covers the `get_sub_domains` and `search` tools.

Status and evidence: Windows 11 / Python 3.11.9 / main; the example was re-collected via the MCP `search` tool (anonymous), and `request_id` comes from `_meta.request_id` in the response; the raw data is an **external** data source (financialmodelingprep).
`````

## Notes

- **Delivery template**: Entity | Capability used | Request parameters | Fields obtained | Data time | Source URL | Unknowns

  | Entity | Capability used | Request parameters | Fields obtained | Data time | Source URL | Unknowns |
  |---|---|---|---|---|---|---|
  | AAPL (NASDAQ) | finance.quote | type=stock,symbol=AAPL,cn_code= | Price/Change/Volume/MarketCap, etc. | Only `search_time_ms=927ms`; no quote as-of → timeliness unverified | https://site.financialmodelingprep.com/?ref=quote-AAPL | Data cutoff time, currency, whether delayed; see the example YAML for `request_id` |

- **Source distinction**: The raw data is an **external** data source (financialmodelingprep), not an official exchange feed; timeliness is governed by response fields (only `search_time_ms`, no quote as-of time).

- **Failures and degradation**: On entity mismatch, record "entity mismatch" with the source rather than forcing fields; when no reliable data time exists, mark "timeliness unverified" rather than presenting it as a live quote; on 429 or empty results, keep the status and the redacted error category (not triggered this time).
- **Limits and unknowns**: **The response contains only `data.metadata.search_time_ms` (search latency) and has no quote as-of field**, so timeliness cannot be proven; any price cited must carry "timeliness unverified"; `AAPL.DE` had all fields 0 this time and cannot be treated as a valid quote; values are a single snapshot and change over time; the provider's delay statements and licensing terms were not checked.
- **Environment and status**: Windows 11; Python 3.11.9; anysearch-skill (main, including PR #47); example re-collected via the MCP `search` tool on 2026-11-24 (anonymous, `X-Anysearch-Client: mcp/1.0.0`), `request_id` from `_meta.request_id`; single run, not a benchmark.
- **Verification date**: 2026-11-23 (original CLI run), 2026-11-24 (re-collected with real `request_id` values)

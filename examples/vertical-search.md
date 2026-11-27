# Example: Vertical Search (Sub-domain Discovery + Structured Quote)

- Environment: Windows 11 / Python 3.11.9 / anysearch-skill main
- Auth: API key mode

## Request

```bash
python scripts/anysearch_cli.py get_sub_domains --domain finance
python scripts/anysearch_cli.py search "AAPL stock quote" --domain finance --sub_domain finance.quote --sdp type=stock,symbol=AAPL,cn_code= --max_results 3
```

## Response 1: Sub-domain Catalog (truncated)

```text
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
```

## Response 2: Vertical Quote (truncated)

```text
## Search Results (3 results, 1407ms)

### 1. Apple Inc. (AAPL)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL
- Symbol: AAPL | Name: Apple Inc. | Exchange: NASDAQ | Price: 342.56 | Open: 352.63 | PrevClose: 349.21 | Change: -6.65 | Change%: -1.90% | Volume: 80692545 | MarketCap: 4978150432000

### 2. LS 1x Apple Tracker ETC (AAPL.L)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL.L

### 3. Apple Inc. (AAPL.MX)
- **URL**: https://site.financialmodelingprep.com/?ref=quote-AAPL.MX
```

## Notes

- Call `get_sub_domains` before a vertical search; pass `type/symbol/cn_code` according to the schema, and pass empty values for unavailable fields.
- The same entity may return multiple exchange codes (AAPL / AAPL.L / AAPL.MX); distinguish them as needed.

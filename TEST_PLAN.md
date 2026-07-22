# AnySearch Skill 端到端测试计划

## 测试目标

验证 AnySearch skill 的以下功能在所有 CLI 上正常工作：

- `--sdp key=value` 扁平参数格式
- `{key:value}` 兼容格式（PowerShell 环境双引号被剥后的退化 JSON）
- `-p` 短别名
- `batch_search` 共享参数注入（`--domain` / `--sub_domain` / `--sdp` / `--max_results`）
- `batch_search` per-item KV 字符串解析
- `batch_search` hybrid 混合查询
- `batch_search` 内联 JSON / mangled JSON 的 repair 逻辑
- `get_sub_domains` 单 domain 和批量 domain
- `extract` 页面内容提取
- 错误处理（unknown flag）

## 前置条件

1. 确认 `.env` 文件中有有效的 API Key
2. 确认 `runtime.conf` 或按优先级检测可用 CLI runtime（Python > Node.js > Shell）
3. 所有命令中 `-m 2` 表示 `--max_results 2`，减小 API 负担

---

## 第一组：search 基础场景

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 1 | 搜索 "capital of France"，返回 2 条结果 | `## Search Results` |
| 2 | 搜索 "AAPL"，domain=finance, sub_domain=finance.quote，`--sdp type=stock,symbol=AAPL,cn_code=`，返回 2 条 | `## Search Results` |
| 3 | 搜索 "latest trends"，domain=finance, sub_domain=finance.quote，`--sdp type=stock,symbol=TSLA,cn_code=,period=30d`，返回 2 条 | `## Search Results` |
| 4 | 搜索 "MSFT"，domain=finance, sub_domain=finance.quote，`-p type=stock,symbol=MSFT,cn_code=`，返回 2 条 | `## Search Results` |
| 5 | 搜索 "market trends"，domain=finance, sub_domain=finance.market，`--sdp region=,timeframe=`（required param 填空值），返回 2 条 | `## Search Results` |

---

## 第二组：search 兼容性

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 6 | 搜索 "AAPL"，domain=finance, sub_domain=finance.quote，`--sub_domain_params '{"type":"stock","symbol":"AAPL","cn_code":""}'`（JSON 向后兼容） | `## Search Results` |
| 7 | 搜索 "AAPL"，domain=finance, sub_domain=finance.quote，`--sub_domain_params '{type:stock,symbol:AAPL,cn_code:}'`（模拟 PowerShell 剥引号退化格式） | `## Search Results` |

> ⚠️ 场景 7 是本次新增的 `{key:value}` 兼容修复。如果返回 Error 而非 Search Results，是 bug。

---

## 第三组：get_sub_domains

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 8 | 查看 `--domain finance` 的子域列表 | `## finance Domain Capabilities` |
| 9 | 同时查看 `--domains finance,health` 的子域列表 | `## finance Domain Capabilities` |

---

## 第四组：batch_search 共享参数

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 10 | batch_search：`--query "AAPL stock" --query "MSFT revenue"`，共享 `--domain finance --sub_domain finance.quote --sdp type=stock,symbol=,cn_code=`，不加 per-item 参数 | `## Query 1:` |
| 11 | batch_search 用 `@文件` 引用 JSON 文件。文件内容：`[{"query":"AAPL earnings","sub_domain_params":"type=stock,symbol=AAPL,cn_code="},{"query":"MSFT revenue","sub_domain_params":"type=stock,symbol=MSFT,cn_code="}]`。共享 `--domain finance --sub_domain finance.quote` | `## Query 1:` |
| 12 | batch_search：`--query AAPL --query GOOG --max_results 3`，共享 `--max_results` 注入所有 query item（item 自带 max_results 时以 item 为准） | `## Query 1:` |

---

## 第五组：batch_search 复杂场景

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 13 | batch_search 用 `@文件` 引用 JSON 文件。文件内容：`[{"query":"quantum computing"},{"query":"AAPL stock","domain":"finance","sub_domain":"finance.quote","sub_domain_params":"type=stock,symbol=AAPL,cn_code="}]`。**不加共享参数** | `## Query 1:` |
| 14 | batch_search 直接传内联 JSON 数组：`[{"query":"test general"},{"query":"AAPL","domain":"finance","sub_domain":"finance.quote","sub_domain_params":"type=stock,symbol=AAPL,cn_code="}]` | `## Query 1:` |
| 15 | batch_search 传 mangled JSON（无引号 key，模拟 PowerShell 剥引号）：`[{query:test general},{query:AAPL,domain:finance,sub_domain:finance.quote,sub_domain_params:type=stock,symbol=AAPL,cn_code=}]` | `## Query 1:` |

> ⚠️ 场景 15 验证 batch_search 的 repairJson 逻辑能处理退化 JSON。如果报错（非网络超时），是 bug。

---

## 第六组：其他

| # | 需求 | 预期结果第一行 |
|---|---|---|
| 16 | extract 提取 `https://example.com` 内容 | `## Example Domain` |
| 17 | search "test" 附带不存在的 flag `--foobar` | 返回 `Unknown flag` 或 `unrecognized arguments` 错误 |

---

## 通过标准

- 所有 17 个场景的第一行输出匹配上述预期（`## Search Results` / `## Query 1:` / `## finance Domain Capabilities` / `## Example Domain` / 错误提示）
- 场景 7、15 是本次新增兼容修复，如果在任何 CLI 下报非网络错误 → **回归 bug**
- 偶发 `Error: No response from API` 或 `Connection Error` 不算失败（网络抖动），重试即可

## 执行方式

在另一个 session 中加载 anysearch skill，AI 会自动走平台检测和 CLI 路由。只需用自然语言描述上述每个场景的需求即可，无需手动指定 CLI 命令。

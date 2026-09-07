# T17 · 已验证知识注册表试用套件

## 范围

knowledge 一等值类型（已验证知识注册表）的语言面行为基线：store/get 快照
隔离、amend 审计链、验证门 fail-fast、save/load 保真、canonical idiom
（先查知识库再决定是否调 LLM——e25 机制"用得越久越确定"的语言级落地）。

## 用例矩阵

| 用例 | 面 | LLM |
|------|-----|-----|
| T17-K-M1 | store/get round-trip + 未登记 null | 否 |
| T17-K-M2 | 快照隔离（取回值修改不污染知识库） | 否 |
| T17-K-M3 | amend + history append-only + 事件数 | 否 |
| T17-K-M4 | 验证门拒绝（check 假 → KNW_CHECK_REJECTED） | 否 |
| T17-K-M5 | 重复键（KNW_KEY_EXISTS——登记/更正机器强制区分） | 否 |
| T17-K-M6 | save/load 保真（同入口程序——变更丢弃/值保真/事件保真） | 否 |
| T17-K-L1 | canonical idiom 真实双轨（LLM 提案+验证+登记 → 复查 0 调用） | 是 |

## 断言纪律

- mock 面（M1-M6）确定性（纯语言机制，零 LLM）；
- 真实面（L1）= e25 惯用语义性质断言：首次未命中 → LLM 提案 + 确定性
  验证 + 登记；复查命中 → 0 次 LLM 调用（机器持有的知识）；
- 错误面用例 expect-code 断言（诊断码可定位）。

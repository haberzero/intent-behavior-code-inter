# 代码缺陷复查与修复计划（临时任务文档）

> **状态**：D2/D3/D5/D6/D7/D8/D9/D10 全部完成；待讨论项已清空。剩余 6 项测试相关（暂缓，待测试重构）。
> **性质**：临时文档，全部待讨论项处置完成后删除。

---

## 测试相关（暂缓，待测试重构）

- `test_runtime_getitem_contract.py:13` 陈旧 module docstring
- `test_collection_semantics.py:256` INV-STR-6 未测变异
- `test_scope_semantics.py:155` 冗余重复断言
- `test_e2e_exceptions.py:276` H1 覆盖缺口
- `test_e2e_llmexcept.py:497` 部分快照协议未验状态
- `test_meta/test_layering.py:85` 混合测试白名单

---

## 已完成项索引（详见 git 提交历史）

| 批次 | Commit | 内容 |
|---|---|---|
| 第一轮 | `94a5397` | C1/M1/M8/M9/M11a-b/M12/M17（8 项缺陷修复） |
| 第二轮 | `7e9ad85` | C2 禁用 dispatch + M5 删 inherit_variables 死代码 + M3+D1 移除 SyncManager |
| 注释清洁 | `3bcfa3d` | 全代码库 ~530 处注释清洁 |
| 注释卫生纪律 | `da98858` | 注释卫生原则写入 docs/README.md §三.6 + AGENTS.md |
| 诊断码规范化 | `4c5e4ae` | 诊断码命名制 + 公理码命名空间清理 |
| M14-M16 文档化 | `756992b` | KNOWN_LIMITS §十八 + §十九 |
| MINOR 低风险 | `bb7d223` | 8 项低风险代码异味修复 |
| llm_except_frame | `89db9f7` | 黄金快照 else val 改 fail-fast |
| D4 inherit_plugins | `ce56c47` | Union[bool, List[str]] + engine 消费者（另一 session） |
| MINOR 根因修复 | `c4c38ec` | ServiceContext 注入 + _intent_ctx 治理 + _module_metadata_map 统一 + _prompt 加固 |

**测试基线**：1173 passed, 10 skipped

# 代码缺陷复查与修复计划（临时任务文档）

> **状态**：D6/D7/D8/D9/D10 全部完成。剩余 3 个架构决策项（D2/D3/D5）+ 6 项测试相关（暂缓）。
> **性质**：临时文档，全部待讨论项处置完成后删除。

---

## 待讨论项（等待项目负责人决策）

### D2. M4 - request_collect 超时策略
- `thread.join()` 无超时。VM_SPEC §4.2 对超时沉默。
- **问题**：超时值？可配置（policy/config）还是固定？还是无界+心跳？固定值违反"禁止魔法哨兵"。

### D3. M6 - 进程全局 sys.path/sys.modules 与每引擎隔离冲突
- `sys.path.insert` 无清理、非线程安全；`sys.modules` 全局缓存致同名插件跨 project_root 冲突。
- **问题**：接受进程全局加载为文档化已知限制（廉价），还是投入 scoped `importlib` 加载（正确，较大）？

### D5. M10 - 浅引用快照的健全性：接受残余风险 还是 重开 COW 架构决策？
- 浅路径引用快照是已定设计。但 disable-list 本质是打地鼠：`file.remove()` 未禁用、`write_new(同路径)`、子进程触碰 backing 路径都能绕过。
- **问题**：接受 disable-list 不完整性为残余风险，还是重开 COW-vs-浅引用架构决策？

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

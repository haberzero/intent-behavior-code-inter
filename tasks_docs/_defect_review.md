# 代码缺陷复查与修复计划（临时任务文档）

> **状态**：CRITICAL/MAJOR 可决断/MINOR/设计限制/注释清洁/诊断码规范化全部完成。剩余 8 个待讨论项（D2-D3, D5-D10）+ 6 项测试相关（暂缓）。已完成项的详细分析见 git 提交历史。
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

### D6. M13 - `resolve(...) or self._any_desc` 修复范围与严重性
- `01_principles.md §5.3` 明令禁止。16 处不均：A 类(9 处)真违规；B 类(3 处)内建名查找(防御性)；C 类(2 处)推断缺失；D 类(2 处)死代码。
- **问题**：A 类发 ERROR 还是 WARNING？哪个 pass 发？B/C/D 保持原样？改动语义错误集需全量 pytest 评估破坏面。

### D7. M11c - SEM_052 是否覆盖属性/下标赋值目标？
- `obj.f = x` / `lst[0] = x` 当前返回 None 被静默跳过。快照隔离原则要求覆盖，但 spec 示例只展示简单名重绑定。
- **问题**：SEM_052 覆盖简单名重绑定，还是也覆盖属性/下标变异？后者扩大错误集。

### D8. Minor - prelude 重导出过滤标准
- `scheduler.py` 模块导出含 prelude 符号。修复需过滤，但标准未定：provenance？scope 深度？显式导出列表？

### D9. Minor - 通配符 import 冲突处理
- `from mod import *` 冲突静默跳过；`from mod import name` 冲突发 SEM_IMPORT_CONFLICT。不一致。
- **问题**：通配符冲突应 warn 还是静默跳过？

### D10. Minor - cast 无 converter 时 SEM_CAST_NO_CONVERTER
- 目标类型无 converter cap 时 cast 静默未校验（编译期）。
- **问题**："无 converter"意味着"cast 不在编译期检查"（故意宽松）还是"cast 总是无效"（应 warn）？

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

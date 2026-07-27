# 代码缺陷复查与修复计划（临时任务文档）

> **状态**：8 项无歧义缺陷已修复并验证（C1/M1/M8/M9/M11a-b/M12/M17，1176 passed/7 skipped）。M5 前提错误（get_value 不存在，需重新调查）。C2 无歧义但需专项重构。D1-D10 待逐个讨论。
> **日期**：2026-07-24（更新：修复完成）
> **性质**：临时文档，缺陷处置完成后归档或删除。
> **关联**：注释清洁清单 `tasks_docs/_cleanup_inv_*.md`。

---

## 一、总览

| 类别 | 数量 | 说明 |
|------|------|------|
| CRITICAL | 2 | C1（symlink 沙箱）、C2（dispatch_eager 数据竞争） |
| MAJOR | 17 | M1-M17 |
| MINOR | ~25 | 设计异味/边沿/陈旧 |
| **可决断（有明确修复方案）** | ~28 | 无歧义或低歧义 |
| **需讨论（无法从文档/原则决断）** | 10 | 见 §四 |
| **设计限制（非 bug）** | 3 | M14/M15/M16 |

---

## 二、CRITICAL

### C1. 符号链接 entry_file 破坏 project_root 沙箱边界
- **位置**：`core/engine.py:228-232`（`_establish_project_root`）vs `:514-517`（`run`）
- **设计意图**：project_root = 显式 OR entry_dir 的 canonical 父目录（ADR-019 §2，`06_path_system.md` §2 "沙箱边界"）。
- **缺陷**：`_establish_project_root` 对 entry_file 用词法 `resolve_dot_segments()` 后取 parent，再 canonicalize parent；`run()` 另对 entry_file 做 `canonicalize_for_security`（realpath）。符号链接 entry -> project_root（词法父）≠ canonical entry 父目录，入口文件落在 project_root 之外。
- **合理构想**：canonicalize entry_file **之前**取 parent（realpath 幂等，非符号链接场景语义不变）。
- **修复方案**：`_establish_project_root` 改为先 `canonicalize_for_security(entry_file)` 再取 `.parent`。
- **歧义**：低。`06_path_system.md` §2/§4 + validator docstring 明确要求 canonical project_root。
- **异味风险**：无（realpath 幂等）。
- **架构影响**：跨模块--`PathContext.derive_isolated`（`context.py:84`）有同类词法-parent 模式，应共用 canonical-parent helper。
- **需讨论**：否。

### C2. dispatch_eager 后台线程数据竞争（PT-4.7）
- **位置**：`core/runtime/interpreter/llm_executor/_scheduler.py:53-62`
- **设计意图**：`VM_SPEC §3` axiom LLM-1 明确："dispatch 时刻捕获 prompt 内容与意图上下文，后台线程中发起实际调用"。并发 HTTP dispatch 是**预期特性**（`test_concurrent_llm.py` §3.1 验证）。
- **缺陷**：当前后台线程重入 `execute_behavior_expression` -> `vm.run(child)`，在共享 VMExecutor/runtime_context 上重入 `_drive_loop`，与主线程并发改写 `_current_stack`/`step_count`/作用域/intent_ctx。
- **合理构想**：dispatch 时（主线程）预求值 prompt 段，后台线程只跑 `_call_llm`（HTTP）。DDG 保证 `dispatch_eligible=True` 节点依赖已解析，预求值安全。
- **修复方案**：将 `execute_behavior_expression` 拆为"构建 prompt"（同步）+"调用+解析"（异步），后台线程只提交 HTTP 调用。
- **歧义**：低（VM_SPEC §3 + 合规测试 + assignment.py 注释一致确认意图）。
- **异味风险**：minor（需保证 `last_call_info`/`retry_hint`/`_parse_result` 线程安全，局部于 llm_executor 包）。
- **架构影响**：局部（llm_executor 包内）。
- **需讨论**：否。

---

## 三、MAJOR

### 可决断（明确修复方案）

#### M1. 多类型 list 可赋值性用集合相等而非子集
- **位置**：`core/kernel/spec/registry/_assignability.py:63-64`
- **意图**：注释明说"same or subset"（协变子集）；代码用 `{src}=={tgt}`（相等）。多类型 list 访问返回 `any`（设计性宽松），故协变子集内部自洽。
- **修复**：改 `{src_heads} <= {tgt_heads}`（子集）。单行。无测试断言相等行为。
- **歧义**：低。**异味**：无。**架构**：局部。**需讨论**：否。

#### M3. save_state 忽略 sync() 返回值
- **位置**：`core/runtime/host/service.py:81`
- **修复**：检查返回值，挂起时 raise。歧义低（局部），但修复"含义"依赖 M2 决议（若 sync 是残余则删调用而非检查）。**需讨论**：否（局部），但与 M2 耦合。

#### M5. run_isolated 共享 IbObject 实例（隔离破坏）-- ⚠️ 前提错误，需重新调查
- **位置**：`core/runtime/host/service.py:208-220`
- **原分析（subagent）**：inherit_variables 传 IbObject 实例给子引擎，可变状态共享，破坏隔离。修复=深克隆。
- **复核发现（已实证）**：`get_value` 在整个 core/ 中**不存在**（`rg "def get_value" core/` 零结果）。`hasattr(val, 'get_value')` 恒为 False，`initial_vars[name] = val.get_value()` 是**死代码**，变量根本没被传递到子引擎。
- **实际 bug**：不是"共享破坏隔离"，而是"inherit_variables 完全不工作"（get_value 路径死代码）。实际机制与 subagent 分析不符。
- **需重新调查**：`global_scope.resolve(name)` 返回什么？`get_value` 应该是什么（已删除的方法？应为 `to_native()`？）？inherit_variables 的预期数据流是什么？修复方案取决于此调查结果。
- **需讨论**：是（需重新调查后确定修复方案）。

#### M8. request_collect TOCTOU 竞争
- **位置**：`core/engine.py:777-788`
- **意图**：VM_SPEC §4.2 axiom SC-3 要求 collect 恰好一次（重复抛 RuntimeError）。
- **修复**：原子 pop 先认领（锁内 pop，锁外 join+提取）；pop 返回 None 则 raise SC-3 错误。
- **歧义**：低（SC-3 契约明确）。**异味**：无。**架构**：局部。**需讨论**：否。

#### M9. __from_descriptor__ 硬编码 IbFileHandle（子类丢失）
- **位置**：`core/runtime/objects/file_handle.py:98-111`
- **意图**：`__clone_ref__` 正确用 `type(self)`；`__from_descriptor__` 硬编码不一致。反序列化时 `self` 是 IbClass（非实例），应用 `ib_class.name` 查实现类。
- **修复**：`impl_cls = get_ib_implementation(ib_class.name) or IbFileHandle`。描述符格式不变（type 从 ib_class 取）。
- **歧义**：低。**异味**：minor。**架构**：无。**覆盖缺口**：无 disk_backed round-trip 测试，应补。**需讨论**：否。

#### M11a/b. SEM_052 漏报（作用域 + AugAssign）
- **位置**：`core/compiler/semantic/passes/binding_analysis_pass.py:242-249`（a），`:280-290`（b）
- **意图**：`docs/syntax/10_robustness.md:61`"llmexcept 体内禁止写入外部变量"，"外部作用域"含外层函数局部。当前 analyzer 非 ScopedVisitor，只读 module 作用域。
- **修复 a**：analyzer 收集所有外层作用域名（走 scope 链或用 `prior_symbol_bindings`）。修复 b：`_check_assignments_readonly` 增加 `IbAugAssign` 检查。
- **歧义**：a 低；b 低。**异味**：minor。**架构**：局部。**需讨论**：否（a/b）；**M11c 见 §四**。

#### M12. 双诊断 + ERROR/WARNING 不一致
- **位置**：`core/compiler/semantic/passes/_expression_visitors.py:260-318`
- **意图**：CALLABLE_SIG 是硬结构约束->ERROR(SEM_005/003)；FUNCTION(容器写方法)是特化提示->WARNING(SEM_081)。当前 CALLABLE_SIG 同时发 ERROR+WARNING。
- **修复**：SEM_081 条件移除 `CALLABLE_SIG`（只留 `FUNCTION`）。单行条件改。
- **歧义**：低（测试 `test_generics.py:172-184` 明确 SEM_081 为 warning）。**异味**：无。**架构**：无。**需讨论**：否。

#### M17. except X as e 类型为 any（测试锁定不存在的限制）
- **位置**：`tests/e2e/test_e2e_exceptions.py:209`
- **实证**：`e` 实际类型为 `any`（`symbol_resolution_pass.py:372`），**非** Exception。`e.detail`（子类字段）无需强转即可编译运行（已验证）。测试 docstring"e 仅按 Exception 基类解析"是**假的**，强转 workaround 不必要。
- **修复**：测试去掉强转，直接断言 `e.detail`；修正 docstring。设计改进：将 `e` 收窄为捕获类型 X（handler 已声明 `except X`，运行时只绑定匹配异常，sound）。
- **歧义**：低（实际语义可决断）。**需讨论**：否。

### 需讨论（无法从文档/原则决断）- 见 §四
M2、M4、M5(重新调查)、M6、M7、M10、M13、M11c

---

## 四、需讨论项（等待项目负责人决策）

### D1. M2 - sync 语义：保留+实现 还是 移除？
- `SyncManager._wait_for_sync()` 是 `pass`。docstring 描述多上下文协调模型，但架构（§3.6/§8/§11，一引擎一上下文）并不实例化它。M3 的修复依赖此决议。
- **问题**：多上下文 sync 是未来方向特性（保留+实现）还是已放弃方向（移除 API）？文档未表态。

### D2. M4 - request_collect 超时策略
- `thread.join()` 无超时。VM_SPEC §4.2（SC-1..SC-5）对超时沉默。
- **问题**：超时值？可配置（policy/config）还是固定？还是无界+心跳？固定值违反"禁止魔法哨兵"。

### D3. M6 - 进程全局 sys.path/sys.modules 与每引擎隔离冲突
- `sys.path.insert` 无清理、非线程安全；`sys.modules` 全局缓存致同名插件跨 project_root 冲突。
- **问题**：接受进程全局加载为文档化已知限制（廉价），还是投入 scoped `importlib` 加载（正确，较大）？文档未声明 Python 级模块加载的隔离边界。

### D4. M7 - inherit_plugins 模型：bool 标志 还是 selective 列表？
- 类型标注 `Optional[List[str]]` 但代码设 `True`（bool）。字段当前**无消费者**（死字段），但契约破损。
- **问题**：插件继承是 bool(all/none) 还是 List[str](selective)？无 axiom 指定。

### D5. M10 - 浅引用快照的健全性：接受残余风险 还是 重开 COW 架构决策？
- ADR-014/016 已定"浅路径引用快照，不复制字节"。PT-ARCH-27 disable-list 是承诺设计（非临时补丁）。但 disable-list 本质是打地鼠：`file.remove()` 未禁用、`write_new(同路径)`、子进程触碰 backing 路径都能绕过。
- **问题**：接受 disable-list 不完整性为残余风险（按承诺的浅引用设计），还是因健全性顾虑重开 COW-vs-浅引用架构决策？文档说浅引用是最终决定，但健全性顾虑真实且未闭合。

### D6. M13 - `resolve(...) or self._any_desc` 修复范围与严重性
- `01_principles.md §5.3` 明令禁止。但 16 处不均：A 类(9 处)真违规->应发诊断；B 类(3 处)内建名查找(防御性)；C 类(2 处)推断缺失；D 类(2 处)死代码。
- **问题**：① A 类发 ERROR 还是 WARNING？（前向引用/LazySpec 可能瞬时未解析，硬 ERROR 会破坏合法前向引用）② 哪个 pass 发？（早期 pass 见瞬时 None）③ B/C/D 保持原样？④ 单 PR 还是逐 pass 推进？改动语义错误集，需全量 pytest 评估破坏面。

### D7. M11c - SEM_052 是否覆盖属性/下标赋值目标？
- `obj.f = x` / `lst[0] = x` 当前返回 None 被静默跳过。快照隔离原则要求覆盖（对象按引用共享，字段修改破坏快照），但 spec 示例只展示简单名重绑定。
- **问题**：SEM_052 覆盖简单名重绑定，还是也覆盖属性/下标变异？后者扩大错误集，可能破坏现有代码。

### D8. Minor - prelude 重导出过滤标准
- `scheduler.py:578` 模块导出含 prelude 符号。修复需过滤，但标准未定：provenance？scope 深度？显式导出列表？IBCI 无 `__all__`。

### D9. Minor - 通配符 import 冲突处理
- `from mod import *` 冲突静默跳过；`from mod import name` 冲突发 SEM_009。不一致。
- **问题**：通配符冲突应 warn 还是静默跳过（`*` 本就是"尽量导入"）？全 warn 会很吵。

### D10. Minor - cast 无 converter 时 SEM_091
- 目标类型无 converter cap 时 cast 静默未校验（编译期）。
- **问题**："无 converter"意味着"cast 不在编译期检查"（故意宽松）还是"cast 总是无效"（应 warn）？运行时仍经 `receive("cast_to")` 校验。

---

## 五、设计限制（非 bug，仅记录/文档化）

| ID | 位置 | 性质 | 处置 |
|----|------|------|------|
| M14 | test_type_invariants.py:35 | Optional[T] 方法无运行时分发（编译期契约已就位，运行时未接） | 记入 KNOWN_LIMITS；修陈旧 PT-5.1 指针；补运行时负向测试或标 skip |
| M15 | test_scope_semantics.py:98 | IBCI 无 walrus(`:=`)（明确排除） | 确认；删陈旧 PT-5.1 前缀；可同步入 KNOWN_LIMITS |
| M16 | test_scope_semantics.py:174 | SEM_002 禁止 if-block 重声明（明确排除） | 确认；删陈旧 PT-5.1 前缀 |

---

## 六、MINOR 汇总（分类）

### 明确修复（低歧义）
- `engine.py` spawn `isolated` 参数死逻辑（移除）
- `engine.py:347-353` `hasattr`/`setattr` 字符串属性穿透（改协议方法）
- `primitive_initializer.py:276` 防御性回退掩盖配置错误（改 fail-fast）
- `primitive_initializer.py:556-558` 私有属性穿透（封装突破）
- `primitive_initializer.py:677` 陈旧注释（删除）
- `service.py:263-269` `_resolve_isolated_path` 静默回退（传播错误）
- `service.py:78,107` 魔法哨兵 `__EXTERNAL_FILE_REF__`（提常量）
- `host_interface.py` re-export 垫片（违反"禁止 compat shim"，更新调用点或文档化）
- `engine.py:717-723` 子引擎 auto_sniff 硬编码（继承父设置）
- `loader.py:233-241` 插件直接导出类静默跳过（加 warning）
- `interpreter.py:26` 注释与 compat 垫片矛盾（修正）
- `llm_result.py`/`constants.py`/`vm/task.py` re-export 垫片（评估删除）
- `_prompt.py:199-223` stringly-typed 返回（评估统一）
- `llm_except_frame.py:310-315` 黄金快照再克隆失败边沿（加守卫）
- `contract_validator.py:24` "STAGE 7" 陈旧输出（改当前术语）
- `scheduler.py:306,408` 私有字典穿透（加公开方法）
- `_declaration_visitors.py:252-256` SEM_092 双向可赋值（**故意简化，非缺陷**，保留）
- `test_runtime_getitem_contract.py:13` 陈旧 module docstring（更新）
- `test_collection_semantics.py:256` INV-STR-6 未测变异（补测试）
- `test_scope_semantics.py:155` 冗余重复断言（删除）
- `test_e2e_exceptions.py:276` H1 覆盖缺口（补深层栈/finally 路径）
- `test_e2e_llmexcept.py:497` 部分快照协议未验状态（补状态断言）
- `test_meta/test_layering.py:85` 混合测试白名单（已知债，保留至拆分）

### 需讨论（见 §四 D8-D10）
- prelude 重导出过滤标准（D8）
- 通配符 import 冲突（D9）
- cast 无 converter SEM_091（D10）

---

## 七、修复进度与后续顺序

### 已完成（8 项，已提交 `94a5397`，1176 passed/7 skipped）
- ✅ C1（critical）：symlink project_root 沙箱边界
- ✅ M1：多类型 list 可赋值性子集
- ✅ M8：request_collect TOCTOU 原子认领
- ✅ M9：__from_descriptor__ 子类保留
- ✅ M11a/b：SEM_052 作用域 + AugAssign
- ✅ M12：CALLABLE_SIG 双诊断
- ✅ M17：except-as-e 测试修正

### 待处理
1. **C2（critical，无歧义但需专项重构）**：拆分 `execute_behavior_expression` 为 prompt 构建(同步)+调用(异步)。
2. **M5（前提错误，需重新调查）**：`get_value` 不存在，inherit_variables 死代码；需查清预期数据流再定方案。
3. **M3（依赖 D1）**：save_state sync 返回值检查，方案取决于 sync 语义决议。
4. **D1-D10（逐个讨论）**：见 §四。
5. **设计限制 M14-M16**：文档化（KNOWN_LIMITS）。
6. **MINOR 批量清理**：见 §六。
7. **注释清洁（573 处）**：`_cleanup_inv_*.md`，涉及缺陷的注释暂不清。
8. **诊断码/公理编号规范化**：独立工作流。

> 涉及语义错误集的修复（M11/M12/M13）须在分支早期跑全量 pytest 评估破坏面（AGENTS.md 要求）。

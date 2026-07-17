# PENDING_TASKS — 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**——每项都有明确的阻塞原因或前置条件。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-07-17（**G2 内核原生化完成**：ai/ihost/idbg/isys 四模块已提升为 `Provenance.KERNEL_NATIVE + Visibility.IMPORT_GATED`，经 bootstrap 预注册、loader 短路、HostInterface 覆盖保护、late-hydrate 窗口实现；新增 10 个测试，全量 pytest `1157 passed, 7 skipped`。下一项 **G3+G4+G5+G6 磁盘型存储体系（合并单阶段）**。）
>
> **阅读指南**：
> - 标为 `[P1]` 的条目：前置条件已满足，可由 `NEXT_STEPS.md` 随时提升为当前任务
> - 标为 `[P2]`/`[P3]` 的条目：有明确前置链，需按序解锁
> - 标为 `[VISION]` 的条目：远期愿景，当前无明确用户需求推动
> - 标为 `[DESIGN-DEBT]` 的条目：已有部分基础设施但存在未解决的设计冲突
> - 标为 `[SHELVED]` 的条目：明确搁置，有独立文档记录设计思路
> - 标为 `[DONE]` 的条目：已完成，保留供追溯（将在下次清理时移除）
> - 标为 `[GATED]` 的条目：被显式前置 gate 阻塞（见 `NEXT_STEPS.md` 工作模式定论）

---

## 一、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2]

> 本条目的完整规划以此处为准；NEXT_STEPS 中仅保留指针（遵守单点真理规则）。

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅

**具体待做**：
1. **错误信息优化**：`SEM_xxx` 错误码转化为用户友好表述
2. **诊断工具**：符号表/类型绑定/行为依赖图 JSON/dot 导出
3. **性能基准**：编译时间基准测试
4. **CI/CD 集成**：语义分析测试套件纳入 CI

**预估工作量**: 15-20 小时

---

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

---

### PT-SEM-3　二层 IR 路线评估 [VISION]

---

## 二、VM 异步/协程层（L3）[SHELVED]

> **独立设计文档**：`docs/design/COROUTINE_DESIGN_NOTES.md`
> **搁置决策日期**：2026-05-28
> **搁置原因**：当前优先完善多模态功能（Phase 3-5）

> ⚠️ **2026-06-24 全量分析补充**：
> - 搁置理由"dispatch_eager + LLMFuture 已覆盖主要异步需求"有漏洞：`handlers.py` 在 llmexcept 活跃时禁用 dispatch
> - 11 个 `test_e2e_multi_interpreter` 测试与 PT-3.1 相关（已在 P0 修复中解决路径转义问题，测试全绿）

### 阻塞原因
1. 调度器架构需从单根任务升级为多任务挂起/恢复
2. `async`/`await`/`yield` 关键字不在 KEYWORDS 表
3. 快照协议需覆盖协程 yield 点

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 需要协程句柄实现异步等待 |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义 |

### 恢复条件
详见 `docs/design/COROUTINE_DESIGN_NOTES.md §六`。核心前提：多模态 Phase 3-5 稳定后 + 出现明确用户需求。

---

## 三、语言级能力扩展

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

> ⚠️ **2026-06-24 质疑**：原"95% 覆盖"声明未经验证。`primitives.py` 把成员值一律设为名字字符串，数字状态码枚举无法 round-trip。

---

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]

> ⚠️ **2026-06-24 备注**：`__call__` 协议在 3 个文档有 3 种不同定性（KNOWN_LIMITS §一"建议禁用"、AUDIT_REPORT"已知缺陷"、本条目"VISION"），框架应统一。

---

### PT-4.3　语言级协程 [SHELVED]

见 §二 + `docs/design/COROUTINE_DESIGN_NOTES.md`。

---

### PT-4.4　用户类泛型类型参数 [VISION]

---

### PT-4.5　用户类运算符重载 [VISION]

---

### PT-4.7　DDG 并行调度真正接入 VM [DESIGN-DEBT]

> ⚠️ **2026-06-24 修正**：原"snapshot × future-deref"误诊。真实失败模式是 `dispatch_eager` 捕获 `execution_context` 按引用传递给后台线程 → 数据竞争。与 L3 同根因。

---

## 四、设计原则与明确排除方向

### 坚持的设计原则

1. **显式优于隐式**
2. **单点真理**
3. **公理调度 + 单次锁定**
4. **运行时可观测性优先**

> ⚠️ **2026-06-24 备注**：
> - 原则 1 在 `ibci_ai/core.py` 有违反（未探测模型静默 `is_reasoning_model = True`）—— ADR-010 已决策修复方案
> - 原则 4 在多模态设计中有冲突（D3 磁盘卸载透明性 vs 可观测性）—— ADR-007 已裁决

### 明确排除的方向

- ❌ 静态类型检查器作为解释器前置强依赖
- ❌ 为优化独立 LLM 调用而创建多 Interpreter
- ❌ 完整的 HM 风格类型推断
- ❌ AST 字段 + 侧表 + MetadataStore 三处同时存储同一语义事实

> ⚠️ **2026-06-24 备注**："静态检查器非强依赖"排除正变得自相矛盾——4-Phase pipeline 已达 ~1491 行 type_checking_pass。

---

## 五、架构健康改善项

> 来源：2026-06-24 全量分析。**大部分已完成**，此处仅保留未完成项。

### [DONE] PT-ARCH-1 提取 `core/runtime/shared/` ✅
### [DONE] PT-ARCH-2 拆分 `HostInterface` ✅
### [DONE] PT-ARCH-3 移动 `fuzzy_json.py` ✅
### [DONE] PT-ARCH-4 拆分 7 个 god modules ✅（全部 7 个已完成）
### [DONE] PT-ARCH-5 Group 1+2 折叠重复分支 ✅

### PT-ARCH-5 Group 3　CPS/non-CPS 薄提取 [部分 DONE — 薄提取 ✅ / 深统一推迟]
- ✅ 薄提取（2026-06-25）：提取 `LLMExecutorCore._finalize_invoke_result`，4 个 `invoke_*` 后处理统一。
- ⏳ 深统一（3 对 `execute_*`，~100 行/对）仍推迟：需先统一 `_evaluate_segments`/`_cps` 段求值器，~6h，风险较高。无用户需求推动时可继续推迟。

---

### [DONE] PT-ARCH-7　静默吞异常治理 ✅（2026-06-25）
- Phase 1-3：7 处关键修复 + 4 处裸 except: 收窄（core/ 中零裸 except:）。
- Phase 4-5：11 处 `except Exception: pass` → `core_debugger.trace` 可观测化（`_prompt.py`×3 / `base.py`×2 / `_shared.py`×3 / `engine.py` / `interpreter.py` / `media.py`）。`_scheduler.py __del__` 按惯例保持静默。
- 附带：IbDict 缺键 `KeyError` → `InterpreterError` 统一 + 删除一处重复 `__getitem__`。

### [DONE] PT-ARCH-10　剩余 ~24 处 except Exception 审计 ✅（2026-06-25）
- 审计 core/ 的 ~35 处 `except Exception:`：12 处真静默补日志（`runtime_serializer`×4 / `host/service`×2 / `auto_discovery`×1 / `llm_except_frame`×2 / `intent`×1 / `llm_parsing_strategy`×2）；~11 处确认非静默（已 re-raise/log/record）；~4 处编译层错误恢复保留；2 处良性（`module_manager:88` 有 raise、`io:27` stdout best-effort）。
- **结论**：运行时层无一处掩盖真实 bug 的漏网吞异常。

---

### [DONE] PT-ARCH-6 删除死代码 ✅
- `IbStatelessPlugin` 删除
- `IbInteger.__hash__` 修复
- `_check_type` 死分支删除

### [DONE] PT-ARCH-8 → 推迟　`CapabilityRegistry` 类型化键 [P3]
**现状**：字符串键 service locator，无真实多 provider 竞争用例。低优先级。

### [DONE] PT-ARCH-9 → 推迟　`AutoDiscoveryService` 健壮性 [P3]
**现状**：一个 broken plugin 中止全部 discovery。低优先级。

---

## 六、Phase 3 多模态决策 [DONE — ADR-007~012]

> 全部 7 个决策矛盾已通过 ADR 解决：
> - ADR-007: snapshot 策略（DEC-5/6 裁决）+ 代码修复 `type() is` → `isinstance`
> - ADR-008: `register_model` API 形态（D4 裁决）
> - ADR-009: `_call_llm_raw` 引入（D6/DEC-4 裁决）
> - ADR-010: per-model 能力探测（R5 裁决）
> - ADR-011: `runtime/shared/` 叶子包
> - ADR-012: 多模态类型作为普通类名（DEC-1 裁决）

---

## 七、文档健康改善项

> 来源：2026-06-24 全量分析。**部分已完成**。

### [DONE] PT-DOC-1 标注 AUDIT_REPORT 已解决发现 ✅
### [DONE] PT-DOC-2 修复 hub 文档锚点 ✅
### [DONE] PT-DOC-3 IBCI_SYNTAX_REFERENCE 补充 ✅（`@NAME~` + `__payload_prompt__`）
### [DONE] PT-DOC-5 SEMANTIC_COVERAGE_MATRIX 刷新 ✅
### [DONE] PT-DOC-6 VM_SPEC 幽灵引用修复 ✅

### PT-DOC-4　ARCH_DETAILS.md §1.2 更新 [P2]
- "if/while 检测 uncertain → 立即返回空结果"已更新为 BUG #A 后语义 ✅
- 但 §1.2 整体仍需与当前 handler 分包结构对齐

### PT-DOC-7　清理 HISTORY_LOG 旧编号 [P3]
- 4 处引用 KNOWN_LIMITS 旧编号（§十九/§二十三/§二十四/§二十五）→ 死指针

### PT-DOC-8　README 补全 [P2]
- 补测试命令 `python -m pytest tests/ -q --tb=short`
- 补架构概览 + 链接 NEXT_STEPS/COMPLETED
- 加 CONTRIBUTING.md

### PT-DOC-9　评估合并/删除小文档 [P3]
- `FUNC_DESIGN_NOTES.md`（48 行，冻结）→ 评估合并入 KNOWN_LIMITS
- `MULTIMODAL_ANALYSIS_CONCLUSIONS.md`（已归档）→ 评估删除

### PT-DOC-10　TYPE_SYSTEM_DESIGN.md §5.1 更新 [P3]
- "Pass 4/5 SemanticAnalyzer" → 4-Phase pipeline

### PT-DOC-11　VM_AND_INTERPRETER_DESIGN.md §12 更新 [P3]
- "目前无新增 P0/P1/P2" → 更新为当前状态

---

## 八、测试基础设施改善项

> 来源：2026-06-24 全量分析。**部分已完成**。

### [DONE] PT-TEST-1 pytest.ini + CI ✅
### [DONE] PT-TEST-2 层级元测试 + 文件迁移 ✅
### [DONE] PT-TEST-3 MOCK 独立测试 ✅
### [DONE] PT-TEST-4 Area 3 (path) ✅（85 个测试 + 5 个 bug 修复）
### [DONE] PT-TEST-5 BUG #A 回归测试 ✅
### [DONE] PT-TEST-9 IbString.to_bool 越层修复 ✅

### [DONE] PT-TEST-4　覆盖缺口填补 ✅（2026-06-25，5/5 全部完成）

| # | 区域 | 测试数 | 状态 |
|---|------|--------|------|
| 1 | `runtime/serialization/` round-trip | 11 | ✅（+1 反序列化 bug 修复） |
| 2 | `engine.py` 生命周期 | 7 | ✅ |
| 3 | `kernel/__getitem__` 契约 | 13 | ✅（+ IbDict 错误统一） |
| 4 | `host/service.py` collect 委托 | 4 | ✅ |
| (Area 3) | `runtime/path/` | 85 | ✅（早前完成，+5 盘符 bug） |
> 详见 `docs/COMPLETED.md` 2026-06-25 条目。本会话累计 +46 测试，暴露并修复 2 个潜伏回归 bug。

### PT-TEST-6　删除死 fixtures + 统一 MOCK 前缀 [P3]
- 3 个 orphan fixtures 无测试导入
- `AI_SETUP` 重复定义

### PT-TEST-7　清理 stale 引用 [P3]
- `tests/kernel/conftest.py` 引用不存在的文件
- `tests/COVERAGE_MAP.md` 计数过时

### PT-TEST-8　修复测试命名违规 [P3]
- 6 个 `TestM2*`/`TestD3*` 类名违反 `tests/README.md` 规范

---

## 九、media Phase 4 前置技术债（2026-06-25 三轮架构审计）

> **背景**：2026-06-25 三轮架构审计（详见 `docs/COMPLETED.md` 当日条目）发现：当前 media 内存实现是"哑的"（两个潜伏 bug 致字节静默丢失）、路径系统严重碎片化、ADR-009 的分叉前提被证伪；第三轮确立了**变量存储模型**框架（ADR-016）；P0-1 完成后复审又发现路径模块层位置遗留违规（ADR-017）。
> **治理决策**：ADR-013（修订，协议驱动分发）/ ADR-014（修订，磁盘型 handle，砍 MemoryBacking）/ ADR-015（路径统一为强制前置）/ **ADR-016（变量存储模型，上层治理）** / **ADR-017（路径模块层位置重构，已实现）**。
> **工作模式**：受 `NEXT_STEPS.md ⛔ 工作模式定论` 约束——禁止 compat shim / 胶水 / tricky / 过程式硬编码分发；**潜伏 bug 不允许过渡修复**，必须随存储模型架构（PT-ARCH-17/18）统一修复。
> **执行序列**：见 `NEXT_STEPS.md` 的 **PT-ARCH-21（ADR-019 路径与插件模型重设计）**。

> ⚠️ **2026-07-13 重大重构**：经 5-agent 交叉验证 + 多轮研讨，本节原"路径统一"实为**模型重设计**。立 [ADR-019](decisions/ADR-019-path-and-plugin-model-redesign.md) 为正本。**下方 PT-ARCH-19/20 的逐文件:行清单已被 ADR-019 吸收**：
> - **已完成且保留**：P0-A（SnapshotLayout BUG）、P0-B（3 能力测试）、D2（canonicalize_for_security 规范化）。
> - **需回退/改造**：D1''（root 必填→可选）、C1（方案 B entry_file→合成 `__string_exec__.ibci`）。
> - **机械清理项（P0-C~J + P0-L）**：转入 ADR-019 阶段 D（因组件本身要重构，先清理再重构=浪费）。
> - **隔离语义**（D5/derive_isolated）：反转（子必须在父 proj_root 内），旧测试删除。
> - **本节以下内容作为历史档案保留**（文件:行仍可参考），但**执行以 ADR-019 + NEXT_STEPS PT-ARCH-21 序列为准**。

### ✅ [主体完成] PT-ARCH-21　路径与插件模型重设计（ADR-019）

> 正本：`docs/decisions/ADR-019-path-and-plugin-model-redesign.md`。实现序列（阶段 A 路径核心 / B 插件分离 / C 隔离修订 / D 机械清理）：见 `NEXT_STEPS.md` PT-ARCH-21。
> 取代 ADR-018 的 D1/D5/CWD 上界/D4 穿透。取代下方原 PT-ARCH-19/20 的执行计划（保留为历史档案）。
> **2026-07-13 进度**：阶段 A/B/C/D 已实现并提交（`64cb49d`）。交叉验证发现的 R1/G1/B1/B2/Gate-A1 已修。以下为本轮**明确延后/预留**项（负责人指示：插件内部 path/os 待研讨后再处理）。

#### ✅ PT-ARCH-21-FU：路径整合收尾（已完成）

**[已完成] 插件内部 path/os 统一化**
- ✅ `core/project_detector.py` — 内部路径构造全部 IbPath 化（`IbPath.from_native` / `/` / `parent` / `to_native`）；FS 查询（isdir/isfile）保留；删除死方法 `is_valid_project_root`。
- ✅ `core/runtime/module_system/discovery.py` + `loader.py` — 确认处于 Python importlib 边界，保留原生路径；移除 `__init__` 中冗余的 `os.path.abspath`，添加边界注释。
- ✅ `ibci_modules/ibci_file/core.py` — `os.path.relpath` 统一为 `safe_relpath`；`_read_media_bytes` 扩展名从已解析原生路径取。
- ✅ `core/runtime/rt_scheduler.py` — 确认 `dispatch()` 零调用方、`spawn()` 隔离分支已不可达（隔离执行改为新建 Engine）；一并删除死代码及 `ExecutionRequest`/`ExecutionSignal`。

**[预留·仍不实现] ADR-019 Open 项**
- [ ] 全局 ibci.json 查找（global_plugin 的全局源）。
- [ ] 全局 config 文件（plugin_paths 全局兜底）。
- [ ] CWD 的实际使用（`engine._cwd` 已保存，待权限系统设计后启用）。
- [ ] 隔离的外部 zone 配置（未来 policy 细粒度：允许特定子脚本读/运行指定外部位置）。
- [ ] plugin_path 细粒度权限（本轮：只读特权 + 写禁；细粒度待权限系统）。

**[已完成] 覆盖缺口测试**
- ✅ plugin 发现 e2e：`tests/e2e/test_e2e_plugin_discovery.py` 验证 `ibci.json` 的 `plugin_paths`/`global_plugin` 路径可被 `import` 解析，且显式配置抑制嗅探。
- ✅ 隔离继承 e2e：`tests/e2e/test_e2e_isolation_plugin_inheritance.py` 验证子脚本通过 `ihost.run_isolated` 可导入仅父项目拥有的插件。

**[已知限制·记录]**
- R4：`isys.entry_path()` 在 run_string 下返回合成 `__string_exec__.ibci`（无害 cosmetic）。
- R1'：`_load_plugins` 公理发现面扩大（修复，但可能暴露同名公理冲突）。
- **SDK 测试 flake（观察中，未复现）**：`tests/sdk/test_check_plugin.py` 在完整套件运行时**偶发**失败（不同次不同测试，如 `test_param_count_mismatch`）。调查结论：① `check_plugin` 声明且实现上**不依赖 core.\***（`ibci_sdk/check.py:19`，纯 importlib 反射），故 ADR-019 路径改动逻辑上不影响其校验；② 单独跑稳定（8/8）、压测 10 次稳定（0/10），仅编辑期快速连跑偶发——疑似 sys.path 操控竞态或 spawn 测试线程泄漏（测试基础设施层面）；③ **未捕获具体错误信息**（不再复现），**未做"旧代码对比"判定性实验**。属插件/SDK 范畴，待研讨后决定是否加固 `_load_module`（唯一模块名 + sys.modules 清理）。

---

### 🔴 PT-ARCH-22：全项目文件命名清理（ADR-020 衍生，负责人 2026-07-13 指令）

> 起因：ADR-020 设计中发现 `file.py` 命名隐患——影子化 Python 内建（Py2 `file`）、过于笼统、区分度不足、在 core 层有危险性。负责人指令：**全面排查整个 ibci 项目里类似过短/欠层次/欠区分度/影子化内建的代码文件命名**，做一轮全方位清理。

**排查范围与判定准则**：
- **影子化 Python 内建/关键字**：如 `file.py`、`string.py`、`types.py`、`code.py`、`io.py`、`time.py`（与 stdlib 撞名 → import 歧义/阴影）。
- **过短/欠区分度**：单字母或极短名（`a.py`、`x.py`）、纯领域通用词在 core 层（`base.py`、`core.py`、`path.py`、`main.py` 是否恰当需逐处判断）。
- **跨包重名混淆**：同名文件散布多包（如多个 `__init__.py` 之外的 `core.py`/`base.py`/`utils.py`），降低可导航性。
- **层次不足**：名字未反映所属抽象层或职责。

**待做**：
- [ ] 全仓扫描（`glob **/*.py`）产出命名清单 + 按上述准则标记可疑项。
- [ ] 逐项裁决：保留 / 重命名（附迁移影响：import 站点、测试、文档）。
- [x] **ADR-020 FileHandle 命名已定**（2026-07-13）：Python axiom/值类文件用 `file_handle.py`（非 `file.py`）；IBCI 模块名保留 `file`。其余可疑命名待本任务扫描裁决。
- [ ] 重命名执行（机械迁移 + 全量 pytest 守护）。
> **排期（负责人 2026-07-13 确认）**：暂缓。PT-ARCH-23 之后或独立窗口执行。命名隐患与 ADR-020 实现解耦，不阻塞。

---

### 🔴 PT-ARCH-23：内核原生化 + 磁盘型存储模型 + 类型化 flag 轴（ADR-020 + ADR-021 + P0-2 + P0-3 协同里程碑）

> **负责人 2026-07-17 规划重排**：① 所有核心模块（ai/ihost/idbg/isys/file）的内核迁移**同步执行，同一里程碑内完成**（不分子批）；② ADR-020 与 P0-2/P0-3 **强耦合，协同设计**（FileHandle = ADR-016 磁盘型基类的落地 = P0-3 media 的父类）；③ **经 flag/state 碎片化审计立 [ADR-021](decisions/ADR-021-typed-provenance-visibility-storage-axes.md)，落地顺序重排为 G1→G1.5→路径收尾→G2→G3+G4+G5+6（合并）**；④ file 相关模块全 import-gated；⑤ FileHandle 具体 API 延后到实现期细化。
>
> **本里程碑整合**：ADR-020（内核原生边界重划）、ADR-021（类型化来源/可见性/存储轴）、P0-2（ADR-016 存储模型基础设施）、P0-3（ADR-014 media 重建为磁盘型）。ADR-021 修正 ADR-020 G2 的 `is_user_defined` 写法。

#### 依赖图与任务分配（重排，2026-07-17）

```
G1 重分类基础设施（ADR-020 A/C/D/E）✅ 已完成 2026-07-17
   │
   └─→ G1.5 数据结构迁移改善（ADR-021：三枚举 Provenance/Visibility/StorageModel，
   │      Symbol.metadata 清理，is_llm 删除，序列化同步）✅ 已完成 2026-07-17
   │        └─→ 路径整合收尾（PT-ARCH-21-FU）✅ 已完成 2026-07-17
   │             └─→ G2 ai/ihost/idbg/isys 内核原生化 ✅ 已完成 2026-07-17
   │             │      （bootstrap 预注册；provenance=KERNEL_NATIVE + visibility=IMPORT_GATED；
   │             │       HostInterface 覆盖保护；late-hydrate 窗口）
   │             │      └─→ G3+G4+G5+G6 磁盘型存储体系（合并单阶段，不可拆分）★ 当前最紧要
   │             │            G3 存储模型机制（P0-2：消费 G1.5 的 storage_model 字段）
   │             │            → G4 FileHandle（ADR-020 B，依赖 G3）
   │             │            → G5 media→FileHandle 子类（P0-3）
   │             │            → G6 file 模块内核原生化（ibci_file 消亡）
```

#### 执行子序（里程碑内阶段，每阶段完整测试 + 干净切口，禁 shim）

**阶段 1 — 重分类基础设施（G1，ADR-020 E/A/C/D）** ✅ **已完成 2026-07-17**：见 `NEXT_STEPS.md` G1 条目 / `COMPLETED.md` 2026-07-17。

**阶段 2 — 数据结构迁移改善（G1.5，ADR-021）** ✅ **已完成 2026-07-17**：见 `NEXT_STEPS.md` G1.5 条目。

**阶段 3 — 路径整合收尾（PT-ARCH-21-FU）** ✅ **已完成 2026-07-17**：待做项见上方 PT-ARCH-21-FU。

**阶段 4 — G2 ai/ihost/idbg/isys 内核原生化（ADR-020）** ✅ **已完成 2026-07-17**：bootstrap 预注册 4 模块（经 loader 短路，零文件移动）；**`provenance=KERNEL_NATIVE + visibility=IMPORT_GATED`** → 恒可解析/不可覆盖 + import-gated 保留；HostInterface 覆盖保护；late-hydrate 钩子随 ai 建。全量 pytest `1157 passed, 7 skipped`。

**阶段 5 — G3+G4+G5+G6 磁盘型存储体系（合并，ADR-016/014/020）** ★ **当前最紧要**：不可拆分。
- **G3 存储模型机制（P0-2）**：消费 G1.5 的 `storage_model` 字段；磁盘协议族（lazy materialize/path-payload/path-snapshot，**方法名本阶段设计期定**）；`deep_clone.py:89` isinstance 修复 + 磁盘型浅拷贝分支；序列化器磁盘型分支 + 便携描述符。
- **G4 FileHandle（ADR-020 B）**：新建 `core/kernel/axioms/primitives/file_handle.py`（FileHandleAxiom，零 I/O）+ `core/runtime/objects/file_handle.py`（IbFileHandle，持 IbPath+backing）+ bootstrap 绑定；FileBacking/GeneratedBacking；创建经 resolve_path + canonicalize 沙箱；修既有违规 media.py:72-73。
- **G5 media→FileHandle 子类（P0-3）**：IbAudio/IbImage/IbVideo 改 (IbFileHandle)；删 media_storage.py；改 ibci_file read_* 返回 FileBacking（零拷贝）。
- **G6 file 模块内核原生化**：ibci_file 插件消亡；file 模块（free 函数 open/read/write）内核原生 + import-gated；FS 操作落 runtime 值类原生方法。

#### 验证
- 每阶段全量 pytest 0 failure；机械门槛（rg 零散点 os.path、零 compiler→runtime 反向依赖、零平 bool flag 重载残留）。
- 阶段 5 收尾：MOCK e2e（file.read_audio → FileHandle → @~ $x）端到端；snapshot/serialize round-trip（暴露过潜伏 bug）。
- 完成门槛：再次交叉检验（subagent）确认零残留 compat 垫片/零"核心层插件"中间态/零 flag 碎片化/FileHandle 体系自洽。

#### 强耦合说明（记录）
- **不可拆分**：G3/G4/G5/G6 是 disk-backed 变量体系的同一件事——P0-2 是机制、FileHandle 是基类、P0-3 是子类、file 是用户入口。各自独立做会产生 compat 垫片（违 ⛔#1）。
- **G1.5 与 G3 的边界（铁律）**：G1.5 的 `storage_model` 字段**仅落地，禁止任何 workflow 读取/分发**（默认写死 MEMORY_BACKED）；分发逻辑（deep_clone/序列化器分支）留待 G3 真正启用——避免 G1.5 变成"G3 半成品"。
- **可独立**：G1（重分类基础设施）、G2（内核原生化）与存储正交。
- **命名清理（PT-ARCH-22）**：本里程碑之后做（file_handle.py 已定，其余待扫）。

---

### [历史档案] 以下为原 PT-ARCH-19/20 逐文件:行清单（已被 ADR-019 吸收，仅作参考）

### 🔴 [重开-进行中] PT-ARCH-19　路径模块层位置重构（分层完成，统一未彻底 + 1 BUG）

> 测试基线：1070 passed（但 3 新能力零测试覆盖，BUG 因此漏网）。
> **2026-06-25 双轮交叉检验（8 subagent）重开**。分层搬迁与 realpath 收口达标，但"真正完全统一、无妥协"未达成，且引入 1 个实锤 BUG。
> **下个 session 续作：按下方"逐文件:行清单"逐项处理，每项配测试，完成门槛为再次交叉检验通过。**

**已达标（保留，勿动）**：3 层分工（base/kernel/runtime）；compiler→runtime 违规消除；realpath 收口至 `canonicalize_for_security`；3 新能力已建并被调用；base/source_manager 迁 IbPath。

#### P0-A：SnapshotLayout BUG（必须立即修，已实证）
- [ ] **`core/kernel/path/snapshot.py:23`** — `asset_dir_for`：`return save_path + ".assets"` → `IbPath.__add__` 是路径 join，产出 `state.json\.assets`（文件当目录），旧契约是 `state.json.assets`（同级）。**修法**：`return IbPath.from_native(save_path.to_native() + ".assets")`（字符串拼接，再包 IbPath）。
  - **2026-07-13 5-agent 复核**：BUG 机制已逐行证实（`ib_path.py:289` `__add__` 委托 `join`，`.assets` 经 `_normalize` 不剥离前导点 → join 为子段）。
  - **运行时影响（已证实）**：win32 首次 save_state 触发 `PermissionError`/`NotADirectoryError`；跨版本 load_state 静默丢 assets。BUG 漏网根因 = SnapshotLayout 零测试覆盖。
  - `asset_file`（:28，`asset_dir / f"{uid}.txt"`，用 `__truediv__`）**已确认不受影响**——修 :23 后下游自愈。
- [ ] **（剥离，非 P0-A 范围）uid 加固**：`snapshot.py:28` 的 `uid` 未校验，含 `/`/`..` 会路径穿越。当前 uid 是内部 hash 不可利用。**单列为后续 hardening 项**，不塞进 P0-A 止损（避免范围蔓延）。
- [ ] **（订正误报）`resolver.py:137` 非 BUG**：`_probe_file(self, base_path: str)` 签名证明 `base_path` 为 str，`base_path + ext` 是字符串拼接（功能正确）。属 P0-H 迁移项（IbPath 化），**不并入 P0-A 止损**。

#### P0-B：测试缺口（必须补，是 BUG 漏网原因）
- [ ] **`tests/runtime/test_path.py`** — 补 `TestCanonicalizeForSecurity`（验证 realpath + IbPath 返回、相对输入、符号链接场景）。
- [ ] **`tests/runtime/test_path.py`** — 补 `TestDeriveIsolated`（验证 (entry, root=dirname(entry)) 契约、无 parent 退化、与 `test_run_isolated_absolute_path_still_works` 语义一致）。
- [ ] **`tests/runtime/test_path.py`** — 补 `TestSnapshotLayout`（验证 `asset_dir_for` 产出同级目录、`asset_file` 路径；**含修 BUG 后的回归断言**）。
- [ ] **`tests/runtime/` 或 `tests/e2e/`** — 补 `save_state`/`load_state` 端到端（含 assets 外化，触发 SnapshotLayout，守护 BUG）。

#### P0-C：PathContext 真正落地（D4，消灭空架子）
- [ ] **`core/engine.py`**（`__init__` + `run()`）— 构造 `PathContext(entry_dir, project_root)`，存为 `self._path_ctx`；向下传递给 scheduler/resolver/permissions/interpreter。
- [ ] **`core/compiler/scheduler.py:42-43`** — 接收 PathContext（或 `.project_root`），删除 `self._root_ib = canonicalize_for_security(...)` + `self.root_dir = ...` 私有派生。
- [ ] **`core/compiler/parser/resolver/resolver.py:27-28`** — 同上。
- [ ] **`core/runtime/interpreter/permissions.py:16-17`** — 同上（`self._root_path` 改从 PathContext 取）。

#### P0-D：CHILDBOOT 双轨清除
- [ ] **`core/runtime/rt_scheduler.py:68-70`** — 删除死代码内联备份 `root_dir = os.path.dirname(os.path.abspath(artifact))`（与 `PathContext.derive_isolated` 同公式；在 run_isolated/spawn_isolated 链路不可达；`dispatch()` 唯一潜在触发者零调用）。

#### P0-E：check() 双轨统一
- [ ] **`core/engine.py:438`** — `abs_entry = os.path.abspath(entry_file)` 改为 IbPath 规范化（与 `run()`:320 / `compile()`:363 一致），并登记 `_entry_file`/`_entry_dir`。

#### P0-F：CWD 兜底移除（ADR-018 D1）
- [ ] **`core/engine.py:74`** — `_root_src = root_dir if root_dir else os.getcwd()` 删除 CWD 分支；退化统一到 entry_dir（见 PT-ARCH-20 D1/D3）。
- [ ] **`core/engine.py:71-73`** — 删除"CWD 兜底保留至……"过渡注释。

#### P0-G：三重规范化链消除
- [ ] **`core/compiler/scheduler.py:126`** — `entry_file = os.path.abspath(entry_file)` 删除（engine 上游已规范化，二次 abspath 冗余且引入 CWD 锚定）。

#### P0-H：ModuleResolver SSOT 落实（内部构造层接 IbPath）
- [ ] **`core/compiler/parser/resolver/resolver.py:4`** — `IbPath` 导入目前是死的；要么删除，要么在下方构造层真正使用（推荐后者）。
- [ ] **`core/compiler/parser/resolver/resolver.py:77`** — `os.path.dirname(os.path.abspath(context_file))` → IbPath.from_native + parent。
- [ ] **`core/compiler/parser/resolver/resolver.py:82`** — `base_dir = os.path.dirname(base_dir)` → `.parent`。
- [ ] **`core/compiler/parser/resolver/resolver.py:87`** — `os.path.join(base_dir, rel_path)` → IbPath `/`。
- [ ] **`core/compiler/parser/resolver/resolver.py:95`** — `os.path.join(self.root_dir, rel_path)` → IbPath `/`。
- [ ] **`core/compiler/parser/resolver/resolver.py:143`** — `os.path.join(base_path, '__init__' + ext)` → IbPath 构造（消除字符串 `+ ext`）。

#### P0-I：abspath 收口 + module_system/project_detector 接入新轨
- [ ] **`core/project_detector.py:56,75,175`** — `os.path.abspath` → IbPath；全文 `os.path.join/dirname`（:57,81,87,92,116,121,143,148,153,155,176,183）接 IbPath。
  - **2026-07-13 订正**：原清单误列 `:184`，实际 `:184` 是 `os.path.isdir`（FS 查询，合法边界，不动）。原"~14 处"实为 12 处 join/dirname + 3 处 abspath。
- [ ] **`core/runtime/module_system/discovery.py:19`** — `[os.path.abspath(p) for p in search_paths]` → IbPath。
- [ ] **`core/runtime/module_system/loader.py:24`** — 同上。
- [ ] **`core/runtime/module_system/discovery.py:52,56,88,104,108`** + **`loader.py:185,190,197`** — os.path.join/dirname/basename 评估迁移（部分为 os.walk/sys.path 互操作边界，需逐处判断）。
- [ ] **`core/compiler/scheduler.py:96`** — `os.path.join(self.root_dir, "__init__.ibci")` → IbPath `/`。

#### P0-J：死代码清理
- [ ] **`core/runtime/interpreter/permissions.py:1`** — 未用 `import os`（确认 canonicalize_for_security 后是否还需 os；若不需则删）。
- [ ] **`core/runtime/interpreter/execution_context.py:1`** — 未用 `import os`。
- [ ] **`core/runtime/interpreter/module_manager.py:6`** — 未用 `import os`。
- [ ] **`core/runtime/interpreter/module_manager.py:43,49`** — 死字段 `self.root_dir`（默认 `"."`，CWD 模式；构造时接受但永不读取）。
- [ ] **`core/runtime/interpreter/intrinsics/meta.py:2`** — 未用 `import os`。
- [ ] **`core/extension/auto_discovery.py:18`** — 死导入 `from pathlib import Path`。
- [ ] **`core/extension/auto_discovery.py:73,85,89`** — os.path 用法（与 BuiltinPaths 三轨混乱）。

#### P0-K（附带，非路径，但违反全局"禁兼容层"标准）
- [ ] **`core/runtime/interpreter/constants.py`** — 显式 `# 向后兼容垫片` 重导出。
- [ ] **`core/runtime/interpreter/llm_result.py`** — 同。
- [ ] **`core/runtime/host/host_interface.py`** — 同。
- [ ] **`core/runtime/vm/task.py:28-30`** — "重新导出以保持向后兼容"。
> **2026-07-13 决策**：此 4 处与路径无关，与 media Phase 4 无关。**从完成门槛 ⑥ 剥离**——不再作为 PT-ARCH-19 的通过条件（避免门槛含被搁置项导致自相矛盾）。单列为独立技术债 track，由负责人另行排期；不堵 P0-1 完成判定。

#### P0-L：5-agent 完备性审计新增漏项（2026-07-13）

> 对抗式完备性审计（rg 全仓扫描）发现原清单"零碎片化"声称不成立。以下为原 P0-A~K 漏列的路径碎片化，必须并入收尾。

- [ ] **`ibci_modules/ibci_file/core.py`（整文件遗漏）** — 用户可见文件 API，含 `os.path.relpath`（:102,:127，与 canonical `safe_relpath` 平行实现）、`os.path.join`（:95）、`os.path.splitext`（:211）。**这是 IBCI 脚本可见的路径行为，优先级高于纯内部清理。**
- [ ] **`core/runtime/interpreter/interpreter.py:1`** — 死 `import os`（body 零 `os.` 命中）。原 P0-J 漏列。
- [ ] **`core/compiler/scheduler.py:13`** — 死 `IbPath`（`from core.kernel.path import IbPath, ...`，body 仅用 PathValidator/ModuleNameSpace/safe_relpath）。原 P0-H 只列了 resolver.py:4。
- [ ] **`core/runtime/interpreter/permissions.py:5`** — 死 `IbPath`（body 仅用 PathValidator）。原 P0-H 漏列。
- [ ] **`core/runtime/rt_scheduler.py:83`** — `plugins_path = os.path.join(root_dir, "plugins")`，**消费了 P0-D 要删的死 `root_dir`**。P0-D 删除前必须先处理此下游，否则断链。
- [ ] **`ibci_sdk/check.py`** — 多处 `os.path`（:64,73-81,141,244-254）。文件头声明"不依赖 core.*"——需**显式排除或并入**（二选一，当前是沉默遗漏）。
  - **✅ 2026-07-13 负责人裁决：显式排除**。`ibci_sdk` 是不介入 core 的独立工具；其 `os.path` 用法不视为路径碎片化。文档注明边界即可，不纳入清理。
- [ ] **（P1，本轮推迟）`main.py:9`** — `os.path.dirname(os.path.abspath(__file__))` 装根（sys.path 注入），违反"BuiltinPaths 唯一 `__file__` 交互点"。注：此处运行于 engine 构造前，需评估能否经 BuiltinPaths 或显式排除。
- [ ] **（P1，本轮推迟）`main.py:29`** — `os.path.splitext(os.path.basename(path))[0]` 模块名派生；`ModuleNameSpace` 声称集中化模块↔路径映射，此处是平行实现。
- [ ] **（P1，本轮推迟）`core/runtime/module_system/discovery.py:109`** — `internal_name = f"ibci_{parent_dir}._spec"` 字符串构造模块名，绕过 ModuleNameSpace。原 P0-I 列了 :104,:108 漏了 :109。
> **2026-07-13 优先级裁决**：P0-L 的 P0 项（`ibci_file/core.py`、`rt_scheduler.py:88`、3 处死 import）本轮做；P1 项（main.py × 2、discovery.py:109）推迟到 media Phase 4 前——不阻塞 P0-2/P0-3，且 main.py 预引擎操作风险较高需单独评估。
> **完备性结论**：原清单对"compiler/runtime/kernel 8 文件"逐行准确（97.2%），但"零碎片化"声称在 repo 边界（`ibci_modules/`/`ibci_sdk/`/`main.py`）被证伪。P0-L 补全后方接近真正完备。

---

### 🔴 PT-ARCH-20　路径概念澄清与 project_root 统一 [P0 / ADR-018]

> 2026-06-25 路径概念交叉检验（3 subagent）发现主侧 project_root 严重混淆。**5 项决策已由项目负责人确认，固化为 ADR-018**。下个 session 按 ADR-018 + 下方"逐文件:行清单"执行。
> **2026-07-13 5-agent 补充**：发现 D1↔D5 逻辑空转 + 隐藏依赖（见下方"设计决策"与"依赖图"）。

**5 路径概念健康度（收敛裁决）**：概念 4（child entry）/ 5（child project_root）🟢 健康，**无需改动**；概念 1（CWD）/ 2（main entry）/ 3（project_root）需按下文统一。

#### ⚠️ 设计决策（D1/D5 开工前必须定，2026-07-13 新增）

> **D1↔D5 逻辑空转（已识别）**：`run_string`/`compile_string` 用 tempfile，D1 让 `project_root` 退化为 `entry_dir`=tempdir；而 D5 说"子锚点默认改用 project_root（而非 tempdir）"——在 D5 自己的目标场景里 `project_root == tempdir`，**D5 自我抵消，实际啥也没改**。`run_string` 有 77 个调用点（含测试），非边角案例。

**✅ 2026-07-13 负责人裁决（已定）**：
- **采用方案 B（解耦 entry_dir 与 entry_file）**：`compile_string`/`run_string` 把 `entry_dir` 设为 **project_root**（有意义），`entry_file` 仍为 tempfile（源码所在）。`_resolve_isolated_path` 永远用 `entry_dir`，**无 if/else、无标志位**（符合工作模式定论第 4 条）。正常 `run(entry_file)`：`entry_dir = entry_file.parent`（§6.1 契约不变）。
- **D1''（最严格显式 root）**：`root_dir` 成为 `IBCIEngine.__init__` 的**必填参数**（移除 `Optional[str] = None` 默认值与 CWD 兜底）。负责人指令"尽可能使用足够强制且明确的 root 配置"。
- **可行性探查（2026-07-13，零改动只读）已通过**：
  - `SourceManager`（`core/base/source/source_manager.py`）按 canonical file path 键化，**不依赖 entry_dir** → 方案 B 不破坏源码管理。✓
  - `entry_dir` 流向：`engine._entry_dir`(:323/:367) → `execution_context._entry_dir`(:49/:170) → `get_entry_dir()`(:251) → `_resolve_isolated_path`(service.py:234) + `PathResolver`。可独立覆盖。✓
  - **CWD 兜底（engine.py:74）实为死代码**：全仓 44 处 `IBCIEngine(` 调用**全部显式传 `root_dir=`**（含 main.py:129 经 `detect_project_root` 探测后传入）。**零调用方依赖 None→CWD 兜底**。→ D1'' 移除兜底**不破坏任何现存调用方**。
  - **D1'' 溶解了 subagent 5 的"__init__ 重构"顾虑**：顾虑基于"root 延迟到 run()"假设；D1'' 让 root 在构造期就绑定，`__init__` 的 eager 消费（:95/:113/:128）天然兼容，无需重构 init 时序。

**实现序列（D1'' + 方案 B 落地）**：
1. **第一步（D1'' + D2 合并）**：`root_dir` 改必填；移除 CWD 兜底；规范经 `PathValidator.canonicalize_for_security`（D2：解 symlink，与 scheduler/resolver/permissions 同源）。
2. **第二步（P0-C/D4 PathContext 落地，吸收方案 B）**：PathContext 承载 `entry_dir + project_root`；`run()` 构造 `(entry_dir=entry_file.parent, project_root=root)`，`compile_string`/`run_string` 构造 `(entry_dir=root, project_root=root)`。方案 B 因此天然实现（无 hack）。

> 当前 D5 草案（`_entry_is_tempfile` 标志 + `if 标志: project_root else: entry_dir`）**作废**——方案 B 用 entry_dir 语义本身区分，无需标志。

#### 依赖图（订正"并行"误导，2026-07-13 新增）

原 `NEXT_STEPS.md` 把 P0-C~K + D1~D5 列为并行块，**隐藏了 2 条软依赖**：
- **D1 ← D4（PathContext）**：D1 要求 `project_root` 延迟到 run() 确立（`engine.__init__` 当前在 :95/:113/:128 立即消费 root）。D4 的 PathContext 是承载该延迟 root 的自然位置。**D1-done-right 需 D4 先落地。**
- **D5 ← {D1, D4}**：D5 读 `_entry_is_tempfile` 选锚点，依赖 D4 把 project_root 传到 `_resolve_isolated_path`，且依赖 D1 的 project_root 定义已定。
- **P0-L `rt_scheduler.py:88` ← P0-D**：P0-D 删死 `root_dir` 前，必须先迁移 `:88` 的 `plugins_path` 消费点，否则断链。
- **无硬循环依赖**；P0-A / P0-B 与 P0-C 系列无数据依赖，可真并行。

#### D1：CWD 兜底移除（退化统一 entry_dir）
- [ ] **`core/engine.py:74`** — 见 PT-ARCH-19 P0-F。
- [ ] **`core/engine.py` `__init__`/`run()`** — project_root 的确立时机调整：entry_dir 在 run() 才知，故 engine 需在 run() 时（或 PathContext 构造时）确立 project_root；无 entry_dir 时显式报错（不再 CWD 兜底）。

#### D2：project_root 规范化统一（解 symlink，与下游同源）
- [ ] **`core/engine.py:75`** — `IbPath.from_native(_root_src).resolve_dot_segments()` 改为 `PathValidator.canonicalize_for_security(_root_src)`（解符号链接），使 engine.root_dir 与 scheduler/resolver/permissions 同源，消除 symlink 基准分裂。
- [ ] 核查 **`ibci_modules/ibci_isys/core.py:62-67`** — `isys.project_root()` 返回 permission.root_dir（已 realpath）；D2 后与 engine.root_dir 一致（同步验证）。

#### D3：静默退化消除
- [ ] **`main.py:104-105,108-109`** — `hasattr(args,'verbose')` 守卫是死代码（`--verbose` 未注册）；改为注册 `--verbose` 或**无条件 stderr 警告**退化。
- [ ] **`main.py:107`** — 退化目标 `os.path.dirname(os.path.abspath(args.file))` 保留（= entry_dir），但与 engine.py 统一（D1）。
- [ ] **`main.py:43-86`** — argparse 配置注册 `--verbose`（若走该方案）。

#### D4：PathContext 真正落地（同 PT-ARCH-19 P0-C）
- 见 PT-ARCH-19 P0-C 的 4 处文件:行。

#### D5：run_string 场景子 entry 锚点（默认 project_root + 预留用户覆盖接口）
- [ ] **`core/engine.py:286-288`** — `run_string`/`compile_string` 创建 tempfile 处：增设标记 `_entry_is_tempfile = True`（或等价机制），标识此 entry 非用户语义文件。
- [ ] **`core/runtime/host/service.py:234`** — `_resolve_isolated_path`：当父 entry 是 tempfile（`_entry_is_tempfile`）时，子 entry 相对解析的锚点**默认改用 project_root**（而非 tempfile dir）；正常文件场景保持父 entry_dir（H3 不变）。
- [ ] **预留用户覆盖接口**：在 `ihost.run_isolated(path, policy)` 的 `policy` dict 增加 `sandbox_base`（或类似）字段；`_resolve_isolated_path` 读取之；`ibci_modules/ibci_ihost/core.py` + `_spec.py` vtable 同步暴露。即便 IBCI 动态命名参数机制不完善，先以 policy dict 字段形式留可用 hook。
- [ ] **`ibci_modules/ibci_ihost/core.py`** + **`ibci_modules/ibci_ihost/_spec.py`** — run_isolated/spawn_isolated 签名增加 policy 字段透传。

#### 概念 2（main entry）规范化一致性
- [ ] **`core/engine.py:438`** — check() 统一（同 PT-ARCH-19 P0-E）。
- [ ] **`core/engine.py:363-367`** — `compile()` 的 `if not hasattr(self,'_entry_file')` 守卫与 `run()` 不对称（run 无守卫会覆盖）；统一两者行为（要么都覆盖要么都不覆盖）。
- [ ] **`core/engine.py:324`** — `abs_entry` 命名谎言（可能仍相对）；改名或确保绝对化。（**2026-07-13 订正**：原引 `:321` 实为 `self._entry_file = _entry_ib.to_native()`；`abs_entry = self._entry_file` 在 `:324`。）

#### 隔离侧（概念 4/5）—— 无需改动（已健康）
- child entry：`HostService._resolve_isolated_path`（service.py:234）经父 entry_dir 锚定的 PathResolver，H3 一致，有测试守护。
- child project_root：`PathContext.derive_isolated`（context.py:63-85）集中化，刻意设计（=子入口目录），测试锁定。
- 唯一清理项：`rt_scheduler.py:68-70` 死备份（PT-ARCH-19 P0-D）。

#### 完成门槛（2026-07-13 机械化订正）
> **订正原因**：旧门槛"零混淆/妥协/BUG"不可测量，且含被搁置项 P0-K（门槛⑥要求"零 compat 垫片含 P0-K"但动作是"负责人裁决"）——门槛含被搁置项即非真门槛。且新门槛用的仍是上次误判 DONE 的同一 subagent 机制，无结构性护栏。改为**机械可证伪断言**。

**机械断言（全部必须为真，git bash / PowerShell 跑 rg）**：
```bash
# A. 编译层零 os.path 构造 + 零 CWD 锚定 + 零 runtime 反向依赖
rg -c 'os\.path\.(abspath|getcwd)|os\.getcwd' core/compiler/ core/base/    # == 0
rg -n 'from core\.runtime' core/compiler/ core/base/                        # 空
# B. PathContext 成为唯一锚点：私有 root 字段清零
rg -n '_root_ib|self\._root_path' core/compiler/ core/runtime/interpreter/   # 空
rg -n 'os\.getcwd' core/                                                     # 空
# C. 死 import 清零（每处 import os 必须有对应 os. 使用）
rg -n '^import os' core/runtime/interpreter/permissions.py core/runtime/interpreter/execution_context.py core/runtime/interpreter/module_manager.py core/runtime/interpreter/interpreter.py core/runtime/interpreter/intrinsics/meta.py  # 期望均无死命中
# D. 3 新能力覆盖率门槛（守护 BUG 漏网根因——上次 DONE 因零测试致 BUG 漏网）
python -m pytest tests/runtime/test_path.py -k "Canonicalize or Derive or Snapshot"  # 每类 ≥1 命中且 pass
python -m pytest tests/ -q --tb=no --no-header   # 0 failure（数字以当次为准）
# E. SnapshotLayout BUG 回归（直接守护 P0-A）
python -m pytest tests/runtime/test_path.py -k "Snapshot"                    # 含 asset_dir 同级断言
```

**非机械项（需人工确认，但不作为唯一门槛）**：
- ① SnapshotLayout BUG 已修（由 E 守护）。
- ② 5 概念清晰区分（概念 4/5 已健康勿动；1/2/3 由 A/B 间接守护）。
- ③ D1/D5 设计决策已选定（方案 a 或 b），且 run_string 锚点行为已**文档化**（不再"伪装修了"）。
- ⑥ P0-K 已**剥离**（见 P0-K 决策，独立 track，非本门槛）。

> **门槛治理原则**：下次若再次误判 DONE，根因诊断应落在"哪个机械断言本应存在却缺失"，而非再加一轮 subagent。

---

#### PT-ARCH-19 历史计划详情（已完成的部分：分层搬迁）

> **项目负责人 2026-06-25 指定为最高优先级**。修正 P0-1 的 premature DONE；gates P0-2。单点真理以 ADR-017 为准。

**遗留问题（复审实锤）**：
1. **compiler→runtime 违规**（2 处）：`core/compiler/scheduler.py:13` + `core/compiler/parser/resolver/resolver.py:4` import `core.runtime.path`。违反 `ARCHITECTURE_PRINCIPLES §4.1`（兄弟层互不依赖），与已修 HostInterface 同类。
2. **P0-1 的 3 个"排除项"实为保留的碎片化**：
   - `os.path.realpath` 在 scheduler/resolver/permissions **3 处独立调用**（应统一到 PathValidator 一处）。
   - CHILDBOOT 派生内联在 engine（应集中到 PathContext）。
   - save_state 的 `.assets` 布局内联（应集中到 SnapshotLayout）。
   - **根因**：层位置错误（path 在 runtime）使加统一能力会加剧 compiler→runtime 违规，故 P0-1 回避了吸收。
3. **base 例外**：`core/base/source/source_manager.py` 用 `os.path.abspath` ×4（CWD 锚定）。

**方案（ADR-017 三层分工）**：
```
core/base/path/     【新】原子原语：IbPath（迁入）+ safe_relpath（迁入）
core/kernel/path/   【新】IBCI 模型：PathResolver + PathValidator(+canonicalize_for_security)
                                       + ModuleNameSpace + PathContext(+derive_isolated) + SnapshotLayout(新)
core/runtime/path/  【保留】BuiltinPaths（import ibci_modules，不进 kernel）
```

**待做（按 ADR-017 执行序列）**：
1. 建 `core/base/path/` + `core/kernel/path/`，搬迁 6 文件，更新 `__init__`。
2. 更新全部消费者 import 路径（~10 处，机械；含 compiler 2 处违规站点）。
3. 加 3 个新能力：
   - `PathValidator.canonicalize_for_security(path) -> IbPath`（kernel/path/validator.py，全仓唯一 realpath）。
   - `PathContext.derive_isolated(child_entry) -> PathContext`（kernel/path/context.py，CHILDBOOT 集中化，**语义保持**=子入口目录）。
   - `SnapshotLayout`（kernel/path/snapshot.py，独立类，快照资产布局集中化）。
4. 收尾：迁 `base/source_manager` 用 IbPath；scheduler/resolver/permissions 改调 canonicalize_for_security（消灭 realpath 3×）；engine 改调 derive_isolated；host/service 改调 SnapshotLayout。
5. 每步全量 pytest（1070 passed/0 fail）；最终 grep 确认 compiler 层零 `from core.runtime` 导入。

**四个能力决策**（项目负责人 2026-06-25 确认）：
| # | 决策 |
|---|------|
| 1 | `canonicalize_for_security` 收口进 PathValidator（IbPath 保持纯字符串）—— 按判断进行 ✓ |
| 2 | CHILDBOOT 语义保持（子入口目录），但策略集中化到 `derive_isolated`；未来显式 `policy["sandbox"]` 化留后续 ✓ |
| 3 | SnapshotLayout 独立类 ✓ |
| 4 | FS 查询（exists/isdir/isfile）不收口（保持边界）✓ |

**预估工作量**：~1-2 天（行为不变，纯搬迁+加法，低风险）

---

### ⚠️ [DONE] PT-ARCH-11　路径系统统一（已完成；层位置修正由 PT-ARCH-19 完成）

> 完整执行 ADR-015 的 10 点合并目标。测试基线：**1070 passed, 5 skipped**（0 failures，较统一前 +13 来自新增 canonical 测试）。
> 2026-06-25 复审发现遗留 compiler→runtime 违规 + 3 个未吸收排除项，由 **PT-ARCH-19（ADR-017）完成修正**。两者共同构成 P0-1 的真正完成。

**落地的 canonical 层**（`core/runtime/path/`）：
- `PathResolver` 重写为 entry_dir 单锚点语义（§6.1 契约）；`ExecutionContextImpl.resolve_path` / `HostService._resolve_isolated_path` 均委托之——**PathResolver 成为唯一生产解析器**（ADR-015 第 2 点达成）。
- 新建 `BuiltinPaths`（安装根计算一次，消灭 4 处 `__file__` 遍历）。
- 新建 `ModuleNameSpace`（模块名↔路径映射，无 `os.sep`，消灭 6 处 `replace` 对）。
- 新建 `PathContext`（entry_dir/project_root 锚点容器）。
- `safe_relpath` 从 `core/base/path_utils.py` 迁入 path 包（`relpath.py`），原文件**已删除**。

**消费者迁移**：engine.py（7 处）/ scheduler.py（MODNAME×4 + SANDBOX-DUP + CANON）/ compiler/resolver.py（同）/ permissions.py / rt_scheduler.py / auto_discovery.py / host/service.py（save_state IbPath 化 + _resolve_isolated_path 委托）/ project_detector.py（删 vestigial pathlib）/ ibci_file（删死 import）。**零残留 TODO(path-unify)**。

**关键裁决**：
- CHILDBOOT（子 host root = 子入口目录）经测试验证为**刻意的隔离设计，非 bug**——更新 ADR-015 第 7 点与 PT-ARCH-15。
- `realpath` 在安全边界（scheduler/resolver/permissions）**保留**——符号链接解析是安全需求，非碎片化。
- `save_state` 的 `"__EXTERNAL_FILE_REF__"` 哨兵属序列化格式债（PT-ARCH-13，media 重建时统一），**非路径碎片化**——正确 scoping 排除。

**保留的合法 OS 边界操作**（非碎片化）：`os.path.exists/isdir/isfile/isabs/getmtime`（FS 查询）、`os.path.realpath`（符号链接解析）、`os.makedirs/open`（IO）。

---

### [DONE] PT-ARCH-14　HostService.save_state 路径处理 ✅（并入 PT-ARCH-11）

**落地**：save_state 的路径操作已 IbPath 化（`os.path.abspath/dirname/join/+".assets"` → IbPath）。`"__EXTERNAL_FILE_REF__"` 哨兵保留为序列化格式债（PT-ARCH-13 范畴，非路径碎片化）。注：save_state 是宿主级特权操作，不经 PermissionManager 沙箱校验——这是有意设计，非安全缺口。

---

### [DONE] PT-DOC-12　IBCI_SPEC §6.1 路径语义修正 ✅（并入 PT-ARCH-11）

**已修**（2026-06-25）：`IBCI_SPEC.md` §6.1 重写为区分**数据路径**（entry_dir 锚定，§6.1 契约）与**模块导入路径**（导入者目录锚定，Python 相对导入语义）。消除原"所有相对路径都基于入口目录"的虚假笼统声称。

---

### PT-ARCH-17　变量存储模型基础设施 [P0-2 / ADR-016]（核心新架构）

> ADR-016 的实现。受工作模式定论约束——**全程协议驱动，零过程式 `if/else` 分发**。

**待做**：
1. 在 axiom/spec 体系引入 **`storage_model` 类型级属性**（取值 `memory-backed` / `disk-backed`）。内存型为默认（含全部现有内置类型与用户类），语义不变。
2. 设计并确立**磁盘型协议族**（与 `__prompt__` 平行）的具体方法名与签名——治理惰性物化、基于路径的 payload 构建、基于路径的响应解析、路径引用的快照/序列化。具体方法名在本条设计期决定。`__prompt__` 族继续作为内存型协议，不泛化。
3. 改造 `core/runtime/objects/deep_clone.py`：按存储模型分发——磁盘型对象拷贝路径引用（浅、廉价），内存型走既有路径。**此处一并完成 `:89` 的 `type(val) is KernelIbObject` → `isinstance(val, IbObject)` 修复**（ADR-007 未竟部分），并补 `IbValue`-with-payload 的处理分支（按存储模型分发，不硬编码字节处理）。
4. 改造 `core/runtime/serialization/runtime_serializer.py` + `core/base/serialization.py`：按存储模型分发——磁盘型序列化路径引用；内存型既有路径不变。补 `BaseFlatSerializer._process_value` 缺失的处理能力（路径类型；bytes 仅在内存型 legacy 路径需要时考虑）。
5. 改造响应解析分发（ADR-013 修订版）：`AxiomParsingStrategy.parse` 通过 `receive()` 委托给目标类型的协议方法，**不写 `if/else`、不查能力标志位**。`has_multimodal_response_cap` 等能力位若保留则仅作编译期/内省元数据，不参与运行时分发。
6. executor / strategy / deep_clone / 序列化器**存储模型无关**——新增磁盘型类型不改这些层一行代码。

**验证**：内存型路径字节级不变（全量 pytest 0 failure）；新增"磁盘型分发不命中内存型协议"守护测试；`has_multimodal_response_cap` 默认不声明 → 今日文本路径行为不变。

**预估工作量**：~2-3 天

---

### PT-ARCH-18　media 重建为磁盘型 + 潜伏 bug 统一修复 [P0-3 / ADR-014]（含 PT-ARCH-12/13/16）

> ADR-014 的实现。**潜伏 bug 在此随模型切换统一消解**——按项目负责人指令，不允许先行过渡修复。`MediaStorage` 整体淘汰。

**待做**：
1. 新建 `core/runtime/objects/media_backing.py`：`MediaBacking` 抽象 + `FileBacking` / `GeneratedBacking`（均持 `IbPath`，**无 MemoryBacking**）。
2. 重写 `core/runtime/objects/media_types.py`：`IbAudio`/`IbImage`/`IbVideo` 改为磁盘型 handle（声明 `storage_model = disk-backed`，identity-object opt-out）。
3. **删除** `core/runtime/objects/media_storage.py`（字节持有者，整体淘汰）；其单测替换为 handle 契约测试。
4. 改 `core/kernel/axioms/primitives/media.py`：`__payload_prompt__` 从 backing **惰性物化**字节（按需从路径读，base64）。
5. 改 `ibci_modules/ibci_file/core.py` 的 `read_audio`/`read_image`/`read_video`：返回 `FileBacking(resolved_path)`，**不立即读字节**（零拷贝）。
6. 改 `core/runtime/bootstrap/builtin_initializer.py` 的 media 注册段（:605-634）：注册新的磁盘型协议族方法（PT-ARCH-17 确立的方法名）；**保留** `tn=`/`ax=` lambda 晚绑定修复。
7. **潜伏 bug 统一修复**（不再独立先行）：
   - **PT-ARCH-12（原潜伏 bug #1）**：`deep_clone.py:89` 的 isinstance + IbValue-payload 分支已在 PT-ARCH-17 落地；media 改为磁盘型后，handle 拷贝路径引用，原"静默跳过"不复存在。
   - **PT-ARCH-13（原潜伏 bug #2）**：序列化器磁盘型分支已在 PT-ARCH-17 落地；media 改为序列化路径引用，原"字节静默丢失"不复存在。
   - **PT-ARCH-16（原"统一响应解析基础设施"）**：协议驱动分发已在 PT-ARCH-17 落地；`MediaAxiom` 实现磁盘型响应协议即可，无需 `if/else`。

**验证**：MOCK 模式 e2e（`file.read_audio` → handle → `@~ $x ~`）端到端跑通；snapshot/serialize round-trip 守护测试（专门覆盖过潜伏 bug 的路径）；media 在 llmexcept 重试下正确快照/恢复。

**预估工作量**：~2-3 天

---

### [已折叠] PT-ARCH-12 / PT-ARCH-13 / PT-ARCH-16 → 并入 PT-ARCH-17/18

> 经第三轮研讨，这三个原独立条目不再先行。它们随 PT-ARCH-17（存储模型分发）与 PT-ARCH-18（media 磁盘型重建）统一修复。
> - PT-ARCH-12（`deep_clone.py:89` isinstance + IbValue-payload）→ PT-ARCH-17 step 3 + PT-ARCH-18 step 7。
> - PT-ARCH-13（序列化器 media-payload + bytes）→ PT-ARCH-17 step 4 + PT-ARCH-18 step 7。
> - PT-ARCH-16（统一响应解析基础设施）→ PT-ARCH-17 step 5（协议驱动分发）。
>
> **不允许过渡修复**（项目负责人明确指令）。在 PT-ARCH-17/18 完成前，media 在 snapshot/serialize 下"静默丢失"的现状作为已知限制保留（媒体目前仅 MOCK 可用、零生产路径 hit、零序列化测试覆盖，回归风险为理论性）。

---

### [GATED] media Phase 4 — MediaAxiom + IbMedia 全模态容器

> **阻塞于**：PT-ARCH-11（路径统一）+ PT-ARCH-17（存储模型架构）+ PT-ARCH-18（media 重建）全部完成（即 `NEXT_STEPS.md` 的 P0-1/P0-2/P0-3 全部 done）。
> **决策依据**：ADR-014（磁盘型 handle）+ ADR-016（存储模型）+ ADR-013（修订，协议驱动解析）。
> 解锁后提升为 `NEXT_STEPS.md` 的 P0。详见 `NEXT_STEPS.md` 的 GATED 段。

**剥离到独立后续（不纳入主线，结构不堵死）**：
- 元组解包 `(str t, audio a) = @~...~`（D5）——需 TypeCheckingPass 解包推断 + CPS 多返回值；`IbMedia` 的 modality→payload 映射为其预留接入位。

---



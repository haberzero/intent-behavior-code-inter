# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-01（原生 `**kwargs` 分传接通完成；候选 1 = PT-HEALTH-1）

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合。
3. **禁止 tricky 实现**：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支。
5. **质量优先于速度**：技术债必须先清，再推进依赖它的特性。潜伏 bug 不允许过渡修复。

---

## 当前测试基线

```bash
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 当前主线：无（函数参数机制已收官 + 解析算法已收敛 + 原生 kwargs 已接通）

> **函数参数机制（默认 / 具名 / 动态参数）P1-P4 已全部完成并提交**（2026-07-31，`git log`：`14ec729` P1+P2+维修、`f4e501f` P3、`8326063` P4、`b5a54ab` 任务控制、`5d7c2e8` skill 规整）：P1 AST+Parser → P2 语义 → P3 运行时统一绑定器 + vtable 签名升级 → P4 `file.write` 统一 API + 文档。质量维修（人工复查驱动：描述符单点化 / 双路径清理 / 兜底清零）与 `code-quality` skill 同期完成。
>
> **架构决策收尾（2026-08-01）已落地**：`ParamDescriptor`/`param_descriptors` → `docs/architecture/03_type_system.md` §3.6；统一绑定器 → `docs/architecture/04_vm_interpreter.md` §2.6；AST 参数节点 → `docs/architecture/02_metadata_ast.md` §2.5；vtable `params` 格式 → `docs/subsystems/04_plugin_system.md` §4.2（已有）。临时文档 `tasks_docs/_function_params.md` 已删除。
>
> **语义/运行时解析算法收敛（2026-08-01）已完成**：`_resolve_with_descriptors`（语义）与 `_resolve_call_arguments_runtime`（运行时）的双实现收敛为共享纯核心 `core/kernel/arg_binding.py:resolve_call_binding`（输入 names/kinds/has_default + 位置/具名 → 输出绑定计划 + 中性问题），两适配层各自映射诊断/实参装配。绑定算法单点真源，命中"单点真理/禁双写真相"。
>
> **原生 `**kwargs` 分传接通（2026-08-01）已完成**：原生模块函数可声明 `VAR_KEYWORD` 并正确接收未声明具名实参（`create_proxy` 把末位 varkw dict 分传为 `**kwargs`）；签名校验改为只计非 VAR_* 声明参数；声明 VAR_KEYWORD 但实现不接受 `**kwargs` 加载即失败。附带：`_ibci_param_meta` 形式化为 `IbNativeFunction.param_meta` 字段，消除 VM 层对 loader 代理私有属性的 duck-typing。

**已解锁的受益项**：
- PT-ARCH-28：`file.write(target, data, overwrite_flag="new"|"overwrite")` 统一 API 已落地（`PENDING_TASKS.md` 标记完成）
- PT-PHASE4-1（已封存）：`register_model(name, url, key, model, **kwargs)` 的运行时前置（`**kwargs` 收集 + 原生分传）已全部就绪，解封恢复时只需声明 vtable VAR_KEYWORD

**skill 体系现状**（2026-07-31 规整）：`code-health` 已并入 `code-quality`（健康诊断十查 + 质量红线）；新增 `code-odor`（异味特征检测 + 工作过程自查 + 自我质询协议）、`self-grill`（内向化自我质询）、`grilling`（对用户质询）。AGENTS.md 必读清单已同步。

**下一主线候选**（2026-08-01 评估，择一立项）：

1. **PT-HEALTH-1（推荐作为下一主线）**：`hasattr` 能力探测 → 协议化（封装纪律）。
2. **测试体系治理**（`TEST_REFACTOR.md`，独立低优先级）。

**既定推荐顺序**：先 1（封装纪律）→ 再 2（测试体系）。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **media Phase 4**（多模态容器）：**已彻底封存（2026-08-01）**，短期不考虑实现，恢复需显式解封；代码层零启动（`PENDING_TASKS.md` §六）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。

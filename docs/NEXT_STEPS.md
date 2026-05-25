# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-25（P0 全部完成，P2-B/C 完成）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-25 实测结果**：`789 passed, 7 skipped`（0 failures）。

---

## ⏭ 当前 P0：Semantic Pipeline 架构改进（5 步渐进式重构）✅ 全部完成

> 目标：使 IBCI 类型系统与语义分析架构更清晰、更易维护、更符合现代编译器设计理念。
> 原则：不引入完整 HM/约束求解；保持"单次锁定 + 公理调度"核心哲学；但为未来高阶函数与类型传播留下受控扩展点。

### Step 1 ✅：TypeEnvironment → TypeInferenceState

- ~~删除死代码 `TypeEnvironment`~~ → 完成：TypeEnvironment alias 彻底移除，不保留向后兼容
- TypeInferenceState 已引入：`auto_return_accumulator` + `TypeSlot` 单次锁定绑定点
- 所有测试 imports 已迁移至 TypeInferenceState

### Step 2 ✅：ScopedVisitor 基类 + context manager scope 管理

- 新建 `core/compiler/semantic/passes/scoped_visitor.py`
- 统一 SymbolResolver、TypeCheckingVisitor、LambdaCaptureAnalyzer 三个 visitor 的 scope 管理
- 引入 `@contextmanager enter_scope()` 保证 scope 生命周期安全
- 消除 ~60 行重复 scope_stack/push_scope/pop_scope 代码

### Step 3 ✅：SpecRegistry.resolve_call_return() 统一类型决议

- 新增 `resolve_call_return()` 方法：统一处理 FUNCTION/CALLABLE_SIG/CLASS/PRIMITIVE/LIST/DICT/CALLABLE_INSTANCE/BOUND_METHOD + axiom fallback
- 新增 `resolve_callable_instance_return()` 方法：处理 `__call__` 协议
- `visit_IbCall` 从 5 层 ad-hoc fallback 重构为 3 段清晰结构：callable-instance → callability-check → unified-resolve
- `resolve_return()` 已彻底移除（零调用方，无向后兼容负担）
- 14 个新增单元测试覆盖所有 callable 形态

### Step 4 ✅：7-Pass 归并为 4-Phase

- 新建 SymbolPhase（Pass 1+2 合并，共享 scope stack）
- 新建 TypePhase（Pass 2.5+3 合并，消除重复 _resolve_type）
- 新建 BindingPhase（Pass 4+5 合并，一次调度）
- 新建 IntegrityPhase（包装 IntegrityCheckPass，保持独立）
- pipeline.py 从 7 个 Pass 实例化为 4 个 Phase
- 原子 Pass 文件保留作为内部实现，Phase 为组合层

### Step 5 ✅：PassOutput + Immutable Pipeline

- ✅ 每个 Phase 产出显式 `PassOutput`（result.py 中 frozen dataclass）
- ✅ Pipeline 负责 merge 多个 PassOutput 到最终 MetadataStore（`MetadataStore.from_outputs()`）
- ✅ Context threading 通过 `prior_symbol_bindings` / `prior_type_bindings` 实现跨 Phase 数据传递
- 务实折中：SymbolPhase 内部（Collection→Resolution 子步骤间）仍共享可变 SymbolTable，这是标准编译器设计（构建符号表→使用符号表），不属于跨 Phase 的 mutation

---

## ⏭ 当前 P2：Semantic 静态诊断增强

### P2-B ✅ `intent_context.push()` 静默无效陷阱编译期警告

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），编译期现在发出 SEM_090 警告。
- 检测 `intent_context.push/pop/fork/merge/combine/clear()` 在类对象上调用
- `get_current()`/`use()`/`clear_inherited()` 不触发警告（这些在类上调用也生效）
- 17 个新增测试覆盖

### P2-C ✅ NS-5 编译期类型转换检查（激活 `can_convert_from`）

`(TargetType)source_expr` 表达式现在使用目标类型的 `can_convert_from(source)` 公理方法进行编译期校验。
- 当目标类型公理明确拒绝转换时发出 SEM_091 警告（非错误，因运行时仍可能有动态路径）
- 例如：`(int)list_var` → SEM_091；`(int)str_var` → 无警告
- 已有 `can_convert_from` 实现的 axiom：IntegerAxiom, FloatAxiom, BoolAxiom, StrAxiom, ListAxiom, DictAxiom, EnumAxiom 等
- 8 个新增测试覆盖

---

## P3 候选（远景；详见 PENDING_TASKS）

- 二层 IR 路线（结构 IR + 执行 IR）。
- 公理 + 元数据 LLVM 化。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。

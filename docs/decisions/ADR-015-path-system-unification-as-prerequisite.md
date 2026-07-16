# ADR-015: 路径系统统一为强制前置

## Status
Accepted (2026-06-25)

## Date
2026-06-25

## Context

2026-06-25 审计量化了路径处理的碎片化（详细 Fragmentation Map 见 `docs/COMPLETED.md` 2026-06-25 条目及工作日志）：

- `core/runtime/path/`（`IbPath`/`PathResolver`/`PathValidator`）设计良好，但 `PathResolver` **零生产调用点**（死代码，被 `ExecutionContextImpl.resolve_path` 手搓的两层版取代）。
- **5 种"root"定义并存**：`engine.root_dir`（带 CWD 兜底）、`engine._entry_dir`、`PermissionManager.root_dir`、`Scheduler.root_dir`、`ModuleResolver.root_dir`，各独立 `realpath` 规范化。
- **3 套并行沙箱检查**：`scheduler.py:244`、`parser/resolver/resolver.py:51`、`permissions.py`（只有这处用了 `PathValidator`）。
- **模块名 ↔ 路径**靠散在两文件的 `replace('.', os.sep)` ↔ `replace(os.sep, '.')` 字符串变换耦合到 OS 分隔符。
- **4 处 `__file__` 遍历**用 3 种不同公式计算安装根。
- `HostService.save_state` **绕过沙箱**（安全缺口），用字符串拼接的 `.assets/` 兄弟目录 + `"__EXTERNAL_FILE_REF__"` 魔法哨兵。
- 子 ihost 的 root 被强设为 `dirname(child_entry)`（`engine.py:462-463`），**绕过 `ProjectDetector`** → 子脚本可能找不到共享的 `ibci_modules/`。
- IBCI_SPEC §6.1"所有相对路径基于入口文件目录解析"的声称**对模块导入是假的**（相对导入按导入者目录解析，`parser/resolver/resolver.py:81`）。

这种碎片化不是学术问题：ADR-014（media handle/backing）使媒体变量**指向**路径系统。Phase 5 设计文档已预承诺会放大碎片化（hardcoded `.ibci_media_cache/` 锚点未定义；stringly-typed `"disk:/path"` location——第三套路径格式）。在当前碎片化之上盖 media-as-handle，等于把不一致性乘以三。

## Decision

**路径系统统一是 ADR-014（media handle/backing）与 Phase 4 media 工作的强制前置**。在路径统一完成前，不得落地任何 media-as-handle 代码。

统一**必须**合并（按审计）：

1. 每个执行上下文**恰好两个良定义锚点**：`entry_dir`（数据路径）与 `project_root`（沙箱 + 插件发现），并文档化二者关系。
2. `PathResolver` 成为**唯一**生产解析器（要么退役 `ExecutionContextImpl.resolve_path` 的手搓版，要么删除 `PathResolver`——二选一，删掉败者）。
3. 模块名 ↔ 路径映射抽象进一个 OS-separator-agnostic 的服务。
4. **唯一**沙箱检查走 `PathValidator`（合并现有三套）。
5. **唯一** `BuiltinPaths` 服务取代 4 处 `__file__` 遍历。
6. 跨盘边界情况集中进 `IbPath`。
7. 子 ihost root 语义**已裁决**（2026-06-25）：子 host 沙箱 = 子入口所在目录是**刻意的隔离设计，非 bug**——`test_run_isolated_absolute_path_still_works` 证明 child 可能在父 project_root 之外，子沙箱必须包含子入口才能编译。碎片化的只是 `os.path.abspath/dirname` 用法，已统一走 IbPath。集中化落地（`PathContext.derive_isolated`）归属 PT-ARCH-19（重开-进行中，见 `docs/PENDING_TASKS.md §九`）。
8. 序列化采纳路径感知状态（save_state 走 resolver+validator；定义明确的快照锚点）。
9. Phase 5 media **不得引入第三套路径格式**——`MediaBacking.path` 是 `IbPath`，溢写目录由 `project_root` 派生。
10. IBCI_SPEC §6.1 与模块导入现实对齐。

本工作受"扎实推进，禁止快速实现/兼容层/胶水实现/tricky 实现"原则约束：**不留兼容 shim、不在旧代码外包 wrapper**。必须是真正的合并。

## Alternatives Considered

### Alternative A：先做 media，路径统一并行推进
- Pros：在头条特性上更快出可见成果
- Cons：media-as-handle 会把碎片化的路径约定冻结进已发布特性；重构成本复合
- Rejected：被工作模式原则明确禁止；耦合太深，无法安全并行

### Alternative B：不设正式 gate，逐步统一路径
- Pros：前期承诺更低
- Cons：没有 gate，media 工作会落在我们恰好还没统一的路径之上；审计的 10 点合并在精神上不可分割（锚点与沙箱检查相互关联）
- Rejected：gate 是工作模式原则的执行机制

## Consequences

- Phase 4 media 时间线因路径统一而延长（可接受；按工作模式，质量优先于速度）。
- `IBCI_SPEC §6.1` 必须修正（文档债）。
- 死代码 `PathResolver` 的去留必须作为统一第一步被回答（revive-or-delete）。
- **ADR-014 被本 ADR 阻塞**至完成。
- 全部 5 个"root"字段、3 套沙箱检查、4 处 `__file__` 遍历成为合并目标，追踪于 `docs/PENDING_TASKS.md`（PT-ARCH-11 ~ PT-ARCH-15）。
- `HostService.save_state` 的沙箱绕过（安全缺口）作为本统一的子项一并修复。

## 改动面（实现期，按合并目标分批）

详见 `docs/PENDING_TASKS.md §九 PT-ARCH-11`（含 10 点合并清单的文件:行清单）。

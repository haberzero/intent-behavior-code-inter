# ADR-017: 路径模块层位置重构 —— base/kernel/runtime 三层分工

## Status
Accepted (2026-06-25) — 已实现（2026-06-25 经 PT-ARCH-19 落地，2026-07-13 经 ADR-019/PT-ARCH-21 完成路径模型重设计）。

**优先级**：历史最高（项目负责人 2026-06-25 指定，已完成）。曾 gates P0-2（存储模型）的干净落地——该 gate 已满足。

## Date
2026-06-25

## Context

P0-1（PT-ARCH-11）统一了全仓的路径**处理**，但路径**模块**仍位于 `core/runtime/path/`。2026-06-25 复审发现三个相互关联的问题：

### 1. compiler→runtime 架构违规（2 处，实锤）

```
core/compiler/scheduler.py:13                  from core.runtime.path import IbPath, PathValidator, ModuleNameSpace, safe_relpath
core/compiler/parser/resolver/resolver.py:4    from core.runtime.path import IbPath, PathValidator, ModuleNameSpace
```

`ARCHITECTURE_PRINCIPLES.md §4.1`：compiler 与 runtime 是**兄弟层**，互不依赖（`compiler → runtime 禁止`）。这与此前已修复的 `HostInterface` 违规（从 runtime 迁到 kernel）**完全同类**。P0-1 迁移中把 compiler 接到了 runtime.path 上，制造/延续了此违规。

### 2. P0-1 三处"排除项"的根因（关键洞察）

P0-1 完成报告里，三处路径处理被作为"合法边界操作"保留（realpath 在 scheduler/resolver/permissions 各调一次；CHILDBOOT 派生内联在 engine；save_state 的 `.assets` 布局内联）。**根因**：若把统一能力（`canonicalize_for_security` / `derive_isolated` / `SnapshotLayout`）加进 runtime/path，compiler 就要 import 它们 → **加剧** compiler→runtime 违规。层位置错误**阻塞**了能力的正确吸收。项目负责人识破这些"排除项"实为保留的碎片化。

### 3. base 层例外

`core/base/source/source_manager.py`（base 层）用 `os.path.abspath` ×4 做源码键化——CWD 锚定，正是正在消除的隐式全局状态。base 不能 import kernel/runtime，故只要 IbPath 不在 base，base 就只能继续用 os.path。这是当前唯一的 base 例外。

### 4. path 包自包含

`core/runtime/path/` 无任何跨 core 层依赖（仅 intra-package + stdlib + 顶层 `ibci_modules` for BuiltinPaths）。**搬迁低风险**。

## Decision

把路径模块按抽象级别重分布为三层：

```
core/base/path/          【新】原子路径原语（任何层可用）
  ├── ib_path.py         IbPath（从 runtime/path 迁入）
  └── relpath.py         safe_relpath（从 runtime/path 迁入）

core/kernel/path/        【新】IBCI 路径模型（语言核心概念）
  ├── resolver.py        PathResolver
  ├── validator.py       PathValidator + canonicalize_for_security【新】
  ├── modulename.py      ModuleNameSpace
  ├── context.py         PathContext + derive_isolated【新】
  └── snapshot.py        SnapshotLayout【新建，独立类】

core/runtime/path/       【保留】运行时/环境特有
  └── builtin.py         BuiltinPaths（import ibci_modules；安装发现；不进 kernel）
```

### 依赖流（全部合法）

```
base/path/IbPath  ←  kernel/path/{Resolver,Validator,ModuleName,Context,Snapshot}
                          ↑                                   ↑
                     compiler（合法）                    runtime（合法）
                                                             ↑
                                                   runtime/path/BuiltinPaths
                                                   （仅 runtime/extension/core-root 用，compiler 不用）
```

### 四个能力决策（项目负责人 2026-06-25 确认，落地于最终位置）

1. **`PathValidator.canonicalize_for_security(path) -> IbPath`**（`kernel/path/validator.py`）：全仓唯一 `os.path.realpath` 调用点。scheduler/resolver/permissions 三处改调它，消灭 3× realpath 重复。IbPath 仍保持纯字符串（FS 感知归 PathValidator 这一个安全成员）。
2. **`PathContext.derive_isolated(child_entry) -> PathContext`**（`kernel/path/context.py`）：子沙箱派生策略集中化。**语义保持**（子沙箱 = 子入口目录，由 `test_run_isolated_absolute_path_still_works` 验证的隔离设计）；engine 调它。未来显式 `policy["sandbox"]` 化留作后续。
3. **`SnapshotLayout`（独立类）**（`kernel/path/snapshot.py`）：快照资产布局策略集中化（`save_path + ".assets"` 等）；host/service 调它。
4. **FS 查询（exists/isdir/isfile）不收口**：保持边界操作（过度统一反而臃肿）。

### base/source_manager 迁移
改用 `base/path/IbPath`（`IbPath.from_native(...).resolve_dot_segments()`），消除 base 例外与 CWD 锚定。

## Alternatives Considered

### Alternative A：路径模块留 runtime，接受 compiler→runtime 违规
- Rejected：违反 `ARCHITECTURE_PRINCIPLES §4.1`；与已修 HostInterface 同类；阻塞能力吸收。

### Alternative B：全部进 kernel/path，base 留 os.path
- Pros：更简（2 层而非 3 层）
- Cons：base/source_manager 留在 CWD 锚定的 os.path.abspath（正是要消除的模式）；违反"不出现例外"立场
- Rejected：项目负责人明确倾向无例外；base 合理需要 IbPath 做一致规范化。

### Alternative C：全部进 base/path
- Pros：最大化底层
- Cons：PathContext/PathResolver 的 IBCI 特有锚点/语义不属于 base（原子/可迁移层）；BuiltinPaths 的 `import ibci_modules` 不适合 base
- Rejected：混淆抽象级别；base 只应持真正原子原语。

## Consequences

- **compiler→runtime 违规消除**（2 处）。
- **base 例外消除**（source_manager 改用 IbPath）。
- **3 个能力解锁**（canonicalize_for_security / derive_isolated / SnapshotLayout）落地于 kernel/path。
- **realpath 重复消除**（唯一调用点在 PathValidator）。
- **CHILDBOOT 派生集中化**（PathContext.derive_isolated）。
- **快照布局集中化**（SnapshotLayout）。
- 影响面：~6 文件搬迁；~10 import 站点更新；行为不变（纯搬迁 + 加法能力）；每步全量 pytest 守护。
- BuiltinPaths 留 runtime/path（compiler 不需要它——search_paths 由 engine 传入）。
- **历史优先级**：曾 gates P0-2（存储模型需要路径原语在正确的层）——现已满足，路径模型已统一（ADR-019）。

## 执行序列（详见 PENDING_TASKS §九 PT-ARCH-19）
1. 建 base/path/ + kernel/path/，搬迁文件，更新 __init__。
2. 更新全部消费者 import 路径（机械）。
3. 加 3 个新能力（canonicalize_for_security / derive_isolated / SnapshotLayout）。
4. 迁移 base/source_manager + 消除 realpath 3× 重复 + CHILDBOOT/快照布局集中化。
5. 每步全量 pytest；最终零残留违规（grep compiler→runtime.path 应为空）。

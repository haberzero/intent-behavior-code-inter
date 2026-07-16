# ADR-018: 路径概念模型 —— 5 概念形式化 + 统一原则

## Status
**Partially Superseded (2026-07-13)** by [ADR-019](ADR-019-path-and-plugin-model-redesign.md).

被取代项：D1（root 必填 → 引擎级默认 entry_dir）、D5（`_entry_is_tempfile` 标志 → 合成 entry `__string_exec__.ibci`）、`CWD ⊇ project_root` 不变量（撤回）、D4 的"PathContext 穿透 scheduler/resolver/permissions"（重构为五概念模型）。

未取代项：5 概念形式化定义（§Decision 表）中概念 4/5（隔离侧 child entry / child project_root）的**健康部分**仍有效；D2（project_root 规范化经 canonicalize_for_security）、D3（静默退化消除）仍有效。

原 Acceptance 保留如下（历史记录）：
Accepted (2026-06-25)

## Date
2026-06-25

## Context

3 轮路径概念交叉检验（共 8 个 subagent）发现 IBCI 主侧路径概念管理存在严重混淆，集中在 **project_root**：
- CWD 被当作 project_root 兜底（`engine.py:74`）——隐式全局状态 + 安全语义错位。
- project_root 的 4 个持有者 realpath 规范化不统一（engine 词法 vs scheduler/resolver/permissions 解 symlink）→ symlink 下基准漂移。
- 退化静默（`main.py` 的 `--verbose` 死代码）+ 双入口退化目标不一致（main.py→entry_dir vs engine.py→CWD）。
- main entry 三入口（run/compile/check）规范化机制不一致。

隔离侧（child entry / child project_root）经检验**健康**，无需重构。

5 个路径概念需形式化定义并明确区分，统一原则需确立。

## Decision

### 5 概念形式化定义

| 概念 | 定义 | 规范化 | 锚点用途 |
|------|------|--------|---------|
| **1. CWD** | OS 进程工作目录（shell 当前位置） | 无（OS 属性） | **不进入业务路径**——不作任何路径概念的兜底 |
| **2. main entry** | CLI 传入的目标 .ibci 文件 | 绝对化（经 IbPath + resolve_dot_segments） | 派生 entry_dir（数据路径解析锚，§6.1 契约） |
| **3. project_root** | 项目根目录（沙箱边界 + 插件发现） | = ProjectDetector 探测结果；退化时 = entry_dir | 沙箱判定 + 插件发现 + isys.project_root() |
| **4. child entry** | ihost.run_isolated 子脚本 | 相对解析锚定**父 entry_dir**（H3 契约） | 子 Engine 的 main entry |
| **5. child project_root** | 子 Engine 的根 | = child entry 的 dirname（刻意隔离设计） | 子沙箱 + 子插件发现 |

### 5 项统一决策（项目负责人 2026-06-25 确认）

#### D1. CWD 兜底彻底移除
- `engine.py:74` 的 `root_dir or os.getcwd()` 删除。
- 退化统一到 **entry_dir**（与 PathContext 文档 `context.py:11-13` 一致）。
- `IBCIEngine(root_dir=None)` 时：project_root = entry_dir（entry_dir 在 run() 时才知，故 engine 需延迟/重构 project_root 的确立时机，或在无 entry_dir 时显式报错）。

#### D2. project_root 规范化统一（解 symlink）
- `engine.py:75` 的 `IbPath.from_native(_root_src).resolve_dot_segments()` 改为也走 `PathValidator.canonicalize_for_security`（解符号链接）。
- 使 engine.root_dir 与 scheduler/resolver/permissions 的 root_dir **同源**（消除 symlink 基准分裂）。

#### D3. 静默退化消除
- 注册 `--verbose` 参数（或退化时无条件 stderr 警告）。
- main.py 与 engine.py 的退化目标统一为 **entry_dir**（消除双入口不一致）。
- 用户必须能感知 project_root 退化。

#### D4. PathContext 真正落地（成为唯一锚点容器）
- engine 构造 `PathContext(entry_dir, project_root)` 一次，向下传递。
- scheduler/resolver/permissions 接收 PathContext（或其 `.project_root`），**删除各自的 `_root_ib`/`_root_path`/`root_dir` 私有派生**。
- PathContext 不再是空架子——它取代历史上的"5 个 root_dir 字段"。

#### D5. run_string 场景的子 entry 锚点（默认 project_root + 预留用户覆盖接口）
- 当父 entry 是 `run_string`/`compile_string` 生成的 tempfile 时，`_resolve_isolated_path` 的锚点**默认用 project_root**（而非 tempfile dir）。
- **预留用户可覆盖的接口**：即便 IBCI 当前的动态多参数/命名参数传递机制不完善，也要在入口函数（`ihost.run_isolated` / `_resolve_isolated_path`）留下可用的 hook（如 policy dict 的 `sandbox_base` 字段，或 HostService 的可配置锚点），允许用户显式指定子 entry 的解析锚点。
- 检测父 entry 是否为 tempfile：可经 engine 标记（`run_string` 路径设 `_entry_is_tempfile = True`）。

## Alternatives Considered

### D1 备选：保留 CWD 兜底但显式化
- Rejected：CWD 是隐式全局状态，与"显式优于隐式"原则冲突；安全语义错位（/tmp 跑时 /tmp 成沙箱）。

### D2 备选：engine 保持词法，下游保持 realpath
- Rejected：symlink 下基准分裂会导致模块名派生与沙箱判定不一致。

### D4 备选：承认 PathContext 暂不落地，降级 docstring
- Rejected：那是保留空架子（违反"无妥协"）；既然建了规范容器就应真正使用。

### D5 备选：run_string 场景仍用 tempdir 锚点
- Rejected：tempfile dir 不是用户语义上的"项目位置"，子 entry 相对解析会错位。

## Consequences

- CWD 不再进入业务路径（消除隐式全局状态）。
- project_root 在所有持有者处同源（消除 symlink 基准分裂）。
- 退化显式可感知（消除静默）。
- PathContext 成为唯一锚点来源（消除 5 字段并存）。
- run_string 子隔离行为可预测 + 可用户覆盖。
- **影响面广**：engine/scheduler/resolver/permissions/main.py/host/service 全部需改——详见 `PENDING_TASKS.md §九 PT-ARCH-19/20` 的逐文件:行清单。
- 隔离侧（概念 4/5）无需改动（已健康）。

## 执行前置
- 本 ADR 的实现归属 PT-ARCH-19（收尾）+ PT-ARCH-20（概念统一）。
- **第一步必须是修 SnapshotLayout BUG + 补 3 新能力测试**（止损，详见 PT-ARCH-19 P0）。
- 完成门槛：再次交叉检验（subagent）确认无残留混淆/妥协/BUG。

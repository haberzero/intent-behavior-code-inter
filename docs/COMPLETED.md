# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 更早期的详细日志见 `docs/HISTORY_LOG.md`。
> 设计与实现细节见对应正式文档：`docs/design/TYPE_SYSTEM_DESIGN.md`、`docs/design/VM_AND_INTERPRETER_DESIGN.md`、`docs/design/VM_SPEC.md`、`docs/design/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-07-17（G2 ai/ihost/idbg/isys 内核原生化完成；下一项：G3+G4+G5+G6 磁盘型存储体系）

---

## 2026-07-17：G2 — ai/ihost/idbg/isys 内核原生化（ADR-020）

> 分支：`feat/G2-kernel-native-modules`；提交：见 `feat/G2-kernel-native-modules` 分支最新提交（含代码、测试、文档一次性切口）。
> 测试基线：**1157 passed, 7 skipped**（0 failures/errors，2026-07-17 实测，win32）。

### A. 核心改动
- 新建 `core/runtime/bootstrap/kernel_native_modules.py`：预注册 `ai`/`ihost`/`idbg`/`isys` 四模块为 `Provenance.KERNEL_NATIVE + Visibility.IMPORT_GATED`；提供 `late_hydrate_kernel_native_modules(service_context)` 二次水化窗口。
- 修改 `core/kernel/host_interface.py`：新增 `_kernel_native_names` 集合与 `reserve_kernel_native_name()` / `is_kernel_native()`；`register_module()` 拒绝用户插件覆盖 kernel-native 模块。
- 修改 `core/runtime/module_system/discovery.py`：`discover_all()` 支持可选 `host` 参数以保留构造期预注册；扫描时跳过已 kernel-native 的目录。
- 修改 `core/runtime/module_system/loader.py`：搜索路径扫描时跳过逻辑名为 kernel-native 的目录，避免从磁盘重复加载。
- 修改 `core/engine.py`：`HostInterface` 构造时即与引擎共享 `MetadataRegistry`，确保 kernel-native 模块元数据对编译器可见；`__init__` 中调用 `register_kernel_native_modules`；`_prepare_interpreter` 在 registry hooks 注入后调用 `late_hydrate_kernel_native_modules`；`_ensure_plugins_discovered` 传入现有 `host_interface` 保留预注册。
- 修改 `ibci_modules/ibci_ai/core.py`：`AIPlugin` 新增 `hydrate(service_context)` 方法，在 late-hydrate 窗口重新确认 LLM Provider 注册。

### B. 测试
- 新增 `tests/runtime/test_kernel_native_modules.py`：验证构造期预注册、元数据标记、覆盖保护、import-gating、late-hydrate 调用。
- 新增 `tests/e2e/test_e2e_kernel_native.py`：验证 ai MOCK 调用链、ihost 隔离执行、idbg/isys import 调用在 kernel-native 化后行为不变。

### C. 验证
- 全量 pytest：`1157 passed, 7 skipped`（0 failures）。
- 分层红线：`tests/runtime/test_kernel_native_modules.py` 通过 `tests/meta/test_layering.py` runtime 层检查；`tests/e2e/test_e2e_kernel_native.py` 通过 e2e 层黑盒检查。

---

## 2026-07-17：G1 重分类基础设施完成 + PT-ARCH-23 规划重排（文档卫生 + 碎片化审计）

测试基线：**1139 passed, 7 skipped**（0 failures/errors，2026-07-17 实测，win32，junitxml 捕获）。G1 改动未提交（领先 origin 的 WIP）。

### A. 文档卫生清理（无代码变更）
- 修 `NEXT_STEPS.md` 失效"未提交 WIP"警示；PT-ARCH-21/ADR-017 等过时"最高优先级"标签（NEXT_STEPS/PENDING_TASKS/decisions·README/ADR-017/TYPE_SYSTEM_DESIGN/VM_AND_INTERPRETER_DESIGN 共 6 处）；`rt_scheduler.py` 行号漂移 `:88→:83`。

### B. G1 — 重分类基础设施（ADR-020 E/A/C/D）✅
- **E 术语**：彻底消除 "builtin" 一词五义，7 族改名（`BuiltinPaths→InstallPaths`、prelude 目录、`builtin_initializer→primitive_initializer`、`is_builtin→is_intrinsic`+UID `builtin:`→`intrinsic:`、内核实例、`BUILTIN_TYPES→PRIMITIVE_TYPES`、**`objects/builtins/→objects/primitives/` 包重命名**），含全量注释/错误消息/测试名/docstring 同步。代码标识符层面 builtin 已归零（余 4 处溯源 docstring + 2 处 Python stdlib `builtins_round`）。
- **D 协议规则**：清硬编码 axiom 回退表 + enum 特例（`primitive_initializer.py:97-108`），改为从 `AxiomRegistry.get_all_names()` 派生 + fail-fast（实证均为死代码）。
- **A/C 复核**：prelude/import-gate 机制、bootstrap（`register_module`+loader 短路+懒查找）均验证健全；late-hydrate 随 ai 在 G2 建。

### C. flag/state 碎片化审计（F1-F7 实证）→ ADR-021 立
- 审计 `IbSpec`/`Symbol`/`RuntimeSymbolImpl` 控制变量，确认碎片化成立：`is_user_defined` 重载（来源+可见性）、"intrinsic"/`is_llm` 三编码并存、2 死字段（`axiom_provided`、`is_llm` 未序列化漏丢失）、`symbols.py:147` 真值表（过程式分支）。
- 立 **[ADR-021](decisions/ADR-021-typed-provenance-visibility-storage-axes.md)**：三枚举 `Provenance`/`Visibility`/`StorageModel` 取代平 bool；`Symbol.metadata` 来源键升级 + 删 2 死字段；真值表→`Provenance.compatible_with`；`storage_model` 枚举提前就位（仅落字段，分发待 G3）。**修正 ADR-020 G2 的 `is_user_defined` 写法**为 `provenance=KERNEL_NATIVE + visibility=IMPORT_GATED`。

### D. PT-ARCH-23 规划重排（依赖审查后调整）
- 新落地顺序：**G1（已完成）→ G1.5 数据结构迁移改善（ADR-021，当前最紧要）→ 路径整合收尾（PT-ARCH-21-FU，前移到 G2 之前——避免插在中间破坏 G3-G6 强耦合）→ G2 内核原生化 → G3+G4+G5+G6 磁盘型存储体系（合并单阶段，不可拆分）**。
- 撤销原"G2 与 G3 可并行"标注。
- 产出：ADR-021、decisions/README 索引 +、NEXT_STEPS（G1/G1.5/路径收尾/G2/G3-G6 新序列）、PENDING_TASKS（PT-ARCH-23 重构）。

---

## 2026-07-17：G1.5 — 数据结构迁移改善（ADR-021）完成

测试基线：**1139 passed, 7 skipped**（0 failures/errors，2026-07-17 实测，win32）。

### A. 核心字段迁移
- `core/base/enums.py` 新增三枚举：`Provenance`（KERNEL_NATIVE/AXIOM_PROVIDED/USER_DEFINED/EXTERNAL_MODULE）、`Visibility`（PRELUDE_VISIBLE/IMPORT_GATED/SCOPE_PRIVATE）、`StorageModel`（MEMORY_BACKED/DISK_BACKED）。
- `IbSpec`：`is_user_defined: bool` → `provenance: Provenance`、`visibility: Visibility`、`storage_model: StorageModel`（默认 MEMORY_BACKED）。
- `TypeDef.is_llm` 删除（死字段 + 漏序列化）。

### B. Symbol 清理
- `Symbol` 新增类型化 `provenance: Provenance`；`metadata["is_intrinsic"]` / `["is_external_module"]` 全部迁移到 `provenance`。
- 删除两个死字段：`metadata["axiom_provided"]`、`metadata["is_llm"]`（与 `SymbolKind.LLM_FUNCTION` 重复）。
- `SymbolTable.define` 的 4 行真值表替换为 `Provenance.compatible_with`。

### C. 序列化同步
- `serializer.py` 持久化 `provenance`/`visibility`/`storage_model`（enum name）。
- `artifact_rehydrator.py` 按 name 还原三枚举；旧 `is_user_defined` 字段不再使用。

### D. 读取点机械迁移
- 全仓 ~12 处 `is_user_defined` 读取点迁移到 `provenance`/`visibility`：runtime_context、artifact_loader、interpreter、bootstrapper、scheduler、prelude、context、symbol_collection_pass、_declaration_visitors、_type_checking_base、spec_builder、discovery。
- 对应测试 (`test_resolve_call_return.py`, `test_type_annotations.py`) 同步更新。

### E. 文档更新
- `docs/design/TYPE_SYSTEM_DESIGN.md` 更新 `TypeDef` 字段描述与 `SpecFactory` API。
- `docs/METADATA_ARCHITECTURE.md` §2.4 已登记三枚举（G1 WIP 中已落）。
- `docs/NEXT_STEPS.md` 移除 G1.5 条目，路径整合收尾（PT-ARCH-21-FU）提升为当前最紧要。

### F. 验证
- 全量 pytest 1139 passed / 7 skipped。
- rg 确认代码层零 `is_user_defined` 残留、零 `metadata["is_intrinsic"/"is_external_module"/"axiom_provided"/"is_llm"]` 残留。
- `StorageModel` 仅落字段，未引入任何 workflow 读取/分发（遵守 G1.5 与 G3 边界铁律）。

---

## 2026-06-25：ADR-018 路径概念模型确立 + PT-ARCH-19 重开（无代码变更）

> 5 路径概念交叉检验（3 subagent）+ 项目负责人决策。无代码改动；测试基线 1070 passed 不变。

### 5 路径概念健康度（收敛）
- 概念 1 CWD / 2 main entry / 3 project_root：需统一（混淆）。
- 概念 4 child entry / 5 child project_root：健康，无需改动。

### 5 项决策（项目负责人 2026-06-25 确认 → ADR-018）
- **D1**：CWD 兜底移除；退化统一 entry_dir。
- **D2**：engine.root_dir 也走 canonicalize_for_security（解 symlink），与下游同源。
- **D3**：静默退化消除（注册 --verbose 或无条件警告）；main.py 与 engine.py 退化目标统一 entry_dir。
- **D4**：PathContext 真正落地，替代 4 个私有 root 字段。
- **D5**：run_string 场景子 entry 锚点默认 project_root（非 tempdir）；**预留用户可覆盖接口**（policy dict 字段，即便 IBCI 动态命名参数机制不完善先留 hook）。

### 治理
- 立 **ADR-018**（路径概念模型）。
- PT-ARCH-19 由"DONE"改为**重开-进行中**（SnapshotLayout BUG + 统一未彻底）。
- 新增 **PT-ARCH-20**（路径概念澄清与 project_root 统一）。
- **逐文件:行清单**已嵌入 `PENDING_TASKS.md §九` PT-ARCH-19（P0-A~K）+ PT-ARCH-20（D1~D5），供 session 切换交接。
- 第一优先：修 SnapshotLayout BUG + 补 3 新能力测试（止损）。

### 反思（累积）
本 session 两次过早宣称"完成"（P0-1、PT-ARCH-19）。根因：以"测试通过 + 能力存在"为完成标准，未验证能力正确性、统一彻底性、无妥协、测试覆盖。**今后以"交叉检验（subagent）通过"为完成门槛。**

---

## 2026-06-25：PT-ARCH-19 完成声明撤回 —— 双轮交叉检验发现真实未完成项（无代码变更）

> 本条目是对上一条"PT-ARCH-19 完成"的诚实撤回。两轮交叉检验（第一轮 5 subagent：分层/碎片化/能力/行为/shim；第二轮 3 subagent：5 路径概念）证明统一未真正完成，且引入 1 个 BUG。测试基线 1070 passed 未变（无代码改动）。

### 第一轮交叉检验（5 subagent）发现
- **P0 BUG（实证）**：`SnapshotLayout.asset_dir_for`（snapshot.py:23）`save_path + ".assets"` 经 `IbPath.__add__`（路径 join）产出 `state.json\.assets`（文件当目录），而非旧契约 `state.json.assets`（同级）→ `save_state` 含资产时 `NotADirectoryError`。
- **P0 测试缺口**：canonicalize_for_security / derive_isolated / SnapshotLayout 零单测；save_state/load_state 零 e2e（BUG 漏网原因）。
- **未达标项**：PathContext 空架子（5 root_dir 字段仍在）/ CHILDBOOT 双轨（rt_scheduler:68-70）/ check() 双轨 / CWD 兜底自证过渡 / 三重规范化链 / ModuleResolver 违反 SSOT / abspath 未收口 / module_system+project_detector 未接入 / 死代码。
- **达标项（保留）**：3 层分工合法；compiler→runtime 违规真消除；realpath 真单点；字符串拼接/replace 技巧清零。

### 第二轮交叉检验（3 subagent）—— 5 路径概念健康度
| 概念 | 裁决 |
|------|------|
| 1. CWD | 🟡 混淆——被当作 project_root 兜底 |
| 2. main entry | 🟡 部分混淆——三入口规范化不一致 |
| 3. project_root | 🔴 严重混淆——4 持有者 realpath 不统一；symlink 基准漂移；静默退化；双入口退化不一致 |
| 4. child entry | 🟢 健康 |
| 5. child project_root | 🟢 健康 |

**核心病灶**：主 project_root 在不同运行姿势下取到 4 种不同值（显式/探测/CWD/entry_dir），未向用户披露。

### 治理
- PT-ARCH-19 由 DONE 改为**重开-进行中**（PENDING_TASKS §九）。
- 新增 **PT-ARCH-20**（路径概念澄清与 project_root 统一），待 ADR-018。
- P0-2（存储模型）继续后置。
- 文档：NEXT_STEPS（PT-ARCH-19 重开、PT-ARCH-20 最高优先级）、PENDING_TASKS（PT-ARCH-19 重开 + PT-ARCH-20 完整）。

### 反思
两次过早宣称"完成"（P0-1、PT-ARCH-19），根因相同：用"测试通过 + 能力存在"作完成标准，未验证能力正确性、统一彻底性、无妥协、测试覆盖。交叉检验正是为抓这些——它成功了。后续以"交叉检验通过"为完成门槛。

---

## 2026-06-25：PT-ARCH-19 路径模块层位置重构完成（ADR-017）

测试基线：**1070 passed, 5 skipped**（0 failures）。

> 完成 ADR-017 / PT-ARCH-19。修正 P0-1（PT-ARCH-11）遗留的 compiler→runtime 层违规与 3 个未吸收排除项。P0-1 至此真正完成。

### 落地

- **3 层分工**（按抽象级别）：
  - `core/base/path/`（新）：`IbPath` + `safe_relpath`（原子原语，任何层可用）。
  - `core/kernel/path/`（新）：`PathResolver` + `PathValidator` + `ModuleNameSpace` + `PathContext` + `SnapshotLayout`（IBCI 路径模型，compiler/runtime 共用）。
  - `core/runtime/path/`（保留）：仅 `BuiltinPaths`（安装发现，`import ibci_modules`，不进 kernel）。
- **compiler→runtime 违规消除**：compiler 层零 `core.runtime` 导入（scheduler/resolver 改 import `core.kernel.path`）。与此前已修 HostInterface 同类违规，现全部清零。
- **3 个新能力**（落地于最终位置）：
  - `PathValidator.canonicalize_for_security(path) -> IbPath`：全仓唯一 `os.path.realpath` 调用点；scheduler/resolver/permissions 委托，消灭散点 realpath 重复。
  - `PathContext.derive_isolated(child_entry) -> (entry, root)`：CHILDBOOT 派生集中化（语义保持=子入口目录，由测试验证的隔离设计）。
  - `SnapshotLayout`（独立类）：快照资产布局集中化；`save_state`/`load_state` 委托。
- **base 例外消除**：`source_manager` 改用 `base/path/IbPath`（消除 CWD 锚定的 `os.path.abspath`）。

### 根因复盘
P0-1 的 3 个"排除项"（realpath×3 / CHILDBOOT 内联 / 快照布局内联）的根因是路径模块错放在 runtime 层，使加统一能力会加剧 compiler→runtime 违规。下沉到 base/kernel 后，能力吸收不再受阻——这正是项目负责人识破的"整合失败"真实原因。

### 产出文件
- 新建 `core/base/path/__init__.py`、`core/kernel/path/{__init__,resolver,validator,modulename,context,snapshot}.py`。
- 删除 `core/runtime/path/{ib_path,relpath,resolver,validator,modulename,context}.py`（搬至 base/kernel）。
- 更新 ~10 消费者 import；3 处 realpath → canonicalize_for_security；engine CHILDBOOT → derive_isolated；host/service save/load → SnapshotLayout；base/source_manager → IbPath。
- 文档：NEXT_STEPS（P0-1 真正完成、P0-2 进位）、PENDING_TASKS §九（PT-ARCH-19 DONE）。

---

## 2026-06-25：P0-1 复审修正 —— 路径模块层位置遗留违规（无代码变更，纯复审记录）

测试基线：**1070 passed, 5 skipped**（0 failures；本轮无代码改动）。

> 本条目是对 P0-1（PT-ARCH-11）"完成"状态的诚实修正。P0-1 表面工作完成（零残留 TODO、1070 passed），但复审发现遗留问题，真正的完成在 PT-ARCH-19 之后。

### 复审发现

1. **compiler→runtime 架构违规（2 处实锤）**：`core/compiler/scheduler.py:13` 与 `core/compiler/parser/resolver/resolver.py:4` import `core.runtime.path`。违反 `ARCHITECTURE_PRINCIPLES §4.1`（兄弟层互不依赖），与此前已修 HostInterface 违规同类。P0-1 迁移中把 compiler 接到 runtime.path，制造/延续了此违规。
2. **P0-1 三处"排除项"实为保留的碎片化**（项目负责人识破）：
   - `os.path.realpath` 在 scheduler/resolver/permissions 3 处独立调用（非"合法边界操作"）。
   - CHILDBOOT 派生内联在 engine（非集中化）。
   - save_state 的 `.assets` 布局内联（非集中化）。
3. **根因**：路径模块层位置错误（在 runtime）使加统一能力（canonicalize_for_security / derive_isolated / SnapshotLayout）会加剧 compiler→runtime 违规，故 P0-1 回避了吸收——这是"整合失败"的真实原因。

### 治理决策

- 立 **ADR-017**（路径模块层位置重构 —— base/kernel/runtime 三层分工），**最高优先级**。
- 新增 **PT-ARCH-19**（路径模块层位置重构），列为 `NEXT_STEPS.md` 最高优先级 P0，gates P0-2。
- P0-1 的"DONE"修正为"功能完成，遗留违规见 PT-ARCH-19"。
- 四个能力决策由项目负责人确认：canonicalize_for_security 收口 PathValidator / CHILDBOOT 语义保持但集中化到 derive_isolated / SnapshotLayout 独立类 / FS 查询不收口。

### 产出文件

- 新增 `docs/decisions/ADR-017-path-module-layering.md`（Accepted，最高优先级）。
- 更新 `docs/decisions/README.md`（+ADR-017）。
- 更新 `docs/NEXT_STEPS.md`（PT-ARCH-19 提为最高优先级 P0；P0-1 标注遗留违规；P0-2 后置）。
- 更新 `docs/PENDING_TASKS.md`（§九 新增 PT-ARCH-19 完整计划；PT-ARCH-11 标注修正）。

---

## 2026-06-25：第三轮研讨 —— 变量存储模型提升（无代码变更，纯治理决策）

测试基线：**1057 passed, 5 skipped**（0 failures；本轮无代码改动，基线维持）。

> 本条目记录第三轮架构研讨结论：把"media 内存值 vs 磁盘引用"之争从实现细节提升为**类型级一等区分**，确立协议驱动分发框架。结论已固化为 ADR-016（新建）+ ADR-013/014 修订。

### 触发问题

项目负责人回归后，对前轮（第二轮）的两个具体设计提出质疑：
1. 我在 P0-3 提出的 `if has_multimodal_response_cap: from_response else: from_prompt`（`AxiomParsingStrategy` 内的标志位分支）是否属于此前被否定的 bypass？
2. 记忆中存在"高于 `__prompt__` 协议族的一层设计"，关于 LLM input/output，把全模态容器纳入协议管理、保留 `__prompt__` 作纯内存协议——要求核查其可靠性。

### 核查结论

1. **"Inter 层"命名溯源**：仅在 `AUDIT_REPORT_20260527.md §一` 出现，被定义为 `__prompt__` 协议族的同义词（四元结构的第四层）。**不存在**任何文档把它描述为"高于 `__prompt__`、按存储模型分发的元层"。项目负责人不认可此命名的出处（疑似过往智能体自造）。→ ADR-016 正式废弃该命名，采用"变量存储模型（Variable Storage Model）"。
2. **P0-3 的 if/else 确属被禁止的形态**：虽优于 ADR-009 的 `execute_*` 分叉（已死），但仍是过程式硬编码判断，违反项目负责人"不在运行流程里硬编码过程式判断、基于协议驱动"的原则。→ ADR-013 修订，改协议驱动分发（`receive()` 委托）。
3. **项目负责人确立了更强的架构立场**（4 条）：
   - 类型显式分纯内存类 / 硬盘卸载类；**所有 media 一律硬盘卸载类**。
   - 这种区分是**类型级一等区分**，基于路径系统建模，与内存类**平行**（不嵌套）。
   - 分发**协议驱动**，零 `if/else` 标志位分支。
   - 允许**整体淘汰** `MediaStorage`；潜伏 bug **不允许过渡修复**，须随存储模型架构统一修复。

### 关键架构发现：潜伏 bug 与存储模型架构耦合

原计划作为独立 P0-1 先行修复的两个潜伏 bug（`deep_clone.py:89` 严格身份判定 + 序列化器 payload 缺失），经分析**与存储模型决策深度耦合**：
- 若按当前内存模型修（深拷贝字节 / 序列化字节），等 media 改为磁盘型后这段代码必被推翻——**过渡实现，违反工作模式定论**。
- 正确路径：先完成存储模型架构（PT-ARCH-17），media 改为磁盘型 handle（PT-ARCH-18），此时 deep_clone/序列化器按存储模型分发，handle 拷贝/序列化路径引用——bug 在模型切换中**自然消解**。
- 现实风险评估：media 目前仅 MOCK 可用、零生产路径 hit、零序列化测试覆盖 → 回归风险为理论性，可承受"延后统一修复"。

### 产出文件

- 新增 `docs/decisions/ADR-016-variable-storage-model.md`（Accepted，上层治理）：确立 `storage_model` 类型级属性（memory-backed / disk-backed）；磁盘型变量基于路径系统建模；协议驱动分发（零 `if/else`）；`__prompt__` 族保持为内存型协议；磁盘型获得平行协议族；制动 `MediaStorage` 整体淘汰；废弃"Inter 层"命名。
- 修订 `docs/decisions/ADR-013-unified-response-parsing.md`：去除标志位 `if/else` 内部分支，改协议驱动分发；supersede ADR-009 的核心结论（单入口/单策略/无 execute_* 分叉）仍成立。
- 重写 `docs/decisions/ADR-014-media-storage-handle-backing.md`：砍除 `MemoryBacking`；存储模型升为类型级（ADR-016）；制动 `MediaStorage` 整体淘汰；潜伏 bug 处置并入 PT-ARCH-18。
- 更新 `docs/decisions/README.md`：新增 ADR-016；标注 ADR-013/014 已修订。
- 重写 `docs/NEXT_STEPS.md`：新 P0 序列＝**P0-1 路径统一**（ADR-015）→ **P0-2 存储模型架构**（ADR-016，PT-ARCH-17）→ **P0-3 media 重建**（ADR-014，PT-ARCH-18，潜伏 bug 随之统一修复）；工作模式定论追加第 4 条（禁止过程式硬编码分发）与第 5 条（潜伏 bug 不允许过渡修复）。
- 更新 `docs/PENDING_TASKS.md`：PT-ARCH-12/13/16 不再独立先行，折叠入 PT-ARCH-17/18；新增 PT-ARCH-17（存储模型基础设施）+ PT-ARCH-18（media 重建）；PT-ARCH-14/15/PT-DOC-12 重标为 P0-1 子项。

### 工作模式定论补强

`NEXT_STEPS.md ⛮ 工作模式定论` 追加两条：
- 第 4 条：**禁止过程式硬编码分发**——分发只通过协议驱动（`receive()` / vtable）完成，不在运行流程写 `if 能力标志位` 分支（ADR-016 第 3 条）。
- 第 5 条：**潜伏 bug 不允许过渡/简易修复**——必须在依赖它的架构完善后统一修复。

---

## 2026-06-25：media Phase 4 双轮架构审计（无代码变更，纯分析）

测试基线：**1057 passed, 5 skipped**（0 failures；本轮无代码改动，基线维持）。

> 本条目记录为 media Phase 4 铺垫的两轮系统级架构审计结论。结论已固化为 ADR-013/014/015 与 `PENDING_TASKS.md §九` 的前置技术债清单。**本轮未改任何代码**——所有发现归类为"待清债务"，受 `NEXT_STEPS.md ⛮ 工作模式定论` 约束分阶段清理。

### 第一轮：Phase 4 media 设计的全方位系统级分析

- 确认 Phase 3（输入侧 `__payload_prompt__`）已完成且扩展干净；Phase 4（输出侧 `from_response`）需新基础设施。
- 定位 8 个 media 类型注册镜像点（axiom→spec→builtin_initializer）与 3 个 Phase 4 新增路由点。
- 识别 5 个 Phase 3 已踩/文档标注的陷阱（lambda 晚绑定、两个 `get_axiom`、`receive()` 分发、`_finalize_invoke_result` 形状契约、MOCK 双重处理点）。

### 第二轮：耦合架构深挖（路径 / 存储 / 解析）

**关键发现 1 — 当前 media 内存实现是"哑的"（潜伏 bug）**：
- `deep_clone.py:89` 仍 `type(val) is KernelIbObject`（ADR-007 修复只做了一半）→ llmexcept 重试时 media **静默跳过**。
- `RuntimeSerializer._collect_instance` 无 `IbValue`-payload 分支 + `BaseFlatSerializer` 无 `bytes` 分支 → `save_state`/`load_state` 把 media 字节**静默丢失**，零测试覆盖。
- 含义：选"内存值"还是"引用"不是"省不省成本"——今天两边都没正常工作，存储/快照/序列化管线**无论如何都得修**。

**关键发现 2 — ADR-009 的分叉前提被证伪**：
- ADR-009 称"目标类型在 `_call_llm` 调用时未知"——实测证伪：类型来自 AST（`node_data["returns"]` / side-table），`type_name` 已作为参数贯穿整个解析管线至 `AxiomParsingStrategy.parse`。
- 因此路由判定**本就该在策略层**（唯一同时握有"原始响应 + 目标类型"的层）；在 `execute_*` 分叉是重复决策。
- 结论：以 ADR-013（单一入口/单一策略/内部分支）supersede ADR-009；`_call_llm_multimodal` 不再引入；文本路径字节级零回归（能力位默认 `False`，今日无类型声明 multimodal cap）。

**关键发现 3 — media 存储重框为来源感知的 handle/backing**：
- 媒体来源异质：文件来源（字节已在磁盘，内存拷贝是浪费）vs LLM 生成（必须物化）。
- 决定：media 变量为 handle（身份对象，`deep_clone` opt-out，序列化为描述符并在恢复期重解析——同 `IbNativeObject` 先例），底层 `MediaBacking` 抽象为 FileBacking / GeneratedBacking / MemoryBacking。字节惰性物化（`__payload_prompt__` 是唯一不可避免的开销）。
- **关键耦合**：handle 可靠性 = 路径可靠性 → 路径统一成为强制前置（ADR-015）。

**关键发现 4 — 路径碎片化量化**（Fragmentation Map）：
- `PathResolver` 零生产调用（死代码，被手搓两层版取代）。
- 5 种 "root"、3 套沙箱检查、4 处 `__file__` 遍历（3 种公式）、散在两文件的 `replace('.',os.sep)` 模块名↔路径耦合。
- `HostService.save_state` 绕过沙箱（安全缺口）+ `.assets/` 字符串拼接 + `"__EXTERNAL_FILE_REF__"` 魔法哨兵。
- 子 ihost root 绕过 `ProjectDetector`（`engine.py:462-463`）。
- IBCI_SPEC §6.1"统一路径语义"对模块导入为假。

### 产出文件

- 新增 `docs/decisions/ADR-013-unified-response-parsing.md`（Accepted；supersede ADR-009）。
- 新增 `docs/decisions/ADR-014-media-storage-handle-backing.md`（Accepted；阻塞于 ADR-015）。
- 新增 `docs/decisions/ADR-015-path-system-unification-as-prerequisite.md`（Accepted；media 强制前置 gate）。
- 更新 `docs/decisions/ADR-009-call-llm-raw.md`（Status → Superseded by ADR-013）。
- 更新 `docs/decisions/README.md` 索引（+ Superseded 段、+ Phase 4 Media Foundation Decisions 段）。
- 重写 `docs/NEXT_STEPS.md`（新 P0 阶段序列：P0-1 清债 / P0-2 路径统一 / P0-3 统一解析；media 改为 gated；置入"⛔ 工作模式定论"）。
- 更新 `docs/PENDING_TASKS.md`（新增 §九 PT-ARCH-11~16 + PT-DOC-12 前置技术债）。

### 工作模式定论（强制原则）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

详见 `NEXT_STEPS.md ⛮ 工作模式定论`。本原则凌驾于一切"先出成果再还债"的提议之上；media Phase 4 被显式 gate 在 §九 债务清完之前。

---

## 2026-06-25：PT-ARCH-5 G3 薄提取 + PT-ARCH-10 吞异常审计

测试基线：**1057 passed, 5 skipped**（0 failures，纯重构/日志，无行为变更）。

### PT-ARCH-5 Group 3（薄提取）
- 提取 `LLMExecutorCore._finalize_invoke_result(result, ec)` 共享后处理（回写 `last_llm_result` + None-safe 解包）。
- 4 个 `invoke_*` 方法（`invoke_llm_function`/`_cps`、`invoke_behavior`/`_cps`）的近重复后处理统一委托，消除"改 sync 忘改 CPS"的漂移风险。
- **深统一（3 对 `execute_*`）仍推迟**：需先统一 `_evaluate_segments`/`_cps`，~6h，风险较高。

### PT-ARCH-10（剩余 except-Exception 审计）
- 全量审计 core/ 的 ~35 处 `except Exception:`，分类如下：
  - **12 处真静默 → 补 `core_debugger.trace` 日志**：`runtime_serializer`×4、`host/service`×2、`auto_discovery`×1、`llm_except_frame`×2、`intent`×1、`llm_parsing_strategy`×2
  - **~11 处其实非静默**（已 re-raise / 已 debugger.trace / 已记录错误）——确认无隐藏 bug，无需动
  - **~4 处编译层错误恢复**（lexer/parser/resolver 回溯）——故意控制流，保留
  - **2 处良性**：`module_manager:88`（实际有 `raise`）、`io:27`（stdout 重配置 best-effort，在 print 路径不宜日志）
- 审计结论：除编译层恢复外，**运行时层无一处是掩盖真实 bug 的漏网吞异常**。

### 即时任务版图
Phase 3 多模态、PT-TEST-4（5/5）、PT-ARCH-7、PT-ARCH-5 G3、PT-ARCH-10 全部完成。即时 P0/P1 与已知技术债清空，下一主线为多模态 Phase 4。

---

## 2026-06-25：IbDict 错误类型统一 + PT-ARCH-7 静默吞异常治理

测试基线：**1057 passed, 5 skipped**（0 failures，无行为回归）。

### A. IbDict 错误类型统一（错误一致性修复）
- `IbDict.__getitem__` 缺键由原始 `KeyError` 统一为 `InterpreterError("KeyError: '{k}'")`，与 IbList/Tuple/String 越界行为一致（也匹配 IbDict.pop 既有风格）。
- **附带修复潜在 bug**：IbDict 存在**两个** `__getitem__` 定义（collections.py:278 与 :325），后者（无错误处理）覆盖前者。删除劣质重复版本，保留修复版。
- 风险核查：全代码库无任何处专门 catch IbDict 的 KeyError（`module_manager:146` 的 `except (InterpreterError, KeyError)` 是变量查找路径，与 dict 下标无关）。

### B. PT-ARCH-7 Phase 4-5：静默吞异常可观测化（11 处）
- 将 11 处 `except Exception: pass` 收窄为 `except Exception as e: core_debugger.trace(...)`，纯日志、无行为变更（core_debugger 默认 NONE 级，零开销）：
  - `_prompt.py` ×3（`__to_prompt__`/`to_native`/`__payload_prompt__` fallback 链）
  - `objects/kernel/base.py` ×2（cast via `__to_prompt__` / `__from_prompt__` 解析）
  - `vm/handlers/_shared.py` ×3（模块导入 / set_variable 回退 / unpack 提取）
  - `engine.py` ×1（collect 跳过不可转换值）、`interpreter.py` ×1（预评估允许失败）、`media.py` ×1（`_extract_media_storage` to_native 回退）
- `_scheduler.py __del__` 析构器**有意保持静默**（析构期日志是反模式，且可能在解释器关闭时自身失败）。

### 发现（非本轮范围）
- PT-ARCH-7 文档称"10 处"，实际 core/ 共 ~35 处 `except Exception:`。本轮处理了 11 处运行时有意图的吞异常；剩余 ~24 处多为编译层错误恢复（lexer/parser/resolver）或序列化可选路径，属另一类问题，建议作为独立审计项（见 PENDING_TASKS）。

---

## 2026-06-25：PT-TEST-4 全部完成（覆盖缺口填补 P0 收官）

测试基线：**1057 passed, 5 skipped**（0 failures，本会话累计 1011 → 1057，+46 测试）。

### area 4：`host/service.py` collect 委托
- 新增 `tests/runtime/test_runtime_host_collect.py`（4 个测试）：无 orchestrator→`RuntimeError` 守护、委托 `request_collect` 返回结果、handle 原样透传、orchestrator 异常向上传播。完整 spawn→collect 流程已由 e2e 覆盖，此处补齐薄包装自身分支。

### PT-TEST-4 收官汇总（5/5）
| 区域 | 测试 | 发现 bug |
|------|------|---------|
| `runtime/path` | 85 | 5（Windows 盘符） |
| `runtime/serialization` | 11 | 1（`define_variable` 协议混淆，反序列化此前完全不可用） |
| `engine.py` 生命周期 | 7 | 0 |
| `kernel/__getitem__` | 13 | 0（1 个不一致观察：dict 缺键 KeyError） |
| `host/service collect` | 4 | 0 |

> **方法学验证**：本会话证明"补覆盖缺口"的高价值在于暴露潜伏的回归级 bug——serialization 的反序列化此前从未可用（零测试是主因），Phase 3 注册三处断链亦由 e2e 暴露。

---

## 2026-06-25：PT-TEST-4 kernel/__getitem__ 契约覆盖

测试基线：**1053 passed, 5 skipped**（0 failures，较上轮 +13）。

### PT-TEST-4 area 3：容器/字符串 `__getitem__` 契约测试
- 新增 `tests/runtime/test_runtime_getitem_contract.py`（13 个测试）：
  - IbList：正/负索引、切片类型保持（list→list）、越界抛 `InterpreterError`
  - IbTuple：索引、切片类型保持（tuple→tuple）
  - IbDict：键访问、缺键行为、IbObject 键拆箱
  - IbString：字符索引（返回 str）、切片（返回 str）、负索引、越界 `InterpreterError`
  - IbObject 键路径（VM 实际传递 IbInteger/IbString，经 `to_native()` 拆箱）

### 观察项（非本轮改动）
- IbDict 缺键抛原始 `KeyError`，而 IbList/Tuple/String 越界抛 `InterpreterError` —— 错误类型不一致，属潜在改进项（已用测试锁定当前实际行为）。

---

## 2026-06-25：PT-TEST-4 engine.py 生命周期覆盖

测试基线：**1040 passed, 5 skipped**（0 failures，较上轮 +8）。

### PT-TEST-4 area 2：`engine.py` 生命周期测试
- 新增 `tests/e2e/test_e2e_engine_lifecycle.py`（7 个测试）：
  - 新引擎未封印/无解释器（惰性初始化）
  - `compile_string` 不封印（编译无 seal 副作用）
  - `execute` 封印注册表（单次执行语义）
  - **封印后重入 `execute` 抛 `PermissionError`**（NEXT_STEPS 指定的核心安全契约）
  - `compile_string` → `execute` 分步流程产出输出
  - `run_string` 单次运行后封印
  - 多引擎实例隔离（A 封印不阻塞 B）
- 此前该模块零覆盖（引擎的单次执行/封印契约无回归守护）

---

## 2026-06-25：PT-TEST-4 serialization round-trip 覆盖 + 反序列化 bug 修复

测试基线：**1032 passed, 5 skipped**（0 failures，较上轮 +11）。

### PT-TEST-4 area 1：`runtime/serialization/` round-trip 覆盖
- 新增 `tests/runtime/test_runtime_serialization.py`（11 个测试）：
  - 值保真 round-trip：primitive（int/float/str/bool）/ list / tuple / dict / 嵌套容器 / None / 空容器 / 混合多变量
  - 结构契约：版本化 payload、factory 必需性、恢复上下文为独立深拷贝
- 此前该模块**零覆盖**（消费者 HostService save/load_state、rt_scheduler isolation snapshot 无任何回归守护）

### 反序列化 bug 修复（round-trip 测试暴露）
- `RuntimeDeserializer._get_scope` 误用 `scope.define_variable(...)`（那是 `RuntimeContextImpl` 的方法），而 `ScopeImpl` 只有 `scope.define(...)` —— 协议混淆。
- **影响**：`deserialize_context` 对任何含变量的上下文都抛 `AttributeError`，即反序列化**从未真正可用**。零测试是它能潜伏的原因。
- 修复：`core/runtime/serialization/runtime_serializer.py` 改为 `scope.define(...)`（签名匹配）。

---

## 2026-06-25：Phase 3 多模态文件 I/O 完成 + 注册缺口修复

测试基线：**1021 passed, 5 skipped**（0 failures）。

### Phase 3 P0：file.read_audio/image/video
- `ibci_file` 插件扩展：`read_audio`/`read_image`/`read_video`（读字节 → `MediaStorage` → 经 `kernel_registry.get_class()` 装箱为 `IbAudio`/`IbImage`/`IbVideo`）
- `_spec.py` vtable 注册三函数（`return_type`: audio/image/video）；版本 2.3.0 → 2.4.0
- 4 个 e2e 测试（`tests/e2e/test_e2e_multimodal_file_io.py`）：MOCK 模式下 `audio x = file.read_audio(...)` + `@~ ... $x ... ~` 端到端跑通

### Phase 3 注册缺口修复（关键 bug，由 e2e 测试暴露）

> 此前 `COMPLETED.md` 声称"完整注册路径 + builtin_initializer 方法绑定"已完成，实际存在三处断链，导致 `audio`/`image`/`video` 类型从未真正进入类型系统。

1. **IbSpec 缺口**：axiom 已注册但对应 IbSpec 从未创建 → `metadata_registry.resolve("audio")=None` → `builtin_initializer` 静默跳过 IbClass 创建。
   - 修复：`core/kernel/spec/specs.py` 新增 `AUDIO_SPEC`/`IMAGE_SPEC`/`VIDEO_SPEC`（CLASS kind，parent Object）；`_runtime.py` 注册元组 + `__init__.py` 导出。
2. **`get_axiom` 调用错误**（`builtin_initializer.py` 媒体块）：直接把 IbSpec 传给 `AxiomRegistry.get_axiom`（期望字符串名）→ 永远返回 None → `__payload_prompt__` 从未注册。
   - 修复：改用 `SpecRegistry.get_axiom(spec)`（内部经 `spec.get_base_name()` 取名）。
3. **lambda 闭包晚绑定**（`builtin_initializer.py` 媒体块）：循环变量 `_media_type_name`/`_axiom_ref` 晚绑定到最后值 `"video"`，导致三种类型的 `__to_prompt__` 全显示 "video"、`__payload_prompt__` 全用 VideoAxiom。
   - 修复：用默认参数 `tn=_type_name` / `ax=_axiom_ref` 在定义时绑定。

### 测试
- 5 个 runtime 层测试（`tests/runtime/test_runtime_multimodal_dispatch.py`）：真实媒体对象 `_obj_to_payload` 分发 + base64 round-trip + `__to_prompt__` 类型名回归（守护缺口 3）

---

## 2026-06-24：全量分析体检 + 架构改善 + Phase 3 多模态基础

测试基线：**1011 passed, 5 skipped**（0 failures）。工作日志见 `docs/worklogs/`。

### P0 基线修复（commit 72f59e6）
- 修复 11 个测试失败（6 个编码 + 5 个 Windows 路径转义）
- 跨盘硬化：`safe_relpath()` + `pytest_configure` basetemp
- 修复 `interpreter.py:128` `symbol.spec` → `declared_type`（Critical）
- 修复 `kernel.py` 裸 `except:` → 正确错误传播（Critical）
- 修复 `llm_executor.py` `_pending_futures` 无锁并发竞争

### P1 架构健康修复（commits 55288e8~fa4c28d）
- 提取 `core/runtime/shared/` 打破 3 个 runtime 内循环
- 移动 `HostInterface` → `core/kernel/`（修复 compiler→runtime 反转）
- 移动 `fuzzy_json.py` → `core/base/support/`（恢复 kernel 永不导入 runtime）
- 拆分 `handlers.py`（2022 行 → 8 个子模块）
- `pytest.ini` + GitHub Actions CI 矩阵
- 层级元测试（31 个静态检查）+ 迁移 4 个违规文件
- MOCK 指令独立测试（20 个）
- 审计报告已解决标注 + Hub 文档锚点修复

### 6 个 God Module 拆分（commits 87e9ffb~9be0984）
- `type_checking_pass.py`（1490 行 → shell + 4 mixin）
- `primitives.py`（1350 行 → 8 子模块 package）
- `spec/registry.py`（1146 行 → 7 mixin package）
- `llm_executor.py`（1132 行 → 5 mixin package）
- `builtins.py`（1054 行 → 5 子模块 package）
- `objects/kernel.py`（1196 行 → 7 子模块 package）

### 代码质量改善（commits 78e5214~7fd085f）
- LLM-error axiom 工厂折叠（4 类 → 共享基类 + 配置子类）
- capability accessor 统一（6 getter → `_get_cap` 助手）
- `IbString.to_bool/cast_to` 越层访问修复（LLM-aware 逻辑迁移到 interpreter/VM 层）
- 裸 `except:` 全部收窄（core/ 中零裸 except:）
- `from e` traceback 链恢复（4 处）
- 关键日志添加（3 处：字段初始化/axiom 注册/模块导入）
- 死代码清理：`IbStatelessPlugin` 删除 + `__hash__` 修复 + 死分支删除

### Phase 3 多模态基础（commit 363fcd7）
- `AudioAxiom`/`ImageAxiom`/`VideoAxiom`（`has_payload_prompt_cap`）
- `MediaStorage`（Phase 3 纯内存，ADR-007）
- `IbAudio`/`IbImage`/`IbVideo`（`@register_ib_type`，IbValue 子类）
- 完整注册路径 + `builtin_initializer` 方法绑定
- 36 个新测试

### 路径测试 + bug 修复（commit 4cb4ef7）
- 85 个路径单元测试覆盖 IbPath/PathResolver/PathValidator
- 发现并修复 5 个 Windows 盘符处理 bug

### ADR 制度（commits d6890d2~a219878）
- `docs/decisions/` 目录 + ADR-007~012（6 份决策记录）
- 解除 Phase 3 全部 6 个阻塞条件

### 文档更新
- `IBCI_SYNTAX_REFERENCE.md` 新增 `@NAME~` 路由（§7.5）+ `__payload_prompt__`（§7.6）
- `AUDIT_REPORT_20260527.md` 已解决标注
- `SEMANTIC_COVERAGE_MATRIX.md` + `VM_SPEC.md` 刷新

测试基线：**838 passed, 2 skipped**（0 failures）。

- **super() SEM_001 修复**：`SymbolResolutionPass.visit_IbFunctionDef` 现在为类方法注入 `super` 符号（使用固定 UID `"builtin:super"` 与 runtime `IbSuperProxy` 注入对齐）。此前 `super()` 在编译期被标记为"未定义符号"，导致 `IBCI_SYNTAX_REFERENCE §6.4` 文档示例无法编译。
- **__restore__ 冗余调用消除**：
  - `vm_handle_IbRetry`：移除 `restore_snapshot` 调用——`retry` 语句现只设置 hint + `should_retry` 标志
  - `vm_handle_IbLLMExceptionalStmt`：添加 `first_iteration` 守卫，首次迭代跳过 restore（刚 save_context 完成，状态一致）
  - 效果：`__snapshot__` 恰好调用 1 次（帧创建），`__restore__` 恰好每轮 retry 调用 1 次（无冗余）
- **super() e2e 测试**：新增 `TestE2ESuperCall` 测试类（6 个测试用例），覆盖 `super().__init__`、`super().method()`、多级继承、虚方法分发保持等场景
- **文档更新**：KNOWN_LIMITS §六更新 `super()` 规避方案代码示例

---

## 2026-05-27：紧急 Bug 修复 + KNOWN_LIMITS 文档大扫除

测试基线：**832 passed, 2 skipped**（0 failures）。

- **BUG #A 修复**：统一 `if`/`while`/`for` 在 LLM 条件不确定时的语义——`vm_handle_IbIf` 和 `vm_handle_IbWhile` 原先静默吞掉 uncertain 条件（跳过分支/退出循环），现改为与 `vm_handle_IbFor` 一致，抛出 `LLMParseError`（由 `llmexcept` 接管或向用户报错）
- **示例修复**：`examples/01_getting_started/03_flow_control_and_behavior.ibci` 改用 MOCK 指令确保零配置跑通
- **示例修复**：`examples/03_advanced_features/isolation_demo/parent.ibci` 路径修正（`./sub_project/child.ibci`）
- **KNOWN_LIMITS 文档大扫除**：
  - 移除已修复条目（旧§1/§2/§6/§8/§9/§16.1-16.3/§16.5/§16.6/§22/§23/§24/§25）
  - 修正过时描述：旧§12.3（容器快照已通过 deep_clone 正确还原）、旧§20.4（`__snapshot__`/`__restore__` 协议已实现）、旧§10（VMExecutor 已支持复杂表达式字段默认值）、旧§20.3/§20.5（SEM_092/SEM_091 已实现）
  - 重新编号，精简至 16 节（从 26 节缩减）

---

## 2026-05-27：Phase 2 `__payload_prompt__` 多模态 payload 协议实现完成

测试基线：**832 passed, 2 skipped**（0 failures）。

- **Phase 2**：多模态 payload 构建基础设施——`__payload_prompt__` 协议层 + `_obj_to_payload()` 分发 + `_evaluate_segments_cps` 混合 content blocks + AIPlugin 多模态 API 调用
- **新协议**：`has_payload_prompt_cap` 标志 + `__payload_prompt__` 方法（TypeAxiom/BaseAxiom 层）
- **新方法**：`LLMExecutorImpl._obj_to_payload()`、`AIPlugin._flatten_content_parts()`、`AIPlugin._build_user_content()`
- **架构特性**：receive() 分发一致性、相邻 str 合并、纯文本路径零开销向后兼容、MOCK 模式展平处理
- **测试**：`tests/e2e/test_e2e_multimodal_payload.py` 覆盖 13 个场景（向后兼容、辅助方法、协议分发）
- **技术债记录**：payload 验证层待实现、`_call_llm_raw` 待 Phase 4、dispatch_eager 多模态交互测试待补充

## 2026-05-27：Phase 1 命名模型路由实现完成

测试基线：**818 passed, 2 skipped**（0 failures）。

- **Phase 1**：`@NAME~` 语法端到端路由实现——VM handler 提取 `tag` 字段 → `LLMExecutorImpl` 接收 `target_model` 参数 → `AIPlugin.__call__` 路由到命名模型配置
- **新 API**：`ai.register_model(name, url, key, model)` — 注册命名模型用于路由
- **架构特性**：命名模型客户端缓存、tag 大小写敏感（精确匹配）、后向兼容（空 tag 走默认路径）
- **测试**：`tests/e2e/test_e2e_model_routing.py` 覆盖 7 个场景（默认路径、注册模型路由、字母数字 tag、MOCK 模式兼容、多模型并存、大小写敏感、大小写区分注册）
- **文档修正**：更正 `MULTIMODAL_BEHAVIOR_DESIGN.md` 中关于 `isalpha()` 的错误声明（实际源码使用 `isalnum()`），更新 Phase 1 状态为已完成

## 2026-05-27：P0-3 统一初始化路径完成

测试基线：**812 passed, 2 skipped**（0 failures）。

- **P0-3**：实现 `_bind_operator_method()` 显式绑定运算符方法，消除技术债，架构对称性完成
- 用户类与内置类运算符绑定机制差异已文档化
- 编译期保证 + 运行期 `receive()` 统一派发

---

## 2026-05-26：P0-C `nonlocal` 关键字全链路实现完成

测试基线：**790 passed, 2 skipped**（0 failures）。

- **P0-C**：`nonlocal` 关键字完整实现——Lexer（`TokenType.NONLOCAL`）→ Parser（`IbNonlocalStmt`）→ SymbolResolutionPass（`_collect_nonlocal_names` + `_prescan_body_locals` 跳过 + `visit_IbNonlocalStmt` 外部绑定验证）→ BindingAnalysisPass（Cell 提升标记）→ VM（`vm_handle_IbFunctionDef` Cell 闭包构建 + 写回）
- **错误诊断**：SEM_060（模块级 nonlocal 禁止）、SEM_061（外部作用域无此变量）
- **测试**：`tests/compiler/semantic/test_nonlocal.py` 覆盖 11 个场景（简单写回、多变量、计数器模式、两层嵌套、返回闭包读/写、多闭包共享 Cell、错误诊断、lambda 交互）
- **INV-CONTEXT-2 合约测试解除 SKIP**：使用 nonlocal 语法实现"多闭包独立帧"测试

---

## 2026-05-26：P0-A/B 行为表达式一般化完成

测试基线：**778 passed, 3 skipped**（0 failures）。

- **P0-A**：解除 3 项 SKIP 测试（INV-BEHAVIOR-4, INV-CONTEXT-1, INV-CELL-2）— 底层实现已到位，编写正式测试验证
- **P0-B**：行为表达式参与二元运算（INV-BEHAVIOR-3）— `TypeCheckingPass.visit_IbBinOp/visit_IbCompare` 增加 behavior 操作数适配
- **确认为设计限制**（保持 SKIP）：INV-LAMBDA-3（无 walrus/lambda 体赋值）、INV-SCOPE-1（SEM_002 禁止 if-block 重声明）

---

## 2026-05-25：Semantic Pipeline 5 步架构改进全部完成 + OOP 诊断增强

测试基线高峰：**806 passed, 7 skipped**（后经测试合并降至 778）。

- **PT-ARCH-1→5 全部完成**：
  - Step 1: TypeEnvironment → TypeInferenceState（frozen dataclass）
  - Step 2: ScopedVisitor 统一基类
  - Step 3: `SpecRegistry.resolve_call_return()` 统一类型决议
  - Step 4: 7-Pass 归并为 4-Phase（SymbolPhase → TypePhase → BindingPhase → IntegrityPhase）
  - Step 5: PassOutput + Immutable Pipeline + MetadataStore.from_outputs()
- **P2-B SEM_090**：intent_context 静默无效陷阱警告
- **P2-C SEM_091**：编译期 cast 转换合法性校验
- **P2-D SEM_092**：方法重写签名兼容性检查（逆变参数 + 协变返回）
- **P2-E SEM_093**：super() 调用合法性检查

---

## 2026-05-24–25：v2 Semantic 全面替代 v1

- **v2 默认启用 + 12 项 parity 修复**（锚点 C）
- **v2 100% 输出 parity**（锚点 B）：SEM_052 read-only + node_to_symbol 100% + 对比测试套件
- **TypeCheckingPass 静态诊断补全**（锚点 D）：fn 签名结构检查、Lambda 类型安全、泛型容器、Optional、Tuple 位置推断
- **v1 代码完全删除**：`semantic_v2` → `semantic` 重命名完成

---

## 2026-05-22：P1 全套完成 + P0 三项基础修复

- **P1-A**：文档与 v2 自我矛盾收口
- **P1-B**：核心设计原则补全（auto 单次锁定、any 永久动态、-> auto 统一、BinOp 公理自决议）
- **P1-C**：TypeCheckingPass 新增 17 个 visitor
- **P1-E**：独立 TypeResolutionPass
- **P1-F**：`_bind_llm_except` 复刻到 v2
- **P0 三项**：H5 测试基线恢复 + 双写真相收敛 + v2 阻塞 bug 修复

---

## 2026-07-17：PT-ARCH-21-FU 路径整合收尾完成

测试基线：**1146 passed, 7 skipped**（0 failures）。

- **rt_scheduler 死代码清理**：删除 `dispatch()` 方法、`spawn()` 内已不可达的隔离分支（`ModuleDiscoveryService` / `ModuleLoader` 局部重发现），删除 `_resolve_install_path` 辅助方法；从 `core/runtime/interfaces.py` 移除 `ExecutionRequest` / `ExecutionSignal` 及 `IRuntimeScheduler.dispatch` 协议声明。
- **ProjectDetector IbPath 化**：`core/project_detector.py` 内部路径构造统一使用 `IbPath.from_native` / `/` / `parent` / `to_native`；FS 查询（`isdir`/`isfile`）保留；删除死方法 `is_valid_project_root`。
- **module_system 边界清理**：`core/runtime/module_system/discovery.py` 与 `loader.py` 移除 `__init__` 中冗余的 `os.path.abspath`，添加模块级注释说明 Python importlib 边界保留原生路径。
- **ibci_file relpath 修复**：`ibci_modules/ibci_file/core.py` 将 `os.path.relpath` 替换为 `safe_relpath`，`_read_media_bytes` 扩展名从已解析原生路径取。
- **覆盖缺口 e2e**：新增 `tests/e2e/test_e2e_plugin_discovery.py`（plugin_paths / global_plugin 实际 import 解析、显式配置抑制嗅探）与 `tests/e2e/test_e2e_isolation_plugin_inheritance.py`（子脚本通过 `ihost.run_isolated` 继承父插件）。

提交：见 `feat/PT-ARCH-21-FU` 分支最新提交（含代码、测试、文档一次性切口）。

---

## 2026-05-15 及更早：详细日志

详见 `docs/HISTORY_LOG.md`。主要里程碑包括：

- 2026-05-15：回顾性事实核查 + ARCHITECTURE_REVIEW 报告
- 2026-05-14：one-shot 意图注释语义升级 + H1/H2/H3/H4 维修 + 事实重核
- 2026-05-13：LLM 解析责任链重构 + 代码库健康度审计 + 测试体系契约化
- 2026-05-12：NS-4/NS-6/NS-7 语法清理 + PT-1.2/1.3/3.3 idbg + NS-3/PT-2.1/2.2 CPS 化
- 2026-05-11：lambda/snapshot 语义对齐 + NS-1 CPS 合流 + NS-2 intent OOP 化
- 2026-05-08：类型系统五件套 M1-M5 + VM CPS 全链路 + 语法系统重设计
- 2026-04-28~29：VM CPS 调度循环 + DDG 编译期分析 + 公理化通道

---

## 关联文档

- 类型系统正式设计：`docs/design/TYPE_SYSTEM_DESIGN.md`
- VM 与解释器正式设计：`docs/design/VM_AND_INTERPRETER_DESIGN.md`
- VM 公理化规范：`docs/design/VM_SPEC.md`
- 实现细节备份：`docs/design/ARCH_DETAILS.md`
- 意图系统：`docs/design/INTENT_SYSTEM_DESIGN.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 当前已知限制：`docs/KNOWN_LIMITS.md`
- 历史详细日志：`docs/HISTORY_LOG.md`

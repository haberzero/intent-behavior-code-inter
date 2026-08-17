# ROADMAP — Provider 层分离（近期主线）+ IBCI 原生宿主绑定（远期愿景）

> **定位**：本文件是「LLM provider 层分离收尾（近期、当前最紧要）」与「IBCI 用户层原生绑定
> Python 内容（远期愿景）」的**总路线图与交接主线**——面向下一个干净 session 接手此大任务的
> **单一权威源**。与 `tasks_docs/HANDOFF.md` §2（持久交接动态状态）、`NEXT_STEPS.md`（当前最紧要）
> 配合阅读。本文件描述**方向、两段式目标、阶段切分、验证门、关键裁决点、当前状态与交接**；
> 具体阶段实现细节按 `code-workflow` 在独立分支展开。

---

## 〇、重大方向裁定（用户拍板，2026 主线）

**两段式**：
1. **近期（当前最紧要）**：把 **LLM provider 层分离彻底完成**。当前短期分发为 Python 源码直接
   分发，故**近期几乎不向用户开放语言级自定义 API**；需自定义的少量用户被指引**直接修改内核
   特定文件 `ibci_modules/ibci_ai/core.py`**（推荐 provider 实现，经 `LLMProvider` 契约解耦、
   自包含、可整文件替换），并配修改指导。解耦本身必须做彻底，为远期留位、不返工。
2. **远期（post-近期）**：抛开"用户 Python 侧手写 `_spec.py` 暴露库给 IBCI"的思路，改为
   **IBCI 用户层原生绑定 Python 内容**（宿主导入语法 + 协议/impl 到宿主类型 + 插件体系重构），
   并延伸至内核 IBCI 自举 + 缓存/JIT + 隔离改造 + 反射执行能力。近期不做超前的复杂设计。

**约束**：
- 凡推进的方向必须推进到底，不留妥协/历史包袱/兼容层/tricky；健康中间态仅作脚手架、最终拆除。
- 遵循工作模式定论；原则优先于行为维持；可推翻 IBCI 自身设计缺陷。
- 破坏性重构默认已授权（独立分支实验 + 复核后合入 `unsafe-vibe-dev`；永不触碰 `main`；不 push）。
- 全程本地 commit。

---

## 一、现状实证（已核实的架构事实，路线图的事实基石）

以下为经过逐行核对的关键事实。路线任何阶段都不得与这些事实冲突。

### 1.1 值/宿主边界（已存在）
- `kernel/registry.box()` 能包装**任意** Python 对象：
  - `callable(val)` → `IbNativeFunction`（IBCI 可调用）；
  - 其它 → `IbNativeObject`（`native_module.py`，持 `.py_obj` 的通用对象盒）。
- `unbox()` 把 `IbObject` 值 → 原生 Python。
- **结论：IBCI 已能将任意 Python 对象/可调用对象作为一等值持有与传递。**

### 1.2 成员门控（已有安全边界）
- `IbNativeObject.receive`/`_dispatch_getattr` 只允许 **vtable 方法 + whitelist 属性**；
  未声明成员 → `AttributeError`。
- 通用路径 `box(native)` 构造的 `IbNativeObject` 的 vtable **为空** → 对象能持有但成员对
  IBCI 不可见，除非绑定 vtable。
- **结论：缺"让用户 IBCI 代码按声明导出 native 成员"的干净机制。**

### 1.3 import 解析路径（当前）
- `import X` 解析：(a) InterOp 注册的 **Python 包**（需 `_spec.py` 契约提供 vtable/whitelist）→
  包装为 `IbModule`；或 (b) IBCI artifact 模块。
- **结论：没有"直接导入裸 Python 模块并自动按 IBCI 声明绑定成员"的路径；当前取 Python 包必经
  `_spec.py`（即本路线要推翻的）。**

### 1.4 协议/impl/类型理论（已存在且成熟）
- 用户类 + 泛型（多参/嵌套/继承/协议 bound）能力成熟（`KNOWN_LIMITS.md` §十四）。
- `protocol` / `implements` / retroactive `impl`（可带方法体）——可作为能力契约载体。
- **硬限制**：`impl` 目标须为本模块用户类；**泛型类与内置/宿主类型不支持**（`06_oop.md` §6.8）。
- dunder 协议集 + `receive` 分派 + `Object`/`any` 基元在场（用户 `any`/Object 字段可存 box 值）。

### 1.5 LLM provider 中间层（已落地，半接通）
- 批 1-4 已合入 `unsafe-vibe-dev`：`core/base/llm_protocol/`（`LLMCallRequest`/`LLMCallResult`/
  `LLMProvider`/`ConfigSourceAdapter`/`recommended`）。
- **近期不开放的接口位**：`register_provider`/`set_config_source` 用户入口、`thinking_mode`
  provider 消费、`ConfigSourceAdapter` 替换——这些是**为远期统一的接口位**（近期不造用户入口，
  见 §三.R1），近期只保证契约字段与推荐实现干净正确。

---

## 二、两段式总目标（近期主线 + 远期愿景）

> **总纪律**：凡推进的方向必须推进到底，不留妥协/历史包袱/兼容层/tricky。健康的中间态只作
> 脚手架，最终必须拆除、不留隐患。分析/实现冲突时以"架构正确性 + 设计统一 + 长期收益"裁决。

### 2.A 近期主线（当前，最紧要）—— Provider 层分离彻底完成

当前短期分发形态为 **Python 源码直接分发**，因此：
- **近期几乎不向用户开放"自定义底层"的语言级 API**——不为一个尚无真实用户的新颖能力提前
  透支设计（避免过早抽象）。
- 需要自定义 LLM 底层/供应商/配置格式的用户，被指引**直接修改内核内一个特定文件**
  `ibci_modules/ibci_ai/core.py`（推荐 provider 实现，经 `LLMProvider` 契约解耦、自包含、
  `create_implementation()` 工厂），并配修改指导与注意事项（见 `docs/howto/modify_llm_provider.md`）。
- 近期的核心任务是**把 provider/内核/配置解耦本身做彻底**：
  - 内核只认 `LLMCallRequest`/`LLMCallResult`/`LLMProvider` 契约，不触碰供应商细节；
  - 推荐 provider / 默认配置适配器是干净、可替换的实现，无脏代码、无隐藏耦合；
  - **为远期方案留好接口位**（`ConfigSourceAdapter` 抽象、`thinking_mode` 契约字段等），
    近期只接通用位、不单独造用户入口，避免为未来留额外重构或需拆除的脚手架。

### 2.B 远期愿景（post-近期，不在近期推进）—— 成熟现代方案

- **宿主导入一等语法 + 协议/impl 扩展到宿主类型**：用户用 IBCI 原生类型/协议包装 Python 内容
  （取代"Python `_spec.py` 插件"思路）。
- **内核自举 + 缓存/JIT**：内核引入 IBCI 级别启动包装层 + 三层分解（L0 Python 保底 / L1 内核
  IBCI 层预编译缓存 / L2 用户入口）；`serializer↔rehydrator` 落盘为持久缓存（指纹失效），
  档 A（预编译缓存）优先、档 B（真 JIT）另行评估。
- **隔离改造**：缓存产物只读共享 + 隔离可变状态，提高健康性与可维护性。
- **反射/实时执行 Python**：随宿主绑定能力的成熟而获得（非默认 `exec(python)`）。
- 这些是远期候选，**近期不做**；但近期进行的解耦会为其预留接口位，确保远期不返工。

---

## 三、阶段切分（近期主线 + 远期愿景；每阶段独立分支 + 全量 pytest 零回归 + 复核放行）

### 【近期主线 · 当前】R0 — 现状固化与 Provider 解耦审计
- 确认 `unsafe-vibe-dev` 全量 pytest 基线（以实跑为准，不冻结数字）。
- 审计 provider 层当前解耦面：内核 `_call_llm` 是否已完全不碰供应商细节；`_prompt_assembly`
  是否已收敛（仅 retry 消息）；`thinking_mode`/`probe` 是否半接通；`ConfigSourceAdapter` 是否
  硬编码默认、但**抽象与推荐实现分离干净**（可为远期替换留位）。
- **验证门**：全量 pytest 绿；无半接通/无脏耦合（grep + 残留扫描）。

### R1 — Provider 层接口位清理（为远期留位，但不造近期用户入口）
- 把 `thinking_mode`、`probe()`、`ConfigSourceAdapter` 等**面向远期替换但当前尚未完全接电**的
  契约点，收敛为"契约字段存在 + 推荐实现干净 + 当前默认行为正确"，**不新增语言级注册 API**。
- 确保推荐 provider（`core.py`）+ 默认配置适配器（`config_source_adapter.py`）是**自包含、可整文件替换**
  的干净实现，替换路径清晰（改 `core.py` / 换 adapter 注入点集中）。
- **验证门**：全量 pytest 零回归；无新增未用接口（code-quality 半接通红线）。
- **独立分支**：`exp/provider-decouple-r1`。

### R2 — 近期分发指导文档（Python 源码分发形态）
- 新增 `docs/howto/modify_llm_provider.md`：指引"修改 `ibci_modules/ibci_ai/core.py` 自定义
  LLM 底层/供应商/配置"，含：文件职责、`LLMProvider` 契约方法（`call`/`stream`/`probe`/`get_retry`）、
  修改点与注意事项（思考抑制字段、返回类型提示、如何换配置适配器）、改动后全量回归。
- 更新 `docs/architecture/01_principles.md` §3.7：明确"近期=改内核文件；远期=原生绑定"两段式定位。
- **验证门**：文档与代码一致（governance 自检）；全量 pytest 零回归。

### 【近期主线收尾】：R0-R2 完成后，Provider 层分离即"彻底、干净、分叉口就绪"——
远期愿景不在此开展，但接口位已留、无返工债务。

---

### 【远期愿景 · post-近期】F0 — Native Binding 地基验证
- 证明 `box`/callable→用户 IBCI 类导出可行，产出宿主绑定机制设计底稿
  （`docs/architecture/01_native_host_binding.md`）。
- **验证门**：全量 pytest 绿；设计文档与代码一致。

### F1 — 宿主导入一等语法 + 用户类持有 native
- 宿主导入（`host lib = python.import("pkg")`）+ 用户 IBCI 类/`any` 字段持 `IbNativeObject`，
  显式绑定到 IBCI 声明方法（非自动穿透）。
- **验证门**：e2e（`.ibci` 绑定宿主 callable 并调用成功）；全量 pytest 零回归。

### F2 — 协议/impl 扩展到宿主类型
- `impl`/`implements` 目标扩展到"宿主导入类型"；编译期成员并集（类自身 + impl + 宿主绑定）。
- **验证门**：`impl SomeProto for HostValue:` 用例；全量 pytest 零回归。

### F3 — 插件体系重构（废弃 Python `_spec.py` 思路）
- 既有 `_spec.py` 插件按新绑定统一 / 废弃 / 内核原生隔离；**不保留双通道**。
- **验证门**：全量 pytest 零回归 + 既有插件用例按新语义重构。

### F4 — Provider 自定义经新绑定统一（接 R 期留位）
- `thinking_mode`/`ConfigSourceAdapter`/provider 注册用 F1-F3 新绑定实现（R 期统一位），
  逆 R 期的"改内核文件"临时态，成为"成熟现代方案"。
- **验证门**：全量 pytest 零回归 + 自定义 provider e2e + T09 真实 LLM 复跑。

### F5 — 架构统一 / 文档收敛（含内核自举 + 缓存/JIT / 隔离改造 / 反射能力的规划评估）
- 补齐原生绑定语法/协议/用户 IBCI 库文档；评估并落地档 A（缓存预编译）→ 档 B（真 JIT）。
- **验证门**：全量 pytest 零回归；无 stub/半接通；脚手架全部拆除。

---

## 四、关键裁决点（触及对外契约/语言机制，需用户拍板）

> 近期（R0-R2）无待拍板的语言级契约变化。以下为**远期愿景（F 段）**推进时需定的裁决点，
> 近期不留存。

1. **宿主绑定语法形态**：一等关键字 `host`/`native`（如 `host lib = python.import("pkg")`）
   vs 借助既有 `import` 扩展 vs 独立 `bind` 语句。→ 影响 F1，届时定。
2. **"宿主导入类型"在类型系统的地位**：作为一等类型（可被 `impl`/协议引用）还是受限的
   `any` 子类？→ 影响 F2 与类型理论。
3. **旧 `_spec.py` 用户插件的归宿**（F3）：删除 / 降级为"内核开发者专用" / 保留为新绑定的编译目标。
   → 影响破坏面。
4. **provider 自定义（F4）与 R 期"改内核文件"临时态**：R 期是健康的近期脚手架（Python 源码分发
   下合理），F4 用原生绑定统一后**彻底拆除**该临时态——这两者不是双通道（R 期是近期唯一的用户面，
   F4 是远期替换），但须保证移交时不并存。

---

## 五、当前进度与交接状态

- **已合入 `unsafe-vibe-dev`**：LLM provider 中间层批 1-4（契约 + 内核收口 + provider 插件化 +
  内省/文档），全量 pytest 3027 pass。当前 provider 分离的内部结构已干净。
- **近期未开放用户自定义**：`register_provider`/`set_config_source` 等 WIP 已回退；
  近期限定"修改 `ibci_modules/ibci_ai/core.py`"这一条路径。设计要点保留于 git 历史 +
  本路线图 §三.R1（为远期统一留位，不近期造用户入口）。
- **触发此两段式规划**：用户裁定近期聚焦 provider 分离（Python 源码分发，改内核文件），
  远期才做原生绑定成熟方案；任何方向都要求彻底、不留脚手架。
- **交接**：下一 session 从 §三.近期主线 R0 开始；详细交接见 `tasks_docs/HANDOFF.md` §2。

---

## 六、工作纪律（延续 AGENTS.md）

- 禁 push；只本地 commit。破坏性重构独立分支实验、复核后合并 `unsafe-vibe-dev`，永不碰 `main`。
- 工作模式定论；质量红线（禁兜底/双通道/历史包袱）；原则优先于行为维持。
- 每阶段全量 pytest 零回归 + 提交 + 同步 NEXT_STEPS/WORKLOG。
- 分析/实现均须加载匹配 skill（code-workflow / code-quality / design-philosophy / self-grill 等）。

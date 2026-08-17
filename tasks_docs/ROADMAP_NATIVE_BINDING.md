# ROADMAP — IBCI 原生宿主绑定重构（路线 X：IBCI 用户层原生包装 Python 内容）

> **定位**：本文件是「IBCI 用户代码层 ↔ Python 代码层」原生绑定重构的**总路线图与交接主线**——
> 面向下一个干净 session 接手此大任务的**单一权威源**。
> 与 `tasks_docs/HANDOFF.md` §2（持久交接动态状态）、`NEXT_STEPS.md`（当前最紧要）配合阅读。
> 本文件描述**方向、目标、阶段切分、验证门、决策记录与现状实证**；具体阶段实现细节按
> `code-workflow` 在独立分支展开（临时 `_code_*.md` 细化为阶段内再写）。

---

## 〇、重大方向裁定（用户拍板，2026 主线）

**抛弃"用户在 Python 侧手写 `_spec.py` 来暴露库给 IBCI"的思路。**
改为 **IBCI 用户代码层原生包装 Python 原生内容**——用户用 IBCI 原生类型/协议/`impl`/
宿主绑定语法来表达能力契约，把 Python 对象绑定到 IBCI 声明的成员背后；
宿主导入（取到 Python 模块/类/对象与 callable）成为 IBCI 一等语法，而非插件 `_spec.py`。

**约束**：
- 是**彻底重构**，不是局部补丁；审查既有插件体系后按新思路**重构或废弃**，不留双通道。
- 遵循工作模式定论（禁止 compat shim / 胶水 / tricky）；原则优先于行为维持；可推翻 IBCI
  自身设计缺陷。
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
- **未接线**：`register_provider`/`set_config_source` 用户入口；`thinking_mode` 内核不填、provider
  不读；`ConfigSourceAdapter` 硬编码默认。→ 这些是"输入面自定义"子目标（见 §三.P1）。

---

## 二、目标（路线 X 的完整愿景）

1. **宿主导入一等语法**：IBCI 用户代码能直接在 `.ibci` 里取到一个 Python 模块 / 类 / 对象 /
   callable，作为一等值。
2. **IBCI 声明绑定 native 成员**：用户用 IBCI 类型/协议/`impl` 定义能力接口，把 Python 对象的
   成员绑定到这些 IBCI 声明之后（而非在 Python 里写 `_spec.py`）。
3. **协议/impl 扩展到宿主类型**：让 `protocol implements` / retroactive `impl` 能作用于"宿主导入
   类型"，从而用户能对 Python-backed 值声明协议满足与补方法。
4. **插件体系按新思路重构**：审查既有 `_spec.py` 插件机制，决定重构为"用户 IBCI 库 + 可选宿主
   绑定"或废弃；不留双通道。
5. **输入面（LLM provider 等）自定义落地**：`ai.register_provider` / `set_config_source` /
   `thinking_mode` 全部接通，成为新绑定机制的首个真实用例与验证场。
6. **架构统一**：整个"用户代码层 ↔ 底层代码层"交互只有一套设计语言、一个配合模式、
   单一权威源；宿主绑定与协议/类型理论机制同构。

---

## 三、阶段切分（依赖驱动；每阶段独立分支 + 全量 pytest 零回归 + 复核放行）

> 原则：先做"地基验证"（证明 box/callable→用户 IBCI 类导出可行），再做"语言机制"，
> 再"协议/impl 扩展"，再"插件重构"，最后"输入面用例 + 文档统一"。

### P0 — 基线固化与研究底稿
- **确认**当前 `unsafe-vibe-dev` 全量 pytest 基线（以实跑为准，不冻结数字）。
- 清点需触动的内核面：`box/unbox`、`IbNativeObject`、`IbNativeFunction`、`IbImport` 解析、
  `impl` 语义/编译期检查、`Object`/`any` 字段、协议满足检查。
- 产出 `docs/architecture/01_native_host_binding.md`（宿主绑定机制设计起点）。
- **验证门**：全量 pytest 绿；范围分析文档与实际代码一致（grep 交叉核验）。

### P1 — 宿主导入一等语法 + 用户类持有 native（最小可用闭环）
- 新增语言机制：宿主导入（如 `host lib = python.import("pkg")`），把裸 Python 模块/对象绑定
  （按用户 IBCI 声明导出成员），返回可持有一等值。
- 让用户 IBCI 类 `Object`/`any` 字段能干净持有 `IbNativeObject`，并通过用户 IBCI 声明的方法把
  调用转发到 `.py_obj`（显式绑定，非自动穿透）。
- 目标：**一个最小示例**——用户 `.ibci` 里取 Python callable/对象，用 IBCI 类包它、调用它，
  不经 `_spec.py`。
- **验证门**：新增 e2e（从 `.ibci` 绑定一个宿主 callable 并成功调用返回）；全量 pytest 零回归。
- **独立分支**：`exp/native-binding-p1`。

### P2 — 协议/impl 扩展到宿主类型
- 扩展 `impl` / `implements` 语义：允许目标为"宿主导入类型"（系统引入的一等宿主类型），
  用户可对 Python-backed 值声明协议满足、`impl` 补方法（读 `self` 与宿主绑定的成员）。
- 编译器/语义层改动：类型满足检查、成员并集（类自身 + impl + 宿主绑定声明）。
- **验证门**：新增用例（`impl SomeProto for HostValue:` 内调用宿主绑定成员）；全量 pytest 零回归。
- **独立分支**：`exp/native-binding-p2-protoimpl`。

### P3 — 插件体系重构（废弃 Python `_spec.py` 思路，按新绑定统一）
- 审查既有 `_spec.py` 插件（ibci_json/math/time/schema/net + ai/file/ihost/idbg/isys）在新机制下的
  归宿：或改写成"用户 IBCI 库 + 宿主绑定"，或废弃，或保留为内核原生（不通用户手写）。
- **不保留双通道**：新绑定是唯一"用户扩展底层"途径；旧 `_spec.py` 用户插件路径按裁决删除或降级。
- **验证门**：全量 pytest 零回归 + 既有插件用例在新机制下行为不变（或按新语义重构用例）。
- **独立分支**：`exp/native-binding-p3-plugin`。

### P4 — 输入面落地（LLM provider / 配置源自定义，作为新机制的真实用例）
- 接通 `ai.register_provider`（经宿主绑定/模块路径）、`set_config_source`、`thinking_mode`
  （内核填 + provider 消费）——用 P1-P2 的新绑定机制作为"用户自定义 provider"的规范写法。
- 补 `docs/howto/custom_llm_provider.md`。
- **保留的设计要点（源自已回退的 WIP，供 P4 复用）**：
  - 委托容器：`AIPlugin` 仍为 `CAP_LLM_PROVIDER` 唯一注册对象，内部设 `_delegate_provider`，
    `call/stream` 委托；内核侧零改动。
  - `register_provider(provider_or_path)`：接受宿主对象或模块路径（`importlib` +
    `create_implementation()` 工厂约定 + `invalidate_caches()`）。
  - `thinking_mode`：provider 读 `request.thinking_mode`（on/off/auto；auto fallback 模型能力）
    决定 `enable_thinking`，不硬编码。
  - `set_config_source(adapter_or_path)`：`AIPlugin._config_source` 可注入，`load_project_config`
    经它（默认 `ProjectApiConfigAdapter`；`load_raw_dict` 缺省时按 mock=False）。
  - vtable 增 `register_provider`/`set_config_source`。
  - 测试：注册委托/thinking 消费/适配器替换 单元 + e2e（模块路径注册真实调用自定义 provider）。
- **验证门**：全量 pytest 零回归 + T09 真实 LLM 复跑（内置 provider 行为不变）+ 自定义 provider
  e2e。
- **独立分支**：`exp/llm-user-customable`（承接，先前 WIP 已回退，按新机制重做）。

### P5 — 架构统一与文档收敛
- `docs/architecture/01_principles.md` 更新宿主绑定机制章节（替换"插件=Python `_spec.py`"叙述）。
- `docs/syntax/` 补宿主绑定语法、协议/impl 宿主类型、用户 IBCI 库（非 Python 插件）编写指南。
- `docs/howto/write_user_lib.md`（替代/补充 write_user_plugin.md，改为"用 IBCI 写扩展"）。
- **验证门**：全量 pytest 零回归；文档与代码一致（governance 自检）；无 stub/半接通。
- **独立分支**：`exp/native-binding-p5-doc`。

---

## 四、关键裁决点（触及对外契约/语言机制，需用户拍板）

1. **宿主绑定语法形态**：一等关键字 `host`/`native`（如 `host lib = python.import("pkg")`）
   vs 借助既有 `import` 扩展 vs 独立 `bind` 语句。→ 影响 P1，需定。
2. **"宿主导入类型"在类型系统的地位**：作为一等 IOC 类型（可被 `impl`/协议引用）还是受限的
   `any` 子类？→ 影响 P2 与类型理论。
3. **旧 `_spec.py` 用户插件的归宿**（P3）：删除 / 降级为"内核开发者专用" / 保留为新绑定的编译目标。→
   影响破坏面。
4. **输入面（P4）是否必经 P1-P2**：若先做"模块路径 + 宿主注入"的临时路径（低风险）再在 P2 后统一到
   原生绑定，是否接受"临时宿主注入"这一中间态？（工作模式定论禁 compat shim，故倾向直接走 P1-P2。）

---

## 五、当前进度与交接状态

- **已合入 `unsafe-vibe-dev`**：LLM provider 中间层批 1-4（契约 + 内核收口 + provider 插件化 +
  内省/文档），全量 pytest 3027 pass。
- **已回退**：`exp/llm-user-customable` 上的 provider WIP（含 `register_provider`/thinking_mode 半成品），
  待 P4 按新机制重做。设计要点保留于 git 历史 + 本路线图 §三.P4。
- **触发此路线**：用户裁定抛弃"Python `_spec.py` 插件"思路，转向"用户 IBCI 层原生绑定 Python 内容"。
- **交接**：下一 session 从 §二/§三 开始，按 P0 → P5 推进；详细交接见 `tasks_docs/HANDOFF.md` §2。

---

## 六、工作纪律（延续 AGENTS.md）

- 禁 push；只本地 commit。破坏性重构独立分支实验、复核后合并 `unsafe-vibe-dev`，永不碰 `main`。
- 工作模式定论；质量红线（禁兜底/双通道/历史包袱）；原则优先于行为维持。
- 每阶段全量 pytest 零回归 + 提交 + 同步 NEXT_STEPS/WORKLOG。
- 分析/实现均须加载匹配 skill（code-workflow / code-quality / design-philosophy / self-grill 等）。

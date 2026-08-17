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
- 审计 provider 层当前解耦面（精确核对项）：
  1. 内核 `_call_llm` 是否已完全不碰供应商细节（应只调 `llm_callback.call(request)`）；
  2. `_prompt_assembly.py` 是否已收敛为仅 retry 消息结构（系统提示词组装已下沉 `recommended`）；
  3. `thinking_mode` / `probe()` 是否半接通：`thinking_mode` 契约字段存在、内核不填、provider 不读
     （硬编码 `enable_thinking`）；`probe_model` 已委托 `probe()`（单入口，非假重复）；
  4. `ConfigSourceAdapter` 抽象与推荐实现 `ProjectApiConfigAdapter` 分离是否干净（推荐实现可整文件替换，
     `load_project_config` 是否硬编码默认适配器）；
  5. **`core.py` 职责混杂面（关键）**：802 行文件把「纯 provider 逻辑」（`call`/`stream`/`probe`/
     `_assemble_provider_sys_prompt`/`_build_messages`/`_post_process_answer`/配置）与「IBCI 模块胶水」
     （`setup`/`run_batch`/`stream_call`/`stream_channel`/意图方法/`save_plugin_state`/经 execution_context
     加载配置）混杂；纯 provider 部分无 kernel import，胶水部分 lazily import
     `core.runtime.frame`/`objects.stream`/`objects.kernel`。这决定"用户改内核文件"的干净度与远期
     "用户 IBCI 类型包装纯 host provider"的前置分裂（→ R1 决策）。
- **验证门**：全量 pytest 绿；无半接通/无脏耦合（grep + 残留扫描：无 `ILLMProvider`、无旧 `_prompt_assembly`
  装配 API、无 vtable 漂移——已初步核验全绿）。

### R1 — Provider 层接口位清理（为远期留位，但不造近期用户入口）
- 把 `thinking_mode`、`probe()`、`ConfigSourceAdapter` 等**面向远期替换但当前尚未完全接电**的
  契约点，收敛为"契约字段存在 + 推荐实现干净 + 当前默认行为正确"，**不新增语言级注册 API**。
- **R1 关键裁决（本次审计新发现，需定）**：是否将 `core.py` 的「纯 provider 逻辑」与「IBCI 模块胶水」
  拆分为两文件——
  - 拆：`provider_impl.py`（纯 `LLMProvider`，无 kernel import —— 用户改这个，真正的"干净可替换单元"）+ 
    `module.py`（`AIPlugin` 作为 ibci `ai` 模块宿主，持胶水、委托 provider_impl）。
  - 不拆：保持单文件，把"改 `core.py` 整个文件"作为近期引导路径（但远期原生绑定仍要拆，届时返工）。
  - **倾向**：拆（让"改内核文件"真正干净、且为远期 native-binding "用户 IBCI 类型包纯 host provider"
    铺路）；但拆会动 `core.py` 内部结构，属重构，须独立分支 + 全量回归 + 复核。
  - **拆的耦合注意点（审计发现）**：纯 provider 若要支持 MOCK 指令/sentinel，`mock_scenario.py` 目前
    依赖 `core.runtime.shared.llm_result`（MOCK sentinel）；分拆时须决定 MOCK 归属（留在模块胶水侧 /
    sentinel 下沉 `core.base`，使纯 provider 保持 kernel-free）——这是拆分设计的关键取舍，不与
    `_model_capabilities`/`_mock_engine` 状态耦合。
  - **R0 审计确认的另两个 R1 前置关注点**：① `load_project_config` 直接实例化
    `ProjectApiConfigAdapter()`——默认适配器"整文件替换"路径 = 替换 `config_source_adapter.py`
    （保持类名）；拆分时该实例化随纯 provider 走还是随模块胶水走，一并定夺。② `thinking_mode`
    半接通实证：`LLMCallRequest.thinking_mode` 字段在内核构造 request 时未填（auto）、provider
    不读 request 字段（payload 硬编码 `enable_thinking=False`，仅经 `ModelSpec.thinking_mode`
    定 `is_reasoning`）——R1 收敛为"契约字段存在 + 推荐实现干净 + 当前默认行为正确"，
    不新增语言级注册 API。<br>
- 确保推荐 provider + 默认配置适配器是**自包含、可整文件替换**的干净实现，替换路径清晰。
- **验证门**：全量 pytest 零回归；无新增未用接口（code-quality 半接通红线）；若拆则确认 kernel import
  边界干净。
- **独立分支**：`exp/provider-decouple-r1`。

### R2 — 近期分发指导文档（Python 源码分发形态）
- 新增 `docs/howto/modify_llm_provider.md`：指引"修改 `ibci_modules/ibci_ai/`（近期单文件 `core.py`，
  若 R1 拆分为 `provider_impl.py` 则是该纯 provider 文件）自定义 LLM 底层/供应商/配置"，含：
  文件职责、`LLMProvider` 契约方法（`call`/`stream`/`probe`/`get_retry`）、修改点与注意事项
  （思考抑制字段、返回类型提示、如何换配置适配器）、改动后全量回归。
- 明确**两类关注点**：纯 provider 逻辑（请求组装/响应解析/思考抑制，用户改这）vs IBCI 模块胶水
  （run_batch/stream_channel/意图/断点状态——不改、随模块宿主走），避免用户误改胶水破坏 `ai` 模块。
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

### F4 — Provider 自定义经新绑定统一（已完成，exp/provider-bind-f4）
- 用户经宿主绑定提供自定义 provider，`ai.set_provider(lib.provider)` 注册为激活
  `llm_provider`（HIGH 优先级覆盖内置默认 RecommendedProvider）；provider 能力经
  capability_registry 惰性 get 使运行期切换生效（内核 LLM 执行器不改架构）。
- 逆 R 期"改内核 provider_impl.py"临时形态：已拆除该文档指导形态（provider_impl.py
  降为内置默认实现，不手动改）；`docs/howto/modify_llm_provider.md` 改写为宿主绑定
  通道。用户面自定义唯一边 = 宿主绑定 + set_provider。
- **验证门达成**：全量 pytest 零回归（2956 passed / 1 skipped）+ 自定义 provider e2e
  （tests/e2e/test_provider_host_binding.py，内核实际调用用户 provider）+ T09 真实 LLM
  复跑（开发环境无真实 LLM 端点，记录留待环境可行时）。

### F5 — 架构统一 / 文档收敛（含内核自举 + 缓存/JIT / 隔离改造 / 反射能力的规划评估）
- 补齐原生绑定语法/协议/用户 IBCI 库文档；评估档 A（缓存预编译）→ 档 B（真 JIT）、
  内核自举、隔离改造、反射能力。
- **评估结论（2026-08-18）**：档 A 缓存 / 内核自举 / 档 B 真 JIT / 隔离改造 / 反射
  能力均列为**远期 pending 规划**（当前"引擎单次执行"模型下收益有限或为规划评估），
  见 WORKLOG；F5 当前聚焦可落地的文档/架构收敛（消除 F0-F4 漂移、目录树校验、分工
  澄清）。done 后更新 NEXT_STEPS/WORKLOG。
- **验证门**：全量 pytest 零回归；docs 与代码一致无漂移。

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
   F4 是远期替换），但须保证移交时不并存。**→ 已落定（F4，2026-08-18）**：用户授权新增 bind-based
   provider 注册 API 并统一 F4；`ai.set_provider` 落地，R 期"改 provider_impl.py"文档形态拆除
   （provider_impl.py 降为内置默认实现，用户面唯一边 = 宿主绑定 + set_provider），不并存。

---

## 五、当前进度与交接状态

- **近期主线（R0-R2）已全部完成并合入 `unsafe-vibe-dev`**：
  - R0 审计：全量 pytest 实跑零回归（基线以实跑为准）；内核仅 `llm_callback.call(request)`；
    `_prompt_assembly.py` 收敛为仅 retry 消息结构；`probe_model()` → `probe()` 单入口；
    无 `ILLMProvider` 残留 / 无旧装配 API / vtable 无漂移。
  - R1 拆分（`exp/provider-decouple-r1` → 零风险直接合并）：`provider_impl.py`
    （`RecommendedProvider`，纯 provider，kernel-free，可整文件替换）+ `core.py` 宿主
    （`AIPlugin(RecommendedProvider, IbStatefulPlugin)`，仅 IBCI 胶水）；MOCK 哨兵下沉
    `core.base.llm_protocol.llm_call`（单一权威源）；kernel-free `config_normalize.py`
    （默认常量 + `to_llm_config` 归一）；provider 失败契约统一 RuntimeError。
  - R2 文档：`docs/howto/modify_llm_provider.md`（改内核 provider 文件指南）；
    `docs/architecture/01_principles.md` §3.7 两段式定位（近期=改内核文件；
    远期=原生绑定）。
  - 验证：全量 pytest 3027 passed / 1 skipped（分支与合并后均实跑）；独立复核放行
    （probe 启发式 P1 修复 + 字节级二次验证）。
- **远期主线（F 段）已启动**：
  - **F0 已完成（`exp/native-binding-f0` → 零风险直接合并）**：Native Binding 地基验证——
    实证 box 裸 Python 模块 + 手动 vtable 绑定成员 + receive 调用可行（内核 API）；
    设计底稿 `docs/architecture/01_native_host_binding.md`（现状实证 + 设计框架 +
    关键落点 + F2 机制细节）；裁决点 1（宿主绑定语法形态）定稿 `import python "pkg" as lib`；
    裁决点 2/3 定方向（一等类型 EXTERNAL_MODULE / 显式声明式绑定）。临时设计文档
    `tasks_docs/_f0_native_binding.md` 保留至 F1 复用（含 F1 设计问题清单）。
  - **F1 已完成（`exp/native-binding-f1` → 零风险直接合并）**：宿主导入一等语法
    `import python "pkg" as lib: bind ...` + 用户类持有 native。全链路实现（AST/
    lexer/parser/依赖扫描/scheduler/语义/运行时/VM）；显式声明式绑定（非自动穿透，
    契约外成员 fail-fast）+ 编译期类型检查（bind 签名约束调用实参）+ 用户 IBCI 类
    `any` 字段持 native；共享函数提取（annotation_to_typeref / create_proxy）消除
    双真相。验证：e2e（sqrt=4.0/pi/pow/用户类=5.0/磁盘文件 rehydrate/跨模块），
    负样本 3 项，全量 pytest 3039 passed / 1 skipped。测试
    `tests/runtime/test_host_binding.py`；语法文档 `docs/syntax/11_modules.md` §11.10；
    设计底稿 §五。
  - **F2 已完成（`exp/native-binding-f2` → 零风险直接合并，65414738）**：协议/impl
    扩展到宿主类型——bind class 宿主类型绑定（`bind class Name: ...` 块形式 +
    `bind class Name -> any` 简写）+ impl 目标限制解除（EXTERNAL_MODULE 放行、
    KERNEL_NATIVE 仍拒绝）。编译期：scheduler `_inject_host_class` 注册一等类型
    EXTERNAL_MODULE CLASS + 合成 owned_scope；运行期：HostClassBinding(IbClass)
    恒走 instantiate + per-instance vtable（bind 方法）+ whitelist（bind 属性），
    impl 方法经 IbNativeObject 类方法回落 → IbBoundMethod；协议满足纯编译期静态
    spec 判定（bind 声明 + impl 补充并集）。独立复核（b228d4fd）整改闭环：
    B1（回落加 HostClassBinding 门控，实证误诊但保留机制隔离）/ M1（bind vs impl
    同名编译期 SEM_REDEFINITION）/ M2（unbox_for_native_call 单一权威）/
    L1-L3 已修 / L4 已修 / L5 记录。验证：全量 pytest 3053 passed / 1 skipped，
    零回归。临时设计 `tasks_docs/_f2_native_binding.md`（并入本路线图后删除）。
  - **F3 已完成（`exp/plugin-refactor-f3`）**：插件体系重构——废弃 Python 侧 `_spec.py`
    磁盘发现/加载通道，用户侧扩展唯一边 = 宿主绑定 `bind`，不保留双通道。F3-1：10 个
    `_spec.py` 删除，内置 11 模块（内核原生 5 + 工具 5 + file）TypeDef 字面量集中
    `core/runtime/bootstrap/builtin_modules.py` 构造期一次注册全部含实现（结构等价
    探针 + 契约测试 + loader 环 2 去双绑定）。F3-2：磁盘插件发现/加载双通道彻底铲除
    （discovery/auto_discovery/loader 环 2/插件搜索路径配置面 plugin_paths/global_plugin/
    嗅探/继承透传/main.py --plugin/ibci_sdk/__ibcext_axiom__ 死协议/spec_builder 死代码/
    幽灵码 KDIAG_POLICY_MODULE_NO_EXPORT）；Engine 签名简化 `IBCIEngine(root_dir=...)`。
    F3-3：examples/trials/docs 全迁移（删 plugins_demo/isolation plugins/T01 plugins；
    D2-21 改写为宿主绑定演示；write_user_plugin → extend_with_host_binding；subsystems/04
    重写；20+ docs 更新到 F3 事实）。F3-4：残留扫描 `_spec.py`/`__ibcext_vtable__`/
    discovery 引用清零（功能面零残留）。三阶段全量 pytest 零回归（最终 2946 passed /
    1 skipped）。决策定稿已沉入
    `docs/architecture/01_native_host_binding.md` §3.4 与 07_kernel_native_modules.md。
    裁决点 3（旧 _spec.py 用户插件归宿）
    落定 = 删除（不保留双通道、降级为新绑定编译目标）。达分支合并"零风险直接合并
    unsafe-vibe-dev"标准（全量 pytest 零回归 + F3-1 结构探针 + F3-2/F3-3 独立 subagent
    复核 + F3-4 残留扫描，无对外契约/架构级风险）——合并仍需用户授权。
  - **F4 已完成（`exp/provider-bind-f4`）**：Provider 自定义经宿主绑定统一。用户经
    `import python "<mod>" as lib: bind provider` 声明实现 `LLMProvider` 契约的 provider，
    `ai.set_provider(lib.provider)` 注册为激活 `llm_provider`（HIGH 优先级覆盖内置默认
    `RecommendedProvider`）；内核 LLM 执行器经 capability_registry 惰性 get 使切批生效，
    不改内核架构。R 期"改 provider_impl.py"临时文档形态拆除（provider_impl.py 降为内置
    默认实现，不手动改）；`docs/howto/modify_llm_provider.md` 改写为宿主绑定通道。
    **用户 2026-08-18 授权**推翻 R0-R2"不新增语言级注册 API"裁定（WORKLOG 长期裁定）。
    验证：全量 pytest 2956 passed / 1 skipped 零回归 + 自定义 provider e2e
    `tests/e2e/test_provider_host_binding.py`（内核实际调用用户 provider）+ 契约
    fail-fast + 默认 provider 保持。
- **近期未开放用户自定义语言级 API**：`register_provider`/`set_config_source` 等 WIP
  已回退；F4 已由用户授权新增 `ai.set_provider`（bind-based provider 注册出口），
  统一 provider 自定义。设计要点保留于 git 历史 + 本路线图。
- **触发此两段式规划**：用户裁定近期聚焦 provider 分离，F4 起原生绑定统一 provider
  自定义（成熟现代方案）。
- **交接**：远期 F0-F4 全部完成（宿主导入 + 宿主类型绑定 + 插件体系重构 + provider
  自定义统一），F5 待启动。下一步候选见 `tasks_docs/NEXT_STEPS.md`。

---

## 六、工作纪律（延续 AGENTS.md）

- 禁 push；只本地 commit。破坏性重构独立分支实验、复核后合并 `unsafe-vibe-dev`，永不碰 `main`。
- 工作模式定论；质量红线（禁兜底/双通道/历史包袱）；原则优先于行为维持。
- 每阶段全量 pytest 零回归 + 提交 + 同步 NEXT_STEPS/WORKLOG。
- 分析/实现均须加载匹配 skill（code-workflow / code-quality / design-philosophy / self-grill 等）。

# F4 — Provider 自定义经宿主绑定统一（设计底稿，临时文档，用后即删）

> 临时任务控制文档（governance：F4 完成后删除，决策沉入 docs/）。主线：
> ROADMAP_NATIVE_BINDING.md §三 F4 + 裁决点 4。分支 `exp/provider-bind-f4`
> （自 unsafe-vibe-dev @3261200e，即 F3 合并后）。
> **用户 2026-08-18 授权**：新增 bind-based provider 注册出口/API、统一 F4，
> 推翻 R0-R2 "不新增语言级注册 API / 不提前实现用户入口"裁定。

## 〇、F4 目标与验证门

- **目标**：用 F1-F3 宿主绑定 `import python "..." as lib: bind ...` 统一 LLM
  provider 自定义——用户自写 provider 类（Python，实现 `LLMProvider` 契约），经
  宿主绑定接入 IBCI 并注册为激活的 `llm_provider`，替代 R 期"改
  `provider_impl.py`"的临时分发形态。统一后拆除 R 期临时形态，不留双通道。
- **验证门**：全量 pytest 零回归；自定义 provider 经宿主绑定被内核实际调用
  （非 stub）；`provider_impl.py` 不再作为"用户自定义入口"被文档指导（降为内置
  默认实现）；T09 真实 LLM 复跑（若环境可行）。

## 一、现状（F4-0 实证，已完成）

### 1.1 provider 注入链路
- `ai` 模块宿主 `AIPlugin(RecommendedProvider, IbStatefulPlugin)`（`ibci_modules/ibci_ai/core.py`）。
- `AIPlugin.setup(capabilities)` → `capabilities.expose(CAP_LLM_PROVIDER, self)`
  ——把 **模块宿主自身** 注册为 `llm_provider` 能力（engine STAGE_4 加载期）。
- 内核 LLM 执行器 `LLMExecutorImpl.llm_callback`（`core/runtime/interpreter/llm_executor/_core.py`）
  属性**每次调用时**从 `service_context.capability_registry.get(CAP_LLM_PROVIDER)` 读
  provider，再 `provider.call(request)` / `provider.stream(request)`。
- `capability_registry`（`core/runtime/capability_registry.py`）支持 `register` /
  `replace` / `get`；`get` 懒解析、`_primary_cache` 每次 `_rebuild_cache` 重建。
  → **运行期更换 provider 能力，下次 LLM 调用即生效，无需重启引擎**（llm_callback
  每次读 registry）。

### 1.2 R 期临时分发形态
- 用户自定义 LLM 底层 = **修改/替换** `ibci_modules/ibci_ai/provider_impl.py`
  （`RecommendedProvider`，kernel-free 单一可替换单元）；操作指南
  `docs/howto/modify_llm_provider.md`。
- 这是"源码直接分发"下的临时形态：用户在自己的代码树里改一个 Python 文件。

### 1.3 宿主绑定能提供什么
- F1-F3 的 `import python "pkg" as lib: bind 成员` 把 Python 模块成员绑定为 IBCI
  一等符号（成员表 = bind 声明）。
- **不自动touch能力注册**——bound 对象只是 IBCI 可调用表面，不经 `capability_registry`。

## 二、F4 设计（本 session 定稿方向）

### 2.1 核心机制：`ai.set_provider(<bound lib>)` 运行时注册
- 用户在项目里写一个自定义 provider 类（Python，实现 `LLMProvider` 契约：
  `call` / `stream` / `get_retry` / `is_auto_intent_injection_enabled` /
  `get_current_call_info`，可选 `probe`），放在项目内 Python 模块（如
  `my_provider.py`）。
- 用户在 IBCI 脚本里：
  ```
  import python "my_provider" as lib:
      bind call(request) -> any
      bind stream(request) -> any
      bind get_retry() -> int
      bind is_auto_intent_injection_enabled() -> bool
      bind get_current_call_info() -> dict
  import ai
  ai.set_provider(lib)
  ```
- `ai.set_provider(lib)` 在 `ai` 模块宿主内实现：校验 `lib`（宿主绑定模块）具契约
  面，然后 `capability_registry.replace(CAP_LLM_PROVIDER, <lib 的原生对象>, plugin_id=..., force=True)`。
- 内核 LLM 执行器下次 `llm_callback` 读到用户的 provider → 调用用户实现。

### 2.2 关键设计点
- **`ai.set_provider` 的参数形态**：接受宿主绑定 lib（IBCI 侧一等对象）。宿主绑定
  成员（`call`/`stream` 等）是 `IbNativeFunction`/proxy；注册进能力表时应解出**原生
  Python 可调用**（bound module 的原生实现对象），或让能力表直接持有 bound 对象
  （bound 对象本身 `receive` 可调）。需 spike 验证哪种形态最简单不 tricky。
- **契约校验**：`set_provider` 时校验宿主lib 具备 LLMProvider 契约面（`call`/`stream`/
  `get_retry`/`is_auto_intent_injection_enabled`/`get_current_call_info`），缺失即
  fail-fast（不静默降级）。
- **与 `ai` KERNEL_NATIVE 关系**：不替换 `ai` 模块，只替换其暴露的 provider 能力。
  `ai` 仍是内核受保护模块；`provider_impl.RecommendedProvider` 仍作为**内置默认**
  provider（无 `set_provider` 时用默认）。
- **拆除 R 期临时形态**：`ai.setup()` 不再无条件 `expose(self)` 作为唯一 provider；
  改为：无用户 `set_provider` 时仍用默认 `RecommendedProvider`，`set_provider`
  后切换到用户 provider。`docs/howto/modify_llm_provider.md` 从"改 provider_impl.py"
  改写为"经宿主绑定自定义 provider"（`provider_impl.py` 仅作内置默认实现说明）。
- **MOCK 兼容**：`set_mock_mode`/MOCK 哨兵路径需在用户 provider 接入后仍成立（或
  明确：MOCK 测试模式独立于 provider 选择，由 ai 模块在 provider 外层处理）。

### 2.3 待 spike 验证的点
1. 宿主绑定 lib → 能力表替换的**对象形态**（bound 模块原生对象 vs proxy）。
2. `set_provider` 后内核 LLM 调用确实走用户 provider（用 fake LLM 响应验证）。
3. 现有 llm 测试（MOCK/真实 provider）零回归。

## 三、实施顺序

1. **F4-SPIKE**：最小 spike——写一个 fake `LLMProvider` 类，经 `import python` 绑定 +
   `ai.set_provider` 注册，验证内核调用走用户 provider。验证对象形态与契约校验。
2. **F4-1 实现**：`ai.set_provider` API（宿主 + IBCL 契约校验 + 能力替换）；spike
   结论落地。
3. **F4-2 拆除**：`ai.setup` 调整（默认 provider 仍可用，`set_provider` 覆盖）；
   `modify_llm_provider.md` 改写；`provider_impl.py` 定位降为"内置默认实现"。
4. **F4-3 测试/文档**：e2e 测试（自定义 provider host-binding）；全量 pytest 零回归；
   思考抑制/ConfigSourceAdapter 接口位按新模型收敛；T09（环境可行则跑）。
5. **收尾**：决策沉 docs/architecture/01_principles.md §3.7 + howto；同步
   NEXT_STEPS/WORKLOG/ROADMAP；删本临时文档。

## 四、关键裁决（记录）

- **F4-0 设计取向**：provider 运行期替换已由 capability_registry 惰性 get 天然支持
  （llm_callback 每次读 registry）——F4 不需改内核 LLM 执行器架构，只需在 ai 宿主提供
  `set_provider` 注册出口。这是最小、机制一致、非胶水的路径。
- **用户授权推翻 "不新增语言级注册 API"**（WORKLOG 长期裁定）——本次 F4 新增
  `ai.set_provider` 语言级 API。
- **SPIKE 发现（重要）**：
  1. `CapabilityRegistry.replace()` **不能**同等优先级换 primary：`replace` 只移除
     `plugin_id` 相同的 provider，原 `ai`（priority 50）保留且与用户 provider（50）
     等优先级，`_rebuild_cache` 仍选原 `ai` → 替换无效。
  2. **正确机制 = 以 `HIGH` 优先级 `register()` 用户 provider** → `get()` 返回用户
     provider（primary）。无用户 provider 时默认 `ai` provider（NORMAL）仍为 primary。
     这是 registry 设计的优先级主选机制，单一 primary、非双通道。验证通过。
  3. provider 注册发生在 `ai.setup()`（engine STAGE_4 loader 环 1），非构造期——
     用户 `set_provider` 须在引擎运行期（import ai 后）调用，能力表懒读使其生效。


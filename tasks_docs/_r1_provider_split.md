# R1 — Provider 层接口位清理：core.py 拆分设计（临时任务文档）

> 定位：R1 拆分方案设计决策记录（code-workflow Phase 2 产物）。实现落地、复核放行后
> 本文件删除（git 承载）。权威路线图：`tasks_docs/ROADMAP_NATIVE_BINDING.md` §三.R1。

## 一、目标与边界

- 目标：把 `ibci_modules/ibci_ai/core.py`（802 行）拆分为「纯 provider 逻辑」与「IBCI
  模块胶水」两文件；纯 provider 文件 **kernel-free**（零 `core.kernel`/`core.runtime`/
  `core.extension` 导入），成为用户"改这一个文件"自定 LLM 底层的干净可替换单元。
- 边界：**零行为变化**（推荐 provider 的调用/配置/探测/MOCK 语义原样保留）；不新增语言级
  注册 API；`LLMProvider` 契约与 `_spec.py` vtable 完全不变；`__init__.py` 不变。
- 验证门：全量 pytest 零回归 + provider_impl 无 kernel import（grep 实证）+ 无半接通/
  无残留（`ILLMProvider`、旧装配 API、双通道）。

## 二、决策记录

### D1 文件布局：宿主保留 `core.py`，新增 `provider_impl.py`（偏离路线图 "module.py" 命名）

- 路线图 §三.R1 设想 `module.py`（胶水宿主）+ `provider_impl.py`。**决策：宿主仍用
  `core.py`**。
- 理由（design-philosophy 设计语言统一）：全仓 `ibci_modules/<name>/` 10/10 模块的
  实现宿主文件一律是 `core.py`（`__init__.py` 从 `.core` 导入；`ibci_sdk/check.py`
  报错文案亦指向 core.py）。保留 `core.py` = 宿主名与代码库约定一致；`__init__.py`、
  `_spec.py`、全部测试的导入锚点零漂移。`provider_impl.py` 名称按路线图原样采用
  （R2 文档面向用户指向这个文件）。
- 结论：`ibci_modules/ibci_ai/core.py` = `AIPlugin`（宿主 + 胶水）；`provider_impl.py`
  = `RecommendedProvider`（纯 provider，kernel-free）。

### D2 宿主关系：继承（`class AIPlugin(RecommendedProvider, IbStatefulPlugin)`），非组合委托

- 路线图 R1 表述"持胶水、委托 provider_impl"（暗示组合）。**决策：继承**。
- **基类顺序是 load-bearing**：`RecommendedProvider` 在前（`AIPlugin(RecommendedProvider,
  IbStatefulPlugin)`）才能让 `super().save_plugin_state()` 解析到 provider 实现而非
  ABC 占位（ACMeta 只从被创建类自身命名空间扣除抽象方法，故 AIPlugin 须在自身
  `__dict__` 显式定义 `save_plugin_state` / `restore_plugin_state` 委托）。
- 理由（证据驱动）：
  1. 测试体系把 `AIPlugin` 当作 provider 本体：`test_probe_model.py` 白盒注入/断言
     `plugin._client` / `plugin._model_capabilities`（探测只读消费不变式）；`test_mock_directives.py`
     25+ 处直接调 `plugin._handle_mock_response(...)`；`test_api_config.py` 调
     `plugin._is_test_mode()` / `_model_registry` / `_config`。继承 → 全部零改动、
     行为身份（"AIPlugin 即 provider"）保持；组合 → 上述测试须大规模重写为
     `plugin._provider.*`，削弱既有语义。
  2. 破坏性重构授权覆盖文件重组，但"行为保持 + 测试面零漂移"是更稳妥的零风险路径，
     与"零风险直接合并"细则匹配。
  3. AIPlugin 的胶水方法（`load_config`/`load_project_config`/`run_batch`/`stream_call`/
     `stream_channel`/意图方法/`setup`）全部只调用继承自 provider 的公开/内部方法，
     无需委托样板，无胶水判断逻辑。
- `RecommendedProvider(LLMProvider)`：纯 provider 逻辑 + 状态（config 字典、命名模型
  注册表/客户端缓存、返回类型提示表、MOCK 引擎、模型能力缓存、探针/告警去重标志、
  `_last_call_info`）。`AIPlugin.__init__` = `super().__init__()` + `self._capabilities = None`。

### D3 MOCK 哨兵下沉 base：`MOCK_REPAIR_SENTINEL` / `MOCK_AMBIGUOUS_SENTINEL` 移至
`core.base.llm_protocol.llm_call`

- 现状：定义于 `core/runtime/shared/llm_result.py`（顶层，无 `__all__`）；消费者仅
  `core/runtime/interpreter/llm_executor/_llm_function.py`、`_behavior.py`、
  `ibci_modules/ibci_ai/mock_scenario.py`、`tests/plugins/test_mock_directives.py`(sync 检查)。
- 决策：定义**下移**到 `core.base.llm_protocol.llm_call`（与 `LLMCallResult` 同层，result
  数据契约的哨兵）；上述消费者改从 base 导入；`llm_result.py` 删除原定义（不留再导出
  ——真删除，遵工作模式定论）。理由：`mock_scenario.py` 被 provider 导入，provider
  kernel-free 要求哨兵不在 runtime 层；其余 kernel 消费者本来就在依赖 base 的合法方向。
- `core/kernel/axioms/primitives/enum.py` 的 `_MOCK_AMBIGUOUS_SENTINEL_UPPER` 镜像常量
  （层约束，axioms 不导入 runtime/base）与 `test_mock_directives` 的 sync 断言保持。
- 方向检查：core/base 只出不进（`01_principles.md` §四）；base 定义、runtime 导入合法。

### D4 配置归一基元下沉：新建 kernel-free `ibci_modules/ibci_ai/config_normalize.py`

- 现状：`_DEFAULT_TIMEOUT/_DEFAULT_RETRY/_DEFAULT_AUTO_INTENT` 定义于
  `config_loader.py`（该模块因 `ApiConfig.validate` 抛 `InterpreterError`（CFG_ 诊断码，
  公开测试契约）而 kernel-touching）；`ProjectApiConfigAdapter.to_llm_config` 静态方法
  在 `config_source_adapter.py`（transitively 经 config_loader 拉入 kernel）。
- 决策：新建 `config_normalize.py`（仅 import `core.base.llm_protocol.config`，kernel-free）：
  迁入三默认常量 + `to_llm_config(validated: dict) -> LLMConnectionConfig`（原样迁移）。
  `config_loader.py` 删除本地定义、改为 `from .config_normalize import ...`（内部引用随之）；
  `config_source_adapter.py` 的 `load()` 改调 `config_normalize.to_llm_config`，删除其静态
  方法（单一权威源）。
- 理由：provider 需要默认值（`__init__`/`register_model`）与 dict 归一
  （用户面 `apply_config(dict)`，vtable 契约，测试直调）而必须 kernel-free；经旧 adapter
  transitively 拉 `core.kernel.issue` 违反净边界。

### D5 provider 错误类型统一：`_init_client` 的 `InterpreterError` → `RuntimeError`

- 现状：`_init_client` 配置缺失分支抛 `InterpreterError`（core.kernel.issue）——provider
  内唯一的 kernel 错误引用。消息文本："LLM 配置缺失：..."。
- 决策：改抛 `RuntimeError`（文本不变）。理由：provider 失败契约本就约定 RuntimeError
  （文件注释"provider 层失败契约…RuntimeError"，`_PROVIDER_ERRORS` 含 RuntimeError）；
  唯一测试消费者 `test_set_mock_mode_switch.test_exit_mock_without_config_fails_fast`
  用 `pytest.raises(Exception, match="LLM 配置缺失|base_url")` broad-match，兼容。
- 记录为行为差异：异常类 InterpreterError→RuntimeError（仅此一处、仅"未配置即初始化"
  路径；各 error_code 诊断不变——那些是 config_loader 侧）。

### D6 `get_current_call_info` 保留在 AIPlugin（kernel 委托 + provider 本地回退）

- 现实现：优先经 `self._capabilities.kernel_registry.get_llm_executor()` 读主线程单写槽
  （e2e `test_ai_batch` 依赖批内立即可见），回退 provider 本地 `_last_call_info`。
- 决策：方法留在 AIPlugin（需要 capabilities）；`_record_call_info` 与 `_last_call_info`
  留在 RecommendedProvider（`__init__` 初始化 `_last_call_info = {}`），AIPlugin 回退分支
  经 `super().get_current_call_info()` 读取 provider 本地实现（等价于原
  `dict(self._last_call_info) if getattr(self, "_last_call_info", None) else {}` 兜底语义）。
  RecommendedProvider 自身实现协议方法 `get_current_call_info`（返回本地槽），宿主覆盖
  之：优先内核执行器单写槽，回退 `super()`。

### D7 接口位收敛口径（R0 关注点①/②，不新增语言级 API）

- `thinking_mode`：`LLMCallRequest.thinking_mode` 保持"契约字段存在、内核不填（auto）、
  推荐 provider 不读请求字段"的**远期接口位**状态；推荐 provider 默认行为不变：
  `ModelSpec.thinking_mode`（api_config `reasoning` 字段）驱动 `is_reasoning` 能力声明；
  payload 的 `enable_thinking=False` 抑制为推荐 LM Studio + Qwen 适配（思考禁用是
  provider 侧能力，PT-DECIDE-2 已定案；强制思考模型覆盖缺口已登记 KNOWN_LIMITS/
  PT-DECIDE-2，不在 R1 行为面内）。R2 文档写明注意事项。
- `probe()`：`probe_model()` → `probe()` 单入口保持（R0 实证已全绿）。
- `ConfigSourceAdapter`：`load_project_config` 实例化 `ProjectApiConfigAdapter()` 是**推荐
  默认适配器**的显式使用（替换路径 = 整文件替换 `config_source_adapter.py` 保持类名），
  属"推荐实现干净正确"；不新增 `set_config_source` 注册入口（WIP 已回退，为远期 F4 留位）。

## 三、改动清单（实现顺序）

| # | 文件 | 动作 |
|---|------|------|
| 1 | `core/base/llm_protocol/llm_call.py` | 新增两 MOCK 哨兵常量（D3） |
| 2 | `core/runtime/shared/llm_result.py` | 删除哨兵定义（D3） |
| 3 | `core/runtime/interpreter/llm_executor/_llm_function.py`、`_behavior.py` | 哨兵改从 base 导入 |
| 4 | `ibci_modules/ibci_ai/mock_scenario.py` | 哨兵改从 base 导入 |
| 5 | `tests/plugins/test_mock_directives.py` | sync 断言处哨兵改从 base 导入 |
| 6 | `ibci_modules/ibci_ai/config_normalize.py` | 新建：默认常量 + to_llm_config（D4） |
| 7 | `ibci_modules/ibci_ai/config_loader.py` | 删除本地默认常量定义，改 import（D4） |
| 8 | `ibci_modules/ibci_ai/config_source_adapter.py` | 删除静态 to_llm_config，load() 改调 config_normalize（D4） |
| 9 | `ibci_modules/ibci_ai/provider_impl.py` | 新建：`RecommendedProvider(LLMProvider)`（D2/D5/D6） |
| 10 | `ibci_modules/ibci_ai/core.py` | 瘦身为 `AIPlugin(RecommendedProvider, IbStatefulPlugin)` 宿主（D1/D2/D6） |
| 11 | `tests/runtime/test_probe_model.py` | `MOCK_CLIENT_SENTINEL` 导入改 provider_impl（1 处） |
| 12 | 执行 | 全量 pytest 零回归 + grep 实证 + 复核 |

## 四、provider_impl.py 净边界承诺（实现后 grep 验证）

- 禁止出现：`core.kernel` / `core.runtime` / `core.extension` / `ibcext` / `InterpreterError`
  导入；只允许 `core.base.llm_protocol.*` + `ibci_modules.ibci_ai` 内部 kernel-free 模块
  （`mock_scenario` / `config_normalize`）+ stdlib + openai（可选）。

## 五、验证门与合入

- 全量 pytest 零回归（基线 3027 passed / 1 skipped / 实跑为准）。
- grep 实证 provider_impl 无 kernel import；无残留 `ILLMProvider`；vtable 与 AIPlugin
  方法集一致。
- 独立分支 `exp/provider-decouple-r1` 实现；复核（code-review P4 精神）后按"零风险
  直接合并"细则合入 `unsafe-vibe-dev`（行为零变化 + 全量零回归 + 边界清晰）。
- 完成登记：ROADMAP §三.R1→done、NEXT_STEPS/WORKLOG 同步、本临时文档删除。
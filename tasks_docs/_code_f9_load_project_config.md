# _code_f9_load_project_config — F9 显式配置落地实现记录

> 2026-08-12 用户拍板：命名 `ai.load_project_config`，本轮立即实施。
> 设计权威：`_code_ai_autoset.md`。本文档记录实施决策与变化前后，Phase 5 汇报后清理。

## 一、变更目标

把 api_config.json 加载从"引擎启动自动加载（副作用绑定 setup）"改为"显式
`ai.load_project_config()` 调用"。引擎启动不再自动加载。

## 二、设计决策（self-grill 质询收敛）

1. **ec/project_root fail-fast 迁移**：`setup()` 去掉自动加载段后仅剩
   `capabilities.expose`（注册 provider）。原 setup 内的 ec/project_root
   注入检查（engine 未正确装配即 fail-fast）**迁移到 `load_project_config()`**
   显式调用点——失败时点从"启动（用户不可见）"移到"用户可见调用点"，契约保留。
2. **`load_project_config()` 语义**：加载 `project_root/api_config.json`；
   - 不存在 → **no-op 合法态**（用户无配置，静默跳过，不抛错）；
   - 存在 → `ApiConfig.load` + `apply_config`（校验失败带 CFG_ 诊断 fail-fast）；
   - **幂等**：覆盖式应用，无累积副作用；
   - 路径经 `PathValidator.canonicalize_for_security` 规范化（符号链接解析）。
3. **`load_config(path)` 保留**：显式指定路径入口，语义不变（相对 project_root
   解析）。docstring 中"与引擎自动加载同锚点"表述改为"与 load_project_config 同锚点"。
4. **`_spec.py` vtable 注册 `load_project_config`**（零参数，return void，带 description）。
5. **历史试用档案不改**（决策记录）：`_LLM_TRIAL_*` 用例是已完成的历史归档
   （日志/REGISTER 记录于"自动加载"时代），改动会污染历史一致性。若未来重跑
   需在真实 LLM 用例入口加显式调用，交接中记录。examples/ 为交付物必须改。
6. **examples 01/02/03**（用 `has_api_key` 判断的真实 LLM 兼容路径）：判断前加
   `ai.load_project_config()`。无配置时 no-op → has_api_key False → set_mock_mode，
   行为不变；有配置时加载 → has_api_key True。04/05/06 纯 mock 无需改。

## 三、变更清单（实施中勾选）

- [ ] `core.py`：`setup()` 去自动加载段；新增 `load_project_config()`；`load_config` docstring 同步
- [ ] `_spec.py`：vtable 注册 `load_project_config`
- [ ] `tests/contracts/test_api_config.py`：
  - `TestEngineAutoLoad.test_engine_auto_loads_api_config` → 改显式调用语义
  - `TestAIPluginSetupContract` → 改为 load_project_config 契约（no-op/加载/符号链接/fail-fast）
  - 新增：语言级显式 `ai.load_project_config()` 可达性 + 幂等测试
- [ ] `examples/01_getting_started/01/02/03`：判断前加 `ai.load_project_config()`
- [ ] `README.md`（157/187/201 自动加载表述改显式）
- [ ] `docs/guide/01_setup.md`（14/22/110 自动加载表述改显式 + 入口调用示例）
- [ ] `docs/syntax/11_modules.md` §11.3（63-69 自动加载表述改显式 + load_project_config 入口）
- [ ] `config_loader.py` 顶部 docstring（"引擎自动加载"→ 显式入口）
- [ ] `execution_context.py:20` 注释（"AIPlugin 自动加载 api_config.json"→ load_project_config）
- [ ] `catalog.py` CFG_CONFIG_NOT_FOUND title/fix（含 load_project_config）
- [ ] `docs/syntax/15_diagnostics.md` CFG_ 段（含 load_project_config）
- [ ] 全量 pytest 零回归 + 独立复核（general agent）+ commit + 落档

## 四、验证

- 全量 `python -m pytest tests/` 零回归。
- 契约测试：加载成功 / no-op / 幂等 / ec 缺失 fail-fast / project_root 缺失
  fail-fast / 符号链接规范化 / 语言级显式调用可达。

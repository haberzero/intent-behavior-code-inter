# _code_api_config - PT-FEAT-13 C1-C3 配置机制完备化设计与实现记录

> 任务来源:`tasks_docs/_API_CONFIG_DESIGN.md`(设计权威)。本文件为 C1-C3 落地的
> 临时任务文档(code-workflow Phase 2 设计 + Phase 5 汇报后删除)。
> 主任务:真实 LLM e2e 前置--使 api_config.json 成为原生一等配置机制。

## 一、现状(代码核实)

- `api_config.json` **非运行时原生加载**:每个示例 `.ibci` 手动 `file.exists/json.parse/ai.set_config`(01_hello_world.ibci:22-36)。README 写成"机制"但实为脚本约定。
- `AIPlugin`(`ibci_modules/ibci_ai/core.py`):`_config` dict(url/key/model/retry/timeout/auto_intent_injection);`set_config(url,key,model,**kwargs)` 3 位置参数;`register_model(name,url,key,model,**kwargs)` 命名模型;`_is_test_config` 字符串嗅探(TESTONLY/MOCK_KEY/env)。
- `IbciConfig`(`core/kernel/config.py`):加载 `ibci.json`(项目配置,插件路径),在 `engine.resolve_plugin_search_paths` 调用。**与 api_config.json 分离**(后者含敏感信息)。
- `IExecutionContext` / `ExecutionContextImpl`:持有 `_entry_file`/`_entry_dir`(经 `get_entry_path()`/`get_entry_dir()` 暴露),**无 project_root**。
- 诊断码体系(`core/base/diagnostics/codes.py`):LEX/PAR/SEM/DEP/INT/RUN/KDIAG 域,无 CFG 域。

## 二、C1-C3 范围(P0,真实 LLM e2e 前置)

| 项 | 内容 | 本批次 |
|----|------|--------|
| C1 | 原生配置加载(`ai.load_config(path)` 显式 API) | ✅ |
| C2 | `set_config` 结构化(新增 `ai.apply_config(dict)`) | ✅ |
| C3 | 配置校验与诊断(fail-fast + CFG_ 诊断码) | ✅ |
| 引擎自动加载 | setup 时自动加载 project_root/api_config.json | ⏸ 延后(见决策 D-04) |

## 三、设计决策

### D-01 API 设计:三个入口,职责分离
- `ai.set_config(url, key, model, **kwargs)`:**保留不变**(兼容现有契约,测试/示例/宿主直调路径零破坏)。低级位置参数配置。
- `ai.apply_config(config: dict)`:**新增**。结构化配置应用(程序化入口)。从 dict 提取 default_model + 命名模型,委托 set_config + register_model。
- `ai.load_config(path: str)`:**新增**。文件入口。读取 api_config.json -> 校验 -> apply_config。

三者关系:`load_config = read+validate+apply_config`;`apply_config = set_config + register_model`;`set_config` 是底层位置参数配置。

**为什么不改 set_config 签名**(D-01 决策依据):
- set_config 现有 3 位置参数被测试(20+ 处)、示例、宿主路径广泛使用,改签名破坏面大。
- IBCI 语言层方法签名固定(vtable params 列表),不支持重载/union;改 set_config 第一参数为 any 接受 str|dict 是类型判断分派(违工作模式定论第 4 条"禁止过程式硬编码分发")。
- apply_config 作为结构化变体,职责清晰,不破坏契约。符合"新设计就是真设计,旧代码真合并或真删除"--这里是新增而非兼容层。

### D-02 schema(C1-C3 简化版,兼容旧式)
```json
{
  "default_model": { "base_url": "...", "api_key": "...", "model": "...", "timeout": 30.0, "reasoning": false },
  "models": {
    "local": { "base_url": "...", "api_key": "...", "model": "...", "timeout": 30.0, "reasoning": false }
  }
}
```
- `default_model`(必需):默认模型配置。支持两种形态:
  - **对象形态**(兼容旧式 example_api.json):`{base_url, api_key, model, ...}` 直接配置。
  - **字符串形态**(引用):`"local"` -> 引用 `models.local` 的配置。
- `models`(可选):命名模型字典,供 `@NAME~` 路由。每个值同 default_model 对象形态。
- 单个模型对象字段:
  - `base_url`(必需 str)、`api_key`(必需 str)、`model`(必需 str)
  - `timeout`(可选 number,默认 30.0)、`reasoning`(可选 bool,默认 false)
- **providers 分层暂不支持**(C6/C7 P1 完善):models 直接含连接信息。
- **env 引用暂不支持**(C4 P1):`{env:VAR}` 留后续。
- **mock 配置化暂不支持**(C5 P1):`_is_test_config` 字符串嗅探保留(兼容);新 schema 无 `mock` 字段。

### D-03 校验诊断(fail-fast + CFG_ 域)
- 新增诊断码域 `CFG_`(配置),注册到 `codes.py` + `catalog.py`:
  - `CFG_CONFIG_NOT_FOUND`:`load_config` 文件不存在。
  - `CFG_CONFIG_INVALID_JSON`:JSON 解析失败。
  - `CFG_CONFIG_NOT_OBJECT`:顶层不是 dict。
  - `CFG_CONFIG_MISSING_DEFAULT`:缺 default_model。
  - `CFG_CONFIG_MODEL_NOT_OBJECT`:模型条目不是 dict。
  - `CFG_CONFIG_MISSING_FIELD`:模型缺必要字段(base_url/api_key/model)。
  - `CFG_CONFIG_INVALID_FIELD_TYPE`:字段类型错误。
  - `CFG_CONFIG_UNKNOWN_MODEL_REF`:default_model 字符串引用的命名模型不存在。
- 校验失败 -> `raise InterpreterError(diagnostic_code=CFG_xxx, message=...)`(fail-fast,不静默回退 mock)。
- `load_config` 文件不存在也 fail-fast(显式调用即期望存在;示例脚本可用 `file.exists` 预判或 try-except)。

### D-04 引擎自动加载延后(决策)
- 设计文档 C1 提到"引擎启动自动加载"为目标,但本批次**延后**:
  - 自动加载需在 `AIPlugin.setup` 时获取 project_root,但 `IExecutionContext` / `ExecutionContextImpl` **不持有 project_root**(只有 entry_dir)。
  - 正确实现需扩展 `IExecutionContext` 协议加 project_root 属性 + `ExecutionContextImpl` 实现 + engine 构造期注入 + 测试 mock 更新--属架构改动,超出 C1-C3 最小可行范围。
  - 近似用 entry_dir 不严谨(显式 root_dir 场景 project_root != entry_dir)。
- **本批次用 `ai.load_config(path)` 显式 API 满足 C1**("ai 模块原生加载",非脚本手动 file/json.parse)。示例脚本 `ai.load_config("./api_config.json")` 一行替代手动解析。
- 引擎自动加载作为后续增强(待 execution_context 持有 project_root 的架构改动),不影响真实 LLM e2e(脚本显式 load_config 一行可接受)。

### D-05 实现位置
- 新建 `ibci_modules/ibci_ai/config_loader.py`:`ApiConfig` 类(load + 校验 + 解析为结构化数据)。
- `ibci_modules/ibci_ai/core.py`:`AIPlugin` 新增 `load_config(path)` + `apply_config(config)` 方法,委托 `ApiConfig`。
- `ibci_modules/ibci_ai/_spec.py`:vtable 新增 `load_config`/`apply_config` 声明。
- `core/base/diagnostics/codes.py` + `catalog.py`:新增 CFG_ 码 + 条目。
- `docs/syntax/11_ai_module.md`(如存在)+ README + example_api.json:同步更新。

## 四、实现步骤(Phase 3)

1. 新增 CFG_ 诊断码(codes.py + catalog.py)。
2. 新建 `config_loader.py`(`ApiConfig` 类:load + 校验 + 解析)。
3. `AIPlugin` 新增 `load_config` + `apply_config` 方法。
4. `_spec.py` vtable 新增声明。
5. 更新 example_api.json(新 schema 示例)+ 示例 .ibci(用 load_config)。
6. 文档同步(README + syntax/11 + KNOWN_LIMITS 如需)。

## 五、测试计划(Phase 4)

- 契约测试 `tests/contracts/test_api_config.py`:
  - load_config 成功(对象形态 default_model / 字符串引用形态)
  - 校验失败各诊断码(NOT_FOUND/INVALID_JSON/NOT_OBJECT/MISSING_DEFAULT/MODEL_NOT_OBJECT/MISSING_FIELD/INVALID_FIELD_TYPE/UNKNOWN_MODEL_REF)
  - apply_config 结构化应用(default_model + 命名模型注册)
  - catalog 条目完备(CFG_ 每码有条目)
- e2e 测试:`ai.load_config` 替代手动 file/json.parse,配置 TESTONLY mock 后跑行为表达式。
- 全量 pytest 零回归(基线 2137/1)。

## 六、工作模式定论对照

- ✅ 禁兼容层:apply_config 是新增真设计,非 set_config 兼容包装。
- ✅ 禁胶水:ApiConfig 独立加载器,不塞字符串拼接/魔法哨兵。
- ✅ 禁 tricky:校验显式逐字段,不靠凑巧相等。
- ✅ 禁过程式硬编码:配置应用经 set_config/register_model 既有协议,不写能力标志位分派。
- ✅ 质量优先:_is_test_config 字符串嗅探保留(C5 P1 另行处理),本批次不引入新魔法哨兵。

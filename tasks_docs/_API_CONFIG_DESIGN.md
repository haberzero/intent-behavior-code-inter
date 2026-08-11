# _API_CONFIG_DESIGN — `api_config.json` 配置机制分析与改进设计

> 用户 2026-08-11 提出：当前 api_config.json 内容结构/形式/机制都太简陋，结合 opencode.json 配置模式，
> 思考 json 文件改进 + 对应 IBCI 语法/功能层面改进，使配置机制功能完备可行。
> 本文件为设计权威；落地后按 doc-governance 收敛写入技术手册。

## 一、现状分析（代码核实）

### 1.1 关键发现：`api_config.json` 并非运行时原生加载
- **运行时（engine/ai 模块）不读取 api_config.json**。它只是**示例脚本级约定**：每个示例 `.ibci` 手动
  ```ibci
  if file.exists("./api_config.json"):
      dict config = json.parse(file.read("./api_config.json"))
      ai.set_config((str)config["default_model"]["base_url"], (str)config["default_model"]["api_key"], (str)config["default_model"]["model"])
  else:
      ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")   # 回退 mock
  ```
- README 把它写成"机制"，但实际是用户脚本责任；逻辑在每个示例重复、脆弱。
- 已核实：全仓 `api_config` 仅出现在 `core/kernel/config.py` docstring 与示例 `.ibci`、egg-info PKG-INFO（README 内容）。

### 1.2 现有 `ai` 配置能力
- `_config`：`url/key/model/retry(3)/timeout(30.0)/auto_intent_injection(True)`。
- `ai.set_config(url, key, model, **kwargs)`：3 位置参数 + kwargs（仅 auto_intent_injection）；timeout/retry 另有 setter。
- `ai.register_model(name, url, key, model, timeout)` + `@NAME~` 模型路由。
- Mock 判定：`_is_test_config`（url==MOCK 或 key==MOCK 或 env 变量）——**字符串嗅探**。
- 容器取值需强制转换（示例注释自认限制）：`(dict)config["default_model"]`。

### 1.3 现状缺陷
1. **非原生**：脚本约定，非一等机制，重复且脆弱。
2. **schema 极简**：仅 `default_model{base_url,api_key,model}`；无多模型/多 provider/每模型参数/环境变量引用/校验。
3. **无校验**：config 损坏/缺字段静默回退 mock，掩盖配置错误。
4. **mock 靠字符串嗅探**：url/key 相等判定，非显式声明（魔法哨兵，code-quality 红线）。
5. **不支持本地 LLM 场景**：无 reasoning（非思考模型）标志、无本地端点声明、无每模型 timeout/retry。

## 二、改进设计（参考 opencode.json 模式）

### 2.1 `api_config.json` 目标 schema（示例）
```json
{
  "$schema": "./api_config.schema.json",
  "defaults": { "timeout": 30.0, "retry": 3, "auto_intent_injection": true, "mock": false },
  "providers": {
    "dashscope": { "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "{env:DASHSCOPE_API_KEY}" },
    "ollama":    { "base_url": "http://localhost:11434/v1", "api_key": "{env:OLLAMA_KEY}" }
  },
  "models": {
    "default":  { "provider": "dashscope", "model": "qwen3-8b", "reasoning": false },
    "local":    { "provider": "ollama", "model": "qwen3-8b", "reasoning": false },
    "coder":    { "provider": "dashscope", "model": "qwen3-coder", "timeout": 60.0 }
  },
  "default_model": "default"
}
```
借用 opencode 的要点：
- **`$schema`**：IDE/校验（未来 schema 校验基础设施）。
- **分层结构**：providers（连接）/ models（命名模型，引用 provider + 模型名 + 每模型参数）/ defaults（全局默认）。
- **环境变量引用 `{env:VAR}`**：加载时解析，避免硬编码密钥。
- **`reasoning` 标志**：直接承载"非思考模型"约束（本地 LLM 试用红线）。
- **每模型参数**：timeout/retry/temperature/max_tokens。
- **`default_model` 选择** + `@NAME~` 路由直接用配置模型。

### 2.2 IBCI 语法/功能层面改进（对应）
| # | 改进 | 说明 | 优先级 |
|---|------|------|--------|
| C1 | **原生配置加载** | `ai` 模块/引擎原生加载 api_config.json（仿 ibci.json）；脚本不再手动 file/json.parse。提供 `ai.load_config(path)` 或引擎启动自动加载 | **P0** |
| C2 | **`ai.set_config` 结构化** | 接受 dict 配置（不只 3 位置参数）；兼容现有位置参数签名 | P0 |
| C3 | **配置校验与诊断** | 加载失败/字段错误 → 诊断（fail-fast 或 warn），非静默回退 mock；用现有诊断码体系 | P0 |
| C4 | **env 变量引用解析** | config 中 `{env:VAR}` 加载时解析 | P1 |
| C5 | **mock 配置化** | config 显式 `mock:true` 声明，替代 url/key 字符串嗅探（消魔法哨兵） | P1 |
| C6 | **命名模型配置路由** | `@NAME~` 直接用 config 声明模型；`default` 别名 | P1 |
| C7 | **reasoning/每模型参数** | 承载非思考模型约束 + timeout/retry/temperature | P1 |
| C8 | **容器类型系统改善（可选）** | 消除 `(dict)config[...]` 强制转换限制（示例注释自认），配置读取为典型用例 | P2 |

## 三、与真实 LLM e2e 阶段的关系
- 本地 LLM 试用（`_REAL_LLM_E2E_PLAN.md`）需要 C1/C3/C4/C5/C7 才能"干净地"配置本地非思考模型端点，
  替代当前每脚本手动 `file.exists/json.parse/set_config` 约定。
- 建议 C1-C3 作为真实 LLM e2e 的**前置准备**（使试用配置成为一等机制），C4-C7 随 e2e 阶段完善。

## 四、优先级/分期建议
- **阶段 A（真实 LLM e2e 前置）**：C1 原生加载 + C2 set_config 结构化 + C3 校验诊断。
- **阶段 B（随 e2e 完善）**：C4 env 引用 + C5 mock 配置化 + C6 命名路由 + C7 reasoning/每模型参数。
- **阶段 C（远期）**：C8 容器类型系统；`$schema` 校验基础设施（如有）。

## 五、约束
- 涉及语言/插件功能改动 → code-workflow Phase 0-5 + 全量 pytest 零回归 + general 复核。
- 对外契约（`ai.set_config` 签名）改动默认已授权（破坏性重构授权），详记决策。
- 文档：落地后更新 README（api_config 从"脚本约定"改"一等机制"+ 本地 LLM 快速开始）+ syntax/11（ai 模块）+ KNOWN_LIMITS（如容器类型限制仍存）。

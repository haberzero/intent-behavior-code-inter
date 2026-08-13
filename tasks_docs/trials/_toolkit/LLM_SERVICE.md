# LLM_SERVICE — 本机真实 LLM 服务规范（单一权威源）

> 试用体系以**真实 LLM 为主**（用户裁定，2026-08-13）：本机试用始终利用本机 LLM 服务做
> 真实测试，mock 仅用于无 LLM 依赖的用例。**当前服务非通用化，仅本机有效**；
> 引导其他开发者配置的指导为未来任务（见 §五）。

## 一、本机服务（当前唯一权威端点）

| 项 | 值 |
|----|----|
| 服务类型 | LM Studio 本地推理服务 |
| 端点 | `http://127.0.0.1:1234/v1` |
| 模型 | `qwen3.6-35b-a3b`（非思考模型，reasoning:false） |
| 备用模型 | `text-embedding-nomic-embed-text-v1.5`（embedding，试用不常用） |

## 二、可用性探测（每次试用前必做）

```bash
curl -s -m 5 http://127.0.0.1:1234/v1/models
# 期望 JSON 含 "id": "qwen3.6-35b-a3b"；失败则服务未启动，LLM 用例不可跑
```

试用前未通过探测 → 只跑 mock 用例（`expect-llm: false`），LLM 用例标
`HARNESS`（环境缺失），不误判为缺陷。

## 三、api_config.json 模板（真实 LLM 模式）

```json
{
    "defaults": { "timeout": 30.0, "retry": 3, "auto_intent_injection": true, "mock": false },
    "providers": { "local": { "base_url": "http://127.0.0.1:1234/v1", "api_key": "lm-studio" } },
    "models": { "default": { "provider": "local", "model": "qwen3.6-35b-a3b", "reasoning": false } }
}
```

mock 模式：`defaults.mock: true`（用例无需真实调用时用；无 LLM 依赖用例始终 mock）。

## 四、用例分层与耗时预算

| 层 | 标记 | 耗时 | 运行方式 |
|----|------|------|----------|
| mock | 无 `# expect-llm: true` | <1s/用例 | `run_batch.py <trial> --mock-only --timeout 10` |
| llm | `# expect-llm: true` | 5-30s/用例（真实模型推理） | `run_batch.py <trial> --llm-only --timeout 60` |

- 批量运行**先 mock 后 llm**（`run_batch.py <trial>` 默认顺序），单用例卡住由
  harness 超时 SIGKILL，不影响整批。
- llm 用例断言（`expect-out`）为真实模型期望输出；模型输出非确定，断言取
  稳定可判定的部分（如枚举成员名→值映射、意图注入的关键字），避免整句精确匹配。

## 五、未来任务：引导其他开发者配置（当前只本机）

> 记录为 PENDING_TASKS 待办，不阻塞本机试用。方向：
> 1. 端点/模型参数化（`--provider-url`/`--model` 覆盖，或环境变量）；
> 2. 服务可用性自动探测并生成诊断（`probe` 子命令）；
> 3. 跨平台安装指导（LM Studio / ollama 等）与 api_config 模板分发；
> 4. CI/CD 中 LLM 用例的降级策略（无服务时跳过而非失败）。

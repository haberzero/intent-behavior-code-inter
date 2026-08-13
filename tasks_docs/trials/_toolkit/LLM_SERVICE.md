# LLM_SERVICE — 本机真实 LLM 服务规范（单一权威源）

> 试用体系以**真实 LLM 为主**（用户裁定，2026-08-13）：本机试用始终利用本机 LLM 服务做
> 真实测试，mock 仅用于无 LLM 依赖的用例。**当前服务非通用化，仅本机有效**；
> 引导其他开发者配置的指导为未来任务（见 §五）。

## 一、本机服务（当前唯一权威端点）

| 项 | 值 |
|----|----|
| 服务类型 | LM Studio 本地推理服务 |
| 端点 | `http://127.0.0.1:1234/v1` |
| 模型 | `qwen3.6-35b-a3b`（**实测为强制思考模型**，见 §二.1） |
| 备用模型 | `text-embedding-nomic-embed-text-v1.5`（embedding，试用不常用） |

## 二.1 模型思考模式（实测事实，2026-08-13）

- **qwen3.6-35b-a3b 在 LM Studio 上强制思考**：即使传 `enable_thinking: false` /
  `thinking: {"enabled": false}` / `chat_template_kwargs: {"enable_thinking": false}`
  （全部 API 形态，已逐一实测），模型仍输出 `reasoning_content` 思考，且 `content`
  在 `max_tokens` 被思考吃满时为**空**（`reasoning_tokens` 计数）。**API 参数无法关闭**
  本模型的思考。
- **影响**：每次真实调用有思考 token 开销 + 响应慢（10-30s）；`content` 为空时
  IBCI 回退用 reasoning 提取答案（postprocess 剔除思考块，可靠性依赖模型输出形态）。
- **配置建议**：`reasoning: false` 声明与实际不符时，IBCI 会在运行时发**思考禁用失败警告**
  （一次性去重），引导用户联系开发者 / 提交 issue 并附供应商文档——**不引导用户改配置
  绕开**（掩盖而非解决）。**供应商感知的思考禁用机制（按供应商参数形态禁用/检测失败）为
  开发者待完善项**（登记 PENDING_TASKS），当前仅识别"请求抑制但仍思考"并警告。
- **死机/超时防护**：思考模型响应慢，批量试用用 `run_batch.py`（每用例 harness 超时
  SIGKILL，进程组清理彻底）；避免大量用例并发压爆 LM Studio。

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
- **并发模式**：`run_batch.py <trial> --parallel N`（N=1 串行，默认）。mock 用例可设
  4-8（快、独立）；真实 LLM 用例建议 **1-2**（思考模型响应慢，高并发压爆本地服务——
  曾实测并发压爆导致响应超时/假死）。每用例独立 subprocess + 独立超时，并发下卡死
  互不影响。
- llm 用例断言（`expect-out`）为真实模型期望输出；模型输出非确定，断言取
  稳定可判定的部分（如枚举成员名→值映射、意图注入的关键字），避免整句精确匹配。

## 五、未来任务：引导其他开发者配置（当前只本机）

> 记录为 PENDING_TASKS 待办，不阻塞本机试用。方向：
> 1. 端点/模型参数化（`--provider-url`/`--model` 覆盖，或环境变量）；
> 2. 服务可用性自动探测并生成诊断（`probe` 子命令）；
> 3. 跨平台安装指导（LM Studio / ollama 等）与 api_config 模板分发；
> 4. CI/CD 中 LLM 用例的降级策略（无服务时跳过而非失败）。

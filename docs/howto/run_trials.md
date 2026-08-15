# 如何运行 IBCI 试用套件

> 本文档解决“如何运行 mock 与真实 LLM 试用套件，以及如何接入自己的 API 服务”的问题。
> 面向需要执行 `trials/` 下试用套件的开发者。阅读前需了解 `trials/` 的体系结构（见 `docs/trials/README.md`）。

## 一、准备环境

试用套件使用项目 conda 环境：

```bash
conda activate ibci
```

## 二、运行 mock 批

mock 层不依赖外部服务，先运行以确认工具链与用例契约：

```bash
python trials/_toolkit/run_batch.py trials/T01_llm_full --mock-only --timeout 10
```

参数 `--mock-only` 只运行头部未声明 `# expect-llm: true` 的用例。每个用例由独立子进程执行，
超时后由 harness 强制终止，不影响整批。

## 三、接入自己的 API 服务

真实 LLM 层使用 OpenAI 兼容 API。在试用地基根目录放置 `api_config.json`：

```json
{
    "defaults": { "timeout": 30.0, "retry": 3, "auto_intent_injection": true, "mock": false },
    "providers": { "local": { "base_url": "http://127.0.0.1:1234/v1", "api_key": "lm-studio" } },
    "models": { "default": { "provider": "local", "model": "qwen3.6-35b-a3b", "reasoning": false } }
}
```

字段说明：

| 字段 | 含义 |
|------|------|
| `defaults.mock` | `true` 走 mock 模式；`false` 走真实 API |
| `providers.<name>.base_url` | OpenAI 兼容端点的完整 URL |
| `providers.<name>.api_key` | 服务端要求的 API key |
| `models.default` | 默认模型路由 |

运行前先探测服务可用性：

```bash
curl -s -m 5 http://127.0.0.1:1234/v1/models
```

服务不可达时只运行 mock 用例；真实 LLM 用例会被记为环境缺失，而不是误判为内核缺陷。

## 四、运行真实 LLM 批

```bash
python trials/_toolkit/run_batch.py trials/T01_llm_full --llm-only --timeout 60
```

`--llm-only` 只运行头部声明 `# expect-llm: true` 的用例。`--timeout` 是单用例硬超时（秒），
应大于单次 LLM 调用最坏耗时。`--parallel` 控制并发度：mock 用例可设 4-8；真实 LLM 用例建议 1-2，
避免压垮本地推理服务。

## 五、运行单个用例

```bash
python trials/_toolkit/run_one.py trials/T01_llm_full/cases/D1-01-001-basetypes.ibci \
    --label D1-01-001 --dim D1 --doc "syntax/01_types.md" --expected "基础类型输出" \
    --timeout 60 --root trials/T01_llm_full
```

`--timeout` 必填。harness 在超时后向用例进程组发送 SIGKILL，保证死循环用例也能被终止。

## 六、查看结果

每次运行写入试用地基的 `logs/` 目录：

- `<label>.log`：单次运行完整输出。
- `register.jsonl`：每行一条机械判定记录。

`logs/` 是本地参考分析产物，不纳入版本控制。人工汇总与缺陷登记在 `REGISTER.md` 和
`trials/INDEX.md`。

## 七、常见问题

| 问题 | 处置 |
|------|------|
| 真实 LLM 服务不可达 | 只运行 mock 用例，真实用例标为环境缺失 |
| 用例超时 | 调大 `--timeout`，或检查是否进入死循环 |
| 思考模型响应慢 | 优先使用非思考模式，并降低 `--parallel` |
| 自定义模型输出不稳定 | 断言只匹配稳定可判定的部分，如枚举值、关键字 |

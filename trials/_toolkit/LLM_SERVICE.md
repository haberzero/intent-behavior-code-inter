# LLM_SERVICE — 本机真实 LLM 服务规范（单一权威源）

> 试用体系以**真实 LLM 为主**（用户裁定）：本机试用始终利用本机 LLM 服务做
> 真实测试，mock 仅用于无 LLM 依赖的用例。**当前服务非通用化，仅本机有效**；
> 引导其他开发者配置的指导为未来任务（见 §七）。
>
> **开发试用基线**：**所有开发试用均在本地 `Qwen3.6-35B-A3B`
> 非思考模式下进行**——用例断言、结果分类、文档对齐均以此模式的输出形态为准。
>
> **模型红线（用户裁定）**：本机 LLM 试用只允许 `Qwen3.6-35B-A3B`；
> **禁止使用 `Qwen3.8-27B-NVFP4`**。

## 一、本机服务（当前唯一权威端点）

| 项 | 值 |
|----|----|
| 服务类型 | vLLM OpenAI 兼容服务（强制 Bearer 鉴权，无凭证/错凭证返回 401） |
| 端点 | `http://localhost:8001/v1` |
| API key | **不入版本控制**：trial 各 `api_config.json`（gitignored）承载；命名路由用例经环境变量 `IBCI_TRIAL_LLM_KEY` 读取（见 §五） |
| 允许模型 | `Qwen3.6-35B-A3B`（**非思考模式**，见 §二；模型 ID 以服务端 `/v1/models` 精确大小写为准） |
| 禁止模型 | `Qwen3.8-27B-NVFP4`（本机试用一律不得使用） |

## 二、思考模式（非思考 = 唯一基线）

**当前事实**：服务端为 Qwen3.6 启用了 reasoning parser——思考内容隔离在响应的
`message.reasoning` 字段，`content` 为最终答案。非思考实现 = 请求携带
`chat_template_kwargs: {"enable_thinking": false}`（vLLM 模板变量通道）：实测非思考
响应亚秒级、`reasoning_tokens=0`。顶层 `enable_thinking` 字段会被 vLLM **静默忽略**
（实测仍思考），不能作为关闭手段。

内置默认 provider 同时发送顶层 `enable_thinking=false` 与
`chat_template_kwargs.enable_thinking=false` 两种抑制字段（多后端兼容）；
`api_config.json` 统一配置 `"reasoning": false`。**所有开发试用均在此模式下进行**；
用例断言与结果分类以非思考输出形态为基准。探测/调用检测"请求已抑制但仍思考"时
触发一次性告警（引导联系开发者，不引导改配置绕开）。

**死机/超时防护**：批量试用用 `run_batch.py`（每用例 harness 超时 SIGKILL，进程组清理
彻底）；避免大量用例并发压爆本地服务。

## 三、可用性探测（每次试用前必做）

```bash
python trials/_toolkit/probe.py          # 读发现的 api_config.json，校验端点/鉴权/模型
# 或批量运行时内置预检：run_batch.py <trial> --probe
```

探测未通过（服务未启动/鉴权失败/模型缺失）→ 只跑 mock 用例（`expect-llm: false`），
LLM 用例标 `HARNESS`（环境缺失），不误判为缺陷。

## 四、api_config.json 单源（真实 LLM 模式）

**配置单源 = 仓库根 `api_config.json`**（gitignored）：加载时自 project_root 向上
发现**最近**配置（子目录可放置覆盖配置做差异化），搜索上界 = 含 `.git` 的仓库根
（不拾取仓库外配置）。trial 体系零本地副本；端点/密钥/模型变更只改根配置一份。

```json
{
    "defaults": { "timeout": 30.0, "retry": 3, "auto_intent_injection": true, "mock": false },
    "providers": { "local": { "base_url": "http://localhost:8001/v1", "api_key": "<本机密钥，不入库>" } },
    "models": { "default": { "provider": "local", "model": "Qwen3.6-35B-A3B", "reasoning": false } }
}
```

mock 模式：`defaults.mock: true`（用例无需真实调用时用；无 LLM 依赖用例始终 mock，
现有 mock 用例经 `ai.set_mock_mode()` 显式进入，不依赖配置）。

## 五、命名路由用例的密钥通道

- 硬编码端点凭据的用例（如 T01 `D1-07-006`、T08 `D5-03`）经宿主绑定读取环境变量
  `IBCI_TRIAL_LLM_KEY` 作为密钥——**tracked 用例文件不得包含真实密钥**：

```ibci
import python "os" as oslib:
    bind getenv(key: str) -> str
str key = oslib.getenv("IBCI_TRIAL_LLM_KEY")
ai.register_model("NAME", "http://localhost:8001/v1", key, "Qwen3.6-35B-A3B")
```

- 运行此类用例前导出该变量（本机导出行与本机密钥明文见 `AGENTS.local.md`）。

## 六、用例分层与耗时预算

| 层 | 标记 | 耗时 | 运行方式 |
|----|------|------|----------|
| mock | 无 `# expect-llm: true` | <1s/用例 | `run_batch.py <trial> --mock-only --timeout 10` |
| llm | `# expect-llm: true` | 1-5s/用例（Qwen3.6-35B-A3B 非思考模式推理） | `run_batch.py <trial> --llm-only --timeout 60` |

- 批量运行**先 mock 后 llm**（`run_batch.py <trial>` 默认顺序），单用例卡住由
  harness 超时 SIGKILL，不影响整批。
- **并发模式**：`run_batch.py <trial> --parallel N`（N=1 串行，默认）。mock 用例可设
  4-8（快、独立）；真实 LLM 用例建议 **1-2**（非思考模式单例响应快，但高并发仍可能
  压爆本地服务——曾实测并发压爆导致响应超时/假死）。每用例独立 subprocess + 独立
  超时，并发下卡死互不影响。
- llm 用例断言（`expect-out`）为真实模型期望输出；模型输出非确定，断言取
  稳定可判定的部分（如枚举成员名→值映射、意图注入的关键字），避免整句精确匹配。

## 七、未来任务：引导其他开发者配置（当前只本机）

> 记录为 PENDING_TASKS 待办，不阻塞本机试用。方向：
> 1. 端点/模型参数化（`--provider-url`/`--model` 覆盖，或环境变量）；
> 2. 跨平台安装指导（LM Studio / ollama 等）与 api_config 模板分发；
> 3. CI/CD 中 LLM 用例的降级策略（无服务时跳过而非失败；`--probe` 预检已覆盖本机侧）。

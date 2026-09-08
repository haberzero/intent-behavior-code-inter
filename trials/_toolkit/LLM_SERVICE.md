# LLM_SERVICE — 试用 LLM 服务规范（单一权威源）

> 试用体系以**真实 LLM 为主**（用户裁定）：试用利用 LLM 服务做真实测试，mock 仅用于
> 无 LLM 依赖的用例。本文件是**服务无关的规范**（端点/模型/密钥等本机事实不入库，
> 见本机 `AGENTS.local.md` 本地层）；引导其他开发者配置的指导为未来任务（见 §七）。
>
> **开发试用基线原则**：所有开发试用在**非思考模式**下进行（用例断言、结果分类、
> 文档对齐以该输出形态为准）；所用模型由本机配置声明。

## 一、服务要求（对任意 OpenAI 兼容端点）

| 项 | 要求 |
|----|------|
| 协议 | OpenAI 兼容 `/v1`（chat/completions + embeddings 未来扩展） |
| 鉴权 | Bearer token（无凭证/错凭证必须 401，不得静默放行） |
| 模型 | 非思考基线模型一个（本机模型与红线见 `AGENTS.local.md`） |
| 配置 | 仓库根 `api_config.json`（gitignored，单源向上发现，见 §四） |

## 二、思考模式（非思考 = 唯一基线）

**机制事实（实证）**：非思考实现 = 请求携带
`chat_template_kwargs: {"enable_thinking": false}`（vLLM 模板变量通道）。
**顶层 `enable_thinking` 字段会被 vLLM 静默忽略**（实测仍思考），不能作为关闭手段；
不同后端的字段映射属 provider 实现职责（见 `docs/howto/modify_llm_provider.md`）。

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
本机实际值见 `AGENTS.local.md`；字段单位：**`timeout` 为秒**。

```json
{
    "defaults": { "timeout": 30.0, "retry": 3, "auto_intent_injection": true, "mock": false },
    "providers": { "local": { "base_url": "<OpenAI 兼容端点>", "api_key": "<本机密钥，不入库>" } },
    "models": { "default": { "provider": "local", "model": "<基线模型 ID，以服务端 /v1/models 精确大小写为准>", "reasoning": false } }
}
```

mock 模式：`defaults.mock: true`（用例无需真实调用时用；无 LLM 依赖用例始终 mock，
现有 mock 用例经 `ai.set_mock_mode()` 显式进入，不依赖配置）。

## 五、命名路由用例的密钥通道

- 硬编码端点凭据的用例（如 T01 `D1-07-006`、T08 `D5-03`）经 `ihost.getenv`
  读取环境变量（变量名本机事实见 `AGENTS.local.md`）作为密钥——**tracked
  用例文件不得包含真实密钥**：

```ibci
import ihost
str key = ihost.getenv("<本机环境变量名>")
ai.register_model("NAME", "<端点>", key, "<模型>")
```

- `ihost.getenv(key)` 是宿主 OS 环境变量的一等语言面通道（缺失返回空串）。
  任意宿主 API 仍可经宿主绑定（`import python "os" as oslib: bind getenv(...)`）
  直接访问——`ihost.getenv` 是常用路径的便捷面，绑定是通用底层手段。
- 运行此类用例前导出该变量（本机导出行见 `AGENTS.local.md`）。

## 六、用例分层与耗时预算

| 层 | 标记 | 耗时 | 运行方式 |
|----|------|------|----------|
| mock | 无 `# expect-llm: true` | <1s/用例 | `run_batch.py <trial> --mock-only --timeout 10` |
| llm | `# expect-llm: true` | 1-5s/用例（非思考模式推理） | `run_batch.py <trial> --llm-only --timeout 60` |

- 批量运行**先 mock 后 llm**（`run_batch.py <trial>` 默认顺序），单用例卡住由
  harness 超时 SIGKILL，不影响整批。
- **并发模式**：`run_batch.py <trial> --parallel N`（N=1 串行，默认）。mock 用例可设
  4-8（快、独立）；真实 LLM 用例建议 **1-2**（非思考模式单例响应快，但高并发仍可能
  压爆本地服务——曾实测并发压爆导致响应超时/假死）。每用例独立 subprocess + 独立
  超时，并发下卡死互不影响。
- llm 用例断言（`expect-out`）为真实模型期望输出；模型输出非确定，断言取
  稳定可判定的部分（如枚举成员名→值映射、意图注入的关键字），避免整句精确匹配
  与机器特定值（路径长度/绝对路径等）。

## 七、未来任务：引导其他开发者配置

> 记录为 PENDING_TASKS 待办，不阻塞本机试用。方向：
> 1. 端点/模型参数化（`--provider-url`/`--model` 覆盖，或环境变量）；
> 2. 跨平台安装指导（LM Studio / ollama 等）与 api_config 模板分发；
> 3. CI/CD 中 LLM 用例的降级策略（无服务时跳过而非失败；`--probe` 预检已覆盖本机侧）。

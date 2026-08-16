# LLM_SERVICE — 本机真实 LLM 服务规范（单一权威源）

> 试用体系以**真实 LLM 为主**（用户裁定）：本机试用始终利用本机 LLM 服务做
> 真实测试，mock 仅用于无 LLM 依赖的用例。**当前服务非通用化，仅本机有效**；
> 引导其他开发者配置的指导为未来任务（见 §五）。
>
> **开发试用基线**：**所有开发试用均在本地 `qwen3.6-35b-a3b`
> 非思考模式下进行**——用例断言、结果分类、文档对齐均以此模式的输出形态为准。

## 一、本机服务（当前唯一权威端点）

| 项 | 值 |
|----|----|
| 服务类型 | LM Studio 本地推理服务 |
| 端点 | `http://127.0.0.1:1234/v1` |
| 模型 | `qwen3.6-35b-a3b`（**非思考模式**，见 §二.1） |
| 备用模型 | `text-embedding-nomic-embed-text-v1.5`（embedding，试用不常用） |

## 二.1 模型思考模式（当前：非思考模式为唯一基线）

**当前事实**：本机服务在 LM Studio 界面应用了禁用思考预设（替换提示模板，见 §二.3）
——**不输出 think 标签**（`reasoning_content` 为空、`content` 直接返回），真实调用
响应 **<1-2s**、`reasoning_tokens=0`。`api_config.json` 统一配置 `"reasoning": false`
（见 §三）。**所有开发试用均在此模式下进行**；用例断言与结果分类以此输出形态为基准。

**死机/超时防护**：批量试用用 `run_batch.py`（每用例 harness 超时 SIGKILL，进程组清理
彻底）；避免大量用例并发压爆 LM Studio。

## 二.2 LM Studio 禁用思考模式 — 机制与方案

**官方机制（modelyaml 文档 `https://lmstudio.ai/docs/app/modelyaml`）**：模型的思考由
`model.yaml` 的 `customFields.enableThinking` + Jinja 模板 `enable_thinking` 变量控制：

```yaml
customFields:
  - key: enableThinking
    displayName: Enable Thinking
    description: Controls whether the model will think before replying
    type: boolean
    defaultValue: true
    effects:
      - type: setJinjaVariable
        variable: enable_thinking
```

Jinja 模板须含 `enable_thinking` 变量分支（qwen3-8b 官方示例：`enable_thinking is false`
→ 输出空 `<think> </think>` 标签 = 禁用思考）。

**本机限制**：本地模型目录是**纯 GGUF（无 model.yaml）**，不走官方配置 → API 参数
`enable_thinking` 无效。

**可靠禁用方案**：
1. **（推荐）LM Studio 界面改本机模型 prompt template**：本机模型（qwen3.6-35b-a3b）→
   高级设置 → 提示模板 → 替换为**不含 think 标签**的 Qwen 模板（见 §二.3）→ 重载模型后
   禁用思考生效（不依赖 model.yaml，无下载）。
2. **（官方）从 Hub 添加 qwen3.6-35b-a3b**：用官方 model.yaml（含 enableThinking 开关），
   界面关闭 Enable Thinking；需下载官方 GGUF/MLX（本机 UD 变体与官方 repo 不匹配，
   LM Studio 会重新下载）。
3. **（降级）换非思考模板模型**（如 qwen2.5 系列）。
4. **IBCI 侧**：已传 `enable_thinking: false`（对支持它的模型有效）+ **禁用失败警告**
   （probe/调用检测"请求抑制但仍思考"→ 一次性警告，引导联系开发者/提交 issue，
   不引导用户改配置绕开——见 PENDING_TASKS"供应商感知思考禁用"）。

**机制结论**：在模型目录放 model.yaml（base 用 `type: local` 指向本机 GGUF）
**不被 LM Studio 支持**——model.yaml 规范当前仅 `type: huggingface` source
（`lmstudio-js VirtualModelDefinition` 实证），`type: local` 导致虚拟模型 base 无法解析、
模型从 `lms ls` 消失（删除 model.yaml 后恢复）。

## 二.3 非思考 Qwen 提示模板（LM Studio 界面可粘贴）

```jinja
{{- '<|im_start|>system\n' }}
{%- if system_message %}{{- system_message }}{%- endif %}
{{- '<|im_end|>\n' }}
{%- for message in messages %}
{{- '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n' }}
{%- endfor %}
{%- if add_generation_prompt %}
{{- '<|im_start|>assistant\n' }}
{%- endif %}
```

替换本机模型模板后模型不再输出 think 标签（禁用思考）。

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
| llm | `# expect-llm: true` | 1-5s/用例（qwen3.6-35b-a3b 非思考模式推理） | `run_batch.py <trial> --llm-only --timeout 60` |

- 批量运行**先 mock 后 llm**（`run_batch.py <trial>` 默认顺序），单用例卡住由
  harness 超时 SIGKILL，不影响整批。
- **并发模式**：`run_batch.py <trial> --parallel N`（N=1 串行，默认）。mock 用例可设
  4-8（快、独立）；真实 LLM 用例建议 **1-2**（非思考模式单例响应快，但高并发仍可能
  压爆本地服务——曾实测并发压爆导致响应超时/假死）。每用例独立 subprocess + 独立
  超时，并发下卡死互不影响。
- llm 用例断言（`expect-out`）为真实模型期望输出；模型输出非确定，断言取
  稳定可判定的部分（如枚举成员名→值映射、意图注入的关键字），避免整句精确匹配。

## 五、未来任务：引导其他开发者配置（当前只本机）

> 记录为 PENDING_TASKS 待办，不阻塞本机试用。方向：
> 1. 端点/模型参数化（`--provider-url`/`--model` 覆盖，或环境变量）；
> 2. 服务可用性自动探测并生成诊断（`probe` 子命令）；
> 3. 跨平台安装指导（LM Studio / ollama 等）与 api_config 模板分发；
> 4. CI/CD 中 LLM 用例的降级策略（无服务时跳过而非失败）。

# _REAL_LLM_E2E_PLAN — 基于本地 LLM 服务的真实 e2e 全面试用与高强度批判检测

> 目标（用户 2026-08-11 裁定）：下一阶段不再以 MOCK 系统作为唯一演示/验证手段，需
> **基于可调用的真实 LLM 模型**（本地 LLM 服务）做 IBCI 的**全面试用体验 + e2e 高强度批判检测**。
> 这种真实检测可能暴露更多问题；通过后评估 unsafe-vibe-dev 合并取代 main。
> 设计权威：本文件 + `_MAIN_MERGE_PLAN.md` + `tasks_docs/HANDOFF.md` §二 交接要点。

## 一、为什么需要真实 LLM 检测（背景）
- 现有测试体系（2137 测试）**全部基于 MOCK 模式**（`MOCK:STR/INT/FAIL/SLEEP/REPAIR/AMBIGUOUS` 指令），
  验证的是**确定性执行路径/机制正确性**，不验证**真实 LLM 的格式服从/非确定性/提示词约束**是否成立。
- MOCK 是"零成本、可复现、离线"的工程验证；但 **MOCK 太听话**——真实 LLM 会：
  - 不严格遵守输出格式约束（`-> T` / `__from_prompt__` / 枚举/数字）
  - 在 `llmexcept`/`retry` 下产生非确定性行为、重试节奏、死循环风险
  - 意图注释/`__to_prompt__`/`__outputhint_prompt__` 的实际注入效果与 MOCK 不同
  - 暴露真实 API 客户端（openai sdk 的 base_url/参数/超时/流式）的边界问题
- 用户要求：demo 应能展示**真实 LLM 驱动的真实代码体系**，不只 MOCK。

## 二、本地 LLM 服务搭建（前置准备）
目标：起一个 **OpenAI 兼容**（`/v1/chat/completions`）的本地端点。任选其一（推荐 Ollama 或 LM Studio）：
| 方案 | 默认 base_url | 说明 |
|------|--------------|------|
| **Ollama** | `http://localhost:11434/v1` | `ollama serve` 后 `ollama pull <model>`；`api_key` 任意非空（如 `ollama`） |
| **LM Studio** | `http://localhost:1234/v1` | 本地模型，OpenAI 兼容 server |
| **vLLM / llama.cpp server** | 自定义 | 更专业，可复现性好 |

**⚠️ 模型选择红线（README 已注明）**：**禁止使用思考/推理模型**（尤其本地小尺寸思考模型），
会在 IBCI 提示词约束下陷入"等一等，我再深入思考"的反思死循环。**务必使用非思考（非 reasoning）模型**，
如 `qwen3-8b`（非 thinking 版）、`llama3.1-8b`、`mistral-7b` 等足够强的指令模型。

## 三、IBCI 指向本地服务
方式一（推荐，api_config.json，项目根下）：
```json
{
    "default_model": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen3-8b"
    }
}
```
方式二（脚本内）：
```
import ai
ai.set_config("http://localhost:11434/v1", "ollama", "qwen3-8b")
```
> 可先用最小探针验证连通：`str r = @~ 说你好 ~` 能拿到真实模型回复。

## 四、全面试用（功能遍历）—— 每项用真实 LLM 各跑一遍
按 `docs/SYNTAX_REFERENCE.md` / `docs/syntax/` 逐项：
1. **行为表达式 `@~...~`**：纯文本 / `-> str` / `-> int` / `-> float` / `-> bool` / `-> auto` 类型约束
2. **LLM 函数 `llm ... llmend`**：`__sys__`/`__user__` 段、参数 `$var` 注入、`-> T` 返回解析
3. **提示词协议**：`__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__validate_prompt__`
4. **意图机制**：`@` 意图注释、`@+`/`@-`/`@!`、意图栈、全局意图、`use_intent_context`
5. **AI 容错控制流**：`llmexcept` / `retry` / `ai.set_retry_hint` / 重试耗尽（`LLMRetryExhaustedError`）
6. **行为驱动循环**：`for @~...~` 语义迭代
7. **并发/异步**：`await`、`chan`/`slot`/`subscriber`/`thread`、`ai.run_batch` 批量并发、auto-yield
8. **动态宿主/隔离**：`ihost.spawn_isolated`/`collect`/`run_isolated`
9. **用户类**：构造、继承、`super()`、协议方法、`type()`/`__return_type__()`
10. **生成器**：`yield`/`yield from`/`next()`/`for` 迭代
11. **内建**：`int()/str()/float()/bool()`、`len`/`zip`/`enumerate`/`sorted` 等
12. **异常/健壮性**：`try/except`、`raise`、自定义异常、环境限制

## 五、e2e 高强度批判检测
1. **把既有 MOCK e2e 套件指向真实 LLM**：识别 MOCK 专用用例（依赖 `MOCK:xxx` 指令）与非 MOCK 用例；
   把非 MOCK 的 e2e/契约用例改为配置真实本地端点跑一遍，记录差异（MOCK 能过而真实 LLM 不过的用例 = 真实缺陷候选）。
2. **对抗/批判场景（重点，暴露真实问题）**：
   - **格式服从**：`-> int/float/bool/枚举` 且模型不遵守时，是否稳定报错/重试/收敛（而非死循环）
   - **llmexcept 收敛**：连续不确定时 `retry` 是否能在有限次数内收敛，还是死循环/耗尽
   - **意图注入效果**：`@ 用冷酷口吻` 等意图是否真实影响输出
   - **长提示/复杂 `__to_prompt__`**：对象序列化进提示词的边界
   - **并发真实调用**：`run_batch`/多任务真实并发是否有竞态/阻塞
   - **非确定性**：同一输入多次结果差异是否被语言层正确处理（尤其布尔/数字判断）
   - **超时/网络边界**：本地端点慢/断连时行为
3. **记录纪律**：每个发现记录"代码路径 + 复现脚本 + 期望 vs 实际 + 严重级别"；能自主修复的按 code-workflow 修；
   触及公理/语义/对外契约的登记 PENDING_TASKS 待裁决。

## 六、成功门 / 评估输出
- 全部核心特性真实 LLM 试用通过（无死循环/崩溃/静默错误结果）
- MOCK-vs-真实 差异清单收敛（每个差异有处置：修复/豁免/登记）
- 产出"真实 LLM 验证报告"（通过项 + 暴露问题 + 建议）
- **评估输出**：unsafe-vibe-dev 是否可进入 main 合并（见 `_MAIN_MERGE_PLAN.md`）

## 七、约束（硬原则）
- 全程本地 commit，**禁 push**（除非用户显式授权）
- 破坏性重构按"独立分支 + 零风险直接合并/大风险 cherry-pick"政策
- 工作日志：所有自主决策/方案取舍/验证差异详尽记录于 WORKLOG
- demo 对外宣传以"真实 LLM 驱动"为定位；MOCK 仅作工程验证，不作展示主路径

## 八、执行顺序（下一 session 主任务链）
1. **（前置）PT-FEAT-13 C1-C3 配置机制完备化**（`_API_CONFIG_DESIGN.md`）：原生配置加载（`ai.load_config`/引擎自动，
   替代每脚本 `file/json.parse/set_config` 约定）+ `set_config` 结构化 + 配置校验诊断（fail-fast/诊断码，不静默回退 mock）。
   使本地非思考模型端点配置成为一等机制。
2. **本地 LLM 服务就绪**（§二）+ IBCI 指向（§三）：用新的原生配置声明 `providers.ollama` + `models.local(reasoning:false)`，
   最小探针验证连通。
3. **真实 LLM 全面试用**（§四）。
4. **e2e 高强度批判检测**（§五）。
5. **暴露问题处置 + 验证报告**（§六）→ 评估 unsafe-vibe-dev 是否可进入 main 合并（`_MAIN_MERGE_PLAN.md`）。
6. **文档/README 更新**（`_MAIN_MERGE_PLAN.md` §三 + `_DOC_HEALTH_20260811.md` 剩余 P0/P1）。

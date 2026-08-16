# T08_llm_pressure — LLM 全能力真实压力试用（第一轮）

> 承接主线：IBCI LLM 全能力真实压力试用（本地 qwen3.6-35b-a3b 非思考模式）。
> 目标：以挑刺/对抗态度真实调用本地 qwen3.6-35b-a3b（非思考模式），覆盖直接/间接 LLM 能力，
> 记录缺陷、边界与体验问题；发现可自主修复的缺陷直接根因修复并补回归。
>

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底；无超时不运行 |
| 分层 | mock 用例（快）+ 真实 LLM 用例（qwen3.6-35b-a3b 非思考模式 @ 127.0.0.1:1234，先探测） |
| 记录优先 | logs/ + register.jsonl + REGISTER.md 确定性记录 |
| 修复纪律 | 根因修复 + tests/ 回归 + 文档同步；禁 compat shim / 胶水 / tricky |
| 禁 push | 全程本地 commit |

## 二、试用矩阵（第一轮 41 例）

| 维度 | 覆盖内容 | 用例组 |
|------|----------|--------|
| D1 | 内联行为表达式：类型化输出 / 容器输出 / 表达式语句 / 控制流 | D1-* |
| D2 | 用户协议族：`__from_prompt__` / `__validate_prompt__` / `__outputhint_prompt__` / `__to_prompt__` / `__payload_prompt__` / Enum | D2-* |
| D3 | 批量与意图：`ai.run_batch` 类型化 / 空列表 / 持久与排他意图 / 全局意图 / intent_context / provider 失败 / 容器结果 | D3-* |
| D4 | 命名 LLM 函数：容器返回 / auto / 函数值 / void / 用户类 / llmexcept 真实重试 | D4-* |
| D5 | 流式、路由、并发与间接：stream_call / stream_channel / 命名模型 / 未注册路由 / 线程 / chan / 生成器 / 可观测性 | D5-* |
| D6 | 配置与错误路径：provider 失败捕获 / 缺失配置 / probe / retry 边界 / call_info 空态 / 未读赋值静默 | D6-* |

## 三、结果概览（第一轮）

- 41 例：**32 PASS + 2 GUARD + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT**
- 修复 2 项 KERNEL_ISSUE（LLM 函数容器返回解析、`set_retry(0)` 重试耗尽）
- 发现 1 项 DOC_ISSUE（`@!` + run_batch 文档与实现不一致）
- 发现 2 项 BOUNDARY、1 项已知 LIMIT 复现

## 四、待扩展

- 更多真实 LLM 压力：长 prompt / 超时 / 并发压测 / 多模态 payload 真实媒体文件
- `ai.run_batch` 与线程/生成器深层组合
- 更多配置错误路径与 provider 变体

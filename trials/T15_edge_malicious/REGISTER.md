# REGISTER — T15 恶意边界测试（阶段 C 恶意试用）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。mock 层先行（确定性）。
> 参考规范版本：_toolkit 当前 HEAD。起点清单：`tasks_docs/_trial_edge_catalog.md`。

## 一、总览

- **用例总数**：22 个（mock 19 + 真实 LLM 5 含 PR4 子目录），全部经死循环保护。
- **PASS**：14 例；**GUARD**：7 例；**LIMIT**：1 例。
- **KERNEL_ISSUE**：0 项（本套件；KERNEL_ISSUE-LLM-4 为 T08 回归发现并已修，见 T10/T08 REGISTER）。**BOUNDARY**：0 项。**DOC_ISSUE**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

**无内核缺陷**。16 项恶意边界全部落为 PASS（文档化行为确认）/ GUARD（防御守卫生效）/
LIMIT（文档化限制）。关键确认：

- **fail-fast 防御面**（全部守卫生效）：实参多于/少于声明、声明参数不传参（M6/M14/M16）、
  `__intent__` 层值非列表（M12）、`__retry__` max_retry=0（M13）、协议方法异常传播不吞
  （M7 `__to_prompt__` 抛 → Runtime Error）。
- **文档化限制确认**：深递归 → `RecursionError`（KNOWN_LIMITS §二十三）；容器 `==` 身份比较
  （PT-DEBT-34 文档化）；意图 one-shot `@ 内容` 为**下一条语句窗口**语义（`@` 后接无 LLM
  语句则窗口结束清理，文档 §9.1 约束——M11 初版因此未见 smear，改测 resolve 只读视图）。
- **设计事实**：`ctx.resolve()` 只读持久栈视图（不含 one-shot/smear）且不消费持久意图
  （M11，与 §9.3 只读契约一致）；`__llm_call__` 装配 dict 未知键静默忽略（M5，非 fail-fast，
  登记供文档复核评估是否应告警）；`@!` override 丢弃 smear = 后者覆盖前者（M4，文档 §十三 #2）。

## 三、LIMIT / 待修候选池

| 用例 | 命中文档 | 是否值得修 | 评估 |
|------|----------|-----------|------|
| M8（深递归 RecursionError） | KNOWN_LIMITS §二十三 | 否（设计：trampoline 调用链 + 作用域链 Python 递归） | 维持，文档已列 |

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| M1 | 容器 == 身份比较 | same_ref=False | 同 | PASS | — | logs/B-T15-E-M1.log |
| M2 | 意图值空格 | has_stripped=True | 同 | PASS | — | logs/B-T15-E-M2.log |
| M3 | @- 按值移除 | top_removed=True | 同 | PASS | — | logs/B-T15-E-M3.log |
| M4 | override 丢弃 smear | has_smear=False has_override=True | 同 | PASS | — | logs/B-T15-E-M4.log |
| M5 | 未知装配键忽略 | val=ok | 同 | PASS | — | logs/B-T15-E-M5.log |
| M6 | 多参 fail-fast | too many positional arguments | 同 | GUARD | P2 | logs/B-T15-E-M6.log |
| M7 | 协议异常传播 | Runtime Error: String('boom') | 同 | GUARD | P2 | logs/B-T15-E-M7.log |
| M8 | 深递归（文档化限制） | RecursionError | 同 | LIMIT | P3 | logs/B-T15-E-M8.log |
| M9 | ctx 静态调用静默无效 | has_intent=False | 同 | PASS | — | logs/B-T15-E-M9.log |
| M10 | switch 重复 case | got=1 | 同 | PASS | — | logs/B-T15-E-M10.log |
| M11 | resolve 只读视图 | resolved_has_persistent=True still_persistent=True | 同 | PASS | — | logs/B-T15-E-M11.log |
| M12 | __intent__ 层值非列表 | fail-fast | 同 | GUARD | P2 | logs/B-T15-E-M12.log |
| M13 | __retry__ max_retry=0 | fail-fast | 同 | GUARD | P2 | logs/B-T15-E-M13.log |
| M14 | 少参 fail-fast | fail-fast | 同 | GUARD | P2 | logs/B-T15-E-M14.log |
| M15 | 泛型嵌套特化 | nested_ok=True | 同 | PASS | — | logs/B-T15-E-M15.log |
| M16 | 声明参数不传参 fail-fast | fail-fast | 同 | GUARD | P2 | logs/B-T15-E-M16.log |
| M17 | retry 体内 fs.write 编译期禁（SEM_LLMEXCEPT_FILE_WRITE） | 诊断码 | 同 | GUARD | P2 | logs/B-T15-E-M17.log |
| PR1 | >4k token 长 prompt 真实 LLM | done=True | 同 | PASS | — | logs/B-T15-PR1.log |
| PR2 | __retry__ 多轮 message_history 回喂 | got=3 | 同 | PASS | — | logs/B-T15-PR2.log |
| PR3 | run_batch 批量并发 10 项 | len=10 | 同 | PASS | — | logs/B-T15-PR3.log |
| PR4 | 多模块交叉：跨模块 llm 可调用类直接调用（真实 LLM） | len_gt0=True | 同 | PASS | — | cases/PR4_multimodule/logs/T15-PR4.log |
| PR4b | 跨模块 expected_type=用户类（限定名，__from_prompt__ 生效） | parsed_len_gt0=True | 同 | PASS | — | cases/PR4_multimodule/logs/T15-PR4b.log |
| E18 | [清单 #31] 线程内 LLM 调用 + try/except（并发交叉） | got=7 | 同 | PASS | — | logs/B-T15-E-M18.log |
| E19 | [清单 #28] llmexcept 快照隔离：retry 体内改受保护变量 → 告警 + 黄金快照恢复 | inner_val=0 | 同 | PASS | — | logs/B-T15-E-M19.log |

## 五、结论

- **恶意边界试用（批 1+2，16 项）**：无内核缺陷。fail-fast 防御面扎实（参数数量/装配键值/
  协议异常/retry 策略/__intent__ 层值全部守卫生效）；文档化限制与设计事实被确认/记录。
- **登记待文档复核项**：`__llm_call__` 装配 dict 未知键静默忽略（是否应告警，供阶段 C 末
  文档/诊断评估）。
- **快照隔离确认（E19）**：retry 体内修改 LLM 参与变量（out）→ `RUN_LLMEXCEPT_SNAPSHOT_VIOLATION` 告警（UserWarning）+ 黄金快照恢复（KNOWN_LIMITS §十/§二十 一致，实测）。
- **LLM_BEHAVIOR 观察（PR4b）**：限定 expected_type 名（mod_resp.Resp）会注入 provider
  类型约束提示词，模型可能误echo类型名（本用例输出 mod_resp:ok）——解析契约正确（Resp
  实例），属模型服从度观察，非内核缺陷。
- **下一步**：恶意试用继续扩展（清单其余项：序列化 round-trip/跨引擎/并发/动态宿主/多模块，
  mock 不可确定项留待 LLM 层或专项）；真实 LLM 层全量回归。

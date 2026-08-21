# DESIGN — T15 恶意边界测试（阶段 C 恶意试用 · `_trial_edge_catalog.md` 起点清单）

> **目标**：按 `tasks_docs/_trial_edge_catalog.md` 33 项起点清单设计对抗性用例，带着
> "可能存在缺陷/可能有问题/开发者没考虑到" 的姿态攻击 IBCI 边界。mock 层确定性先行；
> 发现 → 分类（KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LIMIT/GUARD）→ 只记录不修复优先。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建，16 例，对应清单编号）

| 维度 | 清单 # | 边界 | 用例 | 覆盖状态 |
|------|--------|------|------|----------|
| E-M1 | #25 | 容器 == 身份比较（list 无 __eq__） | M1 | ✅ PASS |
| E-M2 | #2 | 意图值空格（strip/子串观测） | M2 | ✅ PASS |
| E-M3 | #3 | @- 无参弹栈 vs 按值移除 | M3 | ✅ PASS |
| E-M4 | #4 | @! override 丢弃 smear（后者覆盖前者） | M4 | ✅ PASS |
| E-M5 | #8 | __llm_call__ 装配 dict 未知键（忽略） | M5 | ✅ PASS |
| E-M6 | #13 | 实参多于声明 → fail-fast | M6 | ✅ GUARD |
| E-M7 | #11 | 协议方法异常传播（__to_prompt__ 抛） | M7 | ✅ GUARD |
| E-M8 | #29 | 深递归 → KNOWN_LIMITS §二十三（LIMIT） | M8 | ✅ LIMIT |
| E-M9 | #7 | intent_context 类静态调用静默无效 | M9 | ✅ PASS |
| E-M10 | #30 | switch 重复 case | M10 | ✅ PASS |
| E-M11 | #1 | ctx.resolve() 只读持久栈视图不消费 | M11 | ✅ PASS |
| E-M12 | #9 | __intent__ 层值非列表 → fail-fast | M12 | ✅ GUARD |
| E-M13 | #10 | __retry__ max_retry=0 → fail-fast | M13 | ✅ GUARD |
| E-M14 | #13 | 实参少于声明 → fail-fast | M14 | ✅ GUARD |
| E-M15 | #26 | 泛型特化嵌套 Box[Box[int]] | M15 | ✅ PASS |
| E-M16 | #13 | 声明参数但调用不传参 → fail-fast | M16 | ✅ GUARD |
| E-M17 | #28 | llmexcept retry 体内 fs.write 编译期禁（SEM_LLMEXCEPT_FILE_WRITE） | M17 | ✅ GUARD |
| PR1-3 | 压力 | >4k token / 多轮 message_history / 批量并发（真实 LLM） | PR1-3 | ✅ PASS |

> 结论：16 项恶意边界**无内核缺陷**——fail-fast 防御面（参数数量/装配键值/协议异常/
> retry 策略/__intent__ 层值）全部守卫生效；文档化限制（递归深度/容器身份比较/意图
> one-shot 语句窗口）被确认。清单其余项（序列化 round-trip/跨引擎/并发/动态宿主/多模块）
> 部分在 mock 层不可确定观测，留待 LLM 层/后续扩展。

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- mock 用例 `# expect-llm: false` + `ai.set_mock_mode()`（确定性）。
- 只记录不修复优先；不为规避缺陷改套件（缺陷触发用例保留）。

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 起点非穷尽：恶意试用须自行扩展清单未列场景。

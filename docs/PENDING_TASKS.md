# PENDING_TASKS（阻塞项与前序依赖项）

> 本文档只保留：
> 1) 被前序任务阻塞；
> 2) 明确属于未来阶段（非当前主线）；
> 3) 暂不执行但需保留追踪的任务。
>
> 当前最高优先任务请见 `docs/NEXT_STEPS.md`。
>
> 最后更新：2026-05-08

---

## A. intent_context 完整对象化（依赖 P0 收敛决策）

- [ ] `intent_context` 作为函数参数类型的全链路强化（语义、提示、测试）
- [ ] `intent_context` 作为函数默认上下文输入的统一约定
- [ ] 更复杂上下文操作（merge/use/fork 组合策略）的正式规范化

---

## B. DynamicHost / 多解释器后续（依赖隔离策略统一）

- [ ] 子解释器插件注册边界与可见性统一
- [ ] HOST breakpoint 能力统一入口
- [ ] 子解释器变量深拷贝隔离策略补完

---

## C. 运行时基础设施（依赖主线稳定后再推进）

- [ ] ImmutableArtifact `__deepcopy__`
- [ ] LLM 输出持久化机制
- [ ] llmexcept 重试历史追踪（frame history）
- [ ] llmexcept 最大嵌套深度保护

---

## D. 语法与插件中长期项

- [ ] `(str n) @~ ... ~` 边界行为完善
- [ ] llmretry 后缀语义补全
- [ ] 插件显式引入完整实现（剩余清理）
- [ ] 模块符号去重机制

---

## E. 已解决（迁出说明）

- MetadataRegistry 双轨统一已完成，不再作为 pending。

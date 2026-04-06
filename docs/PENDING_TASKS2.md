# LLM Retry 机制长期改进计划

> 本文档记录 LLM Retry 机制的长期改进方向和具体待办事项。

## 概述

IBCI 语言的 LLM Retry 机制经历了多次迭代演进：

1. **阶段 0**: 无 retry 机制，LLM 调用失败直接抛出异常
2. **阶段 1**: Python try-except 模拟 retry，逻辑分散在各处
3. **阶段 2**: `_with_unified_fallback` 统一包装器（隐式 fallback）
4. **阶段 3**: `IbLLMExceptionalStmt` AST 节点 + `LLMExceptFrame` 帧栈（显式语法）

当前正处于 **阶段 3** 的实现初期，本文档记录后续需要完善的方向。

---

## 一、核心框架完善

### 1.1 LLMExceptFrame 状态保存/恢复

**状态**: 已创建框架，待完善实现

**待办**:
- [ ] **TODO [优先级: 高]**: 实现完整的变量快照机制
  - 当前 `save_context()` 仅保存了 intent 栈引用
  - 需要实现变量的深拷贝/序列化
  - 考虑支持不可变对象的引用共享优化

- [ ] **TODO [优先级: 高]**: 实现完整的变量恢复机制
  - 当前 `restore_context()` 为空实现
  - 需要恢复所有保存的变量值
  - 考虑常量保护机制

- [ ] **TODO [优先级: 中]**: Loop 上下文保存/恢复
  - 当前 `saved_loop_context` 需要完善
  - 需要正确恢复 `for` 循环的迭代器状态

### 1.2 重试策略增强

**待办**:
- [ ] **TODO [优先级: 中]**: 支持重试策略配置
  - 固定次数重试（当前实现）
  - 指数退避（Exponential Backoff）
  - 固定延迟（Fixed Delay）
  - 抖动（Jitter）支持

- [ ] **TODO [优先级: 低]**: 重试条件表达式
  - 支持基于错误类型的条件重试
  - `retry if error.type == "rate_limit"`

### 1.3 帧栈完整性

**待办**:
- [ ] **TODO [优先级: 高]**: 确保帧栈平衡
  - 添加 `__enter__`/`__exit__` 上下文管理器支持
  - 添加异常时帧栈清理的断言检查

- [ ] **TODO [优先级: 中]**: 嵌套 llmexcept 支持
  - 当前假设无嵌套，未来需支持
  - 需要确保正确的作用域隔离

---

## 二、架构迁移

### 2.1 _with_unified_fallback 迁移

**状态**: 暂保留用于隐式 fallback

**待办**:
- [ ] **TODO [优先级: 中]**: 评估是否将 `_with_unified_fallback` 迁移到帧栈
  - 优点: 统一机制，更易维护
  - 缺点: 可能影响现有行为

- [ ] **TODO [优先级: 低]**: 移除 `node_data.llm_fallback` 属性
  - 完全迁移到 `IbLLMExceptionalStmt` AST 节点

### 2.2 visit_IbWhile/For 中的隐式 fallback 迁移

**当前状态**: `visit_IbWhile/For` 使用硬编码的 fallback 逻辑

**待办**:
- [ ] **TODO [优先级: 中]**: 评估是否支持 `while/for` 的显式 `llmexcept`
  - `while @~condition~: llmexcept: retry()`
  - 需要语义分析验证语法正确性

---

## 三、语义分析增强

### 3.1 llmexcept 目标验证

**当前状态**: 基础验证已实现

**待办**:
- [ ] **TODO [优先级: 中]**: 验证 `llmexcept` 目标确实包含 LLM 调用
  - 当前仅验证包含 `@~` 语法
  - 未来可检查是否调用了 `IbLLMFunction`

- [ ] **TODO [优先级: 低]**: 验证 `llmexcept` 不在非法位置
  - 例如: 函数定义内部、lambda 内部等

### 3.2 作用域规则

**待办**:
- [ ] **TODO [优先级: 中]**: 完善 llmexcept 的作用域规则文档
  - 变量修改在 retry 时的行为
  - 意图栈的隔离/共享策略

---

## 四、错误处理与诊断

### 4.1 重试日志

**待办**:
- [ ] **TODO [优先级: 中]**: 添加重试事件的详细日志
  - 当前帧状态
  - 重试次数
  - 错误原因

- [ ] **TODO [优先级: 中]**: 支持重试历史的查询 API
  - 用于调试和分析

### 4.2 错误聚合

**待办**:
- [ ] **TODO [优先级: 低]**: 支持收集多次重试的错误信息
  - 当前仅保存最后一个错误
  - 未来可保存错误历史用于分析

---

## 五、性能优化

### 5.1 变量快照优化

**当前问题**: 每次 retry 都进行完整变量快照，可能较慢

**待办**:
- [ ] **TODO [优先级: 中]**: 实现增量快照
  - 只记录变化的变量
  - 使用写时复制（Copy-on-Write）优化

- [ ] **TODO [优先级: 低]**: 添加快照性能指标

### 5.2 意图栈优化

**待办**:
- [ ] **TODO [优先级: 低]**: 意图栈的结构共享优化
  - 当前使用链表实现
  - 可考虑持久化数据结构

---

## 六、测试覆盖

### 6.1 单元测试

**待办**:
- [ ] 为 `LLMExceptFrame` 添加单元测试
- [ ] 为 `RuntimeContextImpl.llm_except_*` 方法添加单元测试
- [ ] 测试各种边界情况（嵌套、并发等）

### 6.2 集成测试

**待办**:
- [ ] 创建 `verify_loop_retry_fix.ibci` 的正确版本（修复 triple quotes 问题）
- [ ] 测试显式 `llmexcept` 的各种用法

---

## 七、文档完善

### 7.1 用户文档

**待办**:
- [ ] 编写 `llmexcept` 语法说明文档
- [ ] 编写 `retry` 语句语法说明文档
- [ ] 添加使用示例和最佳实践

### 7.2 开发者文档

**待办**:
- [ ] 更新 `ARCHITECTURE_PRINCIPLES.md` 说明新的帧栈机制
- [ ] 添加 LLMExceptFrame 的 API 文档
- [ ] 记录设计决策和替代方案

---

## 八、技术债务清理

### 8.1 清理旧代码

**待办**:
- [ ] 移除 `IbStmt.supports_llm_fallback` 属性（已废弃）
- [ ] 移除 `IbStmt.llm_fallback` 属性（已废弃）
- [ ] 移除 `_fallback_stack`（如不再需要）

### 8.2 注释清理

**待办**:
- [ ] 移除所有 `TODO [优先级: 高]: 完成后移除此注释` 的注释
  - 在功能完全实现后删除这些提示性注释

---

## 优先级排序

按优先级排序的待办事项：

### 高优先级 (P0)
1. [x] 创建 `LLMExceptFrame` 和 `LLMExceptFrameStack` 框架
2. [x] 扩展 `RuntimeContextImpl` 添加现场管理方法
3. [x] 重构 `visit_IbLLMExceptionalStmt` 使用新框架
4. [ ] **实现完整的变量快照机制**
5. [ ] **实现完整的变量恢复机制**

### 中优先级 (P1)
6. [ ] 支持重试策略配置
7. [ ] Loop 上下文保存/恢复
8. [ ] 重试事件详细日志
9. [ ] 增量快照优化

### 低优先级 (P2)
10. [ ] 重试条件表达式
11. [ ] 错误聚合历史
12. [ ] 意图栈优化

---

## 版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-04 | v0.1 | 初始版本，记录框架设计和长期改进计划 |

---

## 参考资料

- [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) - 架构原则
- [PENDING_TASKS.md](./PENDING_TASKS.md) - 原始待办任务文档
- `core/runtime/interpreter/llm_except_frame.py` - 帧栈实现
- `core/runtime/interpreter/runtime_context.py` - 运行时上下文
- `core/runtime/interpreter/handlers/stmt_handler.py` - 语句处理器

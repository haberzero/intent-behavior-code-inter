# IBC-Inter 重构与改进日志 (Refactoring Log)

## 目标
1.  **领域对象规范化**：引入 `IbIntent` 消除意图系统的碎片化。
2.  **类型语义解耦**：解决 `BehaviorType` 向 LLM 泄露内部术语的问题。
3.  **代码逻辑净化**：移除 `llm_executor` 中的兼容性补丁。

## 执行记录

### Phase 1: 意图系统重构 (Intent System Refactoring)
- [x] 定义 `core.runtime.objects.intent.IbIntent` 类。
- [x] **[Fix]** 将 `IbIntent` 升级为 `IbObject` 子类，并在 `Bootstrapper` 中注册 `Intent` 类。
- [x] 更新 `core.runtime.interpreter.interpreter.py` 使用 `IbIntent`。
- [x] 更新 `core.runtime.interpreter.runtime_context.py` 使用 `IbIntent`。
- [x] 验证：意图栈的压入与弹出逻辑。

### Phase 2: 类型系统优化 (Type System Optimization)
- [x] 修改 `core.domain.symbols.StaticType`，增加 `prompt_name` 属性。
- [x] 修改 `core.domain.symbols.BehaviorType`，覆盖 `prompt_name`。
- [x] 更新 `core.compiler.semantic.passes.semantic_analyzer.py`，在生成 `node_to_type` 时使用 `prompt_name`。

### Phase 3: 执行器清理 (Executor Cleanup)
- [x] 重构 `core.runtime.interpreter.llm_executor.py`：
    - 移除 `_merge_intents` 中的类型检查 hack。
    - 移除类型注入时的 `behavior` 过滤 hack。

### Phase 4: 回归测试 (Regression Testing)
- [x] 运行 `intent_stacking.ibci` 验证意图叠加与 Override。
- [x] 运行 `basic_ai.ibci` 验证类型提示词是否正常。

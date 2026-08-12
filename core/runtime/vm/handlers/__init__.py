"""
core.runtime.vm.handlers — CPS 节点处理器包。

每个 ``vm_handle_<NodeType>`` 是一个 **生成器函数**，遵循以下契约：

* ``yield child_uid``        —— 挂起当前任务，调度器会启动 ``child_uid`` 的求值；
                                 求值完成后通过 ``generator.send(result)`` 把结果送回
* ``return value``           —— 任务完成，``value`` 通过 ``StopIteration.value``
                                 传给调用方
* ``return Signal(kind, v)`` —— 触发控制流信号：调度器识别
                                 ``StopIteration.value`` 是 :class:`Signal` 时，
                                 把 Signal 通过 ``gen.send(Signal)`` 传给父帧；
                                 父 handler 用 ``isinstance(res, Signal)`` 检查
                                 是否拦截/继续传播

handler 形参：
    ``executor`` —— :class:`VMExecutor` 实例，提供 ``ec`` / ``runtime_context``
                    / ``registry`` / ``service_context`` 等访问入口

**多语句容器的信号检查约定**：
``IbModule`` / ``IbIf`` / ``IbWhile`` 这类包含子语句序列的 handler，每次
``yield stmt_uid`` 后必须检查返回值是否为 ``Signal``：循环 handler 自行
消费 BREAK/CONTINUE，其余信号（RETURN/THROW）和非循环 handler 应通过
``return res`` 把信号继续向上传播。

**llmexcept 保护机制**：
llmexcept 统一通过 AST 字段 ``llmexcept_handler`` 挂载到被保护语句
（``IbAssign`` / ``IbIf`` / ``IbWhile`` / ``IbFor`` / ``IbSwitch`` / ``IbExprStmt``），
被保护语句从 body 中正常执行，llmexcept 语句本身不入 body。

运行期：各被保护语句 handler 求值条件 / RHS 后，检查返回值是否为
``IbLLMCallResult(is_certain=False)`` 不确定容器；有 handler 时创建
``LLMExceptFrame`` 并内联执行 handler body + 完整多轮重试（见
``_shared._retry_llm_uncertain``），无 handler 时抛出 ``LLMParseError``。

所有 llmexcept 触发路径均通过 AST 字段（llmexcept_handler）显式建立，
不再有侧表间接关联，也不存在 ``IbLLMExceptionalStmt`` 包装节点。

本包按节点类别组织为子模块；公共 API 保持不变：

* :func:`build_dispatch_table`
* :func:`build_one_shot_intent_from_annotation`
"""
from core.runtime.vm.handlers._shared import (
    build_one_shot_intent_from_annotation,
)
from core.runtime.vm.handlers.dispatch import (
    build_dispatch_table,
)

__all__ = [
    "build_dispatch_table",
    "build_one_shot_intent_from_annotation",
]
